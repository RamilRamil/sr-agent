# Data Model: SR-agent

*Phase 1 output for `/speckit-plan`. Entities from spec.md + research decisions.*

---

## Core Entities

### MemoryRecord

Единица хранения в Episodic Memory. Каждая запись HMAC-подписана оркестратором.

```python
@dataclass
class MemoryRecord:
    # Identity
    record_id: str                  # UUID, генерируется оркестратором
    project_id: str                 # изоляция по проекту
    target: str                     # файл или функция: "Vault.sol" / "Vault.sol:withdraw"

    # Provenance (оркестратор заполняет, LLM не меняет)
    source_type: SourceType         # human_input | tool_output | external_llm_output
                                    #   | human_relayed_tool | llm_inference
    tool: str | None                # "read_file", "run_slither", etc. — если source=tool_output
    session_id: str                 # UUID текущей сессии

    # Timing
    timestamp: datetime             # UTC, ISO 8601

    # Content — строго структурированное (не raw text)
    finding: Finding | None         # если это находка
    checkpoint: Checkpoint | None   # если это checkpoint стадии
    status_change: StatusChange | None  # если это изменение статуса

    # Supersedes chain (append-only correction)
    supersedes: str | None          # record_id предыдущей записи, которую эта отменяет
                                    # только source_type=human_input может установить

    # Integrity
    hmac: str                       # HMAC-SHA256(все поля выше, secret_key)
                                    # secret_key известен только оркестратору
```

**Validation rules**:
- `supersedes` → требует `source_type == human_input`
- `status` в `{verified_safe, skip_analysis, audit_complete}` → требует `source_type == human_input`
- `hmac` пересчитывается оркестратором при записи, проверяется при чтении
- Записи с невалидным HMAC → silent drop, не попадают в LLM context

**State transitions** (Finding.status):
```
open → [human confirms PoC]     → confirmed
open → [PoC uses mock patterns] → mock_review
open → [PoC fails]              → unverified
open → [multiple checks clean]  → false_positive
mock_review → [human validates] → confirmed
mock_review → [human rejects]   → false_positive
unverified  → [manual review]   → confirmed | false_positive
```

---

### Finding

Структурированная находка безопасности. Хранится внутри MemoryRecord. Строгая enum-схема предотвращает инъекцию через поля.

```python
@dataclass
class Finding:
    finding_id: str                 # "CRIT-001", "HIGH-002", etc.
    location: str                   # "Vault.sol:47" — путь:строка
    function_name: str              # "withdraw"

    # Classification
    bastet_tag: BastetTag | None    # enum из 46 тегов Bastet датасета
    severity: Severity              # critical | high | medium | low | informational
    status: FindingStatus           # confirmed | mock_review | unverified | false_positive

    # AttackPathGNN preconditions (12 total: 8 GNN + 4 DeFi)
    preconditions: dict[int, bool]  # {1: True, 2: False, ...} — precondition_id → active
    mitigations_present: list[str]  # ["reentrancy_guard", "checks_effects_interactions"]

    # Evidence
    poc_path: str | None            # "tests/poc/CRIT-001-reentrancy.sol"
    poc_status: PoCStatus | None    # passed | failed | mock_review

    # Chain
    combined_with: list[str] | None # finding_ids из Stage 3 combination analysis
```

**Validation rules (Guardrails conjunction check)**:
- `len(active_preconditions) >= 4 AND NOT mitigations_present` → severity must be >= high
- `ANY mitigation in mitigations_present` → severity must be <= medium
- Violation → Guardrails overrides with `SeverityVerdict`, logs correction

---

### Action

Действие, которое агент запрашивает у оркестратора. Никогда не выполняется до валидации.

```python
@dataclass
class Action:
    action_id: str                  # UUID
    action_type: ActionType         # read_file | search_code | build_graph
                                    # | run_slither | run_mythril | run_auditor_skill
                                    # | analyze_transactions | decompile_bytecode
                                    # | write_poc | run_tests | deploy_test_contract
                                    # | write_memory | request_human_confirmation
    params: dict                    # типизированы per action_type (не произвольные строки)

    # Classification
    action_class: ActionClass       # read_only | write_execute
    is_reversible: bool             # False для write_execute

    # Validation (заполняет оркестратор)
    validation_status: ValidationStatus | None  # pending | approved | rejected
    rejection_reason: str | None
    human_confirmation: bool | None  # None = не требуется
```

**Validation rules**:
- `action_type` must be in `TOOL_REGISTRY` whitelist
- `params` validated against per-tool parameter schema (FilePath exists, enum values valid, etc.)
- `action_class == write_execute` → requires human out-of-band confirmation
- Rejected actions → logged as blocked attempt with reason

---

### Principal

Субъект, в контексте которого работает агент. Определяет границу изоляции памяти.

```python
@dataclass
class Principal:
    user_id: str                    # уникальный идентификатор пользователя
    platform: str                   # "cli" | "api" | "webhook"
    project_id: str                 # комбинация user_id + target_repo
```

**Invariant**: Все MemoryRecord.project_id должны совпадать с текущим Principal.project_id. Оркестратор проверяет до HMAC verify.

---

### AuditInput

Входные данные для запуска аудита. Валидируется оркестратором до старта.

```python
@dataclass
class AuditInput:
    # Source (один или оба)
    path: Path | None               # директория с .sol файлами
    address: str | None             # EIP-55 checksum адрес контракта

    # Scope
    exclude_paths: list[Path]       # директории вне scope
    focus_files: list[Path]         # если задан — только эти файлы
    include_imports: bool           # включать ли OpenZeppelin / Uniswap в SIG

    # Principal
    principal: Principal

    # Resume
    resume_session_id: str | None   # продолжить прерванную сессию
```

**Validation rules**:
- `path` must exist and contain at least one `.sol` file
- `address` must be valid EIP-55 checksum address
- At least one of `path` or `address` must be provided
- `path` must not escape allowed root directory

---

### AuditSession

Состояние текущей сессии. Checkpoint сохраняется в Episodic Memory после каждой завершённой цели.

```python
@dataclass
class AuditSession:
    session_id: str
    principal: Principal
    audit_input: AuditInput
    started_at: datetime

    # Stage progress
    current_stage: int              # 1 | 2 | 3
    stage1_report: Stage1Report | None
    stage2_completed: list[str]     # target names
    stage2_remaining: list[str]
    stage3_completed: list[str]     # combination keys

    # Findings
    finding_ids: list[str]          # все finding_ids текущей сессии

    # Resources
    token_budget_used: int
    iterations: int
```

---

### Checkpoint

Детерминированный snapshot состояния на границе стадий. Создаётся оркестратором (не LLM).

```python
@dataclass
class Checkpoint:
    stage: int
    completed_at: datetime
    files_analyzed: list[str]       # список файлов, не summary
    finding_ids: list[str]          # ссылки на MemoryRecord.finding_id
    high_priority_locations: list[str]
    skipped: list[SkipReason]       # явные причины пропуска
    source_type: Literal["orchestrator"]  # всегда orchestrator, не llm_inference
```

---

### AttackScenario

Воспроизводимый сценарий MI-атаки для тестирования ASR. Используется в `tests/security/`.

```python
@dataclass
class AttackScenario:
    scenario_id: str
    attack_type: str                # "exfiltration" | "verdict_suppression" | "status_override"
    malicious_record: dict          # запись для инъекции в Episodic Memory
    trigger_query: str              # запрос, активирующий инъекцию
    expected_blocked_action: str    # действие, которое НЕ должно выполниться
    baseline_asr_pct: float         # ожидаемый ASR без защиты (из 2503.16248v3)
```

---

## Enum Definitions

```python
class SourceType(str, Enum):
    HUMAN_INPUT = "human_input"
    TOOL_OUTPUT = "tool_output"
    EXTERNAL_LLM_OUTPUT = "external_llm_output"
    HUMAN_RELAYED_TOOL = "human_relayed_tool"
    LLM_INFERENCE = "llm_inference"

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"

class FindingStatus(str, Enum):
    CONFIRMED = "confirmed"
    MOCK_REVIEW = "mock_review"
    UNVERIFIED = "unverified"
    FALSE_POSITIVE = "false_positive"

class ActionClass(str, Enum):
    READ_ONLY = "read_only"
    WRITE_EXECUTE = "write_execute"

class ValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

REQUIRES_HUMAN_CONFIRMATION: set[str] = {
    "verified_safe",
    "skip_analysis",
    "audit_complete",
    "previously_reviewed",
}

TRUST_LEVELS: dict[SourceType, int] = {
    SourceType.HUMAN_INPUT:          4,
    SourceType.TOOL_OUTPUT:          3,
    SourceType.EXTERNAL_LLM_OUTPUT:  2,
    SourceType.HUMAN_RELAYED_TOOL:   2,
    SourceType.LLM_INFERENCE:        1,
}
```

# Implementation Plan: SR-agent — Secure Memory Agent

**Branch**: `001-secure-memory-agent` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-secure-memory-agent/spec.md`

## Summary

Модульный security-агент для аудита смарт-контрактов с архитектурной защитой против Memory Injection (MI) атак. Защита строится в Orchestration Plane (детерминированный код): HMAC-подписи на каждой записи памяти, source_type иерархия, human gate для критических статусов, append-only log, structured JSON outputs. MVP демонстрирует воспроизводимую устойчивость к MI (ASR ≤5% против базового ≥40%) через 3-стадийный аудитный цикл (Discovery → CheckRunner → Synthesis).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- `anthropic` — Claude Opus API (Stage 1/3, extended thinking)
- `ollama` / `llama-cpp-python` — локальная Qwen3-4B fine-tuned (Stage 2), в Docker
- `slither-analyzer` — статический анализ Solidity
- `mythril` — символьное выполнение
- `foundry` / `anvil` — PoC тесты, локальный EVM (Solidity-only тесты)
- `docker` SDK — изолированные sandbox контейнеры
- `web3.py` + Alchemy RPC — on-chain данные, archive node, trace API
- Tenderly API — симуляция эксплойтов на mainnet fork
- `cryptography` (stdlib `hmac`) — HMAC-SHA256 подписи памяти
- `langfuse` SDK — LLM observability, prompt management, eval datasets (self-hosted)

**Storage**:
- Knowledge Base: директория `knowledge/` (JSONL + Markdown, HMAC на файлах, human writes only)
- Episodic Memory: `memory/{project_id}/{target}.jsonl` (HMAC-подписанные append-only записи)
- In-context: Python dataclasses в памяти процесса (текущая сессия)
- Langfuse: self-hosted Postgres + ClickHouse (трейсы, промпты, eval датасеты — изолированы от агентной памяти)

**Testing**: `pytest` (unit + integration + security/MI scenarios) + `forge test` (PoC Solidity тесты)

**Target Platform**: Linux/macOS developer workstation

**Project Type**: CLI tool (`sr-agent audit ...`) + Python library (импортируемые модули)

**Performance Goals**:
- Полный цикл Stage 1→2→3 для 10-20 контрактного протокола: ≤30 мин
- Stage 2 CheckRunner per target (Qwen3-4B local): ≤2 мин
- HMAC verify при чтении: O(1), <1 мс

**Constraints**:
- Extended thinking включён на ВСЕХ Stage 1 и Stage 3 вызовах (требование безопасности, не опция)
- Qwen3-4B должен помещаться на consumer GPU (≤8GB VRAM, Q4_K_M quant)
- Docker обязателен для Slither/Mythril/Foundry sandbox
- LLM не имеет доступа к `update_memory` / `delete_memory` — только `write_memory`
- Все tool outputs оборачиваются в `[DATA START]...[DATA END]` до попадания в LLM

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Конституция проекта (`/.specify/memory/constitution.md`) содержит шаблон без заполненных принципов. Формальные gates не определены. Специфические требования безопасности взяты напрямую из спецификации:

| Gate | Status | Note |
|------|--------|------|
| LLM не может инициировать необратимое действие напрямую | PASS | WRITE/EXECUTE tools требуют out-of-band подтверждения (FR-016) |
| Память подаётся только через [DATA] обёртку | PASS | Оркестратор контролирует контекст (FR-003) |
| Все записи памяти HMAC-подписаны | PASS | Подписывает только оркестратор (FR-014) |
| LLM не пишет в память напрямую | PASS | Только через схему + оркестратор (FR-006) |
| Нет `run_command(cmd: str)` — только типизированные инструменты | PASS | Узкие параметры, enum-детекторы (FR-007, FR-008) |

**Действие**: Заполнить конституцию принципами проекта до фазы задач (`/speckit-tasks`).

## Project Structure

### Documentation (this feature)

```text
specs/001-secure-memory-agent/
├── plan.md           # This file
├── research.md       # Phase 0 output — технические решения
├── data-model.md     # Phase 1 output — сущности, поля, переходы статусов
├── contracts/        # Phase 1 output — CLI schema, модульные интерфейсы
│   ├── cli.md        # CLI команды и флаги
│   ├── memory.md     # MemoryRecord schema, orchestrator contract
│   ├── tools.md      # Tool registry contract, parameter schemas
│   └── llm-core.md   # Model routing contract, structured output schema
├── quickstart.md     # Phase 1 output — установка и первый запуск
└── tasks.md          # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code

```text
sr_agent/
├── __main__.py          # Entry point: `python -m sr_agent`
├── cli.py               # Click/Typer CLI: audit, demo-attack, resume
├── orchestrator/
│   ├── loop.py          # Главный агентный цикл (ReAct dispatch)
│   ├── action.py        # Action validation, whitelist enforcement
│   ├── context.py       # Context window management, [DATA] wrapping
│   └── checkpoint.py    # Stage checkpoint save/load
├── memory/
│   ├── hmac.py          # HMAC-SHA256 sign/verify (orchestrator-only key)
│   ├── episodic.py      # JSONL append-only store, load(project_id, target)
│   ├── knowledge.py     # Knowledge Base reader, 3-model retrieval pipeline
│   └── models.py        # MemoryRecord, Checkpoint dataclasses
├── tools/
│   ├── registry.py      # TOOL_REGISTRY, description hash verification
│   ├── readonly.py      # read_file, search_code, build_graph, run_slither, ...
│   ├── write_execute.py # write_poc, run_tests, deploy_test_contract
│   ├── onchain.py       # analyze_transactions, decompile_bytecode (Alchemy)
│   └── sandbox.py       # Docker ephemeral container management
├── guardrails/
│   ├── severity.py      # Conjunction check, SCB correction
│   ├── mock_detect.py   # Static MOCK_PATTERNS scan
│   ├── sanitize.py      # Unicode normalization, encoding flags
│   └── escalation.py    # ESCALATION_TRIGGERS evaluation
├── planner/
│   ├── stage1.py        # Discovery ReAct loop, SIG prioritization
│   ├── stage2.py        # CheckRunner deterministic for-loop
│   ├── stage3.py        # Synthesis ReAct, SIG-filtered combinations
│   └── sig.py           # State Interference Graph builder
├── llm_core/
│   ├── router.py        # Model selection by task type
│   ├── claude_client.py # Anthropic API, extended thinking
│   ├── local_client.py  # Ollama/llama.cpp wrapper for Qwen3-4B
│   └── file_bridge.py   # External LLM file bridge reader
├── io/
│   ├── input_val.py     # FilePath, EIP-55 address validation
│   ├── progress.py      # Progress stream, checkpoint events
│   └── report.py        # Markdown report generator
└── models/              # Shared Pydantic schemas
    ├── finding.py       # Finding, FindingStatus, Severity
    ├── memory.py        # MemoryRecord, SourceType, TrustLevel
    ├── action.py        # Action, ActionClass, ValidationResult
    └── audit.py         # AuditInput, AuditSession, Principal

tests/
├── unit/
│   ├── test_hmac.py
│   ├── test_conjunction_check.py
│   ├── test_mock_detect.py
│   └── test_tool_registry.py
├── integration/
│   ├── test_memory_write_read.py
│   ├── test_action_validation.py
│   └── test_stage2_loop.py
└── security/
    ├── mi_scenarios.py        # Воспроизводимые MI-атаки (из 2503.16248v3)
    ├── test_mi_resistance.py  # ASR measurement с защитой и без
    └── fixtures/
        ├── malicious_memories.jsonl
        └── trigger_queries.txt

knowledge/                    # Knowledge Base (human-maintained, read-only for agent)
├── vulnerability-patterns/
│   ├── reentrancy.md
│   ├── oracle-manipulation.md
│   └── mev-patterns.md
├── methodology/
│   ├── audit-phases.md
│   └── preconditions.md
└── taxonomy/
    └── bastet-tags.md

memory/                       # Runtime episodic memory (gitignored)
data/
└── finetune/
    ├── train.jsonl           # Fine-tuning dataset (Bastet + Hermes FC + MI rejections)
    └── val.jsonl
adapters/
└── qwen3-4b-stage2/          # LoRA adapter weights (gitignored)
scripts/
├── demo_attack.sh            # Запуск `sr-agent demo-attack` одной командой
└── finetune/
    ├── prepare_dataset.py    # Bastet + Hermes FC → ShareGPT формат
    ├── generate_mi_rejections.py  # Synthetic MI rejection examples
    ├── finetune_stage2.py    # Unsloth + QLoRA training
    ├── eval_finetune.py      # ASR comparison before/after
    └── Modelfile             # Ollama Modelfile для sr-stage2
```

**Structure Decision**: Single project. CLI tool + importable modules. Без frontend/backend split — все в одном процессе.

## Complexity Tracking

| Компонент | Почему нужен | Почему упрощение не подходит |
|-----------|-------------|------------------------------|
| Orchestration Plane separation | Без детерминированного слоя защиту нельзя формально верифицировать | LLM не может сама себя защитить — это математически показано в 2503.16248v3 |
| 3-стадийный pipeline (Stage 1/2/3) | Stage 1 (open-ended ReAct) и Stage 2 (deterministic checklist) требуют разных стратегий | Один ReAct делает Stage 2 непредсказуемым и дорогим |
| HMAC + source_type + human gate | Три независимых механизма защиты разных векторов | Каждый механизм закрывает свой вектор: tamper / intra-session injection / privilege escalation |
| Dual model routing (Claude Opus + Qwen3-4B local) | Stage 2 на Opus = ~$0.22/аудит минимум; fine-tuned 4B = $0 + ASR 1.7% | Один Opus для всего — дорого и код клиентов покидает API |

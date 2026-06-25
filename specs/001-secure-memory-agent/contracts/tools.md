# Tools Module Contract

*Tool registry schema and parameter contracts for all SR-agent tools.*

## TOOL_REGISTRY structure

```python
TOOL_REGISTRY: dict[str, ToolSpec] = {
    "tool_name": {
        "description": "...",            # строковая константа в коде
        "description_hash": "sha256:...", # зафиксирован в git
        "action_class": "read_only",      # read_only | write_execute
        "parameters": ParameterSchema,    # Pydantic model
    }
}
```

Оркестратор верифицирует `description_hash` при каждом старте. Несовпадение → `ToolTampered` exception, старт прерывается.

---

## READ-ONLY Tools

### `read_file`
```python
class ReadFileParams(BaseModel):
    path: FilePath          # существует в репо, не выходит за пределы root_dir
    line_start: int | None  # опционально, для больших файлов
    line_end: int | None
```
Returns: `str` (file contents)

### `search_code`
```python
class SearchCodeParams(BaseModel):
    pattern: str            # regex или plain string
    scope: DirectoryPath    # директория в пределах репо
    file_ext: list[str] = [".sol"]
```
Returns: `list[SearchMatch]` — `{file: str, line: int, content: str}`

### `build_graph`
```python
class BuildGraphParams(BaseModel):
    contracts: list[FilePath]  # .sol файлы для включения в SIG
    include_imports: bool = True
```
Returns: `StateInterferenceGraph`
```python
@dataclass
class StateInterferenceGraph:
    nodes: list[FunctionNode]       # функции контракта
    edges: list[InterferenceEdge]   # interferes / can_reenter рёбра
    red_flag_functions: list[str]   # без modifier + critical operations
```

### `run_slither`
```python
class RunSlitherParams(BaseModel):
    target: FilePath
    detectors: list[SlitherDetector] = []  # пустой = все детекторы

class SlitherDetector(str, Enum):
    REENTRANCY_ETH = "reentrancy-eth"
    REENTRANCY_NO_ETH = "reentrancy-no-eth"
    CONTROLLED_DELEGATECALL = "controlled-delegatecall"
    ARBITRARY_SEND_ETH = "arbitrary-send-eth"
    INCORRECT_EQUALITY = "incorrect-equality"
    UNINITIALIZED_STATE = "uninitialized-state"
    TX_ORIGIN = "tx-origin"
    ORACLE_MANIPULATION = "oracle-manipulation"
    # ... полный список при разработке
```
Returns: `list[SlitherFinding]` — runs in Docker sandbox (no network)

### `run_mythril`
```python
class RunMythrilParams(BaseModel):
    target: FilePath
    timeout: int = 120      # секунды
    max_depth: int = 22
```
Returns: `list[MythrilFinding]` — runs in Docker sandbox

### `run_auditor_skill`
```python
class AuditorSkillType(str, Enum):
    SOLIDITY_AUDITOR = "solidity-auditor"
    DEFI_SECURITY    = "defi-security"
    SPEC_KIT         = "spec-kit"

class RunAuditorSkillParams(BaseModel):
    skill_type: AuditorSkillType
    target: FilePath
    context: str | None     # дополнительный контекст для sub-agent
```
Returns: content read via file bridge → `source_type: external_llm_output`

### `analyze_transactions`
```python
class AnalyzeTransactionsParams(BaseModel):
    address: EIP55Address
    block_range: BlockRange         # max 10_000 блоков
    focus: list[str] | None         # функции для фокуса

class BlockRange(BaseModel):
    from_block: int | Literal["latest-N"]
    to_block: int | Literal["latest"]
```
Returns: `TransactionAnalysis` via Alchemy archive node
All calldata → always wrapped in `[DATA]`, never treated as instructions

### `decompile_bytecode`
```python
class DecompileBytecodeParams(BaseModel):
    address: EIP55Address
    tool: Literal["heimdall", "panoramix"] = "heimdall"
```
Returns: `DecompilationResult` — `{source: str, confidence: float}`

---

## WRITE/EXECUTE Tools

All require out-of-band human confirmation before execution.

### `write_poc`
```python
class WritePoCParams(BaseModel):
    finding_id: str         # ссылка на Finding в Episodic Memory
    test_framework: Literal["foundry"] = "foundry"
    # Solidity тесты только — скрипт не может быть произвольным кодом
```
Returns: `PoCResult` — `{test_path: str, test_code: str}`
Note: сгенерированный код проверяется Guardrails на mock patterns до выполнения

### `run_tests`
```python
class RunTestsParams(BaseModel):
    test_suite: TestSuitePath   # путь к test файлу или директории
    fork_url: str | None        # Alchemy RPC для mainnet fork
```
Returns: `TestResult` — `{passed: bool, output: str, gas_used: int | None}`
Runs in: Docker → Anvil → Foundry → EVM (4 isolation layers)

### `deploy_test_contract`
```python
class DeployTestContractParams(BaseModel):
    bytecode: str           # hex-encoded bytecode
    target: Literal["anvil"]  # только локальный Anvil, никогда mainnet/testnet
```
Returns: `DeployResult` — `{address: str, tx_hash: str}`

---

## Parameter Type Aliases

```python
FilePath = Annotated[Path, AfterValidator(validate_in_repo_root)]
DirectoryPath = Annotated[Path, AfterValidator(validate_directory_in_repo)]
TestSuitePath = Annotated[Path, AfterValidator(validate_test_path)]
EIP55Address = Annotated[str, AfterValidator(validate_eip55)]
BlockRange = ...  # see above
```

All validated by orchestrator before tool execution, not by LLM.

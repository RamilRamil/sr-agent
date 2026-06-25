# LLM Core Module Contract

*Model routing, structured output schema, and LLM interface contracts.*

## Model Routing

```python
class ModelRouter:
    def route(self, task: TaskType) -> LLMClient:
        """Returns the appropriate LLM client for a given task type."""

class TaskType(str, Enum):
    STAGE1_DISCOVERY  = "stage1_discovery"   # → Claude Opus + extended thinking
    STAGE2_CHECK      = "stage2_check"        # → Qwen3-4B fine-tuned (local)
    STAGE3_SYNTHESIS  = "stage3_synthesis"    # → Claude Opus + extended thinking
    POC_WRITING       = "poc_writing"         # → Qwen3-Coder (local) / Claude Sonnet fallback
    KNOWLEDGE_EXPAND  = "knowledge_expand"    # → qmd-query-expansion-17B (local)
    KNOWLEDGE_EMBED   = "knowledge_embed"     # → gemma-300M (local)
    KNOWLEDGE_RERANK  = "knowledge_rerank"    # → qwen-reranker-0.6b (local)

MODEL_CONFIG: dict[TaskType, str] = {
    TaskType.STAGE1_DISCOVERY: os.environ.get("SR_STAGE1_MODEL", "claude-opus-4-8"),
    TaskType.STAGE2_CHECK:     os.environ.get("SR_STAGE2_MODEL", "qwen3-4b-local"),
    TaskType.STAGE3_SYNTHESIS: os.environ.get("SR_STAGE3_MODEL", "claude-opus-4-8"),
    TaskType.POC_WRITING:      os.environ.get("SR_POC_MODEL",    "qwen3-coder-local"),
    TaskType.KNOWLEDGE_EXPAND: "qmd-query-expansion-17b-local",
    TaskType.KNOWLEDGE_EMBED:  "gemma-300m-local",
    TaskType.KNOWLEDGE_RERANK: "qwen-reranker-0.6b-local",
}
```

---

## Structured Output Schema (LLM → Orchestrator)

All LLM responses must conform to `AgentAction` schema. Orchestrator validates before executing.

```python
class AgentAction(BaseModel):
    """
    The only output format accepted from LLM.
    Extended thinking content is NOT part of this schema — it's in the API response,
    but orchestrator ignores thinking content for action execution.
    """

    # Required
    next_action: ActionType     # from TOOL_REGISTRY keys + "write_memory" + "request_human"
                                # + "complete" (audit done) + "escalate" (force human escalation)

    # Optional per action_type
    tool_params: dict | None    # validated against per-tool ParameterSchema

    # Memory write (only if next_action == "write_memory")
    finding: FindingPayload | None
    checkpoint_notes: str | None    # short, factual, orchestrator wraps in Checkpoint

    # Reasoning summary (required, used for progress stream — not stored in memory)
    reasoning_summary: str          # max 200 chars, "what I found and why this action"

    # Escalation details (required if next_action == "escalate")
    escalation_trigger: str | None
    escalation_detail: str | None


class FindingPayload(BaseModel):
    """Strict finding schema — enum fields prevent injection via content."""
    location: str               # validated as "filename.sol:N"
    function_name: str          # validated as identifier
    bastet_tag: BastetTag | None
    severity: Severity
    preconditions: dict[str, bool]   # keys must be "1"-"12"
    mitigations_present: list[str]   # from KNOWN_MITIGATIONS enum
    poc_needed: bool
```

---

## Claude Client Interface

```python
class ClaudeClient:
    """Wraps Anthropic SDK. Extended thinking always on for Stage 1/3."""

    def complete(
        self,
        messages: list[Message],
        task_type: TaskType,
        *,
        budget_tokens: int = 8000,  # extended thinking budget
    ) -> AgentAction:
        """
        Calls claude-opus-4-8 with extended thinking.
        budget_tokens is always set — thinking is never disabled for Stage 1/3.

        Raises:
            ValidationError: if response doesn't conform to AgentAction schema
            RateLimitError: orchestrator handles with backoff
        """

    def _build_system_prompt(self, task_type: TaskType, context: OrchestratorContext) -> str:
        """
        System prompt is built by orchestrator, not LLM.
        Context includes: current stage, findings so far, knowledge chunks (in [DATA] blocks).
        """
```

---

## Local Client Interface

```python
class LocalClient:
    """Wraps Ollama/llama.cpp for Qwen3-4B (Stage 2) and Qwen3-Coder (PoC)."""

    def complete(
        self,
        messages: list[Message],
        task_type: TaskType,
    ) -> AgentAction:
        """
        Calls local model. No extended thinking (not supported on Qwen3-4B).
        Stage 2 fine-tuned model: ASR 1.7%, structured JSON output reliable.

        Raises:
            ModelUnavailableError: if local model not loaded
        """

    # Fallback: if local model unavailable → orchestrator escalates to human
    # before falling back to Claude API (privacy concern for client code)
```

---

## File Bridge Reader

```python
class FileBridgeReader:
    """
    Reads results written by external LLM to /shared/results/.
    source_type: external_llm_output (trust level 2).
    """

    def read(
        self,
        tool: str,
        target: str,
        *,
        max_age_minutes: int = 60,
    ) -> ExternalLLMResult:
        """
        Reads /shared/results/{tool}-{target}.json.

        Validates:
          - File exists and is readable
          - Timestamp within max_age_minutes (freshness check)
          - sha256(findings) == content_hash (tamper detection)

        Raises:
            ResultStaleError: if timestamp too old
            ResultTamperedError: if content_hash mismatch
            ResultNotFoundError: if file doesn't exist
        """


class ExternalLLMResult(BaseModel):
    tool: str
    target: str
    timestamp: datetime
    content_hash: str           # sha256 of findings field
    findings: list[dict]        # raw findings — orchestrator wraps in [DATA] before LLM
```

---

## Context Window Management

```python
CONTEXT_LIMITS = {
    "claude-opus-4-8": 200_000,   # tokens
    "qwen3-4b-local":   32_000,
    "qwen3-coder-local": 32_000,
}

class ContextBuilder:
    """
    Orchestrator builds LLM context. LLM never sees raw memory records.
    All external content wrapped in [DATA START]...[DATA END].
    """

    def build(
        self,
        task_type: TaskType,
        session: AuditSession,
        knowledge_chunks: list[KnowledgeChunk],
        tool_output: str | None,
    ) -> list[Message]:
        """
        Constructs context within model token limit.
        Priority order (most important first if truncation needed):
          1. System prompt + schema
          2. Current task description
          3. Latest checkpoint
          4. Relevant knowledge chunks (in [DATA])
          5. Tool output (in [DATA])
          6. Recent findings summary (structured, not raw LLM text)
        """
```

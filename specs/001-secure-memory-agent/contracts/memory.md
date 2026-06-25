# Memory Module Contract

*Interface between Orchestrator and Memory module.*

## EpisodicMemory

```python
class EpisodicMemory:
    """
    Append-only JSONL store for per-project audit findings and checkpoints.
    Only the orchestrator writes; reads are filtered by HMAC verification.
    """

    def write(
        self,
        project_id: str,
        target: str,
        content: Finding | Checkpoint | StatusChange,
        source_type: SourceType,
        tool: str | None,
        session_id: str,
        *,
        supersedes: str | None = None,
    ) -> MemoryRecord:
        """
        Appends a new HMAC-signed record to memory/{project_id}/{target}.jsonl.

        Raises:
            PermissionDenied: if content.status in REQUIRES_HUMAN_CONFIRMATION
                              and source_type != SourceType.HUMAN_INPUT
            PermissionDenied: if supersedes is not None
                              and source_type != SourceType.HUMAN_INPUT
            ValidationError: if content fails schema validation
        """

    def load(
        self,
        project_id: str,
        target: str,
    ) -> list[MemoryRecord]:
        """
        Loads all HMAC-valid records for a specific project + target.
        Records with invalid/missing HMAC are silently dropped.
        Applies supersedes chain: returns only the latest non-superseded records.

        Never raises on individual record failure (corrupt = dropped).
        """

    def load_session(
        self,
        project_id: str,
        session_id: str,
    ) -> list[MemoryRecord]:
        """
        Loads all records for a session (across targets) for resumption.
        Used by orchestrator to rebuild AuditSession from checkpoint.
        """
```

## KnowledgeBase

```python
class KnowledgeBase:
    """
    Read-only knowledge store. Human writes only (outside agent boundary).
    3-model retrieval pipeline: query-expansion → embedding → reranker.
    """

    def search(
        self,
        query: str,
        category: Literal["vulnerability-patterns", "methodology", "taxonomy"] | None = None,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]:
        """
        Semantic search via 3-model pipeline.
        query-expansion-17B expands query → gemma-300M embeds → qwen-reranker-0.6b reranks.

        Returns top_k most relevant chunks, each with:
          - content: str
          - source_path: str
          - score: float
        """
```

## MemoryRecord JSONL format

Each line in `memory/{project_id}/{target}.jsonl`:

```json
{
  "record_id": "rec-550e8400-e29b",
  "project_id": "project-vault-abc",
  "target": "Vault.sol",
  "source_type": "llm_inference",
  "tool": null,
  "session_id": "sess-f47ac10b-58cc",
  "timestamp": "2026-06-25T10:00:00Z",
  "finding": {
    "finding_id": "HIGH-001",
    "location": "Vault.sol:47",
    "function_name": "withdraw",
    "bastet_tag": "Reentrancy",
    "severity": "high",
    "status": "unverified",
    "preconditions": {"1": true, "2": true, "3": false, "4": true},
    "mitigations_present": [],
    "poc_path": null,
    "poc_status": null,
    "combined_with": null
  },
  "checkpoint": null,
  "status_change": null,
  "supersedes": null,
  "hmac": "a3f9c2d8e1b5f7c4..."
}
```

## Orchestrator checkpoint format

```json
{
  "record_id": "chk-6ba7b810-9dad",
  "project_id": "project-vault-abc",
  "target": "__checkpoint__",
  "source_type": "tool_output",
  "tool": "orchestrator",
  "session_id": "sess-f47ac10b-58cc",
  "timestamp": "2026-06-25T10:30:00Z",
  "finding": null,
  "checkpoint": {
    "stage": 2,
    "completed_at": "2026-06-25T10:30:00Z",
    "files_analyzed": ["Vault.sol", "Pool.sol"],
    "finding_ids": ["HIGH-001", "MEDIUM-002"],
    "high_priority_locations": ["Vault.sol:47"],
    "skipped": []
  },
  "hmac": "b7d2a4f6e8c1..."
}
```

# Contract: Lesson lifecycle (capture → gate → promote → retrieve)

The kernel module `sr_agent/memory/lessons.py` exposes the mechanism. Signatures are
illustrative (behavioral contract, not final Python).

## `LessonStore`

```python
class LessonStore:
    def __init__(self, lessons_root: Path, knowledge_root: Path, secret_key: bytes,
                 embedder: Embedder | None = None) -> None: ...

    # --- capture side (called by the harness; NEVER promotes) ---
    def capture(self, candidate: LessonCandidate) -> bool:
        """Best-effort. Write lessons/pending/<sig_id>.json IFF no pending file and no
        promoted manifest record already exists for this sig_id (dedup, FR-002).
        Returns True if a new candidate was written, False if deduped/skipped.
        MUST NOT raise — any error is swallowed+logged (FR-001)."""

    # --- review side (called by the CLI only) ---
    def list_pending(self) -> list[LessonCandidate]: ...
    def show(self, sig_id: str) -> LessonCandidate | None: ...
    def dismiss(self, sig_id: str) -> bool:
        """Delete the pending file. Never touches the knowledge corpus."""
    def promote(self, sig_id: str, edited: PromotedLesson | None = None) -> PromotedLesson:
        """THE gate. Write knowledge/lessons/<sig_id>.md + a signed manifest record.
        `edited` lets the operator amend content at approval. Removes the pending file.
        The ONLY writer of the promoted store (FR-004/SC-004). Preserves
        origin='llm_inference' and sets authorization='human_input' (Principle IV)."""

    # --- retrieval side (called by the harness draft/fix) ---
    def retrieve(self, context: str, top_k: int = 3) -> list[str]:
        """Category-scoped KnowledgeBase.search over knowledge/lessons/, VERIFYING each
        result's manifest HMAC+content_hash and DROPPING unverified ones silently.
        Returns already-DATA-wrapped strings ('[DATA START]…[DATA END]'), or [] when
        nothing relevant/verified (SC-007 inert-when-empty)."""

    # --- integrity (called by `sr-agent lessons verify`) ---
    def verify(self) -> LessonIntegrityReport:
        """Report (not drop) any promoted lesson failing HMAC/content_hash."""
```

## Contract guarantees (each maps to an SC)

| Guarantee | Behavior | SC |
|-----------|----------|----|
| Dedup | `capture` of a sig_id with an existing pending or promoted record returns False, writes nothing. | SC-001 |
| Non-blocking | `capture` never raises; a write error → logged, run continues. | (FR-001) |
| Out-of-band gate | `promote` is called only from the CLI; no harness/orchestrator reference (AST test). | SC-004 |
| Tamper-evidence | `retrieve` drops a lesson whose HMAC or content_hash mismatches; `verify` reports it. | SC-003 |
| Suggestion-not-control | `retrieve` returns DATA-wrapped strings only; a lesson can't be an instruction. | SC-005 |
| No new dependency | `retrieve` works with `embedder=None` (lexical fallback). | SC-006 |
| Inert when empty | empty/irrelevant corpus → `retrieve` returns `[]`; prompt byte-identical. | SC-007 |
| Origin preserved | `promote` sets `authorization='human_input'` (Principle IV) but never rewrites `origin='llm_inference'` (honest audit); retrieval DATA-wraps regardless of tier. | (Principle I & IV) |

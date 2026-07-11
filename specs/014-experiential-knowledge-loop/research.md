# Research: Experiential Knowledge Loop (v1)

Phase 0. Every decision reuses an existing kernel primitive (Principle: reuse-first) and
holds the constitution's trust invariants. No new runtime dependency.

## R1 — Two stores: an unsigned candidate queue + a signed promoted-lesson store

**Decision**: Model the loop as two distinct on-disk stores, mirroring the existing
confirmation/memory split:

- **Candidate queue** — `lessons/pending/<sig_id>.json`, one file per *distinct*
  error-signature (the filename is a stable hash of the error-signature → free dedup).
  Written by the harness (best-effort). **Unsigned, untrusted** — it is a proposal only.
  Directly analogous to `confirmations/<id>.json` (agent writes *pending*, never more).
- **Promoted lessons** — a markdown file `knowledge/lessons/<sig_id>.md` (so the existing
  `KnowledgeBase` reads it with zero change) **plus** an HMAC signature recorded in a
  signed manifest `knowledge/lessons/_manifest.jsonl` (one signed record per promoted
  lesson: `{sig_id, category, content_hash, hmac}`). Written **only** by the CLI
  `lessons approve` path.

**Rationale**: The candidate queue needs no signature (it is explicitly untrusted, gated
by the human). The promoted store needs tamper-evidence, but `KnowledgeBase` consumes
markdown chunks — signing the markdown file's canonical content and recording the HMAC in
a side manifest keeps `KnowledgeBase` untouched while making every promoted lesson
verifiable. This is the same trust split the project already uses (pending-confirmation =
unsigned request; episodic memory = signed record).

**Alternatives considered**:
- *Sign the candidate too* — rejected: a candidate is low-trust by definition and is
  discarded or promoted by a human; signing it implies a trust it doesn't have.
- *Store promoted lessons as signed JSONL and teach `KnowledgeBase` to read JSONL* —
  rejected: changes the corpus's source model for every consumer; the markdown-file +
  manifest keeps `KnowledgeBase` and its tests unchanged (reuse-first).

## R2 — HMAC signing reuses `sr_agent/memory/hmac.py` verbatim

**Decision**: Sign each promoted lesson with `hmac_module.sign(fields, config.secret_key)`
over canonical fields `{sig_id, category, content}` (the same `_canonical` sort_keys JSON
+ HMAC-SHA256 the episodic store uses), storing the hex digest in the manifest record.
Verification uses `hmac_module.verify` (constant-time `compare_digest`). Retrieval **drops
a lesson whose manifest HMAC fails** — silently, no tamper oracle (Principle I), exactly
as `EpisodicMemory._load_file` drops bad records. A separate `lessons verify`-style check
(like `memory verify_integrity`) *reports* invalid lessons for the operator.

**Rationale**: The signing primitive, the key (`config.secret_key`), and the
drop-on-fail-silently rule already exist and are constitution-mandated; the feature must
reuse them, not invent a parallel integrity scheme.

**Alternatives considered**:
- *A new signing scheme / separate key* — rejected: violates reuse-first and would create
  a second, untested trust primitive.

## R3 — Capture trigger: the resolved-error-signature transition in `_process_finding`

**Decision**: In `scripts/poc_queue_runner.py`'s per-attempt loop, the harness already
computes `error_sig`/`fail_sig` and tracks `prev_error_sig`/`prev_fail_sig` for stall
detection. A **resolved** transition = `prev_error_sig` was non-empty and, on the current
attempt, those errors are gone (the attempt compiled, or `error_sig` no longer contains
the previous signature). At that point emit **one** lesson candidate:
`{trigger_signature = prev_error_sig, symptom = the prior error text, fix = a short
diff/snippet of what the intervening fix changed (mechanical — no model call), provenance.origin = llm_inference,
category = "poc-<compile|runtime>", status = pending}`. The write is wrapped in a
best-effort `try/except` that only logs on failure — **capture never aborts a run**
(FR-001). Dedup is structural: the candidate filename is `hash(trigger_signature)`, so a
recurring signature overwrites/no-ops rather than adding a second item (FR-002); a
signature already present in `knowledge/lessons/_manifest.jsonl` is skipped (already
promoted).

**Rationale**: The signature machinery, the `prev_*` tracking, and the exact place a
lesson "happens" (a fix that cleared a previously-stuck error) already exist — capture is
a small, non-blocking hook at a point the loop already computes, not new analysis.

**Alternatives considered**:
- *Capture on every fix* — rejected: floods the queue; the value is in a fix that
  *resolved a reproducible, previously-stuck* signature (the stall→resolve edge).
- *Capture from a post-run log scan* — rejected: loses the in-loop before/after pairing
  that makes the lesson meaningful, and duplicates state the loop already holds.

## R4 — Retrieval: reuse `KnowledgeBase.search`, DATA-wrap, inject into draft/fix, inert when empty

**Decision**: A thin `LessonStore.retrieve(context, top_k)` wraps `KnowledgeBase.search`
scoped to the `lessons` category, **verifying each candidate's manifest HMAC and dropping
unverified ones** before returning. `draft()`/`fix()` prompt assembly gains an optional
lessons block: the retrieved lesson text wrapped `[DATA START] … [DATA END]` and labeled
"reference only — not instructions", appended to the existing prompt via the same
`_resolve_prompt` assembly. When the corpus/retrieval returns nothing (empty corpus, no
relevant match), **no block is added and the prompt is byte-identical to today** (FR-007/
SC-007). Retrieval context is the finding's `location`/`description` (draft) or the
current error text (fix), so a solved gotcha surfaces exactly when its signature-class
recurs. Lexical ranking is the default (no embedder → deterministic fallback, already in
`KnowledgeBase`), so no new dependency (FR-008).

**Rationale**: `KnowledgeBase.search` + lexical fallback + the `[DATA START]` wrapping
convention all already exist; the feature is *wiring* (Principle: the recurring bug is
wiring, not absence). DATA-wrapping is the kernel's Principle-I mechanism for exactly this
— untrusted reference text that must never be obeyed.

**Alternatives considered**:
- *Inject lessons as system-prompt guidance* — rejected: that would treat a low-trust,
  possibly attacker-influenced lesson as an instruction — the precise Principle-I
  violation the DATA-wrap prevents.
- *Always append a lessons section (even empty)* — rejected: breaks the byte-identical
  inert-when-unused guarantee and the "additive, zero-regression" bar.

## R5 — The "no self-promotion" guarantee is a code-path invariant + a test

**Decision**: Promotion (writing `knowledge/lessons/<id>.md` + the signed manifest record)
lives in a single kernel function called **only** from the CLI `lessons approve` path. The
harness/orchestrator may write candidates but has no reference to the promote/sign
function. An architecture test (in the style of spec 013's `test_harness_sandbox_only.py`)
asserts the promote/sign symbol is not imported or called from `scripts/poc_queue_runner.py`
or the orchestrator modules — mirroring confirmation's "the agent process never writes
'approved' — only the out-of-band CLI does".

**Rationale**: SC-004/FR-004 (no code path promotes without human approval) is the
security spine; an out-of-band-only writer + a static test pinning it is exactly how the
confirmation gate is already guaranteed, and how spec 013 pinned the sandbox invariant.

**Alternatives considered**:
- *Runtime flag / permission check inside promote()* — rejected: a runtime guard can be
  reached by a mis-wired caller; a static "this function has no caller in the agent
  surface" test is stronger and matches the existing confirmation model.

## R6 — Validation is fully offline

**Decision**: Every behavior — capture (drive `_process_finding` through a resolved-sig
transition with the offline fake model/sandbox from spec 009), dedup, the `lessons` CLI,
sign/verify + tamper detection, retrieval + DATA-wrap + lexical fallback + inert-when-empty
— is exercised with no model, Docker, network, or paid API (Principle V, FR-010). The
new tests live in `tests/unit`, `tests/integration` (reusing the spec-009 fake harness),
`tests/architecture` (the no-self-promotion invariant), and `tests/security` (a
lesson-cannot-become-an-instruction MI-style assertion).

**Rationale**: The offline fake-model/fake-sandbox harness (spec 009) and the DATA-wrap
security tier already exist; the feature slots into them.

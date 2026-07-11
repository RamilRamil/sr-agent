# Data Model: Experiential Knowledge Loop (v1)

Two entities, two stores. The candidate is untrusted and unsigned; the promoted lesson is
signed and the only kind retrieval surfaces. IDs derive from the error-signature so dedup
is structural.

## `sig_id` — the stable dedup / correlation key

`sig_id = sha256(canonical(trigger_signature))[:16]` where `trigger_signature` is the
harness's `_error_signature`/`_fail_signature` tuple (sorted). The same recurring signature
always maps to the same `sig_id`, so:
- a second capture of the same signature **overwrites/no-ops** its pending file (dedup),
- a signature already present in the promoted manifest is **skipped** at capture (known),
- retrieval can correlate a promoted lesson back to the signature class that triggers it.

## Entity: Lesson candidate (unsigned, pending)

Store: `lessons/pending/<sig_id>.json` (one file per distinct signature; runtime, untracked).

| Field | Type | Notes |
|-------|------|-------|
| `sig_id` | str | `sha256` prefix of the trigger signature (filename stem). |
| `trigger_signature` | list[str] | The resolved error/FAIL signature (sorted tuple → list). |
| `symptom` | str | The prior error/FAIL text that was stuck. |
| `fix` | str | **Mechanically derived — no model call**: a unified diff of the previous vs current PoC attempt (or the new attempt's relevant snippet). Capture must stay offline + non-blocking, so it never asks a model to summarize. |
| `provenance` | obj | `{origin: "llm_inference", finding_id, attempt, captured_at}` — `origin` is low-trust by construction; a candidate has no `authorization` (not in the KB). |
| `category` | str | `"poc-compile"` or `"poc-runtime"` (pack taxonomy; scopes retrieval). |
| `status` | str | Always `"pending"` in this store (promotion/dismissal removes the file). |

**Rules**: written best-effort by the harness (a write failure is logged, never raised —
FR-001). No HMAC (it is explicitly untrusted). Presence of the file = one queued lesson;
re-capture of the same `sig_id` does not add a second (FR-002).

## Entity: Promoted lesson (signed, retrievable)

Store: `knowledge/lessons/<sig_id>.md` (the human-approved content, read verbatim by
`KnowledgeBase`) **plus** one signed record in `knowledge/lessons/_manifest.jsonl`.

Markdown file (`<sig_id>.md`) — a normal knowledge chunk:
```markdown
# <short lesson title>   (category: poc-compile)

**Trigger**: <human-readable form of the signature>
**Symptom**: <what was stuck>
**Fix**: <what resolved it>
```

Manifest record (`_manifest.jsonl`, one line per promoted lesson):

| Field | Type | Notes |
|-------|------|-------|
| `sig_id` | str | Correlates to the `.md` file and the triggering signature class. |
| `category` | str | Retrieval scope. |
| `content_hash` | str | `sha256` of the `.md` file's bytes (detects file edits). |
| `hmac` | str | `hmac.sign({sig_id, category, content}, config.secret_key)` — hex HMAC-SHA256. |
| `promoted_at` | str | tz-aware ISO timestamp (spec 013 convention). |
| `origin` | str | Audit trail — always `"llm_inference"`: a model drafted the text. Immutable, honest; never rewritten by promotion. |
| `authorization` | str | The promotion act — `"human_input"`: a human reviewed and commanded it into the applied knowledge base (Principle IV). Set by `promote()`. |

**Rules**:
- Written **only** by `LessonStore.promote()`, called **only** from the `sr-agent lessons
  approve` CLI (out-of-band; FR-004/SC-004). Promotion is the human's Principle-IV act: it
  sets `authorization = human_input` (the human vouches for this knowledge) **while
  preserving `origin = llm_inference`** (the honest record that a model drafted it).
  Retrieval still DATA-wraps the lesson regardless of `authorization` (Principle I applies
  to any artifact re-entering context) — so "human_input-authorized" governs *whether it
  may enter the applied KB*, not *whether it may act as an instruction* (it never can).
- Verification: `hmac.verify({sig_id, category, content}, record.hmac, secret_key)` **and**
  `sha256(content) == content_hash`. On failure the lesson is **dropped silently** at
  retrieval (Principle I, no tamper oracle); a separate `lessons verify` reports it.

## State transitions

```text
(harness resolves a stuck signature)
        │  capture (best-effort, dedup by sig_id, skip if already promoted)
        ▼
lessons/pending/<sig_id>.json   ── operator: sr-agent lessons dismiss ──▶  (deleted, never promoted)
        │
        │  operator: sr-agent lessons approve   (out-of-band; may edit content first)
        ▼
knowledge/lessons/<sig_id>.md  +  signed _manifest.jsonl record
        │
        │  next run: LessonStore.retrieve(context)  → verify HMAC → DATA-wrap
        ▼
draft()/fix() prompt gains a [DATA START]…[DATA END] lessons block  (suggestion, not control)
```

## Trust & provenance (constitution mapping)

- **Two distinct facts, never conflated**: `origin` (where the text came from — always
  `llm_inference`, an immutable audit note that a model drafted it) and `authorization`
  (whether it may enter the applied KB — set to `human_input` by the human's promotion act,
  Principle IV: "only a human's review-and-command elevates it… into the applied knowledge
  base"). A candidate has `origin = llm_inference` and **no** authorization (it is not in
  the KB). Promotion grants `authorization = human_input` without ever rewriting `origin`.
- Retrieval output is DATA (`[DATA START]…[DATA END]`) — **never** an instruction —
  *regardless of `authorization`* (Principle I DATA-wraps every artifact re-entering
  context). Human-authorization decides KB membership, not instruction-power.
- Promotion is the human-authority act (Principle II/IV); capture and retrieval carry no
  authority.
- Signing/verify reuse the episodic-memory HMAC scheme and its silent-drop rule.

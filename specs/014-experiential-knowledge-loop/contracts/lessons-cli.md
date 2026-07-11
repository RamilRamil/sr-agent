# Contract: `sr-agent lessons` CLI

Mirrors `sr-agent confirm` — out-of-band, a separate process from the agent loop. It is the
**only** surface that promotes a lesson.

```text
sr-agent lessons list
    → one line per pending candidate: <sig_id>  [category]  <symptom-preview>

sr-agent lessons show <sig_id>
    → full candidate JSON (trigger_signature, symptom, fix, provenance, category)

sr-agent lessons approve <sig_id> [--edit <file>]
    → promote: write knowledge/lessons/<sig_id>.md + signed manifest record; remove pending.
      --edit supplies operator-authored replacement content (else the candidate's fix text).
      Prints: "Lesson <sig_id> promoted (category …); signature verifies."

sr-agent lessons dismiss <sig_id>
    → delete the pending candidate; nothing enters the corpus.
      Prints: "Lesson <sig_id> dismissed."

sr-agent lessons add --from <file>
    → seeding affordance: write a hand-authored candidate (trigger/symptom/fix/category
      JSON, origin="llm_inference") into lessons/pending/ so it can be reviewed + approved
      through the same gate. This is how non-captured lessons (e.g. the 13 gotchas) enter
      the human path — the ONLY way in besides harness capture. Does NOT promote (approve does).
      Prints: "Candidate <sig_id> queued for review."

sr-agent lessons verify
    → scan knowledge/lessons/_manifest.jsonl; print per-lesson OK / INVALID and a total.
      Exit non-zero if any promoted lesson fails (like `sr-agent memory verify`).
```

## Guarantees

- `approve` is the sole path that calls `LessonStore.promote`; no agent/harness code
  reaches it (FR-004/SC-004) — pinned by `tests/architecture/test_lessons_promote_gate.py`.
- `approve`/`dismiss` operate on the pending queue written by the harness; the harness
  never writes to the promoted store.
- `verify` *reports* tamper (operator tool); the retrieval path *drops silently* (no
  tamper oracle to the agent). Same split as `sr-agent memory verify` vs the load path.
- Exit codes mirror `confirm`: missing `<sig_id>` → non-zero with an error on stderr.

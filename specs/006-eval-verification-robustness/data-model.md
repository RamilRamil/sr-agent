# Data Model: Eval/Verification Robustness

This feature is primarily a correctness fix + an audit + documentation, not a
data-storage feature. The "entities" below are conceptual — how they're recorded in
practice is in `contracts/` and `quickstart.md`.

## Success Gate

An automated check that produces a verdict over a generated artifact.

| Field | Type | Notes |
|---|---|---|
| `name` | string | e.g. `_compiled`, `_poc_defects`, `mechanism_signal` |
| `signal_type` | `positive` \| `denylist` | MUST be `positive`, OR carry a `justification` |
| `blocking` | bool | Does it gate an `outcome` (e.g. `compiled`, `passed`, `vacuous_pass`), or is it diagnostic-only (logged, never gates)? |
| `justification` | string \| null | Required when `signal_type == denylist` (should not occur post-fix) or when a positive-signal check has a narrow, explicit exception (see `_poc_defects`'s own-declaration check, research.md R3) |
| `known_limitations` | string \| null | Required when `blocking == false` — a diagnostic's blind spots must be legible (FR-004) |

**Validation rule**: `signal_type == "denylist"` without a `justification` is a defect —
this is exactly what the 2026-07-05 incident was, and what FR-001/FR-003 close.

**State**: this is a property of code, not a runtime record — its "instances" are the
audit table in `research.md` R3, kept current as checks are added/changed.

## Cross-Check

The second, independently-computed signal required before a Success Gate's verdict is
recorded as a documented milestone/claim (FR-002).

| Field | Type | Notes |
|---|---|---|
| `primary_signal` | ref → Success Gate | The verdict being corroborated |
| `independent_signal` | string | Must be independently computed — a different data source (e.g. exit code vs. stdout text) or a different method (execution vs. static parsing) or a different actor (human vs. automated), never a second read of the same transcript with a similar method |
| `applies_to` | `per-attempt-log` \| `documented-claim` | Cross-check is mandatory for `documented-claim`, not for internal per-attempt telemetry (research.md R2) |

**Validation rule**: an `independent_signal` that shares its data source AND its method
with the `primary_signal` does not satisfy this entity — it is not independent.

## Mechanism-Verification Recommendation

The documented adopt/adapt/defer decision on using SmartGraphical (or an equivalent
structural analysis) as a stronger mechanism-check than the current regex-based
`mechanism_signal()`.

| Field | Type | Notes |
|---|---|---|
| `verdict` | `adopt` \| `adapt` \| `defer` | Exactly one; see research.md R4 — this feature's verdict is `adapt` |
| `reasoning` | string | Why — see research.md R4 |
| `conditions_to_revisit` | string | What would change the verdict (e.g., a spike confirming Foundry-file parsing; the harness's needs outgrowing path B alone) |
| `current_alternative` | ref → Success Gate / diagnostic | What stands in for it today (`mechanism_signal`, labeled non-blocking) and what carries the correctness burden meanwhile (path B fork execution) |

**Validation rule**: `verdict != adopt` MUST NOT leave the gap silently unaddressed —
`current_alternative` and its `known_limitations` must be documented (satisfies User
Story 3's Acceptance Scenario 2).

## Relationships

```
Mechanism-Verification Recommendation ──recommends about──> (a future) Success Gate
                                       └─currently stands in for─> mechanism_signal (diagnostic)
Cross-Check ──corroborates──> Success Gate (when applies_to == documented-claim)
```

No persistent storage, no migration — these are documentation/code-review constructs,
recorded in `research.md`, `docs/eval-principles.md`, and the audited functions'
docstrings, not database rows.

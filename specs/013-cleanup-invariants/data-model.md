# Data Model: Deprecation Cleanup + Architecture-Invariant Guards

No persisted data. The "entities" are the fixed call sites and the two invariants.

## Timestamp call site (fixed)

| File:line | Form | After |
|---|---|---|
| `sr_agent/cli.py:97` | `datetime.utcnow()` (datetime value) | `datetime.now(timezone.utc)` |
| `sr_agent/packs/audit/checkpoint.py:26` | datetime value | `datetime.now(timezone.utc)` |
| `sr_agent/packs/audit/report.py:64` | datetime value | `datetime.now(timezone.utc)` |
| `sr_agent/orchestrator/relay.py:84` | `.isoformat()` string | `datetime.now(timezone.utc).isoformat()` |
| `sr_agent/orchestrator/confirmation.py:53` | `.isoformat()` string (created_at) | `datetime.now(timezone.utc).isoformat()` |
| `sr_agent/orchestrator/confirmation.py:131` | `.isoformat()` string (decided_at) | `datetime.now(timezone.utc).isoformat()` |

**Validation rule**: same UTC instant; `timezone` added to each file's datetime import;
no test that pins a timestamp's meaning/shape regresses (FR-002).

## SourceType trust-hierarchy ranking (pinned by US2)

`sr_agent/models/memory.py`: `human_input:4 > tool_output:3 >
external_llm_output:2 == human_relayed_tool:2 > llm_inference:1`.

**Validation rule (test)**: the relations hold exactly; any reorder fails (FR-004).

## Harness execution partition (pinned by US3)

| Kind | Path | Guard |
|---|---|---|
| PoC/forge execution | `run_tests` → `DockerSandbox` (sandboxed) | ONLY path allowed for PoC/forge |
| benign git | `git apply` (mutation-verify), `git ls-files` (`_tracked_sol`) | allowed |
| direct forge/shell PoC exec | — | MUST NOT exist (test fails if added) |

**Validation rule (test)**: every `subprocess` call in `scripts/poc_queue_runner.py` is
a `git` command; PoC/forge runs go via `run_tests` (FR-005).

# Data Model: Harness Verdict-Logic Test Coverage + Orchestration Integration Test

This is a testing/reliability feature — it introduces no persisted data. The
"entities" are the units under test and the test doubles that drive them.

## Verdict gate (unit under test)

A harness function whose output determines a finding's status.

| Function | Verdict it produces | Bug class the test must pin |
|---|---|---|
| `_compiled(stdout, stderr)` | did the PoC actually compile+run a suite? | positive-signal only — a compile failure in ANY wording is "not compiled" (spec 006) |
| `_poc_defects(code, target_stems, scaffold_used)` | is the PoC vacuous/mock/no-import? | flags empty/commented body, re-declared target, missing import |
| stall signatures (`error_sig`, `fail_sig` derivation in the loop) | did this attempt repeat the last one's failure? | keys on error MESSAGE text, not line number |

## Deterministic repair helper (unit under test)

A harness function that turns a failed attempt's forge output into guidance or a
mechanical fix — no model involved.

| Function | Transform under test |
|---|---|
| `_targeted_hints(...)` / `_line_level_hints(...)` / `_sig_by_method(...)` | resolve a forge error to the real signature/path hint |
| `_fix_setup_override(code)` | strip a non-virtual `setUp` override, re-inject its statements |
| `_fix_import_paths(code, project)` | fix bare-SPDX and wrong-depth import paths |
| `revert_hints(...)` | build the compiled-but-reverted feedback block |

**Validation rule**: each helper's test feeds it a representative input and asserts the
exact transform — offline, synthetic input, no target-project code.

## Fake model (test double)

Drives the loop's draft/fix calls with scripted output.

| Aspect | Shape |
|---|---|
| Interface used by the loop | `pqr.draft(...)` / `pqr.fix(...)` (monkeypatched to pop scripted code) |
| Scripted content | a list of PoC source strings, one per draft/fix call, per scenario |

## Fake sandbox + fake run_tests (test double)

Drives the loop's execution result with scripted forge output.

| Aspect | Shape |
|---|---|
| `sandbox` | a bare sentinel — the loop only passes it through to `run_tests` |
| `pqr.run_tests(...)` | monkeypatched to return scripted `TestResult(passed, exit_code, stdout, stderr)` per attempt |

## Outcome path (integration assertion target)

The five per-finding outcomes the loop can reach, each an integration-test scenario.

| Outcome | Scripted setup |
|---|---|
| `passed` | first draft's `run_tests` returns passed + no defects (+ real compile under fork bar) |
| `vacuous_pass` (rejected) | `run_tests` returns passed but the code is empty/mock/no-import |
| repair→corrected | draft returns a compile error, next fix returns a version that passes |
| `exhausted` (stall) | every attempt returns the identical failure signature |
| budget-limited | more findings/attempts than the wall-clock/attempt budget allows |

**Validation rule**: each scenario asserts BOTH the finding's recorded `outcome` AND
the key `event`s emitted (`task_start`, per-attempt `tested`, `rejected_vacuous`/
`stall_detected` where applicable, `task_done` with the right `outcome`).

## Relationships

```
_process_finding(task, client, sandbox, log, ...config...)  ← extracted from main() (R1)
   ├─ calls pqr.draft/pqr.fix   ← fake model scripts these
   ├─ calls pqr.run_tests       ← fake sandbox scripts the TestResult
   ├─ calls verdict gates       ← also unit-tested directly (US1)
   └─ emits events via `log`, returns outcome  ← integration test asserts both (US2)

scaffold_missing_types(scaffold, target_stems)  ← re-platformed onto SymbolIndex (US3)
   └─ resolves declared + inherited state-var types, not single-file regex
```

No persistent storage; every entity here lives only for the duration of one test.

# Contract: `_process_finding` (extracted per-finding loop body)

The single behavior-preserving function extracted from `main()`'s per-finding loop
(research.md R1). This contract fixes its interface so the integration test and
`main()` agree, and so the extraction can be verified as behavior-preserving.

## Signature (shape, not final Python)

```
_process_finding(
    task: dict,                 # {id, title, location, description}
    *,
    client,                     # LocalClient or fake — used only via draft()/fix()
    sandbox,                    # DockerSandbox or sentinel — passed through to run_tests
    log,                        # callable(dict) -> None — the JSONL emitter
    symbol_index,               # SymbolIndex | None
    protocol_mode: str,         # "tool" | "marker"
    scaffold, example, file_map, callable_api,   # grounding (already computed)
    fork_rpc, require_pass_effective,            # run mode
    lookup_budget, attempts, ...                 # budgets
    tracer, ...                                  # observability (NOOP in tests)
) -> str                        # the finding's outcome string
```

The exact parameter list is whatever the current loop body reads from its enclosing
scope; the point of the contract is: **everything the loop body needs is passed in, it
returns the outcome, and it emits events only via `log`** — no reads of module globals
that a test can't control, no `sys.exit`.

## Invariants (guard the extraction)

- **Events unchanged**: emits exactly the events the current inline loop emits, in the
  same order, for the same inputs — `task_start` … per-attempt `written`/`tested` …
  optional `rejected_vacuous`/`stall_detected`/`targeted_hints`/`revert_hints` …
  `task_done` with the same `outcome`.
- **Outcome unchanged**: returns the same outcome string the inline loop set
  (`passed` / `compiled` / `vacuous_pass` / `exhausted` / `fix_failed` /
  `sandbox_unavailable` / `run_error`).
- **File writes unchanged**: writes the PoC to the same `poc_dir` path each attempt and
  quarantines on failure exactly as before.
- **No `sys.exit`**: any exit conditions stay in `main()` (setup/budget), not in the
  extracted body — the body signals via its return value / events.

## What the integration test drives through it

Per scenario (data-model.md's outcome table): construct `task`, a scripted fake
`client` (via monkeypatched `draft`/`fix`), a sentinel `sandbox` with monkeypatched
`run_tests`, a capturing `log`, then call `_process_finding(...)` and assert the
returned outcome and captured events.

## `main()` after extraction

`main()` keeps all setup (argparse, warm/ready, extract_tasks, protocol select,
symbol_index build, grounding per finding) and simply calls `_process_finding(...)`
inside `for task in todo:` — the budget check and the wall-clock guard stay in `main()`
(they gate whether the call happens at all).

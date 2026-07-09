# Research: Harness Verdict-Logic Test Coverage + Orchestration Integration Test

## R1 — How to make the per-finding loop testable: extract, don't heroically monkeypatch

**Decision**: Extract `main()`'s per-finding loop body (currently ~200 lines,
`scripts/poc_queue_runner.py` between the `task_start` and `task_done` log events)
into a single behavior-preserving function, e.g. `_process_finding(task, *, client,
sandbox, log, symbol_index, protocol_mode, ...grounding/run config...) -> str`
(returns the outcome string). `main()` then calls it once per finding; the emitted
events, the written PoC files, and the returned outcome are byte-for-byte what they
are today.

**Rationale**: The loop body is already a self-contained unit — it reads configuration
computed once before the loop (scaffold, example, file_map, callable_api,
symbol_index, protocol_mode, fork_rpc, require_pass_effective, budgets) and writes only
`log` events plus files under `poc_dir`. Driving it through `main()` instead would
require faking argparse (via sys.argv/env), `warm()`/`ready()`/`available()`/
`supports_tools()`, `extract_tasks`, `DockerSandbox()`, and `SymbolIndex.build`, and
surviving five `sys.exit()` points — a large, brittle test setup for what is really a
test of ONE function's control flow. Extracting is the smaller-risk, higher-clarity
move and directly serves the spec's goal (a fast offline test of the loop).

**Alternatives considered**:
- *Monkeypatch `main()` end-to-end* — rejected: high setup cost, brittle against the
  five `sys.exit` points and the argparse surface, and it would test far more than the
  loop (warm/extract/select-protocol) in one opaque call, making failures hard to
  localize.
- *Leave `main()` as-is and only unit-test the gates (drop US2)* — rejected: the loop's
  control flow (outcome classification, stall→fix wiring, budget/quarantine) is exactly
  where several of this session's bugs lived; it must be covered.

**Constraint**: the extraction MUST be behavior-preserving — same event names/order,
same outcome strings, same file writes. The integration test asserts the event
sequence precisely, which also guards the extraction itself against accidental drift.

## R2 — Test-double shape: fake model + fake sandbox

**Decision**: Two small scripted doubles, matching only the surface the loop actually
uses:
- **Fake model**: an object with the `LocalClient` methods the loop reaches through
  `draft()`/`fix()` → ultimately `.chat()` (tool mode) or `.generate()` (marker mode)
  and `.model`. It returns a scripted sequence of drafts/fixes. Simplest form: script
  at the `draft()`/`fix()` level by monkeypatching `pqr.draft`/`pqr.fix` to pop from a
  scripted list — the loop calls them as module-level names, so this is a clean seam
  and avoids re-deriving the whole chat round-trip (already covered by its own unit
  tests).
- **Fake sandbox + fake `run_tests`**: `run_tests` is imported at module top
  (`pqr.run_tests`) and called positionally in the loop, so monkeypatch `pqr.run_tests`
  to return scripted `TestResult(passed, exit_code, stdout, stderr)` per attempt. The
  `sandbox` object itself is only passed through to `run_tests`, so a bare sentinel
  suffices.

**Rationale**: The loop's decision logic keys entirely on the `TestResult` fields and
the returned code string — nothing else about the model or Docker matters to outcome
classification. Scripting at `draft`/`fix`/`run_tests` gives full control of every
path with the least machinery, and keeps the integration test focused on the LOOP, not
on re-testing the round-trip or the sandbox (each already/separately covered).

**Alternatives considered**:
- *A full fake `LocalClient` implementing chat/generate/warm/ready* — more faithful but
  re-exercises the round-trip the unit tests already cover; unnecessary for a
  loop-control-flow test. Keep it as an option if a path needs real `draft()` behavior.

## R3 — US3: resolve inherited state variables via SymbolIndex

**Decision**: Replace `scaffold_missing_types`'s single-file regex with a
`SymbolIndex`-backed resolution: build (or reuse) an index over the scaffold file plus
the project (so parents resolve), read the scaffold contract's inheritance chain
(`is A, B`), and consider a target type "provided" if any contract in the scaffold's
own body OR its transitive parents declares a `state_var` Symbol of that type.
`SymbolIndex` already indexes `state_var` symbols with their contract and (via the
parsed AST) the contract's `baseContracts`, so the inheritance walk is data already
present, not new parsing.

**Rationale**: The current regex only sees `Type name;` in the one file's text — blind
to a variable declared in an inherited parent, the exact regex-fragility class specs
007/008 moved away from, and `SymbolIndex` (one function away in the same file) already
resolves it correctly. Keeping the check diagnostic-only (non-gating) and its log event
unchanged means the only change is precision, not behavior contract.

**Alternatives considered**:
- *Extend the regex to also scan parent files* — rejected: reimplements a worse
  `SymbolIndex`; inheritance resolution via text is exactly what the AST index exists
  to avoid.
- *Leave it single-file and just document the limitation* — rejected: it's a live
  false-positive source and the correct tool is already in the file.

## R4 — Where the integration test lives

**Decision**: The EXISTING `tests/integration/` directory gains `test_poc_runner_loop.py`,
run under the same offline pytest invocation as `tests/unit`. Pure-unit verdict/repair
tests stay in `tests/unit/test_poc_queue_runner.py`.

**Rationale**: The loop test is a different granularity (multi-function control flow)
than the pure-unit gate tests; a separate directory keeps that distinction visible and
mirrors the project's existing split (`tests/unit`, `tests/architecture`,
`tests/security`, `tests/frontend`). Both are offline and run together; no separate
tooling.

**Alternatives considered**:
- *Put it in `tests/unit/`* — acceptable but blurs unit vs. loop-integration; the
  project already separates test tiers by directory, so follow that.

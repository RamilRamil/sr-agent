# Feature Specification: Harness Verdict-Logic Test Coverage + Orchestration Integration Test

**Feature Branch**: `009-harness-verdict-tests`

**Created**: 2026-07-06

**Status**: Draft

**Input**: User description: "Harness verdict-logic test coverage + orchestration integration test (SR-agent PoC-workability harness). A code review found the functions that DECIDE whether a PoC passed/failed (`_compiled`, `_poc_defects`, stall signatures, deterministic repair helpers) have ZERO direct unit tests — the exact gates where a bug produces a false milestone (spec 006 traces to a `_compiled` denylist bug caught by hand in a live run, still untested). `main()`'s whole orchestration loop has no integration test; every bug this session surfaced only in a live GPU run. Scope: (1) direct offline unit tests for every verdict gate + repair helper; (2) an integration test driving `main()`'s draft→test→fix loop through a fake client + fake sandbox; (3) re-platform `scaffold_missing_types` (regex, blind to inherited state vars) onto the AST-backed SymbolIndex. Out of scope: mutation-based PASS verification, Stage 1 scaffold synthesis, datetime deprecation cleanup, kernel OrchestratorLoop changes, new live-run infra."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **operator/maintainer** of the PoC-workability harness —
this is an internal reliability feature for existing tooling, not an end-user product
feature. It follows the eval-robustness doctrine of
[docs/eval-principles.md](../../docs/eval-principles.md): a verdict must rest on a
signal that can ONLY appear on genuine success, and that discipline must itself be
guarded by tests.

### User Story 1 - The pass/fail gates can't silently regress (Priority: P1) 🎯 MVP

As the operator, I need every function that decides whether a PoC "compiled",
"passed", is "vacuous", or has "stalled" to be pinned by a direct test — so a change
to that logic that reintroduces a false-positive class (like spec 006's denylist
`_compiled` bug that reported 3 genuine compile failures as "compiled") fails a local
test instead of only surfacing as a wrong claim in a live run.

**Why this priority**: These are the exact gates where a bug becomes a false
milestone — the single most damaging failure mode this whole project has hit, and the
motivating incident behind spec 006. They currently have zero direct coverage.

**Independent Test**: Feed each verdict gate its known-tricky inputs (a compile
failure worded differently from any anticipated phrase; a PoC that is empty / mocks
the target / omits the import; two attempts whose identical mistake lands on different
line numbers) and confirm each returns the correct verdict, offline, with no model or
Docker.

**Acceptance Scenarios**:

1. **Given** forge output that did NOT run any test (a genuine compile failure, in any
   wording), **When** the compile-success gate evaluates it, **Then** it reports "not
   compiled" — it never keys on the absence of a known failure phrase.
2. **Given** a PoC that compiles/passes but is empty, mocks the target contract, or
   never imports the real target, **When** the vacuous-PoC gate evaluates it, **Then**
   it reports the defect(s) that downgrade the pass.
3. **Given** two consecutive attempts that fail with the same error message on
   different line numbers (because the model rewrote the whole file), **When** stall
   detection compares them, **Then** it recognizes the stall (keys on message text,
   not line number).

---

### User Story 2 - The whole draft→fix loop is testable without a live model (Priority: P1)

As the operator, I need the harness's per-finding orchestration — draft, run,
classify outcome, repair, retry, quarantine — to be exercisable end-to-end through a
scripted fake model and a fake sandbox, so a bug in the loop's control flow or its
outcome classification is caught locally in seconds instead of only in a metered GPU
run.

**Why this priority**: Every bug found this session (raw tool-call text leaking into
the PoC file, the wrong scaffold, an unrelated test scoring a false PASS) surfaced
only in a live run costing Kaggle quota; most were deterministic and would have been
caught by an offline integration test of the loop.

**Independent Test**: Drive the per-finding loop with a fake model that returns
scripted drafts/fixes and a fake sandbox that returns scripted forge results, and
assert the final outcome classification and the emitted event sequence for each key
path — a clean pass, a rejected vacuous pass, a compile-error repair that then
succeeds, a stall, and budget exhaustion — with no Ollama, Docker, or network.

**Acceptance Scenarios**:

1. **Given** a scripted model whose first draft cleanly passes, **When** the loop
   runs, **Then** the finding's recorded outcome is "passed" and the expected event
   sequence is emitted.
2. **Given** a scripted model whose draft compiles/passes but is vacuous, **When** the
   loop runs, **Then** the outcome is "vacuous pass rejected", not a success.
3. **Given** a scripted model whose draft has a compile error the next fix corrects,
   **When** the loop runs, **Then** it performs a repair round and reaches the
   corrected outcome.
4. **Given** a scripted model that repeats the identical failure every attempt, **When**
   the loop runs, **Then** a stall is detected and the run ends as exhausted.
5. **Given** more findings than the wall-clock/attempt budget allows, **When** the loop
   runs, **Then** it stops at the budget without starting the next finding.

---

### User Story 3 - The scaffold-sufficiency check understands inheritance (Priority: P2)

As the operator, I need the check that flags "this scaffold can't deploy what the
finding needs" to resolve state variables provided through an inherited parent base,
not just ones declared verbatim in the one file — so it doesn't falsely flag a
perfectly good scaffold whose deployment variable lives in a parent it inherits.

**Why this priority**: Lower than the verdict/loop coverage, but it removes a
regex-fragility class the whole spec 007/008 arc was about — and, ironically, the
current check (added 2026-07-06) is a regex living one function away from the
AST-backed `SymbolIndex` that already resolves exactly this correctly.

**Independent Test**: Point the check at a scaffold that provides the needed contract
only via an inherited parent base and confirm it does NOT report it missing; point it
at one that genuinely declares nothing of that type (directly or inherited) and
confirm it DOES report it missing.

**Acceptance Scenarios**:

1. **Given** a scaffold that declares the needed contract's state variable in a parent
   base it inherits, **When** the sufficiency check runs, **Then** it reports the type
   as present (no false "missing").
2. **Given** a scaffold that declares no state variable of the needed type anywhere in
   its inheritance chain, **When** the check runs, **Then** it reports the type as
   missing.

### Edge Cases

- What happens when the fake sandbox / fake model in the integration test needs to
  simulate a partial or malformed result (e.g. a forge run that exits non-zero with
  empty stdout)? → The integration test must be able to script that, and the loop must
  classify it without crashing (it is one of the real paths the loop already handles).
- What happens when a verdict gate is fed input shapes it wasn't designed for (empty
  string, only whitespace, a truncated forge log)? → The unit test pins that it returns
  a safe, defined verdict (typically "not compiled"/"has defects"), never an exception.
- What happens when the re-platformed scaffold check meets a `.sol` file the parser
  can't handle? → It degrades the same way `SymbolIndex` already does elsewhere
  (records the unparsed file, doesn't crash), consistent with research from spec 007.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every function in the harness that produces a pass/fail/compiled/vacuous/
  stall verdict MUST have a direct, offline unit test covering at least its known
  failure-mode inputs (the specific bug classes seen this session).
- **FR-002**: The compile-success check MUST be tested to reject any output that did
  not actually run a test suite, regardless of wording — never accepting output merely
  because a known failure phrase is absent (the spec 006 positive-signal doctrine).
- **FR-003**: The vacuous-PoC check MUST be tested to flag an empty/fully-commented
  test, a re-declared/mocked target contract, and a missing target import.
- **FR-004**: Stall detection MUST be tested to recognize a repeated identical failure
  even when its reported line number shifts between attempts.
- **FR-005**: The deterministic repair helpers (compiler-error-driven hints, the
  import-path and setUp fixers, the revert-feedback builder) MUST each have a direct
  test of their core transform.
- **FR-006**: The harness's per-finding orchestration loop MUST be exercisable
  end-to-end through a scripted fake model and a fake sandbox — no Ollama, no Docker,
  no network — covering the outcome-classification paths: clean pass, rejected vacuous
  pass, compile-error repair, stall, and budget exhaustion.
- **FR-007**: The integration test MUST assert both the final recorded outcome and the
  key events emitted for each path, so a regression in either the control flow or the
  logging contract is caught.
- **FR-008**: The scaffold-sufficiency check MUST resolve state variables provided via
  an inherited parent base (not only those declared in a single file), so it does not
  falsely flag a scaffold whose deployment variable is inherited.
- **FR-009**: All new tests MUST run fully offline (no model, Docker, or network) and
  MUST NOT reference or embed any bug-bounty/audited target's code, names, or paths —
  they use synthetic fixtures or the project's existing offline test fixtures only.

### Key Entities

- **Verdict gate**: a harness function whose output determines a finding's
  pass/fail/compiled/vacuous/stall status (e.g. the compile-success check, the
  vacuous-PoC check, the stall signatures).
- **Deterministic repair helper**: a harness function that transforms a failed
  attempt's forge output into targeted guidance or a mechanical code fix, with no model
  involved.
- **Fake model / fake sandbox**: test doubles that return scripted drafts/fixes and
  scripted forge results, letting the orchestration loop run entirely offline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Reintroducing the spec 006 denylist-`_compiled` bug (or any
  absence-of-failure-phrase verdict) causes at least one existing test to fail — it can
  no longer reach a live run undetected.
- **SC-002**: 100% of the harness's verdict gates and deterministic repair helpers have
  at least one direct offline test.
- **SC-003**: The per-finding orchestration loop's five key outcome paths (clean pass,
  rejected vacuous pass, compile-error repair, stall, budget exhaustion) are each
  covered by an offline integration test that needs no model, Docker, or network.
- **SC-004**: The scaffold-sufficiency check returns the correct answer for a scaffold
  whose needed type is provided only through inheritance (no false "missing").
- **SC-005**: The full offline test suite still passes with the new tests added, and
  every new test completes without any live-run infrastructure.

## Assumptions

- The "operator" is the person running `scripts/poc_queue_runner.py`; this is internal
  tooling reliability work, not an end-user product feature.
- "Fake sandbox" means a test double standing in for the Docker-backed `run_tests`
  path, returning scripted forge stdout/stderr/exit — the real sandbox and its security
  invariants are unchanged and out of scope here.
- Re-platforming `scaffold_missing_types` onto `SymbolIndex` changes only how the check
  resolves declared/inherited types; its diagnostic-only (non-gating) behavior and its
  log event are preserved.
- This is step 1 of a multi-part remediation from a broader harness review; automated
  independent PASS verification (mutation-based) and Stage 1 large-model scaffold
  synthesis are deliberately deferred to their own later specs and are NOT in scope
  here.
- No change to the secure kernel (`sr_agent/…` orchestrator, memory, confirmation) is
  required or made — this feature is confined to the standalone harness and its tests.

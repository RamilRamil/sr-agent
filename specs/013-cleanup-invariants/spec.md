# Feature Specification: Deprecation Cleanup + Architecture-Invariant Guards

**Feature Branch**: `013-cleanup-invariants`

**Created**: 2026-07-10

**Status**: Implemented

> **Implementation note (2026-07-10)**: The original scope named 6 `datetime.utcnow()`
> *call* sites (5 files). During implementation a bare-`utcnow` scan found **5 more**
> sites — `default_factory=datetime.utcnow` function references (no parens) in
> `sr_agent/models/memory.py`, `sr_agent/models/chat.py` (×2), and
> `sr_agent/packs/audit/session.py` (×2) — which emit the **same** deprecation when a
> model is instantiated without that field, and were the source of the residual
> `utcnow` warnings after the 6 call sites were fixed. US1's actual goal (a
> `utcnow`-warning-free suite) required fixing these too, so scope was extended to **11
> sites across 8 files**; all use the tz-aware form (`lambda: datetime.now(timezone.utc)`
> for the factories). No test pins these fields' naive shape (verified), so the change is
> behavior-safe. `tests/security/generate_fixtures.py` also uses `utcnow` but is test
> tooling, not kernel/pack code — left as-is per the production-code scope.

**Input**: User description: "Fix `datetime.utcnow()` deprecations (6 kernel/pack call sites, ~84 suite warnings, an error on a future runtime) with the timezone-aware modern form, preserving behavior; add two architecture-invariant guard tests — the SourceType trust hierarchy ordering (Principle I), and that the PoC harness executes PoC/forge code ONLY through the sandbox (`run_tests`/`DockerSandbox`), benign git subprocesses allowed. Validate offline: suite passes with zero remaining `utcnow` warnings from these sites; the two invariants pass and would fail if the ranking changed or a direct forge-exec were introduced. Out of scope: broad datetime refactor / clock abstraction; changing what a timestamp means; the Mythril/smartgraphical subprocess; any behavior change beyond the mechanical call replacement; new dependencies. Roadmap item 5, the final harness-review candidate — pure hardening."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **maintainer**. This is pure hardening — it changes no
feature behavior; it removes a deprecation and pins two structural properties the
project already relies on.

### User Story 1 - No deprecated timestamp calls (Priority: P1) 🎯 MVP

As the maintainer, I need the codebase free of `datetime.utcnow()` — deprecated and
scheduled for removal — so the project keeps running (and its test output stays clean)
on a future runtime, without changing what any timestamp means.

**Why this priority**: On a future Python these deprecations become errors; the fix is
mechanical but load-bearing for forward-compatibility.

**Independent Test**: Run the full suite and confirm zero `datetime.utcnow()`
deprecation warnings originate from the 6 known call sites; each timestamp still
represents the same UTC instant.

**Acceptance Scenarios**:

1. **Given** the codebase, **When** the full test suite runs, **Then** no
   `datetime.utcnow()` deprecation warning is emitted from the kernel/pack call sites.
2. **Given** a timestamp produced by a fixed call site, **When** it is stored/displayed,
   **Then** it represents the same UTC instant as before (only the deprecated call is
   replaced; no test that pins a timestamp's meaning regresses).

---

### User Story 2 - The SourceType trust hierarchy can't silently change (Priority: P1)

As the maintainer, I need the SourceType trust-hierarchy ordering
(`human_input > tool_output > external_llm_output / human_relayed_tool >
llm_inference`) pinned by a test — because Principle I (the trust hierarchy is
authoritative; model/relay output must never outrank human input) depends on that exact
ordering, and a silent reordering would be a security regression no current test would
catch.

**Why this priority**: A change to this ranking is a constitution-level security
regression; it must fail a test, not slip through.

**Independent Test**: An architecture test asserts the exact ranking; flipping any two
ranks makes it fail.

**Acceptance Scenarios**:

1. **Given** the SourceType trust ranking, **When** the invariant test runs, **Then** it
   asserts `human_input` outranks `tool_output` outranks the `external_llm_output`/
   `human_relayed_tool` tier outranks `llm_inference`.
2. **Given** a hypothetical reordering (e.g. `external_llm_output` raised to outrank
   `tool_output`), **When** the test runs, **Then** it fails.

---

### User Story 3 - The harness executes PoCs only through the sandbox (Priority: P2)

As the maintainer, I need a test guaranteeing the PoC-workability harness runs
attacker-influenced PoC/forge code ONLY through the network-isolated sandbox
(`run_tests`/`DockerSandbox`) — never via a direct `forge`/shell subprocess — so the
constitution's sandboxed-execution requirement can't be silently bypassed by a future
edit. The harness's benign git subprocesses (the mutation-verify `git apply`, the
git-tracked-file listing) must remain allowed — the guard distinguishes "run a
PoC/forge" from "run git".

**Why this priority**: Lower than the trust-hierarchy pin, but it guards the same
security posture (sandboxed execution of untrusted code) against a regression the
current tests wouldn't catch.

**Independent Test**: An architecture test inspects the harness's execution calls and
asserts none directly execute PoC/forge/shell code (only `run_tests` does), while git
subprocesses are allowed.

**Acceptance Scenarios**:

1. **Given** the harness source, **When** the invariant test runs, **Then** every
   PoC/forge execution routes through `run_tests` (sandbox-backed) — no direct
   `forge`/`sh -c` subprocess.
2. **Given** the harness's existing git subprocesses (`git apply`, `git ls-files`),
   **When** the test runs, **Then** they are recognized as allowed and do not fail it.
3. **Given** a hypothetical direct `subprocess.run(["forge", "test", ...])` added to the
   harness, **When** the test runs, **Then** it fails.

### Edge Cases

- What happens if a fixed timestamp site is stored as an `isoformat()` string that some
  code later parses? → Verified: the three isoformat sites (relay/confirmation
  `created_at`/`decided_at`) are only stored/displayed, never parsed back for
  comparison, so the tz-aware form (adding an explicit UTC offset) is safe; if any site
  WERE parsed/compared with a pinned shape, that site keeps a behavior-identical form.
- What happens if a new deprecation-free timestamp call is added later? → Out of scope
  to police generally here; this feature fixes the 6 known sites and does not add a lint
  rule (YAGNI).
- What if the harness legitimately needs a new non-git subprocess later? → The invariant
  test targets PoC/forge execution specifically; a genuinely new benign subprocess would
  be evaluated then — the test documents the current guarantee, not a blanket ban.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every `datetime.utcnow` usage in the kernel/pack — both direct calls and
  `default_factory` references (11 sites across 8 files; see Implementation note) — MUST
  be replaced with a timezone-aware UTC equivalent, representing the same instant.
- **FR-002**: No behavior that an existing test pins (a timestamp's meaning/shape) may
  regress — a site whose exact string shape is asserted keeps a behavior-identical form;
  sites only stored/displayed may adopt the tz-aware form.
- **FR-003**: After the change, the full test suite MUST emit zero `datetime.utcnow()`
  deprecation warnings from these sites.
- **FR-004**: An architecture-invariant test MUST pin the SourceType trust-hierarchy
  ordering exactly, and MUST fail if any two ranks are reordered.
- **FR-005**: An architecture-invariant test MUST assert the PoC harness executes
  PoC/forge code only through `run_tests` (sandbox-backed), with benign git subprocesses
  explicitly allowed, and MUST fail if a direct `forge`/shell PoC execution is added.
- **FR-006**: All validation MUST be offline — no model, Docker, or network; the new
  tests run in the existing offline suite.
- **FR-007**: No feature behavior changes and no new runtime dependency is introduced —
  this is pure hardening.

### Key Entities

- **Timestamp call site**: one of the 6 `datetime.utcnow()` usages, each producing a UTC
  instant that must be preserved under the fix.
- **Trust-hierarchy ranking**: the SourceType→rank map Principle I depends on.
- **Harness execution path**: the harness's code-execution calls, partitioned into
  sandboxed PoC/forge runs (must go via `run_tests`) and benign git subprocesses
  (allowed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full offline suite runs with zero `datetime.utcnow` deprecation
  warnings from the fixed kernel/pack sites (down from ~84) — verified by escalating that
  specific warning to an error over the previously-warning tests (272 passed, 0 utcnow).
- **SC-002**: Every previously-passing test still passes — no behavior regression (the
  timestamps mean the same instant).
- **SC-003**: The SourceType trust-hierarchy invariant test passes and fails under a
  simulated reordering.
- **SC-004**: The harness-sandbox invariant test passes, recognizes the existing git
  subprocesses as allowed, and fails under a simulated direct forge-exec.
- **SC-005**: No new runtime dependency; no feature behavior change.

## Assumptions

- The "user" is the maintainer; this is internal hardening, not an end-user feature.
- The three isoformat timestamp sites are only stored/displayed (verified: no code
  parses them back for comparison), so the tz-aware form is safe; the non-isoformat
  sites (`completed_at`, `generated_at`) are datetime values whose UTC instant is
  preserved.
- The two new invariants live alongside the existing `test_kernel_does_not_import_packs`
  in `tests/architecture/`, run in the same offline suite.
- The harness-sandbox invariant targets PoC/forge execution specifically; the harness's
  git subprocesses (`git apply` for mutation-verify, `git ls-files` for tracked-file
  discovery) are benign and explicitly allowed.
- This is roadmap item 5, the final deferred harness-review candidate; after it, that
  remediation arc is complete.
- The only kernel touch is the mechanical timestamp-call replacement (no behavior
  change); the invariants are pure test additions.

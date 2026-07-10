# Research: Deprecation Cleanup + Architecture-Invariant Guards

## R1 — `datetime.utcnow()` → `datetime.now(timezone.utc)`, tz-aware is safe here

**Decision**: Replace each `datetime.utcnow()` with `datetime.now(timezone.utc)`, adding
`timezone` to that file's `from datetime import datetime` line. The result is
timezone-aware (an explicit UTC offset) rather than the old naive value.

**Rationale**: `datetime.utcnow()` is deprecated (removal scheduled); `datetime.now(
timezone.utc)` is the documented modern replacement and represents the same instant. The
tz-aware form is safe at all 6 sites: the three isoformat-string sites (relay
`created_at`, confirmation `created_at`/`decided_at`) are only stored/displayed — no
code parses them back for comparison (verified: no `fromisoformat`/string-compare on
them, and no test pins their exact shape) — so adding `+00:00` is a strictly-more-correct
no-op for behavior; the two datetime-value sites (`completed_at`, `generated_at`) are the
same UTC instant, tz-aware. No test asserts a naive-shaped timestamp, so nothing
regresses (FR-002).

**Alternatives considered**:
- *`datetime.now(timezone.utc).replace(tzinfo=None)`* (naive-equivalent) — rejected as
  the default: it re-introduces a naive datetime for no benefit; tz-aware is more
  correct and safe here. (Would be the fallback ONLY if a site's exact naive shape were
  pinned — none is.)
- *A clock abstraction / `Clock` injectable* — rejected: YAGNI, out of scope; this is a
  mechanical deprecation fix, not a testability refactor.

## R2 — SourceType invariant: import the real rank map, assert the ordering

**Decision**: The US2 test imports the actual SourceType→rank map from
`sr_agent/models/memory.py` and asserts the exact ordering relations Principle I
depends on: `human_input` > `tool_output` > (`external_llm_output` ==
`human_relayed_tool`) > `llm_inference`. A reordering (e.g. raising `external_llm_output`
above `tool_output`) flips a relation and fails the test.

**Rationale**: The ranking is the machine-readable form of the constitution's trust
hierarchy; pinning the real map (not a copy) means the test guards the source of truth
directly. Asserting the relations (not just a frozen dict literal) documents WHY each
rank matters and fails clearly on a reorder.

**Alternatives considered**:
- *Freeze the exact dict literal* — acceptable but less expressive; asserting the
  ordering relations makes the security intent (model/relay never outranks human/tool)
  legible and is equally strict.

## R3 — Harness-sandbox invariant: AST-scan subprocess commands, allow git

**Decision**: The US3 test `ast`-parses `scripts/poc_queue_runner.py`, finds every
`subprocess.run(...)`/`subprocess.Popen(...)` call, and asserts each one's command is a
git invocation (its first list element is the literal `"git"`), i.e. no direct
`forge`/`sh -c`/PoC execution — PoC/forge runs go only through `run_tests` (which the
harness imports and which uses `DockerSandbox`). A hypothetical
`subprocess.run(["forge", "test", …])` added to the harness fails the test.

**Rationale**: The constitution requires attacker-influenced code (forge/PoCs) to run
only in the sandbox; the harness honors this by routing all PoC execution through
`run_tests`. Its only direct subprocesses are benign git (mutation-verify `git apply`,
`git ls-files`), which the test recognizes and allows. An AST scan is exact and
regression-proof: a future direct forge-exec can't slip past it.

**Alternatives considered**:
- *A regex/grep for `forge`* — rejected: brittle (matches comments/strings); AST is
  precise about actual call targets and their argument literals.
- *A runtime guard (wrap subprocess)* — rejected: over-engineering for a
  structural property a static test pins exactly, and it would add runtime surface.

## R4 — Validation

**Decision**: US1 is proven by the full offline suite running with zero
`datetime.utcnow()` deprecation warnings from these sites (a `-W error::DeprecationWarning`
scoped check, or a grep asserting no `utcnow(` remains in the 6 files, plus the suite
staying green). US2/US3 are the two new tests, each with a positive assertion and (in
the test body or a companion assertion) a demonstration that a reorder / a direct
forge-exec would fail. All offline (FR-006).

**Rationale**: The cleanest objective signal for the deprecation removal is "no
`utcnow(` left in the touched files AND the suite green"; the invariants are ordinary
offline tests in the existing architecture tier.

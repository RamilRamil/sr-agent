# Feature Specification: Make via_ir Compilation Viable in the Harness Sandbox

**Feature Branch**: `027-sandbox-viair-memory`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "The first live proof-eval run (spec 026, N=1) surfaced that the harness cannot compile the target at all: solc is OOM-killed. The sandbox caps memory at 512 MB; the target compiles with via_ir (needs GBs). Raise the STANDALONE harness's sandbox memory (env-tunable, calibrated), keep the secure agent at 512 MB, and reuse forge's cache in the mutation-verify copy so patched rebuilds are incremental, not cold full builds."

## Context: what the live run proved

Spec 026's first baseline run reported 0/5 verified with a funnel cliff at **compiled** — 0 of 4 extracted cases compiled — and the recorded error was `solc exited with signal: 9 (SIGKILL)`. Diagnosed from the artifact, triangulated three ways: the sandbox caps container memory at **512 MB**; the target builds with **via_ir** (a Yul-IR pipeline needing multiple GB for a full build); and a clean-directory re-run of a finding that previously OOM'd gave **2/2 SIGKILL**, ruling out stale-file bloat. A **cold** via_ir build of the target does not fit in 512 MB, so solc is killed.

It "worked before" only because forge's incremental cache was warm — the container recompiled just the tiny proof — until a compile-check earlier this session invalidated the cache and forced a full cold rebuild. This is **not** a proving regression, **not** directory hygiene, and **not** about the number of proofs: one big run and the eval's repeated runs hit the same one-time full-build wall.

Two parts follow: raise the memory ceiling so a cold build survives (correctness), and reuse the build cache where cold rebuilds happen most (cost).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The harness can compile the target again (Priority: P1)

An operator runs the workability harness (or the proof-eval that drives it) against a target that requires the memory-heavy compilation pipeline, and it compiles instead of being killed. The funnel stops showing a hard wall at the compile stage caused by the environment rather than by the proofs.

**Why this priority**: Nothing downstream works without it. Right now every compile in a cold-cache state is killed, so the harness produces zero compiled proofs and the eval measures the environment's memory ceiling instead of proving ability. This is the correctness fix.

**Independent Test**: On a target whose full build was being killed at the old memory ceiling, a fresh (cold-cache) build now completes; re-running a finding that previously gave repeated kills now compiles.

**Acceptance Scenarios**:

1. **Given** a target requiring the heavy compilation pipeline and a cold cache, **When** the harness compiles a proof, **Then** the build completes instead of being killed for want of memory.
2. **Given** the raised ceiling, **When** an operator needs a different value for a heavier or lighter target, **Then** the ceiling is adjustable without a code change (a configuration knob), with a sensible calibrated default.
3. **Given** the harness sandbox is raised, **When** the secure interactive agent runs, **Then** its sandbox memory ceiling is unchanged.

---

### User Story 2 - Verified passes stop paying a full cold rebuild each time (Priority: P1)

When a proof passes, the falsification step (spec 025) copies the project, applies the finding's fix, and rebuilds — today always a cold full build because the copy omits the build cache, so it is both an out-of-memory risk and a multi-minute cost on every passing proof. With this feature the copy carries the build cache, so only the one patched file (and its dependents) recompiles — seconds and a small memory peak — while the falsification behaves identically otherwise.

**Why this priority**: falsification is the most frequent place a cold build happens (every passing proof triggers one), so it is both the biggest remaining out-of-memory risk after Story 1 and the dominant time cost of an eval batch. Fixing it is what makes running the eval at any real N affordable.

**Independent Test**: A passing proof's falsification rebuild reuses the cache and recompiles only the changed file(s); the real target tree is still never modified and the same proof is still re-run.

**Acceptance Scenarios**:

1. **Given** a passing proof and a fix to apply, **When** falsification copies the project, **Then** the copy includes the build cache so the patched rebuild is incremental, not a full cold build.
2. **Given** the incremental patched rebuild, **When** it runs, **Then** the falsification verdict is produced by the same rule as before (the proof must fail on the fix), and the real target tree is unmodified.
3. **Given** a source file changed by the fix, **When** the patched build runs, **Then** that file (and only its dependents) is recompiled — a stale cached artifact for it is never reused.

---

### User Story 3 - The memory raise cannot be silently lost, and stays scoped to the harness (Priority: P1)

A maintainer must be able to trust that the operator harness keeps its raised ceiling and the secure agent keeps the low one. A guard makes a future refactor that drops the harness back to the low default fail loudly, and pins that the secure interactive agent's sandbox is not raised.

**Why this priority**: the exact failure this feature fixes is a low memory ceiling meeting a heavy build. If a later change silently reverts the harness to the low default, the out-of-memory kill returns with no signal. And the raise must not leak into the secure agent, whose tighter ceiling is a deliberate posture.

**Independent Test**: A test asserts the harness builds its sandbox with a ceiling greater than the kernel default and that the secure agent's construction does not raise it; flipping either back fails the test.

**Acceptance Scenarios**:

1. **Given** the harness's sandbox construction, **When** inspected, **Then** its memory ceiling is greater than the kernel default.
2. **Given** the secure interactive agent's sandbox construction, **When** inspected, **Then** its memory ceiling equals the kernel default (unchanged).
3. **Given** a refactor that reverts the harness to the default, **When** the test runs, **Then** it fails loudly.

---

### Edge Cases

- The configured memory value is unset → a sensible calibrated default applies (the harness never runs at the old too-low ceiling by omission).
- The configured value is still too low for a given target → the build may still be killed; that is an operator-tunable condition surfaced as the same compile failure, not a crash of the harness.
- The build cache in the copy is stale relative to the applied fix → the changed file is recompiled (cache is keyed on content), so a stale artifact is never used; correctness is preserved.
- The host lacks enough memory to grant the raised ceiling → the container runtime's own error surfaces; this feature does not mask it.
- The secure interactive agent path is exercised → it must be provably unaffected (Story 3).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The standalone workability harness MUST construct its execution sandbox with a memory ceiling higher than the kernel default, sufficient for a cold full build of a via_ir target.
- **FR-002**: That memory ceiling MUST be adjustable via configuration (an environment variable) without a code change, defaulting to a calibrated value in the multi-gigabyte range when unset.
- **FR-003**: The raised ceiling MUST apply ONLY to the standalone harness; the kernel sandbox default and the secure interactive agent's sandbox MUST remain at the existing low ceiling.
- **FR-004**: The default value MUST be calibrated EMPIRICALLY — chosen as the smallest ceiling at which a cold via_ir build of the reference target reliably survives — not guessed as an arbitrary constant.
- **FR-005**: The falsification step's project copy MUST include the build cache so the patched rebuild recompiles only the changed file(s) and dependents, not a full cold build; irrelevant heavy directories (version control, third-party modules) remain excluded.
- **FR-006**: Including the build cache MUST NOT change the falsification behavior: it still works on an ephemeral copy, re-runs the same proof, produces the verdict by the same rule, and NEVER mutates the real target tree.
- **FR-007**: A stale cached artifact for a file changed by the fix MUST NOT be reused; the changed file is recompiled (the cache is content-keyed).
- **FR-008**: The harness's main compile loop MUST benefit from a warm cache across a run/batch — the first build may be cold, but subsequent builds reuse the cache — so an eval of many case-runs does not pay a full cold build every time.
- **FR-009**: No security invariant of the sandbox MAY change: network isolation (and its explicit fork opt-in), dropped capabilities, no-new-privileges, the process limit, ephemerality, and the property that proofs execute ONLY inside the sandbox all remain exactly as they are. Memory is a denial-of-service protection knob, not an isolation invariant.
- **FR-010**: A regression guard MUST assert the harness constructs its sandbox with a memory ceiling greater than the kernel default, and that the secure interactive agent's is not raised — so a future change cannot silently reintroduce the out-of-memory kill or leak the raise into the secure agent.
- **FR-011**: Offline, deterministic tests MUST validate: the harness sandbox is built with the raised, configurable ceiling and the secure agent's is not (FR-003/FR-010); the falsification copy no longer excludes the build cache (FR-005); and these run with no model, container, or network.
- **FR-012**: An empirical calibration/validation step (live, operator-run, not a unit test) MUST confirm that a cold via_ir build of the reference target survives at the chosen ceiling where it was killed at the old ceiling, and that the finding which previously gave repeated kills now compiles.

### Key Entities

- **Sandbox memory ceiling**: the per-run memory cap of the execution container — a DoS-protection knob, distinct from the isolation invariants; raised for the harness, unchanged for the secure agent.
- **Build cache**: forge's incremental compilation artifacts (content-keyed); reused in the falsification copy so patched rebuilds are incremental.
- **Falsification copy**: the ephemeral project copy the verification step patches and rebuilds; now carries the build cache but is otherwise unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the reference target with a cold cache, a proof build that was killed at the old ceiling completes at the new ceiling — 100% of the time in the calibration check.
- **SC-002**: The memory ceiling is changeable by configuration with no code edit, and a sensible default applies when unset.
- **SC-003**: The secure interactive agent's sandbox memory ceiling is unchanged (verified by test), 100% of the time.
- **SC-004**: A falsification rebuild after this change recompiles only the changed file(s), reducing a passing proof's verification from a multi-minute full build to seconds, while the real target tree stays unmodified.
- **SC-005**: A refactor that reverts the harness ceiling to the default, or raises the secure agent's, fails a test.
- **SC-006**: No sandbox security invariant changes; the sandbox-only-execution guard still passes.
- **SC-007**: Re-running the finding that previously gave 2/2 kills now reaches at least the compiled stage.

## Assumptions

- The execution sandbox's memory ceiling is already a settable field, so scoping the raise to the harness needs no change to the shared sandbox mechanism — only how the harness constructs its instance.
- The reference target genuinely requires via_ir to compile (removing it is not an option), so the fix must accommodate a heavy build rather than avoid it.
- The build cache is content-keyed, so including it in the falsification copy is safe: a file changed by the fix is recompiled, never served stale.
- The host has enough memory to grant the raised ceiling for a normal operator run; if it does not, the container runtime surfaces that directly and this feature does not mask it.
- Warming the first build once per run/batch is acceptable operator cost; the mounted project's cache then warms for subsequent builds.

## Out of Scope

- Changing the kernel sandbox class default or the secure interactive agent's memory ceiling — only the standalone harness rises.
- Disabling via_ir — the target requires it (likely stack-too-deep); removing it is not an option.
- Baking the fully-compiled target into the container image — a separate, target-coupling optimization; the image already bakes the compiler binaries, not the compiled project.
- The extraction id-scheme nondeterminism that made spec-026's strata-3 die at extraction — a real, separate fragility (the finding-identifier coupling) needing its own fix.
- Any change to what counts as compiled / passed / verified — specs 025 and 026 own the outcome vocabulary and the eval metrics.

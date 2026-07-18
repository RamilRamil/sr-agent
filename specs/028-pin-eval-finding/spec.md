# Feature Specification: Pin the Finding for the Proof-Eval

**Feature Branch**: `028-pin-eval-finding`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Decouple the harness's welded extract→prove so the proof-eval feeds a curated, deterministic finding instead of re-running nondeterministic model extraction every case-run. The harness gains a task-input that bypasses extraction; the eval case carries a human-curated finding and pins it across all runs. Fixes spec-026's strata-3 extraction death (`only_ids_not_found`) at the root and removes extraction variance from the measured number."

## Context: what the live run proved, and why pinning is the right fix

Spec 026's first proof-eval run had strata-3 die at the **extraction** stage — `only_ids_not_found: ['3']`. Diagnosed from the artifact: the harness re-runs the model's report→tasks extraction on **every** case-run, and the model assigns finding identifiers nondeterministically across runs (observed in the run log: `1..5`, `H-01..H-05`, `F-01..F-05`, `Lead-01..`), while the eval's case carries a **fixed** identifier that must match a **fresh** extraction. When the schemes disagree, the finding is never proven — a death that has nothing to do with proving.

This is **not** a general harness bug. A normal operator run is self-consistent: extraction happens once, and the operator's `--only`/`--fix-patch` reference identifiers from **that same run's** task list. The mismatch bites **only** the eval, which pins a fixed external identifier against N fresh extractions.

The deeper problem is beyond the identifier: even if identifiers were normalized, the model re-extracts each finding's **title/location/description** differently every run, so the prover's input drifts run to run — **extraction variance leaks into the measured number**.

Best practice (spec 026's own experimental-hygiene principle: pin everything but the one variable): the proof-eval measures **proving** given a known finding. Extraction (report→tasks) is the **discovery** axis that the discovery benchmark owns. Conflating them makes a proof-eval delta unattributable — the exact "3/5 vs 2/5" disease. So **hold the finding constant and remove extraction from the measured path.** This also cleanly **decouples** two stages the harness currently welds together — a small, generally useful improvement whose first consumer is the eval.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The eval proves a fixed finding, not a re-guessed one (Priority: P1)

An operator runs the proof-eval; each case's finding is taken verbatim from the case definition and handed to the prover unchanged on every run, instead of being re-derived by the model each time. A case can no longer die because a fresh extraction named the finding differently, and the prover sees identical input across all runs of a case.

**Why this priority**: This is the whole feature. Without it, the eval measures the prover plus extraction noise, and cases die at extraction for reasons unrelated to proving — so the number is neither clean nor attributable.

**Independent Test**: Run the eval over a case set; every case reaches at least the drafting stage (none dies at extraction for an identifier mismatch), and the finding text fed to the prover is byte-identical across a case's runs.

**Acceptance Scenarios**:

1. **Given** a case with a curated finding, **When** the eval runs it N times, **Then** all N runs prove the same finding (same identifier, same title/location/description) and none dies at extraction for an identifier mismatch.
2. **Given** the harness is told to prove a supplied finding, **When** it runs, **Then** it does NOT invoke the model's report→tasks extraction; the supplied finding is what gets drafted.
3. **Given** a supplied finding, **When** the run proceeds, **Then** the pipeline stages downstream of extraction (drafting, compiling, falsification) behave exactly as they do for an extracted finding.

---

### User Story 2 - The harness can be handed a task instead of extracting one (Priority: P1)

An operator (or the eval) can point the harness at a task list to prove, bypassing the model extraction, while the report's own fix material is still read. This decouples the report→tasks stage from the proving stage — useful on its own for reproducibly re-running one finding without extraction noise, or debugging the prover in isolation.

**Why this priority**: This is the general capability the eval consumes. The harness currently welds extraction and proving in one path; separating them is a small architectural improvement with value beyond the eval (deterministic re-runs, prover debugging).

**Independent Test**: Point the harness at a task file; it proves those tasks without calling the model extractor; without the task input, it extracts with the model exactly as before.

**Acceptance Scenarios**:

1. **Given** a task input is provided, **When** the harness runs, **Then** it loads the tasks from that input and does NOT call the model extractor.
2. **Given** NO task input is provided, **When** the harness runs, **Then** it extracts with the model exactly as today — the default behavior is unchanged.
3. **Given** a task input is provided, **When** the harness starts proving, **Then** it emits the same task-list-ready signal (with the supplied identifiers) that downstream consumers and the eval funnel expect, so a pinned finding is not mistaken for one that failed extraction.
4. **Given** a task input is provided, **When** a finding's fix comes from the report, **Then** the report's own fix material is still read (the deterministic report-fix path is unaffected — only the model's task extraction is bypassed).

---

### User Story 3 - The eval case is self-contained ground truth (Priority: P1)

A proof-eval case carries the finding itself — a human-curated title, location, and description transcribed from the published report — alongside its identifier and fix. The case definition is deterministic and model-free, so what the eval proves is fixed ground truth, not a model's whim. A case missing its curated finding fails loudly rather than silently falling back to nondeterministic extraction.

**Why this priority**: The finding is the eval's ground truth, like the fix and like the discovery benchmark's human-curated labels. If it could fall back to model extraction, the determinism this feature exists to provide would silently evaporate.

**Independent Test**: A case manifest with the curated finding loads and pins it; a manifest missing the finding fields fails to load with a clear error.

**Acceptance Scenarios**:

1. **Given** a case manifest with a curated finding (identifier, title, location, description) and a fix, **When** it loads, **Then** the finding is available to pin for every run.
2. **Given** a case manifest missing any curated finding field, **When** it loads, **Then** loading fails loudly — never a silent fallback to model extraction.
3. **Given** a loaded case, **When** the eval runs it, **Then** the pinned finding is fed to the harness identically on every run of that case.

---

### Edge Cases

- The task input names a finding whose identifier differs from a fix's identifier → the fix must still attach to the right finding (the case pins both from one source, so they agree by construction).
- The task input is malformed or empty → loud failure, not a silent fall-through to model extraction.
- A curated case field is present but empty → treated as missing (loud), so an empty description cannot silently produce a degenerate prompt.
- With a pinned finding, the eval funnel's extraction stage is trivially reached (the finding is given) → the funnel must NOT record such a case as an extraction-stage death.
- A normal operator run without the task input → entirely unchanged (still extracts with the model).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST accept a task-list input that, when provided, is used to prove those tasks INSTEAD of invoking the model's report→tasks extraction.
- **FR-002**: The supplied task list MUST use the same shape the harness already produces and records for extracted tasks (per task: identifier, title, location, description).
- **FR-003**: When a task input is provided, everything downstream of extraction (finding selection, operator-fix attachment, drafting, compiling, falsification) MUST behave exactly as for an extracted task.
- **FR-004**: The report's own deterministic fix material MUST still be read when a task input is provided; only the MODEL extraction of the task list is bypassed.
- **FR-005**: When a task input is provided, the harness MUST emit the same task-list-ready signal (carrying the supplied identifiers) that downstream consumers and the proof-eval funnel expect, so a pinned finding is never counted as an extraction-stage failure.
- **FR-006**: With NO task input, the harness's behavior MUST be unchanged — it extracts with the model exactly as before (the default path is untouched).
- **FR-007**: A proof-eval case MUST carry a human-curated finding — identifier, title, location, description — in addition to its target, report, and fix references.
- **FR-008**: Loading a proof-eval case that is missing any curated finding field (or has it empty) MUST fail loudly — never a silent fallback to model extraction.
- **FR-009**: The eval MUST feed the pinned curated finding to the harness identically on every run of a case, so the prover's input is byte-identical across a case's runs (the finding's identifier AND text are constant).
- **FR-010**: The pinned finding's identifier and its fix's identifier MUST agree by construction (both come from the one case definition), so the fix attaches to the right finding without a fresh match.
- **FR-011**: The behavior MUST be validated by offline, deterministic tests over SYNTHETIC fixtures (invented task files and manifests, never real target material): the harness loads a task input and does NOT call the model extractor, and emits the task-list-ready signal with the file's identifiers; without the input it still extracts (default unchanged); a case loader requires the curated finding fields and fails loudly when absent/empty; and the eval's per-case invocation writes a well-formed single-task input and includes it in the harness invocation. The actual harness subprocess and any model call MUST NOT run in these tests (stubbed).
- **FR-012**: The five reference (strata-bb) case manifests MUST be curated with their findings and live OUTSIDE the agent repo; no target material is committed.

### Key Entities

- **Curated finding**: the eval's ground-truth finding — identifier, title, location, description — transcribed from the published report by a human, model-free, part of the case definition.
- **Task input**: the harness's alternative to model extraction — a task list handed in to prove directly, bypassing the report→tasks model call.
- **Proof-eval case**: now self-contained — target, report, curated finding, and fix — so what is proven is fixed and deterministic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an eval run, 0% of cases die at the extraction stage for an identifier mismatch (the spec-026 strata-3 failure mode is eliminated).
- **SC-002**: The finding text fed to the prover is byte-identical across all N runs of a case, 100% of the time.
- **SC-003**: With a task input, the harness makes no model extraction call; without it, it extracts exactly as before — both verified by test.
- **SC-004**: A case missing any curated finding field fails to load, 100% of the time; 0% silently fall back to extraction.
- **SC-005**: A pinned finding is never recorded by the eval funnel as an extraction-stage death.
- **SC-006**: The whole offline test path runs with no model, container, or network.
- **SC-007**: The eval now measures the prover's variance without extraction variance mixed in — a case's outcome differences across runs are attributable to the prover/model sampling, not to re-extraction.

## Assumptions

- The harness already produces and records the task-list shape (identifier, title, location, description) it will now also accept as input, so the input format is the existing one, not a new schema.
- The report's fix material is pulled deterministically and independently of the model task extraction, so bypassing extraction does not disturb report-fix reconstruction.
- The proof-eval already loads external case manifests and can be extended to require the curated finding fields, reusing its existing loud-loading discipline.
- Human curation of five short findings (title/location/description already present in the published report) is acceptable one-time operator work, consistent with curating the fixes and the discovery benchmark's labels.
- The eval's per-case harness invocation is a seam the tests stub, so pinning is validated without a live run.

## Out of Scope

- Normalizing or fuzzy-matching extraction identifiers in the general harness — there is no general bug (normal runs are self-consistent); this pins the eval instead.
- Changing the model's extraction behavior or making it deterministic — the fix bypasses extraction for the eval; it does not alter it.
- The discovery axis or the discovery benchmark.
- The memory / via_ir compilation fix (already landed).
- Any change to the outcome vocabulary or the eval's interval/funnel metrics (owned by prior specs).
- A full re-run of the baseline eval — a separate operator step once this lands.

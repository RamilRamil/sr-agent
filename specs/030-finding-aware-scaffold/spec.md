# Feature Specification: Finding-Aware Scaffold Discovery

**Feature Branch**: `030-finding-aware-scaffold`

**Created**: 2026-07-19

**Status**: DEFERRED — not built. A Level-0 opportunity check (deterministic, no model) over the 5
curated strata-bb findings found **0/5 opportunity**: `StrataProtocolDeploymentBase` (pop 8) is BOTH
the most-inherited AND the best-fitting base for every finding, so finding-aware ranking selects the
same base the current agnostic path already picks. The genuine gap (a needed cooldown contract absent
from every base) is not covered by ANY existing base → synthesis is genuinely required, which
finding-aware ranking cannot replace. This spec is SOUND but unmeasurable on our only eval target;
revisit when a target with multiple viable deploy bases is in the dataset. The eval-first check
(spec's own principle) caught this before implementation. Pivoted to scaffold-synthesis HARDENING
(the measurable lever on strata-bb — synthesis is genuinely needed and currently flaky/one-shot).

**Input**: User description: "An intermediate analysis step that searches the target repo for existing deployment/setup infrastructure that fits THIS finding, and only synthesizes a scaffold when none fits."

## User Scenarios & Testing *(mandatory)*

To prove a finding, the harness gives the model a **scaffold** — the contest's shared deployment
infrastructure (a test base that deploys and wires the protocol) that the PoC inherits, so the model
writes the exploit, not the deployment. A PoC is ~90% deployment boilerplate and ~10% attack, and the
deployment is where models flail — so the *right* scaffold is the single biggest lever on whether a
PoC ever compiles-and-triggers.

**Motivation (from two live proof-eval runs + the literature).** Once a capable model (GLM-5.2)
cleared the compile wall, DEPLOYING+WIRING the protocol — not writing the exploit — became the
bottleneck (live: the synthesized base passed an address where an interface type was required, invented
setters, and had an off-by-one import depth). The harness already consumes the contest's deploy base,
but its discovery is **finding-agnostic**: it auto-picks the single *most-inherited* test base across
the whole repo, checks whether that one base declares the finding's needed contract types, and if not,
falls back to **model synthesis** — the flaky path. A finding whose needed contracts live in a
*different, less-popular but sufficient* base still drops to synthesis even though the target already
ships a base that would work. The research agrees the lever is REUSING the provided environment
(PoCo arXiv:2511.02780 searches the repo for existing helpers; A1 arXiv:2507.05558 runs on real state),
not synthesizing from scratch. So: **search first, synthesize last.**

### User Story 1 - Discovery picks the base that fits the finding (Priority: P1)

When auto-discovering a scaffold, the harness enumerates the target's existing tracked test bases,
ranks them by how many of THIS finding's needed contract types each one deploys, and selects the
best-fitting SUFFICIENT base — instead of always taking the single most-inherited base regardless of fit.

**Why this priority**: This is the feature. It directly reduces how often the flaky synthesis path is
reached, by using deployment infrastructure the target already ships.

**Independent test**: In a repo with two tracked bases — a most-inherited one that is INSUFFICIENT for
the finding and a less-inherited one that is SUFFICIENT — discovery selects the sufficient one. Verified
offline over synthetic multi-base fixtures; no model call, no forge.

**Acceptance Scenarios**:

1. **Given** a tracked test tree with base `A` (inherited by many files but missing a contract type the
   finding needs) and base `B` (inherited by fewer files but declaring all the finding's needed types),
   **When** scaffold discovery runs for that finding, **Then** it selects `B`.
2. **Given** two candidate bases that BOTH cover all the finding's needed types, **When** discovery
   ranks them, **Then** the tie is broken by the existing most-inherited popularity signal.
3. **Given** the operator pinned a scaffold via the override, **When** discovery runs, **Then** the
   override is used outright and ranking is bypassed.

### User Story 2 - Synthesis is the honest last resort (Priority: P1)

Model synthesis runs only when NO tracked candidate is sufficient — not as the default for any gap in
the single most-inherited base.

**Why this priority**: Making synthesis a true fallback is the point of the change; without it the
finding-aware ranking would not actually reduce synthesis attempts.

**Independent test**: With no sufficient candidate present, discovery returns the best partial base and
the harness still reaches the (unchanged) synthesis path. Verified offline.

**Acceptance Scenarios**:

1. **Given** no tracked base covers all the finding's needed types, **When** discovery runs, **Then**
   it returns the best-covering partial base and the harness proceeds to the existing synthesis path.
2. **Given** at least one tracked base covers all the finding's needed types, **When** discovery runs,
   **Then** the synthesis path is NOT reached.

### User Story 3 - The run log explains the scaffold choice (Priority: P2)

A discovery event records the candidates considered, each candidate's missing-type count for the
finding, and the chosen base (or that synthesis was reached and why).

**Why this priority**: Attribution — an operator (and the proof-eval) needs to see WHY a base was
picked or why synthesis was reached. Useful but the selection works without it.

**Independent test**: When discovery runs, an event is emitted naming the candidate bases, their
per-candidate missing-type counts, and the selected one. Verified offline.

**Acceptance Scenarios**:

1. **Given** discovery ran over multiple candidates, **When** a base is selected, **Then** an event
   lists the candidates + their missing-type counts + the chosen base.
2. **Given** no candidate was sufficient, **When** synthesis is reached, **Then** the event records
   that (with the best partial's missing types).

### Edge Cases

- **No tracked test tree / no candidate bases at all**: discovery returns empty and the harness
  behaves as today (proceeds toward synthesis / the honest fallback) — never an error.
- **Operator override**: `--test-scaffold`/`POC_SCAFFOLD` wins outright, unchanged; ranking is skipped.
- **Answer-PoC exclusion**: a tracked file that already exploits/asserts the finding (a per-finding
  answer, not a deploy base) is NEVER selectable as a scaffold — candidates are deployment
  infrastructure only.
- **Untracked files**: our own skill-generated PoCs/bases (untracked) are never discovery candidates —
  only git-tracked original files, as today.
- **A finding with no identifiable needed types** (empty target set): every candidate is trivially
  "sufficient"; ranking falls back to the existing popularity signal (today's behavior).
- **Ties on both fit and popularity**: resolved deterministically (stable order) so the same repo +
  finding always picks the same base.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Scaffold auto-discovery MUST enumerate the target's git-tracked candidate test bases
  (the inheritance-target bases discovered today, plus other tracked base/harness contracts under the
  foundry test dir) as a candidate SET, not a single most-inherited pick.
- **FR-002**: Discovery MUST rank each candidate by FIT to the finding — how many of the finding's
  needed contract types the candidate declares/deploys (the same needed-types signal sufficiency
  already uses) — preferring the candidate with the FEWEST missing types.
- **FR-003**: Ties on fit MUST be broken by the existing most-inherited popularity signal, and any
  remaining tie resolved deterministically (stable) so the choice is reproducible.
- **FR-004**: When at least one candidate is SUFFICIENT (zero missing types), discovery MUST select the
  best-fitting sufficient candidate and the harness MUST NOT reach the synthesis path.
- **FR-005**: When NO candidate is sufficient, discovery MUST return the best-covering partial candidate
  and the harness MUST fall through to the existing synthesis path (unchanged).
- **FR-006**: An operator-pinned scaffold override MUST win outright and bypass ranking (unchanged).
- **FR-007**: A candidate that is a per-finding answer PoC (one that exploits/asserts the finding rather
  than deploying infrastructure) MUST NOT be selectable as a scaffold; only deployment/setup bases are
  candidates.
- **FR-008**: Discovery candidates MUST be restricted to git-tracked original files; untracked
  skill-generated PoCs/bases MUST NEVER be candidates.
- **FR-009**: Discovery MUST emit an event naming the candidates considered, each candidate's
  missing-type count for the finding, and the selected candidate (or that synthesis was reached and the
  best partial's gap).
- **FR-010**: The change MUST be confined to scaffold discovery/selection. The synthesis fallback
  (`synthesize_scaffold`), the drafting/repair loop (incl. the 029 trace feedback), the fork oracle,
  the anti-cheat gate, and falsification MUST be untouched.
- **FR-011**: Behavior MUST be validated offline with deterministic tests over SYNTHETIC fixtures
  (invented multi-base test trees + invented finding target types). The model call and forge MUST NEVER
  run in tests (stubbed). No real target material enters the repo (guarded by
  `test_no_target_material.py`).

### Key Entities *(include if feature involves data)*

- **Scaffold candidate**: a git-tracked deployment/setup base contract under the target's test tree —
  a possible scaffold. Carries its contract name, defining file, inheritance-popularity count, and the
  set of finding-needed types it declares.
- **Finding-needed types**: the contract types a finding requires deployed (derived from the finding's
  location, the same signal current sufficiency checking uses). The ranking key.
- **Fit / missing-type count**: per candidate, the number of finding-needed types it does NOT declare;
  zero = sufficient. Primary ranking signal (ascending).
- **Discovery result**: the selected candidate (or none) plus the per-candidate missing-type counts
  recorded in the discovery event.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When a sufficient-but-less-popular base exists alongside an insufficient most-popular one,
  discovery selects the sufficient base (not synthesis) — verified over synthetic fixtures.
- **SC-002**: When no candidate is sufficient, the synthesis path is still reached with the best partial
  base — verified.
- **SC-003**: Ranking prefers fewer missing types, then popularity, deterministically — the same repo +
  finding always yields the same choice (verified).
- **SC-004**: The operator override bypasses ranking (verified).
- **SC-005**: An answer-PoC file is never selected as a scaffold; only tracked deployment bases are
  (verified).
- **SC-006**: The full offline test suite passes with no model/forge/network access, and
  `test_no_target_material.py` passes.
- **SC-007**: `synthesize_scaffold`, the drafting loop, the fork oracle, `_poc_defects`, and
  `mutation_verify` are unchanged (their existing tests still pass).

## Assumptions

- The finding's needed contract types are already derivable in the grounding path (they are — the same
  signal today's sufficiency check consumes); this feature reuses that signal as the ranking key rather
  than inventing a new notion of "fit".
- Ranking by count-of-needed-types-deployed is an adequate fit proxy; a richer semantic fit (does the
  base actually WIRE the contract, not merely declare a variable of its type) is a possible later
  refinement and is not required for this step.
- A single fixed selection policy (fewest missing types, then popularity, then stable order) is
  acceptable — no new operator flag is required.
- The existing "scaffold is shared deployment infrastructure, never a per-finding answer PoC" invariant
  and the git-tracked-only restriction are correct and are preserved, not redesigned.

## Out of Scope

- Changing `synthesize_scaffold` itself — its address↔interface and invented-setter code-quality issues
  are a separate hardening effort.
- The drafting/repair loop and the spec-029 trace feedback.
- Parsing deploy SCRIPTS (`script/*.s.sol`) as a scaffold source — a possible follow-up; this step ranks
  the existing test BASE/harness contracts discovery already reads.
- Agentic between-attempt repo exploration (PoCo-style tool calls) — a larger change.
- The fork oracle, `_poc_defects`, and `mutation_verify`.
- Model selection / the paid-vs-local strategy and any Constitution Principle V matter (this is a
  deterministic discovery change, model-agnostic).

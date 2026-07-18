# Feature Specification: Proof-Pipeline Eval

**Feature Branch**: `026-proof-eval-bench`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "A measuring instrument for the PoC-workability harness — sibling to the discovery benchmark, not an extension of it. Score PROOF quality: run the harness over a fixed case set N times per case and report the fraction reaching passed_verified as a Bayesian interval, plus a per-stage attrition funnel. Bayes@N statistics, enforced experimental hygiene, honest about contamination, no model in the scoring path."

## Context: why this exists

Spec 023 made **discovery** measurable — did we surface the finding. **Proof quality** is still unmeasured: there is no way to answer "did a harness change make proving better?" with a number. The cost showed up directly this session — "3 of 5 before, 2 of 5 after" across two live runs was uninterpretable, because both the prompts AND the finding count changed between them. No pinned baseline, no statistics: the delta was noise dressed as signal.

Spec 025 delivered the missing **unit of measurement**. The outcome now separates `passed_verified` (falsification ran and the proof broke on the finding's fix — the only trustworthy success) from `passed_unchecked` (never verified) and `unverified_pass` (verified as bogus). Before that split, any aggregate over `passed` was meaningless because it conflated proved with never-checked. That unit is what makes this instrument possible.

**Two orthogonal axes — never merged.** The discovery benchmark scores "given a target, did we find the bug" (input = target). This scores "given a target AND a known finding AND its fix, can the harness produce a verified proof" (input = target + finding + fix). Different question, different instrument, its own file — reusing the discovery benchmark's disciplines (external dataset root, nothing committed, offline scoring) but not its code path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Answer "did this change make proving better?" with a number that admits doubt (Priority: P1)

A maintainer runs the eval over a fixed case set before and after a harness change and gets, for each, the fraction of cases that reached a **verified** proof — expressed as an interval, not a bare number — and can say whether the change decidedly helped, decidedly hurt, or is **not yet distinguishable**. For the first time "is the prover better?" has a defensible answer instead of one anecdotal run compared to another.

**Why this priority**: This is the entire point. Every future harness change (a prompt tweak, a new repair guard, a model swap) is currently faith. This turns it into measurement — and, critically, measurement that refuses to over-claim from too little data.

**Independent Test**: Run the eval on a case set at a fixed N and read a verified-fraction interval; run a second configuration and compare — overlapping intervals report "not distinguishable", separated intervals report a decided direction.

**Acceptance Scenarios**:

1. **Given** a case set and a run count N, **When** the eval completes, **Then** it reports the verified fraction as an interval whose width reflects N (smaller N → wider interval), never as a single point number.
2. **Given** two result sets whose intervals overlap, **When** they are compared, **Then** the tool reports "not yet distinguishable", not a winner.
3. **Given** two result sets whose intervals do not overlap, **When** they are compared, **Then** the tool reports the decided direction (which is better).
4. **Given** a single run of a single case, **When** results are produced, **Then** the tool does not present it as a decisive result — its interval is wide by construction.

---

### User Story 2 - See WHERE proofs die, by stage (Priority: P1)

The maintainer gets a per-stage attrition funnel — how many cases reach extraction, drafting, compiling, real-pass, and finally verified — with a named list of which case died at which stage. This says *what to fix next*: many cases reaching real-pass but none verified points at the fixes/verification, not the exploits; cases dying at compile points at the drafter.

**Why this priority**: A single aggregate number tells you *whether* you regressed, not *why*. The funnel is the discovery benchmark's per-class-breakdown lesson applied to the pipeline — it is what converts a bad number into a next action. This session's own situation (many real-passes, zero verified, because the fixes never applied) is exactly what the funnel would have surfaced immediately.

**Independent Test**: Run the eval on a case set and read the funnel; each stage shows a count and the named cases that did not advance past it, and the counts are monotonically non-increasing down the stages.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the funnel is produced, **Then** it shows, per stage (extraction → draft → compiled → real-pass → verified), how many cases reached that stage and names those that did not advance.
2. **Given** a set of case outcomes, **When** the funnel is computed, **Then** stage counts never increase moving down the funnel (a case cannot verify without having compiled).
3. **Given** a run where cases reach real-pass but not verified, **When** the report is read, **Then** the funnel makes that stall visible and attributable to the verification stage, not the drafting stage.

---

### User Story 3 - The instrument cannot inflate its own number (Priority: P1)

The maintainer must be able to trust the verified fraction. A case counts as verified **only** when the harness itself reports a verified proof — the falsification actually ran and the proof broke on the fix. It is never inferred, never derived from a model judging the outcome, and a case with no fix is a loud load error rather than a silent success or skip.

**Why this priority**: This is the project's hardest-won discipline applied to measurement. A permissive gate ("it compiled") once made worthless proofs look successful; a permissive scorer would make a worthless prover look successful, and we would optimize toward the lie. The verified fraction must under-report before it over-reports.

**Independent Test**: Feed the scorer harness outcomes and confirm the verified count equals exactly the number of harness-reported verified outcomes; feed a case manifest missing its fix and confirm a loud load failure; confirm no model participates in scoring.

**Acceptance Scenarios**:

1. **Given** a set of harness outcomes, **When** the verified fraction is scored, **Then** it counts exactly the outcomes the harness reported as verified — nothing inferred, nothing model-judged.
2. **Given** a case manifest without a fix, **When** the dataset loads, **Then** it fails loudly (verified is unreachable without a fix — this is an error, not a skip).
3. **Given** the scoring path, **When** it runs, **Then** no model and no network is involved in producing the score (only the harness runs themselves are expensive, and those are the measured subject, not the scorer).

---

### User Story 4 - Comparisons across incomparable configurations are caught (Priority: P1)

The maintainer cannot accidentally compare two runs that differed in more than the harness version. Each result set records its full run configuration — case set, model, scaffold/example, settings — and comparing two result sets whose configurations differ in anything other than the harness version is flagged, not silently trusted.

**Why this priority**: This is the exact mistake that made "3/5 vs 2/5" meaningless — the two runs differed in prompts and case count, so the delta was unattributable. Experimental hygiene is not advisory here; it is the difference between a measurement and a coincidence.

**Independent Test**: Produce two result sets with differing configurations (e.g. different case sets or models) and attempt a comparison — the tool flags the mismatch instead of reporting a delta.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** its result set is written, **Then** the full run configuration is recorded alongside the results.
2. **Given** two result sets that differ in anything other than the harness version, **When** they are compared, **Then** the mismatch is flagged and no delta is presented as trustworthy.
3. **Given** two result sets identical in configuration except the harness version, **When** compared, **Then** the comparison proceeds and reports the interval relationship.

---

### Edge Cases

- A dataset root or a case path inside the agent's own project area → rejected (target/fix material must stay external), same guard as the discovery benchmark.
- A case whose fix file is absent or does not exist → loud load error (verified is unreachable without it), never a silent skip that would quietly shrink the denominator.
- A lead (a hypothesis, not a confirmed finding) is NOT an eval case — it is promoted to a confirmed, fix-bearing finding or discarded before entering the set (FR-009). So there is no fix-less "lead case" to exclude; if a manifest for one exists without a fix, it is rejected by FR-008 like any other fix-less case.
- N = 1 → allowed, but the resulting interval is wide by construction and must not read as decisive.
- Zero cases reach a given stage → the funnel shows zero there and below; no division-by-zero, no crash.
- A harness run errors or times out for a case → recorded as its own attrition category (not silently counted as a failure of proving, and not as a success).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run the existing PoC-workability harness over a fixed case set, N times per case, N being a caller-supplied parameter.
- **FR-002**: The system MUST report a PRIMARY metric — the fraction of cases reaching a verified proof — as a credible interval derived from the observed successes over N, never as a single point estimate.
- **FR-003**: The reported interval MUST widen as N shrinks, so an underpowered run reads as "wide, not yet decisive" rather than a confident number.
- **FR-004**: The system MUST support comparing two result sets and MUST report "not yet distinguishable" when their intervals overlap and a decided direction only when they separate.
- **FR-005**: The system MUST report a DIAGNOSTIC attrition funnel over the pipeline stages (extraction → draft → compiled → real-pass → verified), with per-stage counts and a NAMED list of the cases that did not advance past each stage.
- **FR-006**: Funnel stage counts MUST be monotonically non-increasing down the stages.
- **FR-007**: A case MUST count as verified ONLY when the harness itself reports a verified proof; the score MUST NOT be inferred, approximated, or produced by any model judging the outcome.
- **FR-008**: A proof-eval case MUST consist of a target reference, a report reference, a finding identifier, and an operator fix (the ground-truth falsification patch); loading a case without a fix (or whose fix file is absent) MUST fail loudly. This is UNCONDITIONAL — every case in the set is a confirmed, fix-bearing finding.
- **FR-009**: The eval case set MUST contain only confirmed findings. A lead (a hypothesis) is NOT an eval case: it must first be either PROMOTED to a confirmed finding — at which point the operator authors its fix and it enters the set as an ordinary fix-bearing case — or DISCARDED. There is no permanent "lead case" limbo in the eval, so the verified-fraction denominator is exactly the loaded (all fix-bearing) cases; no separate lead-exclusion rule is needed.
- **FR-010**: Each result set MUST record its full run configuration (case set, model, scaffold/example, settings, N, harness version).
- **FR-011**: Comparing two result sets that differ in anything other than the harness version MUST be flagged; a delta across incomparable configurations MUST NOT be presented as trustworthy.
- **FR-012**: The dataset root and every case path MUST be validated as external to the agent's project area; no dataset, target, report, or fix content may be committed with the agent.
- **FR-013**: The scoring path (interval computation, funnel, comparison, reporting) MUST run offline with no model and no network; only the harness runs themselves incur cost.
- **FR-014**: The output MUST state N and the resulting interval width, and MUST state plainly that the case set is a contaminated DEV set (the harness was tuned on it) measuring regression/progress within the set — NOT absolute capability — so a reader cannot mistake a dev number for a capability number.
- **FR-015**: Results MUST be emitted both human-readably and machine-readably, written outside the agent's project area.
- **FR-016**: Reproducibility: given the same recorded harness outcomes, the interval, funnel, and comparison MUST be computed deterministically and identically across runs.
- **FR-017**: The behavior MUST be validated by offline, deterministic tests over SYNTHETIC fixtures (invented case manifests and fake harness outcomes, never real target material): the external-root guard; the unconditional missing-fix loud load error; the stage-mapping of a raw harness EVENT stream to the furthest stage reached (including that a case counts as "extracted" only when its finding identifier appears among the extracted identifiers, since extraction emits all of them); funnel arithmetic and monotonicity on scripted outcomes; interval determinism from a fixed (successes, N) and widening as N shrinks; overlapping-vs-separated interval comparison; presence of the run-configuration record and detection of a config mismatch; and confirmation that the scoring path invokes no model and no network (harness runs stubbed).

### Key Entities

- **Proof-eval case**: one unit — a target reference, a report reference, a finding identifier, and an operator fix (the falsification ground truth). Lives outside the agent's project area.
- **Run configuration**: the pinned experimental conditions of a result set — case set, model, scaffold/example, settings, N, harness version — recorded so incomparable comparisons are caught.
- **Case outcome**: the harness's per-run verdict for a case (verified / unchecked / bogus / compiled / earlier-stage attrition), the raw material of both metrics.
- **Verified-fraction interval**: the primary metric — a credible interval over the verified rate, the thing compared across versions.
- **Attrition funnel**: the diagnostic metric — per-stage survivor counts plus the named non-advancing cases, answering "what to fix next".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can obtain, in a single run, a verified-fraction interval and a per-stage attrition funnel with named casualties for a case set.
- **SC-002**: Re-computing metrics from the same recorded outcomes yields identical intervals, funnels, and comparisons 100% of the time.
- **SC-003**: In 100% of comparisons where the two intervals overlap, the tool reports "not distinguishable"; in 100% where they separate, it reports the decided direction.
- **SC-004**: In 100% of comparisons where configurations differ beyond the harness version, the mismatch is flagged and no delta is trusted.
- **SC-005**: The verified count equals exactly the number of harness-reported verified outcomes in 100% of scored sets — never more.
- **SC-006**: 100% of cases missing a fix produce a loud load error; 0% are silently skipped or counted.
- **SC-007**: No dataset content is committed with the agent, and the scoring path runs fully offline with no model or network.
- **SC-008**: Every produced report states N, the interval width, and the dev-set/contamination caveat.

## Assumptions

- The harness already emits the distinct outcomes this instrument reads (`passed_verified`, `passed_unchecked`, `unverified_pass`, `compiled`, and earlier-stage attrition), delivered by spec 025; this feature consumes them and does not change them.
- The first case set is the 5 strata-bb findings, each with an operator fix already authored and validated (applies cleanly and the target builds with it), living outside the repo.
- A credible interval over a small number of runs is the right honesty tool; the exact interval method is a planning detail, but the property (widens with smaller N, supports an overlap test) is fixed here.
- "Same harness version" is identifiable (e.g. a commit or version marker); pinning everything else is an operator responsibility the tool records and checks, not one it can fully enforce.
- Cost (~a few minutes of model+container+fork per case-run) is inherent; the instrument's job is to make N and the resulting uncertainty explicit, not to reduce the cost.

## Out of Scope

- The discovery axis — the discovery benchmark already owns "did we find the bug".
- Building held-out case sets or acquiring new targets — separate work, correctly blocked on target acquisition; without it, absolute-capability claims are not supported and the tool must say so.
- Authoring operator fixes — already done for the first case set, and a per-target operator task in general.
- Changing the harness or the outcome vocabulary — spec 025 owns `passed_verified`/`passed_unchecked`; this only reads them.
- Any model in the scoring path — disqualified for the same reason model-as-judge was rejected for the discovery benchmark.
- Auto-tuning or optimizing the harness against this eval — that would be optimizing toward the number; the instrument exists to measure honestly, not to be a training signal.

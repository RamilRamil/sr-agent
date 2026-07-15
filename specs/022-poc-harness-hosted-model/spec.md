# Feature Specification: Run the Report→PoC Batch on a Hosted Model

**Feature Branch**: `022-poc-harness-hosted-model`

**Created**: 2026-07-15

**Status**: Draft

**Input**: User description: "Make the report→PoC batch harness able to run on a capable hosted model (GLM via OpenRouter, and Gemini), not just the local model."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate the set of PoCs for a report using a capable hosted model (Priority: P1)

An operator has an external audit report and its target project. They run the batch PoC generator and choose a capable hosted model (GLM, or Gemini). The generator reads the whole report, takes every finding (no prefiltering), and drafts a proof-of-concept per finding through the existing grounding→draft→compile-fix→gate loop — now driven by the hosted model. The result is a set of PoCs the hosted model could actually produce, where the local model could not.

**Why this priority**: This is the whole point — the existing PoC machinery only ever ran on the local model, which provably could not produce a working PoC for a hard finding; wiring in a capable hosted model is what makes "generate the PoCs for this report" actually yield working PoCs.

**Independent Test**: Point the generator at a report + target and select a hosted model; it processes the whole report's findings and drafts a PoC per finding through the same pipeline, using the hosted model instead of the local one — verifiable end-to-end on a live run, and structurally in offline tests with a simulated hosted model.

**Acceptance Scenarios**:

1. **Given** a report + target and a selected hosted model with its key configured, **When** the operator runs the batch, **Then** every finding is processed (no prefiltering) and a PoC is drafted per finding via the existing pipeline, driven by the hosted model.
2. **Given** the operator selects the local model (default), **When** the batch runs, **Then** behavior is exactly as today (no regression).
3. **Given** the batch runs on a hosted model, **When** a PoC compiles and its checks pass, **Then** that is still treated as a mechanical reproduction only — never a safety verdict (the existing structural gate and the vacuous-pass guard remain in force).

---

### User Story 2 - Safe, explicit, optional hosted selection (Priority: P1)

Choosing a hosted model is an explicit opt-in; the local model stays the default. The hosted key comes from the environment (never typed on a command line). If a hosted model is selected without a key — or, for one provider, without its optional software installed — the run stops immediately with a clear message rather than a confusing failure mid-batch. A hosted model is used only through the text-generation path that both hosted models support.

**Why this priority**: The provider selection carries the security-sensitive key handling and the "never required, always opt-in" guarantee; it must be correct from the start.

**Independent Test**: Select a hosted model with no key → the run stops at startup with a clear "no key configured" message. Select the provider whose software isn't installed → a clear "install it" message. Neither happens silently mid-run.

**Acceptance Scenarios**:

1. **Given** the default (no provider chosen), **When** the batch runs, **Then** it uses the local model exactly as before — no hosted dependency.
2. **Given** a hosted model is selected but no key is configured, **When** the batch starts, **Then** it stops with a clear "no API key configured" message before doing any work.
3. **Given** a hosted model is selected whose optional software component is missing, **When** the batch starts, **Then** it stops with a clear "install it" message.
4. **Given** a hosted model and an explicit request for the tool-calling protocol (which hosted models don't support), **When** the batch starts, **Then** it stops with a clear message rather than silently downgrading.
5. **Given** any configuration, **When** the key is used, **Then** it is never echoed to a log, a result, or a command line.

---

### Edge Cases

- Hosted model selected, no key → clear startup stop (not a mid-batch failure).
- Gemini selected without its optional software → clear "install it" startup stop.
- Hosted model + explicit tool-calling protocol request → clear startup stop (hosted models are text-generation only here).
- A single finding's PoC fails to compile → handled exactly as today (the pipeline's per-finding fix/attempt loop is unchanged).
- The report, target, and generated PoCs → always stay outside the agent's own repository (unchanged).
- Local model selected → zero change in behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The batch PoC generator MUST let the operator select the model provider: the local model (default) or a capable hosted model (two hosted options).
- **FR-002**: The default MUST remain the local model with today's exact behavior; hosted selection MUST be an explicit opt-in.
- **FR-003**: A hosted model's key MUST be read from the environment and MUST NEVER appear on a command line, in a log, or in any result.
- **FR-004**: With a hosted model selected, the generator MUST use only the text-generation path both hosted models support (no tool-calling), and MUST reject an explicit request for the tool-calling protocol with a clear startup message.
- **FR-005**: A hosted model selected with no key configured MUST stop the run at startup with a clear "no key configured" message, before any findings are processed.
- **FR-006**: For the hosted provider that needs an optional software component, its absence MUST stop the run at startup with a clear "install it" message.
- **FR-007**: The whole existing pipeline MUST be reused unchanged — whole-report extraction (no prefiltering), grounding, drafting, compile-error-driven fixing, the compile/structural gate, the vacuous-pass guard, and the optional fork-execution — only the model driving it changes.
- **FR-008**: A compiling PoC (and a passing check) MUST continue to mean a mechanical reproduction only, never a safety verdict; the structural gate and vacuous-pass guard MUST remain in force.
- **FR-009**: The report, target project, and generated PoCs MUST stay outside the agent's own repository (unchanged).
- **FR-010**: Selecting a hosted model MUST NOT be required for the generator to work and MUST add no mandatory new software; the local path MUST keep working with no hosted component present.
- **FR-011**: The behavior MUST be validated by offline, deterministic tests using a simulated hosted model (no real hosted call, no network, no container): provider selection builds the corresponding client, a hosted provider forces the supported protocol and rejects the unsupported one, the startup readiness stop fires with no key, and a simulated generation drives the existing draft path. The full offline suite passes.
- **FR-012**: Documentation MUST record how to run the batch on each hosted model (env key, provider selection), that this is the command-line/harness path (a frontend trigger is later), and that the local default is unchanged.

### Key Entities *(include if feature involves data)*

- **Model Provider Selection**: the operator's choice of which model drives the batch — local (default) or one of two hosted models; an explicit opt-in.
- **Hosted Credential**: a write-only secret from the environment used to reach a hosted model; represented only as present/absent, never surfaced.
- **PoC Batch Run**: a run over the whole report's findings, each processed by the existing pipeline, driven by the selected model.
- **PoC Result**: a per-finding proof-of-concept plus its mechanical status (compiled / gate / optional fork execution) — a reproduction signal, never a safety verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can run the report→PoC batch on a capable hosted model (GLM or Gemini) over the whole report's findings, with the model selected by a single explicit option and the key taken from the environment.
- **SC-002**: The local-model path is unchanged — 100% of existing batch behavior and tests pass with no hosted component present (zero regressions).
- **SC-003**: A hosted selection with no key, missing optional software, or an unsupported-protocol request stops at startup with a clear message in 100% of those cases — never a silent downgrade or a mid-batch failure.
- **SC-004**: In 100% of configurations the hosted key never appears in a log, a result, or a command line.
- **SC-005**: The full offline test suite passes with a simulated hosted model and no network/container.

## Assumptions

- Each session/run uses one selected provider; comparing GLM vs Gemini is done by running twice, not concurrently.
- The hosted models are reached over their standard text-generation interface; the harness uses the marker-style protocol that needs only text generation (no provider tool-calling).
- The heavy real end-to-end (a live hosted model plus the sandboxed compiler/fork over a real report) is a live operator run, not part of the automated offline suite; offline tests cover selection, safety stops, and the draft path with a simulated model.
- "Capable hosted model" means a frontier-tier hosted model; the default hosted models are GLM (via the hosted gateway) and a Gemini flash-tier model, each overridable.
- The existing pipeline's correctness gates (structural gate, vacuous-pass guard, optional fork execution) are the sole arbiters of a PoC's quality; this feature changes only which model drafts.

## Out of Scope

- Triggering the batch from the operator frontend or any background-job UI (a separate, later feature).
- The interactive single-PoC action in the chat.
- Any change to the drafting/fixing/verification/grounding logic itself.
- Adding tool-calling to hosted models (text-generation/marker path only).
- Prefiltering findings (all findings are always processed).
- Changing what a passing PoC means (still a mechanical reproduction, gated structurally).

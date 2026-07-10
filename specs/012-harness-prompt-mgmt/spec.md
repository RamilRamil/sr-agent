# Feature Specification: Harness Prompt Management

**Feature Branch**: `012-harness-prompt-mgmt`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "Route the PoC-workability harness's prompts through Langfuse Prompt Management, the same mechanism the kernel already uses. The kernel/pack prompts are versioned + fetched via `Tracer.get_prompt(name, fallback)` with graceful fallback (spec 001 T079); the PoC-harness prompts (`EXTRACT_PROMPT`, `DRAFT_PROMPT`, `FIX_PROMPT`, `EXPLOIT_QUALITY_CHECKLIST`, `_LOOKUP_MARKER_SUFFIX`, `SYNTH_SCAFFOLD_PROMPT`) are raw inline constants — not versioned, not in Langfuse — so this session's heavy prompt iteration happened blind (no prompt-version→trace linkage even though `Tracer` is already wired into draft/fix). Scope: (1) route each harness prompt through `tracer.get_prompt(name, fallback=<constant>)` (the constant stays the byte-exact fallback — behavior identical when tracing off); (2) record the prompt version in the generation trace via an additive `Tracer.get_prompt_versioned(name, fallback) -> (text, version|None)`; (3) a best-effort seeding step pushing the harness prompts to Langfuse (production, v1); (4) validate offline via the spec-009 fake harness. Out of scope: changing kernel prompts / the existing `get_prompt` contract; making Langfuse a hard dependency; A/B tooling; a general prompt-registry abstraction. Deferred harness-review candidate (roadmap item 4); does not change what any prompt SAYS."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **operator/maintainer** of the PoC-workability harness —
internal observability/reliability work. It brings the harness prompts under the same
versioning discipline the kernel already applies to its own prompts.

### User Story 1 - Harness prompts are versioned, with identical behavior when tracing is off (Priority: P1) 🎯 MVP

As the operator, I want each harness prompt fetched through the same versioned
prompt-management path the kernel uses — so I can change a prompt centrally without a
code deploy — while guaranteeing that when tracing is disabled or unreachable, the
harness uses the exact same prompt text it does today (the hardcoded constant is the
fallback), so nothing about a normal run changes.

**Why this priority**: The whole value is versioned prompts; the non-negotiable
constraint is that it costs a normal (tracing-off) run nothing — the fallback IS the
current constant, so behavior must be byte-identical.

**Independent Test**: With a disabled/fake tracer, confirm every harness prompt
resolves to its byte-exact fallback constant and a draft/fix produces the same prompt
text as before — offline, no Langfuse.

**Acceptance Scenarios**:

1. **Given** tracing is disabled (no Langfuse), **When** the harness builds any prompt
   (extract/draft/fix/checklist/lookup-marker/synth), **Then** it uses the hardcoded
   fallback constant unchanged — the run is identical to today.
2. **Given** tracing is enabled and Langfuse returns a versioned prompt for a name,
   **When** the harness builds that prompt, **Then** it uses the fetched version.
3. **Given** Langfuse is enabled but a fetch fails for any reason, **When** the harness
   builds that prompt, **Then** it falls back to the constant (never errors the run).

---

### User Story 2 - A run records which prompt version produced it (Priority: P1)

As the operator, I want each draft/fix generation's trace to record the prompt name and
version it used — so when I compare runs (a checklist tweak, a new synth prompt) I can
tell which prompt version produced which result, instead of iterating blind.

**Why this priority**: This is the observability payoff — the reason to version at all.
Without version→trace linkage, versioning is bookkeeping with no feedback loop.

**Independent Test**: With a fake tracer returning a versioned prompt, confirm the
draft/fix generation's recorded metadata includes the prompt name and that version —
offline.

**Acceptance Scenarios**:

1. **Given** a fetched prompt has a version, **When** the harness runs a draft/fix
   generation with it, **Then** the generation's trace metadata records the prompt
   name and version.
2. **Given** the prompt came from the fallback (no version), **When** the generation is
   recorded, **Then** the metadata records the name with a null/absent version — never
   a fabricated one.

---

### User Story 3 - The harness prompts exist in Langfuse to version against (Priority: P2)

As the operator, I want the harness prompts seeded into Langfuse Prompt Management under
stable names (production, v1) — programmatically, no UI step — so there is a versioned
baseline to edit and roll forward, exactly as the kernel prompts were seeded (T079).

**Why this priority**: Needed to actually use versioning in practice, but lower than the
fetch/record wiring (which works from day one via fallback even before seeding).

**Independent Test**: Run the seeding step against a disabled Langfuse and confirm it is
a clean no-op (does not error); its create-calls are exercised against a fake Langfuse
in a test.

**Acceptance Scenarios**:

1. **Given** Langfuse is configured, **When** the seeding step runs, **Then** each
   harness prompt is created under its stable name with a `production` label.
2. **Given** Langfuse is disabled, **When** the seeding step runs, **Then** it is a
   silent no-op — never a hard error.

### Edge Cases

- What happens when a Langfuse-fetched prompt is missing a `{placeholder}` the harness
  formats into it (a bad edited version)? → The harness's `.format(...)` would raise;
  this is treated the same as any prompt-fetch problem — the operator's edited prompt
  must keep the placeholders, and the safe path is that a formatting failure is caught
  and the fallback constant used, never crashing the run. (An edited prompt that drops a
  placeholder is operator error surfaced safely, not a harness crash.)
- What happens when only SOME prompts are in Langfuse and others aren't? → Each prompt
  resolves independently — a fetched one is used, an absent one falls back — there is no
  all-or-nothing coupling.
- What happens to the existing kernel callers of `get_prompt`? → Untouched — the new
  versioned accessor is additive; `get_prompt` keeps its exact current contract.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each harness prompt (`EXTRACT_PROMPT`, `DRAFT_PROMPT`, `FIX_PROMPT`,
  `EXPLOIT_QUALITY_CHECKLIST`, `_LOOKUP_MARKER_SUFFIX`, `SYNTH_SCAFFOLD_PROMPT`) MUST be
  fetched through the tracer's prompt-management path, keyed by a stable name, with the
  current inline constant passed as the fallback.
- **FR-002**: When tracing is disabled or a fetch fails, the harness MUST use the
  byte-exact fallback constant — a normal (tracing-off) run's prompts MUST be identical
  to today's (no behavior change).
- **FR-003**: The harness MUST record, in each draft/fix generation's trace metadata,
  the prompt name(s) used and their version(s) — with a null/absent version when the
  fallback was used (never a fabricated version).
- **FR-004**: A new versioned accessor MUST be additive — the existing `get_prompt`
  contract and its kernel callers MUST be unchanged.
- **FR-005**: A best-effort seeding step MUST push the harness prompts to Langfuse
  Prompt Management under their stable names (production, v1), programmatically, and MUST
  be a silent no-op when Langfuse is disabled.
- **FR-006**: Langfuse MUST NOT become a hard dependency — the harness runs unchanged
  without it (constitution V), degrading to the fallback constants.
- **FR-007**: A Langfuse-fetched prompt that fails to `.format(...)` (e.g. an edited
  version dropped a required placeholder) MUST fall back to the constant, never crash the
  run.
- **FR-008**: The whole behavior (fallback-identical, versioned-fetch-used,
  version-recorded, seeding no-op) MUST be verifiable offline through the spec-009
  fake-model harness — no Langfuse, Ollama, Docker, or network.

### Key Entities

- **Harness prompt**: a named, versionable prompt template used by the harness
  (extract/draft/fix/checklist/lookup-marker/synth), with a stable name and a byte-exact
  fallback constant.
- **Prompt fetch result**: the resolved `(text, version)` for a name — `version` is
  null when the fallback constant was used.
- **Generation prompt provenance**: the prompt name(s)+version(s) recorded in a
  draft/fix generation's trace metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With tracing disabled, 100% of harness prompts resolve to their byte-exact
  fallback constant and a draft/fix's assembled prompt text is identical to the
  pre-feature behavior (verified offline).
- **SC-002**: With a fetched versioned prompt, the harness uses it and the draft/fix
  generation's trace metadata records that prompt's name and version (verified offline
  with a fake tracer).
- **SC-003**: A fallback-sourced prompt records its name with a null/absent version —
  never a fabricated one.
- **SC-004**: The existing `get_prompt` and its kernel callers are unchanged (the new
  accessor is additive) — the kernel test suite still passes.
- **SC-005**: The seeding step is a silent no-op with Langfuse disabled and issues a
  create per harness prompt with Langfuse enabled (verified against a fake Langfuse).
- **SC-006**: The full offline suite passes with the new tests; no Langfuse/Ollama/
  Docker/network; no bug-bounty target code in tests.

## Assumptions

- The "operator" runs `scripts/poc_queue_runner.py`; internal observability work.
- The harness already constructs a `Tracer` and threads it into draft/fix (spec 009),
  and the kernel already has `Tracer.get_prompt(name, fallback)` + Langfuse Prompt
  Management (spec 001 T079) — this feature reuses both; the versioned accessor is a
  small additive extension of `Tracer`.
- Langfuse is self-hosted (LANGFUSE_HOST localhost) and optional; the hardcoded
  constants remain the trust anchor and the offline default (constitution V).
- This feature changes only WHERE a prompt is fetched from and that its version is
  recorded — it does not change what any prompt SAYS (the constants are the v1 seed and
  the fallback).
- This is roadmap item 4, separated at the operator's request; item 5 (datetime
  deprecations + more architecture invariants) remains deferred.
- No secure-kernel behavior change — the only kernel-adjacent change is an additive
  accessor on the shared `Tracer`; the standalone harness holds the rest.

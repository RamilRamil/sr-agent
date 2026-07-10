# Research: Harness Prompt Management

## R1 — Additive `get_prompt_versioned`, leave `get_prompt` untouched

**Decision**: Add `Tracer.get_prompt_versioned(name, fallback) -> tuple[str, int | None]`
to `sr_agent/eval/tracer.py`: when tracing is off or a fetch fails, return
`(fallback, None)`; otherwise return `(prompt.prompt, getattr(prompt, "version", None))`
from Langfuse's `get_prompt(name, fallback=...)`. Leave the existing `get_prompt`
exactly as-is (its two kernel callers keep the text-only contract, FR-004).

**Rationale**: The kernel's `get_prompt` deliberately returns only the text — its
callers don't record versions. The harness needs the version too, so a parallel
accessor is the minimal additive change; it neither alters `get_prompt`'s signature nor
its callers, so the kernel test surface is untouched (SC-004). `version` is `None` on
the fallback path so provenance never fabricates one (FR-003/SC-003).

**Alternatives considered**:
- *Change `get_prompt` to return `(text, version)`* — rejected: breaks the two kernel
  callers and the T079 contract; the spec's out-of-scope forbids it.
- *Have the harness call Langfuse directly* — rejected: re-implements the graceful-
  fallback + disabled-client logic `Tracer` already owns.

## R2 — One `_resolve_prompt` helper with a format-failure fallback

**Decision**: A harness helper
`_resolve_prompt(tracer, name, fallback, **fmt) -> tuple[str, dict]` that (a) fetches
`(template, version)` via `get_prompt_versioned`, (b) `.format(**fmt)`s it, and (c) on a
`KeyError`/`IndexError` (an edited Langfuse version dropped a required placeholder,
FR-007) retries `.format` on the `fallback` constant and records `version=None`. Returns
the formatted text and a provenance dict `{"name": name, "version": version}`. Prompts
that are inserted verbatim (the exploit checklist, the lookup-marker suffix) call it with
no `**fmt` (a no-op format).

**Rationale**: Centralizing fetch + format-fallback + provenance in one helper means the
FR-007 safety and the FR-003 provenance are guaranteed uniformly at every call site,
not re-implemented per prompt. `.format` is where a bad edited prompt fails, so that's
where the fallback belongs.

**Alternatives considered**:
- *Fetch and format separately at each site* — rejected: duplicates the format-fallback
  and provenance logic six times, easy to get subtly inconsistent.
- *Validate placeholders up front instead of catching format errors* — rejected:
  brittle (must know each prompt's expected keys); catching the actual format error is
  simpler and exact.

## R3 — Thread `tracer` into the two prompt-consuming functions that lack it

**Decision**: `draft`/`fix`/`_traced_round_trip` already receive `tracer` — route
`DRAFT_PROMPT`/`FIX_PROMPT`/`EXPLOIT_QUALITY_CHECKLIST`/`_LOOKUP_MARKER_SUFFIX` through
`_resolve_prompt` there. `extract_tasks` and `synthesize_scaffold` don't have `tracer`
today — add it as a parameter (both are called from `main()`/`_process_finding`, which
hold the tracer), and route `EXTRACT_PROMPT`/`SYNTH_SCAFFOLD_PROMPT` through it.
Provenance from draft/fix (which may combine up to three prompts: draft/fix + checklist
+ marker-suffix) is collected into a list and passed into the existing
`tracer.generation(...)` metadata as `prompt_provenance`.

**Rationale**: The prompts are assembled inside these functions, so resolution must
happen where the tracer is reachable; two of the five consuming functions simply need
the tracer threaded in (a mechanical signature addition, both callers already hold it).
Recording provenance in the generation metadata reuses the metadata channel
`tracer.generation` already accepts (spec 009), so no new tracing surface.

**Alternatives considered**:
- *Resolve all prompts once in `main()` and pass templates down* — rejected: draft/fix
  format per-finding with per-finding values; passing pre-resolved templates down still
  needs the provenance threaded back up — more plumbing than threading the tracer.

## R4 — Best-effort seeding, guarded, no-op when disabled

**Decision**: A `seed_prompts(tracer)` (or a small helper using the tracer's Langfuse
client) that, when tracing is enabled, issues `create_prompt(name, prompt=<constant>,
labels=["production"])` for each of the six harness prompts under their stable names; a
no-op when the client is absent. Invoked once at run start behind the existing
`tracer.enabled` guard (and swallowing any error — seeding is best-effort, FR-005/FR-006).

**Rationale**: Mirrors the kernel's T079 programmatic seeding — a versioned baseline to
edit/roll-forward, with no UI step — and, like everything else here, degrades to a clean
no-op without Langfuse. Running it at start (guarded) keeps the versions present for the
run's own fetches.

**Alternatives considered**:
- *A separate one-off script instead of an in-run step* — acceptable, but an in-run
  guarded no-op is simpler for the operator and matches T079's in-process approach; kept
  idempotent by Langfuse's create semantics (a re-create is a new version / no-op by
  label as the SDK handles it).

## R5 — Offline test seams

**Decision**: (a) `get_prompt_versioned` unit-tested with a disabled tracer (→
`(fallback, None)`) and a fake Langfuse client returning a versioned prompt (→
`(text, version)`) and a raising client (→ fallback). (b) `_resolve_prompt` unit-tested:
disabled → constant + `version None`; versioned → fetched text + version; a fetched
template missing a placeholder → constant (FR-007). (c) Loop-level: with a disabled
tracer, assert the assembled draft prompt equals the pre-feature constant-based prompt
(SC-001 identical-behavior); with a fake versioned tracer, assert the draft/fix
generation metadata records the prompt name+version (SC-002). (d) `seed_prompts` tested
against a fake Langfuse client (create called per prompt) and a disabled tracer (no-op).
All offline (FR-008).

**Rationale**: Splits the additive `Tracer` method, the harness helper, the loop
identical-behavior guarantee, and the seeding no-op into focused offline tests — the
same unit-vs-integration discipline specs 009/010/011 use, reusing their fake harness.

# Contract: `get_prompt_versioned` + `_resolve_prompt` + provenance

## `Tracer.get_prompt_versioned(name: str, fallback: str) -> tuple[str, int | None]`

Additive to `sr_agent/eval/tracer.py` (get_prompt unchanged, FR-004).

```
if not self._client:            # tracing disabled
    return fallback, None
try:
    p = self._client.get_prompt(name, fallback=fallback)
    return p.prompt, getattr(p, "version", None)
except Exception:
    return fallback, None        # best-effort — never raise (FR-006)
```

**Invariant**: returns `(fallback, None)` on every disabled/error path — `version` is
never fabricated (FR-003).

## `_resolve_prompt(tracer, name: str, fallback: str, **fmt) -> tuple[str, dict]`

Harness helper (`scripts/poc_queue_runner.py`).

```
template, version = tracer.get_prompt_versioned(name, fallback)
try:
    text = template.format(**fmt) if fmt else template
except (KeyError, IndexError):   # edited version dropped a required placeholder (FR-007)
    text = fallback.format(**fmt) if fmt else fallback
    version = None
return text, {"name": name, "version": version}
```

**Invariants**:
- Tracing off ⇒ `template is fallback` ⇒ `text` is byte-exact today's prompt (FR-002/SC-001).
- A format failure ⇒ the constant is used, `version=None`, run never crashes (FR-007).
- Always returns a provenance dict for the generation metadata (FR-003).

## Provenance in the generation

`draft`/`fix` resolve their prompts via `_resolve_prompt` and collect the provenance
dicts (draft: `poc-draft` + `poc-exploit-checklist`; `_traced_round_trip` adds
`poc-lookup-marker` in marker mode). The list is passed into the existing
`tracer.generation(..., metadata={..., "prompt_provenance": [...]})` call (spec 009).

**Invariant**: every prompt that composed the generation appears once; a
fallback-sourced entry has `version: None` (SC-002/SC-003).

## Threaded tracer (signature additions)

- `extract_tasks(client, report_path, tracer=NOOP_TRACER)` — resolves `poc-extract`.
- `synthesize_scaffold(project, task, missing_types, existing_scaffold, symbol_index,
  client, sandbox, log, *, image=None, fork_rpc=None, tracer=NOOP_TRACER)` — resolves
  `poc-synth-scaffold`.

Both default to `NOOP_TRACER` (so existing callers/tests without a tracer are unaffected;
`main()`/`_process_finding` pass the real tracer).

## `seed_prompts(tracer) -> None`

Best-effort (`scripts/poc_queue_runner.py`), invoked once at run start behind
`tracer.enabled`:

```
if not tracer.enabled: return
for name, constant in _HARNESS_PROMPTS.items():
    try: tracer._client.create_prompt(name=name, prompt=constant, labels=["production"])
    except Exception: pass          # best-effort (FR-005/FR-006)
```

**Invariant**: a silent no-op when Langfuse is disabled; never a hard error.

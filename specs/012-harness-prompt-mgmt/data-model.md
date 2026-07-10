# Data Model: Harness Prompt Management

No persisted data in the harness — prompt versions live in Langfuse (self-hosted,
optional). The entities are the named prompt, the fetch result, and the provenance
recorded on a generation.

## Harness prompt

A named, versionable prompt template with a byte-exact fallback constant.

| Name (stable) | Fallback constant | Consumed in |
|---|---|---|
| `poc-extract` | `EXTRACT_PROMPT` | `extract_tasks` |
| `poc-draft` | `DRAFT_PROMPT` | `draft` |
| `poc-fix` | `FIX_PROMPT` | `fix` |
| `poc-exploit-checklist` | `EXPLOIT_QUALITY_CHECKLIST` | `draft`/`fix` (inserted into the prompt) |
| `poc-lookup-marker` | `_LOOKUP_MARKER_SUFFIX` | `_traced_round_trip` (marker mode) |
| `poc-synth-scaffold` | `SYNTH_SCAFFOLD_PROMPT` | `synthesize_scaffold` |

**Validation rule**: the fallback constant is the trust anchor and the offline default
(FR-002/FR-006) — with tracing off, every prompt resolves to its constant, byte-exact.

## Prompt fetch result

The resolved `(text, version)` for a name.

| Field | Type | Notes |
|---|---|---|
| `text` | str | the fetched prompt, or the fallback constant on disabled/failed fetch |
| `version` | int \| None | the Langfuse version, or `None` when the fallback was used (never fabricated, FR-003) |

**Validation rule**: `get_prompt_versioned` returns `(fallback, None)` on any
disabled/error path; a formatted prompt whose fetched template dropped a required
placeholder falls back to the constant with `version=None` (FR-007).

## Generation prompt provenance

The prompt name(s)+version(s) recorded in a draft/fix generation's trace metadata.

| Field | Type | Notes |
|---|---|---|
| `prompt_provenance` | list[{name, version}] | one entry per prompt that composed this generation (e.g. draft may list `poc-draft`, `poc-exploit-checklist`, and `poc-lookup-marker`) |

**Validation rule**: recorded in the existing `tracer.generation(..., metadata=…)`
channel; a fallback-sourced entry carries `version: None` (SC-003).

## Relationships

```
Tracer.get_prompt_versioned(name, fallback)          # additive; get_prompt unchanged (FR-004)
   → (text, version|None)

_resolve_prompt(tracer, name, fallback, **fmt)       # harness helper (R2)
   → text = get_prompt_versioned(...).text .format(**fmt)   (format-fails → fallback, FR-007)
   → provenance = {"name": name, "version": version}

draft/fix   → _resolve_prompt(poc-draft/…) + _resolve_prompt(poc-exploit-checklist)
_traced_round_trip → + _resolve_prompt(poc-lookup-marker) (marker mode)
              → collect provenance list → tracer.generation(..., metadata={"prompt_provenance": [...]})
extract_tasks(…, tracer)      → _resolve_prompt(poc-extract, EXTRACT_PROMPT, report=…)
synthesize_scaffold(…, tracer)→ _resolve_prompt(poc-synth-scaffold, SYNTH_SCAFFOLD_PROMPT, …)

seed_prompts(tracer)          # best-effort; per-prompt create_prompt(production, v1);
                              # no-op when Langfuse disabled (FR-005/FR-006)
```

No harness-side persistence; provenance is a trace field, versions live in Langfuse.

# Data Model: Stage 1 Scaffold Synthesis

No persisted data beyond a synthesized base file written under the target project's
UNTRACKED audit area. The entities are the missing-type input, the synthesized base,
and the synthesis verdict.

## Missing type set

The contract type name(s) a finding needs that the auto-discovered scaffold does not
declare/deploy — the trigger for synthesis.

| Field | Type | Notes |
|---|---|---|
| `missing_types` | list[str] | from `scaffold_missing_types(scaffold, target_stems, symbol_index)` (spec 009); non-empty ⇒ attempt synthesis |

**Validation rule**: synthesis fires ONLY when this is non-empty (FR-001) — a
sufficient scaffold never triggers it (SC-003).

## Synthesized deploy-base

A generated Foundry abstract contract that inherits the existing base and
declares+deploys the missing contract(s).

| Aspect | Shape |
|---|---|
| produced by | `client.generate(SYNTH_SCAFFOLD_PROMPT…)` grounded in the missing contract source + existing base pattern (R2) |
| written to | `audit/poc/_synth/<Name>.sol` — UNTRACKED audit area, never git-tracked source (FR-006) |
| required shape | inherits the existing base; declares the missing contract as a state variable; deploys/wires it in a setup helper (FR-003) |
| validated by | a minimal inheriting smoke test compiled via `run_tests` + `_compiled` (R3) |

## Synthesis verdict

| Verdict | Condition | Effect | Event |
|---|---|---|---|
| `synthesized` | model produced a base AND the smoke test COMPILED | the finding's scaffold is swapped to the synthesized base for drafting | `scaffold_synthesized` |
| `failed` | no usable model output / smoke test won't compile / infra error during validation | keep the prior insufficient scaffold; never block | `scaffold_synthesis_failed` (with reason: `no_output` / `no_build` / `infra`) |

**Validation rule**: a base is used ONLY on a positive compile signal (FR-004); every
other path is an honest `failed` fallback (FR-005). Any PASS later produced under a
synthesized base is still gated by spec 010 mutation-verify (FR-008).

## Relationships

```
_process_finding … missing_types = scaffold_missing_types(...)      # spec 009
   └─ if missing_types and synthesis enabled:
        path = synthesize_scaffold(project, task, missing_types, scaffold,
                                    symbol_index, client, sandbox, log, image, fork_rpc):
          code = client.generate(SYNTH_SCAFFOLD_PROMPT grounded in missing source + base)
          if not code → failed(no_output)
          write code → audit/poc/_synth/<Name>.sol           # FR-006 untracked
          write minimal inheriting smoke test → run_tests → _compiled?
             no  → failed(no_build)      (or infra error → failed(infra))
             yes → synthesized(path)
        if path:  scaffold_paths=[path]; scaffold=read_scaffold(project,[path]);
                  guard=_base_has_nonvirtual_setup(scaffold)   # swap, then draft loop
        else:     keep prior scaffold (log scaffold_synthesis_failed)
```

Every entity lives only for the duration of one finding's synthesis attempt; the
synthesized file persists under the untracked audit area for that run.

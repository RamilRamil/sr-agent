# Contract: `synthesize_scaffold` + loop wiring

## `synthesize_scaffold(project, task, missing_types, existing_scaffold, symbol_index, client, sandbox, log, *, image=None, fork_rpc=None) -> Path | None`

Synthesize + compile-validate a deploy-base for a finding's missing contract type(s).

**Preconditions**: called ONLY when `scaffold_missing_types` returned a non-empty
`missing_types` for this finding and synthesis is enabled (FR-001).

**Returns**: the `Path` of the accepted synthesized base file (compiled), or `None` on
any failure (honest fallback).

### Behavior

```
source = read_location_source / SymbolIndex definitions for the missing type(s)
prompt = SYNTH_SCAFFOLD_PROMPT.format(missing=missing_types, source=source,
                                      existing=existing_scaffold, …)
code = _strip_fences(client.generate(prompt, options=…))
if not looks_like_solidity(code):
    log{event:"scaffold_synthesis_failed", finding_id, reason:"no_output"}; return None

synth_path = project / "audit/poc/_synth" / f"{Name}.sol"      # FR-006 untracked area
write code → synth_path
write a minimal inheriting smoke test → <foundry test dir>/_synth_smoke.t.sol:
    contract _SynthSmoke is <Name> { function test_compiles() public {} }
try:
    test = run_tests(project, sandbox, test_path=<smoke rel>, foundry_test_dir=POC_SUBDIR,
                     fork_rpc=fork_rpc, **({"image":image} if image else {}))
except Exception:
    cleanup; log{…reason:"infra"}; return None
finally:
    remove the smoke test file
if not _compiled(test.stdout, test.stderr):
    log{event:"scaffold_synthesis_failed", finding_id, reason:"no_build",
        stderr_tail: …}; remove synth_path; return None
log{event:"scaffold_synthesized", finding_id, path: <rel>, missing_types}
return synth_path
```

### Invariants

- **Never modifies tracked source** — the base + smoke test live under the untracked
  audit area; the smoke test is removed after; a rejected base is removed (FR-006/SC-004).
- **Used only on a positive compile signal** — a base that doesn't build is discarded
  and returns None (FR-004); no-output and infra are likewise `None`+event (FR-005).
- **No new dependency** — uses the harness's existing `client` and sandbox (FR-002).

## Wiring into `_process_finding` (spec 009)

At the existing `missing_types = scaffold_missing_types(...)` branch:

```
missing_types = scaffold_missing_types(scaffold, target_stems, symbol_index)
if missing_types:
    log{event:"scaffold_insufficient", …}         # (existing)
    if not args.no_scaffold_synthesis:
        synth = synthesize_scaffold(args.project, task, missing_types, scaffold,
                                    symbol_index, client, sandbox, log,
                                    image=args.image, fork_rpc=fork_rpc)
        if synth is not None:
            scaffold_paths = [synth]
            scaffold = read_scaffold(args.project, scaffold_paths)
            guard = bool(scaffold) and _base_has_nonvirtual_setup(scaffold)
        # else: keep the prior scaffold (synthesize_scaffold already logged the failure)
```

`example`/`callable_api`/the draft loop are unchanged — they consume whatever `scaffold`
now holds. Any PASS the finding then reaches is still mutation-verified (spec 010,
FR-008). A CLI flag `--no-scaffold-synthesis` disables the whole step (default: on).

# Contract: `mutation_verify` + fix extraction

## `extract_fix_for_finding(report_text, task) -> str | None`

Deterministically pulls the finding's unified-diff fix from the report (R1).

- Parses the report into ordered finding-sections (`[NN] **N. Title**` … `---`).
- Associates `task` with a section by extraction order, guarded by a title-overlap
  sanity check.
- Returns the section's fenced ` ```diff ``` ` block VERBATIM, or `None` when there is
  no diff or no confident section match.

**Invariant**: the returned string is byte-for-byte the report's diff — never
reformatted (so it applies as-authored or is cleanly `unavailable`).

## `mutation_verify(project, task, poc_rel_path, sandbox, log, *, fork_rpc=None, image=None) -> str`

(Calls the module-level `run_tests` directly — not injected as a param — so the same
monkeypatch seam the loop uses drives the patched re-run in tests.)

Runs the post-PASS verification and returns a verdict string.

**Preconditions**: called ONLY from `_process_finding`'s `real_pass` branch (FR-007) —
the PoC has already PASSED on the vulnerable code in this same run.

**Returns** one of: `"verified"`, `"unverified_pass"`, `"unavailable"`.

### Behavior (data-model.md's verdict table)

```
fix = task.get("fix")
if not fix:
    log{event: "mutation_verify_unavailable", finding_id, reason: "no_fix"}
    return "unavailable"

copy = <temp copytree of project, excluding out/ cache_forge/>   # FR-004: real tree untouched
try:
    if not _git_apply(copy, fix):        # git apply, fallback patch -p1 --forward
        log{event: "mutation_verify_unavailable", finding_id, reason: "patch_failed"}
        return "unavailable"
    try:
        test = run_tests(copy, sandbox, test_path=poc_rel_path, foundry_test_dir=POC_SUBDIR,
                         fork_rpc=fork_rpc, **({"image": image} if image else {}))
    except (SandboxUnavailable, Exception):
        log{event: "mutation_verify_unavailable", finding_id, reason: "infra"}   # FR-006
        return "unavailable"
    if not _compiled(test.stdout, test.stderr):
        log{event: "mutation_verify_unavailable", finding_id, reason: "patched_no_build"}
        return "unavailable"
    if test.passed:
        log{event: "mutation_unverified", finding_id}    # still passes on the fix → bad
        return "unverified_pass"
    log{event: "mutation_verified", finding_id}          # fails on the fix → genuine
    return "verified"
finally:
    <delete copy>
```

### Invariants

- **Never mutates the real target tree** — all work on the temp copy (FR-004); the copy
  is deleted in `finally`.
- **Never downgrades on an inability to verify** — no fix / patch fail / no build / infra
  error are all `unavailable`, keeping `passed` (FR-005); only a real test FAILURE on a
  BUILT patched source yields `unverified_pass` (FR-006).
- **Standard patch tooling only** — a diff that won't apply with `git apply`/`patch` is
  `unavailable`, not fuzzily forced (FR-009).
- **Reuses the same sandbox** — no new execution surface or privilege; the patched
  re-run is the existing `run_tests` path against a copy.

## Wiring into `_process_finding` (spec 009)

At the existing `real_pass` branch:

```
outcome = "passed"
verdict = mutation_verify(args.project, task, rel, sandbox, log, fork_rpc=fork_rpc, image=args.image)
if verdict == "unverified_pass":
    outcome = "unverified_pass"
break
```

`verified` and `unavailable` keep `outcome == "passed"`; only `unverified_pass`
downgrades. No other outcome path calls `mutation_verify`.

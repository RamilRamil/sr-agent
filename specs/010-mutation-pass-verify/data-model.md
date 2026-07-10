# Data Model: Mutation-Based PASS Verification

No persisted data — an ephemeral temp copy of the source, deleted after the verify
run. The entities are the fix carried on a finding, the verify run, and its verdict.

## Finding fix

The remediation diff for a finding, carried alongside id/title/location/description.

| Field | Type | Notes |
|---|---|---|
| `fix` | string \| None | the finding's inline unified-diff block, extracted DETERMINISTICALLY from the report section (R1); `None` when the finding has no `**Fix**` diff (e.g. this report's finding #4) |

**Validation rule**: `fix` is preserved byte-for-byte from the report — never
regenerated or reformatted by the model (R1), so it applies as-authored or not at all.

## Mutation-verify run

A post-PASS re-execution of the SAME PoC against a patched ephemeral copy.

| Aspect | Shape |
|---|---|
| trigger | only when `_process_finding` reaches `real_pass` (outcome `passed`) — never otherwise (FR-007) |
| source | a temp `copytree` of the target project, build caches excluded (R2); real tree untouched (FR-004) |
| mutation | `git apply` (fallback `patch -p1`) of `finding.fix` to the copy (R2) |
| execution | the SAME PoC via the existing `run_tests` against the copy (same network-isolated sandbox) |

## Verify verdict

The classification of a mutation-verify run — each with its own log event.

| Verdict | Condition | Effect on outcome | Event |
|---|---|---|---|
| `verified` | patched source builds AND the PoC now FAILS | keep `passed` | `mutation_verified` |
| `unverified_pass` | patched source builds AND the PoC STILL PASSES | downgrade to `unverified_pass` | `mutation_unverified` |
| `unavailable` | no fix / diff won't apply / patched source won't build / infra error on re-run | keep `passed` | `mutation_verify_unavailable` (with reason) |

**Validation rule**: a downgrade (`unverified_pass`) MUST rest on an actual PoC test
FAILURE on a patched source that BUILT (`_compiled` True) — never on a patch/build/infra
problem, which is always `unavailable` (FR-005/FR-006). The feature strengthens a PASS
when it can; it never invents a failure it didn't observe.

## Relationships

```
_process_finding … real_pass → outcome "passed"
   └─ mutation_verify(project, task, poc_rel, sandbox, run_tests, log):
        fix = task["fix"]  (extracted from report, R1)
        if not fix → unavailable(no_fix)
        copy = copytree(project, exclude caches)      # ephemeral, FR-004
        if not git_apply(copy, fix) → unavailable(patch_failed)
        test = run_tests(copy, sandbox, poc_rel, …)   # patched re-run
        if infra error → unavailable(infra)
        if not _compiled(test) → unavailable(patched_no_build)
        if test.passed → unverified_pass              # still passes → downgrade
        else → verified                               # fails on fix → confirmed
   └─ apply verdict to outcome; delete copy
```

Every entity lives only for the duration of one finding's verify run.

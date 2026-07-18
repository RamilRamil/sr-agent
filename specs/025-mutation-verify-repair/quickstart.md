# Quickstart: Reading and Earning a Verification Outcome (spec 025)

## The rule this exists to enforce

> A forge PASS is not a proof. The proof is: **the same test must FAIL once the bug is fixed.**

If it still passes after the fix, it was testing something else. That falsification step is the only
thing separating a proof from a green test — and until spec 025 it had run **zero times in 10 passes
across two live runs**, while every one of them reported `passed`.

## Reading the outcome

| outcome | what it means | trust it? |
|---|---|---|
| `passed_verified` | the proof broke on the fix — it depends on the bug | **yes** |
| `passed_unchecked` | falsification could not run; reason attached | **not yet** — it's a hypothesis |
| `unverified_pass` | falsification ran; the proof SURVIVED the fix | **no** — it proves nothing |
| `compiled` | builds and is structurally real; fork run deferred | n/a |

> `passed_unchecked` ≠ `unverified_pass`. The first means *we couldn't check*; the second means
> *we checked and it failed the check*. The second name is legacy and poor — mind the gap.

Reasons on `passed_unchecked`: `no_fix` · `reconstruction_refused` · `patch_failed` ·
`patched_no_build` · `infra`.

**An inability to verify never downgrades a pass to a failure.** Not knowing is not evidence of a
defect.

## Getting a finding verified

Falsification needs *a* fix — not *the report's* fix. Two sources, operator wins:

### 1. Supply your own patch (works for anything)

```bash
python scripts/poc_queue_runner.py … \
  --fix-patch 7=/path/outside/repo/fixes/7.patch \
  --fix-patch 12=/path/outside/repo/fixes/12.patch
```

**The bar is low.** You do not need the fix that ships — only the bug's behavior gone, so the PoC
breaks. Inverting a condition or hard-failing the vulnerable branch is enough. Minutes, not hours.

```diff
--- a/contracts/Vault.sol
+++ b/contracts/Vault.sol
@@ -41,7 +41,7 @@ contract Vault {
-        if (a <= b) {
+        if (a < b) {
```

Patches live **outside** this repo — they are target material.

### 2. The report's own fix (free, but rare)

Report fix blocks are **illustrations**, not patches: real file headers, but prose hunk markers with no
line numbers.

```diff
--- a/contracts/Vault.sol
+++ b/contracts/Vault.sol
@@ struct TRequest {          ← no line numbers: git apply and patch both reject this
     uint64 unlockAt;
+    uint64 createdAt;
 }
```

`patch_reconstruct.py` turns that into a real patch by finding the anchor in the source and counting
the lines itself. Free — but the available report carries a fix for **3 of 5 findings and 0 of 18
leads**, so this channel caps low. Source 1 is what removes the ceiling.

## Why leads matter most

18 of 23 tasks in a real run are **leads** — hypotheses whose passing proof is their *only* evidence,
and which never carry a report fix. An unverified pass on a lead is the most dangerous thing this
pipeline emits. Only your patch reaches them.

## Refusal is a feature

Reconstruction refuses on: `anchor_not_found` (includes an author's abbreviated `@@ function foo(...)`
— no rule recovers the real signature), `anchor_ambiguous` (>1 match), `context_mismatch` (a line isn't
verbatim in the source), `file_not_found`. Any hunk refusing refuses the whole fix.

**Never fuzzy-match here.** A patch landed in the wrong place produces a *wrong* `verified` — worse
than today's no-op, because you would believe it. Refusal costs one honest label; a wrong verification
costs the mechanism's whole reason to exist. Refused? Write the patch yourself (source 1).

## Adding a fix source later?

There isn't a third. A model is disqualified on principle — this mechanism exists to be trustworthy
*when the model is not*, the same reason model-as-judge was rejected for the discovery benchmark.
Mechanically mutating the finding's named location was considered and rejected too: it tests
sensitivity to a *place*, not dependence on the *bug*, manufacturing exactly the false confidence this
guards against.

## Tests

```bash
pytest tests/unit/test_patch_reconstruct.py \
       tests/architecture/test_verification_no_model.py \
       tests/integration/test_poc_runner_loop.py -q
```

Offline; no model, container, or network.

- Reconstruction tests assert **real `git apply` accepts** the output — not that a string matches. The
  whole bug was that something *looked* like a patch and no tool would take it; a string test would
  have caught nothing.
- Outcome and quarantine behavior is tested in `test_poc_runner_loop.py`, where loop-level verdict
  behavior already lives — not in a new unit file.
- `test_verification_no_model.py` guards FR-011: no model call in the verification path. That is a
  principle, not a preference, so it gets a test.

# Research: Make Falsification-Verification Actually Run (spec 025)

Every decision below is grounded in the current code and in two captured live-run logs — not in
recollection. Two of them exist only because reading the artifact contradicted the plan.

## Decision 1: The naming hazard — `unverified_pass` already exists and means something ELSE

**Finding**: the runner already emits `unverified_pass`, but for a completely different condition
than the one this feature must surface. Today's logic:

```python
if real_pass:
    outcome = "passed"
    if mutation_verify(...) == "unverified_pass":
        outcome = "unverified_pass"
```

`mutation_verify` returns one of three values, and only ONE of them changes the outcome:

| mutation_verify returns | meaning | outcome today |
|---|---|---|
| `"verified"` | proof broke on the fix → it depends on the bug | `passed` |
| `"unavailable"` | could not check at all | `passed` ← **the conflation** |
| `"unverified_pass"` | checked; proof SURVIVED the fix → it proves nothing | `unverified_pass` |

So `unverified_pass` means *"we checked and it failed the check"* — the opposite end from *"we could
not check"*. Naming the new state anything near it would be a trap for every future reader.

**Decision**: three distinct outcomes, chosen so no two can be confused:

- `passed_verified` — falsification ran and the proof broke on the fix.
- `passed_unchecked` — falsification could not run; carries a reason (FR-002).
- `unverified_pass` — **unchanged**, both string and behavior (FR-003).

**Rationale**: FR-003 forbids touching the existing downgrade. Its name is genuinely poor (it means
"the proof is bogus", not "unverified"), but renaming it is a behavior-adjacent change this feature
did not ask for and would obscure the diff. Recorded here as known debt rather than silently fixed.

## Decision 2: Renaming `passed` breaks quarantine — the trap that would have shipped silently

**Finding**: the quarantine gate keys on the literal string:

```python
if outcome not in ("passed", "compiled") and res is not None:
    # move the PoC to audit/poc_failed/
```

Splitting `passed` into `passed_verified`/`passed_unchecked` without touching this line would send
**every successful PoC to quarantine** — a silent, severe regression with no exception and no red
test anywhere near it.

**Decision**: update the membership test to the new success set, and pin it with a dedicated test
asserting each of `passed_verified`, `passed_unchecked` and `compiled` is NOT quarantined while
`unverified_pass` still IS.

**Rationale**: `unverified_pass` being quarantined is correct and must stay — a proof that survives
its own fix proves nothing and belongs with the failures. This is exactly the class of coupling that
`/speckit-analyze` exists to catch; it was found by grepping consumers of the string before writing
any code.

## Decision 3: Only three fix sources exist, and one of them is disqualified

**Finding**: `task["fix"]` has exactly one producer today —
`finding["fix"] = extract_fix_for_finding(report, finding)` — and `mutation_verify` returns
`"unavailable"` immediately when it is falsy (`no_fix`).

**Decision**: add the operator as a second source, with precedence. A model is disqualified as a
third: a model in the verification path destroys the mechanism's purpose (it exists to be trustworthy
*when the model is not*) — the same reasoning that rejected model-as-judge for the discovery
benchmark.

**Rationale**: the falsification invariant needs *a* fix, not *the report's* fix. The report carries
one for 3 of 5 findings and 0 of 18 leads; the operator can write one for any of them. The bar is
low — falsification only needs the bug's behavior gone, so inverting a condition suffices; it need
not be the fix that ships.

**Alternatives considered**: mechanically mutating the finding's named `location` — rejected, it
tests sensitivity to a *place*, not dependence on the *bug*, and would manufacture false confidence.
That is precisely the failure this mechanism exists to prevent, so a weaker signal here is worse than
none.

## Decision 4: The report's diffs are illustrations — proved with the tools, not inferred

**Finding**: the fix blocks carry correct `--- a/<path>` / `+++ b/<path>` headers, but their hunk
markers are prose context with no line numbers (`@@ struct TRequest {`). Both tools reject them, run
against a real fixture:

```
git apply --unsafe-paths -p1  →  "No valid patches in input"     (exit 128)
patch -p1 --forward           →  "I can't seem to find a patch"  (exit 2)
```

**Decision**: reconstruct a real line-numbered patch, then apply it with the unchanged tooling.

**Rationale**: this is normal audit-report style, not a defective report. `mutation_verify`'s founding
assumption ("the report carries an applyable fix") is false in general — which is why the mechanism
has run 0 times in 10 passes across two runs. It was never broken; it could not have worked.

## Decision 5: Three real traps the algorithm must survive

Read from all three real blocks, not from one example:

1. **Abbreviated anchor.** One block reads `@@ function requestRedeemInner(...) internal {` — `(...)`
   is the author's ellipsis. The anchor does not exist verbatim in the source. No deterministic rule
   recovers the original signature → **must refuse** (US4). This is why we expect at most 2 of the 3
   blocks to reconstruct.
2. **Deep indentation.** Removal lines carry real source indentation (8 spaces in one block). Matching
   must be verbatim including leading whitespace; re-indenting would silently target the wrong line.
3. **No trailing context, near-identical add/remove.** One block's removals and additions are
   identical except for a middle line, and it ends with no trailing context line.

**Decision**: match anchor + every context/removal line VERBATIM, require the anchor to resolve to
exactly ONE line, and refuse on anything else. No fuzzy matching, no best-guess, no normalization.

## Decision 6: Reconstruction lives in its own module

**Decision**: `scripts/patch_reconstruct.py`, not inside `poc_queue_runner.py`.

**Rationale**: the runner is already ~2600 lines. The algorithm is self-contained (text in, patch or
refusal out), has no dependency on the runner's state, and its refusal taxonomy deserves tests that
do not drag in the harness. `scripts/solidity_index.py` set the precedent for extracting a
self-contained analysis unit the runner imports.

## Decision 7: Tests must apply the patch with the real tool

**Decision**: reconstruction tests assert `git apply` **accepts** the output against a real temp git
repo — not that a string matches an expected blob.

**Rationale**: FR-016. The entire bug being fixed is that something *looked* like a patch and no tool
would take it. A string-comparison test would have passed against the illustrative diff too, and would
have caught nothing. The test must exercise the same acceptance the production path depends on.

## Revisiting feature 010's FR-009 (no fuzzy patching)

The existing rule: apply with standard tooling; a diff neither tool applies is a clean failure; no
fuzzy patching. That rule is about **applying a real patch**, and it is correct there.

This feature **reconstructs a patch from an illustration**, then applies it with the same tooling,
unchanged. The reconstruction is not fuzzy — Decision 5 makes it *stricter* than the tools (unique
anchor, verbatim context, refuse otherwise). The rule's intent — never land a fix somewhere we are
not certain of — is preserved and tightened.

Recorded as a deliberate, justified narrowing, not a quiet bypass. Spirit unchanged: certainty or
refusal.

## Fixture rule (non-negotiable)

The live report and logs ground this design and stay OUTSIDE the repo. Every fixture is invented,
reproducing only the SHAPE of an illustrative diff (memory `feedback_no_target_code_in_agent`), and
prompts/comments carry no target identifier (guarded by `tests/architecture/test_no_target_material.py`).

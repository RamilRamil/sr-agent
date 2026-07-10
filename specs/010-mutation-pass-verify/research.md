# Research: Mutation-Based PASS Verification

## R1 — Fix extraction: deterministic report parsing, not via the model

**Decision**: Extract each finding's fix diff by DETERMINISTICALLY parsing the report
text — never by asking the model to emit the diff. The report lays findings out
uniformly (confirmed against this session's report): a `[NN] **N. Title**` heading, an
optional `**Fix**` marker, a fenced ` ```diff … ``` ` block, and a `---` separator
between findings. Parse the report into ordered finding-sections; for the finding at
extraction index i, take report section i's fenced diff (if any), guarded by a
title-overlap sanity check (the extracted `title` must share significant tokens with
the report heading) so a mis-alignment degrades to "no fix" rather than a wrong diff.
A finding whose section has no diff (e.g. this report's finding #4) yields `fix=None`.

**Rationale**: A unified diff is whitespace- and character-exact; routing it through
the extraction model risks silent mangling (reindented hunks, dropped context lines)
that then fails to apply — turning a verifiable finding into a false
`mutation_verify_unavailable`. Deterministic parsing preserves the diff byte-for-byte.
Keying by section order + a title sanity-check is robust to the model skipping a
finding while still degrading honestly when unsure.

**Alternatives considered**:
- *Add a `fix` field to the EXTRACT_PROMPT's JSON* — rejected: the model would have to
  reproduce a multi-line diff inside JSON, the highest-risk possible mangling surface.
- *Match finding→section purely by fuzzy title, ignoring order* — rejected as the
  primary key (titles can be paraphrased); order + a title sanity-check is more stable.

## R2 — Applying the fix: ephemeral copy + standard patch tooling

**Decision**: Copy the target project to a temporary directory (`shutil.copytree`,
excluding regenerable build caches like `out/`/`cache_forge/` to keep it lighter — a
cold recompile is acceptable on this rare path), apply the fix diff with `git apply`
(falling back to `patch -p1 --forward`), then run the SAME PoC via the existing
`run_tests` against the copy. The real target tree is never touched (FR-004). The temp
copy is deleted after the run.

**Rationale**: `run_tests(project_dir, …)` mounts `project_dir` into the sandbox, so
verifying against a patched source means running against a patched COPY — a temp
copytree is the simplest correct isolation, and mutation-verify only fires on a genuine
PASS (rare), so the copy cost is amortized to near-nothing. `git apply` handles the
report's git-style hunk headers (`@@ struct TRequest {`) robustly; a diff that fails
both `git apply` and `patch` is a clean `mutation_verify_unavailable` (FR-009 — no
fuzzy patching). If the patched source then fails to COMPILE (`_compiled` is False on
the re-run), that too is `unavailable` (reason: patched source didn't build), not a
downgrade — a downgrade must rest on a real test FAILURE (FR-006).

**Alternatives considered**:
- *`git stash`/worktree on the real tree* — rejected: mutates or complicates the real
  repo; a throwaway copy is safer and simpler (FR-004 by construction).
- *Apply the diff in-memory to specific files without a full copy* — rejected: forge
  needs the whole project tree (lib/, remappings) to build; partial copies are fragile.
- *Copy including build caches* — rejected as the default: larger/slower; excluding
  them forces a clean, trustworthy recompile of the patched source.

## R3 — Where it hooks in: only the `real_pass` branch

**Decision**: Invoke `mutation_verify(...)` from `_process_finding` (spec 009) exactly
where `outcome = "passed"` is set (the `real_pass` branch), and only there. On its
verdict: `verified` → keep `passed` (now log a `mutation_verified` event);
`unverified_pass` → set `outcome = "unverified_pass"`; `unavailable` → keep `passed`
(log `mutation_verify_unavailable`). No other outcome path is touched (FR-007).

**Rationale**: Mutation-verify is a post-hoc strengthener of exactly one claim — "this
PoC passed" — so it belongs at the single point that claim is made. Reusing spec 009's
extracted `_process_finding` means the whole thing is already offline-drivable through
that spec's fake harness; the patched re-run is just one more scripted `run_tests`
result. `compiled`-only (path-A) outcomes are not success claims and are left untouched
(spec's edge case).

**Alternatives considered**:
- *Verify every attempt, not just the final pass* — rejected: wasteful (only a PASS is
  a claim worth verifying) and it would change the common-path behavior (FR-007).
- *A separate post-run pass over all passed findings* — rejected: needs the PoC + task
  + sandbox context that `_process_finding` already holds; inline is simpler.

## R4 — Offline test seams

**Decision**: Two independently-testable layers. (a) Fix extraction + diff application:
tested against a real tmp "project" (a couple of `.sol` files) + a real small unified
diff — exercises the actual parse and `git apply`, fast and deterministic. (b) The
loop-level classification: extend spec 009's `tests/integration/test_poc_runner_loop.py`
— the vulnerable run is the loop's normal scripted `run_tests` PASS, and the patched
re-run is one MORE scripted `run_tests` result (fail → verified; pass → unverified_pass;
and a `fix=None`/apply-fail path → unavailable). The mutation_verify's own `run_tests`
call is the same monkeypatched seam spec 009 already controls.

**Rationale**: Splitting "does the diff apply" (real filesystem, real patch tool) from
"does the loop classify the two runs correctly" (scripted results) keeps each test
focused and fully offline (FR-008), mirroring spec 009's unit-vs-integration split.

**Alternatives considered**:
- *Only integration tests* — rejected: the real `git apply` behavior (does a report's
  diff actually apply) deserves its own direct test against a real diff, not a mock.

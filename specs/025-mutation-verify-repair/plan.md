# Implementation Plan: Make Falsification-Verification Actually Run

**Branch**: `025-mutation-verify-repair` | **Date**: 2026-07-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/025-mutation-verify-repair/spec.md`

## Summary

The project's trust rule — a passing proof is evidence only once it **fails** against the finding's
own fix — has executed successfully **zero times** across two live runs and 10 `passed` verdicts. Not
because of a bug: the report's fix blocks are illustrations (prose hunk markers, no line numbers), both
patch tools reject them outright, and the existing no-fuzzy-patching rule guaranteed a permanent no-op.
Meanwhile "could not check" and "checked and survived" both report as `passed`.

Four changes, in dependency order:

1. **US1 — stop the misreport.** Split `passed` into `passed_verified` / `passed_unchecked` (+reason).
   Cheapest, independent, and it is the floor that makes everything else honest.
2. **US2 — the operator can supply the fix.** Removes the ceiling: works for any finding, including the
   18 leads that never carry a report fix. Highest-trust source, no reconstruction needed.
3. **US3 — reconstruct from an illustrative diff.** Free per finding once built, but caps at 3 of 23.
4. **US4 — refuse rather than guess.** The load-bearing safety property.

Grounded in [research.md](research.md), which caught two traps that would have shipped silently: the
name `unverified_pass` already means the *opposite* thing, and the quarantine gate keys on the literal
string `"passed"`.

## Technical Context

**Language/Version**: Python 3.12 (existing harness code)

**Primary Dependencies**: none new — stdlib `re`/`subprocess`; `git apply` already invoked today

**Storage**: N/A (operator patches are files supplied by path, outside the repo)

**Testing**: pytest, offline; reconstruction tests apply output with the REAL `git apply` against a
temp git repo (FR-016) — never a string comparison

**Target Platform**: operator CLI (`scripts/poc_queue_runner.py`), macOS/Linux

**Project Type**: single project — operator tooling on top of the kernel/pack

**Performance Goals**: N/A (text processing, once per verified finding)

**Constraints**: fully offline; NO model anywhere in the verification path; deterministic (identical
input → identical patch); the falsification execution step untouched

**Scale/Scope**: one new module (~150 lines), ~40 changed lines in the runner, two new test files

## Constitution Check

| Principle | Status | Rationale |
|---|---|---|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | No new trust promotion. The operator's patch is `human_input` — the highest tier, and it is used only as data for a local patch tool. The report's diff is already-ingested tool/report data, unchanged in status. |
| **II. Human Authority** | ✅ **STRENGTHENS** | Directly serves "findings are hypotheses, confirmed only by a passing PoC — never by model assertion". The mechanism enforcing that has never run; this makes it run. US2 puts the *human* in the authoritative seat for what counts as "fixed". No irreversible action; the real target tree is never mutated (FR-014). |
| **III. Kernel / Pack Separation** | ✅ PASS | New module lives in `scripts/` (operator tooling), like `solidity_index.py`. No kernel or pack code touched; no new kernel→pack import. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | No knowledge-store writes. |
| **V. No Paid-API Dependency** | ✅ **STRENGTHENS** | FR-011 forbids a model call anywhere in the verification path, on principle — a model here would destroy the mechanism's reason to exist. Everything added is stdlib + `git apply`. |

**Gate result**: PASS on all five, two of them strengthened. No violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```
specs/025-mutation-verify-repair/
├── spec.md              # what & why (4 stories; "Honest expectations" bounds the claim)
├── plan.md              # this file
├── research.md          # 7 decisions, each grounded in code or captured logs
├── quickstart.md        # how to supply a fix and read a verification outcome
├── tasks.md             # (/speckit-tasks)
└── checklists/
    └── requirements.md
```

No `data-model.md` (no persistence) and no `contracts/` (no external interface — a CLI flag and log
fields, exercised through the existing runner). Omitted rather than stubbed.

### Source Code (repository root)

```
scripts/
├── patch_reconstruct.py        # NEW — illustrative diff -> real patch, or a stated refusal
│   ├── ReconstructionRefused   #   the refusal type, carrying a reason
│   ├── parse_illustrative()    #   headers + hunks at each `@@ <anchor>` marker
│   ├── locate_anchor()         #   exactly-one-or-refuse
│   └── reconstruct()           #   -> unified diff with real line numbers
└── poc_queue_runner.py         # MODIFIED
    ├── mutation_verify(...)    #   returns (status, reason); signature otherwise UNCHANGED
    ├── build tasks (~line 476) #   NEW: finding["fix_patch"] alongside finding["fix"]
    ├── _process_finding(...)   #   outcome split + quarantine set updated
    └── main()                  #   NEW: --fix-patch <id>=<path>

tests/unit/
└── test_patch_reconstruct.py   # NEW — US3/US4, applies output with REAL git apply

tests/integration/
└── test_poc_runner_loop.py     # MODIFIED — US1/US2 outcome + quarantine tests belong here

tests/architecture/
└── test_verification_no_model.py  # NEW — FR-011: no model call in the verification path
```

**Structure Decision**: the reconstruction algorithm gets its own module (research Decision 6) — the
runner is already ~2600 lines, and the algorithm is self-contained (text in, patch-or-refusal out) with
a refusal taxonomy deserving tests that do not drag in the harness. `scripts/solidity_index.py` set the
precedent.

**Test placement follows the layout the repo already documents in-file** — `test_poc_runner_loop.py`
states it explicitly: *"mutation_verify's internals (extract/apply/classify) are unit-tested in
test_poc_queue_runner.py; here we test that the LOOP consults it exactly on a genuine PASS and applies
its verdict"*. Outcome and quarantine behavior is loop behavior, so US1/US2 tests extend that file and
reuse its `_run_with_mutverify`/`_process_finding` harness. An earlier draft invented a new
`tests/unit/test_verify_outcomes.py`, which both duplicated that role and could not have worked — the
quarantine assertion needs `_process_finding`, not a unit seam. Only `test_patch_reconstruct.py` is
genuinely new, because reconstruction is genuinely a new self-contained unit.

## Design

### US1 — the outcome split, and the trap under it

Three outcomes, named so no two can be confused (research Decision 1):

| outcome | meaning |
|---|---|
| `passed_verified` | falsification ran; the proof broke on the fix |
| `passed_unchecked` | falsification could not run — **+ reason** (FR-002) |
| `unverified_pass` | **unchanged**: checked, and the proof SURVIVED the fix → it proves nothing |

`unverified_pass` already exists and means the *opposite* of "we could not check" — hence
`passed_unchecked` rather than anything adjacent to it. Its name is poor (it means "bogus proof"), but
FR-003 forbids touching it; recorded as known debt.

`mutation_verify` returns its reason alongside `"unavailable"` so FR-002's five cases (`no_fix`,
`reconstruction_refused`, `patch_failed`, `patched_no_build`, `infra`) reach the outcome. It already
logs each of these; they simply never surfaced.

**The trap**: the quarantine gate is `if outcome not in ("passed", "compiled")`. Splitting `passed`
without updating it quarantines **every successful PoC**. The membership set becomes
`("passed_verified", "passed_unchecked", "compiled")`, and a dedicated test pins that
`unverified_pass` is still quarantined (correct — a proof that survives its own fix belongs with the
failures).

### US2 — the operator channel

`--fix-patch <finding_id>=<path>`, repeatable. Paths must resolve outside the agent's project area
(FR-015), reusing the guard the runner already applies to target paths.

**The patch is resolved at task-build time, not threaded into `mutation_verify`.** The runner already
attaches the report's fix where findings are built:

```python
finding["fix"]      = extract_fix_for_finding(report, finding)   # ILLUSTRATIVE — needs reconstruction
finding["fix_patch"] = operator_patches.get(finding["id"])       # REAL — applied as-is
```

Two keys, not one, because the two sources are different in kind: `fix_patch` is already a genuine
patch and must never be reconstructed or rewritten (FR-004), while `fix` is an illustration that must
be. Keeping them apart makes that distinction structural rather than a runtime guess.

`mutation_verify`'s signature is therefore **unchanged** — it reads precedence off the task
(`fix_patch` → `fix` → none, FR-005). An earlier draft called a `_resolve_fix(task, operator_patches)`
inside `mutation_verify`, which cannot work: that function has no such parameter and nothing threads
one in. Resolving at build time removes the plumbing instead of adding it.

Failure to apply → `passed_unchecked` with reason `patch_failed`; never verified, never a failure
(FR-006).

### US3/US4 — reconstruction, and the refusal that carries the feature

Input is an illustrative block: real `--- a/` / `+++ b/` headers, body split at each `@@ <anchor>`.
Per hunk: locate the anchor in the real source; require **exactly one** match; walk the hunk's context
and removal lines requiring **verbatim** equality (leading whitespace included); emit a real hunk header
with correct line counts.

Every uncertainty refuses with a stated reason (FR-009):

| refusal | trigger |
|---|---|
| `anchor_not_found` | 0 matches — includes the abbreviated `(...)` anchor, by design |
| `anchor_ambiguous` | >1 match |
| `context_mismatch` | a context/removal line is not verbatim in the source |
| `file_not_found` | the block names a file absent from the target |

Any hunk refusing refuses the whole fix (FR-012) — a partially applied fix is a wrong signal, not a
partial one. No fuzzy matching, no normalization, no best-guess (FR-010): a patch landed in the wrong
place yields a **wrong** `verified`, which is worse than the current no-op because the operator would
believe it.

## Test Strategy

Offline, synthetic fixtures only (invented names/paths — the live report grounds the design and stays
outside the repo).

`tests/unit/test_patch_reconstruct.py` (US3/US4) — **every success case asserts real `git apply`
accepts the output** against a temp git repo (research Decision 7; a string-comparison test would have
passed on the illustrative diff too and caught nothing):

- exact anchor, single hunk → applies cleanly
- removals with deep indentation → applies, indentation preserved
- removals+additions with no trailing context → applies
- multiple hunks in one file → all located independently, combined patch applies
- abbreviated `(...)` anchor → refuses `anchor_not_found`
- anchor matching zero lines → refuses
- anchor matching two lines → refuses `anchor_ambiguous`
- a context line not verbatim in source → refuses `context_mismatch`
- one hunk of two refuses → the whole fix refuses (FR-012)
- determinism: same input twice → byte-identical patch

`tests/integration/test_poc_runner_loop.py` (US1/US2) — extending the existing
`_run_with_mutverify`/`_process_finding` harness, where loop-level outcome behavior already lives:

- verified → `passed_verified`
- unavailable(each reason) → `passed_unchecked` carrying that reason
- survived-the-fix → `unverified_pass`, unchanged
- operator patch preferred over a report fix
- operator patch that fails to apply → `passed_unchecked` + `patch_failed`
- no fix from any source → `passed_unchecked` + `no_fix`
- **quarantine set**: `passed_verified`/`passed_unchecked`/`compiled` NOT quarantined;
  `unverified_pass` still IS
- no inability to verify ever yields a failure outcome (FR-006/SC-006)

That file's header comment currently documents the exact mapping this feature changes
(*"verified/unavailable keep `passed`, only unverified_pass downgrades"*). It must be rewritten in the
same change, or it becomes a confident lie about the code beneath it.

`tests/architecture/test_verification_no_model.py` (FR-011): the verification path performs no model
call. FR-011 is a principle, not a preference — a model here would destroy the mechanism's reason to
exist — and principles in this repo are guarded by a test (`test_harness_sandbox_only.py` sets the
precedent for exactly this shape).

## Complexity Tracking

None. Constitution Check passes on every principle with no deviation to justify.

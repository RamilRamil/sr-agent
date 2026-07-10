# Quickstart: Mutation-Based PASS Verification

How to verify this feature is done — entirely offline (no model, Docker, or network).

## 1. Fix extraction is deterministic and byte-exact

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k extract_fix -q
```

Confirm `extract_fix_for_finding` pulls a finding's fenced ` ```diff ``` ` block
verbatim from a synthetic report, returns `None` for a finding with no `**Fix**`
block, and never reformats the diff.

## 2. The fix actually applies (real patch tooling, real tmp source)

```bash
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k git_apply -q
```

Confirm a real small unified diff applies to a real tmp source copy via `git apply`
(and the fallback path), and a non-applying diff reports failure — no fuzzy patching.

## 3. The loop classifies the two runs correctly (SC-001/SC-002/SC-003)

```bash
.venv/bin/python -m pytest tests/integration/test_poc_runner_loop.py -k mutation -q
```

Confirm, via spec 009's fake sandbox (the patched re-run is one more scripted
`run_tests` result):
- passes-on-vulnerable → FAILS-on-patched ⇒ outcome stays `passed`, `mutation_verified`
  logged (SC-002).
- passes-on-vulnerable → STILL-passes-on-patched ⇒ outcome `unverified_pass`,
  `mutation_unverified` logged (SC-001) — the exact 2026-07-06 false-positive class.
- no fix / diff won't apply ⇒ outcome stays `passed`, `mutation_verify_unavailable`
  with a reason (SC-003) — never a false downgrade.

## 4. The real tree is never mutated (SC-004)

The apply/verify tests assert the source fixture is byte-for-byte unchanged after a
mutation-verify run (all patching happens on a temp copy that is deleted).

## 5. Full offline suite green (SC-005)

```bash
.venv/bin/python -m pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```

All previously-passing tests plus the new ones pass, entirely offline, no
bug-bounty target code embedded.

## 6. (Optional, US3) Live H-01 confirmation

Only if pursued — NOT the completion bar. If a live H-01 run reaches a PASS, record in
[docs/roadmap.md](../../docs/roadmap.md) whether it verified, downgraded to
`unverified_pass`, or was unavailable — a downgrade is an informative, honest outcome
(the pass didn't actually depend on the bug).

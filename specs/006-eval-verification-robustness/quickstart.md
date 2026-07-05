# Quickstart: Eval/Verification Robustness

How to verify this feature is done, and how to apply its principle the next time a
new automated check is added anywhere in this project.

## 1. Verify the corrected detector (the actual incident, reproduced + fixed)

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
.venv/bin/python -c "
import importlib.util as u
spec = u.spec_from_file_location('r', 'scripts/poc_queue_runner.py')
m = u.module_from_spec(spec); spec.loader.exec_module(m)

# Known-bad, worded differently than the old denylist anticipated (the actual incident):
bad = 'Error: Encountered invalid solc version in test/neutrl/NeutrlDeploy.t.sol: No solc version installed that matches the version requirement: =0.8.28'
assert m._compiled(bad, '') is False, 'REGRESSION: incident transcript misclassified as compiled'

# Known-good: forge actually ran the suite (even if the test itself then reverted).
good = 'Ran 1 test for audit/poc/H_03.t.sol:PoC_H_03\n[PASS] testPoC_H_03() (gas: 459)'
assert m._compiled(good, '') is True, 'REGRESSION: a genuine compile+run was misclassified as failed'

print('OK — positive-signal detector: incident case fails, genuine case passes')
"
```

Expected: `OK — ...` — both assertions pass. This is the test that would have caught
the 2026-07-05 incident before it produced a false milestone.

## 2. Re-verify the (corrected) audit table still matches the code

Open `contracts/audit-checklist.md` and confirm each listed function still matches its
described `signal_type`/`blocking`/justification by reading its current source in
`scripts/poc_queue_runner.py`. This is a manual, cheap check — the table is meant to be
re-read whenever that file changes, not automated (it's documentation of *reasoning*,
not a lint rule).

## 3. Confirm the roadmap correction

```bash
grep -n "MILESTONE\|2026-07-05\|solc" docs/roadmap.md | head -20
```

Expected: the entry describing the PoC-workability milestone reflects the HONEST
outcome (the denylist bug, the corrected detector, the re-verified/current compile
status) — not the original, false "all 3 findings compiled" claim.

## 4. Read the durable documentation

```bash
open docs/eval-principles.md   # or: cat docs/eval-principles.md
```

Expected sections: the general principle (positive-signal + cross-check), the audit
table (same content as `contracts/audit-checklist.md`), and the SmartGraphical
recommendation (same content as `contracts/mechanism-check-recommendation.md`).
Cross-linked from `docs/audit-agent.md` and the README's doc index.

## 5. Applying this the next time you add an automated check (for future contributors)

1. Before writing the check, ask: "what marker can ONLY appear on genuine success?" —
   not "what messages have I seen on failure?"
2. Write a test with a known-good case AND a known-bad case **worded differently than
   you'd naturally guess** (the exact shape of this incident) — if you can only think
   of failure messages you've personally seen, you're at risk of writing a denylist by
   habit.
3. Decide out loud whether the check `blocking`s an outcome or is `diagnostic`-only; if
   diagnostic, write its known limitations in its docstring.
4. Add a row to `contracts/audit-checklist.md` in the same change.
5. If the check's verdict will be quoted in a documentation milestone/claim, make sure
   a genuinely independent second signal corroborates it first (research.md R2) —
   re-deriving the same signal from the same transcript does not count.

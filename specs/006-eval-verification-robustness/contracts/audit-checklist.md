# Contract: Success-Gate Audit Checklist

The reusable format for auditing any set of automated verdict-producing checks in this
repository against the positive-signal principle (research.md R1). Every future
capability pack or tool that adds an automated success/failure check over a generated
artifact should be run through this same table before its verdicts are trusted.

## Format

| Check (function/module) | Signal type | Blocking? | Justification (if denylist or narrow exception) | Known limitations (if diagnostic) |
|---|---|---|---|---|
| `<name>` | `positive` \| `denylist` | yes/no | ... | ... |

**Pass condition**: every row has `signal_type == positive`, OR an explicit
`Justification` naming why a narrow exception is acceptable (see research.md R3 for the
one accepted example — a check against the artifact's own controlled declarations,
never an open-ended tool-output message).

## This feature's audit result (`scripts/poc_queue_runner.py`)

| Check | Signal type | Blocking? | Justification | Known limitations |
|---|---|---|---|---|
| `_compiled()` | positive (`Ran \d+ tests?`) | yes (feeds `compiled`/`compiled_real` outcomes) | — | none open |
| `_poc_defects()` | positive (requires active assert/import present) | yes (feeds `real_pass`/`compiled_real`) | its `contract <TargetStem>` re-declaration check is a narrow match against the PoC's OWN declared contract names (a closed, harness-controlled vocabulary), not an open-ended tool-output denylist | none open |
| `mechanism_signal()` | positive (checks a named method IS called) | **no — diagnostic only, logged, never gates an outcome** | — | cannot distinguish which contract **instance/type** a shared-interface method was called on (see research.md R4 — the exact gap a scoped SmartGraphical integration would close) |

## How to use this for a NEW check

1. Write the check as "does X (a well-defined success marker) appear/hold" — never
   "does none of these known-bad things appear."
2. Decide `blocking` deliberately: if it gates an `outcome`, it must be positive-signal
   with no open justification; if it's a diagnostic, it must say so out loud (in its
   docstring AND in the audit table here) together with its known blind spots.
3. Add a known-good and a known-bad-worded-differently-than-you'd-guess test case
   (mirrors this incident's exact shape) before trusting the check (see quickstart.md).
4. Add the row to this table in the same PR.

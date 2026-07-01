# Quickstart: SmartGraphical Engine

## Prerequisites
- SmartGraphical available either as a local checkout (CLI) or the `smartgraphical:local` Docker
  image. If neither is present, the engine pass auto-skips and the audit runs on Slither/Mythril
  + relay/local-model only.

## Running an audit (engine is automatic)
```
sr-agent audit ./contracts
```
During Stage 1's static-analysis pass the agent now also runs SmartGraphical on each `.sol` file.
Its logic findings appear in the report attributed to the `smartgraphical` engine, alongside
Slither and Mythril. The interference graph used by Stage 3 is built from SmartGraphical's
structural model when available.

Enable the engine by pointing SR-agent at a SmartGraphical checkout:
```
export SR_SMARTGRAPHICAL_ROOT=/path/to/SmartGraphical   # uses <root>/.venv/bin/python
```
Disable the engine for a run:
```
sr-agent audit ./contracts --no-smartgraphical
```

## What you should see
- Report `## Findings` entries tagged with `Engine: smartgraphical` for logic-level issues
  (e.g. withdraw preconditions, sensitive call ordering) that Slither/Mythril do not report.
- Cross-contract/inheritance findings combined in `## Combination Chains` when functions share
  state across files (US2).
- Every SmartGraphical finding is an unconfirmed hypothesis until a PoC passes (US3).

## Verifying the integration (tests)
```
pytest tests/unit/test_smartgraphical.py        # JSON→Finding + JSON→graph mapping (no SG needed)
pytest tests/unit/test_sig.py -k smartgraphical  # SIG-from-graph cases
pytest tests/integration/test_smartgraphical_live.py   # live run, auto-skips without SG
```

# Quickstart: AST-Grounded, Agentic Lookup for PoC Drafting

How to verify this feature is done — offline first (no GPU/model needed), then the
live H-01 validation (needs a Kaggle/Colab-hosted local model + Docker + a mainnet
fork RPC, same setup as this session's other live runs).

## 1. Offline: `SymbolIndex` correctness against real target fixtures

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
.venv/bin/python -c "
from scripts.solidity_index import SymbolIndex
from pathlib import Path
P = Path('/Users/ramilmustafin/Projects/Contests/2026-06-strata-bb/contracts')
idx = SymbolIndex.build(P)

# The exact struct-field case that motivated this feature (2026-07-05):
matches = idx.lookup('TBalanceState')
assert matches, 'TBalanceState must resolve'
assert 'shares' not in matches[0].definition, 'must not contain an invented field'
assert 'pending' in matches[0].definition and 'totalRequests' in matches[0].definition
print('OK — TBalanceState resolves to its real 5 fields, no invented shares field')

# Not-found must never fabricate:
assert idx.lookup('TotallyMadeUpStructName') == []
print('OK — a nonexistent symbol resolves to zero matches, never fabricated')
"
```

## 2. Offline: the dedup-collision case (spec 006's own bug, closed at the root)

```bash
.venv/bin/python -c "
from scripts.solidity_index import SymbolIndex
from pathlib import Path
P = Path('/Users/ramilmustafin/Projects/Contests/2026-06-strata-bb/contracts')
idx = SymbolIndex.build(P)
# Two functions sharing an identical modifier set must both be retrievable —
# neither silently dropped (the exact regex-dedup bug this session hit).
c = idx.lookup('cancel')
assert len(c) >= 1 and c[0].modifiers, 'cancel must resolve with its onlyUser(user) modifier intact'
print('OK —', c[0].name, 'modifiers:', c[0].modifiers)
"
```

## 3. Offline: lookup-protocol detection (no model call)

Feed a synthetic model response containing a `LOOKUP: TCancelGuard` line through the
protocol-detection function and confirm it's recognized, resolved, and the follow-up
prompt contains the real field list — without needing Ollama running.

## 4. Live: H-01 validation run (FR-007 / SC-003)

```bash
# same setup as this session's other fork runs: Kaggle tunnel + MAINNET_RPC_URL
cd /Users/ramilmustafin/Claude/Projects/SR-agent
set -a; source .env; set +a
SR_SECRET_KEY=$(printf '0%.0s' {1..64}) \
POC_PROJECT=/Users/ramilmustafin/Projects/Contests/2026-06-strata-bb/contracts \
POC_REPORT=/Users/ramilmustafin/Projects/Contests/2026-06-strata-bb/contracts/audit/contracts-pashov-ai-audit-report-20260702-073215.md \
.venv/bin/python -u scripts/poc_queue_runner.py \
  --host <fresh Kaggle tunnel URL> --model qwen3-coder:30b \
  --image sr-agent-foundry:strata-bb \
  --test-scaffold audit/proof-of-code-composer/base/PashovSharesCooldownBase.sol \
  --example-poc audit/proof-of-code-composer/leads/L05_DustRedemptionFeeRevert.t.sol \
  --only H-01 --attempts 6 --fork --lookup-budget 3 --max-minutes 35
```

Expected artifacts in the run log (`_runner_progress.jsonl`): one or more `event:
"lookup"` entries; a recorded final outcome (whatever it is). Report, per FR-007:
whether lookups were used, for which symbols, whether they resolved, and how the
attempt-by-attempt error signature compares to this session's pre-lookup H-01 runs
(fewer invented-identifier-class compile errors is the expected qualitative signal —
NOT a required passing PoC).

## 5. Regression check: existing static grounding still works unmodified

```bash
.venv/bin/python -m pytest tests/unit/ -k poc_runner -q
```

(Or the equivalent existing offline validations from this session's earlier commits —
file map / callable_api / scaffold resolution must be unaffected, per FR-005/R6:
this feature is additive.)

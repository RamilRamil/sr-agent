# Quickstart: Native Agentic Tool-Calling for PoC Symbol Lookup

How to verify this feature is done — entirely offline (no live model/GPU needed
for the completion bar per FR-009/User Story 4; a live comparison is optional and
listed last).

## 1. Offline: capability detection

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
.venv/bin/python -c "
from sr_agent.llm_core import local_client as lc
import unittest.mock as mock

# A model whose /api/tags entry reports 'tools' in capabilities:
with mock.patch.object(lc.urllib.request, 'urlopen') as m:
    m.return_value.__enter__.return_value.read.return_value = b'''
    {\"models\": [{\"name\": \"qwen3-coder:30b\",
                   \"capabilities\": [\"completion\", \"tools\"]}]}
    '''
    assert lc.LocalClient(model='qwen3-coder:30b').supports_tools() is True
    print('OK — a model reporting tools capability is detected')
"
```

## 2. Offline: native tool-calling round-trip (scripted response, no model)

Feed a fake `LocalClient.chat()` a scripted Ollama-shaped response containing
`message.tool_calls: [{"function": {"name": "lookup_symbol", "arguments": {"name":
"TCancelGuard"}}}]`, confirm:
- the harness resolves it via the REAL `SymbolIndex.lookup()` (same fixture used
  by spec 007's own tests),
- appends a `{"role": "tool", ...}` message whose content matches spec 007's
  text-marker rendering for the identical `matches` byte-for-byte (SC-002),
- logs `{"event": "lookup", ...}` in the pre-existing shape (FR-006),
- and, once the scripted follow-up response has no more `tool_calls`, returns
  clean Solidity source with no residual tool-call scaffolding (FR-007).

## 3. Offline: budget exhaustion and multi-call turns (parity with spec 007)

Scripted response with MORE tool calls in one turn than the remaining budget —
confirm only the remaining budget's worth are resolved and the model is forced to
a final answer, mirroring spec 007's own budget-exhaustion test.

## 4. Offline: fallback to the text-marker protocol

Scripted `/api/tags` response WITHOUT `"tools"` in capabilities — confirm the
harness selects `marker` mode automatically and the existing spec 007 `LOOKUP:`
path runs completely unmodified (regression check on spec 007's own offline
tests, e.g. `tests/unit/test_solidity_index.py`, `tests/unit/test_poc_queue_runner.py`).

## 5. Offline: `--lookup-protocol` override

```bash
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k protocol -q
```

Confirm `--lookup-protocol tool` on a non-tool-capable model errors clearly at
startup (protocol-selection.md's decision table), and `--lookup-protocol marker`
on a tool-capable model still uses the text-marker path (for A/B comparison).

## 6. (Optional, FR-009/User Story 4) Live comparison against spec 007's H-01 baseline

Only if pursued — NOT required for this feature to be considered done. Same setup
as spec 007's live runs (Kaggle tunnel + `MAINNET_RPC_URL`), with
`--lookup-protocol tool` (or `auto`, since `qwen3-coder:30b` is detected as
tool-capable):

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
set -a; source .env; set +a
POC_PROJECT=/Users/ramilmustafin/Projects/Contests/2026-06-strata-bb/contracts \
POC_REPORT=/Users/ramilmustafin/Projects/Contests/2026-06-strata-bb/contracts/audit/contracts-pashov-ai-audit-report-20260702-073215.md \
.venv/bin/python -u scripts/poc_queue_runner.py \
  --host <fresh Kaggle tunnel URL> --model qwen3-coder:30b \
  --image sr-agent-foundry:strata-bb \
  --only H-01 --fork --lookup-budget 3 --max-minutes 20
```

Report, per FR-009: whether `message.tool_calls` was actually used reliably by the
real `qwen3-coder:30b` build (vs. writing the call as plain text despite the
schema being declared), and an honest comparison against
[docs/roadmap.md](../../docs/roadmap.md)'s already-recorded H-01 baseline —
"no observable difference" is a valid, acceptable outcome (this feature changes
transport, not resolution logic).

## 7. Regression check: spec 007's existing suite is untouched

```bash
.venv/bin/python -m pytest tests/unit tests/architecture tests/security tests/frontend -q
```

All previously-passing tests (247 as of spec 007/T020's completion) must still
pass — this feature is additive to `scripts/poc_queue_runner.py` and
`sr_agent/llm_core/local_client.py`, and must not regress `SymbolIndex` or any
kernel behavior.

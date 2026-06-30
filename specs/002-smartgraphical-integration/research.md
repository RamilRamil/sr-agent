# Research: SmartGraphical Integration

Phase 0 decisions. Each: Decision / Rationale / Alternatives considered.

## R1 — Invocation mechanism

**Decision**: Invoke SmartGraphical as an **external tool that emits JSON** — primary path is its
CLI (`python sg_cli.py <file> all auditor json`); the `smartgraphical:local` Docker image is the
sandboxed equivalent. SR-agent shells out and parses stdout JSON, exactly like `run_slither`.

**Rationale**: Mirrors the proven Slither pattern; adds **zero** Python dependency to SR-agent;
keeps the engine swappable and version-pinned behind a stable JSON contract; SmartGraphical's
`web_api` facade already returns JSON-safe dicts and the CLI JSON output is a documented stable
contract. Even though the code is the user's own, a process boundary keeps the two codebases
independently testable and avoids importing SmartGraphical's transitive deps (FastAPI, etc.).

**Alternatives considered**:
- *Library import* (`from smartgraphical.services import web_api`): tightest coupling, pulls in
  its deps, harder to sandbox; rejected for the first integration (can revisit if perf demands).
- *Vendor (copy) the adapter + rules into sr_agent*: large code move, diverges from upstream;
  rejected — premature.

## R2 — Confidence → Severity

**Decision**: Map SmartGraphical `confidence` to SR-agent `Severity`:
`high→high`, `medium→medium`, `low→low`. Findings with no confidence default to `low`.

**Rationale**: SmartGraphical confidence is a calibrated hypothesis strength, not an impact score;
mapping it to severity keeps expectations honest (most rules emit `medium`). True impact is
established later by the severity conjunction check + PoC, not by the engine's self-rating.

**Alternatives considered**: Map by rule category to fixed severities — rejected as less honest
(the engine's own confidence is the better signal, and KNOWN_QUIRKS documents the FP-proneness).

## R3 — Category / rule_id → BastetTag

**Decision**: A best-effort lookup table from SmartGraphical `rule_id` (and `category` fallback)
to `BastetTag`. Unmapped rules store **no tag** (`None`) rather than a guessed one. Initial map:

| SG rule_id | BastetTag |
|---|---|
| read_only_oracle_reentrancy / unstake_share_burn_order / bridge_retry_reentrancy | reentrancy / read_only_reentrancy / cross_function_reentrancy |
| check_order (oracle price→transfer) | oracle_manipulation |
| min_slippage_bounds | sandwich_attack |
| outer_calls / unallowed_manipulation | missing_access_control |
| withdraw_check / local_points / staking | logic_error |
| pool_interactions | erc20_compliance |
| tainted_input_unguarded_sink | missing_check |
| similar_names / contract_version | (none — informational/naming) |

**Rationale**: The taxonomy must stay faithful (the Finding model already rejects hallucinated
tags); leaving unmapped rules untagged is the honest default and the report still shows the
SmartGraphical category + rule_id verbatim.

**Alternatives considered**: Force every rule into the nearest tag — rejected (introduces wrong
categories into memory).

## R4 — Graph → SIG

**Decision**: Add `build_sig_from_smartgraphical(graph_json)` that constructs the existing
`StateInterferenceGraph` from SmartGraphical's edges:
- `state_to_function_read/write` → per-function `reads`/`writes` sets,
- `function_to_function` / `cross_type_call` → call adjacency (for `can_reenter` and cross-fn
  reasoning),
- external-call flags from `function_to_system` / `function_to_object` edges and the function's
  `external_calls`.
`interferes()` / `can_reenter()` keep their current semantics. The pipeline prefers the SG-built
SIG when available and **falls back** to the regex `build_sig` otherwise (FR-005).

**Rationale**: Reuses the `StateInterferenceGraph` contract and Stage 3 unchanged; only the graph
*source* improves (accurate read/write incl. storage aliases, inheritance via `cross_type_call`,
multi-file). The fallback preserves determinism with no SmartGraphical present.

**Alternatives considered**: Replace `sig.py` entirely — rejected; the regex SIG stays as the
no-dependency fallback and for non-Solidity or unparsed files.

## R5 — Multi-file scope

**Decision**: For US2, drive SmartGraphical over the **bundle** of in-scope Solidity files (it
already supports a bundle manifest with import/inheritance resolution and emits cross-file edges).
For US1 (findings), per-file invocation is sufficient and simpler; bundle mode is the US2 add-on.

**Rationale**: Findings are per-file; the interference graph benefits most from cross-file edges.
Staging this keeps US1 minimal.

**Alternatives considered**: Always bundle — rejected; unnecessary for US1 and slower.

## R6 — Engine attribution & dedup

**Decision**: Add an `engine` label to the stored finding payload (`"slither" | "mythril" |
"smartgraphical" | "model"`) surfaced in the report (FR-008). Cross-engine **dedup is soft**: the
report may group findings sharing `(file, function, category)`, but no finding is dropped —
corroboration across engines is signal, not noise.

**Rationale**: Provenance is cheap and high value for the auditor; silent dedup could hide a
second engine confirming the same bug (which raises confidence for PoC prioritization).

**Alternatives considered**: Hard dedup by location — rejected (loses corroboration signal).

## R7 — Hypothesis invariant (US3)

**Decision**: No new mechanism — assert the existing behavior: SmartGraphical findings are written
with `source_type=tool_output`, default `FindingStatus` is unconfirmed, the status gate already
blocks any privileged status without `human_input`, and `sanitize()` is applied to the message.
US3 is a test-only phase pinning these invariants for the new engine.

**Rationale**: The guardrails already enforce this; the feature must not weaken them, so the work
is verification, not new code.

**Alternatives considered**: A dedicated "needs_poc" flag — rejected; `FindingStatus` +
`poc_status` already model this.

# Implementation Plan: Kernel / Capability-Pack Boundary

**Branch**: `004-kernel-pack-boundary` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-kernel-pack-boundary/spec.md`

## Summary

Draw the kernel↔pack seam for real: introduce one explicit **`CapabilityPack`** contract that the kernel consumes by injection, extract every audit-specific concept behind it, and relocate the audit code into `sr_agent/packs/audit/` so the boundary is a **directory rule** an automated check enforces (`no module outside packs/ imports sr_agent.packs`, → 0). The kernel keeps sole ownership of all trust invariants (DATA-wrapping, SourceType hierarchy + no-promotion, HMAC memory, the OOB confirmation gate, the per-turn budget, path-containment, sandbox); a pack may add restrictions but the tested property is that it **cannot lower any of them**.

The work is a behavior-preserving re-layering, not a rewrite. It inverts control at the points the kernel currently reaches into audit:

- **Action model** — `Action`/`ActionClass`/`ValidationStatus`/`ValidationResult` stay kernel; the concrete audit `ActionType` values + their class/reversibility/param-validators move to the pack. The kernel keeps a small built-in set (`read_file`, `search_code`, `write_memory`, `request_human_confirmation`, `escalate`); the pack contributes its domain actions. `validate_action(action, root, pack)` becomes the mechanism; **the OOB-confirmation requirement is derived by the kernel from action class (write_execute ⇒ confirm), never taken on the pack's word** (FR-005).
- **Escalation** — `evaluate_triggers` keeps the three generic triggers (irreversible action, memory status-change, resource limit); the five finding-based triggers move to a pack-provided `domain_escalation`. `EscalationTrigger` (the label enum) stays kernel — the pack imports it (pack→kernel is allowed).
- **Loop** — `_dispatch`, `execute_confirmed`, `_persist_finding` become pack callables; the loop retains the control flow (validate → derive-confirmation → OOB gate → execute) and the invariants. `AgentAction.finding` becomes an opaque `dict` the pack parses, so the model's JSON wire-shape is unchanged.
- **Reasoning** — `ChatReasoningProvider` keeps the local-first + deterministic-escalation mechanism; the audit system prompt and the finding-extraction move to pack-provided `reasoning_prompt` + `persist_finding`/`signal` hooks.
- **Session/Principal** — `Principal` is a generic kernel concept mislocated in `models/audit.py`; it moves to a kernel module (fixes `memory/episodic.py`, `io/`, `cli.py` for free). `AuditSession` factors into a kernel `Session` protocol (session_id, principal, iterations, token_budget_used — all the kernel reads) plus an audit extension that stays in the pack.
- **Relocation** — `models/finding.py`, `models/audit.py` (audit parts), `planner/*`, `tools/{static_analysis,smartgraphical,onchain,write_execute}`, `guardrails/{mock_detect,severity}`, `orchestrator/pipeline.py`, `io/{report,input_val}`, and the extracted policy modules move under `sr_agent/packs/audit/`. `cli.py` is the composition root (the one place allowed to import the pack).

Sequenced so the security property (US2) and a green suite land first, and the boundary check runs as a **ratchet** (violations N→0) with a safe stopping point after each relocation.

## Technical Context

**Language/Version**: Python 3.14 (existing `.venv`, `sr_agent/` package) — unchanged.

**Primary Dependencies**: `pydantic` (models), `click` (CLI), stdlib `ast` (the boundary-check import scan — no new dependency). No new runtime deps; this is structural.

**Storage**: Unchanged. `EpisodicMemory` (HMAC append-only). Note: relocating shared model shapes (e.g. `Finding`, `AuditSession`) may change a signed record's serialized class path; prior records may fail verification and be silently dropped — acceptable (memory is ephemeral; precedent: feature 003).

**Testing**: `pytest` via `PYTHONPATH=. .venv/bin/python -m pytest` (existing convention). New: `tests/architecture/test_kernel_pack_boundary.py` (the import-scan boundary check) and `tests/security/test_hostile_pack.py` (the pack-cannot-weaken-a-guardrail property). The existing suite is the behavior-preservation oracle.

**Target Platform**: CLI on macOS/Linux — unchanged.

**Project Type**: Single Python package (`sr_agent/`) — re-layered internally into kernel modules + one `packs/audit/` pack + a composition root.

**Performance Goals**: None new. Constraint is *no observable behavior change* (US3): same findings/decisions from the audit path, same routing/gating/answers from chat.

**Constraints**: Behavior-preserving (FR-009/010/011); `validate_action` / `REQUIRES_OOB_CONFIRMATION`-equivalent / `confirmation.py` semantics unchanged; the model's `AgentAction` JSON wire-shape unchanged; no dynamic plugin registry / discovery / runtime loader (FR-008); pack→kernel imports allowed, kernel→pack forbidden and checked.

**Scale/Scope**: One pack (audit). 52 `sr_agent` modules today; ~15 kernel-side files currently import audit and will be inverted/cleaned; the audit code relocates under `packs/audit/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against constitution v1.0.0 (ratified 2026-07-02). This feature **is the enforcement of Principle III**, and upholds the rest:

- **I. Secure-Kernel Trust Invariants** — every invariant stays kernel-owned; the refactor moves *policy* out, never the invariants. DATA-wrapping (`context.wrap_data`), the `SourceType` hierarchy + no-promotion, HMAC `EpisodicMemory`, and the per-turn budget are untouched kernel code. PASS.
- **II. Human Authority** — the OOB confirmation gate stays in the kernel loop; **the confirmation requirement is derived from action class by the kernel, not declared by the pack** (FR-005), so a pack cannot shortcut it. Privileged-status set moves to the pack as *data*, but the kernel enforces the gate. PASS.
- **III. Kernel/Pack Separation** — this feature realizes it: one declarative `CapabilityPack`, kernel imports nothing pack-specific (checked), **no dynamic registry** (FR-008, YAGNI). PASS (by construction).
- **IV. Human-Gated Knowledge** — unaffected; no knowledge-promotion path changes. Draft lessons stay `llm_inference`. PASS.
- **V. No Paid-API Dependency** — `claude_client.py` stays an *optional* kernel transport the audit pack may inject; the core loop and chat still run local/relay. No new paid dependency. PASS.

**Security Requirements** — MI harness stays the gate (ASR must remain 0, FR-011); the new `tests/security/test_hostile_pack.py` adds the Principle-III property test the constitution mandates; sandboxed execution of attacker-influenced tools is unchanged (the sandbox stays kernel, pack tools run inside it).

No violations to justify; Complexity Tracking omitted.

## Project Structure

### Documentation (this feature)

```text
specs/004-kernel-pack-boundary/
├── plan.md              # This file
├── research.md          # Phase 0 output — the HOW decisions (R1–R12)
├── data-model.md        # Phase 1 output — CapabilityPack contract, kernel Session protocol, move map
├── quickstart.md        # Phase 1 output — how to run the boundary check + hostile-pack tests
├── contracts/           # Phase 1 output
│   ├── pack-interface.md     # what a pack provides; what the kernel guarantees (the documented contract, FR-013)
│   ├── boundary-check.md     # the automated kernel→pack import rule (SC-001)
│   └── hostile-pack.md       # the pack-cannot-weaken-a-guardrail property (US2/SC-003)
└── tasks.md             # Phase 2 output (/speckit-tasks — not this command)
```

### Source Code (target layout — repository root)

```text
sr_agent/
├── cli.py                         # COMPOSITION ROOT — the one place allowed to import the pack;
│                                   #   wires AUDIT_PACK into OrchestratorLoop / pipeline
├── config.py                      # kernel (unchanged)
├── orchestrator/
│   ├── pack.py                    # NEW kernel — CapabilityPack + ActionSpec contract (the interface)
│   ├── loop.py                    # MODIFY — takes `pack`; dispatch/execute_confirmed/persist_finding
│   │                               #   delegate to pack; control flow + invariants stay kernel
│   ├── action.py                  # MODIFY — validate_action(action, root, pack): mechanism only;
│   │                               #   confirmation-required DERIVED from action_class (kernel rule)
│   ├── confirmation.py            # kernel (unchanged)
│   ├── context.py                 # MODIFY — drop dead AuditSession type hint → pure kernel
│   ├── checkpoint.py              # MODIFY — type to kernel Session protocol
│   └── chat_session.py            # MODIFY — type to kernel Session protocol
├── guardrails/
│   ├── sanitize.py                # kernel (unchanged)
│   └── escalation.py              # MODIFY — keep generic triggers (1,2,8); call pack.domain_escalation
├── memory/                        # kernel (unchanged; episodic.py cleaned by Principal relocation)
├── models/
│   ├── memory.py                  # kernel (unchanged)
│   ├── chat.py                    # MODIFY — type to kernel Session protocol / Principal
│   ├── action.py                  # MODIFY — generic Action/ActionClass/Validation* + kernel built-in actions
│   ├── principal.py               # NEW kernel — Principal (relocated from models/audit.py)
│   └── session.py                 # NEW kernel — Session protocol the loop/escalation read
├── llm_core/
│   ├── schemas.py                 # MODIFY — AgentAction.finding: dict|None (opaque); EscalationTrigger stays
│   ├── chat_reasoning.py          # MODIFY — mechanism only; prompt + finding-extraction come from pack
│   ├── local_client.py            # MODIFY — generic client; audit _PROMPT moves to pack
│   ├── claude_client.py           # kernel — optional transport (pack injects it for paid audit reasoning)
│   ├── relay.py                   # kernel (unchanged)
│   └── router.py                  # kernel (unchanged)
├── tools/
│   ├── registry.py                # MODIFY — ToolDefinition + hash-verify mechanism stays; entries come from pack
│   ├── sandbox.py                 # kernel (unchanged) — pack tools run inside it
│   └── readonly.py                # kernel — read_file/search_code (generic file ops)
└── packs/
    └── audit/
        ├── pack.py                # NEW — AUDIT_PACK = CapabilityPack(...) assembly
        ├── actions.py             # NEW — audit ActionType values + class/reversibility + param validators
        ├── dispatch.py            # NEW — read/write dispatch + execute_confirmed (from loop.py)
        ├── escalation.py          # NEW — the 5 finding-based triggers (from guardrails/escalation.py)
        ├── reasoning.py           # NEW — audit system prompt(s) + finding-extraction (from chat_reasoning/local_client)
        ├── registry_entries.py    # NEW — audit tool descriptions + hashes (from tools/registry.py)
        ├── finding.py             # MOVED from models/finding.py (Finding, Severity, BastetTag, SIG, statuses)
        ├── session.py             # MOVED — AuditSession/AuditInput/Stage1Report/Checkpoint (was models/audit.py)
        ├── pipeline.py            # MOVED from orchestrator/pipeline.py (Stage1→2→3 audit workflow)
        ├── planner/               # MOVED from planner/ (sig, stage1, stage2, stage3)
        ├── guardrails/            # MOVED — mock_detect.py, severity.py (audit-domain guardrails)
        ├── report.py              # MOVED from io/report.py (audit report rendering)
        ├── input_val.py           # MOVED from io/input_val.py (audit input validation)
        └── tools/                 # MOVED — static_analysis.py, smartgraphical.py, onchain.py, write_execute.py

tests/
├── architecture/
│   └── test_kernel_pack_boundary.py   # NEW — ast import scan: no kernel module imports sr_agent.packs → 0
├── security/
│   ├── test_hostile_pack.py           # NEW — pack cannot skip confirmation / author human_input / opt out of containment
│   └── (existing MI harness)          # REUSED — ASR must stay 0
└── (existing unit/integration)        # REUSED unchanged as the behavior-preservation oracle
```

**Structure Decision**: Keep the kernel modules in their existing packages (`orchestrator/`, `guardrails/`, `memory/`, `llm_core/`, `tools/`, `models/`) — relocating *them* would be churn for cosmetic gain — and give the audit pack a real home under `sr_agent/packs/audit/`. "Kernel" is then definitionally *everything under `sr_agent/` except `packs/` and the composition root (`cli.py`)*, which is exactly what the directory-based boundary check enforces. This is the incremental reading of Constitution III: one pack, an explicit wiring point in `cli.py`, no registry.

## Complexity Tracking

*No constitution violations to justify — table intentionally omitted (see Constitution Check above). The one judgment call — keeping kernel modules in place rather than moving them into a `sr_agent/kernel/` directory — is the lower-churn way to achieve a directory-checkable boundary and is recorded in the Structure Decision.*

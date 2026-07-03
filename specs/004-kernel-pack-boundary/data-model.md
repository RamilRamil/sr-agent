# Data Model: Kernel / Capability-Pack Boundary

This feature adds **no domain data** — it re-homes existing entities and introduces the *contract types* through which the kernel consumes a pack. Shapes below are the intended Python surface; field lists are illustrative of the boundary, not a frozen signature.

## New kernel contract types

### `CapabilityPack` (kernel — `sr_agent/orchestrator/pack.py`)

The declarative bundle the kernel consumes. Frozen dataclass (R1). Everything a pack contributes; nothing a pack can use to weaken a guarantee.

| Field | Type | Meaning | Kernel use |
|---|---|---|---|
| `name` | `str` | pack identifier (e.g. `"audit"`) | logging / diagnostics |
| `actions` | `Mapping[str, ActionSpec]` | domain action types → their spec | merged with kernel built-ins for `validate_action` + dispatch |
| `tools` | `Sequence[ToolDefinition]` | domain tool registry entries (name, description, class, hash) | merged into the verified registry (`verify_all_hashes`) |
| `privileged_statuses` | `frozenset[str]` | domain statuses that require OOB confirmation (`{verified_safe, skip_analysis, audit_complete}`) | kernel gates any status-change to one of these |
| `reasoning_prompt` | `str` | domain system prompt for the reasoning provider | injected into `ChatReasoningProvider` (R6) |
| `dispatch` | `Callable[[Action, PackContext], str]` | execute an approved read/other action, return DATA-wrapped output | called by the loop after validation (R8) |
| `execute_confirmed` | `Callable[[Action, PackContext], tuple[str, object \| None]]` | execute an approved **write_execute** action | called only on the resume path, post-approval |
| `persist_finding` | `Callable[[dict, PackContext], object \| None]` | turn an `AgentAction.finding` payload into a persisted domain artifact | called by the loop when the model reports a finding |
| `domain_escalation` | `Callable[[DomainEscalationInput], EscalationResult \| None]` | the finding-based escalation triggers (R5) | called by `evaluate_triggers` after the generic checks |
| `signal_from` | `Callable[[AgentAction], object \| None]` | extract the escalation signal a chat turn feeds to `domain_escalation` | used by `ChatReasoningProvider` (R6) |

**Constraint (the whole point):** `CapabilityPack` has **no** field that lets a pack set an action's confirmation requirement, its trust tier, or opt a tool out of validation/containment/sandbox. Those are kernel-derived (R2) and untouchable. This absence is what the hostile-pack test verifies.

### `ActionSpec` (kernel — `sr_agent/orchestrator/pack.py`)

Per-action metadata a pack supplies; the kernel's `validate_action` reads it.

| Field | Type | Meaning |
|---|---|---|
| `action_class` | `ActionClass` | `read_only` \| `write_execute` \| `memory` \| `control` — **this is the only confirmation lever a pack has**, and misclassification is caught by reversibility/sandbox rules + the hostile-pack test |
| `is_reversible` | `bool` | feeds trigger #1 (irreversible action) |
| `validate_params` | `Callable[[Action, Path], str \| None]` | per-action param validation (path-containment etc.); returns rejection reason or `None`. **The kernel still applies its own whitelist + containment even if this is absent/permissive** (fail-closed, R8/R10) |

### `PackContext` (kernel — `sr_agent/orchestrator/pack.py`)

The narrow, least-privilege surface passed to pack callables (R8) — **not** the loop itself.

| Field | Type | Meaning |
|---|---|---|
| `audit_root` | `Path` | scope root (path-containment already enforced by the kernel) |
| `sandbox` | `DockerSandbox` | the network-isolated sandbox pack tools must run inside. **Invocation-safety note (validated 2026-07-02, docs/roadmap.md gotcha #3):** `DockerSandbox.run()` passes `command` as raw argv appended after the image name; an image with a **shell-form `ENTRYPOINT`** (e.g. `ENTRYPOINT=["/bin/sh","-c"]`, as `ghcr.io/foundry-rs/foundry` uses) double-wraps a multi-element argv under its own `sh -c`, and the real command silently no-ops (exit 0, empty output — indistinguishable from a trivial pass). A pack tool wrapper MUST hand such an image a **single command string** (`command=[full_shell_string]`), never an argv list, and MUST NOT assume a passing exit code means the command actually ran. |
| `poc_dir` | `Path` | where write_execute artifacts land |
| `wrap_data` | `Callable[..., str]` | the kernel's DATA-wrapper — pack output re-enters context wrapped, never raw |
| `memory` | `EpisodicMemory` | append-only, HMAC — a pack writes through it but cannot forge `human_input` (kernel sets source tier) |

### `Session` protocol (kernel — `sr_agent/models/session.py`)

Structural `typing.Protocol` (R4) — the fields the kernel reads from *any* session.

```python
class Session(Protocol):
    session_id: str
    principal: Principal
    iterations: int
    token_budget_used: int
```

### `Principal` (kernel — `sr_agent/models/principal.py`, relocated)

Unchanged shape (`user_id`, `platform`, `project_id`) — moved out of `models/audit.py` so the memory isolation boundary and CLI can reference it without importing the pack.

## Modified kernel types

- **`AgentAction`** (`llm_core/schemas.py`) — `finding: FindingPayload | None` becomes `finding: dict | None` (opaque payload; the pack validates it). Envelope fields (`next_action`, `tool_params`, `reasoning_summary`, `escalation_trigger`) unchanged. Wire-shape identical (R8/R11). `FindingPayload` moves to the pack.
- **`Action` / `ActionClass` / `ValidationStatus` / `ValidationResult`** (`models/action.py`) — stay kernel (generic). The concrete audit `ActionType` enum + `ACTION_CLASS_MAP` + `REVERSIBLE` move to the pack; the kernel keeps a small built-in action set (`read_file`, `search_code`, `write_memory`, `request_human_confirmation`, `escalate`).
- **`EscalationTrigger`** (`llm_core/schemas.py`) — stays kernel as a shared label taxonomy (the pack imports it; pack→kernel allowed).

## Move map (kernel → pack)

Relocated under `sr_agent/packs/audit/` (behavior-preserving; import sites updated):

| From | To | Notes |
|---|---|---|
| `models/finding.py` | `packs/audit/finding.py` | `Finding`, `Severity`, `BastetTag`, `SIG`, `FindingStatus`, `PoCStatus` |
| `models/audit.py` (audit parts) | `packs/audit/session.py` | `AuditSession`, `AuditInput`, `Stage1Report`, `Checkpoint`; `Principal` → kernel instead |
| `planner/` | `packs/audit/planner/` | `sig`, `stage1`, `stage2`, `stage3` |
| `orchestrator/pipeline.py` | `packs/audit/pipeline.py` | Stage1→2→3 audit workflow driver |
| `tools/static_analysis.py`, `smartgraphical.py`, `onchain.py`, `write_execute.py` | `packs/audit/tools/` | run inside the kernel sandbox |
| `guardrails/mock_detect.py`, `severity.py` | `packs/audit/guardrails/` | audit-domain guardrails |
| `io/report.py`, `io/input_val.py` | `packs/audit/report.py`, `input_val.py` | audit report + input validation |
| `llm_core/schemas.py::FindingPayload` | `packs/audit/` | the model-output finding DTO |
| policy extracted from `models/action.py` + `orchestrator/action.py` | `packs/audit/actions.py` | audit `ActionType`, class/reversibility, param validators |
| policy extracted from `guardrails/escalation.py` | `packs/audit/escalation.py` | 5 finding-based triggers |
| policy extracted from `tools/registry.py` | `packs/audit/registry_entries.py` | audit tool descriptions + hashes |
| prompt extracted from `chat_reasoning.py` + `local_client.py::_PROMPT` | `packs/audit/reasoning.py` | audit prompt + finding-extraction |
| dispatch extracted from `orchestrator/loop.py` | `packs/audit/dispatch.py` | `dispatch` + `execute_confirmed` |
| assembly | `packs/audit/pack.py` | `AUDIT_PACK = CapabilityPack(...)`, wired in `cli.py` |

## What stays kernel (invariants — never pack-overridable)

DATA-wrapping (`context.wrap_data`), the `SourceType` trust hierarchy and the no-promotion-to-`human_input` rule, HMAC append-only `EpisodicMemory`, the OOB confirmation gate + kernel-derived confirmation requirement (R2), the per-turn tool-call budget, path-containment, the Docker sandbox, `validate_action`'s whitelist mechanism, `verify_all_hashes`, and the generic escalation triggers (irreversible / memory-status-change / resource-limit).

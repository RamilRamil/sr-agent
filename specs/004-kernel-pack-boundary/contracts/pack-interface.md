# Contract: Capability-Pack Interface

The documented surface between the kernel and a capability pack (FR-013). A reader should be able to enumerate **everything a pack provides** and **everything the kernel guarantees regardless of the pack** from this file alone, without reading kernel internals.

> **No plugin registry.** There is exactly one pack (`audit`), wired explicitly in `sr_agent/cli.py`. This contract documents the interface so a *second* pack could be written against it later; it does **not** authorize building discovery/loading infrastructure now (Constitution III, FR-008).

## What a pack provides (the `CapabilityPack`)

A pack is a single frozen `CapabilityPack` value. It supplies exactly these, and nothing else:

1. **`name`** — an identifier for diagnostics.
2. **`actions`** — a map of its domain action-type ids to an `ActionSpec` (`action_class`, `is_reversible`, `validate_params`). The pack's *only* risk lever is `action_class`.
3. **`tools`** — registry entries (`name`, `description`, `action_class`, `description_hash`) for its domain tools, merged into the kernel-verified registry.
4. **`privileged_statuses`** — the set of domain statuses whose change requires human confirmation.
5. **`reasoning_prompt`** — the domain system prompt for the reasoning provider.
6. **`dispatch(action, ctx)`** — execute an approved non-write action; return DATA-wrapped output.
7. **`execute_confirmed(action, ctx)`** — execute an approved `write_execute` action (resume path only).
8. **`persist_finding(payload, ctx)`** — turn a model-reported finding payload into a persisted domain artifact.
9. **`domain_escalation(input)`** — the domain's finding-based escalation triggers.
10. **`signal_from(agent_action)`** — extract the escalation signal a chat turn feeds to `domain_escalation`.

Pack callables receive a narrow **`PackContext`** (`audit_root`, `sandbox`, `poc_dir`, `wrap_data`) — never the loop, never kernel internals, and **no memory handle**: a pack cannot write memory, so it structurally cannot forge a `human_input`-tier record. The pack *returns* domain artifacts; the kernel persists them with a kernel-set tier.

## What the kernel guarantees (a pack CANNOT alter any of these)

- **DATA-wrapping** — every tool result and re-entering artifact is wrapped `[DATA START]..[DATA END]` and treated as untrusted; a pack's output goes through `wrap_data`, never raw into context.
- **Trust hierarchy + no promotion** — `human_input > tool_output > external_llm_output > llm_inference`; a pack's output (and its model's output) is recorded no higher than `external_llm_output`/`tool_output` and is never promotable to `human_input`.
- **HMAC append-only memory** — a pack has **no memory-write capability** (no handle in `PackContext`); the kernel performs every write with a kernel-set source tier, so a pack cannot forge a tier, backdate, or delete. A pack only returns artifacts for the kernel to persist.
- **OOB confirmation gate** — the requirement is **kernel-derived from `action_class`** (`write_execute ⇒ confirm`) and from `privileged_statuses`; a pack cannot mark such an action/status as not-requiring-confirmation. No convenience surface bypasses it.
- **Per-turn tool-call budget** — bounds every turn; a pack cannot raise or remove it.
- **Whitelist + path-containment + sandbox** — every pack tool is validated against the registry, confined to `audit_root`, and (for attacker-influenced execution) run inside the network-isolated Docker sandbox; a pack cannot opt out. A missing/permissive `validate_params` fails **closed** — kernel defaults still apply.
- **Sandbox invocation safety (pack-author responsibility, not kernel-enforced)** — `DockerSandbox.run()` is a thin argv-passthrough; it does not inspect or normalize the target image's `ENTRYPOINT` form. A pack tool wrapper invoking an image with a **shell-form entrypoint** (`ENTRYPOINT=["/bin/sh","-c"]`) MUST pass its command as a single string, not an argv list — an argv list double-wraps under the image's own `sh -c` and silently no-ops (exit 0, empty output, indistinguishable from a trivial pass). Confirmed 2026-07-02 against `ghcr.io/foundry-rs/foundry`; see `docs/roadmap.md` gotcha #3 and `data-model.md`'s `PackContext.sandbox` entry.
- **Generic escalation** — irreversible-action, unauthorized memory-status-change, and resource-limit triggers fire independent of the pack.

## Directionality

- **kernel → pack imports: forbidden** (enforced by [boundary-check.md](boundary-check.md)).
- **pack → kernel imports: allowed and expected** — a pack imports kernel contract types (`CapabilityPack`, `Action`, `ActionClass`, `EscalationTrigger`, `Session`, `Principal`, `wrap_data`, the sandbox).
- **composition root**: `sr_agent/cli.py` is the one place that imports the pack and injects it.

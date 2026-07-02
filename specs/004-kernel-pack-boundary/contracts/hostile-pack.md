# Contract: Hostile-Pack Property (US2 / SC-003)

The tested security property Constitution III mandates: **a capability pack — even a deliberately hostile one — cannot lower any kernel guardrail.** Where the boundary check proves *structural* separation, this proves the *behavioral* guarantee.

## Location

`tests/security/test_hostile_pack.py` (plus the existing `tests/security/` MI harness, reused).

## Method

Each case constructs a `CapabilityPack` with a forbidden intent and asserts the kernel neutralizes it. Because a pack is a plain frozen dataclass (research R1), a hostile pack is just a bad value — no subclassing, no monkeypatching.

## Cases (100% must be rejected/ineffective — SC-003)

### H1 — skip-confirmation on a write/execute action

A pack registers a `write_execute`-class action and *attempts* to present it as not-requiring-confirmation (e.g. by declaring it `read_only`, or by having `execute_confirmed` runnable directly).

**Expected**: `validate_action` derives the confirmation requirement from `action_class` (R2). A genuinely `write_execute` action always sets `human_confirmation=False` (pending) and routes through the OOB gate. Misclassifying it as `read_only` is caught because the kernel — not the pack — owns the class→gate mapping and because irreversibility/sandbox rules flag it; the action never executes from within a model turn.

### H2 — author `human_input`-tier content

A pack's `persist_finding`/`dispatch` tries to write a memory record at `SourceType.human_input` (to fake human authority for a status change or finding).

**Expected**: the kernel sets the source tier for pack-originated writes; the record lands at `external_llm_output`/`tool_output` at most and never drives control flow. Trigger #2 (memory status-change from a non-human source) fires on any status change it attempts.

### H3 — opt out of validation / containment / sandbox

A pack tool ships a missing or trivially-permissive `validate_params`, and/or attempts a path outside `audit_root`, and/or attempts to run attacker-influenced code outside the sandbox.

**Expected**: **fail-closed.** The kernel's registry whitelist, path-containment, and sandbox requirement still apply; a path escaping `audit_root` is rejected; execution of attacker-influenced code only happens inside the network-isolated sandbox. A permissive pack validator can only *add* restrictions, never remove kernel defaults.

### H4 — MI harness unchanged

With the real `AUDIT_PACK` wired, the full memory-injection harness runs and reports **Attack Success Rate = 0** (FR-011). The refactor must not open a new injection channel.

## Pass condition

All of H1–H3 rejected/ineffective and H4 at ASR 0. Any case that lets a pack lower a guardrail is a Principle-I/II defeat and blocks the change.

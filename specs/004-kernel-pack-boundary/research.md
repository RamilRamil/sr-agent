# Research: Kernel / Capability-Pack Boundary

Phase 0 decisions. Each resolves a HOW left open by the spec. Grounded in the actual coupling measured in the codebase (import scan + reads of `orchestrator/{loop,action}.py`, `guardrails/escalation.py`, `llm_core/{schemas,chat_reasoning,local_client}.py`, `models/{action,audit}.py`, `orchestrator/context.py`, `tools/registry.py`).

## R1 — How is a pack represented?

**Decision**: A single frozen dataclass `CapabilityPack` holding **data + callables** (declarative bundle), instantiated once as `AUDIT_PACK` and injected. No base class for packs to subclass, no ABC/plugin protocol to implement dynamically.

**Rationale**: Constitution III says a pack is *declarative and constrained* and forbids a dynamic registry until a second pack exists (FR-008/YAGNI). A frozen dataclass is the least-powerful representation that carries everything the kernel needs, and it makes the US2 test trivial to write: a hostile pack is just a `CapabilityPack(...)` with bad values, constructed inline. Callables (not subclass overrides) keep the kernel in control of *when* pack code runs.

**Alternatives considered**: (a) An ABC `CapabilityPack` with abstract methods a pack subclasses — more ceremony, invites a registry, and a subclass can override more than intended. (b) Entry-point/plugin discovery — explicitly rejected by FR-008. (c) Config/YAML-driven pack — rejected; code is the pack, wired in `cli.py`.

## R2 — Who decides an action needs out-of-band confirmation?

**Decision**: The **kernel** derives it from `action_class`: any `write_execute`-class action requires OOB confirmation, full stop. The pack declares each action's *class* (and reversibility), but cannot declare "this write_execute action skips confirmation." `validate_action` sets `human_confirmation=False` (pending) for every write_execute-class action regardless of pack input.

**Rationale**: This is the load-bearing security invariant of the whole feature (FR-005, Constitution II). If the pack supplied a `requires_confirmation: bool`, a hostile/ buggy pack could set it `False` and shortcut the gate. Deriving from class means the pack's only lever is classification, and misclassifying a write as read-only is itself caught by the class→reversibility→sandbox rules and by the hostile-pack test.

**Alternatives considered**: A per-action `requires_confirmation` flag on the pack — rejected: it hands the pack the exact lever Constitution II forbids. A kernel allow-list of "safe" pack actions — rejected: inverts the fail-closed default.

## R3 — Where does the boundary physically sit, and how is it checked?

**Decision**: Pack code lives under `sr_agent/packs/audit/`. "Kernel" = every `.py` under `sr_agent/` **except** `sr_agent/packs/**` and the composition root `sr_agent/cli.py`. The boundary check (`tests/architecture/test_kernel_pack_boundary.py`) uses `ast` to parse every kernel file's imports and asserts none resolve to `sr_agent.packs`. **pack→kernel imports are allowed and expected**; only kernel→pack is forbidden.

**Rationale**: A directory rule is self-enforcing and cannot rot — a new kernel file that imports the pack fails the check automatically, unlike a hand-maintained allowlist (which, measured today, would have to whitelist ~15 violating files and thus enforce almost nothing). The single composition-root exception is real and honest: `cli.py` is neither kernel nor pack; it wires them.

**Alternatives considered**: Hand-maintained `KERNEL_MODULES`/`PACK_MODULES` lists (option C from planning) — rejected as rot-prone and currently near-meaningless. Moving the kernel into `sr_agent/kernel/` too — rejected as churn for cosmetic gain; the "everything-but-packs" definition is sufficient and the plan's Structure Decision records it.

## R4 — How does `Principal` / `AuditSession` split?

**Decision**: `Principal` (user_id, platform, project_id) moves to a kernel module `sr_agent/models/principal.py` — it is a generic identity concept only mislocated in `models/audit.py`. A kernel `Session` **protocol** (`sr_agent/models/session.py`) declares the fields the kernel actually reads: `session_id`, `principal`, `iterations`, `token_budget_used`. `AuditSession` moves to the pack (`packs/audit/session.py`), keeps its audit fields (stages, finding_ids, audit_input), and structurally satisfies the protocol.

**Rationale**: The scan showed `memory/episodic.py` imports `models.audit` only for `Principal` — so the scariest-looking coupling (memory→audit) is fixed for free by relocating `Principal`. `escalation.py` reads only `token_budget_used`/`iterations`; `context.py` reads *nothing* (dead hint); `checkpoint.py`/`chat_session.py` read `session_id`/`principal`. A structural `typing.Protocol` lets these type to the kernel `Session` without importing the pack and without a runtime base class.

**Alternatives considered**: A kernel `Session` base class `AuditSession` inherits — works but forces an import direction and a runtime dependency; a Protocol is lighter and import-free. Leaving `Principal` in audit and passing `project_id: str` around — rejected: loses the typed principal the memory isolation boundary relies on.

## R5 — How does `evaluate_triggers` split?

**Decision**: The kernel keeps the three **domain-independent** triggers — irreversible action (from `action_class` + reversibility), memory status-change (from a non-human `status_change` record), resource-limit (from session budget). The five **finding-based** triggers (critical, unverified-high, mock-test, contradicting, unknown-pattern) move to `packs/audit/escalation.py` as `domain_escalation(inputs) -> EscalationResult | None`. The kernel calls generic checks first, then `pack.domain_escalation`; first match wins (order preserved).

**Rationale**: Triggers 1/2/8 reference only kernel types (`Action`, `MemoryRecord`, `Session`); 3–7 reference `Finding`/`Severity`/`FindingStatus`/`PoCStatus`. Splitting on that line removes the kernel's `models.finding` import while preserving the exact evaluation order and semantics (behavior-preserving). `EscalationTrigger` (the label enum in `llm_core/schemas.py`) stays kernel; the pack imports it to tag its results (pack→kernel is allowed).

**Alternatives considered**: Move all of `evaluate_triggers` to the pack — rejected: triggers 1/2/8 are core guardrails (irreversibility, unauthorized status-change) that must hold for *any* pack and belong in the kernel. Make `EscalationTrigger` a plain string per side — rejected: needless churn across many tests; the shared enum is a harmless label.

## R6 — How does `ChatReasoningProvider` shed its audit knowledge?

**Decision**: The provider keeps its mechanism (readiness gate → local generate → strict `AgentAction` parse → generic escalation check → relay routing). The audit **system prompt** and the **finding-extraction** (`_finding_from`) become pack-supplied: `pack.reasoning_prompt` (str) and `pack.signal_from(agent_action)` (maps a parsed `AgentAction` to whatever the pack's `domain_escalation` needs). `chat_reasoning.py` no longer imports `models.finding`, `models.audit`, or the audit prompt.

**Rationale**: FR-002 forbids the kernel referencing finding models; the provider currently imports `BastetTag/Finding/Severity/AuditSession`. Injecting the prompt + a `signal_from` hook keeps the local-first/escalation logic generic while the pack owns "what a finding looks like." The `Session` the provider holds types to the kernel protocol.

**Alternatives considered**: Leave `chat_reasoning.py` in the pack — rejected: local-first + refuse-and-wait + deterministic-escalation-only is a *kernel* guarantee (FR-011, Constitution V), reusable by any pack. Pass the whole pack into the provider vs. just the two hooks — decided to pass the pack (uniform with the loop) but the provider only touches `reasoning_prompt` + `signal_from`.

## R7 — How does the tool registry split?

**Decision**: `tools/registry.py` keeps the `ToolDefinition` shape, the `_hash`/`verify_all_hashes` mechanism, and `ToolTampered`. The audit tool **entries** (descriptions + hashes) move to `packs/audit/registry_entries.py`. The effective registry the kernel verifies is *kernel built-ins ∪ pack tools*; `verify_all_hashes` runs over the assembled set at loop start.

**Rationale**: Tamper-verification is a kernel integrity mechanism; the *content* (audit tool descriptions) is pack data. Read-only `read_file`/`search_code` are kernel built-in tools (generic file ops in `tools/readonly.py`), so they stay kernel; the pack adds slither/mythril/graph/onchain/poc/etc.

**Alternatives considered**: Keep all entries in `tools/registry.py` — rejected: those descriptions ("audit scope", "Slither", "SIG") are pack knowledge in a kernel file. Hash pack entries at import in the pack — kept in the pack module, verified centrally by the kernel mechanism.

## R8 — How does the loop delegate execution without losing the invariants?

**Decision**: `OrchestratorLoop.__init__` takes `pack`. The control flow stays kernel: build DATA-wrapped context → reason → (persist via `pack.persist_finding`) → terminal-action handling → `validate_action(action, root, pack)` → **kernel-derived** OOB gate → dispatch. `_dispatch` and `execute_confirmed` become `pack.dispatch(action, ctx)` / `pack.execute_confirmed(action, ctx)`, where `ctx` exposes only kernel-sanctioned capabilities (audit_root, sandbox, poc_dir, `wrap_data`). The read-only kernel built-ins (`read_file`/`search_code`) may be handled by a kernel default dispatch so even a pack-less kernel can read files.

**Rationale**: The kernel must keep the sequence that enforces Constitution I/II; only the *leaves* (which bytes a tool returns, how a finding is built) are pack. Passing a narrow `ctx` (not `self`) stops a pack from reaching kernel internals. `AgentAction.finding` becomes `dict|None` so the kernel hands the raw payload to `pack.persist_finding` without importing `FindingPayload`/`Finding`.

**Alternatives considered**: Let the pack own the whole loop — rejected: the loop *is* the kernel's trust boundary. Give the pack `self` (the loop) — rejected: too much authority; a narrow `ctx` is the least-privilege surface.

## R9 — What does the boundary check actually assert, and how does it ratchet?

**Decision**: `test_kernel_pack_boundary.py` collects kernel files (glob `sr_agent/**/*.py` minus `packs/**` minus `cli.py`), parses each with `ast`, resolves `import`/`from ... import` targets, and asserts none start with `sr_agent.packs`. During implementation it prints the current violation set and count; the **final** assertion is count == 0. The test is committed early (US1 start) as an executable ratchet.

**Rationale**: Makes SC-001 a real, always-runnable gate and makes progress visible (N→0) so a safe green checkpoint is always identifiable. `ast` (not regex) avoids false hits in strings/comments.

**Alternatives considered**: `grep`-based check — rejected: matches strings/comments. `import-linter` dependency — rejected: no new dep needed; ~40 lines of `ast` suffices and is self-contained.

## R10 — What exactly does the hostile-pack test prove?

**Decision**: `tests/security/test_hostile_pack.py` constructs `CapabilityPack`s that attempt each forbidden move and asserts the kernel neutralizes them: (a) a `write_execute` action the pack tries to treat as no-confirmation → kernel still files an OOB request / sets `human_confirmation=False`; (b) a pack whose `persist_finding`/dispatch tries to write memory as `human_input` → the record lands no higher than `external_llm_output`/`tool_output`; (c) a pack tool with a missing/permissive param validator → kernel whitelist + path-containment + sandbox still apply (fail-closed); (d) the full MI harness still reports ASR 0 with the audit pack.

**Rationale**: This is the Principle-III property the constitution says *must be tested*. Framing each as an independent constructed pack keeps the cases legible and is why R1 chose a plain dataclass.

**Alternatives considered**: Only assert via the real audit pack — rejected: doesn't prove the *constraint*, only that today's pack behaves. A hostile pack is the adversary.

## R11 — How is behavior-preservation guaranteed?

**Decision**: The existing test suite (unit/integration/security) is the oracle and must stay green at every checkpoint. No logic changes — only relocation + dependency inversion. The model's `AgentAction` JSON wire-shape is unchanged (finding stays the same JSON object; only its Python type loosens to `dict`, re-validated in the pack). A representative audit run and a chat turn are diffed before/after (SC-004).

**Rationale**: FR-009/010/011 make no-regression a hard gate. Keeping the wire-shape and the confirmation/validation semantics identical means the oracle is meaningful.

**Alternatives considered**: Rewrite dispatch while moving it — rejected: conflates two risks; move first (green), improve later (separate feature).

## R12 — Placement of the paid `ClaudeClient`

**Decision**: `llm_core/claude_client.py` stays a **kernel** transport (it talks to an API and parses `AgentAction` — generic). The audit pack *injects* it as the reasoning provider for the non-chat paid path; chat injects `ChatReasoningProvider`. The kernel never *requires* it (Constitution V); a pack chooses it.

**Rationale**: Symmetry with `local_client.py` (also a kernel transport). Isolation per Constitution V is about the *core loop not depending* on it, which injection satisfies. Moving it to the pack would wrongly imply "audit == paid API," when the paid path is optional even for audit.

**Alternatives considered**: Move `claude_client.py` into `packs/audit/` — rejected: it's a transport, not audit knowledge; a future pack could use it too.

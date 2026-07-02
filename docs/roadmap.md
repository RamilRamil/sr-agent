# SR-agent — consolidated roadmap

Consolidated 2026-07-02. Meta-plan spanning the constitution + several specs. Captures decisions made in discussion so they survive context loss. Not itself a spec — points at the specs/commands that do the work.

## Framing

Two goals, in priority order: (1) learn to build a **memory-injection-resistant secure agent** (the reusable core); (2) demonstrate it on an **audit agent** (the first task pack). Everything below serves keeping goal (1) clean while goal (2) rides on top.

## Decisions locked (in discussion)

- **Secure microkernel + swappable capability-packs.** Kernel = trust-invariant, task-agnostic. Pack = task-specific (audit today). A pack is *declarative and constrained*: it may register tools and mark actions high-risk, but cannot weaken any kernel guarantee. That constraint is itself a security property to test.
- **Kernel invariants (non-negotiable):** deterministic orchestration plane; DATA-wrapping of every tool/prior-turn artifact on every turn; `SourceType` trust hierarchy; HMAC append-only memory; OOB confirmation for irreversible/privileged actions; per-turn tool-call budget; escalation machinery; model/relay output stays `external_llm_output` (never promoted to `human_input`).
- **Human-gated knowledge promotion.** Pipeline-steering knowledge is embedded ONLY by explicit human command. Tool-output-derived observations never self-promote (closes retrospective-poisoning: the error-learning loop must not become a self-built MI channel). The human's review+command is what elevates a model's draft lesson (`llm_inference`) to trusted (`human_input`).
- **Findings roadmap / progress = memory-backed, derived, mechanical-status-only.** Regenerable from the findings source (not a parallel truth). Tracks `pending → written → compiled → passed/failed/errored → skipped(+reason)` — NEVER security verdicts. "Test passed" = a reproduction exists, NOT "finding confirmed/safe" (that stays confirmation-gated). Enforces the no-lead-prefiltering rule: every finding AND lead gets a row; skips are explicit with reason.
- **YAGNI:** with one pack, do NOT build a dynamic plugin loader/registry. Draw the boundary + document the interface; generalize when pack #2 exists.
- **PoC drafting model routing (evidence-backed):** local `qwen2.5-coder:3b` ≈ 8 min/PoC on this box (measured 442s / 500s). Prefer relay/stronger model for real PoC drafts; keep local for cheap/short turns. This is exactly chat-mode's "hard reasoning → escalate" path.

## Sequence

### Phase 0 — tactical (now, no spec)
- Fix `scripts/poc_queue_runner.py`: default generation timeout 180s → ≥600s (measured need); add a circuit-breaker (stop + report after N consecutive failures, don't burn the queue).
- Ollama health already restored (was wedged at 38h uptime; restart fixed).
- Disposition of the current 22-item run: rerun as a slow overnight batch OR park until PoC-drafting is routed to relay. Open.

### Phase 1 — Constitution (`/speckit-constitution`)  ← recommended next
Fill the empty stub with the three decision-groups above (kernel invariants; kernel/pack separation; human-gated knowledge). High-leverage: it's the authority `/speckit-analyze` checks, and it freezes these decisions before they evaporate.

### Phase 2 — Amend spec 003 (chat mode)
Already has spec/plan/tasks/analyze + I1/C1/C2 fixes. Fold in, placing each on the correct side of the kernel/pack seam:
- **Health-check / readiness (kernel)** — `LocalClient.available()` (liveness) vs new `ready()` (short generate-probe, catches wedged Ollama). Corrects FR-011: "unavailable" must mean "fails readiness", not just "tags reachable".
- **PoC-execution contract (audit-pack)** — new `contracts/poc-execution.md`: output to `audit/poc/`; Foundry `poc` profile / `FOUNDRY_TEST=audit/poc` (NOT a second `foundry.toml` — breaks relative src/lib/remappings); inherit `via_ir=true`; generator output treated as data; generation timeout ≥600s. Adjust tasks T016/T017.
- **Findings-roadmap (memory-backed)** — status events → signed episodic memory; `.md` table = rendered view. Wire to `SessionFacts` (FR-009) + resume (FR-012).
- Re-run `/speckit-analyze`.

### Phase 3 — Implement spec 003 MVP (`/speckit-implement`)
Setup + Foundational + US1 (Q&A chat). This is also what first *wires* the orphaned `orchestrator/loop.py` — i.e. the kernel becomes real. While implementing, respect the seam (Phase-4 prep): new chat code in kernel-appropriate places; PoC/roadmap bits pack-tagged, not hardwired into `loop.py`.

### Phase 4 — Spec 004: kernel ↔ capability-pack boundary
**Status: fully SPEC'D (spec+plan+tasks+analyze committed `85049a0`), implementation DEFERRED.** We pause before implementing to first validate the agent's *workability* on a real task (PoC-writing for the pashov findings) — the near-term priority — rather than invest the multi-hour refactor up front.

Design locked to **Target A (full seam)**: introduce one declarative `CapabilityPack` the kernel consumes by injection; relocate audit-specifics under `sr_agent/packs/audit/`; enforce the boundary with a directory-based import check (`no kernel module imports sr_agent.packs` → 0). One pack, no dynamic registry (wired explicitly in `cli.py`; YAGNI). 35 tasks, 7 phases, sequenced so **US2 (the "a pack cannot lower a guardrail" security property) lands first** with green checkpoints throughout.

Load-bearing decisions (see `specs/004-kernel-pack-boundary/research.md` R1–R12):
- **Confirmation is kernel-derived from `action_class`** (write_execute ⇒ confirm), never a pack-declared flag — the pack has no lever to skip the OOB gate.
- Pack callables get a narrow `PackContext`, not the loop (least privilege).
- `AgentAction.finding` → opaque `dict` keeps the model JSON wire-shape unchanged → behavior-preserving.
- `Principal` relocates to a kernel module (kills the memory→audit coupling — it was just a mislocated generic type); `AuditSession` factors into a kernel `Session` protocol + audit extension.
- Confirmed while reading the code: `context.py`'s `AuditSession` import was a *dead* type hint; the real audit-policy bleed into the kernel is in `guardrails/escalation.py` (triggers #3–#7) and `orchestrator/{loop,action}.py`.

### Phase 5 — Spec 005: experiential knowledge loop
Capture-always → reactive candidate queue (`sr-agent lessons` list/show/approve/dismiss, mirroring `sr-agent confirm`) → human command promotes → embed (HMAC-signed; pack content) → retrieve-at-build as **suggestion, not control** (v1). Dedup by error-signature to keep the human queue low-noise. Mechanism = kernel; content = pack. Depends on Phase 4 + solid memory/knowledge subsystem.

## Ready knowledge-base entries (pending human command)
Two gotchas the human has already confirmed reproducible — the seed entries for Phase 5's store:
1. **Foundry test discovery** — `forge test` only discovers tests under the configured `test` dir; PoCs in `audit/poc/` need `FOUNDRY_TEST`/profile or they're never compiled ("No tests to run"). Keep `via_ir=true`.
2. **Local model latency** — `qwen2.5-coder:3b` ≈ 8 min/PoC on this hardware; set generation timeout ≥600s; prefer relay for real PoC drafts.

## Current focus (2026-07): validate PoC-writing workability
Before implementing Phase 4, test whether the agent can draft a proof-of-code for **all** findings in the pashov audit report (`<strata-bb>/audit/contracts-pashov-ai-audit-report-*.md`). Include ALL findings — no prefiltering (a prior audit missed a vuln from exactly that assumption). This exercises the `write_poc`→`run_tests` path (feature 003 `execute_confirmed`, Foundry `audit/poc/` profile) end-to-end on real contracts.

## Open questions (deferred, not blocking)
- Pack interface exact shape — **RESOLVED** in Spec 004 (Target A; `CapabilityPack` frozen dataclass + `PackContext`, see research.md).
- PoC-drafting default: relay vs local (evidence leans relay for real drafts; the workability test above will add data).
- Disposition of the current 22-item PoC batch (rerun slow vs park) — folded into the workability test.
- Reactive-queue vs inline-in-chat surfacing for Phase 5 (leaning: reactive queue core, inline later).

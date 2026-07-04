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
**Status: CORE DONE (commit `c7e43be`, pushed).** The full kernel↔pack separation landed: SC-001 (boundary check = 0) ✅, US2 (hostile-pack security property) ✅, and **no kernel file imports any audit model or any `packs` module** — kernel is genuinely task-agnostic. The atomic block (loop inversion + `AUDIT_PACK` assembly) is done; audit lives entirely under `sr_agent/packs/audit/`. Suite green (210 unit+security+arch, 68 integration non-live; only environmental `mythril_live` excluded).

**What's left (all optional / boundary-clean, none block SC-001):**
- **US3**: H4 (MI harness ASR 0 with the real AUDIT_PACK) + a before/after behavioral-equivalence spot-check.
- **US4**: promote `contracts/pack-interface.md` → repo docs + reviewer checklist; update the architecture diagram.
- **Cosmetic follow-ups** (kernel-located audit *names*, not import violations): `ActionType`→pack (needs generic `Action.action_type: str`), `_validate_params`→pack, registry split (T018), `AgentAction.finding`→opaque dict (T007).
- **Known env issue** (not a regression): `test_mythril_live` times out on this 4-core box under Docker load.

Design locked to **Target A (full seam)**: introduce one declarative `CapabilityPack` the kernel consumes by injection; relocate audit-specifics under `sr_agent/packs/audit/`; enforce the boundary with a directory-based import check (`no kernel module imports sr_agent.packs` → 0). One pack, no dynamic registry (wired explicitly in `cli.py`; YAGNI). 35 tasks, 7 phases, sequenced so **US2 (the "a pack cannot lower a guardrail" security property) lands first** with green checkpoints throughout.

Load-bearing decisions (see `specs/004-kernel-pack-boundary/research.md` R1–R12):
- **Confirmation is kernel-derived from `action_class`** (write_execute ⇒ confirm), never a pack-declared flag — the pack has no lever to skip the OOB gate.
- Pack callables get a narrow `PackContext`, not the loop (least privilege).
- `AgentAction.finding` → opaque `dict` keeps the model JSON wire-shape unchanged → behavior-preserving.
- `Principal` relocates to a kernel module (kills the memory→audit coupling — it was just a mislocated generic type); `AuditSession` factors into a kernel `Session` protocol + audit extension.
- Confirmed while reading the code: `context.py`'s `AuditSession` import was a *dead* type hint; the real audit-policy bleed into the kernel is in `guardrails/escalation.py` (triggers #3–#7) and `orchestrator/{loop,action}.py`.

### Phase 5 — operator frontend (`specs/005-operator-frontend`) — **SHIPPED**
> Number note: the `005` slot was taken by this operator frontend (built ad hoc after Phase 4). The *experiential knowledge loop* originally sketched as "Spec 005" is now a future spec (see Phase 6 below) — same concept, later number.

**Status: SHIPPED on branch `005-operator-frontend`** (commits `5d2c42d` docs → `3fd5b1a` backend → `25c55e9` SPA+docker → `4eb9575` contract test → `77363db` domain panels). **26/32 tasks; 226 passed; SPA builds clean; svelte-check 0.**

A single-operator web console — a **second composition root** over the kernel + `AUDIT_PACK` (imports them directly like `cli.py`, not a fork): FastAPI backend + Svelte SPA. Delivered:
- **US1** — start a folder-bound session, drive turns (`loop.run_turn`), watch the ReAct steps stream over a WebSocket live trace.
- **US2 (security)** — the FR-009 **deliberate two-step** confirmation gate: a `confirm_token` issued only on fetching an action's notice, one-shot; approval routes through the SAME kernel `resolve_confirmation` as `sr-agent confirm`. No reflexive click / no auto-approve. Proven by `tests/frontend/test_approval_gate.py` (G1–G4).
- **US6** — set the reasoning endpoint (localhost / cloud-GPU tunnel) + model + an EXPLICIT `local|paid` selector + optional write-only paid key + a warm button (ready vs reachable). Paid backend is never a silent fallback. Proven by `test_no_paid_api.py`.
- **US5** — health (ready vs available), active pack + tools + the kernel invariants a pack cannot weaken, and **pack-contributed domain panels** (`GET /api/domain/panels` → audit findings/PoC roadmap, tagged by pack; generic surface stays pack-agnostic — SC-008).
- **US3** — read-only HMAC memory browser (tier-tagged, no edit/delete).

**One additive kernel change:** an optional, observability-only `event_sink` on `OrchestratorLoop` (feeds the live trace) — `None`-safe, swallows its own exceptions, cannot change control flow or any invariant; existing suite stays green.

**Deferred (6 tasks, none block the milestone):**
- **US4 provenance** (T024–26): `GET /api/session/{id}/context` + Provenance/Escalation panels. Deferred because it needs a small **kernel-state addition** (persist the last turn's DATA-wrapped blocks) — weigh against the "004 additive-observability-only" line. Trust tiers are already visible in the LiveTrace / Memory / System panels.
- **US3 audit trail** (T022–23): `GET /api/audit` + AuditTrail panel — a time-ordered re-projection of append-only memory; largely duplicates the shipped Memory panel.
- **T031**: `docker build` + `docker compose up` end-to-end run-through (needs the operator's docker daemon; the SPA build + backend-serves-`dist/` were verified locally).

### Phase 6 — experiential knowledge loop (future spec)
Capture-always → reactive candidate queue (`sr-agent lessons` list/show/approve/dismiss, mirroring `sr-agent confirm`) → human command promotes → embed (HMAC-signed; pack content) → retrieve-at-build as **suggestion, not control** (v1). Dedup by error-signature to keep the human queue low-noise. Mechanism = kernel; content = pack. Depends on Phase 4 + solid memory/knowledge subsystem. (The ready knowledge-base entries below seed this.)

## Ready knowledge-base entries (pending human command)
Gotchas the human has confirmed reproducible — seed entries for Phase 5's store:
1. **Foundry test discovery** — `forge test` only discovers tests under the configured `test` dir; PoCs in `audit/poc/` need `FOUNDRY_TEST`/profile or they're never compiled ("No tests to run"). Keep `via_ir=true`.
2. **Local model latency** — `qwen2.5-coder:3b` ≈ 8 min/PoC on this hardware; set generation timeout ≥600s; prefer relay for real PoC drafts. (Superseded by #4 below for real workloads — CPU-only local inference on this hardware is not viable at all, not just slow.)
3. **`ghcr.io/foundry-rs/foundry:latest` has `ENTRYPOINT=["/bin/sh","-c"]`.** Passing a command as an argv list (`["sh","-c","forge test ..."]`) double-wraps under the image's own `sh -c` and the real command is silently swallowed — the container exits 0 with empty stdout/stderr, and `run_tests` misread this as `passed`. **Root-caused 2026-07-02** during the PoC-workability test (H-01/H-02 "passed" with 0 real forge output). Fix: build the command as a single string for this image, not an argv list. Any code invoking Docker images with a shell-form entrypoint must pass a single command string, not argv.
4. **Local CPU-only Ollama (Docker, no GPU) is not viable for 7b interactive work on modest hardware** (measured: 4-core Intel i5, no CUDA/Metal path — Docker Desktop on macOS cannot pass through the integrated GPU either). A single generate call exceeded 30 minutes and was still incomplete. **Fix that worked**: free Colab T4 + Ollama + a `cloudflared` quick tunnel, `LocalClient(host=<tunnel-url>)` — measured 40 tok/s decode (vs 5.4 tok/s CPU-only) once the image's GPU detection succeeded. **Gotcha within the gotcha**: Ollama's installer only auto-detects the GPU if `pciutils` (`lspci`) is present; without it, Ollama silently falls back to CPU even on a CUDA-capable box. Install `pciutils` (`apt-get install -y pciutils`) BEFORE the first `ollama serve`, or restart `ollama serve` after installing it — GPU detection happens at server start, not lazily.
5. **PoC drafts written blind (from title/location/description alone, without reading the target source) invent nonexistent contract API** — confirmed 2026-07-02: `qwen2.5-coder:7b` invented `SharesCooldown.lockShares()`/`.cancel()` and `UnstakeCooldown.requestUnstake()`, none of which exist on the real contracts. A PoC-drafting prompt MUST include the actual source of the file(s) in `location` (agent reads it first), not just the finding's natural-language description.
6. **`forge`'s `--offline` flag is not respected when combined with `--use`** — [foundry-rs/foundry#2412](https://github.com/foundry-rs/foundry/issues/2412) (confirmed upstream bug, matches what we hit 2026-07-02: `forge test --use 0.8.28` still phoned home to `binaries.soliditylang.org/linux-amd64/list.json` under `--network none`, even against an image where solc had already been compiled once with network access). `--offline` MUST be passed WITHOUT `--use` to actually suppress the network call; forge then auto-detects the solc version from pragma and only refuses if that version genuinely isn't cached. Also per Foundry docs, forge caches solc under `~/.svm` (container user's home, not `/root` — see gotcha re: non-root container users below) when `--offline` is absent.
7. **Non-root container users need cache paths at their real `$HOME`, and named Docker volumes are root-owned by default.** `ghcr.io/foundry-rs/foundry` runs as `foundry` (uid 1000, `HOME=/home/foundry`), not root — mounting a cache volume at `/root/...` silently misses every write. A `docker volume create` volume is root-owned; a non-root container user gets `Permission denied` writing to it unless explicitly `chown -R <uid>:<gid>` from a `--user root` container first. General lesson: verify the actual container user (`whoami`/`id`/`env | grep HOME`) before mounting a cache at a guessed path.
8. **Baking a "warm cache" into a Docker image via `COPY . /image` + a build tool with a staleness-skip heuristic (like `forge build`) can silently no-op** if the copied directory already contains prior build artifacts (`cache_forge/`, `out/` from a host build) — the tool sees "up to date" and skips the real work (including the network fetch meant to be baked in). A suspiciously fast `RUN` step (single-digit seconds where tens/hundreds were expected) is a red flag, not a success signal; force a clean rebuild (`forge clean && forge build --force`, or the tool's equivalent) inside the image. Relatedly, `RUN cmd || true` on a step whose entire purpose IS to succeed (e.g. "bake the compiler in") silently converts a real failure into a fake-successful layer — don't swallow errors on load-bearing bake steps.
9. **A Docker image's *default* runtime `USER` matters even when a build step temporarily switches to `root`** — if a Dockerfile ends on `USER root` (e.g. to `chown` something mid-build), every `docker run` on the final image defaults to root unless `--user` is passed explicitly, so runtime code sees `$HOME=/root` even though the image's real working user (and its cached files, e.g. solc under `~/.svm`) is some other uid. Confirmed 2026-07-02: `docker/Dockerfile.foundry` baked solc successfully at build time under `foundry`'s home, but ended the Dockerfile on `USER root`, so every PoC run at runtime looked in the wrong `$HOME` and reported "no compiler versions available" despite the binary genuinely being cached in the image. Fix: end a Dockerfile on the user you want containers to run as by default.
10. **`forge --offline` is genuinely the right flag for a network-isolated sandbox, but only when NOT combined with `--use`** (confirmed upstream bug, [foundry-rs/foundry#2412](https://github.com/foundry-rs/foundry/issues/2412) — `--offline` is silently ignored when `--use` is also passed, so the command still phones home). Also: a pragma caret range (`^0.8.28`) resolves at *build* time to whatever the *latest* matching release was then (e.g. `0.8.35`, not `0.8.28`) — if you later pass `--use 0.8.28` expecting that to match the cached version, it won't, and forge tries to fetch the literal (uncached) 0.8.28 instead. Omit `--use` entirely and let `--offline` auto-detect from pragma against whatever's actually cached.
11. **A free `cloudflared` "quick tunnel" (`trycloudflare.com`) has an idle-connection timeout of roughly 60–100s** (confirmed via community reports, not official docs — cloudflared's HTTP/2 origin connection idle-timeout and common-proxy 524 boundaries both cited around this range). An Ollama call made with `stream: false` sends the client **zero bytes** until the entire generation finishes — from the tunnel's point of view that's one long idle period, and on a slow model/long output it gets cut mid-generation. The client then reads a truncated-but-still-JSON-parseable partial response (`done: false`, no `done_reason`) and silently treats it as real output — root-caused 2026-07-02 via directly probing Ollama through the tunnel and observing `done: False` on a cut-short `SharesCooldown` PoC draft. **Fix**: use `stream: true` (NDJSON) through any tunnel/proxy — continuous byte flow reads as "not idle" and avoids the cutoff; the client must reassemble the streamed chunks itself instead of reading one final JSON object.

## Current focus (2026-07)
Phase 4 (kernel↔pack boundary) and Phase 5 (operator frontend) have both landed. Two open threads:

**(paused) Validate PoC-writing workability** — test whether the LOCAL-MODEL agent can draft a proof-of-code for **all** findings in the pashov audit report (`<strata-bb>/audit/contracts-pashov-ai-audit-report-*.md`), composing its own detection+PoC task list. Include ALL findings — no prefiltering (a prior audit missed a vuln from exactly that assumption). Exercises the `write_poc`→`run_tests` path end-to-end on real contracts. Blocked on hardware (needs a fresh Colab T4 + cloudflared tunnel); next lever = `forge -vvvv` + grounding (transitive imports / few-shot from existing repo PoCs). Infra gotchas #3–#11 below were all found here.

**(optional) Frontend remainder** — the 6 deferred Phase-5 tasks (US4 provenance, US3 audit trail, T031 docker run-through) — see Phase 5.

## Open questions (deferred, not blocking)
- Pack interface exact shape — **RESOLVED** in Spec 004 (Target A; `CapabilityPack` frozen dataclass + `PackContext`, see research.md).
- PoC-drafting default: relay vs local (evidence leans relay for real drafts; the workability test above will add data).
- Disposition of the current 22-item PoC batch (rerun slow vs park) — folded into the workability test.
- Reactive-queue vs inline-in-chat surfacing for Phase 5 (leaning: reactive queue core, inline later).

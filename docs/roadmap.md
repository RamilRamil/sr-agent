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

### Phase 6 — experiential knowledge loop — **v1 LANDED as spec 014**
Capture-always → reactive candidate queue (`sr-agent lessons` list/show/approve/dismiss/add, mirroring `sr-agent confirm`) → human command promotes → embed (HMAC-signed; pack content) → retrieve-at-build as **suggestion, not control** (v1). Dedup by error-signature to keep the human queue low-noise. Mechanism = kernel; content = pack. Depends on Phase 4 + solid memory/knowledge subsystem.

**Shipped (spec 014):** `sr_agent/memory/lessons.py` (the kernel mechanism — `LessonStore`: capture/dedup, out-of-band-only `promote` + HMAC sign, `verify`, category-scoped `retrieve`); a `sr-agent lessons` CLI (the ONLY promoter — the agent has no promote path, pinned by `tests/architecture/test_lessons_promote_gate.py`); two harness hooks in `scripts/poc_queue_runner.py` (best-effort capture on a resolved-error-signature transition; DATA-wrapped retrieval into `draft()`/`fix()`, inert when the corpus is empty). **C1 (constitution reconciliation):** a promoted lesson keeps an immutable `origin=llm_inference` (honest audit) and gains `authorization=human_input` on promotion (Principle IV) — authorization governs KB membership, retrieval DATA-wraps regardless of tier (Principle I), so a lesson can never act as an instruction. Reuses `memory/hmac.py` + `KnowledgeBase`; no new dependency; 18 offline tests. The 13 gotchas ship as candidate proposals ([specs/014/seed-lessons.jsonl](../specs/014-experiential-knowledge-loop/seed-lessons.jsonl)) for the operator to `add`+`approve` under their own key (never pre-signed with a dev key). **v2 deferred:** the audit `OrchestratorLoop` as a second capture producer; retrieval into the audit-analysis prompt; free-form (non-signature-keyed) lessons.

### Live-run harness robustness — **LANDED as spec 015**
The first live H-01 run with the knowledge loop armed (qwen3-coder:30b on 2×T4, marker protocol) reached a real, non-empty PoC that targeted the right mechanism (deploys `ERC20Cooldown`, calls `setVaultExitBounds` + `cancel`) and iterated on real compile errors — then `exhausted`, surfacing three robustness bugs that spec 015 fixes (all in `scripts/poc_queue_runner.py` + a helper in `scripts/solidity_index.py`; no kernel-invariant change; 23 offline tests):
- **US1 — clean-Solidity extraction.** `_strip_fences` only stripped a leading/trailing fence; when the model prepends chain-of-thought prose it landed verbatim in the `.sol` (`Error (2314): Expected ';'`), and in tool mode the reply was code-free (empty `.sol` → vacuous pass). New `_extract_solidity` takes the span from the first Solidity token to the last brace; a code-free reply is a **failed draft** (no empty/prose file), and a tool round-trip that yields no Solidity **falls back to the marker protocol**.
- **US2 — struct fields grounded up front.** Research correction (R2): the on-demand lookup already returns struct fields — the model just constructs the struct on attempt 1 before it looks up, inventing a 3-field `TExitUpperBounds` that actually has 5 (`p0,p1,TExitParams r0/r1/r2`). New `expand_referenced_types` proactively injects the field lists of struct/enum types the `callable_api` references (one level of nesting) into the draft grounding.
- **US3 — compile-gated capture.** The spec-014 capture fired on any error-signature change, so a **regression** into prose-in-`.sol` (a new `Expected ';'`) made the real errors "disappear" and captured a false-positive lesson (`1de2c917`, correctly quarantined by the human gate). Capture now requires a genuinely-better verdict (`compiled`/`real_pass`), never a lateral/regression change.

**Live-run gotchas recorded (infra, this session):** #14 a model that doesn't fit VRAM → CPU-offload → slow decode → cloudflared **524** on long generations (check `ollama ps` = 100% GPU; `pciutils`+`zstd` before `ollama serve` — see [scripts/gpu_box_bootstrap.sh](../scripts/gpu_box_bootstrap.sh)); #15 native tool-calling on qwen3-coder:30b → empty PoCs (use `--lookup-protocol marker`); #16 the PoC sandbox needs a **solc-baked image** (`--image sr-agent-foundry:strata-bb`) or every compile fails "no compiler versions available" offline. **H-01 still not converged** — its deeper blocker (auto-scaffold doesn't deploy `SharesCooldown`; spec-011 synthesis fails on a `_synth/…` import path) is out of scope, deferred.

### Nested-type import determinism — **LANDED as spec 016**
The spec-015 re-run of H-01 was a decisive step (clean PoCs, `defects=0`, right mechanism, zero false captures) but stalled 6× on one error: the model **named-imports** struct/enum types declared *inside* an interface (`import { TExitUpperBounds, TExitParams } from ".../ISharesCooldown.sol";` → `Error 2904`) and **uses them bare** in the body — even while correctly writing `ISharesCooldown.TCancelGuard` elsewhere. **Key finding (verified by probing `retrieve()`):** the knowledge loop surfaced exactly the right lesson (#12, nested-type import) as the top DATA block in *both* draft and fix prompts — and the 30B model still didn't obey it. So the conclusion, and this spec's thesis: **for a mechanical, index-detectable mistake, deterministic repair must back the suggestion-only loop.** Spec 016 adds three index-driven layers (all in `scripts/poc_queue_runner.py` + `scripts/solidity_index.py`; no kernel/loop change; 25 offline tests):
- **US1 — mechanical guard** `_fix_nested_type_imports` (mirrors `_fix_setup_override`/`_fix_import_paths`, runs post-draft + every fix): for any name the index knows is nested (`SymbolIndex.nested_container`), remove the named-import, ensure the container is imported, **and rewrite the type's bare uses to `Container.Type`** (required — the model uses them bare; verified against the real PoC). Model-independent, idempotent, strict determinism boundary (only unambiguously-nested names touched — a `/speckit-analyze` HIGH finding caught that fixing only the import would trade Error 2904 for `undefined identifier`).
- **US2 — grounding note** in `expand_referenced_types`: a nested type's fields now come with the canonical "import the container, use `Container.Type`, don't named-import" note, up front.
- **US3 — authoritative hint**: `_targeted_hints` gains a 2904 rule (index-driven) — nested → the exact `Container.Type` fix; unknown name → nothing.

**Known index limitation (pre-existing, noted):** file-level (top-level) structs/enums are not indexed (`_index_file` walks only contract/interface bodies), so `nested_container`'s top-level-collision exclusion is defensive/future-proof rather than exercised today. **H-01 still blocked past this** by the deferred scaffold/synthesis issue (SharesCooldown not deployed).

### Code-comprehension graph for our OWN code — **LANDED as spec 017**
A dev/navigation tool (`scripts/codegraph.py`, new; 17 offline tests) that builds a deterministic cross-file map of **our own** codebases (the agent repo + the framework project) and answers structural questions — callers/callees, module deps, symbol definition, shortest path — with **no LLM and no network**. It wraps `graphify` (tree-sitter AST → node-link `graph.json`) as an isolated subprocess and parses the JSON with a stdlib-only `CodeGraph` query layer. **Explicitly scoped away from the audit target and the model path:**
- **graphify cannot parse Solidity** (verified: `.sol` absent from its `CODE_EXTENSIONS`, no solidity grammar/extractor). Audit-target grounding stays solely with `scripts/solidity_index.py`'s `SymbolIndex`. Echoes the earlier SmartGraphical-Universal result: such a graph did not help the local model on the target — so this is a tool for *us*, never model grounding and never an authorization input in the `SourceType` hierarchy (enforced by `tests/architecture/test_codegraph_isolation.py`: no `sr_agent/**` imports it; its query path imports no network/paid/graphify module).
- **Principle V held via `--code-only`.** graphify's code extraction is offline/no-key, but plain `graphify extract --no-viz` on a real repo (which has `.md`/`.txt`) still routes those docs through its key-requiring semantic path and errors. The fix — **caught by the quickstart smoke, not by the first pure-`.py` bench** — is `graphify extract <root> --code-only --no-viz`, which confines extraction to the local AST. graphify is a **dev/optional tool** (`uv tool install graphifyy`), never a project dependency; the core agent runs and tests-pass with it absent.
- **Gotcha #14 (build-tool offline flag masks a doc-path key requirement):** a code-graph/index tool that claims "local, no key" may still demand an API key the moment the corpus contains non-code files, because its *document* path differs from its *code* path. Always pass the explicit code-only flag AND smoke-test on a real (mixed-content) repo, not just a synthetic code-only sample — the synthetic sample hides the doc-path branch entirely.

## Ready knowledge-base entries (pending human command)
Gotchas the human has confirmed reproducible — seed entries for Phase 5's store:
1. **Foundry test discovery** — `forge test` only discovers tests under the configured `test` dir; PoCs in `audit/poc/` need `FOUNDRY_TEST`/profile or they're never compiled ("No tests to run"). Keep `via_ir=true`.
2. **Local model latency** — `qwen2.5-coder:3b` ≈ 8 min/PoC on this hardware; set generation timeout ≥600s; prefer relay for real PoC drafts. (Superseded by #4 below for real workloads — CPU-only local inference on this hardware is not viable at all, not just slow.)
3. **`ghcr.io/foundry-rs/foundry:latest` has `ENTRYPOINT=["/bin/sh","-c"]`.** Passing a command as an argv list (`["sh","-c","forge test ..."]`) double-wraps under the image's own `sh -c` and the real command is silently swallowed — the container exits 0 with empty stdout/stderr, and `run_tests` misread this as `passed`. **Root-caused 2026-07-02** during the PoC-workability test (H-01/H-02 "passed" with 0 real forge output). Fix: build the command as a single string for this image, not an argv list. Any code invoking Docker images with a shell-form entrypoint must pass a single command string, not argv.
4. **Local CPU-only Ollama (Docker, no GPU) is not viable for 7b interactive work on modest hardware** (measured: 4-core Intel i5, no CUDA/Metal path — Docker Desktop on macOS cannot pass through the integrated GPU either). A single generate call exceeded 30 minutes and was still incomplete. **Fix that worked**: free Colab T4 + Ollama + a `cloudflared` quick tunnel, `LocalClient(host=<tunnel-url>)` — measured 40 tok/s decode (vs 5.4 tok/s CPU-only) once the image's GPU detection succeeded. **Gotcha within the gotcha**: Ollama's installer only auto-detects the GPU if `pciutils` (`lspci`) is present; without it, Ollama silently falls back to CPU even on a CUDA-capable box. Install `pciutils` (`apt-get install -y pciutils`) BEFORE the first `ollama serve`, or restart `ollama serve` after installing it — GPU detection happens at server start, not lazily.
5. **PoC drafts written blind (from title/location/description alone, without reading the target source) invent nonexistent contract API** — confirmed 2026-07-02: `qwen2.5-coder:7b` invented contract methods that don't exist on the real target (drafting blind from the finding's prose alone). A PoC-drafting prompt MUST include the actual source of the file(s) in `location` (agent reads it first), not just the finding's natural-language description.
6. **`forge`'s `--offline` flag is not respected when combined with `--use`** — [foundry-rs/foundry#2412](https://github.com/foundry-rs/foundry/issues/2412) (confirmed upstream bug, matches what we hit 2026-07-02: `forge test --use 0.8.28` still phoned home to `binaries.soliditylang.org/linux-amd64/list.json` under `--network none`, even against an image where solc had already been compiled once with network access). `--offline` MUST be passed WITHOUT `--use` to actually suppress the network call; forge then auto-detects the solc version from pragma and only refuses if that version genuinely isn't cached. Also per Foundry docs, forge caches solc under `~/.svm` (container user's home, not `/root` — see gotcha re: non-root container users below) when `--offline` is absent.
7. **Non-root container users need cache paths at their real `$HOME`, and named Docker volumes are root-owned by default.** `ghcr.io/foundry-rs/foundry` runs as `foundry` (uid 1000, `HOME=/home/foundry`), not root — mounting a cache volume at `/root/...` silently misses every write. A `docker volume create` volume is root-owned; a non-root container user gets `Permission denied` writing to it unless explicitly `chown -R <uid>:<gid>` from a `--user root` container first. General lesson: verify the actual container user (`whoami`/`id`/`env | grep HOME`) before mounting a cache at a guessed path.
8. **Baking a "warm cache" into a Docker image via `COPY . /image` + a build tool with a staleness-skip heuristic (like `forge build`) can silently no-op** if the copied directory already contains prior build artifacts (`cache_forge/`, `out/` from a host build) — the tool sees "up to date" and skips the real work (including the network fetch meant to be baked in). A suspiciously fast `RUN` step (single-digit seconds where tens/hundreds were expected) is a red flag, not a success signal; force a clean rebuild (`forge clean && forge build --force`, or the tool's equivalent) inside the image. Relatedly, `RUN cmd || true` on a step whose entire purpose IS to succeed (e.g. "bake the compiler in") silently converts a real failure into a fake-successful layer — don't swallow errors on load-bearing bake steps.
9. **A Docker image's *default* runtime `USER` matters even when a build step temporarily switches to `root`** — if a Dockerfile ends on `USER root` (e.g. to `chown` something mid-build), every `docker run` on the final image defaults to root unless `--user` is passed explicitly, so runtime code sees `$HOME=/root` even though the image's real working user (and its cached files, e.g. solc under `~/.svm`) is some other uid. Confirmed 2026-07-02: `docker/Dockerfile.foundry` baked solc successfully at build time under `foundry`'s home, but ended the Dockerfile on `USER root`, so every PoC run at runtime looked in the wrong `$HOME` and reported "no compiler versions available" despite the binary genuinely being cached in the image. Fix: end a Dockerfile on the user you want containers to run as by default.
10. **`forge --offline` is genuinely the right flag for a network-isolated sandbox, but only when NOT combined with `--use`** (confirmed upstream bug, [foundry-rs/foundry#2412](https://github.com/foundry-rs/foundry/issues/2412) — `--offline` is silently ignored when `--use` is also passed, so the command still phones home). Also: a pragma caret range (`^0.8.28`) resolves at *build* time to whatever the *latest* matching release was then (e.g. `0.8.35`, not `0.8.28`) — if you later pass `--use 0.8.28` expecting that to match the cached version, it won't, and forge tries to fetch the literal (uncached) 0.8.28 instead. Omit `--use` entirely and let `--offline` auto-detect from pragma against whatever's actually cached.
11. **A free `cloudflared` "quick tunnel" (`trycloudflare.com`) has an idle-connection timeout of roughly 60–100s** (confirmed via community reports, not official docs — cloudflared's HTTP/2 origin connection idle-timeout and common-proxy 524 boundaries both cited around this range). An Ollama call made with `stream: false` sends the client **zero bytes** until the entire generation finishes — from the tunnel's point of view that's one long idle period, and on a slow model/long output it gets cut mid-generation. The client then reads a truncated-but-still-JSON-parseable partial response (`done: false`, no `done_reason`) and silently treats it as real output — root-caused 2026-07-02 via directly probing Ollama through the tunnel and observing `done: False` on a cut-short PoC draft. **Fix**: use `stream: true` (NDJSON) through any tunnel/proxy — continuous byte flow reads as "not idle" and avoids the cutoff; the client must reassemble the streamed chunks itself instead of reading one final JSON object. The same fix was later needed for `LocalClient.warm()` too (2026-07-06) — it had its own separate `stream: false` call that hit the identical cutoff on a cold model's first load; a failed first `warm()` reliably succeeded on immediate retry because the model finished loading server-side despite the client losing visibility. General lesson: audit EVERY call site to a tunneled endpoint for this, not just the one you first noticed it on.
12. **A struct or enum declared INSIDE a contract/interface is not a top-level Solidity declaration and cannot be a named-import target** — `import { TExitParams } from "ISharesCooldown.sol";` fails to compile (`Error (2904): Declaration "TExitParams" not found in ...`) even though `TExitParams` genuinely exists in that file, because it's nested inside the `ISharesCooldown` interface body. Confirmed 2026-07-05 on a live local-model PoC-drafting run: an AST-backed symbol lookup correctly resolved the struct and told the model which contract it belongs to, but the model still wrote an invalid direct named import for it. **Fix**: import the containing contract/interface itself and reference the nested type as `Contract.TypeName`; when building any tool that hands a model "here's where symbol X lives," explicitly flag nested types as needing dot-qualification, not a named import — the containing-contract name alone doesn't make this obvious to a small local model.
13. **A shared character/token budget consumed by iterating over several "target" items in priority order silently starves later items entirely if an earlier item's own content (plus its transitive dependencies) is large enough** — general pattern, not project-specific. Confirmed 2026-07-05 in `scripts/poc_queue_runner.py`'s `build_callable_api`: a finding's `location` named two contracts (`StrataCDO`, then `SharesCooldown`); `StrataCDO`'s own signatures plus its resolved dependency chain consumed the entire 6000-char budget before `SharesCooldown` — the actual vulnerable contract — ever got a turn, so the exploit's own required caller-permission (`onlyUser(user)` on `cancel()`) never reached the model in three separate live-testing runs. Even after giving each named item its own budget share, the specific function actually referenced (`cancel`) could still be truncated out by OTHER functions in the same file if they happened to be declared first in source order. **Fix, two parts**: (a) split a shared budget per logical item instead of one pool consumed first-come-first-served; (b) within an item's own share, sort/prioritize whatever the caller most likely actually needs (a function name explicitly mentioned by the caller) ahead of everything else, so truncation drops the least-relevant content first, not whatever the source file happened to declare first. General lesson: any prompt-assembly loop with a shared truncation budget across multiple "important" things should be treated as a fairness bug waiting to happen until proven otherwise.

## Current focus (2026-07)
Phase 4 (kernel↔pack boundary) and Phase 5 (operator frontend) have both landed. Two open threads:

**PoC-writing workability — substantial progress, honestly re-verified (2026-07-05).**
The local model, driven by `scripts/poc_queue_runner.py`, composes its own finding list
from an external report (no prefiltering) and drafts a PoC per finding, exercising the
write_poc→run_tests path against real contracts in a Docker sandbox. Two **orthogonal
axes** had to be closed to get a PoC anywhere near compiling, each by a distinct lever:

1. **Signature/identifier precision** — the model invents "natural" names/methods
   (`IUnstakeCooldown`, `requestUnstake`) even when the real ones are in a source block.
   Closed by *authoritative grounding + deterministic repair*: honest git-tracked-only
   source → transitive dep interfaces → a **file map** (every real contract/interface +
   import path) → **callable_api** (real function signatures, later extended with
   explicit **CALLER REQUIREMENT** annotations for access-control modifiers) →
   **compiler-error-driven targeted repair** + **line-level signature hints** (resolve
   each forge error, including argument-type errors, against real signatures) + **stall
   detection** (escalate when a fix repeats the identical error/FAIL reason). Plus
   deterministic guards for mechanical errors (non-virtual `setUp` override → 4334;
   wrong import depth; bare SPDX line).
2. **Scaffold coverage** — the PoC can only use contracts the test base actually
   deploys. The contest's own base (`StrataProtocolDeploymentBase`) deploys
   cdo/tranches/unstake but NOT sharesCooldown. Closed (in **production mode** —
   generated/own infra is an accepted input here, unlike the honest-experiment mode) by
   inheriting a **complete deploy base** (operator-provided `--test-scaffold`) + a real
   worked **few-shot example** whose setup pattern the model copies.

**Correction to an earlier claim in this doc:** an initial pass reported "all 3 sampled
findings compiled" — **this was a false positive.** The compile-success detector
(`_compiled()`) was a *denylist* (`"Compiler run failed" not in output`); a genuine
compile failure worded differently (`Error: Encountered invalid solc version ...`,
caused by `docker/Dockerfile.foundry` baking solc for `src/` but not `test/`, so the
scaffold's own pinned `solidity 0.8.28` was never cached) slipped past it, and all 3
"successes" were actually silent compile failures. Both are now fixed (positive-signal
detector: `Ran \d+ tests?`; Dockerfile bakes `test/` too) — see
[specs/006-eval-verification-robustness](../specs/006-eval-verification-robustness/)
and [docs/eval-principles.md](eval-principles.md) for the general lesson and the audit
of every other check in this harness for the same failure mode.

**Path B (mainnet-fork execution) is now real and has produced genuine signal.** With
the detector fixed and `--fork` (network + `MAINNET_RPC_URL`) enabled, a
compiled-but-reverted PoC is no longer silently accepted as success (fork mode requires
an actual `passed` verdict). Focused runs on the hardest finding (H-01, SharesCooldown —
honestly deep-testing the fix cycle, not yet reproducing the bug) **did reach genuine
fork execution** (several attempts compiled and ran against real mainnet state) —
a first — but did not converge to a passing PoC within budget. Root-caused a further
grounding gap in the process: `callable_api` shows function signatures but never expands
the **fields of struct types** referenced in them (e.g. `TCancelGuard`, `TBalanceState`),
so the model invents plausible-sounding field names for structs it can't see inside of.
This is the motivating gap for **spec 007** (AST-backed grounding + an agentic
lookup protocol), which generalizes the fix instead of adding another one-off regex.

**Spec 007 live validation against H-01 (2026-07-05) — honest result: mechanism
fired, gap found and fixed, H-01 still not converged.** With
[specs/007-ast-grounded-poc-drafting](../specs/007-ast-grounded-poc-drafting/)'s
`SymbolIndex` + bounded `LOOKUP:` protocol wired into `draft()`/`fix()`, a
`--only H-01 --fork --lookup-budget 3` run produced the **first live use of the
lookup mechanism**: on a compile stall (attempts a3/a4), the model spontaneously
emitted `LOOKUP: ISharesCooldown.TCancelGuard`, `LOOKUP: ISharesCooldown.TExitParams`,
`LOOKUP: ISharesCooldown.TExitUpperBounds` — exactly the struct-field-blindness gap
spec 007 was built to close. All three resolved `resolved=False, matches=0`, which
looked at first like the mechanism doing nothing. Direct verification against the
real target project showed all three symbols **do exist** under their bare names
(1 match each) — the model queried in a qualified `Contract.Symbol` form that
`SymbolIndex.lookup()` (keyed on bare names only) didn't yet normalize. Fixed:
`lookup()` now falls back to the bare suffix when a qualified query misses
([scripts/solidity_index.py](../scripts/solidity_index.py), regression test
`test_qualified_name_falls_back_to_bare`). Recorded honestly per FR-007/SC-003 and
[[project_poc_vacuous_pass]]'s no-overclaiming discipline: the run itself still did
not converge to a passing H-01 PoC within budget (`EXHAUSTED` after 221s, same
outcome class as pre-lookup runs) — the deliverable proven here is that the
lookup protocol activates on a real, previously-undiscovered failure mode and that
the fix generalizes (any future qualified-name query now resolves), not a solved
H-01. **Follow-up runs (2026-07-05, same session) confirm the fix helped, then surface
the next distinct gap — recorded honestly, not chased further this round.** Two
more live `--only H-01 --fork --lookup-budget 3` runs:
- **Run 2** (qualified-name fix only): all lookups now resolved (`TExitUpperBounds`,
  `TExitParams`, `TRequest` — previously all `matches=0`), but the model still wrote
  an invalid `import { TExitParams } from ".../ISharesCooldown.sol";` for a struct
  declared *inside* that interface — a nested type isn't a top-level declaration,
  so this is invalid Solidity. All 3 attempts died on this one compile error.
  Fixed: `_render_lookup_response()` now adds an explicit NOTE for struct/enum
  matches with a non-empty `contract`, telling the model to import the container
  and reference `Contract.Name` instead
  ([scripts/poc_queue_runner.py](../scripts/poc_queue_runner.py)).
- **Run 3** (with that NOTE): attempt 1 hit the same import mistake once (against a
  different wrong file), but **attempt 2 got past it entirely** — genuine forward
  progress, not a repeat of the same stall. It then hit a *new, later-stage* error:
  `Member "setVaultExitBounds" not found ... in contract ERC20Cooldown`.
  Verified: `setVaultExitBounds` is a **real function**, but declared on
  `SharesCooldown`, not `ERC20Cooldown` — sibling contracts, both inherit
  `CooldownBase`, no relation to each other. The model called a real method on the
  **wrong deployed contract instance**. This is a different failure class from
  identifier/field invention — it's the "which instance" confusion already flagged
  as `mechanism_signal`'s known limitation — and is **out of spec 007's declared
  scope** (spec 007 targets invented identifiers, not instance selection). Attempts
  2 and 3 repeated this identical error; run exhausted (161.5s), quarantined.

**Honest conclusion for spec 007 (FR-007/SC-003):** the AST-grounded lookup +
qualified-name fallback + nested-type-import guidance measurably advanced H-01's
draft past two full compile-error classes it was previously stuck on, in the same
number of attempts (3) per run. H-01 itself still has not converged to a passing
PoC — the remaining blocker (wrong-instance method calls) is a distinct,
out-of-scope problem for a future iteration, not a lookup-mechanism gap. Three
Kaggle GPU sessions were spent on this validation thread; stopping here rather than
continuing to patch new gaps one-by-one, per the spec's own explicit stance that
convergence is not a completion condition.

**T020 done (2026-07-05, offline, no live model needed):** `build_file_manifest`/
`build_callable_api` re-platformed onto `SymbolIndex` (grammar-accurate, not regex),
falling back to the old regex scan under `--no-symbol-index`. Verified against the
real target: the AST path surfaces every real interface a multi-interface file
bundles under one misleading filename (e.g. `Interfaces.sol` hid `IAavePool`,
`IERC20Cooldown`, `IEulerVault` behind one filename entry) — a known trade-off, the
~4 files that fail to parse now drop out of the manifest entirely rather than
showing a possibly-wrong filename guess (same shape as research.md R8 elsewhere).

**Separately found and fixed while validating T020 against the real H-01 location
(not a T020 regression — reproduced byte-for-byte by the old regex path too):**
`build_callable_api` gave the WHOLE 6000-char budget to names in `location`
first-come-first-served. On `StrataCDO.coverage / ... + SharesCooldown.cancel`,
`StrataCDO`'s own signatures + dependency chain exhausted the entire budget before
`SharesCooldown` — the actual finding target — ever got a turn, so `cancel()`'s
`onlyUser(user)` CALLER REQUIREMENT never reached the model in any of the 3 live
runs above. Fixed in two parts: each name now gets its own budget share, and within
a file's share a function explicitly named in `location` (e.g. `cancel`) is
rendered first — needed because `cancel` is declared 3rd of 3 external functions in
`SharesCooldown.sol`, so per-name fairness alone still let it get truncated out.
This may well have been a real, silent contributor to H-01's non-convergence above:
the model was never shown the exact caller requirement for the function the
finding is about. Not yet re-validated live (would need a 4th Kaggle session);
5 new offline tests (`tests/unit/test_poc_queue_runner.py`) pin both fixes against
a synthetic fixture reproducing the exact failure shape.

**Spec 008 (2026-07-05, offline, no live model needed): native Ollama tool-calling
for the lookup mechanism, replacing spec 007's `LOOKUP:` text-marker convention
where the model/host supports it.** Spec 007's own research.md (R2) rejected
native tool-calling at the time, explicitly because support was "unverified for
these particular local builds," and closed with "revisit if the harness moves to
models/backends with verified, reliable tool-calling support." This session
verified exactly that (`qwen3-coder:30b` on Kaggle and both local
`qwen2.5-coder:7b`/`:3b` all report `"tools"` in `/api/tags` capabilities), so spec
008 fulfills that condition rather than reversing the earlier decision without new
evidence. Shipped: `LocalClient.supports_tools()`/`chat()`
([sr_agent/llm_core/local_client.py](../sr_agent/llm_core/local_client.py)), a
`lookup_symbol` tool schema + `_generate_with_tool_calls()` round-trip parallel to
spec 007's `_generate_with_lookups()`, and `_select_protocol()` implementing the
full auto/tool/marker decision table (`--lookup-protocol` CLI flag) —
[scripts/poc_queue_runner.py](../scripts/poc_queue_runner.py). Both protocols call
the SAME `_render_lookup_response()` for rendering, so byte-identical resolution
behavior across protocols (SC-002) holds by construction, not by two
implementations kept in sync by hand — verified in
`tests/unit/test_poc_queue_runner.py::test_tool_and_marker_protocols_render_lookup_identically`.
260/260 tests pass (8 new in `test_poc_queue_runner.py`, 5 new in
`test_local_client.py`). A live comparison against this session's H-01 baseline
(T017/T018, explicitly optional per FR-009) was NOT run this session — three
Kaggle GPU sessions were already spent validating spec 007's mechanism, and this
feature's own completion bar is the offline suite above, not a new live claim.
**What remains genuinely unverified**: whether the real Kaggle-hosted
`qwen3-coder:30b` build actually emits a structured `tool_calls` object during
live drafting, rather than writing the call as plain text despite the schema —
only a live run (T017/T018) can answer this. A local CPU-only probe CANNOT
substitute for that check even in principle (gotcha #4 below: local CPU-only
Ollama is not viable for interactive generation on this hardware at all, for
`/api/chat` same as `/api/generate`) — do not re-attempt one.

**T017/T018 done live (2026-07-06): native tool-calling confirmed working on
the real model, twice reaching genuine fork execution — AND a new, real
vacuous-pass gap found and fixed.** A live `--only H-01 --fork
--lookup-protocol tool` run against the real Kaggle-hosted `qwen3-coder:30b`
confirmed `message.tool_calls` genuinely fires (dozens of real symbol lookups
resolved across several runs: `ISharesCooldown`, `SharesCooldown`, `TRequest`,
`TExitParams`, `COOLDOWN_WORKER_ROLE`, …) — the open question from spec 008's
own research.md R3 is answered: yes, on real drafting turns, not just
scripted tests. Two real-text-leak formats were found and fixed live
(`<function=name>` then the Hermes/Qwen `<tool_call>` wrapper — see gotcha
#12 below). H-01 reached genuine `compiled_real: true` fork execution TWICE
across separate runs (once with `[FAIL: EvmError: Revert]` on the actual
exploit assertion, once — see below — with a structurally-clean `PASS` that
turned out to be a false positive).

**The false positive, found by actually reading the code, not the log
line:** one run reported `outcome: "passed", real_pass: true,
compiled_real: true, defects: []` — the first `real_pass: true` on H-01 all
session. Reading the actual PoC (`audit/poc/H_01.t.sol`) showed why this is
NOT a win: the model wrote `testRevertWhenRequestRedeemWithZeroShares()` — a
generic "does requestRedeem revert on zero shares" sanity check, with
**zero relation** to H-01's actual mechanism (same-block silo padding
shifting `coverage()` to self-select the exit tier, then reclaiming padding
via `cancel()`). The structural gate (`_poc_defects`) correctly found no
defects (real import, real assertion, no mock) because the test IS honest —
it's just not testing the right thing. `mechanism_signal()`'s own diagnostic
returned `{"checked": [], "called": []}` — silently useless — because that
run's non-deterministic extraction gave `location: "SharesCooldown.sol"` (a
bare filename, no method names), even though the identical finding's
`description` still explicitly named `coverage()`/`cancel()` in markdown code
spans. Fixed: `mechanism_signal()` now also derives candidates from
`description` via a precision-first backtick-code-span extractor
(`` `coverage()` `` → `coverage`, falling back to loose word-extraction only
if no code spans exist) — re-run against the false-positive PoC:
`{"checked": ["coverage", "cancel"], "called": []}`, correctly flagging it as
suspicious. Still diagnostic-only (not gated — same noise-risk rationale as
before), but no longer silently blind when location degrades. 2 new offline
tests, 266/266 full suite. **Honest status: H-01 has NOT actually passed** —
this session's best evidence remains "reaches real fork execution, exploit
assertion doesn't yet trigger the described bug," now with a corrected,
harder-to-fool diagnostic for next time.

**Two frames, kept distinct:** (a) the honest *experiment* ("can the model do it from
ONLY the target's original code?") — answered: it produces sophisticated
near-compiling PoCs even honestly; (b) the *production tool* ("auto-generate compiling,
correct PoCs") — not yet reached; this is the active thread.

**Open gap → correctness.** `compiled` ≠ *correctly reproduces the bug*: a PoC can
compile with real APIs yet muddle the mechanism (observed: an early H-02 draft deployed
`UnstakeCooldown` but called `sharesCooldown`'s version of a shared-interface method
instead). The structural gate can't judge this — path B (a real fork run) is the
objective check, and is now wired in. See [project_poc_vacuous_pass] memory. Infra
gotchas #3–#11 below were all found on this thread.

**Harness review + remediation (2026-07-06, step 1 landed).** A structured
code-review of the standalone PoC harness (`scripts/poc_queue_runner.py`, ~1750
lines) surfaced that its verdict-producing gates — the functions deciding
pass/fail/compiled/vacuous/stall — had **zero direct tests**, the exact place a bug
becomes a false milestone (spec 006 traces to a `_compiled` denylist bug caught only
in a live run), and that `main()`'s whole draft→run→fix loop had **no integration
test** (every bug this session surfaced only in a metered GPU run). Step 1 —
[specs/009-harness-verdict-tests](../specs/009-harness-verdict-tests/) — closes that:
direct offline tests for every verdict gate + deterministic repair helper (a
re-broken denylist `_compiled` now fails a test, SC-001); the per-finding loop
extracted (behavior-preserving) into `_process_finding` and driven end-to-end by an
offline fake-model + fake-sandbox integration test covering the five outcome paths
(`tests/integration/test_poc_runner_loop.py`) — loop-bug detection moved off Kaggle
onto local seconds; and `scaffold_missing_types` re-platformed onto an
inheritance-aware `SymbolIndex` (a state var provided via an inherited parent base is
no longer false-flagged as missing — the last regex-fragility class from the 007/008
arc). **Remaining review findings, deferred to their own specs** (ranked): (2)
automated independent PASS verification — mutation-style "would the assertion fail if
the described bug were patched?" turning `mechanism_signal` from a heuristic into a
real correctness gate (the deepest "do we trust a green run" question) — **LANDED as
spec 010**: a genuine PASS is now re-run against the finding's own fix applied to an
ephemeral source copy (real tree never touched); still passes on the fix →
`unverified_pass` (the exact 2026-07-06 false-positive class, now caught
automatically), fails on the fix → verified, no applicable/appliable fix →
`mutation_verify_unavailable` keeping `passed` (never a false downgrade). Fix diffs
are pulled deterministically from the report (not via the model, to keep them
byte-exact); applied with `git apply`/`patch`; all orchestration offline-tested
through spec 009's fake harness; (3) Stage 1 scaffold synthesis — **LANDED as spec
011**: when `scaffold_missing_types` flags that the auto-discovered base can't deploy a
contract a finding needs (the exact H-01 blocker — six live attempts burned on
`sharesCooldown` being undeclared), the harness now synthesizes a deploy-base that
declares+deploys it (via the harness's own model, no new paid-API dependency, grounded
in the missing contract's real source + the existing base as pattern),
COMPILE-validates it in the sandbox (a base that doesn't build is discarded — the
eval-robustness bar), and drafts under it on success; every failure path
(`no_output`/`no_build`/`infra`) falls back honestly to the prior scaffold with a
logged reason, never blocking the run, never using a non-compiling base; synthesized
bases live only in an untracked `audit/poc/_synth/` area (tracked source untouched),
and any resulting PASS is still spec-010 mutation-verified. 6 new offline tests
(`--no-scaffold-synthesis` off-switch; default on); (4) **harness prompt management** — the kernel/pack
prompts (`claude-react-system`, `stage2-local-analysis`, `AUDIT_CHAT_SYSTEM`) are
already under Langfuse Prompt Management (versioned, `production`-labelled, graceful
fallback, spec 001 T079), but the PoC-harness prompts (`EXTRACT_PROMPT`, `DRAFT_PROMPT`,
`FIX_PROMPT`, `EXPLOIT_QUALITY_CHECKLIST`, `_LOOKUP_MARKER_SUFFIX` in
`scripts/poc_queue_runner.py`) are raw inline constants — NOT versioned, NOT in
Langfuse, so this session's heavy prompt iteration (exploit-quality checklist, Proof
Explanation, tool-calling protocol) happened blind, with no prompt-version→trace
linkage even though `Tracer` is already wired into draft/fix. **LANDED as spec 012**:
the six harness prompts (`poc-extract`/`poc-draft`/`poc-fix`/`poc-exploit-checklist`/
`poc-lookup-marker`/`poc-synth-scaffold`) are now fetched via an additive
`Tracer.get_prompt_versioned(name, fallback)` (the existing `get_prompt` + its kernel
callers untouched), with the inline constant as the byte-exact fallback — so a
tracing-off run is identical to before (a KeyError from an edited version that dropped
a placeholder also falls back, never crashes); each draft/fix generation records
`prompt_provenance` (name+version, `null` on fallback) in its trace metadata; and a
best-effort `seed_prompts` pushes the constants to Langfuse (`production`, no-op when
disabled). Langfuse stays optional (constitution V). 11 new offline tests; (5) the 84
`datetime.utcnow()` deprecation warnings and more architecture invariants (harness
doesn't bypass sandbox; SourceType hierarchy) — **LANDED as spec 013**: all
`datetime.utcnow` usages in the kernel/pack removed for the tz-aware
`datetime.now(timezone.utc)` — the scope grew from 6 direct call sites to **11 across 8
files** once a bare-`utcnow` scan caught 5 `default_factory=datetime.utcnow` references
(pydantic model fields in `models/memory.py`, `models/chat.py`, `packs/audit/session.py`)
that emitted the same warning on instantiation; no test pins these fields' naive shape, so
tz-aware is behavior-safe (verified by escalating the `utcnow` warning to an error over the
previously-warning tests — 272 passed, 0 utcnow). Plus two new `tests/architecture/`
invariants: `test_source_type_hierarchy.py` pins the `SourceType` trust ordering Principle I
depends on (fails on a reorder), and `test_harness_sandbox_only.py` AST-asserts every direct
subprocess in `scripts/poc_queue_runner.py` is a benign diff/VCS tool (`git`/`patch`) — PoC/forge
execution must go through `run_tests`/`DockerSandbox` (fails if a direct `forge` exec is added).
**This completes the harness-review remediation arc (specs 006–013).**

**(optional) Frontend remainder** — the 6 deferred Phase-5 tasks (US4 provenance, US3 audit trail, T031 docker run-through) — see Phase 5.

## Open questions (deferred, not blocking)
- Pack interface exact shape — **RESOLVED** in Spec 004 (Target A; `CapabilityPack` frozen dataclass + `PackContext`, see research.md).
- PoC-drafting default: relay vs local (evidence leans relay for real drafts; the workability test above will add data).
- Disposition of the current 22-item PoC batch (rerun slow vs park) — folded into the workability test.
- Reactive-queue vs inline-in-chat surfacing for Phase 5 (leaning: reactive queue core, inline later).

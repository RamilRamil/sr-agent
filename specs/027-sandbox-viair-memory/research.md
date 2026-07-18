# Research: via_ir Compilation in the Harness Sandbox (spec 027)

Every decision grounded in the current code and in the captured spec-026 live-run artifact
(`solc exited with signal: 9 (SIGKILL)`), plus the clean-dir re-run (2/2 SIGKILL).

## Decision 1: Raise memory at the harness's construction site — no kernel change

**Finding**: `DockerSandbox.memory_limit` is a settable dataclass field (default `"512m"`). Three
construction sites:
- `scripts/poc_queue_runner.py:2668` → `DockerSandbox()` — the STANDALONE operator harness.
- `sr_agent/packs/audit/pipeline.py:92` → `DockerSandbox()` — the secure agent.
- `sr_agent/orchestrator/loop.py:94` → `DockerSandbox()` — the secure agent.

**Decision**: change ONLY the harness site to `DockerSandbox(memory_limit=<env-tunable>)`. The kernel
`DockerSandbox` class, its `512m` default, and both secure-agent sites are untouched.

**Rationale**: FR-003 + the security framing. Memory is a DoS knob, not an isolation invariant. The
harness is the looser operator context (it already opts into `network=bridge` for mainnet-fork PoC
runs — a far larger relaxation than more RAM). Scoping the raise to the one site keeps the secure
interactive agent tight and needs no kernel edit — the field already exists.

**Alternatives considered**: raising the class default — rejected (leaks into the secure agent,
weakens its posture); adding a per-call `memory` param to `run()` — rejected (touches the kernel
sandbox for no gain; construction-site config is enough).

## Decision 2: A small env-read helper with a calibrated default

**Decision**: add `_harness_sandbox()` in `poc_queue_runner.py` returning
`DockerSandbox(memory_limit=os.environ.get("SR_SANDBOX_MEMORY", <DEFAULT>))`. `main()` calls it in
place of the bare `DockerSandbox()`.

**Rationale**: FR-002 (env-tunable, no code edit to change) + FR-004 (calibrated default). A named
factory is also the seam US3's guard test calls directly (assert its `.memory_limit` > the kernel
default) without running `main()`.

**Default value**: start at a generous-but-reasonable `"6g"` — via_ir on a mid-size project (the
reference target has ~292 out artifacts) typically peaks in the low-single-digit GB; 6g gives clear
headroom above the 512m that was killed. Per FR-004 this is CONFIRMED empirically by the live
calibration (Decision 5): a cold build must survive at the default where it SIGKILLed at 512m; if the
host cannot grant 6g (Docker Desktop allocation), the operator tunes `SR_SANDBOX_MEMORY` down and the
calibration finds the smallest surviving value. The default errs generous because an under-set ceiling
silently reintroduces the OOM this feature exists to remove.

**Alternatives considered**: hardcoding a constant — rejected (FR-002, and different targets need
different amounts); an exhaustive live bisection to the byte — rejected as premature (a generous
default that provably survives is the correct first delivery; tightening is an env tweak).

## Decision 3: Reuse the build cache in the falsification copy

**Finding**: `scripts/poc_queue_runner.py:1682`
`_MUTVERIFY_COPY_SKIP = shutil.ignore_patterns("out", "cache_forge", ".git", "node_modules")`. The
copy omits BOTH forge cache dirs, so `mutation_verify`'s patched rebuild is always a COLD full via_ir
build — the most frequent cold-build site (one per passing proof) and, at 512m, an OOM; even raised,
a multi-minute cost each time.

**Decision**: drop `"out"` and `"cache_forge"` from the skip list; keep skipping `".git"` and
`"node_modules"`. forge then reuses the cache and recompiles only the fix's changed file(s) +
dependents.

**Rationale**: FR-005/FR-007. forge's cache is content-hash keyed (foundry.toml sets
`cache_path = 'cache_forge'`), so a file the fix changed is recompiled — a stale artifact is never
served (FR-007). Behavior is otherwise identical: still an ephemeral `tempfile.mkdtemp` copy, still
`_git_apply` the fix, still re-run the SAME PoC, still `shutil.rmtree` in `finally`, still never
touches the real tree (FR-006). Keeping `.git`/`node_modules` skipped avoids copying huge irrelevant
trees; `out`+`cache_forge` are worth their disk cost because they turn a minutes-long via_ir rebuild
into seconds.

**Alternatives considered**: include only `cache_forge` (not `out`) — rejected as fragile: forge may
rebuild artifacts if `out/` is absent even when the cache says unchanged; include both for a reliable
incremental build.

## Decision 4: The main loop warms via the rw mount — warm it once at the start

**Finding**: `run_tests` mounts the real project rw at `/work`, so a successful container compile
writes `out/`+`cache_forge/` back to the host project → subsequent runs are warm. Only the FIRST
build in a cold-cache state is a full via_ir build.

**Decision**: the harness (or the operator, documented) does ONE warm build at the start of a
run/batch so the first per-finding compile is not cold. Minimal: `main()` may trigger a single
`forge build` warm-up before the loop when the cache looks cold; at minimum this is documented as an
operator pre-step in quickstart (a host-side `forge build`, which has full memory).

**Rationale**: FR-008. Across an eval of C×N case-runs, paying one cold build instead of many is the
difference between minutes and hours. The mount already propagates the warm cache; we only need the
first build to happen once.

**Scope note**: the *reliable* fix is Decision 1 (a cold build must survive on its own merits); this
is a cost optimization on top. If warming is left to the operator (documented), the code change is
just Decisions 1–3; if automated, it is a single guarded warm-up call. Plan picks the documented
pre-step as the minimal, lowest-risk form, with the automated warm-up as an optional refinement.

## Decision 5: Calibration is a LIVE operator step, not a unit test

**Decision**: an explicit calibration/validation task runs a cold via_ir build of the reference target
at 512m (expect SIGKILL) vs the chosen default (expect success), then re-runs the finding that gave
2/2 SIGKILL to confirm it now compiles.

**Rationale**: FR-012/SC-001/SC-007. Offline unit tests cannot run a memory-heavy build (no model, no
container). The deterministic offline tests cover the SCOPING (harness raised, secure agent not) and
the COPY change; the memory value's sufficiency is inherently empirical and must be shown on real
hardware — the session's standing lesson (diagnose/verify from the artifact, don't assert).

## Test seam (offline, deterministic)

`tests/architecture/test_harness_sandbox_memory.py` (new): assert `_harness_sandbox().memory_limit`
parses to strictly more than the kernel default `DockerSandbox().memory_limit` (== "512m", unchanged),
and AST-check that `pipeline.py`/`loop.py` construct `DockerSandbox()` without a `memory_limit`
override (secure agent unraised, FR-003/FR-010). A `_MUTVERIFY_COPY_SKIP` test (unit) asserts the
patterns no longer include `cache_forge`/`out` but still include `.git`/`node_modules` (FR-005). No
model, container, or network.

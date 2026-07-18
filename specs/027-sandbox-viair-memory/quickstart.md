# Quickstart: via_ir-Viable Harness Sandbox (spec 027)

The workability harness compiles the target inside a memory-limited container. A target that builds
with `via_ir` needs several GB for a **cold** build — more than the 512 MB the sandbox used to cap it
at, so `solc` was OOM-killed (`signal: 9`). This feature raises the ceiling for the operator harness
(only), and makes the falsification rebuild reuse the build cache.

## 1. Set the memory ceiling (optional — a calibrated default applies)

```bash
export SR_SANDBOX_MEMORY=6g     # default is generous; tune to your target/host
```

- Applies ONLY to the standalone harness (`poc_queue_runner.py`). The secure interactive agent stays
  at 512 MB — its tighter posture is deliberate and unchanged.
- Requires your container runtime to be able to grant it (Docker Desktop → Resources → Memory ≥ this).
  If the host can't, the runtime says so directly; lower `SR_SANDBOX_MEMORY`.

## 2. Warm the cache once before a run/batch

forge's incremental cache lives in the target's `out/` + `cache_forge/`. A **cold** cache forces a
full via_ir rebuild every compile; a **warm** one recompiles only the tiny proof. The harness mounts
the project read-write, so the cache warms after the first successful build — but do the first one
with full host memory:

```bash
cd /path/to/target && forge build          # one host-side build, unlimited memory → warms the cache
```

Then an eval of C×N case-runs pays incremental builds, not a cold full build every time. (Any edit to
the target invalidates the cache — re-warm after touching sources, e.g. after a compile-check.)

## 3. Calibrate once (live — confirm the ceiling actually works)

Offline tests pin the *scoping* (harness raised, secure agent not) and the *copy* change. The memory
*value* is empirical — confirm it on real hardware:

```bash
# cold build at the OLD ceiling → expect SIGKILL
docker run --rm --network none --memory 512m -v "$PWD":/work -w /work <foundry-image> "forge build"
# cold build at the NEW ceiling → expect success
docker run --rm --network none --memory 6g   -v "$PWD":/work -w /work <foundry-image> "forge build"
```

Then re-run the finding that previously gave repeated kills and confirm it reaches the compiled stage.
If 6g still gets killed, raise it; if you want it tighter, lower until a cold build stops surviving —
that boundary is your calibrated value.

## What this does NOT touch

- The kernel sandbox default (512 MB) and the secure interactive agent — only the harness rises.
- The sandbox's security: `--network none` (opt-in bridge only for a mainnet-fork PoC), `--cap-drop
  ALL`, `no-new-privileges`, the process limit, ephemerality, and "PoCs run ONLY in the sandbox" are
  all unchanged. Memory is a denial-of-service knob, not isolation.
- What counts as compiled / passed / verified (specs 025/026).
- via_ir itself (the target requires it), or the extraction id-scheme fragility (a separate fix).

## Tests

```bash
pytest tests/architecture/test_harness_sandbox_memory.py \
       tests/architecture/test_harness_sandbox_only.py \
       tests/unit/test_poc_queue_runner.py -q
```

Offline. Pins: the harness sandbox is raised above the kernel default and the secure agent's is not;
the falsification copy no longer excludes the build cache; and no isolation invariant moved.

# Quickstart: Pin the Finding for the Proof-Eval (spec 028)

The proof-eval measures **proving**: given a known finding + its fix, can the harness produce a
verified proof? Extraction (report→tasks) is a DIFFERENT axis — and re-running it every case-run made
findings die at extraction (id mismatch) and drift the prover's input. This feature holds the finding
**constant**: the case carries it, and the harness is handed it directly.

## 1. Curate each case's finding (human ground truth)

The case manifest now carries the finding itself — transcribed from the published report, like the
operator fix and the discovery benchmark's labels:

`$SR_PROOF_ROOT/cases/strata-1/case.json`
```json
{ "case_id": "strata-1",
  "target_path": "/path/to/target/contracts",
  "report_path": "/path/to/report.md",
  "finding_id": "1",
  "title": "Same-block silo padding self-selects the exit tier",
  "location": "SharesCooldown.cancel / StrataCDO.coverage",
  "description": "A redeemer locks fee-free padding to shift coverage into the least-restrictive tier, then reclaims it via cancel() — no dwell check.",
  "fix_path": "/path/outside/repo/eval-fixes/1.patch" }
```

- `title`/`location`/`description` are **required** — a case missing any of them fails to load (loud),
  never a silent fall-back to nondeterministic model extraction.
- Everything stays **external** — targets, reports, findings, fixes are never committed.

## 2. Run the eval — the finding is now pinned

```bash
SR_PROOF_ROOT=~/sr-proof-eval GEMINI_API_KEY=… MAINNET_RPC_URL=… \
  python scripts/proof_bench.py run --n 3 --model gemini-3.1-flash-lite --image … --fork
```

Each case-run is handed its curated finding via `--tasks-from`, so:
- **no case dies at extraction** for an id mismatch (the spec-026 strata-3 failure is gone);
- the prover sees **byte-identical** input across all N runs of a case → the interval reflects the
  **prover's** variance, not extraction's.

## 3. Use `--tasks-from` directly (beyond the eval)

The harness gained a general capability — prove a supplied task list instead of extracting one:

```bash
python scripts/poc_queue_runner.py --project … --report … \
  --tasks-from /path/to/tasks.json --fix-patch 1=/path/1.patch --fork
```

`tasks.json` is the same shape the harness writes to `<project>/audit/poc/_extracted_tasks.json`:
```json
[ { "id": "1", "title": "…", "location": "…", "description": "…" } ]
```

Useful for **reproducibly re-running one finding** without extraction noise, or **debugging the prover
in isolation**. Only the MODEL task extraction is bypassed — the report's own fix material is still
read, so report-fix reconstruction (spec 025) works unchanged.

**Default is untouched**: with no `--tasks-from`, the harness extracts with the model exactly as
before. Normal operator runs are unaffected — this is opt-in.

## Why pin, not fuzzy-match the id?

The id mismatch is a symptom. Even normalizing `H-04`→`4` would leave the model re-writing the
finding's title/description differently each run → the prover's input drifts → extraction variance
lands in the eval number. Pinning removes the whole confound. And it is the right decomposition:
proof-eval measures proving; conflating it with extraction makes a delta unattributable — the "3/5 vs
2/5" disease. There is no general harness bug to fix — a normal run is self-consistent; this pins the
eval.

## Tests

```bash
pytest tests/integration/test_poc_runner_loop.py tests/unit/test_proof_bench.py -q
```

Offline; no model, container, or network. Pins: `--tasks-from` bypasses model extraction (and the
default still extracts); the curated-finding loader is loud on a missing field; `run_case` writes a
one-task file and passes `--tasks-from`. The harness subprocess is stubbed — never run.

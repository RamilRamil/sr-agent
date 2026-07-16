# Quickstart: Discovery Benchmark (spec 023)

Answer "what do we miss?" with a number, per vulnerability class.

## 1. Lay out a case (OUTSIDE the agent repo)

```bash
export SR_BENCH_ROOT=~/sr-bench          # anywhere outside this repo; never committed
mkdir -p $SR_BENCH_ROOT/cases/strata
```

`$SR_BENCH_ROOT/cases/strata/case.json`
```json
{ "case_id": "strata",
  "target_path": "/path/to/target/contracts",
  "report_path": "/path/to/audit-report.md" }
```

`$SR_BENCH_ROOT/cases/strata/labels.json` — **you** transcribe the published report's findings (the only judgment call is the tag):
```json
[ { "finding_id": "H-01", "bastet_tag": "access-control",
    "location": "SharesCooldown.sol", "function_name": "cancel", "severity": "high" } ]
```

> Ground truth must be human-curated. If a model extracts it, the benchmark measures a model against itself.

## 2. Get the honest floor (offline, no model)

```bash
PYTHONPATH=. python scripts/bench.py run --detector heuristic
```
Expect **~0 recall on business-logic classes** — today's discovery is 10 regex red-flags. That is the honest baseline, and it's the whole point.

## 3. Get the "what does a model find unaided" number

```bash
OPENROUTER_API_KEY=sk-or-… PYTHONPATH=. python scripts/bench.py run --detector llm --provider openrouter
```

## 4. Read the scorecard

- overall **recall / precision**
- **recall per vulnerability class** ← the headline: which classes we miss
- **named missed list** — every finding we failed to surface, by id/tag/location
- machine-readable copy at `$SR_BENCH_ROOT/results/<case>.<detector>.json`

## Rules that keep the number honest

- A candidate counts as found ONLY on **same location AND same class**. Near-misses → `needs_review`, never recall. (The vacuous-PoC lesson, applied to measurement.)
- Volume can't buy recall — spurious guesses only hurt precision.
- Every ground-truth finding is scored; no prefiltering.
- Nothing from the dataset (targets, reports, findings, paths) enters the agent repo.
- Scoring itself runs offline with no model.

## Adding a new detector later

Register a `name -> Callable[[Case], list[Candidate]]` in `DETECTORS`. The scoring rules and dataset don't change — that's what makes the taxonomy-sweep / invariant-fuzzer work comparable to today's floor.

## Tests (offline, no dataset needed)

```bash
pytest tests/unit/test_bench_rig.py -q
```
Builds a synthetic case in a temp dir and pins the anti-inflation properties.

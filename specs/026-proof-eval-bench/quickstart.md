# Quickstart: Proof-Pipeline Eval (spec 026)

Answer "did this harness change make PROVING better?" with a number that admits doubt — plus a funnel
that says *what to fix next*.

## What it measures (and what it does NOT)

- **PRIMARY**: the fraction of case-runs reaching `passed_verified` (spec 025 — falsification ran and
  the proof broke on the fix), as a **credible interval**, never a bare number.
- **DIAGNOSTIC**: an attrition funnel `extract → draft → compiled → real_pass → verified` with the
  named cases that died at each stage.
- **NOT** discovery — that's `bench.py`. This assumes the finding is known and asks whether the harness
  can *prove* it.

## 1. Lay out a case set (OUTSIDE the repo)

```bash
export SR_PROOF_ROOT=~/sr-proof-eval        # anywhere external; never committed
mkdir -p $SR_PROOF_ROOT/cases/strata-1
```

`$SR_PROOF_ROOT/cases/strata-1/case.json`
```json
{ "case_id": "strata-1",
  "target_path": "/path/to/strata-bb/contracts",
  "report_path": "/path/to/strata-bb/contracts/audit/<report>.md",
  "finding_id": "1",
  "fix_path": "/path/to/strata-bb/contracts/audit/eval-fixes/1.patch" }
```

> **The fix is required.** `passed_verified` is unreachable without one — a case with no `fix_path` is a
> **loud load error**, not a silent skip. (Ground-truth falsification patches are spec 025 US2.)
> The first set is the 5 strata-bb findings, fixes already authored + validated (apply + `forge build`).

## 2. Run at a chosen N

```bash
SR_PROOF_ROOT=~/sr-proof-eval GEMINI_API_KEY=… MAINNET_RPC_URL=… \
  python scripts/proof_bench.py run --n 5 --provider gemini --model gemini-3.1-flash-lite \
    --image sr-agent-foundry:strata-bb --fork
```

Cost is real: each case-run is a full model+docker+fork (~2–4 min), so this is **C·N** runs. The tool
states N and the resulting interval width — a small N reads as "wide, not yet decisive", not a confident
number.

## 3. Read the report

- **verified fraction** as an interval `[lo, hi]` (95% Jeffreys credible) + its width.
- **attrition funnel** with named casualties — the headline diagnostic. `real_pass` high but `verified`
  zero → the FIXES are the problem, not the exploits (this session's exact situation). Dying at
  `compiled` → the drafter.
- a **required caveat line**: strata-bb is a tuned-on **DEV set** — this measures regression/progress
  *within the set*, NOT absolute capability. Do not read a dev number as a capability number.
- machine-readable copy at `$SR_PROOF_ROOT/results/…json`, with the full **run configuration**.

## 4. Compare two versions honestly

```bash
python scripts/proof_bench.py compare $SR_PROOF_ROOT/results/before.json \
                                      $SR_PROOF_ROOT/results/after.json
```

- intervals **overlap** → **"not yet distinguishable"** (never a false winner).
- intervals **separate** → the decided direction.
- configs differ in **anything but the harness version** → **flagged**, no delta trusted. This is the
  exact guard the "3/5 vs 2/5" misread lacked: those two runs differed in prompts AND case count, so the
  delta was meaningless. Pin everything; change one thing.

## Rules that keep the number honest

- A case-run counts as verified ONLY when the harness itself reported `passed_verified` — never
  inferred, never model-judged. **No model anywhere in the scoring path** (guarded by a test), the same
  reason model-as-judge was rejected for the discovery benchmark.
- Leads (hypotheses without a confirmed finding + fix) are OUT of the verified denominator.
- One run is not a result — small N is a wide interval, reported as such.
- Nothing from the dataset (targets, reports, fixes) enters the repo; scoring runs offline.
- **Do not tune the harness against this number.** That optimizes toward the metric; the instrument
  exists to measure honestly, not to be a training signal.

## Tests

```bash
pytest tests/unit/test_proof_bench.py tests/architecture/test_proof_bench_no_model.py -q
```

Offline; no model, container, or network. Scoring is tested on synthetic manifests + scripted harness
outcomes — the real (expensive) harness run is stubbed. Interval anchors are checked against known
Beta values; the no-model guard fails if a client leaks into the scoring path.

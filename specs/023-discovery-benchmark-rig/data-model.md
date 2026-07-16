# Data Model: Discovery Benchmark Rig (spec 023)

Dataset lives OUTSIDE the repo under `SR_BENCH_ROOT`. The rig holds everything in memory; results are written back under that root.

## On-disk dataset (external, never committed)

```text
$SR_BENCH_ROOT/
├── cases/
│   └── <case_id>/
│       ├── case.json      # target reference (+ optional report path)
│       └── labels.json    # curated ground truth (human-transcribed)
└── results/
    └── <case_id>.<detector>.json   # machine-readable scorecard (written by the rig)
```

`case.json`:
| Field | Notes |
|-------|-------|
| `case_id` | stable id |
| `target_path` \| `repo_url` (+ `commit`) | where the code is; exactly one |
| `report_path` | optional — the published report (context only; NOT the label source at run time) |

`labels.json` — a list of ground-truth findings:
| Field | Notes |
|-------|-------|
| `finding_id` | from the published report, e.g. "H-01" |
| `bastet_tag` | MUST be a valid `BastetTag`; unknown → load error (FR-004) |
| `location` | file/contract, e.g. "SharesCooldown.sol" |
| `function_name` | e.g. "cancel" |
| `severity` | critical/high/medium/low/informational |

## In-memory entities (`scripts/bench.py`)

- `BenchError(Exception)` — bad root/case/tag; loud, never a silent skip.
- `Case` — `case_id`, resolved target path (or repo ref), optional report path, `truth: list[GroundTruth]`.
- `GroundTruth` — `finding_id`, `bastet_tag: BastetTag`, `location`, `function_name`, `severity`.
- `Candidate` — what a detector returns: `finding_id`, `bastet_tag: BastetTag | None`, `location`, `function_name`, `severity`.
- `MatchResult` — `matched: list[(Candidate, GroundTruth)]`, `missed: list[GroundTruth]`, `spurious: list[Candidate]`, `needs_review: list[(Candidate, GroundTruth, reason)]`.
- `Scorecard` — `case_id`, `detector`, `recall`, `precision`, `per_tag_recall: dict[str, float|None]`, `missed_named: list[dict]`, counts.

## Detector protocol

```python
Detector = Callable[[Case], list[Candidate]]
DETECTORS: dict[str, Detector] = {"heuristic": ..., "llm": ...}
```
Adding a detector = registering a name. Scoring rules and dataset are untouched (spec US2).

## Matching rule (integrity-critical, FR-006/007)

`normalize_location(x)` → `(basename-or-contract lowercased, function_name lowercased)`.

Credit **iff** `normalize_location` equal **AND** `bastet_tag` equal. Otherwise:
- location-only → `needs_review(reason="tag_mismatch")`
- tag-only → `needs_review(reason="location_mismatch")`
- neither → `spurious`
- unmatched truth → `missed`
- many→one: first credited, rest `spurious`

A `Candidate` with `bastet_tag=None` can never be credited.

## Metrics

- `recall = |matched| / |truth|`; per-tag recall over truth carrying that tag (`None`/`n-a` when that tag has no truth findings).
- `precision = |matched| / |produced|` (`needs_review` + `spurious` sit in the denominator).
- `missed_named` — the headline deliverable: every missed finding by id + tag + location.

## Trust / invariants

- `labels.json` / report text = untrusted external DATA; the rig calls no model (pure scoring).
- Dataset root + case paths validated EXTERNAL to the agent repo; results written outside it; nothing committed.
- `BastetTag` enum-enforced on both sides — a hallucinated/unknown class cannot enter the denominator or the numerator.

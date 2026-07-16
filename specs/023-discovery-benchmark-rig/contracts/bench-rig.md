# Contract: `scripts/bench.py`

## CLI

```bash
export SR_BENCH_ROOT=/path/outside/the/repo/sr-bench     # dataset lives here, never committed

# honest offline floor — today's Stage-1 red-flag heuristic
python scripts/bench.py run --detector heuristic

# "what does a model find unaided" — reuses spec-022 providers
OPENROUTER_API_KEY=sk-or-… python scripts/bench.py run --detector llm --provider openrouter

python scripts/bench.py run --detector heuristic --case strata     # one case
python scripts/bench.py cases                                       # list loaded cases + truth counts
```

- `--detector {heuristic|llm}` (registry; new detectors register by name).
- `--provider {local|openrouter|gemini}` — only for `llm` (spec 022 factory; local needs no key).
- `--case <id>` — scope to one case; default: all.

## Library surface

```python
load_dataset(root: Path) -> list[Case]        # BenchError on non-external root / bad tag / bad manifest
load_case(case_dir: Path) -> Case
normalize_location(location: str, function_name: str) -> tuple[str, str]
match_findings(produced: list[Candidate], truth: list[GroundTruth]) -> MatchResult
score(case, detector_name, match: MatchResult, produced_n: int) -> Scorecard
DETECTORS: dict[str, Detector]
```

## Behavior

- **Load**: `SR_BENCH_ROOT` (or `--root`) must resolve OUTSIDE the agent repo → else `BenchError`. Every `labels.json` tag must be a valid `BastetTag` → else `BenchError` (loud, never a silent skip that would shrink the denominator).
- **Run**: for each case, call the detector, match, score. A detector returning `[]` → recall 0 + every truth listed as missed; no crash.
- **Report**: stdout summary (recall, precision, per-tag table, named missed list) + `<root>/results/<case>.<detector>.json`. Nothing written inside the repo.
- **Determinism**: same case + detector ⇒ identical output (sorted, no wall-clock/random in the score).
- **No prefilter**: every truth finding is scored.

## Guarantees asserted by tests (`tests/unit/test_bench_rig.py`, offline)

The synthetic case is BUILT IN `tmp_path` (external root satisfied; no target-shaped data committed).

- **Load guards**: a root inside the agent repo → `BenchError`; an unknown `bastet_tag` in labels → `BenchError` (not skipped).
- **Anti-inflation (the integrity property, FR-006/007)**:
  - same location + same tag → **matched**;
  - same location + different tag → NOT matched → `needs_review(tag_mismatch)`;
  - same tag + different location → NOT matched → `needs_review(location_mismatch)`;
  - textual-similarity-only (e.g. similar notes) → never matched;
  - `bastet_tag=None` candidate → never matched;
  - recall does not rise in any of the above.
- **Volume can't buy recall**: 100 spurious candidates → recall unchanged, precision collapses.
- **Per-tag recall arithmetic**: 2 truth of tag X, 1 matched → `per_tag_recall["X"] == 0.5`; a tag with no truth → `n/a`, not 0.
- **Named misses**: every unmatched truth appears in `missed_named` with id+tag+location.
- **End-to-end**: a fake detector over the synthetic case produces a full scorecard; re-running is byte-identical.
- **Heuristic detector**: on a synthetic contract with `tx.origin`, it emits a mapped-tag candidate; on a business-logic-only contract it emits nothing (the honest floor).

# Quickstart: Code-Comprehension Graph (spec 017)

A dev tool to answer structural questions about **our own** code (the agent repo and the framework project). Offline, no credentials, no language model.

## One-time: install the external builder

```bash
uv tool install graphifyy      # provides the `graphify` CLI (dev-only; not a project dependency)
```

The core agent runs and tests-pass without this — you only need it to (re)build a map.

## Build the map

```bash
# agent repo (default root)
python scripts/codegraph.py build

# the framework project
python scripts/codegraph.py build /path/to/framework-project
```

Output lands in `<root>/graphify-out/graph.json` (gitignored). Verified to build with zero model-provider credentials present.

## Ask structural questions

```bash
python scripts/codegraph.py define  revert_hints          # where is it defined?
python scripts/codegraph.py callers _fix_scaffold_base    # who calls it?
python scripts/codegraph.py callees _process_finding      # what does it call?
python scripts/codegraph.py deps    poc_queue_runner      # what does this module import?
python scripts/codegraph.py path    _process_finding revert_hints   # how are they connected?
python scripts/codegraph.py module  solidity_index        # module summary
```

Each result shows `label (file:line)` and, for relationships, the kind and whether it is `EXTRACTED` (direct) or `INFERRED`.

## Integration scenarios (mapped to acceptance criteria)

1. **US1 / SC-001** — `callers`, `deps`, `define`, `path` each answer in one command over a built map (validated against the checked-in fixture).
2. **US2 / SC-002** — `build` succeeds with `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`OPENAI_API_KEY` unset and no network; source tree unchanged; output confined to `graphify-out/`.
3. **US2 / FR-010** — with `graphify` uninstalled, `build` prints the install line and exits cleanly; the rest of the agent is unaffected.
4. **US3 / SC-003** — full suite passes offline with graphify absent; `tests/architecture/test_codegraph_isolation.py` fails if any `sr_agent/**` file imports `scripts.codegraph` or if the query path gains a network/paid-API/graphify import.

## Run the tests (offline, deterministic)

```bash
pytest tests/unit/test_codegraph_query.py tests/architecture/test_codegraph_isolation.py -q
```

Both suites run without graphify installed and without network — they drive the checked-in `tests/fixtures/codegraph_sample.json`.

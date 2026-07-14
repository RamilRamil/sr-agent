# Research: Code-Comprehension Graph (spec 017)

All findings below were verified **hands-on this session** by installing graphify (`uv tool install graphifyy`, v0.9.15) and running it against a throwaway two-file Python sample — not read from docs.

## Decision 1: Use graphify's offline `extract` for the code map

**Decision**: Build the map with `graphify extract <root> --code-only --no-viz`, consuming the emitted `graphify-out/graph.json`.

**Rationale**:
- Offline / no credential — VERIFIED twice: (a) on a pure-`.py` sample with `env -u ANTHROPIC_API_KEY -u GEMINI_API_KEY -u OPENAI_API_KEY` the graph built from tree-sitter AST; (b) on this repo's real `scripts/` dir (which contains `.txt`/docs) — 241 nodes / 467 edges, no key.
- **`--code-only` is REQUIRED, not just `--no-viz`.** Caught by the T018 quickstart smoke: on a real repo containing docs (`.md`/`.txt`), plain `--no-viz` still routes those doc files through graphify's semantic path and errors with "no LLM API key found". `--code-only` restricts extraction to the local AST (graphify's own error message names this fix), preserving the offline/no-key guarantee. The initial pure-`.py` sample masked this because it had no doc files.
- Deterministic — the same source yields the same node/edge set; graphify caches AST by content hash.
- Clean machine-readable output — `graph.json` is node-link JSON (see data-model.md), directly parseable with stdlib `json`. No need for graphify's MCP server or any LLM.

**Alternatives considered**:
- graphify MCP server (`python -m graphify.serve graph.json`, tools `get_node`/`get_neighbors`/`shortest_path`): rejected for v1 — adds a running process and a transport; we get the same structured answers by parsing `graph.json` directly, with fewer moving parts and no server lifecycle.
- graphify natural-language `query`/`explain`/`path`: rejected — these route through an LLM (paid API or Ollama), violating the no-paid-dependency intent and adding nondeterminism. We only want structural traversal.
- Building our own tree-sitter walker: rejected — graphify already resolves cross-file `calls`/`imports` across 25+ languages; reimplementing is wasted effort for a dev tool.

## Decision 2: graphify stays an external subprocess dev tool, not a dependency

**Decision**: Invoke the `graphify` CLI via `subprocess`; do **not** `import graphify` and do **not** add `graphifyy` to `pyproject.toml` (neither runtime nor dev).

**Rationale**:
- Isolation & rollback — mirrors the accepted benign-subprocess pattern (git in the harness). If graphify changes or is removed, only the build wrapper is affected; the query layer still works on any existing `graph.json`.
- Principle V / Principle III — the core agent must run and test-pass with graphify absent (FR-006). Keeping it out of the dependency set makes that structural, not aspirational.
- graphify pulls ~30 tree-sitter grammar wheels; vendoring that into the agent's env is undesirable for a dev-only convenience.

**Alternatives considered**:
- Add `graphifyy` as an optional-dependency extra (`[project.optional-dependencies] codegraph`): deferred — a subprocess tool needs no import, so an extra buys nothing and risks someone importing it. Documented `uv tool install graphifyy` instead.

## Decision 3: graphify does NOT parse Solidity — scope is our own code only

**Decision**: The map covers our Python/framework code. Audit-target (Solidity) grounding stays entirely with the existing `scripts/solidity_index.py` `SymbolIndex`.

**Rationale**:
- VERIFIED: `.sol` is absent from graphify's `CODE_EXTENSIONS`; there is no Solidity extractor in `graphify/extractors/` and no plug-in grammar mechanism. Pointing graphify at the Solidity target would silently omit every `.sol` file.
- The user confirmed this scope after the finding: graphify is for comprehension of the agent project and the framework project, echoing the earlier SmartGraphical-Universal result that such a graph did not help the local model on the target.

**Alternatives considered**:
- Fork graphify to add `tree-sitter-solidity`: rejected explicitly — large, fragile, duplicates SymbolIndex, and graphify has no grammar-registration hook, so it would mean patching internals.

## Decision 4: Query layer is stdlib-only, in-memory, deterministic

**Decision**: `CodeGraph` loads `graph.json` once into dict indexes (by node id, by out-edges, by in-edges) and answers queries with plain BFS/lookups. Path queries use unweighted BFS for a shortest relationship chain.

**Rationale**:
- No third-party graph library needed at our scale (thousands of nodes); stdlib keeps the dependency surface at zero and the test offline.
- Deterministic ordering — results sorted by (source_file, line, id) so repeated runs and the fixture tests are stable (SC-004).

**Alternatives considered**:
- `networkx`: rejected — graph.json is already networkx node-link *shape*, but adding networkx as a dependency for a handful of traversals is unjustified (YAGNI) and would be a new packaged dep.

## Decision 5: Schema-drift is validated, not assumed

**Decision**: On load, `CodeGraph` validates the expected top-level keys (`nodes`, `links`) and per-record fields (`id`, `label`, `source_file`, `source_location`; edge `source`/`target`/`relation`/`confidence`) and raises a clear error naming the mismatch if graphify's format changes.

**Rationale**: FR-010 / edge case — a graphify version bump that renames fields must surface as an actionable message, never silently-wrong answers.

## Verified graph.json shape (reference)

Top-level: `{directed, multigraph, graph, nodes:[...], links:[...], hyperedges}`.
- Node: `{id, label, source_file, source_location(e.g. "L5"), file_type, _origin, community, norm_label}`.
- Edge (in `links`): `{source, target, relation ∈ {contains,calls,imports,imports_from,method}, confidence ∈ {EXTRACTED,INFERRED}, source_file, source_location, weight, confidence_score}`.
- Cross-file `calls` resolved correctly in the sample (`main_run → util_add [calls]`, `util_calc_total → util_add [calls]`).

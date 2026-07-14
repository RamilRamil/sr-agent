# Data Model: Code-Comprehension Graph (spec 017)

The feature consumes graphify's node-link `graph.json` read-only and exposes it through a small in-memory model. No persistent storage of our own is introduced.

## Entity: CodeNode

A named unit of code.

| Field | Source (graph.json) | Notes |
|-------|---------------------|-------|
| `id` | `node.id` | Stable identifier, e.g. `util_calc_total`. Primary key. |
| `label` | `node.label` | Human-readable, e.g. `.total()`, `Calc`, `util.py`. |
| `file` | `node.source_file` | Repo-relative path. |
| `line` | `node.source_location` | Parsed from `"L<n>"` → int; `None` if absent. |
| `kind` | derived | `module` if `file_type == code` and label ends `.py`/looks like a file; else `symbol`. Best-effort; not authoritative. |
| `origin` | `node._origin` | e.g. `ast`. Passed through for transparency. |

## Entity: CodeEdge

A directed relationship between two nodes.

| Field | Source (graph.json) | Notes |
|-------|---------------------|-------|
| `source` | `link.source` | CodeNode id. |
| `target` | `link.target` | CodeNode id. |
| `relation` | `link.relation` | One of `contains`, `calls`, `imports`, `imports_from`, `method`. |
| `confidence` | `link.confidence` | `EXTRACTED` (direct evidence) or `INFERRED`. Surfaced in every result (FR-005). |
| `file` / `line` | `link.source_file` / `link.source_location` | Where the relationship is observed. |

## Entity: CodeGraph (in-memory)

Loaded once from a `graph.json`. Holds:
- `nodes: dict[id → CodeNode]`
- `out: dict[id → list[CodeEdge]]` (edges where node is `source`)
- `in_: dict[id → list[CodeEdge]]` (edges where node is `target`)

### Validation (on load)

- Require top-level `nodes` (list) and `links` (list); else raise `CodeGraphFormatError` naming the missing key.
- Require each node has `id`; each edge has `source`, `target`, `relation`. Missing → `CodeGraphFormatError` with the offending record.
- Unknown `relation`/`confidence` values are tolerated (passed through) — graphify may add kinds; only structural absence is an error.

### Query operations (all pure, deterministic, LLM-free)

Results are sorted by `(file, line, id)` for stability.

| Query | Meaning | Returns |
|-------|---------|---------|
| `find(name)` | resolve a short name/label/id to node(s) | list of CodeNode (all matches → disambiguation) |
| `define(name)` | where a symbol is defined | node(s) with file:line, or explicit "not found" |
| `neighbors(id)` | all directly connected nodes | out+in edges with relation/confidence |
| `callers(id)` | who calls this | in-edges where `relation == calls` |
| `callees(id)` | what this calls | out-edges where `relation == calls` |
| `dependencies(id)` | what a module imports | out-edges where `relation ∈ {imports, imports_from}` |
| `path(a, b)` | shortest relationship chain | ordered list of edges via BFS, or "no path" |
| `module_summary(id)` | a module's contents + links | `contains`/`method` children + inbound/outbound counts |

## State transitions

None. The map is immutable once loaded; a rebuild produces a fresh file.

## Relationships to existing entities

- **Independent of** `SourceType` and the trust hierarchy — CodeGraph is never a source of authorization and is not registered anywhere in `sr_agent`.
- **Independent of** the audit `Finding`/`SymbolIndex` model — no shared types; SymbolIndex remains the sole owner of Solidity/target grounding.

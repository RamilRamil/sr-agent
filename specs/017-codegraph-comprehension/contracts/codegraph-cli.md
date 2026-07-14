# Contract: `scripts/codegraph.py` CLI + query surface

The tool exposes a CLI (for developers) and an importable `CodeGraph` class (for tests and ad-hoc use). Both are stdlib-only and never touch the network or a language model.

## CLI

```
python scripts/codegraph.py build   [ROOT]            # build/refresh the map for ROOT (default: repo root)
python scripts/codegraph.py define  NAME  [--graph P]  # where NAME is defined
python scripts/codegraph.py callers NAME  [--graph P]  # who calls NAME
python scripts/codegraph.py callees NAME  [--graph P]  # what NAME calls
python scripts/codegraph.py deps    NAME  [--graph P]  # what module/symbol NAME imports
python scripts/codegraph.py neighbors NAME [--graph P] # all direct connections
python scripts/codegraph.py path    A B   [--graph P]  # shortest relationship chain A→B
python scripts/codegraph.py module  NAME  [--graph P]  # module summary
```

- `--graph P` points at a specific `graph.json`; default resolves to `<root>/graphify-out/graph.json`.
- `ROOT` for `build` defaults to the repository root; may be any of our own repo roots (e.g. the framework project).

### `build` behavior (FR-001, FR-002, FR-003, FR-010)

- Runs `graphify extract <ROOT> --code-only --no-viz` as a subprocess, inheriting the environment (works with no model-provider credentials — verified). `--code-only` is required: it confines extraction to the local tree-sitter AST so doc files in a real repo don't trigger graphify's key-requiring semantic path.
- On success: prints the map path and node/edge counts.
- If `graphify` is not on PATH: prints an actionable install line (`uv tool install graphifyy`) and exits non-zero **without a traceback**. The agent and other scripts are unaffected.
- Does not modify any source file under ROOT; all output lands in `<ROOT>/graphify-out/` (gitignored).

### Query behavior (FR-004, FR-005)

- Every returned code element prints `label  (file:line)`.
- Every relationship prints its `relation` and `confidence` (`EXTRACTED`/`INFERRED`).
- Unknown name → prints `not found: <name>` and exits non-zero (distinct from a crash).
- Ambiguous name → lists all matches with locations; caller disambiguates by id.
- `path` with no connection → prints `no path found: A -> B` and exits non-zero.
- Missing/malformed graph → prints a message pointing at `build` / naming the schema mismatch; no low-level traceback.

## Library surface (for tests)

```python
from scripts.codegraph import CodeGraph, CodeGraphFormatError, build_graph

g = CodeGraph.load(path)              # raises CodeGraphFormatError on bad shape
g.find("add")                         # -> [CodeNode, ...]
g.callers("util_add")                 # -> [CodeEdge, ...] (relation == "calls", inbound)
g.callees("main_run")                 # -> [CodeEdge, ...]
g.dependencies("main")                # -> [CodeEdge, ...] (imports / imports_from)
g.neighbors("util_calc")              # -> [CodeEdge, ...] (in + out)
g.path("main_run", "util_add")        # -> [CodeEdge, ...] or []  (BFS shortest)
g.module_summary("util")              # -> dict(children=[...], inbound=n, outbound=n)

build_graph(root) -> Path             # runs graphify; returns graph.json path; raises GraphifyMissing
```

## Guarantees asserted by tests

- **Query correctness** (unit, over `tests/fixtures/codegraph_sample.json`): `callers("util_add")` returns exactly the top-level function and the class method; `path("main_run","util_add")` returns a chain; `find` on a missing name returns `[]`; deterministic ordering across runs.
- **Isolation** (architecture): no file under `sr_agent/**` (kernel or pack) imports `scripts.codegraph`; the `CodeGraph` query path imports nothing from `requests`/`anthropic`/`socket`/`urllib`/`graphify` (no network, no paid API, no hard graphify import). AST-based, mirroring `test_kernel_pack_boundary.py`.
- **Graceful absence**: `build_graph` raises a typed `GraphifyMissing` (not a raw `FileNotFoundError`) when the CLI is absent, and the CLI turns it into a clean message.

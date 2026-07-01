# Contract: SmartGraphical Tool Interface

## External invocation (consumed)

SR-agent invokes SmartGraphical as a subprocess running **SmartGraphical's own interpreter**
(`<SR_SMARTGRAPHICAL_ROOT>/.venv/bin/python`, overridable) that drives its `web_api` facade
in-process and prints one JSON line to stdout.

**Findings + graph (per file):**
```
<sg_python> -c "<facade one-liner>" <file.sol>
```
The one-liner calls `web_api.analyze_all(file, mode='auditor')` for findings and
`web_api.graph(file)` for the structural graph, then prints:
`{ "findings": [ <SmartGraphical Finding>, ... ], "graph": { "nodes": [...], "edges": [...] } }`

**Implementation note**: `sg_cli.py <file.sol> all auditor json` was the originally planned
invocation, but it only emits a summary (no `findings[]`) and pollutes stdout with a graphviz
warning — not consumable. The `web_api` facade returns clean, JSON-safe dicts with the full
`findings` array and `{nodes, edges}` graph instead (see `research.md` R1).

Exit code is non-authoritative; JSON on stdout is the contract. Empty stdout → `SmartGraphicalError`
(best-effort caller treats this as "engine unavailable", not zero findings). Non-empty non-JSON
stdout → `SmartGraphicalError`.

**Sandboxing**: no Docker path is implemented for this engine; it runs directly via the
SmartGraphical venv interpreter, matching how it's driven today. `SR_SMARTGRAPHICAL_ROOT` (env)
selects the SmartGraphical project root; the interpreter path defaults to `<root>/.venv/bin/python`
and can be overridden.

## Internal interfaces (provided by this feature)

`sr_agent/tools/smartgraphical.py`:

```python
class SmartGraphicalError(Exception): ...

@dataclass
class SGFinding:
    rule_id: str
    task_id: str
    title: str
    category: str
    confidence: str
    message: str
    remediation_hint: str
    function: str
    line: int | None

def parse_sg_findings(stdout: str) -> list[SGFinding]:
    """Parse the facade's JSON output (`{findings, graph}` wrapper or a bare
    findings list) into SGFinding (tolerant; raises only on non-JSON when text
    is non-empty)."""

def sg_to_findings(sg_findings: list[SGFinding], file_rel: str) -> list[Finding]:
    """Map to Finding (severity from confidence, bastet_tag via lookup, location
    = file_rel:line). Mirrors slither_to_findings."""

def run_smartgraphical(
    target: str | Path, audit_root: str | Path, sg_root: str | Path,
    sg_python: str | Path | None = None, timeout_s: float = 120.0,
) -> tuple[list[SGFinding], dict]:
    """Run SmartGraphical on one file via its web_api facade subprocess.
    Returns (findings, graph). Raises SmartGraphicalError when SmartGraphical
    is unavailable or produces nothing usable."""
```

`sr_agent/planner/sig.py`:
```python
def parse_sg_graph(graph) -> dict:
    """Normalize a SmartGraphical graph payload (raw {nodes,edges} or the
    web_api {model_summary: {graph: {...}}} wrapper) to {nodes, edges}."""

def build_sig_from_smartgraphical(graph: dict) -> StateInterferenceGraph:
    """Build the existing StateInterferenceGraph from SmartGraphical edges
    (read/write from state_to_function_*/cross_type_state_*, adjacency +
    transitive state propagation from function_to_function/cross_type_call,
    external-call flags from function_to_system/function_to_object). Same
    interferes()/can_reenter()."""
```

`sr_agent/orchestrator/pipeline.py`:
- `_run_smartgraphical_analysis` runs alongside `_run_static_analysis` (from `start_audit`,
  gated by `smartgraphical_root`) — per file, best-effort/auto-skip, writing `tool_output`
  findings with `engine="smartgraphical"` and collecting each file's graph into
  `PipelineState.sg_graphs`;
- `_finish` builds the SIG from the collected SmartGraphical graph(s) when available, else
  falls back to `build_sig`.

`sr_agent/io/report.py`:
- `_render_finding` shows the `engine` attribution line when present.

## Invariants (must hold)
- Output consumed as **data**: parsed, sanitized, wrapped — never executed.
- Findings stored as `source_type=tool_output`; status unconfirmed; no privileged status set.
- Engine pass is best-effort: any failure → skip, audit continues (FR-004, SC-003).
- Unmapped rule → no taxonomy tag (FR-003).

# Contract: SmartGraphical Tool Interface

## External invocation (consumed)

SR-agent invokes SmartGraphical as a subprocess and reads stdout JSON.

**Findings (per file):**
```
python sg_cli.py <file.sol> all auditor json
```
→ stdout JSON: `{ "artifact", "language", "findings_count", "rules_run": [...],
"graph_rendered", "duration_ms", "findings": [ <SmartGraphical Finding>, ... ] }`

Exit code is non-authoritative (may be non-zero on findings); JSON on stdout is the contract.
If stdout is empty/unparseable → treat as zero findings (best-effort).

**Graph (per file or bundle):** obtained from the same `all` run's graph payload
(`{ nodes, edges }`), or the `web_api.graph` facade when invoked in-process. Docker equivalent:
`docker run --rm --network none -v <root>:/audit/contracts:ro smartgraphical:local <args>`.

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
    """Parse `sg_cli ... json` output into SGFinding (tolerant; raises only on
    non-JSON when text is non-empty)."""

def sg_to_findings(sg_findings: list[SGFinding], file_rel: str) -> list[Finding]:
    """Map to Finding (severity from confidence, bastet_tag via lookup, location
    = file_rel:line). Mirrors slither_to_findings."""

def run_smartgraphical(
    target: str | Path, audit_root: Path, runner=<subprocess|docker>,
    timeout_s: float = 120.0,
) -> list[SGFinding]:
    """Run SmartGraphical on one file inside audit_root; parse findings.
    Raises SmartGraphicalError / SandboxUnavailable when unavailable."""

def parse_sg_graph(stdout_or_payload) -> dict:
    """Return the {nodes, edges} graph payload."""
```

`sr_agent/planner/sig.py`:
```python
def build_sig_from_smartgraphical(graph: dict) -> StateInterferenceGraph:
    """Build the existing StateInterferenceGraph from SmartGraphical edges
    (read/write from state_to_function_*, adjacency from function_to_function /
    cross_type_call, external-call flags). Same interferes()/can_reenter()."""
```

`sr_agent/orchestrator/pipeline.py` (extended `_run_static_analysis` + `_finish`):
- static pass also runs `run_smartgraphical` per file (best-effort, auto-skip), writing
  `tool_output` findings with `engine="smartgraphical"`;
- `_finish` builds the SIG from SmartGraphical's graph when available, else `build_sig`.

`sr_agent/io/report.py`:
- `_render_finding` shows the `engine` attribution line when present.

## Invariants (must hold)
- Output consumed as **data**: parsed, sanitized, wrapped — never executed.
- Findings stored as `source_type=tool_output`; status unconfirmed; no privileged status set.
- Engine pass is best-effort: any failure → skip, audit continues (FR-004, SC-003).
- Unmapped rule → no taxonomy tag (FR-003).

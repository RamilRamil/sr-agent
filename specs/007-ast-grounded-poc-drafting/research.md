# Research: AST-Grounded, Agentic Lookup for PoC Drafting

Phase 0 decisions. Each: Decision / Rationale / Alternatives considered.

## R1 — Parser library: `solidity-parser`, not `tree-sitter-solidity`

**Decision**: Use the `solidity-parser` PyPI package (ANTLR4-based,
`ConsenSysDiligence/python-solidity-parser` upstream) as the AST source.

**Rationale**: Already feasibility-tested this session against the real target
project — `pip install solidity-parser` pulled in exactly one dependency
(`antlr4-python3-runtime`), and `parser.parse_file(...)` + `parser.objectify(...)`
correctly parsed a real interface file's contracts, functions, and — critically — a
struct's complete field list (`TBalanceState` → `pending, claimable, nextUnlockAt,
nextUnlockAmount, totalRequests`, matching the real source exactly, zero regex).
`tree-sitter-solidity` (via `abch-tree-sitter-solidity`) is a credible alternative
(used by editors/tooling broadly) but was not the one actually installed and verified
against this project's real files this session — per this project's own practice of
verifying before recommending (not "the memory says X exists"), the already-validated
option is preferred over an equally-plausible but unverified one.

**Alternatives considered**:
- *tree-sitter-solidity* — plausible, not verified in this environment this session;
  revisit if `solidity-parser`'s ANTLR4 grammar proves to lag newer Solidity syntax the
  target project needs (a real risk to watch, not yet observed).
- *Keep regex, just add more of it* — rejected; this is exactly the pattern the spec
  exists to stop (research.md's own motivating incident list: interfaces → signatures →
  modifiers → struct fields, each a new regex).

## R2 — Lookup protocol: a plain-text marker, not a structured tool-call schema

**Decision**: The model requests a symbol by emitting a single recognizable line in its
response (e.g. `LOOKUP: TCancelGuard`); the harness detects this via a simple
line-anchored pattern, resolves it through `SymbolIndex`, and re-prompts with the
resolved definition appended, before accepting a final answer.

**Rationale**: This session drove the harness against two different local models via
Ollama (`qwen2.5-coder:32b`, `qwen3-coder:30b`) through the plain `/api/generate`
completion endpoint (`LocalClient.generate`, per `sr_agent/llm_core/local_client.py`),
not a native tool-calling turn protocol — a text marker works identically regardless of
which model or Ollama version is behind the tunnel, with no dependency on whether that
specific build reliably honors a JSON `tools` schema (unverified for these particular
local builds). A text-based protocol is exactly the kind of low-ceremony mechanism this
project already uses successfully elsewhere (the DATA-wrapping convention in
`orchestrator/context.py` is also a plain-text convention the model is instructed to
respect, not a structured tool-call).

**Alternatives considered**:
- *Ollama's native `tools`/function-calling API* — more "standard," but adds a real
  portability risk (not verified to work reliably across the specific local builds in
  use) for a problem a text marker solves just as well at this scale (a handful of
  lookups per attempt). Revisit if the harness moves to models/backends with verified,
  reliable tool-calling support.
- *Always append full context (no on-demand asking)* — rejected; this is the "static
  stuffing" pattern the feature exists to move away from (see the motivating research:
  Anthropic's context-engineering guidance, Aider's repo-map, De-Hallucinator's
  iterative-retrieval approach all converge on retrieval being driven by the
  model's own need, not pre-anticipated by the harness author).

## R3 — `SymbolIndex` shape: uniform across symbol kinds, name→list (not name→single)

**Decision**: `SymbolIndex.lookup(name)` returns a **list** of matching definitions
(possibly from different contracts, or multiple overloads of the same function name),
each tagged with its containing contract/file — never silently picks one. The harness
renders all matches back to the model (capped in count/size), letting the model's own
prompt context (which contract it's already working with) disambiguate, rather than the
index guessing.

**Rationale**: Solidity allows function overloading (same name, different parameter
types) and the same struct/interface name can plausibly appear in more than one file
in a large project. Silently returning "the first match" would reintroduce exactly the
kind of silent-wrong-answer failure mode `docs/eval-principles.md` (spec 006) already
identified and fixed for compile-verdicts — the same positive-signal discipline applies
here: an ambiguous lookup must surface as multiple real, complete answers, never a
guessed single one.

**Alternatives considered**:
- *Return only the "most relevant" single match (e.g. nearest to the finding's target
  contract)* — rejected as a first cut; the model may pick the wrong one silently if
  the harness's proximity heuristic is wrong, in the exact same way the 4th-generation
  regex issues surfaced this session (a heuristic that's usually right, occasionally
  silently wrong). Returning all matches, clearly labeled, is the honest option; the
  model has the context to disambiguate. Revisit only if this proves noisy in practice.

## R4 — Bounding lookups: fixed small integer per attempt, logged

**Decision**: A fixed per-attempt lookup budget (default: 3), configurable via a CLI
flag consistent with the harness's existing flag conventions (e.g. `--lookup-budget`).
Each lookup round-trip is logged as its own event (`event: "lookup"`, with the symbol
name and whether it resolved) in the harness's existing JSONL log — satisfies FR-004
and SC-004 (bounded AND observable, not just bounded).

**Rationale**: A small fixed bound is simple, predictable, and matches the harness's
existing pattern for other bounds (`--attempts`, `--max-minutes`). Three is a
starting point informed by this session's manual debugging: resolving H-01's actual
compile errors this session needed on the order of 1-3 distinct real-ground-truth
facts per attempt (a struct's fields, a function's real signature, a caller
requirement) — not dozens.

**Alternatives considered**:
- *Adaptive/unbounded until the model stops asking* — rejected; the spec's own edge
  case (a runaway agentic loop) requires a hard bound regardless of how well-behaved
  the model usually is (defense in depth, not optimism).

## R5 — Dependency placement: harness-only, documented, not `sr_agent`'s core deps

**Decision**: `solidity-parser` is declared as a requirement of the standalone
PoC-workability harness (documented alongside `scripts/poc_queue_runner.py`, e.g. a
`scripts/requirements.txt` or a docstring-documented `pip install` step), not added to
`sr_agent`'s own `pyproject.toml` core dependency list.

**Rationale**: Mirrors the project's existing separation — the harness is a standalone
experiment/tool that already has its own dependency posture distinct from the
installed `sr_agent` package (it already depends directly on `sr_agent.tools.sandbox`/
`sr_agent.packs.audit.tools.write_execute` as a script, not as a packaged consumer).
Adding a Solidity-specific parsing dependency to the KERNEL's own dependency list would
be a boundary violation in spirit (Principle III: the kernel is task-agnostic; Solidity
parsing is audit-pack/harness-specific, not kernel-specific) even though this isn't
literally inside `sr_agent/orchestrator/`.

**Alternatives considered**:
- *Add to `sr_agent/packs/audit`'s own dependency surface* — considered, since Solidity
  parsing IS audit-domain-specific; rejected for THIS feature because the harness
  (`scripts/`) is explicitly a separate standalone tool from the audit pack's own tool
  registry (`sr_agent/packs/audit/tools/`), and this feature's scope is the harness, not
  the pack. Revisit if/when the harness's capabilities are ever promoted into the
  audit pack proper.

## R6 — Hybrid rollout: lookup protocol first, static-block re-platforming secondary

**Decision**: Ship `SymbolIndex` + the lookup protocol as an ADDITION to the existing
draft/fix prompts (file map, callable_api, scaffold, example untouched in this pass).
Reimplementing file-map/callable_api extraction on top of `SymbolIndex` (removing the
regex versions) is a follow-up, not required for this feature's completion.

**Rationale**: Directly per spec Assumptions/FR-005 — don't let re-platforming block
delivering the new capability. The existing regex blocks are known-working (validated
across several live runs this session); replacing them is a real but separable
improvement (would also close SC-002's dedup-collision bug class at its root for THOSE
blocks too, since they'd draw from the same correctly-parsed index) — tracked as
explicit future work, not silently dropped.

**Alternatives considered**: Do both in one pass — rejected; larger, riskier single
change with no additional validation benefit for THIS feature's Success Criteria
(SC-001–005 are all satisfiable by the lookup mechanism alone).

## R7 — Validation against H-01: record, don't gate on convergence

**Decision**: Run the harness against H-01 (fork mode, existing scaffold/example, the
new lookup mechanism enabled) and record, per FR-007/SC-003: whether the model issued
any lookups, which symbols, whether they resolved, and how the run's outcome (compile
errors, stall detection, fork pass/fail) compares qualitatively to the pre-lookup runs
already logged this session. A non-passing outcome is an acceptable, valid result IF
honestly recorded — this feature's job is to show whether/how the mechanism changed
the model's behavior, not to force H-01 to a pass.

**Rationale**: Directly enforces the spec's explicit stance (User Story 4, FR-007) that
full convergence is not a completion gate — motivated by the exact same discipline this
session's earlier incident taught (spec 006): don't let the SHAPE of a desired outcome
pressure a report into overclaiming.

**Alternatives considered**: Require a passing PoC as the acceptance bar — rejected;
explicitly contradicts the spec's own stated Assumptions and would recreate exactly the
overclaiming risk spec 006 exists to prevent.

## R8 — Degradation when parsing fails

**Decision**: `SymbolIndex` builds file-by-file; a single file that fails to parse is
skipped (logged as a warning) rather than aborting the whole index build. A lookup for
a symbol that would have lived in a skipped file resolves as "not found" (same signal
as a genuinely nonexistent symbol — FR-008's contract already requires this to never be
silently fabricated either way) rather than crashing the run. The existing static
grounding blocks are unaffected by an index build failure (FR-009) since they remain
independent code paths in this pass (R6).

**Rationale**: A single malformed/unusual file (e.g. very new syntax the ANTLR4 grammar
doesn't yet support) must not take down an entire PoC-drafting run over a symbol the
model may not have even needed.

**Alternatives considered**: Abort the whole run on any parse failure — rejected, too
fragile for a harness whose whole point is resilience against an unpredictable local
model + an arbitrary external target codebase.

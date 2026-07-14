# Implementation Plan: Code-Comprehension Graph for Our Own Codebases

**Branch**: `017-codegraph-comprehension` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/017-codegraph-comprehension/spec.md`

## Summary

Add an offline, developer-facing code-comprehension capability over **our own** codebases (the SR-agent repo and the separate framework project). A thin `scripts/` wrapper builds a cross-file code map by invoking `graphify` as an isolated subprocess (`graphify extract <root> --no-viz`, verified offline with no credentials), and a small pure-Python query layer reads the resulting node-link `graph.json` to answer structural questions — define, neighbors, callers, callees, dependencies, path, module-summary — with **no language model and no network**. graphify is a dev/optional dependency only; the secure kernel never imports the query module and the map never grounds the audited target or enters the trust hierarchy. Guard tests and an offline fixture pin every one of those boundaries.

## Technical Context

**Language/Version**: Python 3.11 (project target; runs on local 3.14 too)

**Primary Dependencies**: standard library only for the runtime code (`json`, `pathlib`, `subprocess`, `collections`, `argparse`). `graphifyy` (CLI `graphify`) is an **external dev tool**, invoked as a subprocess — not imported, not a packaged dependency. No new packaged runtime or dev dependency is added to `pyproject.toml`.

**Storage**: read-only consumption of a `graph.json` file (graphify's `graphify-out/graph.json`) plus a small checked-in fixture map under `tests/fixtures/`. The generated map for a real repo is written under a gitignored output dir and is not committed.

**Testing**: pytest. New tests are offline & deterministic: a query-layer unit suite driven by the checked-in fixture, and an architecture guard test (AST-based, mirroring `tests/architecture/test_kernel_pack_boundary.py`).

**Target Platform**: developer workstation (macOS/Linux), CLI.

**Project Type**: single project — a `scripts/` dev tool + tests. No kernel/pack change.

**Performance Goals**: interactive — a single query over a repo-scale map returns in well under a second; map build time is graphify's (seconds for our repos), off the critical path.

**Constraints**: fully offline; no paid service, no network, no credential in either build or query path; source tree of the mapped repo left unmodified; graphify absence degrades gracefully (clear install prompt), never breaks the core agent.

**Scale/Scope**: our own repos (order 10²–10³ files). The query layer parses one graph.json into memory (node-link JSON, a few thousand nodes/edges at most).

## Constitution Check

*GATE: evaluated against the 5 principles. Re-checked after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | The code map is DATA about our own source, consumed only by a dev `scripts/` tool. It is never wrapped into the agent's context, never an authorization input, and never touches the `SourceType` hierarchy. FR-007/FR-008/FR-009 forbid any such wiring; a guard test enforces it. No change to memory, sanitization, or the tool-call budget. |
| **II. Human Authority** | ✅ PASS | No privileged or irreversible action is introduced. The tool only reads source and prints query results. No `write_execute`-class behavior, no confirmation-gated status. |
| **III. Kernel / Pack Separation** | ✅ PASS | Pure dev tooling under `scripts/`, isolated from both kernel and pack. The kernel does not import it (guard test). No plugin registry (YAGNI honored). |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | The map never becomes steering knowledge and is explicitly excluded from the lessons/knowledge loop (Out of Scope). It informs a human/developer, not the pipeline. |
| **V. No Paid-API Dependency** | ✅ PASS | Verified this session: `graphify extract --no-viz` builds the map from tree-sitter AST with all model-provider credentials unset. graphify's LLM doc/semantic and natural-language query features are unused. The query layer is stdlib-only. graphify is optional; the core loop does not depend on it. |

**Result: PASS — no violations. Complexity Tracking not required.**

Security-requirements note: this feature runs no attacker-influenced code. graphify is pointed only at our own trusted repositories (Assumptions), so the sandbox mandate (which governs execution of attacker-influenced code) does not apply; graphify does no code execution regardless (static tree-sitter parsing). The subprocess invocation mirrors the existing benign-subprocess pattern (git) already accepted by `tests/architecture/test_harness_sandbox_only.py`.

## Project Structure

### Documentation (this feature)

```text
specs/017-codegraph-comprehension/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── codegraph-cli.md # CLI command + query contract
└── tasks.md             # Phase 2 output (/speckit-tasks — not this command)
```

### Source Code (repository root)

```text
scripts/
└── codegraph.py         # NEW: build wrapper (graphify subprocess) + CodeGraph query layer + argparse CLI

tests/
├── fixtures/
│   └── codegraph_sample.json   # NEW: tiny checked-in node-link map (2-file sample)
├── unit/
│   └── test_codegraph_query.py # NEW: offline query-layer tests over the fixture
└── architecture/
    └── test_codegraph_isolation.py  # NEW: kernel does not import codegraph; no paid/network in query path

docs/
└── roadmap.md           # UPDATED: spec 017 landing entry + boundaries

.gitignore               # UPDATED: ignore generated graphify-out/ map output
```

**Structure Decision**: Single-file dev tool `scripts/codegraph.py` (mirrors `scripts/solidity_index.py` and `scripts/poc_queue_runner.py` as sibling standalone scripts). Two responsibilities in one module, cleanly separated: (a) `build_graph(root)` — subprocess wrapper; (b) `CodeGraph` — a pure-Python, stdlib-only query class over the node-link JSON, plus an `argparse` CLI. Tests live in the existing `tests/unit` and `tests/architecture` trees; the fixture in `tests/fixtures`. No changes under `sr_agent/`.

## Complexity Tracking

No constitution violations — section intentionally empty.

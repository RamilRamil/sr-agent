# Feature Specification: Code-Comprehension Graph for Our Own Codebases

**Feature Branch**: `017-codegraph-comprehension`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "graphify code-comprehension integration for SR-agent's own codebases (dev tooling, NOT audit-target grounding)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Answer structural questions about our own code (Priority: P1)

A developer (or the agent acting as a dev assistant) working on the SR-agent codebase — or on the separate framework project it is built on — needs to understand how the code fits together: who calls a given function, what a module depends on, where a symbol is defined, and what the call path is between two symbols. Today this means manual grepping across many files. This story delivers a pre-built, deterministic cross-file map of our own code and a small set of structured lookups over it, answering those questions in one command.

**Why this priority**: This is the core value — the whole reason to add the capability. Without it, none of the other stories matter. It is independently useful the moment a single query (e.g. "callers of X") returns correct results.

**Independent Test**: Point the tool at a checked-in fixture map of a tiny multi-file code sample and ask "who calls `add`?" — it returns the two known callers (a top-level function and a class method) with their source locations, using no network and no language model.

**Acceptance Scenarios**:

1. **Given** a built code map for a repository, **When** the developer asks for the callers of a named symbol, **Then** the tool lists every caller with its file and line, distinguishing direct-evidence relationships from inferred ones.
2. **Given** a built code map, **When** the developer asks what a module imports/depends on, **Then** the tool lists the imported symbols and modules with their locations.
3. **Given** a built code map, **When** the developer asks for the path between two symbols, **Then** the tool returns an ordered chain of relationships connecting them, or reports that none exists.
4. **Given** a built code map, **When** the developer asks for a per-module summary, **Then** the tool lists the module's defined symbols and its inbound/outbound connections.

---

### User Story 2 - Build/refresh the map offline for any of our repos (Priority: P2)

A developer wants to (re)generate the code map for a chosen repository root — the agent repo by default, or the framework project — as a local, offline step that never contacts a paid service or the network, and that leaves the source tree untouched except for a clearly-scoped output location.

**Why this priority**: The map in Story 1 must come from somewhere and stay current, but a developer can hand-build or reuse an existing map for the first slice of value, so generation is P2 rather than P1.

**Independent Test**: Run the build against a small sample directory with all model-provider credentials removed from the environment; confirm a map file is produced from source parsing alone, with no network access and no credential required.

**Acceptance Scenarios**:

1. **Given** a repository root and an environment with no model-provider credentials, **When** the developer runs the build, **Then** a code map is produced purely from source parsing and the command succeeds.
2. **Given** the build has run, **When** the developer inspects the working tree, **Then** the original source files are unchanged and all generated artifacts live under a single, clearly-named output location.
3. **Given** the external code-graph tool is not installed, **When** the developer runs the build, **Then** the tool reports a clear, actionable message (how to install it) and exits without error noise, and the rest of the agent is unaffected.

---

### User Story 3 - Keep the capability strictly isolated from the secure kernel (Priority: P1)

A maintainer must be able to prove — by an automated test — that this comprehension capability is a developer tool only: it is never imported by the secure kernel, it never becomes a required runtime dependency of the core agent, it never feeds the language model's exploit-drafting/grounding path, and it never contributes to the trust hierarchy that governs which inputs may authorize actions.

**Why this priority**: This is a security-critical boundary for the project. A comprehension tool that silently crossed into the kernel or the model-grounding path would violate the project's core principles. The guarantee is as important as the feature itself, hence P1 alongside Story 1.

**Independent Test**: Run the guard test suite with the external tool absent and all credentials removed; the core agent imports and its existing tests pass, and a dedicated test fails if anyone later makes the kernel import the comprehension module or turns the external tool into a hard runtime requirement.

**Acceptance Scenarios**:

1. **Given** the full test suite, **When** it runs with the external tool not installed and no network, **Then** every core and existing test passes.
2. **Given** the comprehension module, **When** the guard test inspects the kernel's imports, **Then** it confirms the kernel does not import the comprehension module.
3. **Given** the comprehension module, **When** the guard test inspects it, **Then** it confirms the module makes no paid-service or network call in its query path.

---

### Edge Cases

- What happens when a queried symbol name does not exist in the map? → The tool returns an explicit "not found" result, not an error or an empty ambiguous response.
- What happens when a symbol name is ambiguous (same short name in multiple files)? → The tool returns all matches with their locations so the developer can disambiguate.
- What happens when the requested path between two symbols does not exist? → The tool reports "no path found" distinctly from an error.
- What happens when the map file is missing or malformed? → The tool reports a clear message pointing at the build step rather than crashing with a low-level error.
- What happens when the target repo contains languages the external tool cannot parse (e.g. Solidity)? → Those files are simply absent from the map; the tool does not claim coverage it does not have, and this boundary is documented.
- What happens when the external tool is a different version that changes the map's field names? → The parser validates the expected shape and reports a clear mismatch rather than producing silently-wrong answers.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a way to build/refresh an offline cross-file code map for a configurable repository root, defaulting to the agent repository and also usable against the separate framework project root.
- **FR-002**: Building the map MUST NOT require any paid service, credential, or network access; it MUST rely solely on local source parsing. (Verified this session: extraction runs to completion with all model-provider credentials removed.)
- **FR-003**: Building the map MUST NOT modify the target's source files; all generated artifacts MUST be confined to a single, clearly-named output location.
- **FR-004**: The system MUST provide structured, language-model-free lookups over the map: locate a symbol's definition, list a symbol's neighbors, list callers and callees of a symbol, list a module's imports/dependencies, find a path between two symbols, and summarize a module.
- **FR-005**: Query results MUST include, for each reported code element, its source file and line, and MUST distinguish direct-evidence relationships from inferred ones.
- **FR-006**: The comprehension capability MUST be a developer/optional dependency only; the core agent MUST import, run, and pass its tests with the external code-graph tool absent.
- **FR-007**: The secure kernel MUST NOT import the comprehension module, and the comprehension module MUST NOT participate in the trust hierarchy that governs which inputs may authorize actions.
- **FR-008**: The comprehension capability MUST NOT be wired into the language model's exploit-drafting/fixing or grounding path; it is for human/dev navigation only.
- **FR-009**: The system MUST NOT be used or represented as a grounding source for the audited target code; audit-target grounding remains solely owned by the existing Solidity symbol-index capability, which this feature does not change.
- **FR-010**: When the external tool is not installed or the map is missing/malformed, the system MUST report a clear, actionable message and MUST NOT emit misleading or silently-wrong results.
- **FR-011**: The query layer MUST be validated by offline, deterministic tests driven by a small checked-in fixture map, requiring neither the external tool nor the network.
- **FR-012**: An automated guard test MUST fail if the kernel later imports the comprehension module, if the external tool becomes a hard runtime requirement, or if the query path introduces a paid-service/network call.
- **FR-013**: Project documentation MUST record the integration, the offline/no-credential verification, and the explicit boundaries (external tool cannot parse the audited target's language; the map is never model grounding).

### Key Entities *(include if feature involves data)*

- **Code Map**: A cross-file representation of one repository's structure, consisting of code elements and the relationships between them, produced offline from source parsing and consumed read-only.
- **Code Element (Node)**: A named unit of code (module, function, class, method) with an identifier, a human-readable label, and a source location (file and line).
- **Relationship (Edge)**: A directed connection between two code elements with a kind (e.g. contains, calls, imports, defines-method) and an evidence level (direct vs inferred).
- **Query**: A structured request over the map (define, neighbors, callers, callees, dependencies, path, module-summary) that returns code elements and relationships, never free-form model output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can answer "who calls X", "what does module M depend on", "where is X defined", and "what connects X to Y" for our own code with a single command each, without manually grepping.
- **SC-002**: Building the map for a repository succeeds with zero model-provider credentials present and zero network access, in 100% of runs on supported source.
- **SC-003**: The full test suite passes offline with the external tool absent, and the guard test provably fails if the kernel imports the comprehension module or the external tool is made a hard runtime dependency.
- **SC-004**: The query layer returns correct callers/callees/paths for the checked-in fixture in 100% of the defined test cases, deterministically across repeated runs.
- **SC-005**: The core agent's existing behavior and test outcomes are unchanged by this feature (zero regressions).

## Assumptions

- The repositories to be mapped are our own code (the agent project and the framework project); the tool is not pointed at untrusted third-party code as part of this feature.
- The external code-graph tool's offline source-parsing mode is used exclusively; its language-model-backed document/semantic and natural-language query features are out of scope and unused.
- A developer installs the external tool locally when they want to (re)build a map; its absence degrades gracefully to "map already built" usage or a clear install prompt.
- The map's on-disk shape (code elements with identifier/label/location; relationships with kind/evidence) is stable enough to parse against a validated schema; a version drift surfaces as a clear mismatch, not silent wrong answers.
- The framework project root is reachable on the developer's machine when they choose to map it; mapping it is on-demand, not part of the core agent runtime.

## Out of Scope

- Grounding or otherwise assisting analysis of the audited Solidity target (the external tool cannot parse Solidity; the existing symbol-index capability remains the sole owner and is unchanged).
- Wiring the map into the language model's drafting/fixing or grounding path, or into the trust hierarchy as an authorization signal.
- Building a comprehension graph over the experiential-knowledge/lessons store via the external tool's document path (that path requires a language model → excluded on the no-paid-dependency principle).
- The external tool's natural-language query/explain/path commands and its document/PDF/image semantic extraction.
- Alternate export formats (graph databases, HTML, other vault/diagram formats) beyond the single machine-readable map consumed here.
- Making the external tool a hard runtime dependency, or forking it to add a Solidity grammar (explicitly rejected).

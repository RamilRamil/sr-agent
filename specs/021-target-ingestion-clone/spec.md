# Feature Specification: Target Ingestion — Local Path or Git Repository URL

**Feature Branch**: `021-target-ingestion-clone`

**Created**: 2026-07-15

**Status**: Draft

**Input**: User description: "From the frontend, specify the audit target either by pasting a filesystem path or by giving a git repository URL (public, or private via an env token)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audit a public repository by URL (Priority: P1)

The operator starts a session and, instead of a filesystem path, pastes a public git repository URL. The system fetches the repository into an isolated working area it controls and binds the session to that copy — so the operator can audit a target without having it on their machine or mounted into the container. This is the "just give it a target" path that works the same whether the backend runs locally or in a container.

**Why this priority**: This is the headline capability — point the agent at a repo URL and go. It removes the container/host path friction entirely and is the most convenient way to start an audit.

**Independent Test**: Provide a public repo URL at session start; the session's working scope is a fresh copy of that repository, and the agent can read its files. No credential is required. The fetched code is never executed by the fetch step.

**Acceptance Scenarios**:

1. **Given** a valid public repository URL, **When** the operator starts a session with it, **Then** the system fetches the repository into an isolated working area and the session is scoped to that copy.
2. **Given** the fetch succeeds, **When** the operator inspects the session, **Then** its scope is the fetched copy (outside the agent's own project area), and fetching it did not run any of the target's code.
3. **Given** an unreachable or non-existent repository URL, **When** the operator starts the session, **Then** they get a clear error and no broken session is created.
4. **Given** a URL that is not an allowed kind (e.g. a local-file reference or an unsupported scheme), **When** the operator submits it, **Then** it is rejected with a clear message before any fetch is attempted.

---

### User Story 2 - Audit a private repository with an environment token (Priority: P1)

For a private repository, the operator relies on an access token provided through the environment (never typed into the browser). The system uses it to fetch the private repo. The token is treated as a write-only secret: it is never returned by the system, never stored, and never appears in any log or error output. With no token configured, a private URL fails with a clear "authentication required" message.

**Why this priority**: Real audit targets are often private; without token support the URL mode only covers public repos. The token is security-sensitive and must be handled correctly from the start.

**Independent Test**: With a token set in the environment, a private repository URL fetches successfully. Read any status/log surface — the token never appears. With no token, the same private URL yields a clear "authentication required" error, and a public URL still fetches without a token.

**Acceptance Scenarios**:

1. **Given** a token is configured in the environment, **When** the operator fetches a private repository URL, **Then** it succeeds.
2. **Given** any configuration, **When** the operator reads any response, log, or error output, **Then** the token never appears in it.
3. **Given** no token is configured, **When** the operator fetches a private URL, **Then** they get a clear "authentication required" message (not a confusing low-level failure).
4. **Given** a public URL, **When** it is fetched, **Then** it works with no token.

---

### User Story 3 - Path mode stays, clearly scoped (Priority: P1)

The existing "paste a filesystem path" mode continues to work and is clearly documented for both run styles: running the backend directly on the machine accepts any external host path; running it in a container accepts a path under the mounted targets area. The operator picks exactly one input per session — a path or a URL.

**Why this priority**: The path mode is the current behavior and the fastest option for a target already on the machine; it must not regress, and its container behavior must be documented so operators aren't surprised.

**Independent Test**: With the backend on the machine, a session starts on an external host path as before. In a container, a session starts on a path under the mounted targets area. Supplying both a path and a URL is rejected as ambiguous; the external-only guard still rejects a path inside the agent's own project area.

**Acceptance Scenarios**:

1. **Given** the backend runs directly on the machine, **When** the operator pastes an external host path, **Then** the session starts as today.
2. **Given** the backend runs in a container with a mounted targets area, **When** the operator pastes a path under it, **Then** the session starts.
3. **Given** a path inside the agent's own project area, **When** the operator submits it, **Then** it is rejected (unchanged guard).
4. **Given** both a path and a URL are provided, **When** the operator starts the session, **Then** it is rejected as ambiguous (choose one).

---

### Edge Cases

- URL that looks like a local-file or non-repository reference → rejected before any fetch, with a clear message.
- Private URL with no token → clear "authentication required", not a raw fetch failure.
- Fetch fails midway (network, bad URL, auth) → clear error; no half-created session; any partial working copy is cleaned up or clearly inert.
- Repository is very large → the fetch is shallow (latest snapshot only), bounding time and space.
- The same target is used again → each session fetches a fresh copy (no stale reuse in this version).
- Any status/log/error output → never contains the token.
- Working area location → always outside the agent's own project area; target code never lands in the agent's repository.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Session creation MUST accept an OPTIONAL git repository URL as an alternative to a filesystem path; the operator MUST provide exactly one of the two (both provided → rejected as ambiguous).
- **FR-002**: On a repository URL, the system MUST fetch the repository into an isolated working area under a controlled root that is OUTSIDE the agent's own project area, and bind the session to that copy.
- **FR-003**: The fetch MUST retrieve only the latest snapshot (shallow), MUST NOT recurse sub-repositories, and MUST NOT execute any of the target's code (repository hooks are not run).
- **FR-004**: The system MUST validate the URL kind and accept only network git repository URLs; local-file references and other unsupported kinds MUST be rejected with a clear message before any fetch.
- **FR-005**: A private repository MUST be fetchable using an access token read from the environment; with no token, a private URL MUST fail with a clear "authentication required" message, and public URLs MUST fetch with no token.
- **FR-006**: The access token MUST be write-only: never returned by any response, never persisted, and never written to any log, error output, or process command line.
- **FR-007**: A fetch failure MUST produce a clear error and MUST NOT leave a broken/half-created session; any partial working copy MUST be cleaned up or left clearly inert.
- **FR-008**: The existing filesystem-path mode MUST continue to work unchanged, including the external-only guard that rejects a path inside the agent's own project area; the guard MUST apply equally to a fetched working copy.
- **FR-009**: The container deployment MUST offer a documented, optional way to make a host projects directory available so path mode is usable in a container without code changes.
- **FR-010**: Adding this capability MUST NOT introduce any new software package/dependency, MUST NOT add any new privileged or irreversible action, and MUST NOT change the trust hierarchy or the human-confirmation gate.
- **FR-011**: The behavior MUST be validated by offline, deterministic tests (no network, no real token): URL-kind validation, the fetch invocation keeps the token out of its command line, a simulated fetch binds the session to the working copy outside the agent area, ambiguous input is rejected, path mode is unchanged, and the token never appears in any output.
- **FR-012**: Documentation/runbook MUST record both input modes, the container path caveat + the optional projects mount, and the env-token private-repo path.

### Key Entities *(include if feature involves data)*

- **Target Source**: what the operator provides for a session — exactly one of a filesystem path or a git repository URL.
- **Working Copy**: an isolated fetched copy of a URL target, under a controlled root outside the agent's project area, that the session is scoped to.
- **Access Token**: a write-only secret from the environment used to fetch private repositories; represented externally only as present/absent (or not at all).
- **Session Scope**: the resolved external directory a session is bound to — a pasted path or a fetched working copy — subject to the same external-only guard.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can start an audit session from a public repository URL alone — no path, no mount, no credential — and the session is scoped to a fresh copy of that repo.
- **SC-002**: A private repository fetches successfully with an environment token, and in 100% of configurations the token appears in no response, log, or error output.
- **SC-003**: Invalid or unsafe URL kinds (local-file, unsupported scheme) are rejected before any fetch in 100% of the defined test cases.
- **SC-004**: Path mode behavior is unchanged (zero regressions), and ambiguous "both path and URL" input is always rejected.
- **SC-005**: The whole feature adds no new software package and the full test suite passes offline; target code never lands in the agent's own repository.

## Assumptions

- Single-operator, single working area per session; each session fetches a fresh copy (no cross-session cache in this version).
- The access token grants read access to the private repositories the operator intends to audit; scope/expiry are the operator's responsibility.
- "Fetch does not execute target code" relies on the fetch step not running repository hooks; later execution (if any) remains the sandbox's responsibility, unchanged.
- The controlled working-area root is configurable and defaults beside the existing persisted data area; it is outside the agent's project area and is never committed.
- Network egress for fetching is available where the backend runs (e.g. the container has network); this feature does not add offline-mirroring.

## Out of Scope

- Running the whole findings list / the batch harness.
- Authentication methods beyond a single environment token (no interactive OAuth, no SSH-key management UI).
- Sub-repository (submodule) recursion; non-git version control; any fetch that executes target code.
- Caching or reusing fetched copies across sessions.
- Private-registry model providers or anything unrelated to target ingestion.

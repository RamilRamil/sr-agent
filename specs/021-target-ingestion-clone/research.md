# Research: Target Ingestion (spec 021)

## Decision 1: Clone via stdlib `subprocess` + `git` (no new package)

**Decision**: `clone_repo` runs `git clone` via `subprocess.run` — the pattern already used and accepted in this repo (`poc_queue_runner.py` runs `subprocess.run(["git", …])`; `tests/architecture/test_harness_sandbox_only.py` explicitly allows benign git subprocesses).

**Exact command**:
```
git -c core.hooksPath=/dev/null clone --depth 1 --no-tags --single-branch <url> <dest>
```
- `--depth 1` shallow (bounds size/time); `--single-branch`/`--no-tags` trim; NO `--recurse-submodules` (submodules not fetched → FR-003).
- `-c core.hooksPath=/dev/null` disables hooks; `git clone` does not execute the target's code regardless — this is belt-and-suspenders.
- Run with `env` carrying `GIT_TERMINAL_PROMPT=0` (never prompt) and, for private, the askpass wiring (Decision 3).

**Rationale**: No GitPython/new dep (Principle V, FR-010); consistent with the repo's accepted subprocess use.

**Alternatives considered**: GitPython (rejected — new package); a raw tarball download from a forge API (rejected — forge-specific, and we want plain git URLs).

## Decision 2: URL validation before any fetch (FR-004)

**Decision**: `validate_repo_url(url)` accepts only `https`/`http`/`git` schemes with a network host; rejects `file://`, `ssh` (out of scope this version), bare local paths, and anything with no host. Returns a normalized URL or raises `CloneError`.

**Rationale**: Prevents `file://`/local-path SSRF-ish reads (git can clone a local path — must be blocked so the URL field can't be used to read arbitrary local files). Scheme allowlist via `urllib.parse.urlsplit`.

**Alternatives considered**: allowing `ssh`/`git@host:` (deferred — needs SSH key management, out of scope); no validation (rejected — `file://` would let the URL field bypass the path guard).

## Decision 3: Token via `GIT_ASKPASS`, never in argv/URL/log (FR-006 — the crux)

**Decision**: For a private clone, embed only a NON-secret username in the URL (`https://x-access-token@host/org/repo.git`) and provide the token as the password via `GIT_ASKPASS`:
- Write a tiny mode-0700 helper to a temp file: `#!/bin/sh\nprintf '%s' "$SR_GIT_TOKEN"`.
- Run git with `env` = `{…, GIT_ASKPASS: <helper>, SR_GIT_TOKEN: <token>, GIT_TERMINAL_PROMPT: "0"}`.
- git calls the helper for the password; the token lives only in the child's environment, NEVER in argv, the URL string, or git's stderr.
- Delete the helper (and unset) after the clone.

**Rationale**: Putting the token in the URL (`https://<token>@…`) or in `-c http.extraHeader=…` leaks it into `ps`/argv and often into git's error messages. `GIT_ASKPASS` keeps it out of argv entirely. A test asserts the constructed argv and URL contain no token substring.

**Alternatives considered**: token-in-URL (rejected — leaks in argv/logs); `-c credential.helper='!echo password=$SR_GIT_TOKEN'` (works, token value stays in env not argv — but the helper-string form is fiddlier and more error-prone than GIT_ASKPASS); a persistent credential store (rejected — persists the secret).

## Decision 4: Workspace root must default EXTERNAL to the agent repo

**Decision**: `config.workspaces_root` = `SR_WORKSPACES_ROOT` env, default `Path(tempfile.gettempdir()) / "sr-agent-workspaces"`. Docker sets `/data/workspaces`. Each session clones into `<workspaces_root>/<uuid>`.

**Rationale**: The session's external-only guard rejects any path under `_AGENT_ROOT`. A default like `./workspaces` would be INSIDE the repo and get rejected — so the default is the system temp dir (always external), and Docker uses `/data/workspaces` (outside `/app`). The workspace is gitignored so target code never enters the agent repo (`feedback_no_target_code_in_agent`).

**Alternatives considered**: `./workspaces` (rejected — inside the repo, guard rejects it, and risks committing target code).

## Decision 5: Mutual exclusion + failure cleanup

**Decision**: `SessionManager.start(project_path=None, …, repo_url=None)` requires exactly one of `project_path`/`repo_url` (both or neither → `ValueError`). On a URL, clone first; on clone failure remove the partial workspace dir and raise a clear `ValueError`/`CloneError` (no half-created session — FR-007). A cloned workspace then goes through the identical build + external guard as a pasted path.

**Rationale**: One convergent code path; the guard still protects (a workspace under the temp/`/data` root passes; nothing inside `/app` is ever the scope).

## Path mode in Docker (FR-009)

The compose gains an OPTIONAL, commented mount (e.g. `# - ${HOST_PROJECTS:-./projects}:/projects:ro`) so an operator can expose a host projects dir and paste `/projects/<name>` without editing code. The `/targets` mount (fixed last change) also remains. Documented in the runbook.

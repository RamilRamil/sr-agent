# Implementation Plan: Target Ingestion — Local Path or Git Repository URL

**Branch**: `021-target-ingestion-clone` | **Date**: 2026-07-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/021-target-ingestion-clone/spec.md`

## Summary

Let a session target come from a git repository URL in addition to a filesystem path. A small `frontend/backend/clone.py` helper validates the URL scheme and shallow-clones the repo (`git clone --depth 1`, no submodules, hooks disabled) into an isolated workspace under a configurable root that is OUTSIDE the agent repo, using the stdlib `subprocess` (the accepted benign-git pattern — no new package). Private repos authenticate with an env token injected via `GIT_ASKPASS` so the token never touches argv, the URL, or any log. `SessionManager.start` gains `repo_url` (mutually exclusive with `project_path`); a successful clone yields a workspace path that flows through the SAME session build and the SAME external-only guard. Path mode is unchanged; the compose gets an optional host-projects mount so path mode is usable in Docker. Cloning fetches untrusted target code but never executes it (Constitution I).

## Technical Context

**Language/Version**: Python 3.11 (backend) + Svelte/TS (UI).

**Primary Dependencies**: NONE new. `subprocess` + `shutil` + `urllib.parse` (stdlib) drive `git` (already the accepted benign subprocess, per `tests/architecture/test_harness_sandbox_only.py`). No GitPython, no new package.

**Storage**: a workspaces root (configurable, `SR_WORKSPACES_ROOT`) holding fetched copies; defaults to an EXTERNAL location (system temp) so the external-only guard accepts it; in Docker it is `/data/workspaces` (beside memory/relay). Gitignored; target code never enters the agent repo.

**Testing**: pytest, offline/deterministic — the `git` call is mocked (monkeypatch `subprocess.run`); the token-out-of-argv property, URL validation, ambiguity, and session binding are asserted without network or a real token.

**Target Platform**: operator frontend process + compose.

**Project Type**: single project — a clone helper + session/API wiring + a Svelte input + compose/docs.

**Performance Goals**: n/a (fetch time is the network's); shallow clone bounds it.

**Constraints**: token write-only (never in response/log/argv/URL); clone does not execute target code (hooks off, no submodules); workspace external to the agent repo; no new package; exactly one of path/URL per session.

**Verified this session**: the repo already runs benign `git` via `subprocess.run(["git", …])` (`poc_queue_runner.py`), so a clone subprocess is consistent with the accepted pattern.

## Constitution Check

*GATE: evaluated against the 5 principles. Re-checked after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | A cloned repo is untrusted target DATA. Cloning FETCHES but never EXECUTES it — shallow, no submodules, hooks disabled (`-c core.hooksPath=/dev/null`; `git clone` does not run the target's hooks). The workspace is outside the agent repo; the `SourceType` hierarchy is untouched. |
| **II. Human Authority** | ✅ PASS | A clone writes only into a controlled scratch workspace (reversible/cleanable) and executes nothing — it is not a privileged/irreversible action and does not touch the confirmation gate. The operator explicitly supplies the URL (`human_input`), exactly as they supply a path today. |
| **III. Kernel / Pack Separation** | ✅ PASS | Change is in the frontend session layer + a clone helper; no kernel coupling; the kernel does not import it. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | Unrelated to the knowledge loop. |
| **V. No Paid-API Dependency** | ✅ PASS | Uses `git` via stdlib `subprocess` — the already-accepted benign pattern — with NO new package and no paid service. Token is a plain env secret; no paid dependency. |

**Result: PASS — no violations. Complexity Tracking not required.**

Security note (token handling, the sensitive point): the token is NEVER placed in argv, the clone URL, or any printed error. It is supplied to `git` through `GIT_ASKPASS` (a tiny mode-0700 helper that echoes the token from the child process's environment) with `GIT_TERMINAL_PROMPT=0`; the URL carries only a non-secret username (`x-access-token`). A test asserts the constructed argv/URL contain no token.

## Project Structure

### Documentation (this feature)

```text
specs/021-target-ingestion-clone/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/target-ingestion.md
└── tasks.md   # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/backend/
├── clone.py         # NEW: validate_repo_url(url); clone_repo(url, token, dest_root) -> Path (git subprocess, no-argv token, hooks off, shallow); CloneError
├── sessions.py      # EDIT: start(project_path=None, project_id=None, audit_path=None, repo_url=None) — exactly one of path/URL; clone → workspace path → existing build + guard; cleanup on failure
└── app.py           # EDIT: POST /api/session reads repo_url; ValueError → 400

sr_agent/
└── config.py        # EDIT: workspaces_root (SR_WORKSPACES_ROOT, external default) + git_token (GITHUB_TOKEN, optional, write-only)

frontend/ui/src/
├── panels/ChatSession.svelte  # EDIT: a "Repo URL" input beside the path input (choose one)
└── lib/api.ts                 # EDIT: startSession carries repo_url

frontend/docker-compose.yml    # EDIT: SR_WORKSPACES_ROOT=/data/workspaces; GITHUB_TOKEN passthrough; optional commented host-projects mount
.gitignore                     # EDIT: ignore the local workspaces dir

tests/
├── unit/test_clone_helper.py           # NEW: URL validation (reject file://, non-git); argv has NO token + URL has no token; hooks-off/shallow flags; CloneError on failure
├── integration/test_session_repo_url.py # NEW: mocked clone binds session to an external workspace; both path+URL → reject; missing token on private → clear error
└── (reuse) path-mode session tests stay green

docs/roadmap.md · RUN_FRONTEND.local.md  # EDIT: both modes, container caveat + optional mount, env-token private path
```

**Structure Decision**: Keep it a thin ingestion layer. `clone.py` is a small stdlib helper (validate + clone); `SessionManager.start` resolves URL→workspace then reuses the exact existing session build + external-only guard, so a fetched copy and a pasted path converge on one code path. The token-out-of-argv detail lives entirely inside `clone.py` and is pinned by a test. No kernel or trust-model change.

## Complexity Tracking

No constitution violations — section intentionally empty.

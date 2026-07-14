# Data Model: Target Ingestion (spec 021)

No persistent DB. In-memory config + a scratch workspace on disk.

## Entity: clone helper (`frontend/backend/clone.py`, new)

- `CloneError(Exception)` — invalid URL, auth required with no token, or a failed clone.
- `validate_repo_url(url: str) -> str` — accepts only `http|https|git` scheme with a network host; rejects `file://`, bare paths, `ssh`, hostless URLs → `CloneError`. Returns the normalized URL.
- `clone_repo(url: str, dest_root: Path, token: str = "") -> Path`:
  - `dest = dest_root / uuid4()`; runs `git -c core.hooksPath=/dev/null clone --depth 1 --no-tags --single-branch <url> <dest>` via `subprocess.run`.
  - token (if given) → username-only URL `https://x-access-token@host/…` + `GIT_ASKPASS` helper echoing `$SR_GIT_TOKEN` from `env`; `GIT_TERMINAL_PROMPT=0`. Token NEVER in argv/URL.
  - On non-zero exit: remove `dest`; raise `CloneError` with a message that excludes the token and (for private-with-no-token) says "authentication required".
  - Returns `dest` (the working copy path).

## Entity: Config (edited, `sr_agent/config.py`)

| Field | Change |
|-------|--------|
| `workspaces_root: Path` | NEW — `SR_WORKSPACES_ROOT`, default `tempfile.gettempdir()/"sr-agent-workspaces"` (EXTERNAL to the repo so the guard accepts it). |
| `git_token: str` | NEW — `os.environ.get("GITHUB_TOKEN", "")`, optional, write-only (never returned/persisted/logged). |

## Entity: Session inputs (edited `SessionManager.start`)

| Field | Change |
|-------|--------|
| `project_path` | now optional |
| `repo_url` | NEW — optional git URL; EXACTLY ONE of `project_path`/`repo_url` (both/neither → `ValueError`) |
| `audit_path` | unchanged (optional external report) |

Flow: `repo_url` → `validate_repo_url` → `clone_repo(url, config.workspaces_root, config.git_token)` → the returned workspace path is used as the project path → identical build + external-only guard. Clone failure → cleanup + clear error, no session created.

## Entity: Working Copy

- A `<workspaces_root>/<uuid>` directory holding a shallow clone of a URL target.
- External to the agent repo (satisfies the guard); gitignored; not reused across sessions (fresh per session).

## API surface

- `POST /api/session` body: `{project_path?, project_id?, audit_path?, repo_url?}` — exactly one of `project_path`/`repo_url`. Response unchanged (`session_id`, `project_id`, `scope_root`, `has_report`) — `scope_root` is the workspace for a URL target.

## Trust / relationships

- The clone is untrusted target DATA; it is never executed by the fetch (hooks off, no submodules). Sandbox execution (if any later) is unchanged.
- The token is a write-only env secret — not in `config` output, responses, logs, argv, or the URL.
- `SourceType` hierarchy, the confirmation gate, and path-mode behavior are unchanged.

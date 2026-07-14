# Contract: Target ingestion (path or git URL)

## `frontend/backend/clone.py` (library)

```python
from frontend.backend.clone import validate_repo_url, clone_repo, CloneError

validate_repo_url("https://github.com/org/repo.git")  # -> normalized url
validate_repo_url("file:///etc/passwd")               # -> raises CloneError
validate_repo_url("/home/me/proj")                    # -> raises CloneError

clone_repo(url, dest_root, token="") -> Path   # workspace path; CloneError on failure
```

**Guarantees**:
- Uses stdlib only (`subprocess`, `shutil`, `urllib.parse`, `tempfile`, `uuid`) — no new package.
- The constructed `git` argv and the clone URL contain NO token substring (token flows via `GIT_ASKPASS`/env).
- Clone command is shallow, single-branch, no-tags, no-submodules, hooks disabled.
- On failure: the partial `dest` is removed; the raised message excludes the token.

## Frontend backend

- `POST /api/session` body `{project_path?, project_id?, audit_path?, repo_url?}`:
  - Exactly one of `project_path` / `repo_url` (both or neither → 400 "provide exactly one of a path or a repo URL").
  - `repo_url` → validated, cloned into `config.workspaces_root/<uuid>` (external), session bound there.
  - Invalid URL / clone failure / private-without-token → 400 with a clear message (no token in it).
  - Response: `{session_id, project_id, scope_root, has_report}` — `scope_root` is the workspace for a URL target.
- Path mode unchanged (external-only guard still applies).

## ChatSession.svelte

- Session-create form gains a **Repo URL** input beside the target-path input; the operator fills one. (Audit-file field unchanged.)
- `startSession(project_path?, project_id?, audit_path?, repo_url?)` carries the URL.

## docker-compose

- `environment`: `SR_WORKSPACES_ROOT=/data/workspaces`, `GITHUB_TOKEN: ${GITHUB_TOKEN:-}`.
- Optional commented host-projects mount for Docker path mode.

## Tests assert

- **Clone helper** (`tests/unit/test_clone_helper.py`, mocked `subprocess.run`): `validate_repo_url` accepts https/git, rejects `file://` / bare path / hostless; a token clone builds argv + URL with NO token substring anywhere and wires `GIT_ASKPASS`; the argv carries `--depth 1`, `core.hooksPath=/dev/null`, no `--recurse-submodules`; a non-zero git exit → `CloneError` and the partial dir is removed.
- **Session URL flow** (`tests/integration/test_session_repo_url.py`, mocked clone): a `repo_url` binds the session to a workspace under `workspaces_root` (outside the agent repo); both `project_path`+`repo_url` → `ValueError`; neither → `ValueError`; a private URL with no token → clear "authentication required".
- **Secret hygiene**: no response/log/error surface contains the token.
- **Offline/no-dep**: no new package; the full suite passes offline; path-mode tests stay green.

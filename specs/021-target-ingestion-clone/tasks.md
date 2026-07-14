# Tasks: Target Ingestion — Local Path or Git Repository URL

**Input**: Design documents from `specs/021-target-ingestion-clone/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/target-ingestion.md

**Tests**: INCLUDED — spec mandates them (FR-011; the security invariants — token hygiene, no-exec, external workspace — must be pinned).

**Organization**: by user story. US1 (URL clone) + US2 (token) live in the clone helper + session wiring; US3 (path mode) is mostly guard-preservation + compose/docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no dependency on an incomplete task)
- Paths are repo-root-relative

---

## Phase 1: Setup / Foundational

- [X] T001 [P] Add to `sr_agent/config.py`: `workspaces_root: Path = Path(os.environ.get("SR_WORKSPACES_ROOT", str(Path(tempfile.gettempdir()) / "sr-agent-workspaces")))` (EXTERNAL default so the session guard accepts it) and `git_token: str = os.environ.get("GITHUB_TOKEN", "")` (optional, write-only). Import `tempfile`.
- [X] T002 [P] Add `/workspaces/` (local dev workspace) to `.gitignore` so a cloned target never enters the agent repo.

**Checkpoint**: `import sr_agent.config` works; `config.workspaces_root` resolves outside the repo.

---

## Phase 2: User Story 1 + 2 — Clone helper (Priority: P1) 🎯

**Goal**: validate a URL, shallow-clone it (no exec, no submodules), token via env not argv.

**Independent Test**: `validate_repo_url` rejects `file://`/bare paths; a token clone's argv+URL contain no token; a git failure → `CloneError` + cleanup.

### Tests for US1/US2

- [X] T003 [P] [US1] Create `tests/unit/test_clone_helper.py` (monkeypatch `subprocess.run` to capture argv/env and simulate exit codes): `validate_repo_url` accepts `https://…/repo.git` and a `git://` URL, rejects `file:///…`, a bare `/path`, an `ssh://`/`git@` form, and a hostless URL (`CloneError`); `clone_repo(url, tmp_root, token="ghp_secret")` → the captured **argv contains no `"ghp_secret"` and the URL arg has no token substring** (token wired via `GIT_ASKPASS`/env instead), and argv carries `--depth 1`, `--no-tags`, `--single-branch`, `-c core.hooksPath=/dev/null`, and NO `--recurse-submodules`; a non-zero git exit → `CloneError` AND the partial dest dir is removed; a public clone (token="") sets no askpass and no token anywhere. **C1:** also assert (AST) that `frontend/backend/clone.py`'s top-level imports are stdlib + `sr_agent`/`frontend` only — no new package (`gitpython`, `requests`, `httpx`, …) — pinning FR-010.

### Implementation for US1/US2

- [X] T004 [US1] Create `frontend/backend/clone.py`: `CloneError`; `validate_repo_url(url) -> str` (allowlist `http|https|git` scheme + non-empty host via `urllib.parse.urlsplit`; else `CloneError`); `clone_repo(url, dest_root, token="") -> Path` (`dest = dest_root/uuid4()`; build the shallow/hooks-off argv; for a token, rewrite to `https://x-access-token@host/…` + write a `GIT_ASKPASS` helper echoing `$SR_GIT_TOKEN`, pass `env={…, GIT_ASKPASS, SR_GIT_TOKEN, GIT_TERMINAL_PROMPT:"0"}`; `subprocess.run(..., capture_output=True)`; on failure `shutil.rmtree(dest, ignore_errors=True)` + raise `CloneError` with a token-free message ("authentication required" when git reports auth); always delete the askpass helper in a `finally`). **C2:** create the askpass helper via `tempfile.mkstemp` (mode 0700) OUTSIDE the workspace, and the helper's literal text contains only `$SR_GIT_TOKEN` (never the token value — the value is only in the child env). Stdlib only.

**Checkpoint**: `tests/unit/test_clone_helper.py` green; token never in argv.

---

## Phase 3: User Story 1/2 wiring — session + API (Priority: P1)

**Goal**: `repo_url` on session-create → clone → session bound to the external workspace, one-of path/URL.

**Independent Test**: mocked clone binds the session to a workspace under `workspaces_root`; both path+URL → reject; private-without-token → clear error.

### Tests

- [X] T005 [P] [US1] Create `tests/integration/test_session_repo_url.py` (monkeypatch `frontend.backend.sessions` clone to return a tmp dir): `start(repo_url=…)` builds a session whose `scope_root` is that (external) workspace; `start(project_path=X, repo_url=Y)` raises `ValueError` (ambiguous); `start()` with neither raises `ValueError`; a `CloneError` from the helper surfaces as a clear error and creates no session; `POST /api/session {repo_url}` returns 200 and `{repo_url, project_path}` both set → 400.

### Implementation

- [X] T006 [US1] Edit `frontend/backend/sessions.py`: `start(project_path=None, project_id=None, audit_path=None, repo_url=None)` — require EXACTLY ONE of `project_path`/`repo_url` (`ValueError` otherwise); when `repo_url`, `validate_repo_url` → `clone_repo(url, config.workspaces_root, config.git_token)` → use the returned path as the project path; on any `CloneError` re-raise as a clear `ValueError` (no partial session). The existing external-guard + build run unchanged on the resolved path.
- [X] T007 [US1] Edit `frontend/backend/app.py`: `POST /api/session` reads `body.get("repo_url")` and passes it to `_manager.start(...)`; `ValueError` → 400 (message carries no token).

**Checkpoint**: URL flow green; both-inputs rejected.

---

## Phase 4: User Story 3 — Path mode preserved + Docker usability (Priority: P1)

**Goal**: path mode unchanged; Docker path mode documented + an optional projects mount.

- [X] T008 [P] [US3] Edit `frontend/docker-compose.yml`: add `SR_WORKSPACES_ROOT=/data/workspaces` and `GITHUB_TOKEN: ${GITHUB_TOKEN:-}` to `environment`; add an OPTIONAL commented mount `# - ${HOST_PROJECTS:-./projects}:/projects:ro` with a note (host projects → `/projects/<name>` for Docker path mode).
- [X] T009 [P] [US3] Edit `frontend/ui/src/panels/ChatSession.svelte` + `frontend/ui/src/lib/api.ts`: add a **Repo URL** input to session-create beside the target-path input (fill one); `startSession` carries `repo_url`; a short hint that path vs URL is one-or-the-other.

**Checkpoint**: existing path-mode session tests stay green; UI offers both inputs.

---

## Phase 5: Polish & Cross-Cutting

- [X] T010 [P] Update `docs/roadmap.md` (spec 021 landing: both input modes; clone is untrusted, non-executing, shallow/no-submodule/hooks-off; token via `GIT_ASKPASS` never in argv/URL/log; workspace external to the repo; no new package; gotcha #16 — "injecting a secret into a subprocess: never argv/URL, use an askpass/env credential path") and `RUN_FRONTEND.local.md` (repo-URL mode + private `GITHUB_TOKEN` + optional projects mount).
- [X] T011 Final gate: full suite offline (no `GITHUB_TOKEN`, no network) `pytest -q` green, zero regressions; `ruff check` clean on all new/edited Python.

---

## Dependencies & Execution Order

- **Setup (T001-T002)** → config + ignore; blocks the helper's default root.
- **Clone helper (T003-T004)** → the core; blocks session wiring.
- **Session/API (T005-T007)** depends on T004.
- **Path/UI/compose (T008-T009)** depends only on the API shape (T007) for the UI; compose independent.
- **Polish (T010-T011)** last.

## Parallel Opportunities

- T001 / T002 [P]; T003 (helper test) and T005 (session test) are `[P]` once targets exist; T008 (compose) / T009 (UI) / T010 (docs) [P].

## Implementation Strategy

MVP = Setup + clone helper + session/API (URL mode working end-to-end, token-safe). US3 preserves path mode + Docker usability. The token-out-of-argv test (T003) locks the crux invariant before the helper lands.

**Total tasks**: 11 (Setup 2, Clone helper 2, Session/API 3, Path/UI 2, Polish 2).

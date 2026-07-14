# Quickstart: Target Ingestion — path or git URL (spec 021)

Start an audit session from a **repo URL** (fetched for you) or a **filesystem path** — one per session.

## By repo URL (works in Docker and local, no mounting)

1. New session → **Repo URL** = `https://github.com/org/repo.git` → Start.
2. The backend shallow-clones it into an isolated workspace (outside the agent repo) and scopes the session there.
3. Public repos need no credential.

### Private repo
Set a token in the environment (never in the browser):
```bash
export GITHUB_TOKEN=ghp_…      # read scope on the repos you audit; use a short-lived, least-privilege token
```
The clone uses it — the token is never returned, logged, put on git's command line, or in the URL. No token + private URL → clear "authentication required".

## By filesystem path

- **Local run:** any external host path (as before).
- **Docker:** a path under the mounted targets area (`/targets/<name>`), or enable the optional host-projects mount in `frontend/docker-compose.yml` and use `/projects/<name>`.

You provide exactly one — a path or a URL (both → rejected).

## What stays guaranteed

- A cloned repo is untrusted target code; **fetching it never runs it** (shallow, no submodules, hooks off).
- The workspace is always outside the agent repo; target code never lands in the SR-agent repository.
- The git token is write-only: never in a response, log, error, or the git command line.
- No new dependency (uses git via the standard library); the core loop is unaffected.

## Run the tests (offline, no network, no real token)

```bash
pytest tests/unit/test_clone_helper.py tests/integration/test_session_repo_url.py -q
```
The `git` call is mocked; the tests pin URL validation, token-out-of-argv, external workspace binding, and path/URL mutual exclusion.

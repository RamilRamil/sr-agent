# Quickstart: Harness Prompt Management

How to verify this feature is done — entirely offline (no Langfuse, Ollama, Docker, or
network).

## 1. `get_prompt_versioned` — additive, graceful (SC-004)

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
.venv/bin/python -m pytest tests/unit/test_local_client.py -k get_prompt_versioned -q
```

Confirm a disabled tracer returns `(fallback, None)`; a fake Langfuse client returning a
versioned prompt returns `(text, version)`; a raising client returns `(fallback, None)`.
The existing `get_prompt` and its kernel callers are unchanged.

## 2. `_resolve_prompt` — fallback / versioned / format-failure

```bash
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k resolve_prompt -q
```

Confirm: tracing off → the byte-exact constant + `version None`; versioned → fetched
text + version; a fetched template missing a required placeholder → the constant used,
run not crashed (FR-007).

## 3. Tracing off ⇒ identical prompts (SC-001)

```bash
.venv/bin/python -m pytest tests/integration/test_poc_runner_loop.py -k prompt -q
```

Confirm that with a disabled tracer, a draft's assembled prompt text is identical to the
pre-feature (constant-based) prompt — a normal run is byte-for-byte unchanged.

## 4. A versioned run records the prompt version (SC-002/SC-003)

Confirm, with a fake tracer returning a versioned prompt, that the draft/fix
generation's recorded metadata includes `prompt_provenance` with the prompt name+version
— and that a fallback-sourced prompt records `version: None`, never a fabricated one.

## 5. Seeding is a no-op when disabled, creates per prompt when enabled (SC-005)

```bash
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k seed_prompts -q
```

Confirm `seed_prompts` with a disabled tracer does nothing (no error); with a fake
Langfuse client it issues one create per harness prompt under `production`.

## 6. Full offline suite green (SC-006)

```bash
.venv/bin/python -m pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```

All previously-passing tests plus the new ones pass, offline, no bug-bounty target code
embedded, no Langfuse/Ollama/Docker/network.

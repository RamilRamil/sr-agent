# Quickstart: Stage 1 Scaffold Synthesis

How to verify this feature is done — entirely offline (no model, Docker, or network).

## 1. A compiling synthesized base is accepted and used

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k synthesize -q
```

Confirm `synthesize_scaffold` with a fake client returning a Solidity base and a
scripted `run_tests` that COMPILES returns the base's path, writes it only under the
untracked audit area, and logs `scaffold_synthesized`.

## 2. A non-compiling / empty / infra-failed synthesis is discarded, honestly (SC-002)

Confirm, in the same unit tests:
- scripted `run_tests` reports NOT compiled → returns `None`, logs
  `scaffold_synthesis_failed` reason `no_build`, and the rejected base file is removed.
- the fake client returns non-Solidity / nothing → `None`, reason `no_output`.
- `run_tests` raises → `None`, reason `infra`.
- the target project's tracked source is byte-for-byte unchanged after any of these
  (SC-004).

## 3. The loop swaps the scaffold on success and falls back on failure

```bash
.venv/bin/python -m pytest tests/integration/test_poc_runner_loop.py -k synth -q
```

Confirm, via a monkeypatched `synthesize_scaffold` verdict:
- an insufficient-scaffold finding whose synthesis SUCCEEDS drafts under the
  synthesized base (SC-001).
- one whose synthesis FAILS proceeds under the prior scaffold with a logged fallback —
  the run is never blocked (SC-002).
- a finding whose scaffold is already SUFFICIENT never consults synthesis (SC-003).

## 4. Full offline suite green (SC-005)

```bash
.venv/bin/python -m pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```

All previously-passing tests plus the new ones pass, offline, no bug-bounty target
code embedded.

## 5. (Optional, US3 / SC-006) Live H-01 end-to-end

Only if pursued — NOT the completion bar. A live H-01 run where the auto-scaffold is
insufficient, through synthesis → drafting → (spec 010) mutation-verify. Record in
[docs/roadmap.md](../../docs/roadmap.md): did the synthesized `SharesCooldown` base
compile? did H-01 then reach a PASS? was that PASS mutation-verified or downgraded?
Non-convergence is an acceptable, informative outcome.

# Quickstart: Kernel / Capability-Pack Boundary

This feature is an internal re-layering — there is no new user-facing command. "Using" it means verifying the boundary holds and nothing regressed.

## Prerequisites

Same environment as any `sr-agent` work:

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
export SR_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
```

No new dependencies (the boundary check uses stdlib `ast`).

## Verify the boundary (SC-001)

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/architecture/test_kernel_pack_boundary.py -v
```

Passes when **0** kernel files import `sr_agent.packs`. While the refactor is in progress the test prints the remaining violation set and count (the N→0 ratchet, see contracts/boundary-check.md). You can also eyeball it:

```bash
# every kernel file that still reaches into the pack (should be empty at completion)
grep -rn "sr_agent.packs" sr_agent --include="*.py" | grep -v "sr_agent/packs/" | grep -v "sr_agent/cli.py"
```

## Verify the security property (US2 / SC-003)

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/security/test_hostile_pack.py -v
# and the MI harness must still be ASR 0:
PYTHONPATH=. .venv/bin/python -m pytest tests/security/ -v
```

All hostile-pack cases (H1 skip-confirmation, H2 forge human_input, H3 opt-out of containment) must be rejected/ineffective, and the MI harness Attack Success Rate must be 0.

## Verify no behavior change (US3 / SC-004)

The whole existing suite is the oracle:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

Same tests pass as before the refactor (no net loss of green). Spot-check the two live paths are still wired:

```bash
# chat still routes/gates/answers as in feature 003
PYTHONPATH=. .venv/bin/python -m sr_agent.cli chat /path/to/target/contracts --project-id strata-bb
```

## Read the contract (US4 / SC-005)

`specs/004-kernel-pack-boundary/contracts/pack-interface.md` lists everything a pack provides and everything the kernel guarantees — enough to author a hypothetical second pack, and it records that **no plugin registry is built**.

## Where things live after the refactor

- **Kernel** — everything under `sr_agent/` except `sr_agent/packs/` and `sr_agent/cli.py`.
- **Audit pack** — `sr_agent/packs/audit/` (`pack.py` assembles `AUDIT_PACK`).
- **Composition root** — `sr_agent/cli.py` imports the pack and injects it into the loop.

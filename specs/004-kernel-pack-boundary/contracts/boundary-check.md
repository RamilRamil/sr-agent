# Contract: Boundary Check (SC-001)

An automated, always-runnable test proving the kernel imports nothing pack-specific. It is the machine-checkable form of US1 and the reason a directory boundary was chosen over a hand-maintained allowlist.

## Location

`tests/architecture/test_kernel_pack_boundary.py`

## The rule

- **Kernel files** = every `sr_agent/**/*.py` **except** `sr_agent/packs/**` and the composition root `sr_agent/cli.py`.
- For each kernel file, parse it with `ast` and collect all import targets (`import X`, `from X import ...`, including relative imports resolved to their absolute module path).
- **Assert**: no kernel file imports a module under `sr_agent.packs`.
- Result on success: **0 violations**.

`ast` (not `grep`) so that the string `"sr_agent.packs"` in a comment, docstring, or the boundary-check test's own data does not register as an import.

## Ratchet during implementation

The test is committed at the **start** of US1 and prints the current violation set:

```
kernel→pack import violations: 14
  sr_agent/orchestrator/loop.py -> sr_agent.packs.audit.dispatch
  sr_agent/guardrails/escalation.py -> sr_agent.packs.audit.finding
  ...
```

While violations remain it is an informational ratchet (skipped/xfail with the count logged); once the count reaches 0 it flips to a hard assertion. This makes progress visible (N→0) and marks a safe green checkpoint after each relocation.

## Allowed direction (must NOT be flagged)

- `sr_agent/cli.py` importing `sr_agent.packs.audit` — it is the composition root (excluded).
- Any `sr_agent/packs/**` file importing kernel modules (`sr_agent.orchestrator.pack`, `sr_agent.models.action`, `sr_agent.llm_core.schemas`, `sr_agent.tools.sandbox`, …) — pack→kernel is expected.

## Relationship to other gates

Failing this check has the same standing as a memory-injection regression: **the change does not ship** (spec Edge Cases). It complements — does not replace — the hostile-pack property in [hostile-pack.md](hostile-pack.md): this check proves *structural* separation; that one proves the *behavioral* guarantee that a pack cannot weaken a guardrail.

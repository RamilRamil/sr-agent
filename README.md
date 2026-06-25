# SR-agent

A smart contract security auditor agent built to demonstrate what a **secure AI agent** looks like in practice.

## Dual goal

Most agent frameworks focus on capability. SR-agent focuses on both:

1. **Audit smart contracts** — detect reentrancy, oracle manipulation, MEV vulnerabilities, and other EVM security issues across a 3-stage pipeline (Discovery → CheckRunner → Synthesis)
2. **Be a secure agent itself** — implement every current best practice for MI-resistant, auditable, principal-isolated AI agents

The second goal is the research contribution. SR-agent is a reference implementation of an agent that takes its own security as seriously as the security of the contracts it audits.

## The threat: Memory Injection

Memory Injection (MI) is an attack where malicious content planted in an agent's memory causes it to take harmful actions in future sessions — exfiltrating data, skipping analysis, or issuing false safe verdicts. Attack success rates (ASR) against unprotected agents reach **55–85%** depending on the attack type (from paper [2503.16248](https://arxiv.org/abs/2503.16248)).

SR-agent reduces this to **≤ 5% ASR** through architectural controls, not prompt engineering.

## Security architecture

The core idea: separate the **Orchestration Plane** (deterministic code) from the **LLM Context Plane** (probabilistic model). All security guarantees live in the orchestration plane — the LLM cannot override them regardless of what it's been instructed to do by injected content.

```
┌─────────────────────────────────────────────────────────┐
│                  Orchestration Plane                     │
│  HMAC sign/verify · source_type hierarchy · status gate  │
│  action whitelist · path traversal guard · OOB confirm  │
└──────────────────────────┬──────────────────────────────┘
                           │ controlled interface
┌──────────────────────────▼──────────────────────────────┐
│                   LLM Context Plane                      │
│  Claude Opus (Stage 1/3) · Qwen3-4B fine-tuned (Stage 2) │
│  All external data wrapped in [DATA START]...[DATA END]  │
└─────────────────────────────────────────────────────────┘
```

**Memory integrity** — every record in Episodic Memory is HMAC-SHA256 signed by the orchestrator. Records with invalid signatures are silently dropped before entering LLM context. The signing key never leaves the orchestration plane.

**Append-only memory** — no `update_memory` or `delete_memory` tools. Corrections are new records with a `supersedes` pointer. Only `source_type=human_input` can issue corrections.

**Source type hierarchy** — every memory record carries a provenance label. Privileged statuses (`verified_safe`, `skip_analysis`, `audit_complete`) require `source_type=human_input`. An LLM trying to set these via `llm_inference` is rejected deterministically.

**Action whitelist** — the agent has no `run_command(cmd: str)`. Every tool is a named, typed operation (`run_slither`, `read_file`, `analyze_transactions`). Tool descriptions are hash-verified at startup against `TOOL_REGISTRY` to prevent supply-chain attacks.

**Out-of-band confirmation** — irreversible actions (`write_poc`, `run_tests`, `deploy_test_contract`) pause execution and require explicit human approval via a separate CLI invocation before proceeding.

**Extended thinking always on** — Claude Opus extended thinking is a security requirement on Stage 1/3 calls, not a performance option. It provides ~5× MI resistance improvement per the research.

## 3-stage audit pipeline

```
Stage 1 — Discovery (ReAct, Claude Opus)
  Build call graph → identify high-risk targets → prioritized list

Stage 2 — CheckRunner (for-loop, Qwen3-4B fine-tuned, local)
  Per-target: apply 12 preconditions checklist → structured findings
  Code never leaves your machine

Stage 3 — Synthesis (ReAct, Claude Opus)
  Combine findings → identify multi-contract attack paths → final report
```

Stage 2 runs a locally fine-tuned Qwen3-4B via Ollama — no contract code is sent to external APIs. Stage 1/3 use Claude Opus with extended thinking via the Anthropic API.

## Architecture decisions

All technical decisions are documented in [`specs/001-secure-memory-agent/`](specs/001-secure-memory-agent/) with rationale and alternatives considered. Key files:

- [`research.md`](specs/001-secure-memory-agent/research.md) — 17 architectural decisions
- [`data-model.md`](specs/001-secure-memory-agent/data-model.md) — all entities and state transitions
- [`contracts/`](specs/001-secure-memory-agent/contracts/) — module interface contracts

Framework research (why we didn't use LangGraph, Mem0, Hermes, LangMem, NeMo Guardrails) is in [`research/frameworks.md`](research/frameworks.md).

## Quickstart

See [`specs/001-secure-memory-agent/quickstart.md`](specs/001-secure-memory-agent/quickstart.md) for full setup instructions.

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and generate SR_SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"

docker compose up -d ollama langfuse
pip install -e ".[dev]"

sr-agent audit ./path/to/contracts/
sr-agent demo-attack   # run MI attack scenarios, verify ASR ≤ 5%
```

## Running tests

```bash
pytest tests/unit/          # fast, no external dependencies
pytest tests/security/      # MI resistance tests, no LLM calls needed
pytest tests/integration/   # requires Docker
```

## References

- [2503.16248](https://arxiv.org/abs/2503.16248) — Memory Injection attacks, ASR measurements, extended thinking resistance
- [2606.03387](https://arxiv.org/abs/2606.03387) — Bastet dataset: 849 expert-labelled Code4rena findings, 46-tag taxonomy
- [2606.05986](https://arxiv.org/abs/2606.05986) — AttackPathGNN: precondition-based vulnerability detection

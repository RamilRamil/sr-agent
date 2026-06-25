# Research: SR-agent Technical Decisions

*Phase 0 output for `/speckit-plan`. All NEEDS CLARIFICATION resolved.*

---

## 1. Memory Architecture

**Decision**: Two separate stores — Knowledge Base (human-only writes) + Episodic Memory (orchestrator-only writes). No shared store.

**Rationale**: Knowledge Base has no LLM write path → retrieval poisoning surface = zero → full semantic retrieval pipeline is safe. Episodic Memory has LLM write path → semantic search is a retrieval poisoning vector → explicit addressing only (`load(project_id, target)`).

**Alternatives considered**:
- Single vector store for all memory: rejected — LLM write path poisons retrieval ranking
- Semantic search on Episodic Memory with trust-weighted ranking: partially mitigates but doesn't eliminate poisoning (an injected record with `source_type: tool_output` can still rank high)

---

## 2. Memory Integrity: HMAC-SHA256

**Decision**: Every memory record signed with `HMAC-SHA256(content + source_type + tool + target + timestamp + session_id + project_id, secret_key)`. Secret key held only by orchestrator. Records failing HMAC verification are silently dropped before reaching LLM context.

**Rationale**: Attacker who compromises the memory store directly (not via agent) doesn't know the secret key → HMAC mismatch → records dropped. Closes direct tamper vector.

**Alternatives considered**:
- No integrity check: rejected — spec requirement SC-004 (100% invalid-signature records rejected)
- Ed25519 signatures: stronger but adds key management complexity; HMAC sufficient for this threat model where secret is never exported
- Content hash only (no key): rejected — attacker can rehash after modification

---

## 3. Memory Trust Hierarchy (source_type)

**Decision**:
```python
TRUST_HIERARCHY = {
    "human_input":          4,
    "tool_output":          3,
    "external_llm_output":  2,
    "human_relayed_tool":   2,  # transitional MVP
    "llm_inference":        1,
}
```

**Rationale**: Orchestrator applies different validation rules per source_type. Only `human_input` can set `status: verified_safe / skip_analysis / audit_complete` (human gate). This stops LLM from self-authorizing critical status changes.

**Alternatives considered**:
- Binary trusted/untrusted: too coarse — `tool_output` (deterministic) differs meaningfully from `llm_inference`
- No source_type, HMAC only: HMAC proves the record went through the write path, not what generated it

---

## 4. Append-Only Memory Log

**Decision**: `update_memory` and `delete_memory` do not exist in the orchestrator's action schema. Corrections are new records with `supersedes: "<record_id>"`. Only `human_input` can supersede existing records.

**Rationale**: Removes the attack surface of a compromised agent rewriting its own memory. Full audit trail preserved.

**Alternatives considered**:
- Allow LLM to update with human confirmation: rejected — out-of-band confirmation channel itself could be spoofed; simpler to forbid entirely

---

## 5. Knowledge Base Retrieval Pipeline

**Decision**: 3-model pipeline applies only to Knowledge Base:
```
query-expansion (qmd-query-expansion-17B)
    ↓
embedding (gemma-300M) → vector search
    ↓
reranker (qwen-reranker-0.6b) → final ranking
```

**Rationale**: Knowledge Base has no LLM write path → retrieval poisoning risk = zero → semantic search is safe and beneficial for finding relevant vulnerability patterns.

**Alternatives considered**:
- BM25 keyword search: simpler but misses semantic matches (e.g., "balance before call" → reentrancy)
- Apply same pipeline to Episodic Memory: rejected — retrieval poisoning vector (see decision #1)

---

## 6. Structured LLM Outputs + [DATA] Delimiter

**Decision**: All LLM outputs validated against strict JSON schema. All external content (tool outputs, memory records, on-chain data) wrapped in `[DATA START tool=X]...[DATA END]` before entering LLM context. Delimiter injection detected and flagged (not blocked) by Guardrails sanitizer.

**Rationale**: Even if delimiter injection succeeds and LLM "believes" an injected instruction — the action schema limits what can be expressed. Damage is bounded to what the schema permits.

**Alternatives considered**:
- Natural language outputs: rejected — no formal way to validate or bound actions
- Block on any suspicious content: rejected — Solidity contracts legitimately contain Base64, encoded data; blocking breaks analysis

---

## 7. 3-Stage Audit Architecture

**Decision**: Stage 1 (Discovery, ReAct) → Stage 2 (CheckRunner, for-loop) → Stage 3 (Synthesis, ReAct).

**Rationale**:
- Stage 1: scope unknown upfront → needs adaptive ReAct
- Stage 2: fixed target list from Stage 1 → deterministic for-loop is cheaper and safer (Qwen3-4B local)
- Stage 3: combination space unknown → needs ReAct with extended reasoning

**Alternatives considered**:
- Single ReAct for all stages: Stage 2 becomes unpredictable and expensive on Opus
- Stage 2 on Opus API: ~$0.22/audit minimum just for Stage 2 calls; fine-tuned Qwen3-4B achieves ASR 1.7% locally

---

## 8. Model Routing

**Decision**:
```
Stage 1 Discovery      → Claude Opus (API, extended thinking always on)
Stage 2 CheckRunner    → Qwen3-4B fine-tuned (local, Ollama/llama.cpp)
Stage 3 Synthesis      → Claude Opus (API, extended thinking always on)
PoC writing            → Qwen3-Coder (local) / Claude Sonnet (API fallback)
Conjunction check      → pure code, no model
Guardrails evaluation  → pure code, no model
Episodic Memory I/O    → no model (explicit addressing)
Knowledge Base         → 3-model retrieval pipeline
```

**Rationale**: Extended thinking on Stage 1/3 is a security requirement — thinking trajectories are 5× more MI-resistant than standard prompting (2503.16248v3). Local Qwen3-4B for Stage 2 keeps client code off external APIs and reduces cost.

**Alternatives considered**:
- All stages on Claude Sonnet: cheaper but no thinking trajectory MI resistance data
- GPT-4o for Stage 2: external API = client code leaves machine; Qwen3-4B local preferred for NDA contracts

---

## 9. Tool Classification + Out-of-Band Confirmation

**Decision**: READ-ONLY tools (read_file, search_code, build_graph, run_slither, run_mythril, analyze_transactions, decompile_bytecode) run freely. WRITE/EXECUTE tools (write_poc, run_tests, deploy_test_contract) require out-of-band human confirmation before execution.

**Rationale**: Irreversible actions cannot be undone if agent is compromised. Out-of-band channel is not accessible via LLM context manipulation.

**Alternatives considered**:
- Confirmation via same chat channel: rejected — the channel could itself contain injected "confirmations"
- No confirmation for write_poc (just test writing): write_poc generates Solidity code that will be executed — still needs human review

---

## 10. Tool Supply Chain Protection

**Decision**: Tool descriptions stored as string constants in Python source code. SHA256 hash of each description committed to `TOOL_REGISTRY`. Orchestrator verifies hash at every startup.

**Rationale**: MCP server could inject instructions into tool description. Hash comparison in orchestrator code (not LLM) catches any mismatch.

**Alternatives considered**:
- Runtime description fetch from MCP, no hash check: rejected — supply chain attack vector
- GPG-signed MCP tool manifests: overly complex for MVP; code-level constants simpler and equally effective

---

## 11. Severity Validation: Conjunction Check

**Decision**: Deterministic code (no LLM) checks: if ANY mitigation present → severity ≤ Medium. If ≥4 preconditions active + no mitigations → severity ≥ High. Overrides LLM severity assignment.

**Rationale**: Severity Centrality Bias (SCB): LLM systematically pulls Low/Critical toward Medium. Critical findings may be downgraded — a $M risk. Conjunction check from AttackPathGNN corrects this deterministically.

**Alternatives considered**:
- Ask LLM to re-evaluate severity: doesn't eliminate SCB, just repeats it
- Manual human review of all severities: doesn't scale; conjunction check filters to only Human-needed cases

---

## 12. Mock Detection

**Decision**: Static string pattern matching on PoC test code (no LLM). Patterns: `vm.mockCall`, `vm.mockCallExpects`, `vm.assume`, `MockERC20`, `MockOracle`, `deal(`, `hoax(`. Detection → automatic escalation to human (status: `mock_review`).

**Rationale**: PoC test may "reproduce" vulnerability only due to unrealistic mock assumptions. Human review needed to confirm mock assumptions are realistic.

**Alternatives considered**:
- LLM review of test realism: expensive, subjective, and itself a potential injection vector
- Block tests with mocks entirely: would prevent legitimate mock usage in test isolation

---

## 13. RPC Provider

**Decision**: Alchemy (archive node + debug/trace API) + Tenderly (simulation API for PoC verification).

**Rationale**: Alchemy provides archive history needed for state-at-block analysis and `debug_traceTransaction` for internal call tracing. Tenderly simulation verifies exploits on mainnet fork without actual deployment — faster than local Anvil for mainnet-fork scenarios.

**Alternatives considered**:
- Infura: no trace API on standard plans
- Self-hosted node: separate infrastructure project, out of MVP scope
- Tenderly only: no direct RPC, needs Alchemy for raw data

---

## 14. Sandboxing

**Decision**: Docker ephemeral containers for Slither, Mythril. Foundry runs inside Docker → Anvil → EVM (3 isolation layers). No network access in containers. Destroyed after each run.

**Rationale**: Static analyzer (Slither) processes untrusted Solidity code. A malicious contract could attempt to exploit the analyzer. Docker prevents filesystem and network access.

**Alternatives considered**:
- Process-level isolation (no Docker): insufficient — no filesystem isolation
- Permanent containers: state leakage between audits

---

## 15. Escalation to Human (8 Triggers)

**Decision**: Deterministic triggers evaluated in Guardrails after every LLM action:
1. `irreversible_action` — WRITE/EXECUTE tool requested
2. `memory_status_change` — verified_safe / skip_analysis / audit_complete
3. `critical_finding` — severity == Critical
4. `unverified_high` — severity >= High + status == unverified
5. `mock_test` — PoC uses mock patterns
6. `contradicting_findings` — same location, different verdicts across sessions
7. `unknown_pattern` — no bastet_tag + zero preconditions active
8. `resource_limit_approaching` — token_budget > 85% or iterations > 90% of max

**Rationale**: Each trigger represents a case where autonomous agent decision has unacceptable error cost. Human is the final authority for irreversible, high-stakes, or uncertain situations.

**Alternatives considered**:
- LLM decides when to escalate: not safe — a compromised LLM would suppress escalation
- Escalate everything: not useful — defeats purpose of automation

---

## 16. File Bridge Pattern (External LLM Integration)

**Decision**: External LLM writes results to `/shared/results/{tool}-{target}.json`. Orchestrator reads as file. `source_type: external_llm_output` (trust level 2).

Upgrade path: `human_relayed_tool` (manual paste) → `external_llm_output` (file bridge) → `tool_output` (direct API, HMAC from orchestrator).

**Rationale**: Allows using Claude skills (security-auditor, spec-kit) without exposing orchestrator's HMAC key to the external session. Architecture remains unchanged as integration matures.

**Alternatives considered**:
- Direct API call from orchestrator to external LLM: requires orchestrator to hold credentials for all external tools; file bridge is simpler and auditable

---

## 17. Principal Isolation

**Decision**: Memory scoped by `(user_id, platform)` pair. Episodic Memory stored under `memory/{project_id}/`. Retrieval only returns records matching current principal's project_id. No cross-project semantic search.

**Rationale**: One injected record in memory of Principal A must not affect Principal B's audit (spec SC-005, FR-012, FR-013). Directory-level isolation enforced by orchestrator before HMAC check.

**Alternatives considered**:
- Single shared memory with ACL: ACL can be misconfigured; directory-level isolation is simpler and auditable

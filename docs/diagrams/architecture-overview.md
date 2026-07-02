# Architecture overview — what's actually wired up

Two distinct things live in this codebase: (1) the **live batch-audit path**, reachable from the `sr-agent` CLI today, and (2) a **built-but-orphaned agent loop** (`orchestrator/loop.py` + friends) that nothing currently calls. The chat-mode spec (`specs/003-interactive-chat-mode/`) is meant to wire (2) up properly — it isn't built yet.

```mermaid
flowchart TB
    subgraph CLI["sr_agent/cli.py"]
        C1["audit / resume"]
        C2["confirm"]
        C3["relay"]
        C4["memory"]
    end

    subgraph LIVE["Live batch-audit path (wired)"]
        PIPE["orchestrator/pipeline.py<br/>start_audit / resume_audit"]
        S1["planner/stage1.py<br/>deterministic red flags + SIG"]
        S2["planner/stage2.py<br/>local model OR relay"]
        S3["planner/stage3.py<br/>severity correction + SIG combine"]
        TOOLS_RO["tools/static_analysis.py<br/>tools/smartgraphical.py<br/>(Slither/Mythril/SG, via sandbox)"]
        LOCAL["llm_core/local_client.py<br/>Ollama"]
        RELAY["orchestrator/relay.py<br/>manual file relay"]
        MEM["memory/episodic.py<br/>HMAC-signed JSONL"]
        REPORT["io/report.py"]
    end

    subgraph ORPHAN["Built but NOT invoked by anything"]
        LOOP["orchestrator/loop.py<br/>AgentAction ReAct loop"]
        ACT["orchestrator/action.py<br/>validate_action + REQUIRES_OOB_CONFIRMATION"]
        CTX["orchestrator/context.py<br/>DATA-wrapping"]
        CKPT["orchestrator/checkpoint.py"]
        CLAUDE["llm_core/claude_client.py<br/>paid API, unused by design"]
    end

    subgraph WRITE["tools/write_execute.py + tools/sandbox.py"]
        WPOC["write_poc()"]
        RTEST["run_tests()"]
        DEPLOY["deploy_test_contract()"]
    end

    subgraph ADHOC["scripts/poc_queue_runner.py — standalone, bypasses ACT"]
        RUNNER["poc_queue_runner.py"]
    end

    C1 --> PIPE
    C2 --> CONF["orchestrator/confirmation.py"]
    C3 --> RELAY
    C4 --> MEM

    PIPE --> S1 --> S2 --> S3 --> REPORT
    S1 --> TOOLS_RO
    S2 --> LOCAL
    S2 --> RELAY
    S3 --> MEM

    LOOP --> ACT
    LOOP --> CTX
    LOOP --> CKPT
    LOOP --> CLAUDE
    LOOP -.would call.-> WPOC
    ACT -.gates.-> WPOC
    ACT -.gates.-> RTEST
    ACT -.gates.-> DEPLOY

    RUNNER --> LOCAL
    RUNNER ==bypasses ACT==> WPOC
    RUNNER --> RTEST
```

## Reading this

- **Only the `LIVE` subgraph is reachable from the CLI today.** `sr-agent audit` drives Stage 1 → Stage 2 → Stage 3 → report, using either the local Ollama model or the manual relay bridge, never `orchestrator/loop.py`.
- **`ORPHAN` is real, tested code** (`validate_action`, `REQUIRES_OOB_CONFIRMATION = {write_poc, run_tests, deploy_test_contract}`, DATA-wrapping via `context.wrap_data`) — it's the correctly-gated design for an interactive agent loop. It depends on `llm_core/claude_client.py` (paid Anthropic API), which the project avoids using, and nothing imports `orchestrator/loop.py` — confirmed by `grep`, zero call sites outside its own module.
- **`write_poc`/`run_tests` are registered in `tools/registry.py` as `write_execute` class, requiring out-of-band confirmation** (`_D_WRITE_POC`: *"Requires prior human out-of-band confirmation"*). That gate is enforced by `orchestrator/action.py::validate_action` — but only code paths that call `validate_action` get the gate. Today that's only `orchestrator/loop.py` (orphaned).
- **`scripts/poc_queue_runner.py` calls `write_poc`/`run_tests` directly**, importing them straight from `sr_agent.tools.write_execute` — it never touches `validate_action` or the confirmation flow. This was a deliberate, logged simplification (see the script's module docstring) for a low-risk case: writing test files into a local git clone and running `forge test --network none` in an ephemeral container, not touching funds or a live network. It is not what the registered tool description promises, and a real chat-mode implementation must not repeat this shortcut for anything the registry marks `write_execute`.

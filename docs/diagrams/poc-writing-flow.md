# PoC-writing flow — current execution (scripts/poc_queue_runner.py)

This is the mechanism running in the background right now, writing PoCs for the Strata bug-bounty findings/leads. It is **not** the chat-mode orchestrator from `specs/003-interactive-chat-mode/` — that isn't built yet. It's a standalone script that sequentially drives two existing tool modules (`llm_core/local_client.py`, `tools/write_execute.py` + `tools/sandbox.py`), reading a fixed queue and writing one PoC at a time.

```mermaid
sequenceDiagram
    participant Q as poc_queue.json
    participant R as poc_queue_runner.py
    participant L as LocalClient (Ollama)
    participant W as write_poc()
    participant D as DockerSandbox
    participant F as Strata repo<br/>audit/poc/*.t.sol

    R->>Q: load all 22 items at startup
    loop for each item, one at a time
        R->>R: build prompt: finding wrapped in<br/>[DATA START]..[DATA END]
        R->>L: generate(prompt)
        L-->>R: draft Solidity source<br/>(external_llm_output, trust tier 2)
        R->>R: strip markdown fences<br/>(sanitize before write, never execute)
        R->>W: write_poc(finding_id, generator=...)
        W->>F: write PoC_<id>.t.sol
        R->>D: run_tests(project_dir, test_path)
        D->>D: docker run --rm --network none<br/>--cap-drop ALL forge test --match-path
        D-->>R: exit_code, stdout, stderr
        R->>R: append JSONL: {event, finding_id,<br/>passed, exit_code, tails}
    end
    R->>R: log {"event": "done"}
```

## What's real here vs. what's simplified

- **Real, matches the project's trust model**: the finding description is embedded as `[DATA START]..[DATA END]` in the prompt — the prompt text itself instructs the local model not to follow imperative text inside that block. The runner's control flow is fixed Python, not driven by the model's output; the model only ever produces a Solidity string that gets sanitized (fence-stripped) and written to disk.
- **Real**: `run_tests` executes only inside `DockerSandbox` — `--network none`, `--cap-drop ALL`, ephemeral container, matches the sandbox contract used everywhere else in the project (Slither/Mythril runs use the same primitive).
- **Simplified, on purpose, logged in the script's docstring**: no out-of-band `sr-agent confirm` gate per item, and `validate_action`/`REQUIRES_OOB_CONFIRMATION` are bypassed entirely — see [architecture-overview.md](architecture-overview.md) for why this specific script gets away with it (low blast radius: local git clone, sandboxed, no funds, no live network) and why that exception must **not** be copied into the real chat-mode implementation.
- **Not present at all**: no memory-record writing, no finding-status changes, no escalation triggers — the runner only writes test files and appends to its own progress log. It cannot mark anything `verified_safe` or otherwise touch episodic memory, so even a fully adversarial local-model output has nowhere to escalate to.
- **Sequential by design**: one item at a time, not parallel — a stuck/slow local-model call or a hung `forge test` blocks the next item rather than corrupting shared state, at the cost of total wall-clock time for the full queue.

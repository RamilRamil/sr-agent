# Diagrams

Architecture and execution-flow diagrams for SR-agent, reflecting **what is actually wired up and running today** — not the target design. Mermaid source, renders in GitHub/VS Code/most markdown viewers.

- [architecture-overview.md](architecture-overview.md) — module map: what's connected to the live CLI path, what's built but orphaned (not invoked by anything).
- [poc-writing-flow.md](poc-writing-flow.md) — exact current execution flow for `scripts/poc_queue_runner.py`, the background PoC writer.

Update these when the wiring changes — a diagram that lies about what's connected is worse than no diagram.

# Quickstart: Two-Agent Audit Sessions (spec 019)

Point a session at a project AND an audit report, choose a main agent for the work and an optional additional agent for the hard (escalated) parts — all from the frontend.

## In the UI

1. **Settings → Main agent**: method (Local / Gemini) + endpoint/model (+ key for Gemini). This is what answers each turn.
2. **Settings → Additional agent** (optional): method + endpoint/model (+ key). Consulted automatically when a turn escalates. Leave it **Off** to keep today's manual hand-off.
3. **New session**: fill **Project path** (external target folder) and **Audit file** (external report; optional). Start.
4. Chat: ask "confirm finding H-01" — the agent already has the report as reference (you didn't paste it).

## What stays guaranteed

- The report is **reference data only** — its text can never make the agent act against your instruction.
- The additional agent's answers are **untrusted model output**; anything privileged/irreversible it proposes **still pauses for your confirmation**.
- With Main = Local, no Additional, no report → **fully offline**, no hosted dependency.
- API keys are **write-only** — never shown back, logged, or persisted.

## Integration scenarios (→ acceptance)

1. **US1 / SC-001, SC-002** — start with a report path; the agent reflects it; report-embedded instructions are ignored.
2. **US2 / SC-004** — switch Main between Local and Gemini; keys never returned.
3. **US3 / SC-003, SC-005** — with an Additional agent, an escalated turn is auto-answered by it; a privileged action still pauses for confirmation; with none configured, escalation falls back to the manual relay.
4. **SC-006** — local Main + no Additional + no report → full offline suite green.

## Run the tests (offline, no key, no network)

```bash
pytest tests/unit/test_report_context.py tests/unit/test_agent_slots.py \
       tests/integration/test_additional_agent_escalation.py \
       tests/security/test_report_not_instruction.py -q
```

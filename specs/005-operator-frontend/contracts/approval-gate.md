# Contract: Approval Gate (FR-009 — the security heart)

The one place a convenience GUI could defeat the project: turning out-of-band human confirmation into a reflexive click. Constitution II forbids it. This contract defines how the UI can host approval **without** weakening the gate, and the property a test must prove.

## The rule

A privileged/irreversible action (any `write_execute`-class action, any privileged-status change) reaches the confirmation queue and **does not execute** until a **deliberate, explicit** operator act. The UI may host that act, but it MUST NOT be:
- **auto-approve** (no policy, timer, or default approves anything), or
- **a single navigation-equivalent click** (approving must be structurally distinct from browsing — you cannot approve by clicking around).

## The mechanism (two-step, same record as the CLI)

1. The turn pauses at the kernel gate and files a confirmation via the existing `confirmation.py` primitives (`request_confirmation`) — identical to the CLI path. It appears in `GET /api/confirmations` with its `ConsequentialActionNotice` (exactly what would run).
2. To approve, the operator must **fetch the item's notice** (`GET /api/confirmations` / an item view), which issues a short-lived **`confirm_token`** bound to that confirmation id. Approval (`POST /api/confirm/{id}` with `{confirm_token, decision:"approve"}`) writes the **same** out-of-band confirmation record the CLI's `sr-agent confirm --approve` writes. Only then does the kernel's resume path run `execute_confirmed`.
3. A `POST /api/confirm` **without** a valid `confirm_token` (i.e. without having viewed the notice) is rejected — a bare or replayed call never approves.

The `confirm_token` is not security-through-obscurity theatre; it encodes "the human saw the specific consequential-action notice for this specific id before approving," which is the deliberate-act requirement.

## The tested property (`tests/frontend/test_approval_gate.py`)

- **G1**: a `write_execute` turn via `/message` returns `paused_confirmation` and does NOT execute; the action shows in `/api/confirmations`.
- **G2**: `POST /api/confirm/{id}` with no/invalid `confirm_token` does NOT approve (the action stays pending / is not executed).
- **G3**: only a `confirm_token` issued after fetching that id's notice, plus `decision:"approve"`, causes execution — via the kernel's `execute_confirmed`, never a UI-side shortcut.
- **G4**: there is NO endpoint or code path that approves a pending action without step 2 (no auto-approve; grep/audit + test).

## Fallback

The CLI path (`sr-agent confirm <id> --approve`) remains fully valid — the UI approval is the *same* record through the *same* gate, so an operator can always approve from the terminal instead. The UI can also simply **display** the exact `sr-agent confirm` command for an operator who prefers the separate channel.

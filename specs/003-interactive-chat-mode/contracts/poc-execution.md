# Contract: PoC execution (audit-pack)

How a PoC produced in chat mode is written and run. This is **audit-pack** content (Foundry-specific) — it sits on the pack side of the kernel/pack boundary (Constitution III) and MUST NOT be hardwired into `orchestrator/loop.py`. Source of the mechanics: research R11.

## Output location

- PoCs are written to `<audit_root>/audit/poc/<ident>.t.sol` (the target repo's `audit/poc/` dir), NOT into the kernel or the SR-agent repo.
- `<ident>` is a Solidity-safe slug of the finding id (existing `write_execute.py::_ident`).

## Foundry discovery — the gotcha this contract exists to encode

`forge test` discovers and compiles tests only under the profile's `test` dir. The target's default `foundry.toml` uses `src='contracts'`, `test='test'`, so a file in `audit/poc/` is **never compiled** and `--match-path audit/poc/X.t.sol` yields "No tests to run". `--match-path` filters already-discovered tests; it cannot add compile paths.

**Required mechanism** — one of (equivalent):
- Profile: add `[profile.poc]` with `test = "audit/poc"` to the target's root `foundry.toml`, run `FOUNDRY_PROFILE=poc forge test --match-path audit/poc/X.t.sol`; or
- Env override (no toml edit): `FOUNDRY_TEST=audit/poc forge test --match-path audit/poc/X.t.sol`.

Both keep the project root, `src`, `libs`, and remappings intact. A **second `foundry.toml`** under `audit/` as an alternate root is FORBIDDEN — it makes `src`/`lib`/remappings relative to `audit/` and breaks the `contracts/...` and `lib/forge-std` imports.

## Compilation settings

- Inherit `via_ir` from the default profile (the target's contracts require `via_ir=true`; disabling risks stack-too-deep). Cost: slow first compile — accepted; the build cache amortizes it across PoCs in a run.
- Compilation and execution happen only inside `DockerSandbox` (`--network none`, `--cap-drop ALL`, ephemeral) — the generator's Solidity output is untrusted data, never executed on the host.

## Timeouts

- Model generation timeout ≥ 600s per PoC (measured ~7–8 min on `qwen2.5-coder:3b`; the old 180s default caused the observed `write_failed` timeouts). Prefer relay/stronger model for real PoC drafting (chat-mode escalation path).
- `forge test` sandbox timeout stays the `run_tests` default (currently 180s) unless a PoC needs longer.

## Status reporting (feeds R12 roadmap)

`run_tests` maps to a mechanical status event only:
- compile failure → `errored` (not `failed`).
- compiled + test assertion failed → `failed`.
- compiled + test passed → `passed` — meaning "a reproduction exists", NOT "finding confirmed/safe".
A `passed` PoC does NOT flip any finding's security verdict; that remains a `REQUIRES_HUMAN_CONFIRMATION` action (Constitution II).

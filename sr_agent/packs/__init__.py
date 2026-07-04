"""Capability packs (feature 004).

A pack is task-specific capability the task-agnostic kernel consumes through the
`CapabilityPack` interface (`sr_agent/orchestrator/pack.py`). Everything under
`sr_agent/packs/` is pack code; nothing outside it (except the composition root
`sr_agent/cli.py`) may import from here — the boundary is enforced by
`tests/architecture/test_kernel_pack_boundary.py`. Pack→kernel imports are
expected; kernel→pack imports are forbidden.

Exactly one pack exists today (`audit`). No dynamic registry/discovery/loader
(Constitution III, YAGNI) — the pack is wired explicitly in `cli.py`.
"""

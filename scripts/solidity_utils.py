"""Feature 033 — shared low-level Solidity helpers.

The deterministic compile-fixers (scripts/solidity_fixers.py) pull in a handful of
low-level helpers that are ALSO used by poc_queue_runner.py's grounding / symbol-index /
scaffold code. Leaving them in poc_queue_runner.py and importing them into the fixer
module would create a cycle (poc_queue_runner re-exports the fixers from that module).
This module is the cycle-breaker: BOTH poc_queue_runner.py and solidity_fixers.py import
from here, and this module imports NEITHER of them.

Pure moves — the logic is byte-identical to its previous home in poc_queue_runner.py.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

POC_SUBDIR = "audit/poc"            # PoCs live here; needs FOUNDRY_TEST override

# Directories that are never part of the contest's own tracked source (build output,
# vendored deps, our own artifacts) — excluded when resolving/globbing project .sol files.
_SKIP_DIRS = {"out", "cache_forge", "node_modules", "lib", "artifacts"}


def _tracked_sol(project: Path) -> set[Path]:
    """Git-tracked .sol files — the ORIGINAL project. Excludes anything we (or a
    prior skill run) generated but never committed, so grounding/scaffold only ever
    uses the contest's own code, never our own PoCs (honesty of the workability test)."""
    try:
        out = subprocess.run(["git", "-C", str(project), "ls-files", "*.sol"],
                             capture_output=True, text=True, timeout=15)
        return {(project / line).resolve() for line in out.stdout.splitlines() if line.strip()}
    except Exception:
        return set()


def _path_for(file_map: str, name: str) -> str:
    """The real import path for a contract/interface name, from [project_files]."""
    for line in file_map.splitlines():
        if line.startswith(f"{name}: "):
            return line.split(": ", 1)[1]
    return ""


def _strip_comments(sol: str) -> str:
    sol = re.sub(r"/\*.*?\*/", "", sol, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", sol)


_SCAFFOLD_CONTRACT_RE = re.compile(r"\b(?:abstract\s+)?contract\s+(\w+)\s*(?:is\b|\{)")
_SCAFFOLD_IS_RE = re.compile(r"\bcontract\s+\w+\s+is\s+([^{]+?)\s*\{")


def _scaffold_base_name(text: str) -> str | None:
    """The concrete LEAF contract to inherit from a test_scaffold file — the contract
    DECLARED in it that is not itself a base of another in-file contract (e.g. `DemoTest`,
    NOT the imported `DemoDeploy` it extends). Live H-01 run (2026-07-14): given the raw
    scaffold file, the model inherited the grandparent base and lost setUp + all the deployed
    state (`sharesCooldown`, the exit constants) → a cascade of `Undeclared identifier`. The
    leaf is what actually has setUp + the state; Solidity convention puts bases first, leaf last."""
    text = _strip_comments(text or "")
    decls = _SCAFFOLD_CONTRACT_RE.findall(text)
    if not decls:
        return None
    used_as_base: set[str] = set()
    for bases in _SCAFFOLD_IS_RE.findall(text):
        used_as_base.update(b.strip() for b in bases.split(","))
    leaves = [n for n in decls if n not in used_as_base]
    return leaves[-1] if leaves else decls[-1]

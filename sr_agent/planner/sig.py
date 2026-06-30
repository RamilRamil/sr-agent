"""State Interference Graph (T053).

Deterministic, lightweight (no Slither needed): for each function, derive the
set of state variables it reads and writes, and whether it makes an external
call. Two functions *interfere* when one writes state the other touches; a
reentrancy edge exists when an externally-calling function shares state with
another. Stage 3 uses get_filtered_pairs to combine only findings whose
functions actually interact, instead of "same file".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sr_agent.planner.stage1 import extract_functions

_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_WRITE_RE = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\])*\s*(?:=(?![=>])|\+=|-=|\*=|/=)")
_EXTERNAL_CALL = (".call", ".delegatecall", ".transfer(", ".send(", ".staticcall")
_DECL_SKIP = (
    "function", "modifier", "event", "struct", "enum", "constructor",
    "using", "import", "pragma", "error", "receive", "fallback", "return",
)


@dataclass
class FunctionNode:
    name: str
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)
    has_external_call: bool = False


@dataclass
class StateInterferenceGraph:
    functions: dict[str, FunctionNode] = field(default_factory=dict)

    def interferes(self, a: str, b: str) -> bool:
        """True if functions a and b touch shared mutable state."""
        fa, fb = self.functions.get(a), self.functions.get(b)
        if not fa or not fb:
            return False
        return bool(
            (fa.writes & (fb.reads | fb.writes)) or (fb.writes & (fa.reads | fa.writes))
        )

    def can_reenter(self, a: str, b: str) -> bool:
        """True if a makes an external call and shares state with b."""
        fa = self.functions.get(a)
        return bool(fa and fa.has_external_call and self.interferes(a, b))


def extract_state_vars(source: str) -> set[str]:
    """Return contract-level (state) variable names via brace-depth tracking."""
    state_vars: set[str] = set()
    depth = 0
    buf: list[str] = []
    for ch in source:
        if ch == "{":
            depth += 1
            buf = []
        elif ch == "}":
            depth -= 1
            buf = []
        elif ch == ";":
            if depth == 1:
                name = _decl_var_name("".join(buf))
                if name:
                    state_vars.add(name)
            buf = []
        elif depth == 1:
            buf.append(ch)
    return state_vars


def _decl_var_name(stmt: str) -> str | None:
    stmt = stmt.strip()
    if not stmt:
        return None
    first = _IDENT_RE.match(stmt)
    if first and first.group(0) in _DECL_SKIP:
        return None
    decl = stmt.replace("=>", " ").split("=")[0]  # drop initializer, keep mapping
    ids = _IDENT_RE.findall(decl)
    return ids[-1] if ids else None


def build_sig(source: str) -> StateInterferenceGraph:
    """Build the interference graph for one Solidity source file."""
    state_vars = extract_state_vars(source)
    sig = StateInterferenceGraph()

    for name, body, _line in extract_functions(source):
        node = FunctionNode(name=name)
        node.has_external_call = any(tok in body for tok in _EXTERNAL_CALL)
        written = {m for m in _WRITE_RE.findall(body) if m in state_vars}
        referenced = {tok for tok in _IDENT_RE.findall(body) if tok in state_vars}
        node.writes = written
        node.reads = referenced - written
        sig.functions[name] = node

    return sig


def get_filtered_pairs(finding_locations: list[str], sig: StateInterferenceGraph) -> list[tuple[str, str]]:
    """Return interacting (loc_a, loc_b) finding-location pairs for Stage 3.

    Locations are "file:function"; pairing is by interfering functions.
    """
    pairs: list[tuple[str, str]] = []
    for i in range(len(finding_locations)):
        for j in range(i + 1, len(finding_locations)):
            fn_a = finding_locations[i].split(":")[-1]
            fn_b = finding_locations[j].split(":")[-1]
            if sig.interferes(fn_a, fn_b):
                pairs.append((finding_locations[i], finding_locations[j]))
    return pairs

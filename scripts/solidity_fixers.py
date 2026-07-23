"""Feature 033 — the deterministic Solidity compile-fixer layer.

The six deterministic `code -> (code, changed)` transforms the PoC harness applies to
repair mechanical compile errors WITHOUT a model call, plus the five named
transform-application sequence-functions (one per site) that the two repair loops in
poc_queue_runner.py call. Consolidating them here gives each fixer ONE home: the
recurring import-path bug class (which surfaced 3× because the fixers were scattered and
two near-duplicate loops hand-inlined their sequences) now has a single place to fix.

Imports ONLY scripts.solidity_utils (the shared low-level helpers) — never
poc_queue_runner.py — so the import graph stays acyclic (pqr imports this module and
re-exports the fixers transitionally; this module must not import pqr back).

The sequence-functions are NOT unified — each keeps its own separate function and exact
per-site sequence (order + per-call args). Merging them is a separate, measured change
(spec 034). This module is a pure move: the logic is byte-identical to its previous home
in poc_queue_runner.py.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from scripts.solidity_utils import (
    POC_SUBDIR, _SKIP_DIRS, _path_for, _scaffold_base_name, _tracked_sol,
)


def _brace_block(s: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _fix_setup_override(code: str) -> tuple[str, bool]:
    """Remove a PoC's own setUp() (which would 4334 against a non-virtual base) and
    re-inject its statements at the top of the first test function. Returns
    (code, changed)."""
    m = re.search(r"function\s+setUp\s*\([^)]*\)[^{]*\{", code)
    if not m:
        return code, False
    close = _brace_block(code, m.end() - 1)
    if close < 0:
        return code, False
    body = code[m.end():close]
    stmts = "\n".join(l for l in body.splitlines() if "super.setUp" not in l).strip()
    code2 = (code[:m.start()] + code[close + 1:]).replace("\n\n\n", "\n\n")
    tm = re.search(r"function\s+test\w*\s*\([^)]*\)[^{]*\{", code2)
    if tm and stmts:
        ins = tm.end()
        indented = "\n        " + stmts.replace("\n", "\n        ")
        code2 = code2[:ins] + indented + code2[ins:]
    return code2, True


def _fix_import_paths(code: str, project: Path, base_dir: Path | None = None) -> tuple[str, bool]:
    """Fix mechanical codegen issues, LINE BY LINE so non-import lines are never
    touched: (a) a bare `SPDX-License-Identifier` line missing its `//` (a 2314
    syntax error), and (b) an import with the right target but wrong relative depth
    (`../../../` vs `../../`) — we know the real paths, so rewrite to the exact
    relpath from the importing file's dir. Remapped/library imports (@openzeppelin/…,
    forge-std/…) are left as-is; git-tracked (original) files are preferred.

    `base_dir` is the directory the imports are relative TO — defaults to audit/poc/
    (where drafted PoCs live). The scaffold-synthesis base lives a level deeper
    (audit/poc/_synth/), so a model-written parent-scaffold/missing-type import is
    off by one `../`; passing `base_dir=synth_dir` rewrites it to the right depth
    (GLM-5.2 live: the only scaffold-synthesis failure was exactly this off-by-one)."""
    poc_dir = base_dir if base_dir is not None else project / POC_SUBDIR
    tracked = _tracked_sol(project)
    changed = False
    out: list[str] = []
    for line in code.splitlines():
        s = line.lstrip()
        if s.startswith("SPDX-License-Identifier"):
            line = line.replace("SPDX-License-Identifier", "// SPDX-License-Identifier", 1)
            changed = True
        elif s.startswith("import"):
            mo = re.search(r'["\']([^"\']+\.sol)["\']', line)
            if mo:
                path = mo.group(1)
                if not (path.startswith("@") or path.startswith("forge-std")):
                    cands = [p for p in project.rglob(Path(path).name)
                             if p.is_file() and not _SKIP_DIRS & set(p.relative_to(project).parts)]
                    if tracked:
                        cands = [p for p in cands if p.resolve() in tracked] or cands
                    if cands:
                        correct = os.path.relpath(cands[0], poc_dir)
                        if correct != path:
                            line = line.replace(path, correct)
                            changed = True
        out.append(line)
    return "\n".join(out), changed


# solc 9553: passing a bare `address` where a contract/interface type is required.
# `_ADDR_IFACE_LOC_RE` (type + the flagged source LINE number) drives the deterministic
# `_fix_address_interface` transform — keyed on the line number, not the line CONTENT, since forge
# truncates the shown line (`address(shar…`). (The type-only `_ADDR_IFACE_RE` that drives the
# `_targeted_hints` text hint stays in poc_queue_runner.py — it is not a fixer.)
_ADDR_IFACE_LOC_RE = re.compile(
    r"conversion from address to contract (\w+) requested\.\s*-->\s*\S+?:(\d+):")


def _fix_address_interface(code: str, forge_output: str) -> tuple[str, bool]:
    """Feature 031: deterministically repair solc 9553 — a call passing `address(x)` where a
    contract/interface type `T` is required — by wrapping the argument as `T(address(x))` on the exact
    flagged line (line-scoped, mirroring `_fix_import_paths`' safety: touch only the flagged line).
    Idempotent (a line already wrapped as `T(address(…))` is left alone); `changed=False` when the
    forge output reports no 9553. Line-number-keyed, so it is robust to forge truncating the shown
    line. The synth repair pass uses THIS (no model); the drafting PoC gets the `_targeted_hints` hint."""
    lines = code.splitlines()
    changed = False
    for typ, ln in _ADDR_IFACE_LOC_RE.findall(forge_output):
        i = int(ln) - 1
        if 0 <= i < len(lines) and "address(" in lines[i] and f"{typ}(address(" not in lines[i]:
            lines[i] = re.sub(r"address\(([^()]*)\)", rf"{typ}(address(\1))", lines[i], count=1)
            changed = True
    return "\n".join(lines), changed


_NAMED_IMPORT_RE = re.compile(r'import\s*\{([^}]*)\}\s*from\s*["\']([^"\']+)["\']\s*;')

# solc 7576/7920 (undeclared identifier / identifier not found). Neither puts the NAME in the message —
# it is under the `^^^` caret in the source snippet. Capture the source line + the caret line (they
# share the same `|` gutter column), then slice the name from the source at the caret's column span.
_UNDECLARED_BLOCK_RE = re.compile(
    r"Error \((?:7576|7920)\):[^\n]*\n[^\n]*\n[^\n]*\n\s*\d+\s*\|(?P<src>[^\n]*)\n\s*\|(?P<caret>[^\n]*\^+[^\n]*)")


def _fix_undeclared_import(code: str, forge_output: str, symbol_index, file_map: str = "") -> tuple[str, bool]:
    """Feature 032: deterministically repair solc 7576/7920 (undeclared identifier) by AUTO-IMPORTING
    the flagged name — ONLY when it is a KNOWN top-level project symbol (`_path_for(file_map, X)`
    resolves it to a real path). A name the file-map does NOT resolve (a typo / invented API) is LEFT
    for the model (anti-invention — the project's no-invented-API discipline). Idempotent (a name
    already imported is not re-added); `changed=False` when nothing resolvable is undeclared or no
    file-map is available. The name is read from under the error's `^^^` caret (the message omits it)."""
    names: list[str] = []
    for m in _UNDECLARED_BLOCK_RE.finditer(forge_output):
        src, caret = m.group("src"), m.group("caret")
        cs, ce = caret.find("^"), caret.rfind("^") + 1
        name = src[cs:ce].strip() if 0 <= cs < ce <= len(src) else ""
        if re.fullmatch(r"[A-Za-z_]\w*", name):
            names.append(name)
    if not names:
        return code, False
    imported = set()
    for mm in _NAMED_IMPORT_RE.finditer(code):
        imported.update(n.strip() for n in mm.group(1).split(","))
    additions: list[str] = []
    for name in dict.fromkeys(names):
        if name in imported:
            continue                                   # idempotent
        path = _path_for(file_map, name)
        if not path:
            continue                                   # anti-invention: not a known top-level symbol
        additions.append(f'import {{ {name} }} from "{path}";')
        imported.add(name)
    if not additions:
        return code, False
    lines = code.splitlines()
    insert_at = 0
    for i, ln in enumerate(lines):                     # after the pragma / last existing import
        s = ln.strip()
        if s.startswith("pragma") or s.startswith("import"):
            insert_at = i + 1
    lines[insert_at:insert_at] = additions
    return "\n".join(lines), True


def _fix_nested_type_imports(code: str, symbol_index, file_map: str = "") -> tuple[str, bool]:
    """Feature 016: deterministically fix a named-import of a NESTED struct/enum type — the
    mistake the model repeats even with the right lesson in context (Error 2904). For any name
    the index knows is nested (`SymbolIndex.nested_container`), (a) remove it from the
    named-import, (b) ensure its container is imported, and (c) rewrite its BARE uses in the
    body to `Container.Type` (required: the model uses these types bare, so removing only the
    import would leave an undefined identifier). Touches ONLY unambiguously-nested names; leaves
    library/remapped/aliased/top-level/unknown imports and already-qualified uses alone.
    Returns (code, changed); idempotent. Mirrors `_fix_import_paths`' line-by-line safety."""
    if symbol_index is None:
        return code, False
    removed: dict[str, tuple[str, str]] = {}   # nested name -> (container, its import path)
    out: list[str] = []
    changed = False
    for line in code.splitlines():
        m = _NAMED_IMPORT_RE.match(line.strip())
        if not m:
            out.append(line)
            continue
        path = m.group(2)
        if path.startswith("@") or path.startswith("forge-std"):
            out.append(line)
            continue
        names = [n.strip() for n in m.group(1).split(",") if n.strip()]
        keep: list[str] = []
        for n in names:
            container = None if " as " in n else symbol_index.nested_container(n)
            if container:
                removed[n] = (container, path)
            else:
                keep.append(n)
        if len(keep) == len(names):
            out.append(line)
        else:
            changed = True
            if keep:
                indent = line[: len(line) - len(line.lstrip())]
                out.append(f'{indent}import {{ {", ".join(keep)} }} from "{path}";')
            # else: drop the line entirely (all names were nested)
    if not removed:
        return code, False
    # ensure each container is imported (dedup against names already imported anywhere)
    imported = set()
    for line in out:
        mm = _NAMED_IMPORT_RE.match(line.strip())
        if mm:
            imported.update(n.strip() for n in mm.group(1).split(","))
    additions: list[str] = []
    for container, orig_path in {c: p for c, p in removed.values()}.items():
        if container in imported:
            continue
        cpath = _path_for(file_map, container) or orig_path
        additions.append(f'import {{ {container} }} from "{cpath}";')
        imported.add(container)
    if additions:
        insert_at = 0
        for i, line in enumerate(out):
            s = line.strip()
            if s.startswith("import") or s.startswith("pragma"):
                insert_at = i + 1
        out = out[:insert_at] + additions + out[insert_at:]
    code2 = "\n".join(out)
    # rewrite BARE uses of each removed nested type → Container.Type (skip already-qualified)
    for name, (container, _p) in removed.items():
        pat = re.compile(rf'(?<![.\w]){re.escape(name)}\b')
        code2 = pat.sub(f"{container}.{name}", code2)
    return code2, True


def _fix_scaffold_base(code: str, scaffold_text: str) -> tuple[str, bool]:
    """When a test_scaffold is provided, force the PoC to inherit ITS leaf base. Live H-01
    run (2026-07-14): the model wrote a coherent, right-mechanism exploit but inherited the
    imported grandparent (`DemoDeploy`) instead of the scaffold's leaf (`DemoTest`), losing
    setUp + every deployed symbol → `Undeclared identifier`. Deterministic (spec-016 lesson:
    the model doesn't always obey the grounding). Only rewrites when a scaffold leaf is known
    and the PoC's inheritance list doesn't already contain it. Returns (code, changed)."""
    leaf = _scaffold_base_name(scaffold_text or "")
    if not leaf:
        return code, False
    matches = list(re.finditer(r"(contract\s+\w+\s+is\s+)([^{]+?)(\s*\{)", code))
    if not matches:
        return code, False
    m = matches[-1]   # the PoC contract — conventionally the last declared
    current_bases = [b.strip() for b in m.group(2).split(",")]
    if leaf in current_bases:
        return code, False
    return code[:m.start(2)] + leaf + code[m.end(2):], True


# ── The five named transform-application sequence-functions (one per site) ─────────────
# Each reproduces its site's EXACT current sequence (same transforms, same order, same
# per-call args) and returns (code, applied) — the ordered fixer-names that changed the
# code. The two repair loops in poc_queue_runner.py keep their OWN control flow
# (recompile/bounds) and emit their OWN events from `applied`, byte-identical to before.
# NOT unification — each site keeps its own function + sequence (merging is spec 034).

def _seq_synth_prewrite(code: str, project: Path, synth_dir: Path) -> tuple[str, list[str]]:
    """Synthesis pre-write: rewrite import paths relative to the synth file's own (deeper) dir."""
    code, c_imp = _fix_import_paths(code, project, base_dir=synth_dir)
    return code, (["import_paths"] if c_imp else [])


def _seq_synth_repair(code: str, forge_output: str, project: Path, synth_dir: Path,
                      symbol_index) -> tuple[str, list[str]]:
    """Synthesis repair round: import depth + nested-type imports + 9553 address->interface.
    NOTE: nested is called WITHOUT file_map here (defaults "") — a per-call divergence from
    the post-model site's nested(file_map)."""
    code, c_imp = _fix_import_paths(code, project, base_dir=synth_dir)
    code, c_nest = _fix_nested_type_imports(code, symbol_index)
    code, c_iface = _fix_address_interface(code, forge_output)
    return code, [n for n, c in (("import_paths", c_imp), ("nested_imports", c_nest),
                                 ("address_interface", c_iface)) if c]


def _seq_draft_inplace(code: str, forge_output: str, symbol_index,
                       file_map: str = "") -> tuple[str, list[str]]:
    """Drafting in-place repair: undeclared-import of a KNOWN symbol + 9553 address->interface.
    NOTE: does NOT run import_paths — the gap is intentional (pinned, not silently changed)."""
    code, c_und = _fix_undeclared_import(code, forge_output, symbol_index, file_map)
    code, c_iface = _fix_address_interface(code, forge_output)
    return code, [n for n, c in (("undeclared_import", c_und), ("address_interface", c_iface)) if c]


def _seq_postmodel(code: str, project: Path, symbol_index, file_map: str, scaffold: str,
                   guard: bool) -> tuple[str, list[str]]:
    """Drafting post-model (draft & fix): setup-override (guarded) -> import_paths(project) ->
    nested(file_map) -> scaffold_base. The caller emits one event per applied fixer with its stage."""
    applied: list[str] = []
    if guard:
        code, changed = _fix_setup_override(code)
        if changed:
            applied.append("setup_override")
    code, ip_changed = _fix_import_paths(code, project)
    if ip_changed:
        applied.append("import_paths")
    code, nested_changed = _fix_nested_type_imports(code, symbol_index, file_map)
    if nested_changed:
        applied.append("nested_imports")
    code, base_changed = _fix_scaffold_base(code, scaffold)
    if base_changed:
        applied.append("scaffold_base")
    return code, applied


# Post-model applied-fixer name → its run-log event (the loops emit one per `applied` entry,
# in order, preserving the byte-identical per-fixer events the inline sequence emitted).
_POSTMODEL_EVENT = {
    "setup_override": "postfix_setup",
    "import_paths": "postfix_imports",
    "nested_imports": "postfix_nested_import",
    "scaffold_base": "postfix_scaffold_base",
}

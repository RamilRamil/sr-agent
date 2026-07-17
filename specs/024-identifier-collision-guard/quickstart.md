# Quickstart: Deterministic Repair Hints (spec 024)

The harness does not ask a model to fix compiler errors. It **resolves the compiler's complaint
against ground truth it already holds** and hands back an exact instruction. This is that layer.

## The idea

> The compiler says exactly what's wrong; we know exactly what's right — connect the two so the
> repair is a precise instruction, not a hope.

`_targeted_hints` in [poc_queue_runner.py](../../scripts/poc_queue_runner.py) turns each compiler
error into authoritative text appended to the next draft prompt under
`TARGETED FIXES (authoritative — apply exactly)`.

## The entries

| Compiler says | Ground truth consulted | Instruction |
|---|---|---|
| `Declaration "X" not found` (2904) | `SymbolIndex.nested_container` | `X` is nested in `C` — import `C`, use `C.X` |
| `Member "X" not found … in contract Y` (9582) | scaffold ➜ else `callable_api` | **base's own state var → drop the `Y.` qualifier** (spec 024), else use `Y`'s real functions |
| `Source "F.sol" not found` (6275) | `file_map` | import from the real path |
| `Wrong argument count` | `callable_api` | match a real signature |
| `Identifier not found` (7920) | — | use real names; imports aren't inherited |
| `Identifier already declared` (9097) | error block ➜ scaffold | **don't redeclare what the base declares** (spec 024) |

## Two rules that keep this layer honest

**1. Match the message TEXT, never the error code.** Every entry keys on the message string; codes
appear in comments only. Spec 024 was first written against code `2333` — the live compiler emits
**`9097`**. A code-matched guard would have silently never fired. Codes rot; messages don't.

**2. Only claim what you can prove; otherwise fall back.** A wrong specific instruction is worse than
a right generic one — the model chases a name that isn't there.

- Can't parse the colliding identifier? → generic "don't redeclare inherited state" text.
- Can't confirm the missing member is the base's state var? → today's "use `Y`'s real functions" text,
  byte-identical.

The 9582 refinement fires **only on positive evidence** from the scaffold, making it strictly narrower
than the condition it already handles — so it cannot regress what works.

## Why the 9582 refinement exists

Live run, finding-2. The PoC wrote:

```solidity
UnstakeCooldown unstakeCooldown = UnstakeCooldown(address(cdo.unstakeCooldown()));
```

`unstakeCooldown` is **real** — the scaffold base declares and deploys it. The model just reached it
through a wrong qualifier. The old hint answered "`StrataCDO` has no member `unstakeCooldown`, use its
real functions" — true, and *misdirecting*: it sent the model hunting a substitute on the wrong
contract. Two attempts died there; the fix was to delete `cdo.`.

Lesson worth keeping: **"not a member of Y" does not mean "not real."**

## Adding an entry

1. **Get real compiler output first.** Don't write the regex from memory or docs — both live traps
   (code `9097`; the lowercase-initial type `sNUSDAprPairProvider`) would have been missed. Grep a run
   log for the shape.
2. Match the message text. Put the code in a comment.
3. Resolve against ground truth already in scope (`callable_api`, `file_map`, `symbol_index`,
   `scaffold`, `code`). Need something else? Thread it in as an **optional** param so existing callers
   and tests stay valid.
4. **Prefer the compiler's own report over re-deriving.** The error block already names files and lines;
   that is authoritative and attributable to *this* collision. Spec 024 nearly enriched the 9097 hint via
   `_scaffold_base_name` — which is per-file by contract, while this layer receives `read_scaffold`'s
   multi-file blob, so it would have named the wrong base.
5. Check helpers' contracts before reuse. `_scaffold_base_name` strips comments; `scaffold_missing_types`
   does not. Any gate that must not misfire strips first — commented-out source is not evidence.
6. Emit specific-if-provable, generic-if-not.
7. Test offline with **synthetic** fixtures — invented names only, in `test_targeted_hints_<code>.py`.
   Run logs ground the design; target material never enters this repo.

## Tests

```bash
pytest tests/unit/test_targeted_hints_9097.py tests/unit/test_targeted_hints_9582.py -q
```

One file per error code — the convention `test_targeted_hints_2904.py` set. Offline, no model, no
Docker, no network. The byte-identical assertions on the untouched 9582 paths are the regression guard.

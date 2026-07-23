# Feature Specification: Deterministic Compile-Fixers in the Drafting Loop

**Feature Branch**: `032-deterministic-compile-fix`

**Created**: 2026-07-21

**Status**: Draft

**Input**: User description: "Apply deterministic compile-fixers in the drafting/repair loop (not just as model hints) so a mechanical compile error is fixed by the harness rather than left to a model that does not converge."

## User Scenarios & Testing *(mandatory)*

The harness drafts a PoC, then repairs it over several attempts. Between attempts it already applies a
few DETERMINISTIC code transforms (import-path depth, nested-type imports) — mechanical fixes the
harness makes itself, no model round-trip. Everything else is left to the model via text hints. The
problem: the model does not converge on the mechanical errors — it keeps making new ones.

**Motivation (from live run logs).** Two capable models (GLM-5.2, deepseek-v3.2) over two findings,
up to 8 attempts each: the compile-fix loop does not converge — finding-2, on a SUFFICIENT scaffold,
compiled only 2 of 8 attempts, each failure a DIFFERENT compiler error. Measured compile-error
frequency: **"Undeclared identifier / Identifier not found" = 8 (the dominant class)**;
**address→interface conversion = 3**; wrong-argument-count = 3, invalid-token = 2, cannot-instantiate-
interface = 1 (these last three are semantic — not mechanically fixable). Adding the two mechanical
classes to the harness's own deterministic pass repairs them without relying on the flaky model.

### User Story 1 - An undeclared KNOWN symbol is auto-imported (Priority: P1)

When a compile error reports an undeclared identifier that IS a real top-level symbol in the project
(a contract/interface/library/type the index can resolve to a defining file), the harness adds the
missing import itself instead of asking the model to.

**Why this priority**: This is the dominant measured error class (8×). Fixing it deterministically is
the single biggest win for compile-convergence.

**Independent test**: Given code referencing a name that a stubbed index resolves to a real file and a
forge output reporting that name as undeclared, the transform adds `import { Name } from "<path>";`.
Verified offline; no model call, no forge.

**Acceptance Scenarios**:

1. **Given** a draft that uses `Foo` without importing it, a stubbed index that knows `Foo` maps to a
   real file, and forge output "Undeclared identifier `Foo`", **When** the deterministic pass runs,
   **Then** the code gains `import { Foo } from "<Foo's real path>";`.
2. **Given** the same but the forge output uses "Identifier not found `Foo`" (the 7920 wording),
   **When** the pass runs, **Then** the import is still added (both wordings are handled).
3. **Given** `Foo` is already imported, **When** the pass runs again on the same error, **Then** no
   duplicate import is added (idempotent).

### User Story 2 - An unknown identifier is NEVER speculatively imported (Priority: P1)

An undeclared name that is NOT a known project symbol (a typo or an invented identifier) is left
untouched for the model/hint — the harness never invents an import for it.

**Why this priority**: The anti-invention invariant is the safety boundary of the auto-import — a
wrong speculative import would mask the real problem (the model invented an API) and could introduce a
new error. It must ship with US1.

**Independent test**: Given a forge "Undeclared identifier `Bar`" where the stubbed index does NOT
know `Bar`, the code is returned unchanged. Verified offline.

**Acceptance Scenarios**:

1. **Given** forge output "Undeclared identifier `Bar`" and an index that does not resolve `Bar`,
   **When** the pass runs, **Then** the code is unchanged (`changed = false`) and no import is added.
2. **Given** a mix — one undeclared name known to the index and one unknown — **When** the pass runs,
   **Then** only the known name is imported; the unknown is left for the model.

### User Story 3 - The address→interface fix also runs in the drafting loop (Priority: P1)

The deterministic address→interface transform (already used in scaffold synthesis) is also applied in
the drafting loop's deterministic pass, so a drafted PoC's address→interface error is repaired by the
harness rather than only hinted at.

**Why this priority**: This class was measured 3× in the drafting loop; the transform already exists
and is trusted — wiring it in is a small, high-confidence addition that ships with US1.

**Independent test**: Given a drafting attempt whose forge output has an address→interface conversion
error, the deterministic pass wraps the flagged argument. Verified offline.

**Acceptance Scenarios**:

1. **Given** a drafted PoC and forge output with an address→interface conversion error naming a type,
   **When** the deterministic pass runs, **Then** the flagged argument is wrapped as
   `Type(address(x))` (same behavior the synthesis loop already gets).

### User Story 4 - The run log shows the deterministic repair (Priority: P2)

When a deterministic transform changes the code, the run log records which fix was applied, so an
operator can see the harness repaired the error (vs the model).

**Why this priority**: Attribution/observability; the repair works without it.

**Independent test**: When a deterministic transform changes the code in a driven attempt, an event
records the applied fix(es). Verified offline.

**Acceptance Scenarios**:

1. **Given** a deterministic transform changes the code between attempts, **When** the pass runs,
   **Then** the log records the applied fix (alongside/extending the existing post-import event).

### Edge Cases

- **Undeclared name not resolvable to a single real path**: the file-map maps each project symbol to
  ONE path by construction, so the auto-import is single-path; a name the file-map does NOT resolve is
  left for the model (never guessed) — this is the same anti-invention gate as US2.
- **No index / no file map available** (`--no-symbol-index`): the auto-import transform is a no-op
  (it cannot resolve names) — never an error; behavior degrades to today's.
- **Non-mechanical compile errors** (wrong-arg-count, invalid-token, cannot-instantiate-interface,
  member-not-found): unchanged — no deterministic transform fires; the existing text hints still cover
  them; the model still owns them.
- **A transform makes no change**: the pass leaves the code as-is (no event, no false "repaired"
  signal); the loop proceeds exactly as today.
- **Compile-error vs exploit-logic**: these transforms fire ONLY on the mechanical compile errors they
  target; a compiled-but-failed (exploit-logic) attempt is untouched by them (that path is the 029
  trace feedback, unchanged).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a compile error reports an undeclared identifier `X` (both the "Undeclared
  identifier" and "Identifier not found" wordings) AND `X` is a known top-level project symbol the
  index/file-map resolves to a real defining file, the harness MUST add the missing import for `X`.
- **FR-002**: The auto-import MUST use the project's real path for `X` (the same resolution the harness
  already uses for import fixing), and MUST be idempotent (a name already imported is not re-added).
- **FR-003**: The harness MUST NOT auto-import a name that is NOT a known top-level symbol the file-map
  resolves to a real path (a typo / invented identifier) — such names are left for the model/hint (the
  anti-invention invariant).
- **FR-003a**: The deterministic repair happens IN-PLACE within a single attempt (a bounded number of
  apply-transforms-then-recompile rounds) and MUST NOT consume the `--attempts` budget — a mechanical
  fix must not starve the model's exploit-logic attempts. It is bounded (a fixed round cap + the
  transforms' idempotency) so it cannot loop.
- **FR-004**: The existing deterministic address→interface transform MUST also be applied in the
  drafting loop's deterministic post-fix pass (not only in scaffold synthesis).
- **FR-005**: When a transform changes the code, the harness MUST rewrite the PoC and RECOMPILE it
  IN-PLACE (within the same attempt, bounded rounds) to decide the compile verdict — never trusting a
  fix without a real recompile — and only fall through to the model `fix()` when the deterministic
  transforms can no longer change the code.
- **FR-006**: The transforms MUST be deterministic and line/symbol-scoped (never touch an unflagged
  line), MUST NOT make any model call, and MUST NOT change the compile/pass verdict or the
  exploit-logic path.
- **FR-007**: When no index/file-map is available, the auto-import transform MUST be a no-op (never an
  error); behavior degrades to today's.
- **FR-008**: The semantic error classes (wrong-argument-count, invalid-token, cannot-instantiate-
  interface, member-not-found) MUST stay out of the deterministic pass — they remain the model's job
  via the existing text hints.
- **FR-009**: When a deterministic transform changes the code, the run log MUST record which fix was
  applied.
- **FR-010**: Behavior MUST be validated offline with deterministic tests over SYNTHETIC fixtures
  (invented contract/interface names, synthetic forge errors). The model call and forge subprocess MUST
  NEVER run in tests (stubbed). No real target material enters the repo (guarded by
  `test_no_target_material.py`).

### Key Entities *(include if feature involves data)*

- **Undeclared identifier**: a name a compile error flags as undeclared/not-found. It is auto-importable
  ONLY when the index resolves it to a real, unambiguous top-level project symbol.
- **Auto-import transform** (new): a deterministic `code → (code, changed)` rewrite that adds the
  missing import for a resolvable undeclared name; a no-op for unknown/ambiguous names or when no index
  is available.
- **Address→interface transform** (existing, spec 031): the deterministic 9553 fix, now additionally
  applied in the drafting loop.
- **Deterministic post-fix pass**: the existing sequence of `code → (code, changed)` transforms the
  drafting loop runs after each draft/fix; this feature adds two members to it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An undeclared name that is a known project symbol is auto-imported with its real path
  (verified over synthetic fixtures) — the dominant measured error class is now fixed by the harness.
- **SC-002**: An undeclared name that is NOT a known symbol is left unchanged (anti-invention verified).
- **SC-003**: The auto-import is idempotent (verified).
- **SC-004**: The address→interface transform fires in the drafting-loop pass on a 9553 forge output
  (verified).
- **SC-005**: When no index/file-map is available, the auto-import is a no-op (verified).
- **SC-006**: The full offline suite passes with no model/forge/network access, and
  `test_no_target_material.py` passes.
- **SC-007**: The semantic error classes, the compile/pass verdict, `_poc_defects`, the fork oracle,
  `mutation_verify`, the 029 trace feedback, and scaffold synthesis are unchanged (their existing tests
  still pass).
- **SC-008**: A deterministic repair does NOT consume a model attempt — after a deterministic fix, the
  model still has its full remaining `--attempts` for exploit logic (verified: a driven attempt whose
  compile is resolved deterministically does not advance the attempt counter / call the model fix).

## Assumptions

- The index/file-map the harness already builds can tell a real top-level project symbol from an
  unknown name and resolve it to a defining file (it already powers the existing import-fix and
  member-not-found rules); this feature reuses that, not a new notion of "known symbol".
- Both solc wordings ("Undeclared identifier" and "Identifier not found") carry the offending name in
  a stable form the transform can key on; other undeclared-shaped errors are best-effort.
- Adding two members to the existing deterministic pass needs no new control flow — the loop already
  rewrites+recompiles when a transform changes the code.
- A single fixed behavior (auto-import when resolvable, else leave) is acceptable — no operator flag.

## Out of Scope

- The semantic / non-mechanical compile errors (wrong-argument-count, invalid-token, cannot-instantiate-
  interface, member-not-found) — they stay with the existing text hints and the model.
- The exploit-LOGIC wall (the `assertion failed` / access-control class) — that is the
  fuzzing/symbolic-hybrid direction (a separate future spec, item "b").
- Scaffold synthesis and its spec-031 repair loop — unchanged; the address→interface transform is only
  ADDITIONALLY wired into the drafting loop.
- The fork oracle, `_poc_defects`, `mutation_verify`, the spec-029 trace feedback.
- Model selection and cost.

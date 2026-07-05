# Research: Eval/Verification Robustness for Generated-Artifact Success Gates

Phase 0 decisions. Each: Decision / Rationale / Alternatives considered.

## R1 — Positive-signal vs. denylist detection

**Decision**: Every automated success/failure verdict over a generated artifact in this
repository MUST be built on a **positive signal** — a marker that can only appear when
the underlying tool genuinely succeeded (or genuinely reached the state being
classified) — never on the **absence** of a fixed list of anticipated failure strings.

**Rationale**: This is the direct lesson of the 2026-07-05 incident. The original
`_compiled()`:

```python
return "Compiler run failed" not in blob and "Compilation failed" not in blob
```

is a denylist: it fails only for the two failure phrasings its author had seen before.
`forge`'s actual failure mode that day — `Error: Encountered invalid solc version in
test/neutrl/NeutrlDeploy.t.sol: No solc version installed that matches the version
requirement: =0.8.28` — uses neither phrase, so the denylist silently returned `True`
for all 3 findings. A denylist's failure mode is invisible by construction: it never
raises, never logs an anomaly, it just returns the wrong answer with full confidence.
Fixed to a **positive** signal:

```python
_RAN_TEST_RE = re.compile(r"Ran \d+ tests?")
return bool(_RAN_TEST_RE.search(stdout + "\n" + stderr))
```

`forge` prints `Ran N test(s) for ...` if and only if it got past compilation and
actually executed the suite — regardless of whether the test then passed, failed, or
reverted. This is the correct question for a **compile** gate ("did it build") as
distinct from a **pass** gate ("did the test also succeed") — the two must stay
separate signals (see R3).

**Alternatives considered**:
- *Expand the denylist with more known failure phrases* — rejected: this treats the
  symptom, not the pattern; the next unanticipated `forge`/solc/toolchain message
  reintroduces the exact same silent failure mode. A denylist can only ever be
  as complete as the set of failures its author has personally observed.
- *Rely on the subprocess exit code alone* — considered but insufficient alone: forge
  exits non-zero for both compile failures AND passing-suite-with-failing-tests in some
  configurations, and can exit 0 in edge cases (empty test discovery). Exit code is
  used as a **corroborating** signal (R2), not the sole one.

## R2 — Mandatory cross-check before recording a documented success claim

**Decision**: Before any automated verdict is written into project documentation as a
milestone or success claim (e.g., "N findings compiled"), it MUST be corroborated by a
second, **independently-computed** signal — not a second read of the same transcript
with the same regex. For the PoC harness specifically: the compile verdict (`Ran N
tests` marker) is corroborated by (a) the subprocess `exit_code` being consistent with
the claimed outcome and (b) — before writing a *milestone* claim specifically — an
operator-run, independent re-verification (as happened, by chance, in the actual
incident: re-running against a mainnet fork surfaced the same underlying issue from a
different angle and prompted the investigation that found the denylist bug).

**Rationale**: A cross-check whose second signal is derived from the *same* underlying
data via a *similar* method (e.g., two regexes over the same stdout) shares the same
blind spot and only creates false confidence. The value of a cross-check is
independence: a different data source (exit code vs. stdout text), a different
method (execution against a fork vs. static parsing of a transcript), or a different
actor (a human spot-check vs. an automated regex) computed independently.

**Alternatives considered**:
- *No cross-check, just fix the one detector* — rejected: fixes this incident but not
  the general risk; the spec (FR-002, SC-002) explicitly asks for a standing rule, not
  a one-time patch, because the same failure mode can recur in a different check the
  next time a "just check the tool's output for known problems" instinct is applied.
- *Require a second independent tool for every check* — rejected as disproportionate;
  the requirement is scoped to claims that get **documented as milestones/success
  records** (the actual point of failure was writing an unverified claim into
  `docs/roadmap.md`), not every internal per-attempt log line, which would make the
  harness prohibitively slow for no safety benefit (per-attempt telemetry is expected
  to be re-derivable and is not itself a "claim").

## R3 — Audit of the harness's existing verdict-producing checks

Three checks in `scripts/poc_queue_runner.py` produce a verdict. Each reviewed:

| Check | Signal type (before) | Signal type (after) | Disposition |
|---|---|---|---|
| `_compiled()` | Denylist (2 known failure phrases) | **Positive** (`Ran \d+ tests?`) | **Corrected** (R1). This was the actual incident. |
| `_poc_defects()` | Positive (requires an active `assert`/`expectRevert` to be PRESENT; requires a real import to be PRESENT) | unchanged | **Already positive-signal — no change needed.** It never asks "is a known-bad pattern absent"; it asks "is a known-good structural element present" (an active assertion, a real import). This is the correct shape and is kept as-is. Its one denylist-shaped sub-check (flagging `contract <TargetStem>` re-declaration) is a **narrow, explicit** anti-pattern match on the artifact's OWN declarations (something the harness fully controls the shape of, i.e. it's checking the PoC's own source against a known family name, not an open-ended tool-output message) — accepted with this explicit justification, not silently. |
| `mechanism_signal()` | Positive (checks a named method IS called) but **known-limited**: cannot distinguish which contract *instance* a shared-interface method was called on (already documented in its own docstring at introduction) | unchanged | **Already non-blocking/diagnostic**, already labeled with its limitation (docstring + roadmap/memory). FR-004 requires this labeling to persist and be visible in the durable documentation this feature adds (not just a docstring) — done in `docs/eval-principles.md` (R6). |

**Decision**: Only `_compiled()` required a code change; `_poc_defects()` and
`mechanism_signal()` already used a positive-signal shape and are confirmed, with their
respective narrow exception / known limitation now explicitly written down (satisfying
FR-003/FR-004) rather than living only in code comments.

**Rationale**: An audit's job is to find the pattern everywhere it appears, not just
patch the one instance that broke. Reviewing all three confirms the incident was
isolated to `_compiled()` and that the harness's other verdicts don't share its flaw —
while making the "why this is OK" reasoning for the two accepted checks legible to a
future contributor instead of requiring them to re-derive it.

**Alternatives considered**: Rewrite `_poc_defects`/`mechanism_signal` defensively even
though no flaw was found — rejected; per FR-003 the requirement is "corrected OR
justified", and manufacturing a rewrite where the existing shape is already correct
adds complexity without a safety benefit (violates the project's stated anti-abstraction
preference).

## R4 — SmartGraphical as a stronger mechanism-check: feasibility & recommendation

**Question**: Can SmartGraphical's call-graph analysis (`sr_agent/packs/audit/tools/
smartgraphical.py`, integrated per `specs/002-smartgraphical-integration/`) replace or
strengthen `mechanism_signal()`'s regex-based "was the method name called" check with a
real, type-aware "was THIS function on THIS contract type actually called" check?

**What SmartGraphical already provides** (per `specs/002-smartgraphical-integration/
research.md` R1/R4): a JSON graph of `{nodes, edges}` including `function_to_function`,
**`cross_type_call`** (a call resolved across a declared variable's type — exactly the
"which contract instance" resolution `mechanism_signal` cannot do), and
`state_to_function_read/write` edges, already used elsewhere in this project to build a
`StateInterferenceGraph` for reentrancy reasoning. Structurally, `cross_type_call`
edges are precisely the mechanism needed: they would let a check confirm a PoC's test
function has a resolved call edge to the specific target function on the specific
target contract *type* named in a finding's `location` — closing `mechanism_signal`'s
exact, documented blind spot (it currently cannot tell that a call to a shared-interface
method `transfer(...)` landed on `sharesCooldown` rather than `unstakeCooldown`).

**What is NOT yet established** (real, open feasibility risk):
1. SmartGraphical has, to date, only been driven over **audited target contracts**
   (`sr_agent/packs/audit/tools/smartgraphical.py` runs it on "one file" or an
   in-scope bundle) — never over a **Foundry test file** (`forge-std/Test.sol`
   inheritance, `vm` cheatcode calls, a PoC's own contract declaration). Whether its
   parser/graph builder handles that combination cleanly is unverified.
2. The external SmartGraphical installation (`SR_SMARTGRAPHICAL_ROOT`) is **not present
   in this environment** (confirmed: the env var is unset and no installation was found
   on this machine) — the recommendation below is deliberately reachable without
   running it end-to-end here (per the spec's Assumptions), but any "adopt now" path
   would still need that spike done somewhere it IS installed.
3. Running an extra structural-analysis subprocess per draft/fix attempt inside the
   harness's tight loop adds latency and another moving part to a workflow already
   juggling a metered cloud GPU, Docker rebuilds, and (for path B) an RPC key — a real
   operational cost that must be weighed against the value.

**Decision — ADAPT, not ADOPT NOW; and adapt narrowly.** SmartGraphical's `cross_type_call`
edges are structurally the right tool for exactly the blind spot `mechanism_signal` has,
so this is not a "no" — but two things must happen before it's worth wiring in as a
gate: (a) a small spike confirming it parses a Foundry PoC test file without choking
(open question #1 above), run wherever the dependency is actually installed; (b) the
integration should be scoped **narrowly** to answering one question — "does a resolved
call edge exist from this PoC to this specific function on this specific contract
type?" — rather than standing up a full second interference-graph pipeline for the
harness. Until then, `mechanism_signal()` remains what it already is: an explicitly
non-blocking, explicitly-limited diagnostic (R3), and **path B (mainnet-fork execution,
already implemented — `--fork`)** is the higher-priority correctness signal to lean on
next, because it answers a different and more direct question ("does the exploit
actually trigger") that a static call-graph check cannot answer on its own — the two
are complementary (call-graph confirms the *right* code path is targeted; fork
execution confirms it *actually behaves* as claimed), not substitutes, and fork
execution is zero-additional-dependency today.

**Alternatives considered**:
- *Adopt immediately as a hard gate* — rejected: the untested Foundry-file parsing
  path and the unavailable local install make this premature; a hard gate built on an
  unverified capability risks recreating exactly this feature's own incident (trusting
  a check that hasn't been shown to work on the actual input shape it will see).
- *Reject outright ("not worth it")* — rejected: the `cross_type_call` edge type is a
  clear structural match to a real, already-identified, already-documented blind spot;
  dismissing it would be an equally ungrounded verdict in the other direction. The
  recommendation is conditional, not a close.
- *Full StateInterferenceGraph-style integration (mirror the audit pipeline's usage)*
  — rejected as the first step; disproportionate to the one question this feature
  actually needs answered (a scoped type-resolution/call-edge lookup, not a full
  reentrancy-analysis pipeline for a workability harness).

## R5 — Root infra cause (context, already fixed in-session)

**Decision** (for completeness/traceability, not new work in this feature): the reason
`_compiled()`'s blind spot was actually TRIGGERED (as opposed to merely theoretically
possible) was that `docker/Dockerfile.foundry` baked its Foundry image with `forge build
--skip test`, so solc `0.8.28` — pinned exactly by `test/neutrl/NeutrlDeploy.t.sol`,
which the production-mode scaffold (`PashovSharesCooldownBase`) transitively inherits —
was never cached, and every offline compile of a scaffolded PoC hit "invalid solc
version." Already fixed this session (`forge build --force`, no `--skip test`); recorded
here because User Story 2's audit and this feature's documentation should account for
*why* the incident was observable, not only that the detector missed it.

**Rationale**: A positive-signal detector alone does not prevent solc-pinning gaps —
it makes them **visible** instead of silently misreported. Both fixes are required:
the infra fix makes the underlying compile *possible*; the detector fix makes its
*true status* trustworthy either way.

## R6 — Where this lands in durable documentation

**Decision**: A new `docs/eval-principles.md` holds (a) the general principle (R1/R2,
worded so it applies to any future automated verdict, not only the PoC harness), (b)
the audit table (R3), and (c) the SmartGraphical recommendation (R4) with its
conditions. It is cross-linked from `docs/audit-agent.md` (the PoC harness — its
concrete, current application) and from the top-level `README.md`'s doc index. It is
**not** folded into `docs/kernel.md`: kernel invariants (Principle I) are a distinct,
stricter, already-rigorously-tested class (the MI harness, `tests/security/`) — this
principle is a general engineering practice for tooling verdicts, and keeping it
separate avoids diluting or implying equivalence with the kernel's non-negotiable
security invariants. `docs/roadmap.md`'s false milestone entry is corrected in place
(the "Current focus" PoC-workability section) with a pointer to the corrected
detector and the honest re-verified state, per FR-007/SC-004.

**Alternatives considered**: Put the principle only in a code comment on `_compiled()`
— rejected; this is exactly what FR-006/User-Story-4 identifies as insufficient (not
discoverable without reading that one file, and doesn't generalize to a future pack's
own tooling). Put it inside `docs/kernel.md` — rejected per the reasoning above.

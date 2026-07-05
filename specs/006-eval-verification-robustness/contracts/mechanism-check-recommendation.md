# Contract: Mechanism-Verification Recommendation Record

The decision-record format for User Story 3 (SmartGraphical feasibility). Filed once
per candidate stronger-verification tool considered for a Success Gate; kept even when
the verdict is `defer`, so the reasoning survives and the "what would change this"
conditions are checkable later without re-deriving them.

## Format

```
## <Candidate tool/technique> for <what it would verify>

**Verdict**: adopt | adapt | defer
**Reasoning**: <why>
**What it would close**: <the specific blind spot in the current check>
**What's unverified/blocking adoption now**: <concrete open questions>
**Conditions to revisit**: <what would change the verdict>
**Current stand-in**: <what carries the burden meanwhile, with its own known limitations>
```

## This feature's record

## SmartGraphical (`sr_agent/packs/audit/tools/smartgraphical.py`) for "does the PoC's
call chain reach the finding's specific function on the specific contract type"

**Verdict**: adapt (not adopt now, not defer outright)

**Reasoning**: SmartGraphical's existing `cross_type_call` graph edges (see
`specs/002-smartgraphical-integration/research.md` R4) are a structural, type-aware
call-resolution mechanism already built and used elsewhere in this project — exactly
the shape of check `mechanism_signal()`'s regex cannot perform. It is not a "no", but
also not yet proven on this specific input shape.

**What it would close**: `mechanism_signal()`'s documented blind spot — it can tell
that a method NAME was called, but not on WHICH contract instance/type, when two
contracts share an interface (observed: `sharesCooldown.transfer(...)` vs.
`unstakeCooldown.transfer(...)`, both satisfying the same regex).

**What's unverified/blocking adoption now**:
1. SmartGraphical has only ever been driven over audited target contracts, never over a
   Foundry test file (`forge-std/Test.sol` inheritance + `vm` cheatcodes) — whether its
   parser handles that combination is unverified.
2. The external `SR_SMARTGRAPHICAL_ROOT` install is not present in this environment.
3. Running it per draft/fix attempt adds latency + another moving dependency to an
   already GPU/Docker/RPC-heavy harness — the cost must be justified by the value once
   (1) is resolved.

**Conditions to revisit**: (a) a spike (wherever SmartGraphical IS installed) confirms
it parses a real Foundry PoC test file and produces a `cross_type_call` edge from the
test function to the target function/contract without choking; (b) path B (mainnet-fork
execution, already implemented) is exercised at scale and found insufficient on its own
(e.g. too slow, or too many false "green"s that a call-graph check would have caught
before spending a fork run) — that would raise the priority of closing this gap.

**Current stand-in**: `mechanism_signal()` (non-blocking diagnostic, logged every
attempt) + path B mainnet-fork execution (the actual correctness signal — answers "does
the exploit trigger", which is a different, complementary question this feature does
not claim SmartGraphical would replace).

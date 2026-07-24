"""Feature 035 — the deterministic classifier for the invariant verification path.

Given a model-written invariant plus the RESULTS of an honest-behavior run and an engine
search (both produced by the harness/sandbox — this module runs neither), decide the single
outcome, applying the three trust gates that keep a model-authored oracle trustworthy:

  vacuity (FR-006) → honest-check + coverage (FR-013/013a) → engine violation + deterministic
  re-confirm (FR-002/003/005) → mechanism attribution (FR-016) → invariant_verified

Every gate is deterministic and SAFE-ERRING: any doubt withholds the trustworthy-verified
label rather than asserting a pass (a false verified HIDES a failure — the class the project
fought in 006/010 and the recent false-verified guard). The mechanism-attribution SIGNAL is
computed by the caller (via `mechanism_signal`, which lives in poc_queue_runner) and passed in
as a bool — so this classifier is pure, offline-testable, and imports no heavy harness code
(no import cycle; cf. feature 033). This module is the engine-AGNOSTIC trust core: its logic is
identical whichever search engine Level-0 (FR-014) picks.
"""
from __future__ import annotations

import re

from scripts.solidity_utils import _strip_fences

# ── Outcomes (Decision 6) ─────────────────────────────────────────────────────
VERIFIED = "invariant_verified"                 # all gates passed — the ONLY trustworthy outcome
HONEST_MANIFEST = "invariant_honest_manifest"   # FR-019: the finding manifests under HONEST use (no adversary)
OVER_STRICT = "invariant_over_strict"           # FR-013: honest behavior violated the invariant
WEAK_COVERAGE = "invariant_weak_coverage"       # FR-013a: honest run held but did not cover enough
NO_VIOLATION = "invariant_no_violation"         # FR-005: engine found nothing / it did not reproduce
MECHANISM_MISMATCH = "invariant_mechanism_mismatch"  # FR-016: violation did not touch the finding's mechanism
UNAVAILABLE = "invariant_unavailable"           # vacuous invariant, or honest/engine setup failed

# State-changing action names whose presence means the honest run exercised real protocol paths,
# not just deploy/setup — the FR-013a coverage floor for the fallback (no-suite) case.
_STATE_CHANGING = frozenset({
    "deposit", "withdraw", "redeem", "mint", "burn", "transfer", "transferfrom",
    "stake", "unstake", "claim", "cancel", "borrow", "repay", "swap", "liquidate",
})

# Conservative structural vacuity: an assertion whose argument is a literal tautology. Deep
# vacuity (holds for a non-obvious reason) is an OPERATIONAL signal, not this structural gate;
# this catches the obvious `assert(true)` / `x == x` class the anti-vacuity gate exists for.
_VACUOUS_RE = re.compile(
    r"\b(?:assert|assertTrue|require)\s*\(\s*"
    r"(?:true|1\s*==\s*1|0\s*==\s*0|(\w+)\s*==\s*\1|(\w+)\s*>=\s*0)\s*[,)]",
    re.IGNORECASE,
)


def _is_vacuous(invariant_src: str) -> bool:
    """True when the invariant is a structural tautology (unviolatable by any input)."""
    src = invariant_src or ""
    if _VACUOUS_RE.search(src):
        return True
    # a bool invariant whose only body is `return true;` / `true` is vacuous too
    body = re.sub(r"//[^\n]*", "", src)
    return bool(re.search(r"\breturn\s+true\s*;", body, re.IGNORECASE))


# ── T010: invariant authoring (the model writes the property) ─────────────────
# The TOLERANCE clause is not decoration: a zero-tolerance invariant is over-strict as written
# (real protocols round), and without a declared tolerance the honest-check cannot separate
# "lacked slack" from "material" (FR-001/FR-020, Level-0 row C).
INVARIANT_PROMPT = """You are given ONE audit finding for a Solidity protocol.

Write a SINGLE Foundry invariant predicate that:
1. HOLDS on the healthy, un-exploited protocol under legitimate use;
2. IS VIOLATED when this finding's bug is triggered;
3. ENCODES THE PROTOCOL'S STATED TOLERANCE explicitly (e.g. allow per-operation rounding of
   1 wei: `assertLe(gap, TOLERANCE)`), because real protocols round — a zero-tolerance property
   is broken by ordinary use and is therefore useless as an oracle;
4. references only state the target actually exposes.

[finding]
{finding}

[grounded target context]
{grounding}

Return ONLY the Solidity function body of the invariant (no prose, no markdown fences)."""


def author_invariant(client, *, finding: str, grounding: str, options: dict | None = None) -> str:
    """T010/FR-001 — ask the model for the invariant predicate. The reply is
    `external_llm_output`: it is stripped of fences and returned as untrusted SOURCE; nothing here
    trusts it — every gate downstream (FR-006/013/013a/016/019/020) still applies."""
    prompt = INVARIANT_PROMPT.format(finding=finding, grounding=grounding)
    raw = client.generate(prompt, options=options or {})
    return _strip_fences(raw or "").strip()


# ── T011: deterministic harness codegen (one predicate, two actor policies) ────
# FR-017 (BLOCKING, measured in Level-0): senders MUST be pinned. Forge invents a random sender
# per call; on a fork it fetches that account from RPC and a random address never hits the cache,
# so a deep run dies on provider HTTP 429 — which PRESENTS AS A HANG. Pinning took 1 000 calls
# from a 429 failure to 3.2 s.
HONEST = "honest"
ADVERSARIAL = "adversarial"


def build_invariant_harness(
    *,
    invariant_src: str,
    base_import: str,
    base_contract: str,
    actors: list[str],
    policy: str,
    honest_actions: list[str],
    all_actions: list[str],
) -> str:
    """Generate the Foundry invariant test for ONE policy over the SAME predicate (research
    Decision 2): the honest policy exposes only legitimate entrypoints (the invariant must HOLD);
    the adversarial policy exposes everything (it may break). Returns Solidity source."""
    if policy not in (HONEST, ADVERSARIAL):
        raise ValueError(f"unknown policy: {policy}")
    actions = honest_actions if policy == HONEST else all_actions
    handler_fns = "\n".join(
        f"    function act_{a}(uint256 seed) public {{ _asActor(seed); target.{a}(seed); }}"
        for a in actions
    )
    pins = "\n".join(f"        targetSender({a});" for a in actors)
    actor_list = ", ".join(actors)
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;
import {{ {base_contract} }} from "{base_import}";

// policy={policy} — generated by feature 035 (do not edit by hand)
contract Handler_{policy} is {base_contract} {{
    address[] internal _actors = [{actor_list}];
    function _asActor(uint256 seed) internal {{ vm.startPrank(_actors[seed % _actors.length]); }}
{handler_fns}
}}

contract Invariant_{policy} is {base_contract} {{
    Handler_{policy} internal handler;

    function setUp() public override {{
        super.setUp();
        handler = new Handler_{policy}();
        targetContract(address(handler));
        // FR-017: pin senders — random per-call senders are uncacheable on a fork and trip the
        // provider's rate limit mid-run, which looks like a hang rather than an error.
{pins}
    }}

{invariant_src}
}}
"""


# ── T012 (pure half): parse a forge invariant run into the classifier's inputs ──
# Kept here, not in the runner, so every parsing rule is offline-testable against synthetic
# forge-shaped fixtures (no sandbox, no target material).
_INV_VERDICT_RE = re.compile(r"\[(PASS|FAIL[^\]]*)\]\s+(invariant_\w+)", re.I)
_INV_STATS_RE = re.compile(r"runs:\s*(\d+),\s*calls:\s*(\d+),\s*reverts:\s*(\d+)", re.I)
_INV_ACTION_RE = re.compile(r"\bact_(\w+)\b")
_INV_MAGNITUDE_RE = re.compile(r"\bgap[=:\s]+(\d+)\b", re.I)


def parse_invariant_output(stdout: str) -> dict:
    """Turn a forge invariant run's stdout into structured facts.

    Returns `{held, violation_found, call_set, magnitude, coverage:{actions_exercised, suite_used}}`.
    `held` is True only on an explicit PASS — an unparseable or empty run is NOT treated as held
    (safe-erring: absence of a verdict must never read as "the invariant holds")."""
    text = stdout or ""
    m = _INV_VERDICT_RE.search(text)
    verdict = (m.group(1).upper() if m else "")
    held = verdict.startswith("PASS")
    violation = verdict.startswith("FAIL")
    stats = _INV_STATS_RE.search(text)
    mag = _INV_MAGNITUDE_RE.search(text)
    actions = list(dict.fromkeys(_INV_ACTION_RE.findall(text)))
    return {
        "held": held,
        "violation_found": violation,
        "call_set": actions,
        "magnitude": int(mag.group(1)) if mag else None,
        "runs": int(stats.group(1)) if stats else None,
        "calls": int(stats.group(2)) if stats else None,
        "coverage": {"actions_exercised": actions, "suite_used": False},
    }


def accumulates(magnitude_small: int | None, magnitude_large: int | None) -> bool:
    """FR-020 materiality by ACCUMULATION: the same honest policy run at a larger call budget.
    A rounding artifact stays bounded; a real leak grows with the number of operations. Unknown
    on either side → False (never promote on ignorance)."""
    if magnitude_small is None or magnitude_large is None:
        return False
    return magnitude_large > magnitude_small


def derive_actions(callable_api: str) -> tuple[list[str], list[str]]:
    """Split the grounded callable API into (honest_actions, all_actions) for the two handler
    policies. `honest` keeps only recognised LEGITIMATE user entrypoints — the actions a normal
    user performs — so the honest policy exercises real protocol paths (FR-013a) without an
    adversary; `all` is everything the API exposes, for the adversarial policy. Deriving `honest`
    from a fixed vocabulary (rather than from the model) keeps the honest side model-independent,
    which is what makes the honest-check an independent oracle at all (FR-013)."""
    names = list(dict.fromkeys(re.findall(r"\bfunction\s+(\w+)\s*\(", callable_api or "")))
    honest = [n for n in names if n.lower() in _STATE_CHANGING]
    return honest, names


def _is_material(honest_run: dict) -> bool:
    """FR-020 — MODEL-INDEPENDENT materiality for the FR-019 branch.

    Reproduction and attribution both fire for a merely OVER-STRICT invariant in exactly the
    class FR-019 targets: rounding is deterministic (so it reproduces every time) and the honest
    scenario calls the very functions the finding names (so attribution matches). The only signal
    the model does NOT author is how the discrepancy BEHAVES: a rounding artifact stays bounded
    (~1 wei) under repetition, while a real leak GROWS with the number of operations / scale.
    So materiality = the gap accumulates, or it exceeds an externally-supplied threshold.
    Absent either measurement, materiality is FALSE (safe-erring)."""
    if honest_run.get("magnitude_grows"):
        return True
    mag, thr = honest_run.get("magnitude"), honest_run.get("materiality_threshold")
    return mag is not None and thr is not None and mag > thr


def _meets_coverage_bar(coverage: dict | None) -> bool:
    """FR-013a: the honest run covers enough to make `held` meaningful. Met when the target's own
    suite ran (`suite_used`), OR the honest run exercised at least one real state-changing path
    (not just deploy/setUp). A deploy-plus-smoke run fails this — it would pass a naive
    'balance never decreases' invariant that a legitimate withdraw breaks."""
    if not coverage:
        return False
    if coverage.get("suite_used"):
        return True
    acts = {str(a).lower() for a in coverage.get("actions_exercised", [])}
    return bool(acts & _STATE_CHANGING)


def classify_invariant_result(
    *,
    invariant_src: str,
    honest_run: dict | None,
    engine_result: dict | None,
    mechanism_matched: bool | None,
    honest_mechanism_matched: bool | None = None,
) -> tuple[str, str, dict]:
    """Apply the gate pipeline in order; return (outcome, reason, provenance).

    Inputs (all produced elsewhere — this function runs nothing):
    - `honest_run`: {"held": bool, "coverage": {"suite_used": bool, "actions_exercised": [...]}}
      or None / {"error": ...} when the honest run could not be set up.
    - `engine_result`: {"violation_found": bool, "counterexample": {"call_set": [...],
      "reproduced": bool}} or None / {"error": ...} on engine/setup failure.
    - `mechanism_matched`: did the counterexample's call_set touch the finding's named mechanism
      (caller computes via `mechanism_signal`)? Only consulted once a reproduced violation exists.

    SAFE-ERRING: unknown/failed inputs yield UNAVAILABLE or a non-verified outcome, never VERIFIED.
    """
    prov: dict = {}

    # 1 — anti-vacuity (FR-006)
    if _is_vacuous(invariant_src):
        return UNAVAILABLE, "vacuous_invariant", prov

    # 2 — honest-behavior check (FR-013) + coverage bar (FR-013a) — restores INDEPENDENCE
    if not honest_run or honest_run.get("error"):
        return UNAVAILABLE, "honest_run_setup_failed", prov
    coverage = honest_run.get("coverage") or {}
    prov["honest_coverage"] = coverage
    if not honest_run.get("held"):
        # FR-019 (Level-0 row C): a violation during HONEST use is not automatically an over-strict
        # invariant — for the honest-manifesting class (rounding/accounting drift) the bug IS the
        # ordinary path, so honest-check and violation-check are the same event. Discriminate, but
        # SAFE-ERRING: promote only when the honest violation both REPRODUCES and is attributed to the
        # finding's own mechanism; anything less stays over-strict (the guard is not weakened).
        # NOTE the coverage bar is deliberately NOT applied here: coverage guards the "held" direction
        # (absence of evidence proves little); a violation is positive evidence and needs no breadth.
        prov["honest_violation_call_set"] = honest_run.get("violation_call_set", [])
        prov["honest_mechanism_matched"] = bool(honest_mechanism_matched)
        # Magnitude is recorded ALWAYS (SC-013), so a reviewer tells 1 wei from a real loss
        # without rerunning — the analogue of SC-010's coverage provenance.
        prov["violation_magnitude"] = honest_run.get("magnitude")
        prov["magnitude_grows"] = honest_run.get("magnitude_grows")
        material = _is_material(honest_run)
        prov["material"] = material
        # THREE signals required (FR-019 + FR-020). Reproduction and attribution alone do NOT
        # discriminate here: both also fire for an invariant that merely lacked slack.
        if honest_mechanism_matched and honest_run.get("violation_reproduced") and material:
            return HONEST_MANIFEST, "material_violation_under_honest_use", prov
        return OVER_STRICT, "invariant_violated_by_honest_behavior", prov
    if not _meets_coverage_bar(coverage):
        return WEAK_COVERAGE, "honest_run_below_coverage_bar", prov

    # 3 — engine search + deterministic re-confirm (FR-002/003/005)
    if not engine_result or engine_result.get("error"):
        return UNAVAILABLE, "engine_setup_failed", prov
    if not engine_result.get("violation_found"):
        return NO_VIOLATION, "engine_found_no_violation", prov
    ce = engine_result.get("counterexample") or {}
    prov["call_set"] = ce.get("call_set", [])
    if not ce.get("reproduced"):
        return NO_VIOLATION, "violation_did_not_reproduce", prov

    # 4 — mechanism attribution (FR-016) — restores the TIE to the finding, safe-erring
    prov["mechanism_matched"] = bool(mechanism_matched)
    if not mechanism_matched:
        return MECHANISM_MISMATCH, "violation_missed_finding_mechanism", prov

    # all gates passed — the only trustworthy verified
    return VERIFIED, "", prov

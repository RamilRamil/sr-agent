"""Stage 3 — deterministic finding synthesis / combination (T056, relay variant).

No LLM: two deterministic passes over the Stage 2 findings.

  1. Severity conjunction correction (reuses guardrails.severity.check_severity):
     mitigations cap severity at medium; many preconditions floor it at high.
  2. Combination: findings that interact (SIG-lite — same source file share state)
     are linked via combined_with. A conservative chain rule elevates a group of
     2+ unmitigated high/critical findings on the same target to a critical chain
     (blast-radius reasoning: interacting high-severity issues amplify).

Stage 3 returns transformed findings for the report; it does not write to memory
(append-only + supersedes requires human_input, so the raw Stage 2 records stay
as the audit trail and the report shows the synthesized view).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from sr_agent.guardrails.severity import check_severity
from sr_agent.models.finding import Finding, Severity

logger = logging.getLogger(__name__)

_RANK = {
    Severity.informational: 0, Severity.low: 1, Severity.medium: 2,
    Severity.high: 3, Severity.critical: 4,
}


@dataclass
class Stage3Result:
    findings: list[Finding]
    corrections: list[str] = field(default_factory=list)
    combinations: list[str] = field(default_factory=list)


def run_stage3(findings: list[Finding]) -> Stage3Result:
    """Correct severities and link/elevate interacting findings."""
    corrections: list[str] = []
    combinations: list[str] = []

    # Pass 1 — per-finding severity conjunction correction.
    for finding in findings:
        verdict = check_severity(finding)
        if verdict.was_corrected:
            finding.severity = verdict.final
            corrections.append(verdict.correction_reason or "")

    # Pass 2 — group by source file (SIG-lite: same file -> shared state).
    groups: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        groups[finding.location.split(":")[0]].append(finding)

    for source_file, group in groups.items():
        if len(group) < 2:
            continue
        ids = [f.finding_id for f in group]
        for finding in group:
            finding.combined_with = [i for i in ids if i != finding.finding_id]

        # Conservative chain rule: 2+ unmitigated high/critical findings interact.
        severe = [
            f for f in group
            if _RANK[f.severity] >= _RANK[Severity.high] and not f.mitigations_present
        ]
        if len(severe) >= 2:
            for finding in severe:
                finding.severity = Severity.critical
            combinations.append(
                f"{source_file}: {len(severe)} interacting unmitigated high+ findings "
                f"→ critical chain ({', '.join(f.finding_id for f in severe)})"
            )

    logger.info(
        "Stage 3: %d corrections, %d combination chains", len(corrections), len(combinations)
    )
    return Stage3Result(findings=findings, corrections=corrections, combinations=combinations)

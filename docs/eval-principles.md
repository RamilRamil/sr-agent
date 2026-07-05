# Eval / verification principles for generated artifacts

How this project verifies whether an automated check over an LLM-or-tool-generated
artifact (a compiled PoC, a passing test, an extracted finding) is actually telling the
truth. Written after a real incident (spec
[006-eval-verification-robustness](../specs/006-eval-verification-robustness/)) where a
verdict was wrong with full confidence, and nothing about running it raised a flag.

This is a general engineering practice for tooling, distinct from and lighter-weight
than the kernel's security invariants (Principle I, `tests/security/`) — see
[kernel.md](kernel.md) for those. This document applies wherever this project (kernel,
any capability pack, or standalone tooling like the PoC-workability harness) writes an
automated check that produces a success/failure verdict.

## The principle

**Every automated verdict over a generated artifact must be based on a positive
signal — a marker that can only appear on genuine success — never on the absence of a
list of anticipated failure signals (a denylist).**

A denylist's failure mode is invisible by construction: it doesn't raise, doesn't log
an anomaly, it just returns the wrong answer with full confidence. On 2026-07-05, the
PoC-workability harness's compile check was:

```python
return "Compiler run failed" not in blob and "Compilation failed" not in blob
```

A genuine compile failure worded differently (`Error: Encountered invalid solc version
...`) used neither phrase, so this returned `True` for 3 genuinely-failed compiles —
producing a false "all findings compiled" milestone recorded in `docs/roadmap.md`.
Fixed to a positive signal:

```python
_RAN_TEST_RE = re.compile(r"Ran \d+ tests?")
return bool(_RAN_TEST_RE.search(stdout + "\n" + stderr))
```

`forge` prints `Ran N test(s) for ...` if and only if it got past compilation and
actually executed the suite — regardless of whether the test then passed, failed, or
reverted.

**Before an automated verdict is recorded as a milestone/success claim in project
documentation, it must be corroborated by a second, independently-computed signal** —
not a second read of the same transcript with a similar method. A cross-check whose
second signal shares its data source and method with the first shares its blind spot
too. This requirement applies to *documented claims*, not every internal per-attempt
log line (that would make tooling prohibitively slow for no safety benefit).

## Audit checklist (reusable format)

Run any set of automated verdict-producing checks through this table before trusting
their verdicts. Full format + this feature's filled example:
[specs/006-eval-verification-robustness/contracts/audit-checklist.md](../specs/006-eval-verification-robustness/contracts/audit-checklist.md).

| Check | Signal type | Blocking? | Notes |
|---|---|---|---|
| `_compiled()` | positive (`Ran \d+ tests?`) | yes | corrected 2026-07-05 (was a denylist) |
| `_poc_defects()` | positive (requires active assert/import present) | yes | its one narrow exception (own-declaration re-mock check) is against the artifact's own controlled vocabulary, not an open-ended tool message |
| `mechanism_signal()` | positive, but diagnostic | **no** | cannot tell WHICH contract instance a shared-interface method was called on — logged every attempt, never gates an outcome |

When you add a new automated check anywhere in this project: ask "what marker can ONLY
appear on genuine success" (not "what failure messages have I seen"); write a
known-good AND a known-bad test worded differently than you'd naturally guess; decide
out loud whether it blocks an outcome or is diagnostic-only; add a row to the audit
table in the same change.

## Mechanism-verification recommendation: SmartGraphical

**Question**: can SmartGraphical's call-graph analysis
(`sr_agent/packs/audit/tools/smartgraphical.py`) replace `mechanism_signal()`'s
regex-based check with a real, type-aware "was THIS function on THIS contract type
actually called" check?

**Verdict: ADAPT — not adopt now, not defer outright.** SmartGraphical's
`cross_type_call` graph edges are structurally the right mechanism (they resolve a
call across a declared variable's type — exactly what a regex cannot do), but it has
never been driven over a Foundry test file (only over audited target contracts), and
the external install isn't present in this environment. Full reasoning, what it would
close, and the conditions that would change this verdict:
[specs/006-eval-verification-robustness/contracts/mechanism-check-recommendation.md](../specs/006-eval-verification-robustness/contracts/mechanism-check-recommendation.md).

**Follow-up**: the same class of problem (the model inventing plausible-but-wrong
identifiers because the real definition isn't visible to it) recurred at the *drafting*
stage, not just the *verification* stage — a struct's real fields aren't shown anywhere
the model can see them, so it invents field names. See
[specs/007-ast-grounded-poc-drafting](../specs/007-ast-grounded-poc-drafting/) for the
AST-parser-backed, agentic fix to that class of problem (a different, earlier point in
the pipeline than SmartGraphical's post-hoc call-graph check, and — per the research
above on De-Hallucinator — a well-studied problem shape: use the model's own
draft/error as the query to retrieve precise, real definitions).

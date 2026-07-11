# Quickstart: Experiential Knowledge Loop (v1)

All offline. Each maps to a user story and its SCs.

## 1. Human-gated promotion + tamper-evidence (US1 / SC-002, SC-003, SC-004)

```bash
# a candidate exists in lessons/pending/ (seeded or harness-captured)
sr-agent lessons list                    # shows the pending candidate
sr-agent lessons show <sig_id>           # full content
sr-agent lessons approve <sig_id>        # → knowledge/lessons/<sig_id>.md + signed manifest
sr-agent lessons verify                  # OK for the just-promoted lesson

# tamper check: edit knowledge/lessons/<sig_id>.md by hand, then:
sr-agent lessons verify                  # → INVALID for that lesson, non-zero exit

# dismissal: a dismissed candidate never enters the corpus
sr-agent lessons dismiss <other_sig_id>  # gone from the queue; not retrievable
```
Expected: approve makes it retrievable and verifiable; a hand-edit fails verification; the
agent has no code path to promote (asserted by `test_lessons_promote_gate.py`).

## 2. Retrieve-at-build as suggestion, not control (US2 / SC-005, SC-006, SC-007)

```python
# with one promoted lesson whose signature class matches the current context:
store = LessonStore(lessons_root, knowledge_root, secret_key, embedder=None)  # lexical fallback
blocks = store.retrieve(context="Error (2904): Declaration TExitParams not found", top_k=3)
assert blocks and blocks[0].startswith("[DATA START]") and blocks[0].endswith("[DATA END]")

# inert when empty: no relevant/verified lesson → no block, prompt unchanged
assert LessonStore(empty_root, empty_kb, secret_key).retrieve("anything") == []
```
Expected: relevant lesson surfaces DATA-wrapped; no embedder needed (lexical); empty corpus
→ `[]` and the draft/fix prompt is byte-identical to pre-feature (`test_lessons_retrieve.py`).

## 3. Automatic capture + dedup (US3 / SC-001)

```bash
# drive the harness offline (spec-009 fake model + fake sandbox) through a run where
# attempt N is stuck on an error-signature and attempt N+1 resolves it:
pytest tests/integration/test_lessons_capture.py -q
```
Expected: exactly **one** candidate written for the resolved signature; a second identical
resolved-signature transition adds **zero** further candidates (dedup by `sig_id`); a
forced capture-write failure does not abort the run (`capture` swallows it).

## 4. Seeding the 13 gotchas through the gate (T016 runbook)

The 13 confirmed gotchas ship as candidate proposals in
[`seed-lessons.jsonl`](seed-lessons.jsonl) (unsigned — they are *proposals*, not promoted
knowledge). The **operator** onboards them through the same human gate, under their own
`SR_SECRET_KEY` — nothing is pre-signed or committed with a dev key:

```bash
# one candidate per line; add each to the pending queue, then review + approve
while IFS= read -r line; do
  printf '%s' "$line" > /tmp/lesson.json
  sr-agent lessons add --from /tmp/lesson.json
done < specs/014-experiential-knowledge-loop/seed-lessons.jsonl

sr-agent lessons list                 # review the queued candidates
sr-agent lessons approve <sig_id>     # promote each you vouch for (--edit to amend)
sr-agent lessons verify               # all promoted lessons verify under your key
```
Promotion is the human's Principle-IV act; the agent never performs it.

## 5. Full offline validation (all SCs)

```bash
pytest tests/unit/test_lessons_store.py \
       tests/integration/test_lessons_capture.py \
       tests/integration/test_lessons_retrieve.py \
       tests/architecture/test_lessons_promote_gate.py \
       tests/security/test_lesson_not_instruction.py -q
# plus the full suite stays green with no new dependency:
pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```
Expected: all green; no model/Docker/network; no new runtime dependency (Principle V).

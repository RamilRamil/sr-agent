# Quickstart: Report→PoC Batch on a Hosted Model (spec 022)

Run the existing PoC-drafting batch over a whole audit report, driven by a capable hosted model (GLM or Gemini) instead of the local model. CLI/harness path; the machinery (grounding→draft→compile-fix→gate→optional fork) is unchanged.

## Run it on GLM (via OpenRouter)

```bash
export OPENROUTER_API_KEY=sk-or-…      # env only — never on the command line
python scripts/poc_queue_runner.py \
    --project /path/to/target \
    --report  /path/to/audit-report.md \
    --provider openrouter               # model defaults to z-ai/glm-5.2; marker protocol forced
```

## Run it on Gemini

```bash
pip install '.[gemini]'                 # the optional SDK (once)
export GEMINI_API_KEY=…
python scripts/poc_queue_runner.py --project … --report … --provider gemini
```

## Local (default, unchanged)

```bash
python scripts/poc_queue_runner.py --project … --report …   # LocalClient / Ollama, exactly as before
```

## What holds

- The whole report is processed — every finding, no prefiltering (`--only`/`--limit` scope a run without changing extraction).
- A compiling PoC + passing check is a **mechanical reproduction only**, never a safety verdict — the structural gate and vacuous-pass guard still apply.
- Hosted is **opt-in**: the default is local; the harness runs with no hosted key/SDK present.
- A hosted selection with no key (or missing google-genai for Gemini, or an explicit `--lookup-protocol tool`) **stops at startup** with a clear message — never a silent downgrade or a mid-batch failure.
- The key is env-sourced, never logged, never in a result, never on the command line.
- Target, report, and generated PoCs stay outside the agent repo.

## Run the tests (offline, no key, no network, no container)

```bash
pytest tests/unit/test_poc_harness_provider.py -q
```
Covers provider selection, marker-forcing, the readiness/startup stops, and the draft path with a simulated model. The real end-to-end (live GLM + Docker + forge over a real report) is a live operator run, not part of this suite.

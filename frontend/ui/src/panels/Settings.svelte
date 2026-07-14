<script lang="ts">
  import { api, type ModelConfig, type WarmResult } from "../lib/api";

  let cfg: ModelConfig | null = null;
  let endpoint = "";
  let model = "";
  let backend = "local";
  let paidKey = ""; // write-only; the backend never returns it
  let warm: WarmResult | null = null;
  let busy = false;
  let error = "";
  let geminiModels: string[] = []; // populated from /api/model/models

  async function load() {
    cfg = await api.getModelConfig();
    endpoint = cfg.endpoint;
    model = cfg.model ?? "";
    backend = cfg.backend;
    try {
      const m = await api.getModelModels();
      geminiModels = m.models;
    } catch {
      geminiModels = [];
    }
  }
  load();

  async function save() {
    error = "";
    busy = true;
    try {
      cfg = await api.setModelConfig({
        endpoint,
        model,
        backend,
        // only send the key if the operator typed one; then clear the field
        paid_key: paidKey || undefined,
      });
      paidKey = "";
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function doWarm() {
    error = "";
    busy = true;
    warm = null;
    try {
      warm = await api.warm();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="panel">
  <h2>Model backend</h2>
  <div class="stack">
    <label class="stack">
      <span class="muted">Local endpoint (localhost or a cloud-GPU tunnel URL)</span>
      <input bind:value={endpoint} placeholder="http://localhost:11434" />
    </label>
    <label class="stack">
      <span class="muted">Backend (explicit — the paid backend is never a silent fallback)</span>
      <select bind:value={backend}>
        <option value="local">Local (free, Ollama)</option>
        <option value="paid">Gemini (hosted, explicit opt-in)</option>
      </select>
    </label>
    {#if backend === "local"}
      <label class="stack">
        <span class="muted">Model (blank → auto-pick a stage-2 model)</span>
        <input bind:value={model} placeholder="e.g. qwen2.5-coder:14b" />
      </label>
    {:else}
      <label class="stack">
        <span class="muted">Gemini model (simpler/cheaper first)</span>
        <select bind:value={model}>
          {#each geminiModels as m}
            <option value={m}>{m}</option>
          {/each}
        </select>
      </label>
      <label class="stack">
        <span class="muted">Gemini API key (held in memory only — never stored or returned; overrides GEMINI_API_KEY)</span>
        <input type="password" bind:value={paidKey} placeholder={cfg?.has_paid_key ? "•••••• (set)" : "AIza…"} />
      </label>
    {/if}
    <div class="row">
      <button class="primary" on:click={save} disabled={busy}>Save</button>
      <button on:click={doWarm} disabled={busy}>Warm model</button>
      {#if cfg}<span class="badge {cfg.has_paid_key ? 'warn' : 'ok'}">key: {cfg.has_paid_key ? "set" : "none"}</span>{/if}
    </div>

    {#if warm}
      <div class="badge {warm.state === 'ready' ? 'ok' : warm.state === 'warming' ? 'warn' : 'bad'}">
        {warm.state}{warm.reason ? ` — ${warm.reason}` : ""} ({warm.elapsed_s}s)
      </div>
    {/if}
    {#if error}<div class="badge bad">{error}</div>{/if}
  </div>
</div>

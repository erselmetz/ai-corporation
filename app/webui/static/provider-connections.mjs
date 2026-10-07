import {
  assignmentImpactText,
  loadAgentAssignmentImpact,
} from "./assignment-preview.mjs";

export function mountProviderConnections({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  confirmImpl = globalThis.confirm ?? (() => false),
} = {}) {
  const el = id => documentRef.getElementById(id);
  const kind = el("connection-type");
  const connectionSelect = el("assignment-provider");
  const modelSelect = el("assignment-model");
  const agentSelect = el("assignment-agent");
  const state = el("connection-state");
  const key = el("connection-key");
  const url = el("connection-url");
  let connections = [];
  let agents = [];
  let busy = false;
  let canManage = false;
  let canManageRuntime = false;
  let runtimeEvidence = null;

  function option(select, value, label) {
    const item = documentRef.createElement("option");
    item.value = value;
    item.textContent = label;
    select.append(item);
  }

  function controls() {
    const selected = connections.find(item => item.provider_id === connectionSelect.value);
    const slots = el("connection-slots");
    const gemini = kind.value === "gemini";
    el("connection-url-field").hidden = gemini;
    el("connection-key-field").hidden = !gemini;
    slots.disabled = busy || gemini;
    if (gemini) slots.value = "1";
    el("connection-add").disabled = busy || !canManage;
    el("connection-refresh").disabled = busy || !selected || !canManage;
    el("connection-remove").disabled = busy || !selected || !canManage;
    connectionSelect.disabled = busy || !connections.length;
    modelSelect.disabled = busy || !selected || !selected.models.length;
    agentSelect.disabled = busy || !agents.length;
    el("assignment-save").disabled = busy || !selected || !modelSelect.value || !agentSelect.value || !canManage;
    const runtimeSupported = selected?.provider_type === "ollama";
    el("model-runtime-refresh").disabled = busy || !selected;
    el("model-load").disabled = busy || !canManageRuntime || !runtimeSupported || !modelSelect.value;
    el("model-unload").disabled = busy || !canManageRuntime || !runtimeSupported || !modelSelect.value;
  }

  async function request(path, { method = "GET", body } = {}) {
    const options = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
    if (method !== "GET") {
      const sessionResponse = await fetchImpl("/api/local/session", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!sessionResponse.ok) throw new Error("Sign in through local owner access first.");
      const session = await sessionResponse.json();
      options.headers = {
        ...options.headers,
        "Content-Type": "application/json",
        "X-Local-CSRF": session.csrf,
      };
      options.body = JSON.stringify(body ?? {});
    }
    const response = await fetchImpl(path, options);
    let data = {};
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) {
      if (response.status === 401) throw new Error("Sign in through local owner access first.");
      if (response.status === 403) throw new Error("This session lacks provider-connection permission.");
      throw new Error(typeof data.detail === "string" ? data.detail : "Provider connection request failed.");
    }
    return data;
  }

  function renderConnections() {
    connectionSelect.replaceChildren();
    el("connection-list").replaceChildren();
    for (const item of connections) {
      if (!item || typeof item.provider_id !== "string" || !Array.isArray(item.models)) {
        throw new Error("Provider connection response was invalid.");
      }
      option(
        connectionSelect,
        item.provider_id,
        `${item.name} · ${item.provider_id} · ${item.provider_type}`,
      );
      const row = documentRef.createElement("li");
      row.textContent =
        `${item.name} (${item.provider_id}) · ${item.provider_type} · ${item.state} · ` +
        `${item.models.length} catalog model(s) · ${item.request_capacity.provider_slots ?? "UNKNOWN"} request slot(s) · ` +
        "hardware feasibility UNKNOWN";
      el("connection-list").append(row);
    }
    renderModels();
  }

  function renderModels() {
    const current = connections.find(item => item.provider_id === connectionSelect.value);
    runtimeEvidence = null;
    el("model-runtime-state").textContent = "";
    el("model-runtime-evidence").textContent = "";
    modelSelect.replaceChildren();
    if (current) {
      for (const model of current.models) option(modelSelect, model, model);
    }
    state.textContent = current
      ? `${current.name}: ${current.state}; catalog source ${current.source}; checked ${current.checked_at ?? "unknown"}.`
      : connections.length
        ? "Choose a provider connection."
        : "No additional provider connections are configured.";
    controls();
  }

  function showRuntime(observation) {
    runtimeEvidence = observation;
    const runtime = observation.runtime;
    const loaded = Array.isArray(runtime.models) ? runtime.models : [];
    const rows = loaded.map(model => {
      const size = model.size_bytes === null ? "unknown" : `${model.size_bytes} bytes`;
      const vram = model.vram_bytes === null ? "unknown" : `${model.vram_bytes} bytes`;
      return `${model.name} · memory ${size} · VRAM ${vram} · context ${model.context_length ?? "unknown"}`;
    });
    el("model-runtime-evidence").textContent = [
      `Loaded models (${runtime.state}): ${rows.length ? rows.join("; ") : "none reported"}`,
      `Runtime probe latency: ${runtime.probe_latency_ms === null ? "unknown" : `${runtime.probe_latency_ms.toFixed(2)} ms`} (not inference latency)`,
      `Request slots: ${observation.request_capacity.provider_slots ?? "UNKNOWN"} provider / ${observation.request_capacity.global_slots ?? "UNKNOWN"} global; active requests ${observation.request_capacity.active_requests ?? "unknown"}`,
      `Hardware feasibility: ${observation.hardware_feasibility}; inference latency: ${observation.inference_latency}`,
      runtime.reason ?? "",
    ].filter(Boolean).join("\n");
    el("model-runtime-state").textContent = runtime.supported
      ? "Runtime status is provider-reported. A listed model is loaded once per provider/model, regardless of how many Agents share its assignment."
      : "This provider does not expose supported loaded-model telemetry or lifecycle controls.";
    controls();
  }

  async function refresh() {
    const sessionResponse = await request("/api/local/session");
    canManage = sessionResponse.permissions.includes("provider-connection:manage");
    const [agentResult, connectionResult] = await Promise.all([
      request("/api/agents"),
      request("/api/local/provider-connections"),
    ]);
    if (!Array.isArray(agentResult.items) || !Array.isArray(connectionResult.items)) {
      throw new Error("Provider connection response was invalid.");
    }
    agents = agentResult.items;
    connections = connectionResult.items;
    canManageRuntime = sessionResponse.permissions.includes("model-runtime:manage");
    agentSelect.replaceChildren();
    for (const agent of agents) {
      option(agentSelect, agent.id, `${agent.name} · ${agent.provider}/${agent.model}`);
    }
    renderConnections();
    controls();
  }

  async function run(action) {
    if (busy) return false;
    busy = true;
    controls();
    try {
      await action();
      return true;
    } catch (error) {
      state.textContent = error.message;
      return false;
    } finally {
      busy = false;
      controls();
    }
  }

  async function add() {
    return run(async () => {
      const common = {
        id: el("connection-id").value,
        name: el("connection-name").value,
        request_slots: Number(el("connection-slots").value),
      };
      state.textContent = "Verifying the explicitly selected provider connection…";
      try {
        if (kind.value === "gemini") {
          await request("/api/local/provider-connections/gemini", {
            method: "POST",
            body: { ...common, api_key: key.value },
          });
        } else {
          await request("/api/local/provider-connections/ollama", {
            method: "POST",
            body: { ...common, base_url: url.value },
          });
        }
      } finally {
        key.value = "";
      }
      el("connection-id").value = "";
      el("connection-name").value = "";
      await refresh();
      state.textContent = "Connection saved in memory for this app run. Hardware feasibility remains UNKNOWN.";
    });
  }

  async function refreshSelected() {
    return run(async () => {
      if (!connectionSelect.value) return;
      await request(`/api/local/provider-connections/${encodeURIComponent(connectionSelect.value)}/refresh`, {
        method: "POST",
      });
      await refresh();
      state.textContent = "Provider catalog/status refreshed from its configured source.";
    });
  }

  async function refreshRuntime() {
    return run(async () => {
      if (!connectionSelect.value) return;
      el("model-runtime-state").textContent = "Checking provider-reported loaded-model status…";
      const observation = await request(
        `/api/local/provider-connections/${encodeURIComponent(connectionSelect.value)}/runtime`,
      );
      showRuntime(observation);
    });
  }

  async function manageModel(action) {
    return run(async () => {
      const selected = connections.find(item => item.provider_id === connectionSelect.value);
      const model = modelSelect.value;
      if (!selected || !model) return;
      if (action === "unload" && !runtimeEvidence) {
        throw new Error("Refresh runtime status before unloading a model.");
      }
      const warning = action === "load"
        ? `Load ${model} on ${selected.provider_id} for ${el("model-keep-alive").value} seconds of idle time? This model may be shared by multiple Agents. Hardware fit is UNKNOWN; the local runtime may reject the request. No prompt is sent.`
        : `Unload shared model ${model} from ${selected.provider_id}? Active requests block unloading. Agents assigned this model may need it loaded again.`;
      if (!confirmImpl(warning)) {
        el("model-runtime-state").textContent = `Model ${action} cancelled; provider state is unchanged.`;
        return;
      }
      const path = `/api/local/provider-connections/${encodeURIComponent(selected.provider_id)}/models/${action}`;
      const result = await request(path, {
        method: "POST",
        body: { model_id: model, keep_alive_seconds: Number(el("model-keep-alive").value) },
      });
      showRuntime(result);
      el("model-runtime-state").textContent =
        `${action === "load" ? "Load" : "Unload"} requested for ${model}; operation took ${result.operation_latency_ms.toFixed(2)} ms. Hardware feasibility remains UNKNOWN.`;
    });
  }

  async function removeSelected() {
    return run(async () => {
      const selected = connections.find(item => item.provider_id === connectionSelect.value);
      if (!selected || !confirmImpl(
        `Remove ${selected.name} (${selected.provider_id}) and erase its in-memory credentials? ` +
        "Agents must be reassigned first; existing conversations retain their snapshots.",
      )) return;
      await request(`/api/local/provider-connections/${encodeURIComponent(selected.provider_id)}`, {
        method: "DELETE",
      });
      await refresh();
      state.textContent = "Provider connection removed and its in-memory credential erased.";
    });
  }

  async function assign() {
    return run(async () => {
      const agent = agents.find(item => item.id === agentSelect.value);
      const selected = connections.find(item => item.provider_id === connectionSelect.value);
      if (!agent || !selected || !modelSelect.value) return;
      const impact = await loadAgentAssignmentImpact(agent.id, fetchImpl);
      const dataPrivacy = selected.provider_type === "gemini"
        ? "Future chat turns and recent history are sent to Google only after separate per-turn consent."
        : "Requests are sent only to the configured loopback Ollama service.";
      const preview = [
        `Change ${agent.name} (${agent.id}) from ${agent.provider}/${agent.model} to ${selected.provider_id}/${modelSelect.value}?`,
        dataPrivacy,
        `Connection request slots: ${selected.request_capacity.provider_slots ?? "UNKNOWN"}. Hardware feasibility: UNKNOWN.`,
        assignmentImpactText(impact),
      ].join("\n\n");
      if (!confirmImpl(preview)) {
        state.textContent = "Assignment unchanged; the preview was cancelled.";
        return;
      }
      await request("/api/local/provider-connections/assignment", {
        method: "PUT",
        body: {
          agent_id: agent.id,
          provider_id: selected.provider_id,
          model_id: modelSelect.value,
          expected_provider_id: agent.provider,
          expected_model_id: agent.model,
        },
      });
      await refresh();
      state.textContent = "Agent assignment updated. Existing conversations keep their snapshots; start a new conversation to use it.";
    });
  }

  kind.addEventListener("change", controls);
  connectionSelect.addEventListener("change", renderModels);
  modelSelect.addEventListener("change", controls);
  agentSelect.addEventListener("change", controls);
  el("connection-add").addEventListener("click", add);
  el("connection-refresh").addEventListener("click", refreshSelected);
  el("model-runtime-refresh").addEventListener("click", refreshRuntime);
  el("model-load").addEventListener("click", () => manageModel("load"));
  el("model-unload").addEventListener("click", () => manageModel("unload"));
  el("connection-remove").addEventListener("click", removeSelected);
  el("assignment-save").addEventListener("click", assign);
  controls();
  return { initialLoad: run(refresh), add, assign, refresh, refreshSelected, refreshRuntime, manageModel, removeSelected };
}

if (typeof document !== "undefined" && document.getElementById("connection-type")) {
  mountProviderConnections();
}

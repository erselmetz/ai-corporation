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
  el("connection-remove").addEventListener("click", removeSelected);
  el("assignment-save").addEventListener("click", assign);
  controls();
  return { initialLoad: run(refresh), add, assign, refresh, refreshSelected, removeSelected };
}

if (typeof document !== "undefined" && document.getElementById("connection-type")) {
  mountProviderConnections();
}

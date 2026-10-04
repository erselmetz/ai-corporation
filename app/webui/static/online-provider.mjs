import {
  assignmentImpactText,
  loadAgentAssignmentImpact,
} from "./assignment-preview.mjs";

export function mountOnlineProvider({
  documentRef = document,
  fetchImpl = fetch,
  confirmImpl = globalThis.confirm,
} = {}) {
  const el = id => documentRef.getElementById(id);
  const key = el("gemini-key"), agents = el("gemini-agent"), models = el("gemini-model");
  const state = el("gemini-state"), usage = el("gemini-usage");
  let busy = false, permission = false, discovered = false, connected = false, connectionLive = false;
  let agentRecords = [];
  function controls() {
    el("gemini-discover").disabled = busy || !permission || !key.value;
    agents.disabled = busy || !permission || connected;
    models.disabled = busy || !discovered || !models.children.length;
    el("gemini-connect").disabled = busy || !permission || connected || !discovered || !models.value || !agents.value;
    el("gemini-refresh").disabled = busy || !permission || !connectionLive;
    el("gemini-disconnect").disabled = busy || !permission || !connected;
    el("gemini-clear").disabled = busy || !permission || !discovered || connected;
  }
  function clearModels() { models.replaceChildren(); discovered = false; }
  function option(select, value, label) {
    const row = documentRef.createElement("option"); row.value = value; row.textContent = label; select.append(row);
  }
  async function request(path, method = "GET", body = undefined) {
    const options = { method, credentials: "same-origin" };
    if (body !== undefined) {
      const session = await request("/api/local/session");
      options.headers = { "Content-Type": "application/json", "X-Local-CSRF": session.csrf };
      options.body = JSON.stringify(body);
    }
    const response = await fetchImpl(path, options);
    let data;
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) {
      if (response.status === 401) throw new Error("Sign in through local owner access first.");
      if (response.status === 403) throw new Error("This session lacks permission for Gemini setup.");
      throw new Error(typeof data.detail === "string" ? data.detail : "Gemini setup failed. Check provider status and limits.");
    }
    return data;
  }
  async function run(work) {
    if (busy) return;
    busy = true; controls();
    try { await work(); } catch (error) { state.textContent = error.message; }
    finally { busy = false; controls(); }
  }
  async function discover() {
    await run(async () => {
      clearModels(); state.textContent = "Checking the supplied key and listing Gemini models…";
      try {
        const result = await request("/api/local/online-provider/catalog", "POST", { api_key: key.value });
        for (const model of result.models) option(models, model, model);
        discovered = result.models.length > 0;
        state.textContent = discovered ? "Key verified. Choose a generation-capable model and Agent, then explicitly connect." : "No generation-capable text models were returned.";
      } finally { key.value = ""; }
    });
  }
  async function connect() {
    await run(async () => {
      const agent = agentRecords.find((item) => item.id === agents.value);
      if (!agent) return;
      const impact = await loadAgentAssignmentImpact(agent.id, fetchImpl);
      const preview = [
        `Connect Google Gemini ${models.value} to ${agent.name} (${agent.id}) instead of ${agent.provider}/${agent.model}?`,
        "Privacy: Google receives coordinator chat messages, recent history, and configured coordinator chat context only after separate per-turn consent. Individual Employee chat sends only its message and recent history; no Employee profile or Task content is added automatically.",
        assignmentImpactText(impact),
      ].join("\n\n");
      if (!confirmImpl(preview)) {
        state.textContent = "Connection unchanged; the preview was cancelled.";
        return;
      }
      const result = await request("/api/local/online-provider/connection", "PUT", {
        agent_id: agent.id,
        model_id: models.value,
        expected_provider_id: agent.provider,
        expected_model_id: agent.model,
      });
      connected = true; discovered = false; clearModels();
      state.textContent = `Connected ${result.provider_id}/${result.model_id} to Agent ${result.agent_id}. Each cloud reply still needs explicit chat consent.`;
      await loadStatus();
    });
  }
  async function disconnect() {
    await run(async () => {
      await request(`/api/local/online-provider/connection/${encodeURIComponent(agents.value)}`, "DELETE", {});
      connected = false; discovered = false; clearModels(); key.value = "";
      state.textContent = "Gemini disconnected and the in-memory key erased. Existing Gemini chats keep their history and need a new Agent assignment to send.";
      await loadStatus();
    });
  }
  async function eraseStaged() {
    await run(async () => {
      await request("/api/local/online-provider/credential", "DELETE", {});
      discovered = false; clearModels(); key.value = "";
      state.textContent = "The staged Gemini key was erased from this app run.";
    });
  }
  async function refresh() {
    await run(async () => {
      const result = await request("/api/local/online-provider/catalog/refresh", "POST", {});
      clearModels(); for (const model of result.models) option(models, model, model);
      discovered = result.models.length > 0;
      state.textContent = discovered
        ? connected ? "Gemini model list refreshed. Disconnect before changing this Agent’s model." : "Gemini model list refreshed. Select a model and connect."
        : "No generation-capable models are available.";
    });
  }
  async function loadStatus() {
    const session = await request("/api/local/session");
    permission = session.permissions.includes("online-provider:connect")
      && session.permissions.includes("online-provider:disconnect");
    const [agentList, connection] = await Promise.all([
      request("/api/agents"), request("/api/local/online-provider"),
    ]);
    agentRecords = agentList.items;
    for (const agent of agentRecords) option(agents, agent.id, `${agent.name} · ${agent.provider} · ${agent.model}`);
    const selected = connection.selected || connection.expired_assignment;
    connectionLive = connection.connected;
    connected = Boolean(selected);
    if (selected) agents.value = selected.agent_id;
    usage.textContent = connection.connected
      ? `Selected ${connection.selected.model_id}. ${connection.generation_calls_used} of ${connection.generation_calls_limit} generation attempts used in this app run. Key expiry in ${connection.expires_in_seconds} seconds.`
      : connection.expired_assignment
        ? `The Gemini credential expired for ${connection.expired_assignment.agent_name}. Disconnect to restore its previous model, then reconnect.`
        : "No Gemini Agent is connected.";
    state.textContent = connection.connected ? "Connected. Each cloud chat turn requires its own consent." : connection.expired_assignment ? "Credential expired; the registered adapter no longer holds the key." : "Enter a restricted Gemini API key to discover models.";
    controls();
  }
  key.addEventListener("input", controls);
  agents.addEventListener("change", controls); models.addEventListener("change", controls);
  el("gemini-discover").addEventListener("click", discover);
  el("gemini-connect").addEventListener("click", connect);
  el("gemini-disconnect").addEventListener("click", disconnect);
  el("gemini-clear").addEventListener("click", eraseStaged);
  el("gemini-refresh").addEventListener("click", refresh);
  controls();
  return { initialLoad: run(loadStatus), discover, connect, disconnect, eraseStaged, refresh, loadStatus };
}
if (typeof document !== "undefined" && document.getElementById("gemini-key")) mountOnlineProvider();

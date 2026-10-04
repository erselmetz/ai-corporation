import {
  assignmentImpactText,
  loadAgentAssignmentImpact,
} from "./assignment-preview.mjs";

export function mountLocalModels({
  documentRef = document,
  fetchImpl = fetch,
  confirmImpl = globalThis.confirm,
} = {}) {
  const el = id => documentRef.getElementById(id);
  const agents = el("model-agent"), models = el("model-installed");
  const state = el("model-state"), evidence = el("model-evidence");
  let observation = null, canSelect = false, busy = false, agentRecords = [];
  function clear() { observation = null; models.replaceChildren(); evidence.textContent = ""; }
  function controls() {
    agents.disabled = busy;
    el("model-refresh").disabled = busy || !agents.value;
    models.disabled = busy || !observation || !models.children.length;
    el("model-select").disabled = busy || !canSelect || !observation || !models.value;
  }
  async function request(path, options = {}) {
    const response = await fetchImpl(path, { credentials: "same-origin", ...options });
    if (!response.ok) {
      if (response.status === 401) throw new Error("Sign in through local owner access first.");
      if (response.status === 403) throw new Error("This session lacks permission for this operation.");
      if (response.status === 404) throw new Error("Local setup or Agent is unavailable. Use explicit local mode and refresh the list.");
      if (response.status === 409) throw new Error("Agent has active work or its assignment/inventory changed. Wait, then refresh before selecting again.");
      throw new Error("Local provider check failed. Check that Ollama is running, then refresh.");
    }
    return response.json();
  }
  async function run(action) {
    if (busy) return;
    busy = true; controls();
    try { await action(); } catch (error) { clear(); state.textContent = error.message; }
    finally { busy = false; controls(); }
  }
  function option(parent, value, text) {
    const node = documentRef.createElement("option"); node.value = value; node.textContent = text; parent.append(node);
  }
  agents.addEventListener("change", () => { clear(); state.textContent = "Refresh this Agent's installed models."; controls(); });
  models.addEventListener("change", controls);
  el("model-refresh").addEventListener("click", () => run(async () => {
    clear(); state.textContent = "Checking installed models…";
    observation = await request(`/api/local/models/${encodeURIComponent(agents.value)}`);
    const inventory = observation.inventory;
    for (const id of inventory.models) option(models, id, id);
    const selectedAgent = agentRecords.find((item) => item.id === observation.agent_id);
    evidence.textContent = `Agent: ${selectedAgent?.name ?? observation.agent_id} · Configured: ${observation.configured_model} · Installed: ${observation.configured_installed === null ? "unknown" : observation.configured_installed ? "yes" : "no"} · Service: ${inventory.state} · Source: ${inventory.source} · Checked: ${inventory.checked_at} · Execution readiness: unknown`;
    state.textContent = inventory.state === "available"
      ? inventory.models.length ? "Choose an installed model. Selection affects new conversations." : "No installed models reported. Install a model separately, then refresh."
      : inventory.reason || "Inventory is unknown; check the configured local provider.";
  }));
  el("model-select").addEventListener("click", () => run(async () => {
    const selectedAgent = agentRecords.find((item) => item.id === agents.value);
    if (!selectedAgent || !observation) return;
    const impact = await loadAgentAssignmentImpact(agents.value, fetchImpl);
    const preview = [
      `Change ${selectedAgent.name} (${selectedAgent.id}) from ${observation.provider_id}/${observation.configured_model} to ${observation.provider_id}/${models.value}?`,
      "Privacy: future chat messages, recent conversation history, and configured coordinator chat context may go to this local provider. No Employee profile or Task content is added automatically.",
      assignmentImpactText(impact),
    ].join("\n\n");
    if (!confirmImpl(preview)) {
      state.textContent = "Assignment unchanged; the preview was cancelled.";
      return;
    }
    const session = await request("/api/local/session");
    await request(`/api/local/models/${encodeURIComponent(agents.value)}`, {
      method: "PUT", headers: { "Content-Type": "application/json", "X-Local-CSRF": session.csrf },
      body: JSON.stringify({
        provider_id: observation.provider_id,
        model_id: models.value,
        expected_model_id: observation.configured_model,
      }),
    });
    clear(); state.textContent = "Agent model selected for this app run. Start a new conversation to use the changed assignment.";
  }));
  controls();
  return run(async () => {
    const session = await request("/api/local/session");
    canSelect = session.permissions.includes("local-model:select");
    const result = await request("/api/agents");
    agentRecords = result.items;
    for (const agent of agentRecords) option(agents, agent.id, `${agent.name} · ${agent.provider} · ${agent.model}`);
    state.textContent = "Choose an Agent and explicitly refresh inventory.";
  });
}
if (typeof document !== "undefined" && document.getElementById("model-agent")) mountLocalModels();

export function mountLocalModels({ documentRef = document, fetchImpl = fetch } = {}) {
  const el = id => documentRef.getElementById(id);
  const agents = el("model-agent"), models = el("model-installed");
  const state = el("model-state"), evidence = el("model-evidence");
  let observation = null, canSelect = false, busy = false;
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
      if (response.status === 404) throw new Error("Local setup or coordinator is unavailable. Use explicit local mode and refresh the list.");
      if (response.status === 409) throw new Error("Coordinator is busy or inventory changed. Wait, then refresh before selecting again.");
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
  agents.addEventListener("change", () => { clear(); state.textContent = "Refresh this coordinator's installed models."; controls(); });
  models.addEventListener("change", controls);
  el("model-refresh").addEventListener("click", () => run(async () => {
    clear(); state.textContent = "Checking installed models…";
    observation = await request(`/api/local/models/${encodeURIComponent(agents.value)}`);
    const inventory = observation.inventory;
    for (const id of inventory.models) option(models, id, id);
    evidence.textContent = `Configured: ${observation.configured_model} · Installed: ${observation.configured_installed === null ? "unknown" : observation.configured_installed ? "yes" : "no"} · Service: ${inventory.state} · Source: ${inventory.source} · Checked: ${inventory.checked_at} · Execution readiness: unknown`;
    state.textContent = inventory.state === "available"
      ? inventory.models.length ? "Choose an installed model. Selection affects new conversations." : "No installed models reported. Install a model separately, then refresh."
      : inventory.reason || "Inventory is unknown; check the configured local provider.";
  }));
  el("model-select").addEventListener("click", () => run(async () => {
    const session = await request("/api/local/session");
    await request(`/api/local/models/${encodeURIComponent(agents.value)}`, {
      method: "PUT", headers: { "Content-Type": "application/json", "X-Local-CSRF": session.csrf },
      body: JSON.stringify({ provider_id: observation.provider_id, model_id: models.value }),
    });
    clear(); state.textContent = "Model selected for this app run. Start a new conversation in Coordinator chat.";
  }));
  controls();
  return run(async () => {
    const session = await request("/api/local/session");
    canSelect = session.permissions.includes("local-model:select");
    const result = await request("/api/agents");
    for (const agent of result.items) option(agents, agent.id, `${agent.name} · ${agent.provider} · ${agent.model}`);
    state.textContent = "Choose a coordinator and explicitly refresh inventory.";
  });
}
if (typeof document !== "undefined" && document.getElementById("model-agent")) mountLocalModels();

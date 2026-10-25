// A window selects a route, never mutates the shared Agent assignment.
export function createChatWorkspace({ documentRef, windowRef, fetchImpl, onChange }) {
  const model = documentRef.getElementById("workspace-model");
  const project = documentRef.getElementById("workspace-project");
  const agent = documentRef.getElementById("chat-agent");
  let descriptor = null;
  let activeId = "";
  let choicesLoaded = false;
  let changing = false;
  const request = async (url, body) => {
    const session = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    const credentials = session.ok ? await session.json() : null;
    if (!credentials?.csrf) throw new Error("Sign in to choose a workspace.");
    const response = await fetchImpl(url, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": credentials.csrf }, body: JSON.stringify(body) });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Workspace selection is unavailable.");
    return result;
  };
  function option(select, value, text) {
    const node = documentRef.createElement("option"); node.value = value; node.textContent = text; select.append(node);
  }
  async function identity() {
    if (descriptor) return descriptor;
    if (windowRef?.desktopBridge?.getWorkspaceState) {
      descriptor = await windowRef.desktopBridge.getWorkspaceState();
    } else if (windowRef?.crypto?.randomUUID && windowRef?.sessionStorage) {
      let id = windowRef.sessionStorage.getItem("ersel-workspace-id");
      if (!id) { id = windowRef.crypto.randomUUID(); windowRef.sessionStorage.setItem("ersel-workspace-id", id); }
      descriptor = { id };
    }
    return descriptor;
  }
  async function initialize(agents) {
    const state = await identity();
    if (!state?.id) return null; // Legacy API/UI embedding keeps its existing contract.
    if (model && project && !choicesLoaded) {
      const response = await fetchImpl("/api/chat/workspaces/models", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Model choices could not be loaded. Retry.");
      const catalog = await response.json();
      model.replaceChildren(); option(model, "", "Agent default model");
      for (const item of catalog.items || []) option(model, JSON.stringify([item.provider_id, item.model_id]), `${item.model_id} · ${item.provider_id}`);
      const route = catalog.items?.find(item => item.model_id === state.model && (!state.provider || state.provider === item.provider_id));
      if (route) model.value = JSON.stringify([route.provider_id, route.model_id]);
      project.replaceChildren(); option(project, "", "Personal");
      const projectsResponse = await fetchImpl("/api/projects", { credentials: "same-origin", cache: "no-store" });
      const projects = projectsResponse.ok ? await projectsResponse.json() : null;
      for (const item of projects?.items || []) option(project, item.id, item.name);
      if (state.project && (projects?.items || []).some(item => item.id === state.project)) project.value = state.project;
      choicesLoaded = true;
    }
    const chosen = agents.find(item => item.id === state.agent) || agents.find(item => item.id === "local_worker") || agents[0];
    if (!chosen) throw new Error("No available Agent can open this workspace.");
    agent.value = chosen.id;
    const route = model?.value ? JSON.parse(model.value) : [state.provider || chosen.provider, state.model || chosen.model];
    const selected = await request("/api/chat/workspaces", { id: state.id, agent_id: chosen.id,
      provider_id: route[0], model_id: route[1], project_id: project?.value || state.project || "" });
    activeId = state.id;
    descriptor = { ...state, agent: selected.agent_id, provider: selected.provider_id,
      model: selected.model_id, project: selected.project_id };
    return descriptor;
  }
  async function change() {
    if (!descriptor || changing) return;
    changing = true;
    try {
      const route = model?.value ? JSON.parse(model.value) : ["", ""];
      const selected = await request("/api/chat/workspaces", { id: descriptor.id, agent_id: agent.value,
        provider_id: route[0], model_id: route[1], project_id: project?.value || "" });
      descriptor = { id: descriptor.id, conversation: "", agent: selected.agent_id,
        provider: selected.provider_id, model: selected.model_id, project: selected.project_id };
      await windowRef?.desktopBridge?.saveWorkspaceState?.(descriptor);
      await onChange(descriptor);
    } finally { changing = false; }
  }
  return {
    initialize, change,
    commit: () => descriptor ? request("/api/chat/workspaces", { id: descriptor.id,
      agent_id: descriptor.agent, provider_id: descriptor.provider, model_id: descriptor.model,
      project_id: descriptor.project || "" }) : Promise.resolve(null),
    saveBrief: brief => descriptor?.project ? request("/api/chat/workspaces/project-brief",
      { project_id: descriptor.project, brief }) : Promise.reject(new Error("Select a project first.")),
    fetch: (url, options = {}) => fetchImpl(url, { ...options,
      headers: { ...options.headers, ...(activeId && String(url).startsWith("/api/") && !String(url).startsWith("/api/chat/workspaces")
        ? { "X-Chat-Workspace": activeId } : {}) } }),
    selection: () => descriptor,
    setDisabled: value => { if (model) model.disabled = value; if (project) project.disabled = value; },
    remember: value => {
      if (!descriptor) return;
      descriptor = { ...descriptor, ...value };
      if (descriptor.agent) agent.value = descriptor.agent;
      if (project) project.value = descriptor.project || "";
      if (model) model.value = JSON.stringify([descriptor.provider, descriptor.model]);
    },
  };
}

const READ_OPTIONS = { credentials: "same-origin", headers: { Accept: "application/json" } };
const FILTERS = ["all", "active", "paused", "error", "builtin"];

function validAgent(item) {
  return Boolean(item && typeof item.id === "string" && typeof item.name === "string"
    && typeof item.role === "string" && typeof item.provider === "string" && typeof item.model === "string"
    && typeof item.builtin === "boolean");
}

function validStatus(item) {
  return Boolean(item && typeof item.agent_id === "string" && typeof item.status === "string"
    && typeof item.provider_id === "string" && typeof item.model_id === "string"
    && (item.last_active === null || typeof item.last_active === "string"));
}

function requestError(status) {
  if (status === 401) return "Sign in through local owner access first.";
  if (status === 403) return "This session does not have permission to view or manage Agents.";
  if (status === 404) return "This Agent is no longer available. Refresh the list.";
  if (status === 409) return "The Agent is active or the requested change conflicts with its current profile.";
  if (status === 422) return "The Agent profile was rejected. Check the name and selected profile.";
  return "The request could not be completed. Refresh and try again.";
}

export function mountAgentsPage({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
  locationRef = globalThis.location, cryptoRef = globalThis.crypto } = {}) {
  const el = id => documentRef.getElementById(id);
  const list = el("agent-list");
  const pageState = el("agent-page-state");
  const detailState = el("agent-detail-state");
  const detail = el("agent-detail-content");
  const createForm = el("agent-create-form");
  const createState = el("agent-create-state");
  const sourceSelect = el("agent-create-source");
  let agents = [];
  let employees = [];
  let statuses = new Map();
  let selectedId = null;
  let filter = "all";
  let view = "list";
  let loading = false;
  let treeLoaded = false;
  let listError = null;

  const text = (tag, value, className = "") => {
    const node = documentRef.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };

  async function request(path, { method = "GET", body } = {}) {
    const options = { ...READ_OPTIONS };
    if (method !== "GET") {
      const sessionResponse = await fetchImpl("/api/local/session", READ_OPTIONS);
      if (!sessionResponse.ok) throw Object.assign(new Error(), { status: sessionResponse.status });
      const session = await sessionResponse.json();
      options.method = method;
      options.headers = { ...READ_OPTIONS.headers, "Content-Type": "application/json", "X-Local-CSRF": session.csrf };
      options.body = JSON.stringify(body ?? {});
    }
    const response = await fetchImpl(path, options);
    let payload = {};
    try { payload = await response.json(); } catch { /* empty response */ }
    if (!response.ok) throw Object.assign(new Error(), { status: response.status, payload });
    return payload;
  }

  function stateFor(agent) {
    return statuses.get(agent.id)?.status ?? "unknown";
  }

  function matches(agent) {
    const state = stateFor(agent);
    if (filter === "active") return ["idle", "working", "waiting_for_approval"].includes(state);
    if (filter === "paused") return state === "paused";
    if (filter === "error") return ["error", "unavailable"].includes(state);
    if (filter === "builtin") return agent.builtin;
    return true;
  }

  function renderList() {
    list.replaceChildren();
    if (listError) {
      pageState.textContent = listError;
      list.append(text("li", listError, "error-state"));
      return;
    }
    const shown = agents.filter(matches);
    pageState.textContent = `${shown.length} of ${agents.length} Agent${agents.length === 1 ? "" : "s"}.`;
    if (!shown.length) list.append(text("li", "No Agents match this filter.", "empty-state"));
    for (const agent of shown) {
      const item = documentRef.createElement("li");
      item.className = "agent-card";
      const avatar = text("span", agent.name.trim().slice(0, 1).toUpperCase() || "A", "agent-avatar");
      avatar.setAttribute("aria-hidden", "true");
      const summary = documentRef.createElement("div");
      summary.className = "agent-card-summary";
      summary.append(text("h2", agent.name), text("p", agent.role),
        text("p", `${agent.provider} / ${agent.model}`, "agent-model"));
      if (agent.builtin) summary.append(text("span", "Built-in", "agent-builtin-badge"));
      const status = statuses.get(agent.id);
      const runtime = text("p", status?.status ?? "Status unknown", `agent-status status-${status?.status ?? "unknown"}`);
      runtime.setAttribute("aria-label", `Status: ${status?.status ?? "unknown"}`);
      summary.append(runtime);
      const activity = status?.last_active
        ? `Last active ${new Date(status.last_active).toLocaleString()}` : "No activity recorded this run";
      summary.append(text("p", activity, "agent-last-active"));
      const actions = documentRef.createElement("div");
      actions.className = "agent-card-actions";
      const detailsButton = text("button", "Details");
      detailsButton.type = "button";
      detailsButton.setAttribute("aria-label", `View ${agent.name} details`);
      detailsButton.addEventListener("click", () => loadDetails(agent));
      const employee = employees.find(row => row.agent_id === agent.id);
      const chat = text("a", "Chat");
      chat.href = employee ? `/ui/employee-chat?employee_id=${encodeURIComponent(employee.id)}` : "/ui/employee-chat";
      chat.setAttribute("aria-label", `Chat with ${agent.name} through its Employee identity`);
      actions.append(detailsButton, chat);
      item.append(avatar, summary, actions);
      list.append(item);
    }
    sourceSelect.replaceChildren();
    for (const agent of agents) {
      const option = documentRef.createElement("option");
      option.value = agent.id;
      option.textContent = `${agent.name} — ${agent.role}`;
      sourceSelect.append(option);
    }
  }

  async function loadTree() {
    const status = el("agent-tree-state");
    const tree = el("agent-organization-tree");
    status.textContent = "Loading recorded organization positions...";
    try {
      const data = await request("/api/structure-map");
      if (!Array.isArray(data.positions)) throw new Error("Invalid organization response.");
      const byParent = new Map();
      for (const position of data.positions) {
        if (position.reporting_state === "linked") {
          const parent = position.reports_to_position_id;
          byParent.set(parent, [...(byParent.get(parent) ?? []), position]);
        }
      }
      tree.replaceChildren();
      const seen = new Set();
      const renderNode = (position, depth) => {
        const item = documentRef.createElement("li");
        const summary = text("span", `${position.title}${position.active ? "" : " (inactive)"}`);
        const employee = position.employee?.state === "assigned"
          ? `${position.employee.name} (${position.employee.role})` : "No Employee assigned";
        const agent = position.agent?.state === "assigned"
          ? `${position.agent.name} (${position.agent.id})` : "No Agent assigned";
        item.append(summary, text("small", `${employee} · ${agent}`));
        if (!seen.has(position.id) && depth < 32) {
          seen.add(position.id);
          const children = byParent.get(position.id) ?? [];
          if (children.length) {
            const nested = documentRef.createElement("ul");
            for (const child of children) nested.append(renderNode(child, depth + 1));
            item.append(nested);
          }
        }
        return item;
      };
      for (const root of data.positions.filter(item => item.reporting_state !== "linked")) {
        tree.append(renderNode(root, 0));
      }
      for (const orphan of data.positions) if (!seen.has(orphan.id)) tree.append(renderNode(orphan, 0));
      status.textContent = `${data.positions.length} recorded position${data.positions.length === 1 ? "" : "s"}; Agent links are shown only when recorded.`;
      treeLoaded = true;
    } catch (error) {
      status.textContent = error.status === 401 ? "Sign in through local owner access first."
        : error.status === 403 ? "This session does not have permission to read the organization tree."
          : error.status ? "The organization tree could not be loaded. Refresh and retry."
            : "Organization data could not be loaded. Retry by reopening this view.";
      tree.replaceChildren();
      treeLoaded = false;
    }
  }

  function renderProfile(agent, profile) {
    detail.replaceChildren();
    const state = statuses.get(agent.id);
    const activity = state?.last_active ? new Date(state.last_active).toLocaleString() : "No activity recorded this run";
    detail.append(text("p", `Model route: ${agent.provider} / ${agent.model}`),
      text("p", `Current status: ${state?.status ?? "unknown"}${state?.reason ? ` — ${state.reason}` : ""}`),
      text("h3", "Recent activity"), text("p", activity));
    if (!profile) {
      detail.append(text("p", "Profile fields are available to an owner with Agent management permission."));
      detail.hidden = false;
      return;
    }
    const advanced = documentRef.createElement("details");
    advanced.className = "agent-advanced";
    advanced.append(text("summary", "Role profile and permissions"));
    const form = documentRef.createElement("form");
    form.className = "agent-profile-form";
    const fields = [
      ["Name", "name", profile.name, "input"], ["Role", "role", profile.role, "input"],
      ["Role instructions", "system_prompt", profile.system_prompt, "textarea"],
      ["Brain scopes (one per line)", "brain_scopes", (profile.brain_scopes ?? []).join("\n"), "textarea"],
      ["Allowed tools (one per line)", "allowed_tools", (profile.allowed_tools ?? []).join("\n"), "textarea"],
      ["Permissions (one per line)", "permissions", (profile.permissions ?? []).join("\n"), "textarea"],
    ];
    for (const [label, key, value, tag] of fields) {
      const fieldId = `agent-edit-${key}`;
      const labelNode = text("label", label);
      labelNode.htmlFor = fieldId;
      const input = documentRef.createElement(tag);
      input.id = fieldId;
      input.name = key;
      input.value = value;
      if (tag === "textarea") input.rows = key === "system_prompt" ? 4 : 2;
      form.append(labelNode, input);
    }
    const save = text("button", "Save profile");
    save.type = "submit";
    form.append(save);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      save.disabled = true;
      try {
        const lines = name => form.elements.namedItem(name).value.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
        const result = await request(`/api/agents/${encodeURIComponent(agent.id)}/profile`, { method: "PUT", body: {
          name: form.elements.namedItem("name").value,
          role: form.elements.namedItem("role").value,
          system_prompt: form.elements.namedItem("system_prompt").value,
          brain_scopes: lines("brain_scopes"), allowed_tools: lines("allowed_tools"), permissions: lines("permissions"),
        } });
        detailState.textContent = "Profile saved.";
        await refresh({ preserveSelection: false });
        const updated = agents.find(row => row.id === result.id);
        if (updated) await loadDetails(updated);
      } catch (error) { detailState.textContent = error.status ? requestError(error.status) : "Profile could not be saved."; }
      finally { save.disabled = false; }
    });
    advanced.append(form);
    const actions = documentRef.createElement("div");
    actions.className = "agent-profile-actions";
    const pause = text("button", profile.paused ? "Resume Agent" : "Pause Agent");
    pause.type = "button";
    pause.addEventListener("click", () => mutateAgent(agent, "PUT", "pause", { paused: !profile.paused }));
    actions.append(pause);
    if (profile.builtin_key) {
      const reset = text("button", "Reset built-in profile");
      reset.type = "button";
      reset.addEventListener("click", () => mutateAgent(agent, "POST", "reset", {}));
      actions.append(reset);
    }
    const duplicate = text("button", "Copy this profile");
    duplicate.type = "button";
    duplicate.addEventListener("click", () => { sourceSelect.value = agent.id; el("agent-create-name").focus(); el("agent-create-name").value = `${agent.name} copy`; el("agent-create-form").scrollIntoView?.({ block: "nearest" }); });
    actions.append(duplicate);
    detail.append(advanced, actions);
    detail.hidden = false;
  }

  async function loadDetails(agent) {
    selectedId = agent.id;
    el("agent-detail-title").textContent = agent.name;
    detail.replaceChildren(); detail.hidden = true;
    detailState.textContent = "Loading current Agent profile...";
    let profile = null;
    try {
      profile = await request(`/api/agents/${encodeURIComponent(agent.id)}/profile`);
    } catch (error) {
      if (error.status !== 403 && error.status !== 401) {
        detailState.textContent = error.status ? requestError(error.status) : "Profile could not be loaded. Retry.";
        return;
      }
    }
    renderProfile(agent, profile);
    detailState.textContent = profile ? "Current Agent profile." : "Read-only Agent summary.";
  }

  async function mutateAgent(agent, method, action, body) {
    try {
      await request(`/api/agents/${encodeURIComponent(agent.id)}/${action}`, { method, body });
      detailState.textContent = "Agent updated.";
      await refresh({ preserveSelection: false });
      const current = agents.find(item => item.id === agent.id);
      if (current) await loadDetails(current);
    } catch (error) { detailState.textContent = error.status ? requestError(error.status) : "Agent could not be updated."; }
  }

  async function refresh({ preserveSelection = true } = {}) {
    if (loading) return false;
    loading = true;
    listError = null;
    el("agent-refresh").disabled = true;
    pageState.textContent = "Loading current Agent and status information...";
    list.replaceChildren(text("li", "Loading Agents...", "empty-state"));
    try {
      const [agentResult, statusResult, employeeResult] = await Promise.all([
        request("/api/agents"), request("/api/local/agents/status"), request("/api/employees"),
      ]);
      if (!Array.isArray(agentResult.items) || !agentResult.items.every(validAgent)
        || !Array.isArray(statusResult.items) || !statusResult.items.every(validStatus)
        || !Array.isArray(employeeResult.items)) throw new Error("Invalid Agent workspace response.");
      agents = agentResult.items;
      statuses = new Map(statusResult.items.map(item => [item.agent_id, item]));
      employees = employeeResult.items;
      renderList();
      if (preserveSelection && selectedId) {
        const current = agents.find(item => item.id === selectedId);
        if (current) await loadDetails(current);
      }
      return true;
    } catch (error) {
      listError = error.status ? requestError(error.status) : "Agents could not be loaded. Check access and retry.";
      agents = [];
      employees = [];
      statuses.clear();
      selectedId = null;
      detail.replaceChildren();
      detailState.textContent = "Details are unavailable until the Agent list is refreshed.";
      sourceSelect.replaceChildren();
      renderList();
      return false;
    } finally { loading = false; el("agent-refresh").disabled = false; }
  }

  const filterButtons = [...el("agent-filters").querySelectorAll("[data-filter]")];
  function activateFilter(button, moveFocus = false) {
    filter = FILTERS.includes(button.dataset.filter) ? button.dataset.filter : "all";
    for (const choice of filterButtons) {
      const selected = choice.dataset.filter === filter;
      choice.setAttribute("aria-selected", String(selected));
      choice.tabIndex = selected ? 0 : -1;
    }
    el("agent-list-view").setAttribute("aria-labelledby", `agent-tab-${filter}`);
    if (moveFocus) button.focus();
    renderList();
  }
  for (const button of filterButtons) {
    button.addEventListener("click", () => activateFilter(button));
    button.addEventListener("keydown", event => {
      const current = filterButtons.indexOf(button);
      let next = null;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (current + 1) % filterButtons.length;
      if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (current - 1 + filterButtons.length) % filterButtons.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = filterButtons.length - 1;
      if (next !== null) { event.preventDefault(); activateFilter(filterButtons[next], true); }
    });
  }
  for (const button of documentRef.querySelectorAll("[data-view]")) {
    button.addEventListener("click", () => {
      view = button.dataset.view === "tree" ? "tree" : "list";
      el("agent-list-view").hidden = view !== "list";
      el("agent-tree-view").hidden = view !== "tree";
      for (const choice of documentRef.querySelectorAll("[data-view]")) choice.setAttribute("aria-pressed", String(choice.dataset.view === view));
      if (view === "tree" && !treeLoaded) loadTree();
    });
  }
  el("agent-refresh").addEventListener("click", () => refresh());
  createForm.addEventListener("submit", async event => {
    event.preventDefault();
    const sourceId = sourceSelect.value;
    const name = el("agent-create-name").value.trim();
    if (!sourceId || !name) { createState.textContent = "Choose a profile and enter a name."; return; }
    const submit = el("agent-create-submit"); submit.disabled = true;
    try {
      const suffix = cryptoRef.randomUUID().replaceAll("-", "");
      const result = await request(`/api/agents/${encodeURIComponent(sourceId)}/duplicate`, { method: "POST", body: { new_id: `custom_${suffix}`, name } });
      createState.textContent = `Created ${result.name}. Review its permissions before use.`;
      el("agent-create-name").value = "";
      await refresh({ preserveSelection: false });
      const created = agents.find(item => item.id === result.id);
      if (created) await loadDetails(created);
    } catch (error) { createState.textContent = error.status ? requestError(error.status) : "Agent could not be created."; }
    finally { submit.disabled = false; }
  });
  refresh();
  return { refresh, renderList };
}

if (globalThis.document?.getElementById("agent-list")) mountAgentsPage();

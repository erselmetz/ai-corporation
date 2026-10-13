const dashboardResources = {
  status: { path: "/api/status", fields: null },
  employees: { path: "/api/employees", fields: ["id", "name", "role"] },
  agents: { path: "/api/agents", fields: ["id", "name", "role"] },
  providers: { path: "/api/providers", fields: ["id", "type"] },
  models: { path: "/api/models", fields: ["agent_id", "provider_id", "model_id"] },
  tasks: { path: "/api/tasks", fields: ["id", "title", "status"] },
  projects: { path: "/api/projects", fields: ["id", "name", "status"] },
  activity: {
    path: "/api/activity?limit=8",
    fields: ["id", "task_id", "event", "created_at"],
  },
  conversations: { path: "/api/chat/conversations", fields: null },
  approvals: { path: "/api/capabilities/approvals", fields: null },
  system: { path: "/api/system/monitor", fields: null },
};

function validPayload(resource, payload) {
  if (!payload || typeof payload !== "object") return false;
  if (resource.fields) {
    return Array.isArray(payload.items) && payload.items.every(
      (item) => item && resource.fields.every((field) => (
        typeof item[field] === (
          field === "id" && resource.path.startsWith("/api/activity")
            ? "number"
            : "string"
        )
      )),
    );
  }
  if (resource.path === "/api/status") return Boolean(
    payload.corporation &&
    typeof payload.corporation.id === "string" &&
    typeof payload.corporation.name === "string" &&
    payload.node &&
    typeof payload.node.id === "string" &&
    typeof payload.node.name === "string",
  );
  if (resource.path === "/api/system/monitor") {
    return typeof payload.observed_at === "string" && Array.isArray(payload.task_status_counts)
      && typeof payload.provider_availability === "string"
      && (payload.resource_capacities === null || Array.isArray(payload.resource_capacities));
  }
  return Array.isArray(payload.items);
}

export async function loadDashboard(fetchImpl = globalThis.fetch) {
  const entries = await Promise.all(
    Object.entries(dashboardResources).map(async ([name, resource]) => {
      try {
        const response = await fetchImpl(resource.path, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        });
        if (response.status === 401) return [name, { error: "authentication" }];
        if (response.status === 403) return [name, { error: "forbidden" }];
        if (!response.ok) return [name, { error: "failed" }];

        const payload = await response.json();
        if (!validPayload(resource, payload)) {
          return [name, { error: "failed" }];
        }
        return [name, { data: payload, observedAt: new Date().toISOString() }];
      } catch {
        return [name, { error: "failed" }];
      }
    }),
  );
  const results = Object.fromEntries(entries);
  const corporationId = results.status?.data?.corporation?.id;
  if (typeof corporationId !== "string" || !corporationId) {
    results.memory = { error: results.status?.error ?? "unknown" };
  } else {
    const query = new URLSearchParams({ scope: "corporation", scope_id: corporationId, limit: "10" });
    try {
      const response = await fetchImpl(`/api/memory?${query}`, {
        credentials: "same-origin", headers: { Accept: "application/json" },
      });
      if (response.status === 401) results.memory = { error: "authentication" };
      else if (response.status === 403) results.memory = { error: "forbidden" };
      else if (!response.ok) results.memory = { error: "failed" };
      else {
        const payload = await response.json();
        if (!payload || !Array.isArray(payload.items) || !payload.items.every((item) =>
          item && typeof item.id === "string" && typeof item.type === "string"
          && typeof item.created_at === "string" && typeof item.expires_at === "string")) {
          results.memory = { error: "failed" };
        } else results.memory = { data: payload, observedAt: new Date().toISOString() };
      }
    } catch {
      results.memory = { error: "failed" };
    }
  }
  return results;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function addDefinition(container, label, value) {
  const row = element("div", "data-row");
  row.append(element("dt", "", label), element("dd", "", value));
  container.append(row);
}

function addList(container, items, emptyMessage, renderItem) {
  if (items.length === 0) {
    container.append(element("p", "empty-state", emptyMessage));
    return;
  }
  const list = element("ul", "compact-list");
  for (const item of items) list.append(renderItem(item));
  container.append(list);
}

function namedEntry(primary, secondary) {
  const item = element("li", "list-entry");
  item.append(element("strong", "", primary));
  if (secondary) item.append(element("span", "muted", secondary));
  return item;
}

function setPanel(panelId, outcome, loadingText, render) {
  const panel = document.getElementById(panelId);
  const state = panel.querySelector(".section-state");
  const data = panel.querySelector(".section-data");
  data.replaceChildren();
  data.hidden = true;

  if (outcome === undefined) {
    state.textContent = loadingText;
    state.className = "section-state";
    return;
  }
  if (outcome.error) {
    const errors = {
      authentication: "Sign-in required. This browser session is not authenticated.",
      forbidden: "Access denied. This account lacks the required read permission.",
      failed: "Data could not be loaded. Retry to try again.",
      unknown: "Source freshness is unknown because workspace identity could not be read.",
    };
    state.textContent = errors[outcome.error];
    state.className = "section-state error-state";
    return;
  }

  state.textContent = "Data loaded";
  state.className = "section-state success-state";
  data.hidden = false;
  appendFreshness(data, outcome.observedAt);
  render(data, outcome.data);
}

function appendFreshness(data, value) {
  const freshness = element("time", "snapshot-freshness", "Snapshot checked");
  const observedAt = value ?? new Date().toISOString();
  freshness.dateTime = observedAt;
  freshness.dataset.observedAt = observedAt;
  freshness.textContent = freshnessText(observedAt);
  data.prepend(freshness);
}

function freshnessText(value, now = Date.now()) {
  const observed = Date.parse(value);
  if (!Number.isFinite(observed)) return "Freshness unknown; refresh to retry.";
  const age = Math.max(0, now - observed);
  return `${age > 60_000 ? "STALE" : "Snapshot"} · checked ${new Date(observed).toLocaleString()}`;
}

function updateFreshnessLabels(now = Date.now()) {
  for (const marker of document.querySelectorAll?.(".snapshot-freshness[data-observed-at]") ?? []) {
    marker.textContent = freshnessText(marker.dataset.observedAt, now);
    marker.classList?.toggle?.("stale", now - Date.parse(marker.dataset.observedAt) > 60_000);
  }
}

function setCombinedPanel(panelId, resources, render) {
  const panel = document.getElementById(panelId);
  const state = panel.querySelector(".section-state");
  const data = panel.querySelector(".section-data");
  data.replaceChildren();
  data.hidden = true;

  const failures = resources.filter(([, outcome]) => outcome.error);
  const available = resources.filter(([, outcome]) => outcome.data);
  data.hidden = false;
  const sourceReadTimes = available
    .map(([, outcome]) => Date.parse(outcome.observedAt))
    .filter(Number.isFinite);
  appendFreshness(data, sourceReadTimes.length
    ? new Date(Math.min(...sourceReadTimes)).toISOString()
    : undefined);
  if (failures.length) {
    state.textContent = available.length
      ? "Some data could not be loaded."
      : "Data could not be loaded.";
    state.className = "section-state error-state";
    for (const [name, outcome] of failures) {
      const label = name === "employees" ? "Employee data" :
        name === "agents" ? "Agent data" :
        name === "providers" ? "Provider data" : "Model assignment data";
      data.append(element(
        "p",
        "source-error",
        `${label}: ${errorMessage(outcome.error)}`,
      ));
    }
  } else {
    state.textContent = "Data loaded";
    state.className = "section-state success-state";
  }
  render(data, Object.fromEntries(available.map(([name, outcome]) => [name, outcome.data.items])));
}

function errorMessage(error) {
  return {
    authentication: "Sign-in required; this browser session is not authenticated.",
    forbidden: "Access denied; the account lacks the required read permission.",
    failed: "Could not be loaded; retry to try again.",
  }[error];
}

function addSetupLink(container, label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.textContent = label;
  container.append(link);
}

function renderSetup(results) {
  const badge = document.getElementById("setup-state");
  const detail = document.getElementById("setup-detail");
  const links = document.querySelector(".setup-links");
  const relevant = [results.status, results.agents, results.providers];
  const auth = relevant.some((result) => result?.error === "authentication");
  const forbidden = relevant.some((result) => result?.error === "forbidden");
  const failed = relevant.some((result) => result?.error === "failed");
  badge.className = "setup-badge";
  links.replaceChildren();

  if (auth) {
    badge.textContent = "SIGN-IN REQUIRED";
    detail.textContent = "Sign in with the local owner account to review your setup. The default API requires its own authentication backend.";
    addSetupLink(links, "Sign in", "/ui/login");
    return;
  }
  if (forbidden) {
    badge.textContent = "ACCESS DENIED";
    detail.textContent = "This session cannot read one or more setup records. Ask the local owner to review access.";
    addSetupLink(links, "Owner sign-in", "/ui/login");
    return;
  }
  if (failed) {
    badge.textContent = "UNAVAILABLE";
    badge.classList.add("state-unavailable");
    detail.textContent = "Setup information could not be read. This does not report provider health; refresh to try again.";
    return;
  }

  const agents = results.agents.data.items;
  const providers = results.providers.data.items;
  const providerIds = new Set(providers.map((provider) => provider.id));
  const assigned = agents.some((agent) =>
    typeof agent.provider === "string" && providerIds.has(agent.provider)
    && typeof agent.model === "string" && agent.model.trim().length > 0);
  if (!providers.length || !assigned) {
    badge.textContent = "SETUP REQUIRED";
    badge.classList.add("state-required");
    detail.textContent = !providers.length
      ? "No provider is registered yet. Review provider setup, then check that an AI team member has a model assigned."
      : "No registered AI team member has a model assignment that matches a configured provider.";
    addSetupLink(links, "Review providers & models", "/ui/providers");
    addSetupLink(links, "Review AI team", "/ui/employees");
    return;
  }

  badge.textContent = "PARTIALLY CONFIGURED";
  badge.classList.add("state-partial");
  detail.textContent = "Provider and model assignments are present. Availability has not been checked, so the first chat will confirm whether the selected service can reply.";
  addSetupLink(links, "Review providers & models", "/ui/providers");
}

function renderStatus(container, payload) {
  const details = element("dl", "identity-list");
  addDefinition(details, "Workspace", payload.corporation.name);
  addDefinition(details, "Local node", payload.node.name);
  container.append(details);
}

function renderWorkforce(container, { employees, agents }) {
  for (const [label, items] of [
    ["Employees", employees],
    ["Agents", agents],
  ]) {
    if (!items) continue;
    const group = element("div", "data-group");
    group.append(element("h3", "", `${label} · ${items.length}`));
    addList(
      group,
      items.slice(0, 4),
      `No ${label.toLowerCase()} found.`,
      (item) => namedEntry(item.name, `${item.role} · ${item.id}`),
    );
    if (items.length > 4) {
      group.append(element("p", "muted", `Showing 4 of ${items.length} records.`));
    }
    container.append(group);
  }
}

function renderProviders(container, { providers, models }) {
  if (providers) {
    const providerGroup = element("div", "data-group");
    providerGroup.append(element("h3", "", `Configured providers · ${providers.length}`));
    addList(
      providerGroup,
      providers.slice(0, 4),
      "No providers are configured.",
      (provider) => namedEntry(provider.id, `Type: ${provider.type}`),
    );
    if (providers.length > 4) {
      providerGroup.append(element("p", "muted", `Showing 4 of ${providers.length} providers.`));
    }
    container.append(providerGroup);
  }

  if (models) {
    const modelGroup = element("div", "data-group");
    modelGroup.append(element("h3", "", `Agent model assignments · ${models.length}`));
    addList(
      modelGroup,
      models.slice(0, 4),
      "No model assignments found.",
      (assignment) => namedEntry(
        assignment.agent_id,
        `${assignment.provider_id} · ${assignment.model_id}`,
      ),
    );
    if (models.length > 4) {
      modelGroup.append(element("p", "muted", `Showing 4 of ${models.length} assignments.`));
    }
    container.append(modelGroup);
  }

  container.prepend(element(
    "p",
    "muted",
    "Configured identifiers only; provider availability is not reported by the API.",
  ));
}

function renderTasks(container, payload) {
  const tasks = payload.items;
  if (tasks.length === 0) {
    container.append(element("p", "empty-state", "No tasks found."));
    return;
  }

  const counts = new Map();
  for (const task of tasks) counts.set(task.status, (counts.get(task.status) ?? 0) + 1);
  const statusList = element("ul", "status-counts");
  for (const [status, count] of counts) {
    statusList.append(namedEntry(status, String(count)));
  }
  container.append(statusList);

  const active = tasks.filter((task) => task.status === "pending" || task.status === "running");
  const sample = element("div", "data-group");
  sample.append(element("h3", "", `Active tasks · ${active.length}`));
  addList(
    sample,
    active.slice(0, 4),
    "No pending or running tasks.",
    (task) => namedEntry(task.title, `${task.id} · ${task.status}`),
  );
  if (tasks.length > 4) {
    sample.append(element("p", "muted", `Showing 4 of ${tasks.length} task records; task timestamps are not provided.`));
  }
  container.append(sample);
  container.append(element("p", "muted", "Task records have no source timestamps; freshness is based on the last dashboard read."));
}

function renderProjects(container, payload) {
  const projects = payload.items.filter((project) => project.status === "active");
  if (projects.length === 0) container.append(element("p", "empty-state", "No active projects."));
  else addList(container, projects.slice(0, 5), "No active projects.",
    (project) => namedEntry(project.name, `${project.id} · ${project.status}`));
  if (projects.length > 5) {
    container.append(element("p", "muted", `Showing 5 of ${projects.length} projects.`));
  }
  container.append(element("p", "muted", "Project records have no source timestamps; freshness is based on the last dashboard read."));
}

function renderActivity(container, payload) {
  const activity = payload.items;
  addList(
    container,
    activity,
    "No recent activity found.",
    (entry) => namedEntry(entry.event, `Task ${entry.task_id} · ${entry.created_at}`),
  );
}

function renderConversations(container, payload) {
  const items = payload.items.filter((item) => item && typeof item.id === "string");
  if (!items.length) container.append(element("p", "empty-state", "No open owner conversations."));
  else {
    const latest = items.slice(-5).reverse();
    addList(container, latest, "No open owner conversations.", (item) =>
      namedEntry(item.coordinator?.name ?? item.coordinator?.id ?? "Coordinator chat", `Conversation ${item.id}`));
  }
  const link = element("a", "dashboard-card-link", "Open chat");
  link.href = "/ui/chat";
  container.append(link);
}

function renderApprovals(container, payload) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  const pending = items.filter((item) => item.status === "pending");
  container.append(element("p", "data-count", `${pending.length} pending owner approval${pending.length === 1 ? "" : "s"}`));
  addList(container, pending.slice(0, 4), "No pending protected-action approvals.", (item) =>
    namedEntry(item.action_summary ?? item.action_id ?? "Protected action", `${item.requested_at ?? "Request time unavailable"} · expires ${item.expires_at ?? "unknown"}`));
  container.append(element("p", "muted", "Approval details and decisions use the protected approval API; there is no separate review page."));
}

function renderSystem(container, payload) {
  const observedAt = payload.observed_at ?? "unknown";
  container.append(element("p", "muted", `Provider availability: ${payload.provider_availability ?? "unknown"} · no provider probe is run.`));
  const counts = element("ul", "status-counts");
  for (const item of payload.task_status_counts ?? []) counts.append(namedEntry(item.status, String(item.count)));
  container.append(counts);
  const capacities = payload.resource_capacities;
  if (Array.isArray(capacities)) {
    addList(container, capacities.slice(0, 5), "No resource snapshot available.", (item) =>
      namedEntry(item.scope, `${item.allocated}/${item.limit} slots · ${item.remaining} remaining`));
    container.append(element("p", "muted", "Configured request slots are software concurrency, not hardware capacity."));
  } else container.append(element("p", "empty-state", "Resource capacity is not configured; hardware availability is unknown."));
  container.append(element("p", "muted", `Server snapshot: ${observedAt}`));
}

function renderKnowledge(container, payload) {
  const items = [...payload.items].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
  addList(container, items.slice(0, 5), "No owner-readable Corporation knowledge is retained.", (item) =>
    namedEntry(item.type, `${item.id} · created ${item.created_at} · expires ${item.expires_at}`));
  container.append(element("p", "muted", "Metadata only. Private conversation and Project memory are not enumerated here."));
  const link = element("a", "dashboard-card-link", "Inspect knowledge");
  link.href = "/ui/memory";
  container.append(link);
}

export function renderDashboard(results) {
  renderSetup(results);
  setPanel("status-panel", results.status, "Loading status…", renderStatus);
  setCombinedPanel(
    "workforce-panel",
    [["employees", results.employees], ["agents", results.agents]],
    renderWorkforce,
  );
  setCombinedPanel(
    "providers-panel",
    [["providers", results.providers], ["models", results.models]],
    renderProviders,
  );
  setPanel("tasks-panel", results.tasks, "Loading tasks…", renderTasks);
  setPanel("projects-panel", results.projects, "Loading projects…", renderProjects);
  setPanel("activity-panel", results.activity, "Loading activity…", renderActivity);
  setPanel("chat-panel", results.conversations, "Loading owner chat…", renderConversations);
  setPanel("system-panel", results.system, "Loading system snapshot…", renderSystem);
  setPanel("approvals-panel", results.approvals, "Loading approvals…", renderApprovals);
  setPanel("knowledge-panel", results.memory, "Loading retained knowledge…", renderKnowledge);
  updateFreshnessLabels();
}

async function refreshDashboard() {
  const button = document.getElementById("dashboard-retry");
  document.getElementById("setup-state").textContent = "CHECKING";
  document.getElementById("setup-state").className = "setup-badge";
  document.getElementById("setup-detail").textContent = "Checking the available setup information. No provider health check will run.";
  button.disabled = true;
  button.textContent = "Loading…";
  const panels = [
    ["status-panel", "Loading status…"],
    ["workforce-panel", "Loading workforce…"],
    ["providers-panel", "Loading provider information…"],
    ["tasks-panel", "Loading tasks…"],
    ["projects-panel", "Loading projects…"],
    ["activity-panel", "Loading activity…"],
    ["chat-panel", "Loading owner chat…"],
    ["system-panel", "Loading system snapshot…"],
    ["approvals-panel", "Loading approvals…"],
    ["knowledge-panel", "Loading retained knowledge…"],
  ];
  for (const [panelId, message] of panels) setPanel(panelId, undefined, message, () => {});
  try {
    renderDashboard(await loadDashboard());
  } finally {
    button.disabled = false;
    button.textContent = "Refresh status";
  }
}

if (typeof document !== "undefined") {
  document.getElementById("dashboard-retry").addEventListener("click", refreshDashboard);
  refreshDashboard();
  window.setInterval?.(updateFreshnessLabels, 15_000);
}

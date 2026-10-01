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
  return Boolean(
    payload.corporation &&
    typeof payload.corporation.id === "string" &&
    typeof payload.corporation.name === "string" &&
    payload.node &&
    typeof payload.node.id === "string" &&
    typeof payload.node.name === "string",
  );
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
        return [name, { data: payload }];
      } catch {
        return [name, { error: "failed" }];
      }
    }),
  );
  return Object.fromEntries(entries);
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
    };
    state.textContent = errors[outcome.error];
    state.className = "section-state error-state";
    return;
  }

  state.textContent = "Data loaded";
  state.className = "section-state success-state";
  data.hidden = false;
  render(data, outcome.data);
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

function renderStatus(container, payload) {
  const details = element("dl", "identity-list");
  addDefinition(details, "Corporation", payload.corporation.name);
  addDefinition(details, "Corporation ID", payload.corporation.id);
  addDefinition(details, "Node", payload.node.name);
  addDefinition(details, "Node ID", payload.node.id);
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

  const sample = element("div", "data-group");
  sample.append(element("h3", "", "Task records"));
  addList(
    sample,
    tasks.slice(0, 4),
    "No tasks found.",
    (task) => namedEntry(task.title, `${task.id} · ${task.status}`),
  );
  if (tasks.length > 4) {
    sample.append(element("p", "muted", `Showing 4 of ${tasks.length} task records; task timestamps are not provided.`));
  }
  container.append(sample);
}

function renderProjects(container, payload) {
  const projects = payload.items;
  addList(
    container,
    projects.slice(0, 5),
    "No projects found.",
    (project) => namedEntry(project.name, `${project.id} · ${project.status}`),
  );
  if (projects.length > 5) {
    container.append(element("p", "muted", `Showing 5 of ${projects.length} projects.`));
  }
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

export function renderDashboard(results) {
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
}

async function refreshDashboard() {
  const button = document.getElementById("dashboard-retry");
  button.disabled = true;
  button.textContent = "Loading…";
  const panels = [
    ["status-panel", "Loading status…"],
    ["workforce-panel", "Loading workforce…"],
    ["providers-panel", "Loading provider information…"],
    ["tasks-panel", "Loading tasks…"],
    ["projects-panel", "Loading projects…"],
    ["activity-panel", "Loading activity…"],
  ];
  for (const [panelId, message] of panels) setPanel(panelId, undefined, message, () => {});
  try {
    renderDashboard(await loadDashboard());
  } finally {
    button.disabled = false;
    button.textContent = "Retry data loading";
  }
}

if (typeof document !== "undefined") {
  document.getElementById("dashboard-retry").addEventListener("click", refreshDashboard);
  refreshDashboard();
}

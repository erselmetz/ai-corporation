// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";

import {
  loadDashboard,
  renderDashboard,
} from "../app/webui/static/dashboard.mjs";

const expectedPaths = [
  "/api/status",
  "/api/employees",
  "/api/agents",
  "/api/providers",
  "/api/models",
  "/api/tasks",
  "/api/projects",
  "/api/activity?limit=8",
  "/api/chat/conversations",
  "/api/capabilities/approvals",
  "/api/system/monitor",
  "/api/memory?scope=corporation&scope_id=corp&limit=10",
];

function response(status, payload) {
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() {
      return payload;
    },
  };
}

class TestElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.hidden = false;
    this._text = "";
    this.href = "";
    this.dataset = {};
    this.className = "";
    this.classList = { add: (name) => { this.className += ` ${name}`; }, toggle: () => {} };
  }

  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }

  append(...children) {
    this.children.push(...children);
  }

  prepend(child) {
    this.children.unshift(child);
  }

  replaceChildren(...children) {
    this._text = "";
    this.children = children;
  }
}

function dashboardDocument() {
  const panels = new Map();
  const setup = new Map([
    ["setup-state", new TestElement("span")],
    ["setup-detail", new TestElement("p")],
    ["setup-links", new TestElement("div")],
  ]);
  for (const panelId of [
    "status-panel",
    "workforce-panel",
    "providers-panel",
    "tasks-panel",
    "projects-panel",
    "activity-panel",
    "chat-panel",
    "system-panel",
    "approvals-panel",
    "knowledge-panel",
  ]) {
    const panel = new TestElement("section");
    const state = new TestElement("p");
    const data = new TestElement("div");
    panel.append(state, data);
    panel.querySelector = (selector) => selector === ".section-state" ? state : data;
    panels.set(panelId, panel);
  }
  return {
    panels,
    document: {
      createElement: (tagName) => new TestElement(tagName),
      getElementById: (id) => setup.get(id) ?? panels.get(id),
      querySelector: (selector) => selector === ".setup-links" ? setup.get("setup-links") : null,
      querySelectorAll: () => [],
    },
    setup,
  };
}

function setupResults({ agents = [], providers = [], error } = {}) {
  const result = (items) => error ? { error } : { data: { items } };
  return {
    status: error ? { error } : { data: { corporation: { id: "c", name: "AI" }, node: { id: "n", name: "Local" } } },
    agents: result(agents), providers: result(providers),
    employees: result([]), models: result([]), tasks: result([]), projects: result([]), activity: result([]),
    conversations: result([]), approvals: result([]),
    system: error ? { error } : { data: { observed_at: "2026-10-14T00:00:00Z", task_status_counts: [], provider_availability: "unknown", resource_capacities: null } },
    memory: result([]),
  };
}

test("setup guidance distinguishes sign-in, missing configuration, and unchecked availability", () => {
  const { document, setup } = dashboardDocument();
  globalThis.document = document;
  try {
    renderDashboard(setupResults({ error: "authentication" }));
    assert.equal(setup.get("setup-state").textContent, "SIGN-IN REQUIRED");
    assert.equal(setup.get("setup-links").children[0].href, "/ui/login");

    renderDashboard(setupResults());
    assert.equal(setup.get("setup-state").textContent, "SETUP REQUIRED");
    assert.match(setup.get("setup-detail").textContent, /No provider is registered/);

    renderDashboard(setupResults({
      providers: [{ id: "ollama" }],
      agents: [{ id: "worker", provider: "ollama", model: "llama3.2:3b" }],
    }));
    assert.equal(setup.get("setup-state").textContent, "PARTIALLY CONFIGURED");
    assert.match(setup.get("setup-detail").textContent, /Availability has not been checked/);
    assert.doesNotMatch(setup.get("setup-state").textContent, /READY/);
  } finally {
    delete globalThis.document;
  }
});

test("setup read failure is unavailable, not an empty or healthy provider state", () => {
  const { document, setup } = dashboardDocument();
  globalThis.document = document;
  try {
    renderDashboard(setupResults({ error: "failed" }));
    assert.equal(setup.get("setup-state").textContent, "UNAVAILABLE");
    assert.match(setup.get("setup-detail").textContent, /does not report provider health/);
  } finally {
    delete globalThis.document;
  }
});

test("loads the existing protected read resources with same-origin credentials", async () => {
  const calls = [];
  const results = await loadDashboard(async (path, options) => {
    calls.push({ path, options });
    if (path.startsWith("/api/memory?")) return response(200, { items: [] });
    return response(200, path === "/api/status"
      ? {
          corporation: { id: "corp", name: "Corporation" },
          node: { id: "node", name: "Node" },
        }
      : path === "/api/system/monitor"
        ? { observed_at: "2026-10-14T00:00:00Z", task_status_counts: [], provider_availability: "unknown", resource_capacities: null }
        : { items: [] });
  });

  assert.deepEqual(calls.map(({ path }) => path).sort(), [...expectedPaths].sort());
  assert.ok(calls.every(({ options }) => options.credentials === "same-origin"));
  assert.ok(calls.every(({ options }) => options.headers.Accept === "application/json"));
  assert.ok(calls.some(({ path }) => path === "/api/memory?scope=corporation&scope_id=corp&limit=10"));
  assert.deepEqual(results.employees.data, { items: [] });
  assert.equal(typeof results.employees.observedAt, "string");
  assert.deepEqual(results.status.data.node, { id: "node", name: "Node" });
});

test("preserves empty lists as successful data rather than converting failures to empty", async () => {
  const results = await loadDashboard(async (path) => response(
    200,
    path === "/api/status"
      ? {
          corporation: { id: "corp", name: "Corporation" },
          node: { id: "node", name: "Node" },
        }
      : path === "/api/system/monitor"
        ? { observed_at: "2026-10-14T00:00:00Z", task_status_counts: [], provider_availability: "unknown", resource_capacities: null }
        : { items: [] },
  ));

  for (const name of ["employees", "agents", "providers", "models", "tasks", "projects", "activity", "conversations", "approvals", "memory"]) {
    assert.deepEqual(results[name].data, { items: [] });
  }
});

test("distinguishes authentication, authorization, and other failures per resource", async () => {
  const results = await loadDashboard(async (path) => {
    if (path === "/api/status") return response(403, {});
    if (path === "/api/employees") return response(403, {});
    if (path === "/api/agents") return response(500, {});
    if (path === "/api/providers") throw new Error("network unavailable");
    if (path === "/api/models") return response(200, { unexpected: [] });
    if (path === "/api/tasks") return response(200, { items: [] });
    if (path === "/api/projects") return response(200, { items: [] });
    return response(200, { items: [] });
  });

  assert.deepEqual(results.status, { error: "forbidden" });
  assert.deepEqual(results.employees, { error: "forbidden" });
  assert.deepEqual(results.agents, { error: "failed" });
  assert.deepEqual(results.providers, { error: "failed" });
  assert.deepEqual(results.models, { error: "failed" });
  assert.deepEqual(results.tasks.data, { items: [] });
});

test("signed-out dashboard makes one identity request and clears and hides protected panels", async () => {
  const calls = [];
  const results = await loadDashboard(async path => {
    calls.push(path);
    return response(401, {});
  });
  assert.deepEqual(calls, ["/api/status"]);
  assert.ok(Object.values(results).every(value => value.error === "authentication"));
  const { document, panels } = dashboardDocument();
  globalThis.document = document;
  try {
    renderDashboard(results);
    for (const panel of panels.values()) {
      assert.equal(panel.hidden, true);
      assert.equal(panel.querySelector(".section-data").textContent.includes("Snapshot"), false);
    }
  } finally { delete globalThis.document; }
});

test("renders empty collections explicitly", () => {
  const { document, panels } = dashboardDocument();
  globalThis.document = document;
  try {
    renderDashboard({
      status: {
        data: {
          corporation: { id: "corp", name: "Corporation" },
          node: { id: "node", name: "Node" },
        },
      },
      employees: { data: { items: [] } },
      agents: { data: { items: [] } },
      providers: { data: { items: [] } },
      models: { data: { items: [] } },
      tasks: { data: { items: [] } },
      projects: { data: { items: [] } },
      activity: { data: { items: [] } },
      conversations: { data: { items: [] } },
      approvals: { data: { items: [] } },
      system: { data: { observed_at: "2026-10-14T00:00:00Z", task_status_counts: [], provider_availability: "unknown", resource_capacities: null } },
      memory: { data: { items: [] } },
    });

    for (const panel of panels.values()) {
      assert.equal(panel.querySelector(".section-data").hidden, false);
    }
    assert.match(panels.get("workforce-panel").textContent, /No employees found/);
    assert.match(panels.get("workforce-panel").textContent, /No agents found/);
    assert.match(panels.get("providers-panel").textContent, /No providers are configured/);
    assert.match(panels.get("tasks-panel").textContent, /No tasks found/);
    assert.match(panels.get("projects-panel").textContent, /No active projects/);
    assert.match(panels.get("activity-panel").textContent, /No recent activity found/);
    assert.match(panels.get("chat-panel").textContent, /No open owner conversations/);
    assert.match(panels.get("system-panel").textContent, /hardware availability is unknown/);
    assert.match(panels.get("approvals-panel").textContent, /No pending protected-action approvals/);
    assert.match(panels.get("knowledge-panel").textContent, /No owner-readable Corporation knowledge/);
  } finally {
    delete globalThis.document;
  }
});

test("dashboard shows only pending work and active projects, with unknown source freshness where timestamps are absent", () => {
  const { document, panels } = dashboardDocument();
  globalThis.document = document;
  try {
    renderDashboard({
      ...setupResults(),
      tasks: { data: { items: [
        { id: "pending", title: "Queued", status: "pending" },
        { id: "done", title: "Finished", status: "completed" },
      ] } },
      projects: { data: { items: [
        { id: "active", name: "Current", status: "active" },
        { id: "closed", name: "Archived", status: "completed" },
      ] } },
    });
    const tasks = panels.get("tasks-panel").textContent;
    assert.match(tasks, /Active tasks · 1/);
    assert.match(tasks, /Queued/);
    assert.doesNotMatch(tasks, /Finished/);
    assert.match(tasks, /source timestamps/);
    const projects = panels.get("projects-panel").textContent;
    assert.match(projects, /Current/);
    assert.doesNotMatch(projects, /Archived/);
  } finally {
    delete globalThis.document;
  }
});

test("renders failed and partial responses without hiding successful panel data", () => {
  const { document, panels } = dashboardDocument();
  globalThis.document = document;
  try {
    renderDashboard({
      status: { error: "authentication" },
      employees: { error: "forbidden" },
      agents: { data: { items: [{ id: "agent-1", name: "Worker", role: "Worker" }] } },
      providers: { error: "failed" },
      models: { data: { items: [] } },
      tasks: { error: "failed" },
      projects: { data: { items: [] } },
      activity: { error: "forbidden" },
    });

    assert.match(panels.get("status-panel").textContent, /Sign-in required/);
    assert.match(panels.get("workforce-panel").textContent, /Access denied/);
    assert.match(panels.get("workforce-panel").textContent, /Worker/);
    assert.match(panels.get("providers-panel").textContent, /could not be loaded/i);
    assert.match(panels.get("providers-panel").textContent, /No model assignments found/);
    assert.match(panels.get("tasks-panel").textContent, /Retry to try again/);
    assert.match(panels.get("projects-panel").textContent, /No active projects/);
    assert.match(panels.get("activity-panel").textContent, /Access denied/);
  } finally {
    delete globalThis.document;
  }
});

test("shows distinct authentication and forbidden failures for combined panels", () => {
  const { document, panels } = dashboardDocument();
  globalThis.document = document;
  try {
    const unavailable = { error: "failed" };
    renderDashboard({
      status: unavailable,
      employees: { error: "authentication" },
      agents: { error: "forbidden" },
      providers: unavailable,
      models: unavailable,
      tasks: unavailable,
      projects: unavailable,
      activity: unavailable,
    });

    const workforce = panels.get("workforce-panel").textContent;
    assert.match(workforce, /Sign-in required/);
    assert.match(workforce, /Access denied/);
  } finally {
    delete globalThis.document;
  }
});

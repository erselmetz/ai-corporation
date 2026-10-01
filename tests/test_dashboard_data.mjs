import assert from "node:assert/strict";
import test from "node:test";

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
  for (const panelId of [
    "status-panel",
    "workforce-panel",
    "providers-panel",
    "tasks-panel",
    "projects-panel",
    "activity-panel",
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
      getElementById: (id) => panels.get(id),
    },
  };
}

test("loads the existing protected read resources with same-origin credentials", async () => {
  const calls = [];
  const results = await loadDashboard(async (path, options) => {
    calls.push({ path, options });
    return response(200, path === "/api/status"
      ? {
          corporation: { id: "corp", name: "Corporation" },
          node: { id: "node", name: "Node" },
        }
      : { items: [] });
  });

  assert.deepEqual(calls.map(({ path }) => path).sort(), [...expectedPaths].sort());
  assert.ok(calls.every(({ options }) => options.credentials === "same-origin"));
  assert.ok(calls.every(({ options }) => options.headers.Accept === "application/json"));
  assert.deepEqual(results.employees, { data: { items: [] } });
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
      : { items: [] },
  ));

  for (const name of ["employees", "agents", "providers", "models", "tasks", "projects", "activity"]) {
    assert.deepEqual(results[name], { data: { items: [] } });
  }
});

test("distinguishes authentication, authorization, and other failures per resource", async () => {
  const results = await loadDashboard(async (path) => {
    if (path === "/api/status") return response(401, {});
    if (path === "/api/employees") return response(403, {});
    if (path === "/api/agents") return response(500, {});
    if (path === "/api/providers") throw new Error("network unavailable");
    if (path === "/api/models") return response(200, { unexpected: [] });
    if (path === "/api/tasks") return response(200, { items: [] });
    if (path === "/api/projects") return response(200, { items: [] });
    return response(200, { items: [] });
  });

  assert.deepEqual(results.status, { error: "authentication" });
  assert.deepEqual(results.employees, { error: "forbidden" });
  assert.deepEqual(results.agents, { error: "failed" });
  assert.deepEqual(results.providers, { error: "failed" });
  assert.deepEqual(results.models, { error: "failed" });
  assert.deepEqual(results.tasks, { data: { items: [] } });
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
    });

    for (const panel of panels.values()) {
      assert.equal(panel.querySelector(".section-data").hidden, false);
    }
    assert.match(panels.get("workforce-panel").textContent, /No employees found/);
    assert.match(panels.get("workforce-panel").textContent, /No agents found/);
    assert.match(panels.get("providers-panel").textContent, /No providers are configured/);
    assert.match(panels.get("tasks-panel").textContent, /No tasks found/);
    assert.match(panels.get("projects-panel").textContent, /No projects found/);
    assert.match(panels.get("activity-panel").textContent, /No recent activity found/);
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
    assert.match(panels.get("projects-panel").textContent, /No projects found/);
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

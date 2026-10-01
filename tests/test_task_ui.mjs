import assert from "node:assert/strict";
import test from "node:test";

import { mountTaskPage } from "../app/webui/static/tasks.mjs";

function response(status, payload) {
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() {
      return payload;
    },
  };
}

class Element {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.listeners = new Map();
    this.attributes = {};
    this.value = "";
    this.text = "";
    this.hidden = false;
    this.disabled = false;
    this.className = "";
    this.name = "";
  }

  get textContent() {
    return this.text + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this.text = String(value);
    this.children = [];
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.text = "";
    this.children = children;
  }

  setAttribute(name, value) {
    this.attributes[name] = value;
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async dispatch(type, event = {}) {
    for (const listener of this.listeners.get(type) ?? []) {
      await listener({ preventDefault() {}, ...event });
    }
  }

  reset() {
    for (const field of this.formFields ?? []) field.value = "";
  }
}

function findElement(root, predicate) {
  for (const child of root.children) {
    if (predicate(child)) return child;
    const nested = findElement(child, predicate);
    if (nested) return nested;
  }
  return null;
}

function pageElements() {
  const ids = [
    "task-list",
    "task-list-state",
    "task-refresh",
    "task-detail",
    "task-detail-state",
    "task-preview",
    "task-preview-state",
    "task-create-form",
    "task-create-submit",
    "task-create-state",
    "task-title",
    "task-description",
    "task-project-id",
    "task-agent-id",
    "task-role",
    "task-capability",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element("div")]));
  elements["task-create-form"].formFields = [
    elements["task-title"],
    elements["task-description"],
    elements["task-project-id"],
    elements["task-agent-id"],
    elements["task-role"],
    elements["task-capability"],
  ];
  const documentRef = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements[id],
  };
  return { documentRef, elements };
}

const task = {
  id: "TASK-1",
  title: "Review research",
  description: "Summarize the supplied research material.",
  project_id: "project-1",
  status: "pending",
  assigned_agent: null,
  required_role: "Researcher",
  required_capability: null,
};

const dryRun = {
  task_id: "TASK-1",
  task_title: "Review research",
  task_description: "Summarize the supplied research material.",
  selected_agent_id: "agent-1",
  selected_agent_name: "Research Agent",
  selected_agent_role: "Researcher",
  selected_employee_id: "employee-1",
  selected_employee_name: "Research Employee",
  provider: "local",
  model: "model-x",
  routing_method: "employee_role",
  status: "ready",
};

test("loads Task records and displays the existing Task response fields", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      if (path === "/api/tasks") return response(200, { items: [task] });
      return response(200, task);
    },
  });

  await controller.initialLoad;
  assert.equal(calls[0][0], "/api/tasks");
  assert.equal(calls[0][1].credentials, "same-origin");
  assert.equal(elements["task-list"].children.length, 1);
  assert.match(elements["task-list"].textContent, /TASK-1.*Review research.*pending/);

  await controller.loadTaskDetail(task.id);
  assert.ok(calls.some(([path]) => path === "/api/tasks/TASK-1"));
  assert.match(elements["task-detail"].textContent, /Summarize the supplied research material/);
  assert.match(elements["task-detail"].textContent, /project-1/);
  assert.match(elements["task-detail"].textContent, /Researcher/);
});

test("creates a Task with only supported non-empty fields and refreshes details", async () => {
  const { documentRef, elements } = pageElements();
  elements["task-title"].value = "New work";
  elements["task-description"].value = "Perform the requested analysis.";
  elements["task-project-id"].value = "project-1";
  elements["task-role"].value = "Researcher";
  const calls = [];
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (options.method === "POST") return response(201, { ...task, id: "TASK-2", title: "New work" });
      if (path === "/api/tasks") return response(200, { items: [task, { ...task, id: "TASK-2", title: "New work" }] });
      if (path === "/api/tasks/TASK-2") return response(200, { ...task, id: "TASK-2", title: "New work" });
      return response(200, task);
    },
  });
  await controller.initialLoad;
  await controller.createTask({ preventDefault() {} });

  const [path, options] = calls.find(([, item]) => item.method === "POST");
  assert.equal(path, "/api/tasks");
  assert.deepEqual(JSON.parse(options.body), {
    title: "New work",
    description: "Perform the requested analysis.",
    project_id: "project-1",
    role: "Researcher",
  });
  assert.equal(options.credentials, "same-origin");
  assert.equal(elements["task-list"].children.length, 2);
  assert.match(elements["task-create-state"].textContent, /TASK-2 created/);
  assert.match(elements["task-detail"].textContent, /New work/);
});

test("prevents duplicate Task submissions while the first request is pending", async () => {
  const { documentRef, elements } = pageElements();
  elements["task-title"].value = "One submission";
  elements["task-description"].value = "Only create once.";
  let release;
  let submissions = 0;
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (options.method === "POST") {
        submissions += 1;
        return new Promise((resolve) => {
          release = () => resolve(response(201, { ...task, id: "TASK-2" }));
        });
      }
      if (path === "/api/tasks") return response(200, { items: [{ ...task, id: "TASK-2" }] });
      return response(200, { ...task, id: "TASK-2" });
    },
  });
  await controller.initialLoad;
  const first = controller.createTask({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(elements["task-create-submit"].disabled, true);
  await controller.createTask({ preventDefault() {} });
  assert.equal(submissions, 1);
  release();
  await first;
});

test("rejects blank and multiple routing selectors before submission", async () => {
  const { documentRef, elements } = pageElements();
  let submissions = 0;
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (_path, options = {}) => {
      if (options.method === "POST") submissions += 1;
      return response(200, { items: [] });
    },
  });
  await controller.initialLoad;
  await controller.createTask({ preventDefault() {} });
  assert.match(elements["task-create-state"].textContent, /required/);
  elements["task-title"].value = "Invalid routing";
  elements["task-description"].value = "More than one route.";
  elements["task-agent-id"].value = "agent-1";
  elements["task-capability"].value = "research";
  await controller.createTask({ preventDefault() {} });
  assert.match(elements["task-create-state"].textContent, /no more than one routing selector/);
  assert.equal(submissions, 0);
});

test("uses the existing non-mutating dry-run endpoint and renders its declared response", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (path === "/api/tasks") return response(200, { items: [task] });
      if (path.endsWith("/dry-run")) return response(200, dryRun);
      return response(200, task);
    },
  });
  await controller.initialLoad;
  await controller.loadTaskDetail(task.id);
  await controller.runDryRun(task.id);
  const [path, options] = calls.find(([url]) => url.endsWith("/dry-run"));
  assert.equal(path, "/api/tasks/TASK-1/dry-run");
  assert.equal(options.method, "POST");
  assert.equal(options.credentials, "same-origin");
  assert.equal("body" in options, false);
  assert.match(elements["task-preview"].textContent, /Research Agent/);
  assert.match(elements["task-preview"].textContent, /Research Employee/);
  assert.match(elements["task-preview"].textContent, /model-x/);
  assert.match(elements["task-preview-state"].textContent, /No Task state was changed/);
});

test("handles missing/deleted Task detail and refreshes the list", async () => {
  const { documentRef, elements } = pageElements();
  let list = [task];
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path) => {
      if (path === "/api/tasks") return response(200, { items: list });
      if (path === "/api/tasks/TASK-1") return response(404);
      return response(200, task);
    },
  });
  await controller.initialLoad;
  await controller.loadTaskDetail(task.id);
  assert.match(elements["task-detail-state"].textContent, /no longer exists/i);
  assert.equal(elements["task-list"].children.length, 0);

  list = [];
  await controller.loadTasks();
  assert.equal(elements["task-list"].children.length, 0);
  assert.equal(elements["task-detail"].hidden, true);
});

test("clears previously loaded Tasks and details when a list refresh fails", async () => {
  const { documentRef, elements } = pageElements();
  let failList = false;
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path) => {
      if (path === "/api/tasks") {
        return failList ? response(503) : response(200, { items: [task] });
      }
      return response(200, task);
    },
  });
  await controller.initialLoad;
  await controller.loadTaskDetail(task.id);
  assert.equal(elements["task-list"].children.length, 1);
  assert.equal(elements["task-detail"].hidden, false);

  failList = true;
  await controller.loadTasks();
  assert.equal(elements["task-list"].children.length, 0);
  assert.equal(elements["task-detail"].hidden, true);
  assert.match(elements["task-list-state"].textContent, /could not be completed/);
  assert.doesNotMatch(elements["task-list-state"].textContent, /No tasks found/, "failure must not render as empty state");
});

test("distinguishes authentication, permission, validation, conflict, missing and general errors", async () => {
  const { documentRef, elements } = pageElements();
  let listResponse = response(401);
  let createResponse = response(409);
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (options.method === "POST") return createResponse;
      if (path === "/api/tasks") return listResponse;
      if (path === "/api/tasks/TASK-1") return response(404);
      return response(500);
    },
  });
  await controller.initialLoad;
  assert.match(elements["task-list-state"].textContent, /Sign-in required/);

  listResponse = response(403);
  await controller.loadTasks();
  assert.match(elements["task-list-state"].textContent, /Access denied/);

  elements["task-title"].value = "Title";
  elements["task-description"].value = "Description";
  await controller.createTask({ preventDefault() {} });
  assert.match(elements["task-create-state"].textContent, /conflicts/);

  createResponse = response(404);
  await controller.createTask({ preventDefault() {} });
  assert.match(elements["task-create-state"].textContent, /Project was not found/);
  createResponse = response(400);
  await controller.createTask({ preventDefault() {} });
  assert.match(elements["task-create-state"].textContent, /routing selection/);
  createResponse = response(422, {
    detail: [{ loc: ["body", "title"], msg: "Value cannot be blank", input: "" }],
  });
  await controller.createTask({ preventDefault() {} });
  assert.match(elements["task-create-state"].textContent, /title: Value cannot be blank/);
  assert.doesNotMatch(elements["task-create-state"].textContent, /input/);

  listResponse = response(200, { items: [task] });
  await controller.loadTasks();
  await controller.loadTaskDetail(task.id);
  assert.match(elements["task-detail-state"].textContent, /no longer exists/);
});

test("renders a successful empty Task list distinctly from a failed request", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async () => response(200, { items: [] }),
  });
  await controller.initialLoad;
  assert.equal(elements["task-list-state"].textContent, "No tasks found.");
  assert.equal(elements["task-list"].children.length, 0);
});

test("does not implement unsupported Task deletion or lifecycle mutation", async () => {
  const { documentRef } = pageElements();
  const calls = [];
  const controller = mountTaskPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      return response(200, { items: [] });
    },
  });
  await controller.initialLoad;
  assert.equal("deleteTask" in controller, false);
  assert.equal(calls.some(([, options]) => ["DELETE", "PATCH", "PUT"].includes(options.method)), false);
});

test("browser Task module contains no credentials or direct internal-layer access", async () => {
  const { readFile } = await import("node:fs/promises");
  const source = await readFile(new URL("../app/webui/static/tasks.mjs", import.meta.url), "utf8");
  assert.match(source, /\/api\/tasks/);
  assert.doesNotMatch(source, /Bearer\s|api_key|password|secret|process\.env|os\.environ/i);
  assert.doesNotMatch(source, /TaskRegistry|TaskLogger|Orchestrator|ProviderRegistry|Ollama|sqlite|filesystem/i);
  assert.doesNotMatch(source, /method:\s*["']DELETE["']/);
});

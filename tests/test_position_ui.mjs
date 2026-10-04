import assert from "node:assert/strict";
import test from "node:test";

import { mountPositionManagementPage } from "../app/webui/static/positions.mjs";

class Element {
  constructor(id = "") {
    this.id = id;
    this.children = [];
    this.listeners = new Map();
    this.attributes = {};
    this.value = "";
    this.text = "";
    this.hidden = false;
    this.disabled = false;
  }

  get textContent() {
    return this.text + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this.text = String(value);
    this.children = [];
  }

  set innerHTML(_) {
    throw new Error("HTML injection is forbidden");
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
}

const ids = [
  "position-state", "position-list", "position-detail-state", "position-detail",
  "position-history", "position-form", "position-form-state", "position-save",
  "position-deactivate", "position-remove", "position-title",
  "position-responsibilities", "position-reports-to", "position-employee",
  "position-new",
];

function setup(handler) {
  const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));
  const calls = [];
  const documentRef = {
    getElementById: (id) => elements[id],
    createElement: (tag) => new Element(tag),
  };
  const fetchImpl = async (path, options = {}) => {
    calls.push([path, options]);
    const result = await handler(path, options);
    return {
      status: result.status,
      ok: result.status >= 200 && result.status < 300,
      async json() { return result.body; },
    };
  };
  const controller = mountPositionManagementPage({
    documentRef,
    fetchImpl,
    confirmImpl: () => true,
  });
  return { controller, elements, calls };
}

const templates = [
  "Architect", "Developer", "Researcher", "Reasoning Analyst", "QA Engineer",
  "Security", "Code Reviewer", "Project Manager", "Technical Writer", "UI/UX",
];

test("loads actual position and revision data as inert text", async () => {
  const position = {
    id: "position-1",
    title: "Architect",
    responsibilities: ["Review design"],
    reports_to_position_id: null,
    employee_id: "employee-1",
    active: true,
    revision: 2,
    history: [{
      revision: 1,
      title: "Developer",
      responsibilities: ["Build software"],
      reports_to_position_id: null,
      employee_id: "employee-1",
      active: true,
      recorded_at: "2026-10-04T00:00:00+00:00",
    }],
  };
  const ui = setup(async (path) => {
    if (path === "/api/positions") return { status: 200, body: { items: [position] } };
    if (path === "/api/positions/templates") return { status: 200, body: { items: templates } };
    if (path === "/api/employees") {
      return { status: 200, body: { items: [{ id: "employee-1", name: "<Owner>" }] } };
    }
    throw new Error(`Unexpected request ${path}`);
  });

  assert.equal(await ui.controller.initialLoad, true);
  await ui.elements["position-list"].children[0].children[0].dispatch("click");
  assert.match(ui.elements["position-detail"].textContent, /Architect/);
  assert.match(ui.elements["position-detail"].textContent, /employee-1/);
  assert.match(ui.elements["position-history"].textContent, /Revision 1: Developer/);
  assert.ok(ui.elements["position-history"].textContent.includes("employee-1"));
  assert.equal(ui.elements["position-detail"].textContent.includes("<Owner>"), false);
});

test("creates a position through same-origin API with CSRF and independent references", async () => {
  const ui = setup(async (path, options) => {
    if (path === "/api/local/session") return { status: 200, body: { csrf: "csrf-token" } };
    if (path === "/api/positions/templates") return { status: 200, body: { items: templates } };
    if (path === "/api/employees") return { status: 200, body: { items: [] } };
    if (path === "/api/positions" && options.method === "POST") {
      const created = {
        id: "position-new",
        ...JSON.parse(options.body),
        active: true,
        revision: 1,
        history: [],
      };
      return { status: 201, body: created };
    }
    if (path === "/api/positions") {
      const saved = ui.calls.find(([url, request]) => url === "/api/positions" && request.method === "POST");
      return {
        status: 200,
        body: { items: saved ? [{
          id: "position-new",
          ...JSON.parse(saved[1].body),
          active: true,
          revision: 1,
          history: [],
        }] : [] },
      };
    }
    throw new Error(`Unexpected request ${path} ${options.method}`);
  });
  await ui.controller.initialLoad;
  ui.elements["position-title"].value = "Researcher";
  ui.elements["position-responsibilities"].value = "Inspect sources\nRecord unknowns";
  const event = { prevented: false, preventDefault() { this.prevented = true; } };
  assert.equal(await ui.controller.submit(event), true);
  assert.equal(event.prevented, true);
  const create = ui.calls.find(([path, options]) => path === "/api/positions" && options.method === "POST");
  assert.equal(create[1].credentials, "same-origin");
  assert.equal(create[1].headers["X-Local-CSRF"], "csrf-token");
  assert.deepEqual(JSON.parse(create[1].body), {
    title: "Researcher",
    responsibilities: ["Inspect sources", "Record unknowns"],
    reports_to_position_id: null,
    employee_id: null,
  });
  assert.match(ui.elements["position-detail"].textContent, /position-new/);
});

test("position readers without employee:read retain existing employee references", async () => {
  const position = {
    id: "position-1",
    title: "Architect",
    responsibilities: ["Review design"],
    reports_to_position_id: null,
    employee_id: "employee-private",
    active: true,
    revision: 1,
    history: [],
  };
  const ui = setup(async (path) => {
    if (path === "/api/positions") return { status: 200, body: { items: [position] } };
    if (path === "/api/positions/templates") return { status: 200, body: { items: templates } };
    if (path === "/api/employees") return { status: 403, body: { detail: "Forbidden" } };
    if (path === "/api/positions/position-1") return { status: 200, body: position };
    throw new Error(`Unexpected request ${path}`);
  });

  assert.equal(await ui.controller.initialLoad, true);
  await ui.controller.selectPosition("position-1");
  assert.equal(ui.elements["position-employee"].value, "employee-private");
  assert.match(
    ui.elements["position-form-state"].textContent,
    /lacks employee:read; existing references are preserved/,
  );
});

import assert from "node:assert/strict";
import test from "node:test";
import { mountAgentsPage } from "../app/webui/static/agents.mjs";

class Element {
  constructor(tag = "div", dataset = {}) {
    this.tagName = tag.toUpperCase(); this.dataset = dataset; this.children = []; this.listeners = {};
    this.attributes = {}; this.hidden = false; this.disabled = false; this.value = ""; this.text = "";
    this.elements = { namedItem: name => this.children.find(child => child.name === name) };
  }
  set textContent(value) { this.text = value; this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(""); }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(...nodes) { for (const node of nodes) { this.children.push(node); if (this.tagName === "SELECT" && this.children.length === 1) this.value = node.value; } }
  replaceChildren(...nodes) { this.children = []; this.text = ""; if (this.tagName === "SELECT") this.value = ""; this.append(...nodes); }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelectorAll() { return this.buttons ?? []; }
  focus() { this.focused = true; }
  scrollIntoView() {}
}

function setup({ profileAllowed = true } = {}) {
  const ids = ["agent-list", "agent-page-state", "agent-detail-state", "agent-detail-content", "agent-create-form",
    "agent-create-state", "agent-create-source", "agent-create-name", "agent-create-submit", "agent-refresh",
    "agent-detail-title", "agent-list-view", "agent-tree-view", "agent-tree-state", "agent-organization-tree", "agent-filters"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(id.includes("source") ? "select" : "div")]));
  const filters = ["all", "active", "paused", "error", "builtin"].map(filter => new Element("button", { filter }));
  const views = ["list", "tree"].map(view => new Element("button", { view }));
  elements["agent-filters"].buttons = filters;
  const documentRef = {
    getElementById: id => elements[id],
    createElement: tag => new Element(tag),
    querySelectorAll: selector => selector === "[data-view]" ? views : [],
  };
  const calls = [];
  const items = [
    { id: "local_worker", name: "Coordinator", role: "Routes work", provider: "ollama", model: "llama3.2:3b", builtin: true },
    { id: "paused_one", name: "Paused", role: "Review", provider: "ollama", model: "m", builtin: true },
    { id: "custom_error", name: "Custom", role: "Writer", provider: "gemini", model: "g", builtin: false },
  ];
  const statuses = [
    { agent_id: "local_worker", status: "idle", reason: null, provider_id: "ollama", model_id: "llama3.2:3b", last_active: null },
    { agent_id: "paused_one", status: "paused", reason: null, provider_id: "ollama", model_id: "m", last_active: null },
    { agent_id: "custom_error", status: "unavailable", reason: "Assigned model is not installed.", provider_id: "gemini", model_id: "g", last_active: null },
  ];
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    const respond = (payload, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => payload });
    if (path === "/api/agents") return respond({ items });
    if (path === "/api/local/agents/status") return respond({ items: statuses });
    if (path === "/api/employees") return respond({ items: items.map((item, i) => ({ id: `employee-${i}`, agent_id: item.id })) });
    if (path === "/api/structure-map") return respond({ positions: [{ id: "position-root", title: "Coordinator", active: true,
      reporting_state: "root", reports_to_position_id: null,
      employee: { state: "assigned", name: "Coordinator", role: "Coordinates" },
      agent: { state: "assigned", id: "local_worker", name: "Coordinator" } }] });
    if (path === "/api/local/session") return respond({ csrf: "csrf-token" });
    if (path.endsWith("/pause") && options.method === "PUT") return respond({ id: "local_worker", paused: true });
    if (path.endsWith("/reset") && options.method === "POST") return respond({ id: "local_worker", paused: false });
    if (path.endsWith("/profile")) {
      return profileAllowed ? respond({ id: "local_worker", name: "Coordinator", role: "Routes work",
        system_prompt: "You coordinate work.", brain_scopes: [], allowed_tools: [], permissions: [], paused: false,
        builtin_key: "coordinator", provider: "ollama", model: "llama3.2:3b" }) : respond({ detail: "denied" }, 403);
    }
    if (path.endsWith("/duplicate") && options.method === "POST") {
      return respond({ id: JSON.parse(options.body).new_id, name: JSON.parse(options.body).name });
    }
    throw new Error(`Unexpected request ${path} ${options.method}`);
  };
  const cryptoRef = { randomUUID: () => "00000000-1111-2222-3333-444444444444" };
  const ui = mountAgentsPage({ documentRef, fetchImpl, cryptoRef });
  return { elements, filters, views, calls, ui, items };
}

const settle = async () => new Promise(resolve => setImmediate(resolve));

test("Agents page filters by real runtime state and switches to existing organization tree", async () => {
  const ui = setup();
  await settle();
  assert.equal(ui.elements["agent-list"].children.length, 3);
  ui.filters.find(button => button.dataset.filter === "active").listeners.click();
  assert.equal(ui.elements["agent-list"].children.length, 1);
  assert.match(ui.elements["agent-list"].textContent, /Coordinator/);
  ui.filters.find(button => button.dataset.filter === "error").listeners.click();
  assert.equal(ui.elements["agent-list"].children.length, 1);
  assert.match(ui.elements["agent-list"].textContent, /unavailable/i);
  ui.filters.find(button => button.dataset.filter === "builtin").listeners.click();
  assert.equal(ui.elements["agent-list"].children.length, 2);
  assert.equal(ui.filters.find(button => button.dataset.filter === "builtin").getAttribute("aria-selected"), "true");
  let prevented = false;
  ui.filters.find(button => button.dataset.filter === "builtin").listeners.keydown({ key: "ArrowRight", preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(ui.filters.find(button => button.dataset.filter === "all").focused, true);
  ui.views.find(button => button.dataset.view === "tree").listeners.click();
  await settle();
  assert.equal(ui.elements["agent-list-view"].hidden, true);
  assert.equal(ui.elements["agent-tree-view"].hidden, false);
  assert.equal(ui.calls.some(call => call.path === "/api/structure-map"), true);
});

test("profile details remain safe for read-only sessions and link chat to the matching Employee", async () => {
  const ui = setup({ profileAllowed: false });
  await settle();
  const card = ui.elements["agent-list"].children[0];
  const actions = card.children[2];
  assert.equal(actions.children[1].href, "/ui/employee-chat?employee_id=employee-0");
  actions.children[0].listeners.click();
  await settle();
  assert.match(ui.elements["agent-detail-content"].textContent, /owner with Agent management permission/);
  assert.equal(ui.elements["agent-detail-content"].children.some(node => node.tagName === "FORM"), false);
});

test("owner profile editor is collapsed by default and uses existing pause/reset APIs", async () => {
  const ui = setup();
  await settle();
  const card = ui.elements["agent-list"].children[0];
  card.children[2].children[0].listeners.click();
  await settle();
  const advanced = ui.elements["agent-detail-content"].children.find(node => node.tagName === "DETAILS");
  assert.equal(advanced.open, undefined);
  assert.match(advanced.textContent, /Role profile and permissions/);
  const actions = ui.elements["agent-detail-content"].children.at(-1);
  actions.children[0].listeners.click();
  await settle();
  assert.equal(ui.calls.some(call => call.path === "/api/agents/local_worker/pause" && call.options.method === "PUT"), true);
  assert.equal(ui.calls.find(call => call.path.endsWith("/pause")).options.headers["X-Local-CSRF"], "csrf-token");
  actions.children[1].listeners.click();
  await settle();
  assert.equal(ui.calls.some(call => call.path === "/api/agents/local_worker/reset" && call.options.method === "POST"), true);
});

test("New Agent clones an existing profile through the owner API with CSRF", async () => {
  const ui = setup();
  await settle();
  ui.elements["agent-create-source"].value = "local_worker";
  ui.elements["agent-create-name"].value = "My Coordinator";
  await ui.elements["agent-create-form"].listeners.submit({ preventDefault() {} });
  const call = ui.calls.find(item => item.path.endsWith("/duplicate"));
  assert.equal(call.options.method, "POST");
  assert.deepEqual(JSON.parse(call.options.body), { new_id: "custom_00000000111122223333444444444444", name: "My Coordinator" });
  assert.equal(call.options.headers["X-Local-CSRF"], "csrf-token");
  assert.match(ui.elements["agent-create-state"].textContent, /Review its permissions/);
});

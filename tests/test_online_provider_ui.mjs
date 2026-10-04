import assert from "node:assert/strict";
import test from "node:test";
import { mountOnlineProvider } from "../app/webui/static/online-provider.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.children = []; this.value = ""; this.text = ""; this.listeners = {}; this.disabled = false; }
  get textContent() { return this.text + this.children.map(item => item.textContent).join(""); }
  set textContent(value) { this.text = value; this.children = []; }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(...items) { this.children.push(...items); if (this.tag === "select" && this.children.length === 1) this.value = items[0].value; }
  replaceChildren() { this.children = []; this.text = ""; if (this.tag === "select") this.value = ""; }
  addEventListener(event, handler) { this.listeners[event] = handler; }
}
const ids = ["gemini-key", "gemini-agent", "gemini-model", "gemini-state", "gemini-usage", "gemini-discover", "gemini-connect", "gemini-refresh", "gemini-disconnect", "gemini-clear"];
function setup(handler, confirmImpl = () => true) {
  const elements = Object.fromEntries(ids.map(id => [id, new Element(id.endsWith("agent") || id.endsWith("model") ? "select" : "")]));
  const calls = [];
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    const result = await handler(path, options);
    return { ok: result.status < 400, status: result.status, json: async () => result.body };
  };
  const documentRef = { getElementById: id => elements[id], createElement: tag => new Element(tag) };
  const controller = mountOnlineProvider({ documentRef, fetchImpl, confirmImpl });
  return { elements, calls, controller };
}

test("Gemini key is used only for the dedicated catalog request and is cleared immediately", async () => {
  const ui = setup(async (path, options) => {
    if (path === "/api/local/session") return { status: 200, body: { csrf: "csrf", permissions: ["online-provider:connect", "online-provider:disconnect"] } };
    if (path === "/api/agents") return { status: 200, body: { items: [{ id: "worker", name: "Worker", provider: "ollama", model: "local" }] } };
    if (path === "/api/local/online-provider") return { status: 200, body: { connected: false, models: [], selected: null } };
    if (path === "/api/tasks") return { status: 200, body: { items: [{ assigned_agent: "worker", status: "running" }] } };
    if (path === "/api/chat/conversations") return { status: 200, body: { items: [{ coordinator: { id: "worker" } }] } };
    if (path === "/api/employee-chat/conversations") return { status: 200, body: { items: [{ agent: { id: "worker" }, status: "open" }] } };
    if (path === "/api/local/online-provider/catalog") return { status: 200, body: { models: ["gemini-test-flash"] } };
    throw new Error(`Unexpected request ${path} ${options.method}`);
  });
  await ui.controller.initialLoad;
  const key = `AIza${"A".repeat(35)}`;
  ui.elements["gemini-key"].value = key;
  await ui.controller.discover();
  assert.equal(ui.elements["gemini-key"].value, "");
  const catalog = ui.calls.find(item => item.path.endsWith("/catalog"));
  assert.deepEqual(JSON.parse(catalog.options.body), { api_key: key });
  assert.equal(catalog.options.headers["X-Local-CSRF"], "csrf");
  assert.equal(ui.calls.some(item => item.path.includes("/chat/")), false);
  assert.match(ui.elements["gemini-state"].textContent, /Key verified/);
});

test("Gemini reassignment previews affected work and requires explicit confirmation", async () => {
  let preview = "";
  const ui = setup(async (path, options) => {
    if (path === "/api/local/session") return { status: 200, body: { csrf: "csrf", permissions: ["online-provider:connect", "online-provider:disconnect"] } };
    if (path === "/api/agents") return { status: 200, body: { items: [{ id: "worker", name: "Worker", provider: "ollama", model: "local" }] } };
    if (path === "/api/local/online-provider") return { status: 200, body: { connected: false, models: [], selected: null } };
    if (path === "/api/local/online-provider/catalog") return { status: 200, body: { models: ["gemini-test-flash"] } };
    if (path === "/api/tasks") return { status: 200, body: { items: [{ assigned_agent: "worker", status: "running" }] } };
    if (path === "/api/chat/conversations") return { status: 200, body: { items: [{ coordinator: { id: "worker" } }] } };
    if (path === "/api/employee-chat/conversations") return { status: 200, body: { items: [{ agent: { id: "worker" }, status: "open" }] } };
    throw new Error(`Unexpected request ${path} ${options.method}`);
  }, (text) => { preview = text; return false; });
  await ui.controller.initialLoad;
  ui.elements["gemini-key"].value = `AIza${"A".repeat(35)}`;
  await ui.controller.discover();
  await ui.controller.connect();
  assert.match(preview, /gemini-test-flash to Worker \(worker\) instead of ollama\/local\?/);
  assert.match(preview, /configured coordinator chat context only after separate per-turn consent/);
  assert.match(preview, /Individual Employee chat sends only its message and recent history/);
  assert.match(preview, /1 running/);
  assert.match(preview, /Individual Employee conversations: 1 \(1 open\)/);
  assert.equal(ui.calls.some(item => item.path.endsWith("/connection") && item.options.method === "PUT"), false);
  assert.match(ui.elements["gemini-state"].textContent, /preview was cancelled/);
});

test("confirmed Gemini assignment carries the observed Agent identity and connection", async () => {
  let connected = false;
  const ui = setup(async (path, options) => {
    if (path === "/api/local/session") return { status: 200, body: { csrf: "csrf", permissions: ["online-provider:connect", "online-provider:disconnect"] } };
    if (path === "/api/agents") return { status: 200, body: { items: [{ id: "worker", name: "Worker", provider: "ollama", model: "local" }] } };
    if (path === "/api/local/online-provider") return {
      status: 200,
      body: connected
        ? { connected: true, selected: { agent_id: "worker", agent_name: "Worker", model_id: "gemini-test-flash" }, generation_calls_used: 0, generation_calls_limit: 5, expires_in_seconds: 300 }
        : { connected: false, models: [], selected: null },
    };
    if (path === "/api/local/online-provider/catalog") return { status: 200, body: { models: ["gemini-test-flash"] } };
    if (path === "/api/tasks" || path === "/api/chat/conversations" || path === "/api/employee-chat/conversations") {
      return { status: 200, body: { items: [] } };
    }
    if (path === "/api/local/online-provider/connection" && options.method === "PUT") {
      connected = true;
      return { status: 200, body: { agent_id: "worker", provider_id: "gemini", model_id: "gemini-test-flash" } };
    }
    throw new Error(`Unexpected request ${path} ${options.method}`);
  });
  await ui.controller.initialLoad;
  ui.elements["gemini-key"].value = `AIza${"A".repeat(35)}`;
  await ui.controller.discover();
  await ui.controller.connect();
  const assignment = ui.calls.find((item) => item.path.endsWith("/connection") && item.options.method === "PUT");
  assert.deepEqual(JSON.parse(assignment.options.body), {
    agent_id: "worker",
    model_id: "gemini-test-flash",
    expected_provider_id: "ollama",
    expected_model_id: "local",
  });
  assert.equal(assignment.options.headers["X-Local-CSRF"], "csrf");
  assert.match(ui.elements["gemini-state"].textContent, /Each cloud chat turn requires its own consent/);
});

test("staged credential erase uses same-origin CSRF protected local endpoint", async () => {
  let staged = false;
  const ui = setup(async (path, options) => {
    if (path === "/api/local/session") return { status: 200, body: { csrf: "csrf", permissions: ["online-provider:connect", "online-provider:disconnect"] } };
    if (path === "/api/agents") return { status: 200, body: { items: [] } };
    if (path === "/api/local/online-provider") return { status: 200, body: { connected: false, models: [], selected: null } };
    if (path === "/api/local/online-provider/catalog") { staged = true; return { status: 200, body: { models: ["gemini-test-flash"] } }; }
    if (path === "/api/local/online-provider/credential" && options.method === "DELETE") { staged = false; return { status: 200, body: { credential_erased: true } }; }
    throw new Error(`Unexpected request ${path} ${options.method}`);
  });
  await ui.controller.initialLoad;
  ui.elements["gemini-key"].value = `AIza${"A".repeat(35)}`;
  await ui.controller.discover();
  await ui.controller.eraseStaged();
  const deletion = ui.calls.find(item => item.path.endsWith("/credential"));
  assert.equal(deletion.options.method, "DELETE");
  assert.equal(deletion.options.headers["X-Local-CSRF"], "csrf");
  assert.deepEqual(JSON.parse(deletion.options.body), {});
  assert.equal(staged, false);
});

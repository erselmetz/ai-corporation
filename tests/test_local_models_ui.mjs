import assert from "node:assert/strict";
import test from "node:test";
import { mountLocalModels } from "../app/webui/static/local-models.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.children = []; this.value = ""; this.text = ""; this.listeners = {}; }
  set textContent(value) { this.text = value; this.children = []; }
  get textContent() { return this.text + this.children.map(node => node.textContent).join(""); }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(node) { this.children.push(node); if (this.tag === "select" && this.children.length === 1) this.value = node.value; }
  replaceChildren() { this.children = []; this.text = ""; this.value = ""; }
  addEventListener(event, fn) { this.listeners[event] = fn; }
}
function setup({
  permissions = ["local-model:select"],
  handler = () => null,
  confirmImpl = () => true,
} = {}) {
  const elements = Object.fromEntries(["model-agent", "model-installed", "model-state", "model-evidence", "model-refresh", "model-select"].map(id => [id, new Element(["model-agent", "model-installed"].includes(id) ? "select" : "")]));
  const calls = [];
  const inventory = { provider_id: "local", configured_model: "old", configured_installed: false,
    inventory: { models: ["<script>inert</script>"], state: "available", checked_at: "2026-10-04T00:00:00Z", source: "fake" } };
  const fetchImpl = async (path, options) => {
    calls.push({ path, options });
    const custom = await handler(path, options); if (custom) return custom;
    const body = path === "/api/local/session" ? { csrf: "csrf-token", permissions }
      : path === "/api/agents" ? { items: [{ id: "worker", name: "Worker", provider: "local", model: "old" }] }
      : path === "/api/tasks" ? { items: [{ assigned_agent: "worker", status: "running" }] }
      : path === "/api/chat/conversations" ? { items: [{ coordinator: { id: "worker" } }] }
      : path === "/api/employee-chat/conversations" ? { items: [{ agent: { id: "worker" }, status: "open" }] }
      : inventory;
    return { ok: true, status: 200, json: async () => body };
  };
  const loaded = mountLocalModels({
    documentRef: { getElementById: id => elements[id], createElement: tag => new Element(tag) },
    fetchImpl,
    confirmImpl,
  });
  return { elements, calls, loaded };
}

test("refresh is explicit and selection uses CSRF, same-origin and inert installed identifiers", async () => {
  const ui = setup(); await ui.loaded;
  assert.equal(ui.calls.length, 2); // Login state + agents, no provider call until Refresh.
  await ui.elements["model-refresh"].listeners.click();
  assert.equal(ui.elements["model-installed"].children[0].textContent, "<script>inert</script>");
  assert.match(ui.elements["model-evidence"].textContent, /Installed: no.*Service: available.*Execution readiness: unknown/);
  assert.equal(ui.elements["model-select"].disabled, false);
  await ui.elements["model-select"].listeners.click();
  const put = ui.calls.find(call => call.options.method === "PUT");
  assert.equal(put.options.credentials, "same-origin");
  assert.equal(put.options.headers["X-Local-CSRF"], "csrf-token");
  assert.deepEqual(JSON.parse(put.options.body), {
    provider_id: "local",
    model_id: "<script>inert</script>",
    expected_model_id: "old",
  });
  assert.match(ui.elements["model-state"].textContent, /new conversation/);
  assert.equal(ui.elements["model-select"].disabled, true);
});

test("model reassignment previews identity, privacy and affected work before confirmation", async () => {
  let preview = "";
  const ui = setup({ confirmImpl: (text) => { preview = text; return false; } });
  await ui.loaded;
  await ui.elements["model-refresh"].listeners.click();
  await ui.elements["model-select"].listeners.click();
  assert.match(preview, /Worker \(worker\).*old.*<script>inert<\/script>/s);
  assert.match(preview, /configured coordinator chat context may go to this local provider/);
  assert.match(preview, /1 running/);
  assert.match(preview, /Coordinator conversations: 1/);
  assert.match(preview, /Individual Employee conversations: 1 \(1 open\)/);
  assert.equal(ui.calls.some(call => call.options.method === "PUT"), false);
  assert.match(ui.elements["model-state"].textContent, /preview was cancelled/);
});

test("incomplete affected-work reads fail closed before local reassignment", async () => {
  const ui = setup({ handler: (path) => path === "/api/employee-chat/conversations"
    ? { ok: false, status: 503, json: async () => ({}) }
    : null });
  await ui.loaded;
  await ui.elements["model-refresh"].listeners.click();
  await ui.elements["model-select"].listeners.click();
  assert.equal(ui.calls.some((call) => call.options.method === "PUT"), false);
  assert.match(ui.elements["model-state"].textContent, /no assignment was changed/);
});

test("read-only session cannot select and changing coordinator clears stale evidence", async () => {
  const ui = setup({ permissions: [] }); await ui.loaded;
  await ui.elements["model-refresh"].listeners.click();
  assert.equal(ui.elements["model-select"].disabled, true);
  ui.elements["model-agent"].listeners.change();
  assert.equal(ui.elements["model-installed"].children.length, 0);
  assert.equal(ui.elements["model-evidence"].textContent, "");
});

test("busy refresh suppresses duplicate calls and conflicts remove stale selection", async () => {
  let release;
  const ui = setup({ handler: async (path, options) => {
    if (path.includes("/models/") && !options.method) await new Promise(resolve => { release = resolve; });
    if (options.method === "PUT") return { ok: false, status: 409 };
  } });
  await ui.loaded;
  const refresh = ui.elements["model-refresh"].listeners.click();
  await Promise.resolve();
  assert.equal(ui.elements["model-refresh"].disabled, true);
  await ui.elements["model-refresh"].listeners.click();
  release(); await refresh;
  assert.equal(ui.calls.filter(call => call.path.includes("/models/")).length, 1);
  await ui.elements["model-select"].listeners.click();
  assert.match(ui.elements["model-state"].textContent, /active work or its assignment\/inventory changed/);
  assert.equal(ui.elements["model-installed"].children.length, 0);
});

test("unavailable and unknown observations show guidance without enabling selection", async () => {
  const ui = setup({ handler: path => path.includes("/models/") ? { ok: true, status: 200, json: async () => ({
    configured_model: "old", configured_installed: null,
    inventory: { state: "unknown", models: [], source: "unsupported", checked_at: "now", reason: "Unsupported inventory." },
  }) } : null });
  await ui.loaded; await ui.elements["model-refresh"].listeners.click();
  assert.match(ui.elements["model-state"].textContent, /Unsupported inventory/);
  assert.match(ui.elements["model-evidence"].textContent, /Installed: unknown/);
  assert.equal(ui.elements["model-select"].disabled, true);
});

test("missing local login reports sign-in guidance", async () => {
  const ui = setup({ handler: () => ({ ok: false, status: 401 }) }); await ui.loaded;
  assert.match(ui.elements["model-state"].textContent, /Sign in/);
  assert.equal(ui.elements["model-select"].disabled, true);
});

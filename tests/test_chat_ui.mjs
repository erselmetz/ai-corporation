import assert from "node:assert/strict";
import test from "node:test";
import { mountChat } from "../app/webui/static/chat.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.children = []; this.value = ""; this.text = ""; this.listeners = {}; this.disabled = false; }
  get textContent() { return this.text + this.children.map(item => item.textContent).join(""); }
  set textContent(value) { this.text = value; this.children = []; }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(...items) { this.children.push(...items); if (this.tag === "select" && this.children.length === 1) this.value = items[0].value; }
  replaceChildren() { this.children = []; this.text = ""; if (this.tag === "select") this.value = ""; }
  addEventListener(event, handler) { this.listeners[event] = handler; }
}
const agent = { id: "worker", name: "Actual Worker", role: "Worker", provider: "fake", model: "configured-model" };
const snapshot = (messages = [], status = "open", coordinator = agent) => ({ coordinator, conversation: { id: "conversation", status, messages } });
const message = (role, status, content) => ({ id: role, role, status, content });
const response = (payload, status = 200) => ({ ok: status === 200, status, json: async () => payload });
function setup(handler = null) {
  const ids = ["chat-state", "chat-history", "chat-agent", "chat-conversation", "chat-input", "chat-start", "chat-send", "chat-close", "chat-refresh", "chat-identity", "chat-form", "cloud-consent-panel", "cloud-consent"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(id === "chat-agent" || id === "chat-conversation" ? "select" : "")]));
  const calls = [];
  const fetchImpl = async (path, options) => {
    calls.push({ path, options });
    const custom = handler && await handler(path, options);
    if (custom) return custom;
    if (path === "/api/agents") return response({ items: [agent] });
    if (path === "/api/local/session") return response({ csrf: "test-csrf" });
    if (path === "/api/chat/conversations" && !options.method) return response({ items: [] });
    if (path.endsWith("/close")) return response(snapshot([], "closed"));
    return response(snapshot());
  };
  const documentRef = { getElementById: id => elements[id], createElement: tag => new Element(tag) };
  const controller = mountChat({ documentRef, fetchImpl });
  return { controller, elements, calls };
}

test("start and send use same-origin, session CSRF and actual coordinator identity; text stays inert", async () => {
  const untrusted = "<script>alert('x')</script>";
  const ui = setup((path) => path.endsWith("/messages") ? response(snapshot([
    message("user", "completed", "Hello"), message("assistant", "completed", untrusted)])) : null);
  assert.equal(await ui.controller.initialLoad, true);
  assert.equal(await ui.controller.start(), true);
  assert.match(ui.elements["chat-identity"].textContent, /Actual Worker.*fake.*configured-model/);
  ui.elements["chat-input"].value = "Hello";
  assert.equal(await ui.controller.send({ preventDefault() {} }), true);
  assert.ok(ui.elements["chat-history"].textContent.includes(untrusted));
  assert.equal(ui.elements["chat-input"].value, "");
  const post = ui.calls.find(call => call.path.endsWith("/messages"));
  assert.equal(post.options.credentials, "same-origin");
  assert.equal(post.options.headers["X-Local-CSRF"], "test-csrf");
  assert.deepEqual(JSON.parse(post.options.body), { text: "Hello" });
});

test("Gemini requires per-turn cloud consent and sends only an explicit consent flag", async () => {
  const gemini = { ...agent, provider: "gemini", model: "gemini-test-flash" };
  const ui = setup((path, options) => {
    if (path === "/api/agents") return response({ items: [gemini] });
    if (path === "/api/chat/conversations" && options.method === "POST") return response(snapshot([], "open", gemini));
    if (path.endsWith("/messages")) return response(snapshot([message("assistant", "completed", "reply")], "open", gemini));
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  assert.equal(ui.elements["cloud-consent-panel"].hidden, false);
  ui.elements["chat-input"].value = "hello";
  assert.equal(await ui.controller.send(), false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 0);
  ui.elements["cloud-consent"].checked = true;
  assert.equal(await ui.controller.send(), true);
  const post = ui.calls.find(call => call.path.endsWith("/messages"));
  assert.deepEqual(JSON.parse(post.options.body), { text: "hello", cloud_consent: true });
  assert.equal(ui.elements["cloud-consent"].checked, false);
  assert.equal(ui.elements["cloud-consent-panel"].hidden, false);
});

test("pending send prevents duplicate turns and selection changes; provider failure is inspected without replay", async () => {
  let finish;
  const ui = setup((path) => {
    if (path.endsWith("/messages")) return new Promise(resolve => { finish = resolve; });
    if (path.endsWith("/conversation")) return response(snapshot([message("user", "failed", "Hello")]));
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Hello";
  const pending = ui.controller.send();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(ui.elements["chat-state"].textContent, /Pending/);
  assert.equal(ui.elements["chat-input"].disabled, true);
  assert.equal(ui.elements["chat-conversation"].disabled, true);
  assert.equal(await ui.controller.send(), false);
  assert.equal(await ui.controller.refresh(), false);
  finish(response({ detail: "raw failure" }, 502));
  assert.equal(await pending, false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 1);
  assert.match(ui.elements["chat-history"].textContent, /user - failed/);
  assert.match(ui.elements["chat-state"].textContent, /No automatic retry/);
  assert.equal(ui.elements["chat-input"].value, "Hello");
  assert.equal(ui.elements["chat-input"].disabled, false);
});

test("blank and UTF-8 oversized messages never submit", async () => {
  const ui = setup();
  await ui.controller.initialLoad;
  await ui.controller.start();
  for (const value of [" ", "界".repeat(3000)]) {
    ui.elements["chat-input"].value = value;
    assert.equal(await ui.controller.send(), false);
  }
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 0);
});

test("authorization and empty data are distinct and failed refresh removes stale data", async () => {
  let denied = false;
  const ui = setup(path => path === "/api/agents" && denied ? response({}, 401) : null);
  await ui.controller.initialLoad;
  await ui.controller.start();
  denied = true;
  assert.equal(await ui.controller.refresh(), false);
  assert.match(ui.elements["chat-state"].textContent, /Sign in/);
  assert.equal(ui.elements["chat-history"].textContent, "");
  assert.equal(ui.elements["chat-agent"].children.length, 0);
  const empty = setup(path => path === "/api/agents" ? response({ items: [] }) : null);
  assert.equal(await empty.controller.initialLoad, true);
  assert.match(empty.elements["chat-state"].textContent, /No registered coordinator/);
});

test("existing owner conversation can be selected after refresh and closed explicitly", async () => {
  const ui = setup((path, options) => path === "/api/chat/conversations" && !options.method
    ? response({ items: [{ id: "conversation", coordinator: agent }] }) : null);
  await ui.controller.initialLoad;
  ui.elements["chat-conversation"].value = "conversation";
  assert.equal(await ui.controller.load(), true);
  assert.equal(await ui.controller.close(), true);
  assert.match(ui.elements["chat-state"].textContent, /closed/);
  assert.equal(ui.elements["chat-input"].disabled, true);
});


test("a failed send that discovers closure keeps input disabled and never replays", async () => {
  const ui = setup(path => {
    if (path.endsWith("/messages")) return response({}, 502);
    if (path.endsWith("/conversation")) return response(snapshot([], "closed"));
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Hello";
  assert.equal(await ui.controller.send(), false);
  assert.equal(ui.elements["chat-input"].disabled, true);
  assert.equal(await ui.controller.send(), false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 1);
});

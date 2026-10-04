import assert from "node:assert/strict";
import test from "node:test";
import { mountProviderConnections } from "../app/webui/static/provider-connections.mjs";

class Element {
  constructor(tag = "") {
    this.tag = tag;
    this.children = [];
    this.value = "";
    this.text = "";
    this.listeners = {};
    this.disabled = false;
    this.hidden = false;
  }
  set textContent(value) {
    this.text = value;
    this.children = [];
  }
  get textContent() {
    return this.text + this.children.map(child => child.textContent).join("");
  }
  set innerHTML(_) {
    throw new Error("HTML injection is forbidden");
  }
  append(node) {
    this.children.push(node);
    if (this.tag === "select" && this.children.length === 1) {
      this.value = node.value;
    }
  }
  replaceChildren() {
    this.children = [];
    this.text = "";
    this.value = "";
  }
  addEventListener(event, handler) {
    this.listeners[event] = handler;
  }
}

function setup({ permissions = ["provider-connection:read", "provider-connection:manage"] } = {}) {
  const ids = [
    "connection-type", "assignment-provider", "assignment-model", "assignment-agent",
    "connection-state", "connection-key", "connection-url", "connection-slots",
    "connection-url-field", "connection-key-field", "connection-add", "connection-refresh",
    "connection-remove", "connection-list", "connection-id", "connection-name",
    "assignment-save",
  ];
  const elements = Object.fromEntries(ids.map(id => [
    id,
    new Element(["connection-type", "assignment-provider", "assignment-model", "assignment-agent"].includes(id)
      ? "select" : ""),
  ]));
  elements["connection-type"].value = "ollama";
  elements["connection-slots"].value = "2";
  const calls = [];
  let connections = [];
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    if (path === "/api/local/session") {
      return response({ csrf: "local-csrf", permissions });
    }
    if (path === "/api/agents") {
      return response({ items: [{ id: "agent-1", name: "Agent One", provider: "ollama", model: "old-model" }] });
    }
    if (path === "/api/local/provider-connections") {
      return response({ items: connections, capacity: { global_request_slots: 1, hardware_feasibility: "unknown" } });
    }
    if (["/api/tasks", "/api/chat/conversations", "/api/employee-chat/conversations"].includes(path)) {
      return response({ items: [] });
    }
    if (path === "/api/local/provider-connections/gemini" && options.method === "POST") {
      const body = JSON.parse(options.body);
      assert.equal(body.api_key, "test-secret");
      connections = [{
        provider_id: "gemini-work",
        name: body.name,
        provider_type: "gemini",
        state: "available",
        models: ["gemini-test-model"],
        source: "fake-catalog",
        checked_at: "2026-10-04T00:00:00+00:00",
        request_capacity: { state: "configured", provider_slots: 1 },
      }];
      return response(connections[0], 201);
    }
    if (path === "/api/local/provider-connections/assignment" && options.method === "PUT") {
      return response(JSON.parse(options.body));
    }
    throw new Error(`Unexpected request ${options.method ?? "GET"} ${path}`);
  };
  const ui = mountProviderConnections({
    documentRef: {
      getElementById: id => elements[id],
      createElement: tag => new Element(tag),
    },
    fetchImpl,
    confirmImpl: text => {
      calls.push({ confirmation: text });
      return true;
    },
  });
  return { elements, calls, ui };
}

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

test("Gemini setup clears the key, displays truthful capacity, and confirms assignment", async () => {
  const ui = setup();
  const { elements, calls } = ui;
  await ui.ui.initialLoad;
  assert.match(elements["connection-state"].textContent, /No additional provider connections are configured/);
  elements["connection-type"].value = "gemini";
  elements["connection-type"].listeners.change();
  assert.equal(elements["connection-key-field"].hidden, false);
  assert.equal(elements["connection-url-field"].hidden, true);
  assert.equal(elements["connection-slots"].value, "1");
  elements["connection-id"].value = "work";
  elements["connection-name"].value = "Work account";
  elements["connection-key"].value = "test-secret";
  await elements["connection-add"].listeners.click();
  assert.equal(elements["connection-key"].value, "");
  assert.match(elements["connection-list"].textContent, /hardware feasibility UNKNOWN/);
  assert.match(elements["connection-state"].textContent, /Hardware feasibility remains UNKNOWN/);
  assert.equal(elements["connection-list"].textContent.includes("test-secret"), false);

  await elements["assignment-save"].listeners.click();
  const preview = calls.find(item => item.confirmation)?.confirmation;
  assert.match(preview, /gemini-work\/gemini-test-model/);
  assert.match(preview, /separate per-turn consent/);
  assert.match(preview, /Hardware feasibility: UNKNOWN/);
  const assignment = calls.find(item => item.path === "/api/local/provider-connections/assignment");
  assert.equal(assignment.options.headers["X-Local-CSRF"], "local-csrf");
  assert.equal(assignment.options.credentials, "same-origin");
  assert.deepEqual(JSON.parse(assignment.options.body), {
    agent_id: "agent-1",
    provider_id: "gemini-work",
    model_id: "gemini-test-model",
    expected_provider_id: "ollama",
    expected_model_id: "old-model",
  });
  assert.match(elements["connection-state"].textContent, /Existing conversations keep their snapshots/);
});

test("read-only owner session cannot add or assign provider connections", async () => {
  const ui = setup({ permissions: ["provider-connection:read"] });
  await ui.ui.initialLoad;
  assert.equal(ui.elements["connection-add"].disabled, true);
  assert.equal(ui.elements["assignment-save"].disabled, true);
});

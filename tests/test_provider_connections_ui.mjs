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

function setup({
  permissions = ["provider-connection:read", "provider-connection:manage", "model-runtime:manage"],
  initialConnections = [],
} = {}) {
  const ids = [
    "connection-type", "assignment-provider", "assignment-model", "assignment-agent",
    "connection-state", "connection-key", "connection-url", "connection-slots",
    "connection-url-field", "connection-key-field", "connection-add", "connection-refresh",
    "connection-remove", "connection-list", "connection-id", "connection-name",
    "assignment-save",
    "model-runtime-state", "model-runtime-evidence", "model-runtime-refresh",
    "model-load", "model-unload", "model-keep-alive",
  ];
  const elements = Object.fromEntries(ids.map(id => [
    id,
    new Element(["connection-type", "assignment-provider", "assignment-model", "assignment-agent"].includes(id)
      ? "select" : ""),
  ]));
  elements["connection-type"].value = "ollama";
  elements["connection-slots"].value = "2";
  elements["model-keep-alive"].value = "90";
  const calls = [];
  let connections = initialConnections;
  let loadedModels = [];
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
    if (path.endsWith("/runtime")) {
      return response({
        provider_id: "ollama-work",
        hardware_feasibility: "unknown",
        inference_latency: "unknown",
        request_capacity: { state: "configured", global_slots: 2, provider_slots: 2, active_requests: 0 },
        runtime: {
          state: "available", supported: true, models: loadedModels,
          probe_latency_ms: 1.25, reason: null,
        },
      });
    }
    if (path.endsWith("/models/load") && options.method === "POST") {
      loadedModels = [{ name: "local-model", size_bytes: 1234, vram_bytes: 1024, context_length: 2048 }];
      return response({
        action: "load", operation_latency_ms: 4.5,
        hardware_feasibility: "unknown", inference_latency: "unknown",
        request_capacity: { state: "configured", global_slots: 2, provider_slots: 2, active_requests: 0 },
        runtime: { state: "available", supported: true, models: loadedModels, probe_latency_ms: 1.2, reason: null },
      });
    }
    if (path.endsWith("/models/unload") && options.method === "POST") {
      loadedModels = [];
      return response({
        action: "unload", operation_latency_ms: 3.5,
        hardware_feasibility: "unknown", inference_latency: "unknown",
        request_capacity: { state: "configured", global_slots: 2, provider_slots: 2, active_requests: 0 },
        runtime: { state: "available", supported: true, models: [], probe_latency_ms: 1.2, reason: null },
      });
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

test("local runtime controls show provider evidence and confirm bounded load and unload", async () => {
  const ui = setup({
    initialConnections: [
      {
        provider_id: "ollama-work", name: "Workstation", provider_type: "ollama",
        state: "available", models: ["local-model"], source: "fake",
        request_capacity: { state: "configured", provider_slots: 2 },
      },
      {
        provider_id: "ollama-alt", name: "Alternate", provider_type: "ollama",
        state: "available", models: ["local-model"], source: "fake",
        request_capacity: { state: "configured", provider_slots: 2 },
      },
    ],
  });
  await ui.ui.initialLoad;
  await ui.elements["model-runtime-refresh"].listeners.click();
  assert.match(ui.elements["model-runtime-evidence"].textContent, /Loaded models \(available\): none reported/);
  assert.match(ui.elements["model-runtime-evidence"].textContent, /not inference latency/);
  assert.match(ui.elements["model-runtime-evidence"].textContent, /Hardware feasibility: unknown/);
  ui.elements["assignment-provider"].value = "ollama-alt";
  ui.elements["assignment-provider"].listeners.change();
  assert.equal(ui.elements["model-runtime-evidence"].textContent, "");
  assert.equal(ui.elements["model-runtime-state"].textContent, "");
  await ui.elements["model-load"].listeners.click();
  const load = ui.calls.find(call => call.path?.endsWith("/models/load"));
  assert.equal(load.options.credentials, "same-origin");
  assert.equal(load.options.headers["X-Local-CSRF"], "local-csrf");
  assert.deepEqual(JSON.parse(load.options.body), {
    model_id: "local-model", keep_alive_seconds: 90,
  });
  assert.match(ui.elements["model-runtime-evidence"].textContent, /memory 1234 bytes.*VRAM 1024 bytes/);
  assert.match(ui.calls.find(call => call.confirmation)?.confirmation, /Hardware fit is UNKNOWN/);
  assert.match(ui.elements["model-runtime-state"].textContent, /Hardware feasibility remains UNKNOWN/);
  await ui.elements["model-unload"].listeners.click();
  assert.ok(ui.calls.some(call => call.path?.endsWith("/models/unload")));
});

test("model lifecycle controls require their distinct permission", async () => {
  const ui = setup({
    permissions: ["provider-connection:read", "provider-connection:manage"],
    initialConnections: [{
      provider_id: "ollama-work", name: "Workstation", provider_type: "ollama",
      state: "available", models: ["local-model"], source: "fake",
      request_capacity: { state: "configured", provider_slots: 2 },
    }],
  });
  await ui.ui.initialLoad;
  assert.equal(ui.elements["model-load"].disabled, true);
  assert.equal(ui.elements["model-unload"].disabled, true);
});

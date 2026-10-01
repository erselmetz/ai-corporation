import assert from "node:assert/strict";
import test from "node:test";

import { mountProviderModelPage } from "../app/webui/static/providers.mjs";

function response(status, payload) {
  return {
    status,
    ok: status >= 200 && status < 300,
    payload,
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

  querySelector(selector) {
    if (!selector.startsWith(".")) return null;
    return findElement(this, (item) => item.className === selector.slice(1));
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
    "provider-list",
    "provider-list-state",
    "provider-detail",
    "provider-detail-state",
    "provider-refresh",
    "provider-create-form",
    "provider-id",
    "provider-name",
    "provider-create-submit",
    "provider-create-state",
    "model-list",
    "model-list-state",
    "model-detail",
    "model-detail-state",
    "model-refresh",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element("div")]));
  elements["provider-create-form"].formFields = [
    elements["provider-id"],
    elements["provider-name"],
  ];
  const documentRef = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements[id],
  };
  return { documentRef, elements };
}

const provider = { id: "local", type: "LocalProvider" };
const assignment = {
  agent_id: "agent-1",
  provider_id: "local",
  model_id: "local-model",
};

test("loads provider and model lists using the existing APIs and displays detail fields", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      if (path === "/api/providers") return response(200, { items: [provider] });
      if (path === "/api/models") return response(200, { items: [assignment] });
      if (path === "/api/providers/local") return response(200, provider);
      return response(200, assignment);
    },
    confirmImpl: () => false,
  });

  await controller.initialLoad;
  assert.deepEqual(calls.map(([path]) => path), ["/api/providers", "/api/models"]);
  assert.equal(elements["provider-list"].children.length, 1);
  assert.equal(elements["model-list"].children.length, 1);

  await controller.loadProviderDetail("local");
  await controller.loadModelDetail("agent-1");
  assert.match(elements["provider-detail"].textContent, /local/);
  assert.match(elements["provider-detail"].textContent, /LocalProvider/);
  assert.match(elements["model-detail"].textContent, /agent-1/);
  assert.match(elements["model-detail"].textContent, /local-model/);
  assert.equal(elements["provider-detail"].hidden, false);
  assert.equal(elements["model-detail"].hidden, false);
  assert.ok(calls.every(([, options]) => options.credentials === "same-origin"));
});

test("creates Provider with only id and name and refreshes list/detail", async () => {
  const { documentRef, elements } = pageElements();
  elements["provider-id"].value = "remote";
  elements["provider-name"].value = "Remote Provider";
  const calls = [];
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (options.method === "POST") return response(201, { id: "remote", type: "RemoteProvider" });
      if (path === "/api/providers") {
        return response(200, { items: calls.some(([url, opts]) => url === "/api/providers" && opts.method === "POST")
          ? [provider, { id: "remote", type: "RemoteProvider" }]
          : [provider] });
      }
      if (path === "/api/providers/remote") return response(200, { id: "remote", type: "RemoteProvider" });
      return response(200, { items: [assignment] });
    },
    confirmImpl: () => false,
  });

  await controller.initialLoad;
  await controller.createProvider({ preventDefault() {} });
  const create = calls.find(([, options]) => options.method === "POST");
  assert.equal(create[0], "/api/providers");
  assert.deepEqual(JSON.parse(create[1].body), { id: "remote", name: "Remote Provider" });
  assert.deepEqual(create[1].headers, {
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  assert.equal(elements["provider-list"].children.length, 2);
  assert.match(elements["provider-create-state"].textContent, /created/i);
  assert.match(elements["provider-detail"].textContent, /RemoteProvider/);
  assert.equal(elements["provider-create-submit"].disabled, false);
});

test("prevents duplicate Provider creation while the first request is pending", async () => {
  const { documentRef, elements } = pageElements();
  elements["provider-id"].value = "new";
  elements["provider-name"].value = "New Provider";
  let release;
  let posts = 0;
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (_path, options = {}) => {
      if (options.method === "POST") {
        posts += 1;
        return new Promise((resolve) => {
          release = () => resolve(response(201, { id: "new", type: "NewProvider" }));
        });
      }
      if (_path === "/api/providers") return response(200, { items: [{ id: "new", type: "NewProvider" }] });
      return response(200, { items: [] });
    },
    confirmImpl: () => false,
  });
  await controller.initialLoad;
  const first = controller.createProvider({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(elements["provider-create-submit"].disabled, true);
  await controller.createProvider({ preventDefault() {} });
  assert.equal(posts, 1);
  release();
  await first;
});

test("requires confirmation before Provider DELETE and refreshes after success", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  let confirmed = false;
  let prompt = "";
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (options.method === "DELETE") return response(204);
      if (path === "/api/providers") return response(200, { items: [] });
      if (path === "/api/models") return response(200, { items: [] });
      return response(200, provider);
    },
    confirmImpl: (message) => {
      prompt = message;
      return confirmed;
    },
  });
  await controller.initialLoad;
  await controller.loadProviders();
  await controller.loadProviderDetail("local");
  const removeButton = elements["provider-detail"].querySelector(".danger-button");
  await removeButton.dispatch("click");
  assert.equal(calls.some(([, options]) => options.method === "DELETE"), false);
  assert.match(prompt, /local/);

  confirmed = true;
  await removeButton.dispatch("click");
  assert.ok(calls.some(([path, options]) => path === "/api/providers/local" && options.method === "DELETE"));
  assert.equal(elements["provider-list"].children.length, 0);
  assert.match(elements["provider-list-state"].textContent, /No providers/);
  assert.equal(elements["provider-detail"].hidden, true);
});

test("loads model detail and replaces with exactly provider_id/model_id then refreshes", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  let current = assignment;
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (path === "/api/providers") return response(200, { items: [provider] });
      if (path === "/api/models") return response(200, { items: [current] });
      if (options.method === "PUT") {
        current = { agent_id: "agent-1", provider_id: "local", model_id: "updated-model" };
        return response(200, current);
      }
      if (path === "/api/models/agent-1") return response(200, current);
      return response(200, provider);
    },
    confirmImpl: () => false,
  });
  await controller.initialLoad;
  await controller.loadModelDetail("agent-1");
  const form = elements["model-detail"].querySelector(".model-replace-form");
  const inputs = findElement(form, (item) => item.name === "provider_id");
  const modelInput = findElement(form, (item) => item.name === "model_id");
  const submit = findElement(form, (item) => item.tagName === "button");
  inputs.value = "local";
  modelInput.value = "updated-model";
  await controller.replaceModelAssignment(
    "agent-1",
    inputs,
    modelInput,
    submit,
    findElement(form, (item) => item.className === "section-state"),
    { preventDefault() {} },
  );

  const put = calls.find(([, options]) => options.method === "PUT");
  assert.equal(put[0], "/api/models/agent-1");
  assert.deepEqual(JSON.parse(put[1].body), {
    provider_id: "local",
    model_id: "updated-model",
  });
  assert.equal("agent_id" in JSON.parse(put[1].body), false);
  assert.match(elements["model-list"].textContent, /updated-model/);
  assert.match(elements["model-detail"].textContent, /updated-model/);
});

test("prevents duplicate model replacements while the first request is pending", async () => {
  const { documentRef, elements } = pageElements();
  let release;
  let replacements = 0;
  let current = assignment;
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (path === "/api/providers") return response(200, { items: [provider] });
      if (path === "/api/models") return response(200, { items: [current] });
      if (options.method === "PUT") {
        replacements += 1;
        return new Promise((resolve) => {
          release = () => {
            current = { ...assignment, model_id: "next-model" };
            resolve(response(200, current));
          };
        });
      }
      if (path === "/api/models/agent-1") return response(200, current);
      return response(200, provider);
    },
    confirmImpl: () => false,
  });
  await controller.initialLoad;
  await controller.loadModelDetail("agent-1");
  const form = elements["model-detail"].querySelector(".model-replace-form");
  const providerInput = findElement(form, (item) => item.name === "provider_id");
  const modelInput = findElement(form, (item) => item.name === "model_id");
  const submit = findElement(form, (item) => item.tagName === "button");
  const state = findElement(form, (item) => item.className === "section-state");
  modelInput.value = "next-model";
  const first = controller.replaceModelAssignment(
    "agent-1",
    providerInput,
    modelInput,
    submit,
    state,
    { preventDefault() {} },
  );
  await Promise.resolve();
  assert.equal(submit.disabled, true);
  await controller.replaceModelAssignment(
    "agent-1",
    providerInput,
    modelInput,
    submit,
    state,
    { preventDefault() {} },
  );
  assert.equal(replacements, 1);
  release();
  await first;
});

test("keeps auth, permission, conflict, validation, missing, and general failures explicit", async () => {
  const { documentRef, elements } = pageElements();
  let providerListResponse = response(401);
  let modelListResponse = response(403);
  let createResponse = response(409);
  let modelDetailResponse = response(404);
  let replacementResponse = response(500);
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (options.method === "POST") return createResponse;
      if (path === "/api/providers") return providerListResponse;
      if (path === "/api/models") return modelListResponse;
      if (path === "/api/providers/local") return response(404);
      if (options.method === "PUT") return replacementResponse;
      if (path === "/api/models/agent-1") return modelDetailResponse;
      return response(200, provider);
    },
    confirmImpl: () => true,
  });
  await controller.initialLoad;
  assert.match(elements["provider-list-state"].textContent, /Sign-in required/);
  assert.match(elements["model-list-state"].textContent, /Access denied/);

  providerListResponse = response(200, { items: [provider] });
  modelListResponse = response(200, { items: [assignment] });
  await controller.loadProviders();
  await controller.loadAssignments();
  await controller.loadProviderDetail("local");
  assert.match(elements["provider-detail-state"].textContent, /no longer exists/i);

  elements["provider-id"].value = "local";
  elements["provider-name"].value = "Duplicate";
  await controller.createProvider({ preventDefault() {} });
  assert.match(elements["provider-create-state"].textContent, /already exists/);
  createResponse = response(422, {
    detail: [{ loc: ["body", "name"], msg: "Value cannot be blank", input: "" }],
  });
  await controller.createProvider({ preventDefault() {} });
  assert.match(elements["provider-create-state"].textContent, /name: Value cannot be blank/);
  assert.doesNotMatch(elements["provider-create-state"].textContent, /input/);

  await controller.loadModelDetail("agent-1");
  assert.match(elements["model-detail-state"].textContent, /not found|Check the IDs/i);
  modelDetailResponse = response(200, assignment);
  await controller.loadModelDetail("agent-1");
  const form = elements["model-detail"].querySelector(".model-replace-form");
  const providerInput = findElement(form, (item) => item.name === "provider_id");
  const modelInput = findElement(form, (item) => item.name === "model_id");
  const submit = findElement(form, (item) => item.tagName === "button");
  const state = findElement(form, (item) => item.className === "section-state");
  await controller.replaceModelAssignment(
    "agent-1",
    providerInput,
    modelInput,
    submit,
    state,
    { preventDefault() {} },
  );
  assert.match(state.textContent, /could not be completed/);

  providerListResponse = response(503);
  await controller.loadProviders();
  assert.match(elements["provider-list-state"].textContent, /could not be completed/);
  assert.equal(elements["provider-list"].children.length, 0);
});

test("renders successful empty lists separately from failed requests", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountProviderModelPage({
    documentRef,
    fetchImpl: async (path) => response(200, { items: [] }),
    confirmImpl: () => false,
  });
  await controller.initialLoad;
  assert.equal(elements["provider-list-state"].textContent, "No providers found.");
  assert.equal(elements["model-list-state"].textContent, "No model assignments found.");
});

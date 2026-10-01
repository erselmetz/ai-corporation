import assert from "node:assert/strict";
import test from "node:test";

import { mountActivityPage } from "../app/webui/static/activity.mjs";

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
    this.disabled = false;
    this.className = "";
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

function pageElements() {
  const ids = [
    "activity-list",
    "activity-list-state",
    "activity-refresh",
    "activity-limit",
    "activity-task-id",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element("div")]));
  elements["activity-limit"].value = "100";
  const documentRef = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements[id],
  };
  return { documentRef, elements };
}

const records = [
  {
    id: 12,
    task_id: "TASK-12",
    event: "TASK_COMPLETED",
    created_at: "2026-09-30T12:13:14",
  },
  {
    id: 11,
    task_id: "TASK-11",
    event: "TASK_CREATED",
    created_at: "2026-09-30T12:10:00",
  },
];

test("loads the bounded Activity API with same-origin credentials and displays its exact response fields", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      return response(200, { items: records });
    },
  });
  await controller.initialLoad;

  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "/api/activity?limit=100");
  assert.equal(calls[0][1].credentials, "same-origin");
  assert.deepEqual(calls[0][1].headers, { Accept: "application/json" });
  assert.equal(elements["activity-list"].children.length, 2);
  assert.match(elements["activity-list"].textContent, /TASK_COMPLETED/);
  assert.match(elements["activity-list"].textContent, /TASK-12/);
  assert.match(elements["activity-list"].textContent, /2026-09-30T12:13:14/);
  assert.match(elements["activity-list"].textContent, /Activity ID12/);
  assert.doesNotMatch(elements["activity-list"].textContent, /message|Sensitive internal/);
  assert.match(elements["activity-list-state"].textContent, /maximum requested: 100/);
  assert.match(elements["activity-list-state"].textContent, /returned by the API/);
});

test("uses only the supported limit and optional task_id query parameters", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: async (path) => {
      calls.push(path);
      return response(200, { items: [] });
    },
  });
  await controller.initialLoad;

  elements["activity-limit"].value = "25";
  elements["activity-task-id"].value = "TASK-7 & related";
  await controller.loadActivity();
  const query = new URL(calls[1], "http://localhost").searchParams;
  assert.equal(query.get("limit"), "25");
  assert.equal(query.get("task_id"), "TASK-7 & related");
  assert.deepEqual([...query.keys()].sort(), ["limit", "task_id"]);
  assert.match(elements["activity-list-state"].textContent, /No activity records/);
});

test("does not send an unsupported limit value", async () => {
  const { documentRef, elements } = pageElements();
  let calls = 0;
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: async () => {
      calls += 1;
      return response(200, { items: [] });
    },
  });
  await controller.initialLoad;
  elements["activity-limit"].value = "101";
  assert.equal(await controller.loadActivity(), false);
  assert.equal(calls, 1);
  assert.match(elements["activity-list-state"].textContent, /supported maximum/);
  assert.equal(elements["activity-list"].children.length, 0);
});

test("renders a successful empty result differently from an API failure", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: async () => response(200, { items: [] }),
  });
  await controller.initialLoad;
  assert.equal(elements["activity-list"].children.length, 0);
  assert.equal(elements["activity-list-state"].textContent, "No activity records were returned by the API.");
  assert.equal(elements["activity-list-state"].className, "section-state empty-state");
});

test("distinguishes authentication, forbidden, invalid-query and general API failures", async () => {
  const { documentRef, elements } = pageElements();
  let status = 401;
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: async () => response(status),
  });
  await controller.initialLoad;
  assert.match(elements["activity-list-state"].textContent, /Sign-in required/);
  assert.doesNotMatch(elements["activity-list-state"].textContent, /No activity/);

  status = 403;
  await controller.loadActivity();
  assert.match(elements["activity-list-state"].textContent, /activity:read/);

  status = 422;
  await controller.loadActivity();
  assert.match(elements["activity-list-state"].textContent, /rejected the limit or Task ID filter/);

  status = 500;
  await controller.loadActivity();
  assert.match(elements["activity-list-state"].textContent, /could not be loaded/);
  assert.doesNotMatch(elements["activity-list-state"].textContent, /No activity/);
});

test("refresh uses the API again and prevents duplicate requests", async () => {
  const { documentRef, elements } = pageElements();
  let resolveRefresh;
  let calls = 0;
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: async () => {
      calls += 1;
      if (calls === 2) {
        return new Promise((resolve) => {
          resolveRefresh = () => resolve(response(200, { items: records }));
        });
      }
      return response(200, { items: records });
    },
  });
  await controller.initialLoad;

  const refresh = controller.loadActivity();
  assert.equal(elements["activity-refresh"].disabled, true);
  assert.equal(elements["activity-refresh"].textContent, "Loading…");
  assert.equal(elements["activity-list"].children.length, 0);
  assert.equal(await controller.loadActivity(), false);
  assert.equal(calls, 2);
  resolveRefresh();
  assert.equal(await refresh, true);
  assert.equal(elements["activity-refresh"].disabled, false);
  assert.equal(elements["activity-list"].children.length, 2);
});

test("failed refresh clears displayed records instead of leaving them as current", async () => {
  const { documentRef, elements } = pageElements();
  let status = 200;
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: async () =>
      status === 200 ? response(200, { items: records }) : response(503),
  });
  await controller.initialLoad;
  assert.equal(elements["activity-list"].children.length, 2);

  status = 503;
  assert.equal(await controller.loadActivity(), false);
  assert.equal(elements["activity-list"].children.length, 0);
  assert.match(elements["activity-list-state"].textContent, /could not be loaded/);
  assert.doesNotMatch(elements["activity-list-state"].textContent, /No activity/);
});

test("network and malformed-response failures are explicit, not successful empty lists", async () => {
  const { documentRef, elements } = pageElements();
  let fetch = async () => {
    throw new Error("internal transport details");
  };
  const controller = mountActivityPage({
    documentRef,
    fetchImpl: (...args) => fetch(...args),
  });
  await controller.initialLoad;
  assert.match(elements["activity-list-state"].textContent, /could not be loaded/);
  assert.doesNotMatch(elements["activity-list-state"].textContent, /No activity|transport details/);

  fetch = async () => response(200, { items: [{ id: "not-an-integer" }] });
  await controller.loadActivity();
  assert.match(elements["activity-list-state"].textContent, /response was invalid/);
  assert.doesNotMatch(elements["activity-list-state"].textContent, /No activity/);
});

test("uses no Activity detail route, unsupported methods, secrets, or internal layers", async () => {
  const { readFile } = await import("node:fs/promises");
  const source = await readFile(new URL("../app/webui/static/activity.mjs", import.meta.url), "utf8");
  assert.match(source, /\/api\/activity/);
  assert.doesNotMatch(source, /\/api\/activity\/\$\{|\/api\/activity\/\{/);
  assert.doesNotMatch(source, /Bearer\s|api_key|password|secret|process\.env|os\.environ/i);
  assert.doesNotMatch(source, /TaskLogger|TaskRegistry|Orchestrator|ProviderRegistry|Ollama|sqlite|filesystem|database/i);
  assert.doesNotMatch(source, /method:\s*["'](?:POST|PUT|PATCH|DELETE)["']/);
});

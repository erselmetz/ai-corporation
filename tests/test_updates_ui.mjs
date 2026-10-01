import assert from "node:assert/strict";
import test from "node:test";

import { mountUpdatesPage } from "../app/webui/static/updates.mjs";

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
  const ids = ["updates-list", "updates-list-state", "updates-refresh"];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element("div")]));
  const documentRef = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements[id],
  };
  return { documentRef, elements };
}

const entries = [
  {
    date: "2026-10-02",
    type: "development",
    title: "Corporation Updates page",
    summary: "Added the protected read-only updates page.",
  },
  {
    date: "2026-09-30",
    type: "release",
    title: "Example release",
    summary: "A curated release entry.",
  },
];

test("loads the same-origin Updates API and displays explicit entry fields", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountUpdatesPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      return response(200, { items: entries });
    },
  });
  await controller.initialLoad;

  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "/api/updates");
  assert.equal(calls[0][1].credentials, "same-origin");
  assert.deepEqual(calls[0][1].headers, { Accept: "application/json" });
  assert.equal(elements["updates-list"].children.length, 2);
  assert.match(elements["updates-list"].textContent, /Development update/);
  assert.match(elements["updates-list"].textContent, /Release/);
  assert.match(elements["updates-list"].textContent, /2026-10-02/);
  assert.doesNotMatch(elements["updates-list"].textContent, /version/i);
  assert.match(elements["updates-list-state"].textContent, /Loaded 2 curated updates/);
});

test("shows an explicit loading state while the request is pending", async () => {
  const { documentRef, elements } = pageElements();
  let resolveResponse;
  const controller = mountUpdatesPage({
    documentRef,
    fetchImpl: async () => new Promise((resolve) => {
      resolveResponse = resolve;
    }),
  });

  assert.equal(elements["updates-list-state"].textContent, "Loading updates…");
  assert.equal(elements["updates-refresh"].disabled, true);
  resolveResponse(response(200, { items: [] }));
  await controller.initialLoad;
  assert.equal(elements["updates-refresh"].disabled, false);
});

test("distinguishes a successful empty manifest from authentication, permission, and API errors", async () => {
  const { documentRef, elements } = pageElements();
  let result = response(200, { items: [] });
  const controller = mountUpdatesPage({
    documentRef,
    fetchImpl: async () => result,
  });
  await controller.initialLoad;
  assert.equal(elements["updates-list-state"].textContent, "No updates have been recorded yet.");
  assert.equal(elements["updates-list-state"].className, "section-state empty-state");

  result = response(401);
  await controller.loadUpdates();
  assert.match(elements["updates-list-state"].textContent, /Sign-in required/);
  assert.doesNotMatch(elements["updates-list-state"].textContent, /No updates/);

  result = response(403);
  await controller.loadUpdates();
  assert.match(elements["updates-list-state"].textContent, /updates:read/);

  result = response(500);
  await controller.loadUpdates();
  assert.match(elements["updates-list-state"].textContent, /could not be loaded/);
  assert.doesNotMatch(elements["updates-list-state"].textContent, /No updates/);
});

test("failed refresh clears previously rendered updates instead of retaining stale data", async () => {
  const { documentRef, elements } = pageElements();
  let result = response(200, { items: entries });
  const controller = mountUpdatesPage({
    documentRef,
    fetchImpl: async () => result,
  });
  await controller.initialLoad;
  assert.equal(elements["updates-list"].children.length, 2);

  result = response(503);
  await controller.loadUpdates();
  assert.equal(elements["updates-list"].children.length, 0);
  assert.match(elements["updates-list-state"].textContent, /could not be loaded/);
});

test("renders document-supplied strings as text and rejects malformed response data", async () => {
  const { documentRef, elements } = pageElements();
  let result = response(200, {
    items: [{
      ...entries[0],
      title: "<img src=x onerror=alert(1)>",
      summary: "<script>alert(1)</script>",
    }],
  });
  const controller = mountUpdatesPage({
    documentRef,
    fetchImpl: async () => result,
  });
  await controller.initialLoad;

  assert.equal(
    elements["updates-list"].children[0].children[0].children[1].textContent,
    "<img src=x onerror=alert(1)>",
  );
  assert.equal(
    elements["updates-list"].children[0].children[0].children[2].textContent,
    "<script>alert(1)</script>",
  );
  assert.equal(elements["updates-list"].textContent.includes("alert(1)"), true);

  result = response(200, { items: [{ ...entries[0], date: "next week" }] });
  await controller.loadUpdates();
  assert.equal(elements["updates-list"].children.length, 0);
  assert.match(elements["updates-list-state"].textContent, /response was invalid/);
});

test("refresh reloads from the API and prevents duplicate requests", async () => {
  const { documentRef, elements } = pageElements();
  let resolveRefresh;
  let calls = 0;
  const controller = mountUpdatesPage({
    documentRef,
    fetchImpl: async () => {
      calls += 1;
      if (calls === 2) {
        return new Promise((resolve) => {
          resolveRefresh = () => resolve(response(200, { items: entries }));
        });
      }
      return response(200, { items: entries });
    },
  });
  await controller.initialLoad;

  const refresh = controller.loadUpdates();
  assert.equal(elements["updates-refresh"].disabled, true);
  assert.equal(elements["updates-list"].children.length, 0);
  assert.equal(await controller.loadUpdates(), false);
  assert.equal(calls, 2);
  resolveRefresh();
  assert.equal(await refresh, true);
  assert.equal(elements["updates-list"].children.length, 2);
});

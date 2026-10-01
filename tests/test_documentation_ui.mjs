import assert from "node:assert/strict";
import test from "node:test";

import { mountDocumentationPage } from "../app/webui/static/documentation.mjs";

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
    this.hidden = false;
    this.disabled = false;
    this.className = "";
    this.type = "";
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
}

function pageElements() {
  const ids = [
    "documentation-list",
    "documentation-list-state",
    "documentation-refresh",
    "documentation-detail-state",
    "documentation-content-title",
    "documentation-content",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element("div")]));
  const documentRef = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements[id],
  };
  return { documentRef, elements };
}

const summary = { id: "overview", title: "Corporation Overview" };
const documentRecord = {
  ...summary,
  content: "# Corporation Overview\n\nPlain Markdown content.",
};

test("loads document summaries and content from the protected same-origin API", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountDocumentationPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      if (path === "/api/documentation") return response(200, { items: [summary] });
      return response(200, documentRecord);
    },
  });

  await controller.initialLoad;
  assert.equal(calls[0][0], "/api/documentation");
  assert.equal(calls[0][1].credentials, "same-origin");
  assert.equal(elements["documentation-list"].children.length, 1);
  assert.equal(elements["documentation-list"].textContent, "Corporation Overview");

  assert.equal(await controller.loadDocument("overview"), true);
  assert.equal(calls[1][0], "/api/documentation/overview");
  assert.equal(calls[1][1].credentials, "same-origin");
  assert.equal(elements["documentation-content-title"].textContent, "Corporation Overview");
  assert.equal(elements["documentation-content"].textContent, documentRecord.content);
  assert.equal(elements["documentation-content"].hidden, false);
});

test("renders a successful empty response as an empty state", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountDocumentationPage({
    documentRef,
    fetchImpl: async () => response(200, { items: [] }),
  });

  assert.equal(await controller.initialLoad, true);
  assert.equal(elements["documentation-list"].children.length, 0);
  assert.equal(elements["documentation-list-state"].className, "section-state empty-state");
  assert.match(elements["documentation-list-state"].textContent, /No documentation/);
});

test("authentication, permission, invalid response, and server failures are not empty results", async () => {
  for (const [status, expectedText] of [
    [401, /Sign-in required/],
    [403, /Access denied/],
    [422, /rejected the request/],
    [500, /could not be loaded/],
  ]) {
    const { documentRef, elements } = pageElements();
    const controller = mountDocumentationPage({
      documentRef,
      fetchImpl: async () => response(status, {}),
    });

    assert.equal(await controller.initialLoad, false);
    assert.equal(elements["documentation-list"].children.length, 0);
    assert.equal(elements["documentation-list-state"].className, "section-state error-state");
    assert.match(elements["documentation-list-state"].textContent, expectedText);
    assert.doesNotMatch(elements["documentation-list-state"].textContent, /No documentation/);
  }
});

test("missing and failed document reads clear previously displayed content", async () => {
  for (const [status, expectedText] of [
    [401, /Sign-in required/],
    [403, /Access denied/],
    [404, /not found/],
    [500, /could not be loaded/],
  ]) {
    const { documentRef, elements } = pageElements();
    let readStatus = 200;
    const controller = mountDocumentationPage({
      documentRef,
      fetchImpl: async (path) => {
        if (path === "/api/documentation") return response(200, { items: [summary] });
        return readStatus === 200
          ? response(200, documentRecord)
          : response(readStatus, {});
      },
    });

    await controller.initialLoad;
    await controller.loadDocument("overview");
    readStatus = status;
    assert.equal(await controller.loadDocument("overview"), false);
    assert.equal(elements["documentation-content"].textContent, "");
    assert.equal(elements["documentation-content"].hidden, true);
    assert.equal(elements["documentation-content-title"].textContent, "");
    assert.equal(elements["documentation-detail-state"].className, "section-state error-state");
    assert.match(elements["documentation-detail-state"].textContent, expectedText);
  }
});

test("failed refresh prevents duplicates and clears stale records and content", async () => {
  const { documentRef, elements } = pageElements();
  let shouldFail = false;
  let releaseRequest;
  let calls = 0;
  const controller = mountDocumentationPage({
    documentRef,
    fetchImpl: async (path) => {
      calls += 1;
      if (path !== "/api/documentation") return response(200, documentRecord);
      if (!shouldFail) return response(200, { items: [summary] });
      return new Promise((resolve) => {
        releaseRequest = () => resolve(response(500, {}));
      });
    },
  });

  await controller.initialLoad;
  await controller.loadDocument("overview");
  shouldFail = true;
  const firstRefresh = controller.loadDocuments();
  assert.equal(elements["documentation-list"].children.length, 0);
  assert.equal(elements["documentation-content"].textContent, "");
  assert.equal(elements["documentation-list-state"].textContent, "Loading documents…");
  assert.equal(await controller.loadDocuments(), false);
  assert.equal(calls, 3);
  releaseRequest();
  assert.equal(await firstRefresh, false);
  assert.equal(elements["documentation-list"].children.length, 0);
  assert.equal(elements["documentation-list-state"].className, "section-state error-state");
  assert.match(elements["documentation-list-state"].textContent, /could not be loaded/);
});

test("network failures are explicit and invalid document payloads are rejected", async () => {
  const firstPage = pageElements();
  const failedController = mountDocumentationPage({
    documentRef: firstPage.documentRef,
    fetchImpl: async () => {
      throw new Error("network unavailable");
    },
  });
  assert.equal(await failedController.initialLoad, false);
  assert.equal(firstPage.elements["documentation-list-state"].className, "section-state error-state");

  const secondPage = pageElements();
  const controller = mountDocumentationPage({
    documentRef: secondPage.documentRef,
    fetchImpl: async (path) => path === "/api/documentation"
      ? response(200, { items: [summary] })
      : response(200, { ...documentRecord, id: "different-document" }),
  });
  await controller.initialLoad;
  assert.equal(await controller.loadDocument("overview"), false);
  assert.equal(secondPage.elements["documentation-content"].textContent, "");
  assert.match(
    secondPage.elements["documentation-detail-state"].textContent,
    /invalid document/,
  );
});

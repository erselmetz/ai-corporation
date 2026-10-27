// Browser fixture: Python/CDP runner; original assertion behavior retained.
﻿import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { isQuietNow, mountSuggestions } from "../app/webui/static/suggestions.mjs";

class Element {
  constructor(tag = "div") { this.tag = tag; this.children = []; this.listeners = {}; this.value = ""; this.checked = false; this.disabled = false; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  async fire(type, event = {}) { await this.listeners[type]?.({ preventDefault() {}, currentTarget: this, ...event }); }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return (this.text ?? "") + this.children.map(child => child.textContent).join(""); }
}

function setup() {
  const ids = ["suggestions-status", "suggestions-list", "suggestions-settings", "suggestions-enabled",
    "suggestions-quiet-start", "suggestions-quiet-end", "suggestions-refresh"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(id === "suggestions-list" ? "ul" : "div")]));
  const documentRef = { getElementById: id => elements[id], createElement: tag => new Element(tag) };
  return { elements, documentRef };
}

const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

test("quiet periods use browser local time, including windows across midnight", () => {
  const quiet = { quiet_start: "22:00", quiet_end: "07:00" };
  assert.equal(isQuietNow(quiet, new Date(2026, 0, 1, 23, 30)), true);
  assert.equal(isQuietNow(quiet, new Date(2026, 0, 1, 6, 59)), true);
  assert.equal(isQuietNow(quiet, new Date(2026, 0, 1, 7, 0)), false);
  assert.equal(isQuietNow(quiet, new Date(2026, 0, 1, 12, 0)), false);
  assert.equal(isQuietNow({ quiet_start: "", quiet_end: "" }), false);
});

test("disabled suggestions do not read workflow signals and controls remain available", async () => {
  const { elements, documentRef } = setup();
  const calls = [];
  const fetchImpl = async (path, options = {}) => {
    calls.push([path, options]);
    if (path === "/api/local/session") return response({ csrf: "test-csrf" });
    if (path === "/api/local/suggestions/preferences") return response({ preferences: { enabled: false, quiet_start: "", quiet_end: "" } });
    throw new Error(`Unexpected fetch: ${path}`);
  };
  await mountSuggestions({ documentRef, fetchImpl });
  assert.equal(calls.some(([path]) => path === "/api/local/suggestions"), false);
  assert.match(elements["suggestions-status"].textContent, /Suggestions are off/);
});

test("enabled suggestions disclose source, support owner dismissal, and refresh only on request", async () => {
  const { elements, documentRef } = setup();
  const calls = [];
  let enabled = false;
  const fetchImpl = async (path, options = {}) => {
    calls.push([path, options]);
    if (path === "/api/local/session") return response({ csrf: "test-csrf" });
    if (path === "/api/local/suggestions/preferences" && options.method === "PUT") {
      enabled = JSON.parse(options.body).enabled;
      return response({ preferences: { enabled, quiet_start: "", quiet_end: "" } });
    }
    if (path === "/api/local/suggestions/preferences") return response({ preferences: { enabled, quiet_start: "", quiet_end: "" } });
    if (path === "/api/local/suggestions/item-one/dismiss") return response({ dismissed: true });
    if (path === "/api/local/suggestions") return response({ enabled: true, generated_at: "2026-10-14T12:00:00Z", suggestions: [
      { id: "item-one", title: "Inspect failed work", reason: "Recorded state is failed.", state: "failed",
        observed_at: "2026-10-14T12:00:00Z", source: { workflow_id: "workflow-1", work_item_id: "item-1", last_changed_at: "2026-10-14T11:50:00Z" }, href: "/ui/workflow-map" },
    ] });
    throw new Error(`Unexpected fetch: ${path}`);
  };
  await mountSuggestions({ documentRef, fetchImpl, nowImpl: () => new Date(2026, 0, 1, 12, 0) });
  assert.equal(calls.filter(([path]) => path === "/api/local/suggestions").length, 0);
  elements["suggestions-enabled"].checked = true;
  await elements["suggestions-settings"].fire("submit");
  assert.equal(calls.filter(([path]) => path === "/api/local/suggestions").length, 1);
  assert.match(elements["suggestions-list"].textContent, /Inspect failed work/);
  assert.match(elements["suggestions-list"].textContent, /Workflow workflow-1, item item-1.*last changed.*checked/);
  assert.match(elements["suggestions-status"].textContent, /Source: local workflow records/);
  const dismiss = elements["suggestions-list"].children[0].children[3].children[1];
  await dismiss.fire("click");
  assert.equal(calls.filter(([path]) => path.endsWith("/dismiss")).length, 1);
  assert.equal(calls.filter(([path]) => path === "/api/local/suggestions").length, 2);
  assert.equal(calls.find(([path]) => path.endsWith("/dismiss"))[1].headers["X-Local-CSRF"], "test-csrf");
});

test("quiet-period settings suppress fetching and displaying suggestion cards", async () => {
  const { elements, documentRef } = setup();
  const calls = [];
  const fetchImpl = async (path) => {
    calls.push(path);
    if (path === "/api/local/session") return response({ csrf: "csrf" });
    if (path === "/api/local/suggestions/preferences") return response({ preferences: {
      enabled: true, quiet_start: "22:00", quiet_end: "07:00",
    } });
    throw new Error(`Unexpected fetch: ${path}`);
  };
  await mountSuggestions({ documentRef, fetchImpl, nowImpl: () => new Date(2026, 0, 1, 23, 0) });
  assert.equal(calls.includes("/api/local/suggestions"), false);
  assert.equal(elements["suggestions-list"].children.length, 0);
  assert.match(elements["suggestions-status"].textContent, /Quiet period is active/);
});

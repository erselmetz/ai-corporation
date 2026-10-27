// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";

class Element {
  constructor(id) { this.id = id; this.listeners = {}; this.text = ""; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  async fire(type) { await this.listeners[type]?.(); }
  set textContent(value) { this.text = String(value); }
  get textContent() { return this.text; }
}

const elements = Object.fromEntries(["readiness-state", "readiness-report", "readiness-refresh"]
  .map(id => [id, new Element(id)]));
globalThis.document = { querySelector: selector => elements[selector.slice(1)] };
const calls = [];
let result = { state: "measured", value: 12 };
globalThis.fetch = async (url, options) => {
  calls.push([url, options]);
  return { ok: result.state !== "forbidden", status: result.state === "forbidden" ? 403 : 200,
    json: async () => result.state === "forbidden" ? { detail: "Forbidden" } : result };
};

await import("../app/webui/static/readiness.mjs");

test("readiness UI requests a bounded same-origin snapshot only after refresh", async () => {
  assert.equal(calls.length, 0);
  await elements["readiness-refresh"].fire("click");
  assert.equal(calls[0][0], "/api/local/readiness");
  assert.equal(calls[0][1].credentials, "same-origin");
  assert.match(elements["readiness-report"].textContent, /measured/);
});

test("authorization failures clear stale readiness evidence", async () => {
  result = { state: "forbidden" };
  await elements["readiness-refresh"].fire("click");
  assert.equal(elements["readiness-report"].textContent, "");
  assert.match(elements["readiness-state"].textContent, /Forbidden/);
});

import assert from "node:assert/strict";
import test from "node:test";
import { mountInventoryPage } from "../app/webui/static/inventory.mjs";

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ""; }
  set innerHTML(_) { throw new Error("Inventory values must be rendered as text"); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener(type, listener) { this.listenerType = type; this.listener = listener; }
}

function page() {
  const elements = new Map([
    ["#inventory-status", new Element("p")],
    ["#inventory-records", new Element("div")],
    ["#inventory-limitations", new Element("ul")],
    ["#inventory-refresh", new Element("button")],
  ]);
  return {
    elements,
    document: {
      querySelector: (selector) => elements.get(selector),
      createElement: (tag) => new Element(tag),
    },
  };
}

const ok = (body) => ({ ok: true, status: 200, json: async () => body });

test("inventory UI requires sign-in before requesting inventory data", async () => {
  const { document, elements } = page();
  const calls = [];
  const ui = mountInventoryPage(document, async (url) => {
    calls.push(url);
    return { ok: false, status: 401 };
  });
  await ui.refresh();
  assert.deepEqual(calls, ["/api/local/session"]);
  assert.match(elements.get("#inventory-status").textContent, /Sign in/);
  assert.equal(elements.get("#inventory-records").children.length, 0);
});

test("inventory UI renders verified records as inert text and shows limitations", async () => {
  const { document, elements } = page();
  const calls = [];
  const ui = mountInventoryPage(document, async (url, options) => {
    calls.push([url, options]);
    if (url === "/api/local/session") return ok({ permissions: ["inventory:read"] });
    return ok({
      generated_at: "2026-10-12T08:00:00+00:00",
      items: [{
        id: "provider-one", name: "<img src=x onerror=alert(1)>", kind: "integration", status: "stale",
        source: "configured connection", version: null, revision: null,
        dependent_workflows: ["agent:architect"], models: ["qwen3:4b"],
      }],
      limitations: ["Windows software is not scanned."],
    });
  });
  assert.equal(elements.get("#inventory-refresh").listenerType, "click");
  await ui.refresh();
  assert.deepEqual(calls.map(([url]) => url), ["/api/local/session", "/api/local/inventory"]);
  assert.equal(calls[1][1].cache, "no-store");
  const [card] = elements.get("#inventory-records").children;
  assert.equal(card.children[0].textContent, "<img src=x onerror=alert(1)>");
  assert.equal(card.children[1].textContent, "integration - stale");
  assert.match(card.children[2].children.map((node) => node.textContent).join(" "), /agent:architect/);
  assert.equal(elements.get("#inventory-limitations").children[0].textContent, "Windows software is not scanned.");
  assert.match(elements.get("#inventory-status").textContent, /Showing 1 read-only records/);
});

test("inventory UI denies sessions without inventory permission", async () => {
  const { document, elements } = page();
  const calls = [];
  const ui = mountInventoryPage(document, async (url) => {
    calls.push(url);
    return ok({ permissions: ["corporation:read"] });
  });
  await ui.refresh();
  assert.deepEqual(calls, ["/api/local/session"]);
  assert.match(elements.get("#inventory-status").textContent, /cannot inspect inventory/);
});

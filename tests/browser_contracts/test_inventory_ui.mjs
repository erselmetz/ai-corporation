// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { mountInventoryPage } from "../app/webui/static/inventory.mjs";

class Element {
  constructor(tag, value = "") { this.tag = tag; this.children = []; this.textContent = ""; this.value = value; this.hidden = false; this.disabled = false; }
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
    ["#software-manager-state", new Element("p")],
    ["#software-manager-details", new Element("dl")],
    ["#software-manager-controls", new Element("div")],
    ["#software-manager-limitations", new Element("ul")],
    ["#software-action", new Element("select", "install")],
    ["#software-version", new Element("input")],
    ["#software-preview", new Element("button")],
    ["#software-preview-panel", new Element("div")],
    ["#software-preview-details", new Element("dl")],
    ["#software-confirm", new Element("button")],
    ["#software-operation-result", new Element("p")],
  ]);
  elements.get("#software-action").children = ["install", "update", "version", "pin", "unpin", "remove"].map((value) => new Element("option", value));
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
    if (url === "/api/local/session") return ok({ permissions: ["inventory:read", "software:read"], csrf: "csrf" });
    if (url === "/api/local/software") return ok({ name: "VS Code", package_id: "Microsoft.VisualStudioCode", source: "winget", scope: "user", status: "externally_managed", installed_version: "1.2.3", dependent_workflows: [], limitations: [] });
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
  assert.deepEqual(calls.map(([url]) => url), ["/api/local/session", "/api/local/inventory", "/api/local/software"]);
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

test("software lifecycle requires exact preview and separate explicit confirmation", async () => {
  const { document, elements } = page();
  const calls = [];
  const ui = mountInventoryPage(document, async (url, options = {}) => {
    calls.push([url, options]);
    if (url === "/api/local/session") return ok({ permissions: ["inventory:read", "software:read", "software:manage"], csrf: "csrf-owner" });
    if (url === "/api/local/inventory") return ok({ generated_at: "now", items: [], limitations: [] });
    if (url === "/api/local/software") return ok({ name: "Microsoft Visual Studio Code", package_id: "Microsoft.VisualStudioCode", source: "winget", scope: "user", status: "not_installed", installed_version: null, managed_version: null, pinned_version: false, dependent_workflows: ["source_development"], limitations: [] });
    if (url === "/api/local/software/preview") return ok({ action: "install", name: "Microsoft Visual Studio Code", package_id: "Microsoft.VisualStudioCode", source: "winget", scope: "user", from_version: null, to_version: "1.142.0", installer_sha256: "a".repeat(64), affected_dependents: [], preserved_data: ["%APPDATA%\\Code"], removed_install_directory: null, warnings: ["Owner approval required."], expires_in_seconds: 300, confirmation_id: "c".repeat(32), preview_sha256: "d".repeat(64) });
    if (url === "/api/local/software/confirm") return ok({ status: "completed", action: "install", version: "1.142.0" });
    throw new Error(`Unexpected URL ${url}`);
  });
  await ui.refresh();
  assert.equal(elements.get("#software-manager-controls").hidden, false);
  elements.get("#software-version").value = "1.142.0";
  await ui.requestPreview();
  assert.equal(elements.get("#software-preview-panel").hidden, false);
  assert.equal(calls.some(([url]) => url === "/api/local/software/confirm"), false);
  const preview = calls.find(([url]) => url === "/api/local/software/preview");
  assert.equal(preview[1].headers["X-Local-CSRF"], "csrf-owner");
  assert.deepEqual(JSON.parse(preview[1].body), { action: "install", version: "1.142.0" });
  await ui.confirmPreview();
  const confirm = calls.find(([url]) => url === "/api/local/software/confirm");
  assert.deepEqual(JSON.parse(confirm[1].body), { confirmation_id: "c".repeat(32), preview_sha256: "d".repeat(64) });
  assert.equal(elements.get("#software-preview-panel").hidden, true);
});

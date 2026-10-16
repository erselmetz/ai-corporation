import assert from "node:assert/strict";
import test from "node:test";
import { mountOwnerKnowledge } from "../app/webui/static/knowledge.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.children = []; this.text = ""; this.value = ""; this.checked = false; this.disabled = false; this.listeners = {}; this.files = []; }
  get textContent() { return this.text + this.children.map(item => item.textContent).join(""); }
  set textContent(value) { this.text = value; this.children = []; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children = []; this.text = ""; }
  addEventListener(event, fn) { this.listeners[event] = fn; }
}
const ids = ["knowledge-state", "knowledge-index-status", "knowledge-list", "knowledge-detail", "knowledge-note-form",
  "knowledge-source", "knowledge-content", "knowledge-expiry", "knowledge-consent", "knowledge-save",
  "knowledge-upload-form", "knowledge-file", "knowledge-upload", "knowledge-refresh", "knowledge-index",
  "knowledge-inspect", "knowledge-delete"];
const response = (payload, status = 200) => ({ ok: status === 200, status, json: async () => payload });
const record = { id: "note-1", scope: "owner", scope_id: "local-owner", source_reference: "notes.md", expires_at: "2026-10-20T00:00:00+00:00" };
const auth = { identity: "local-owner", csrf: "csrf", permissions: ["memory:read", "memory:manage", "memory:index"] };
const summary = (items = [record], state = "disabled") => ({ scope: "owner", scope_id: "local-owner", items,
  semantic: { state, model: state === "configured" ? "local-embed" : null, detail: "optional local capability" } });
function setup(handler) {
  const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
  elements["knowledge-expiry"].value = "7";
  const calls = [];
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    const custom = await handler(path, options, calls);
    return custom || response({});
  };
  const documentRef = { getElementById: id => elements[id], createElement: tag => new Element(tag) };
  mountOwnerKnowledge({ documentRef, fetchImpl, confirmImpl: () => true, now: () => new Date("2026-10-16T00:00:00Z") });
  return { elements, calls };
}

test("owner notes require explicit retention consent and send CSRF-bound local data", async () => {
  const ui = setup(path => {
    if (path === "/api/local/session") return response(auth);
    if (path === "/api/memory/owner") return response(summary([]));
    return null;
  });
  // The initial refresh completes through the next microtask turn.
  await new Promise(resolve => setTimeout(resolve, 0));
  ui.elements["knowledge-content"].value = "My local project note";
  ui.elements["knowledge-note-form"].listeners.submit({ preventDefault() {} });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(ui.elements["knowledge-state"].textContent, /retention consent/);
});

test("explicit note save persists content and expiry, and index diagnostics stay truthful", async () => {
  let created = false;
  const ui = setup((path, options) => {
    if (path === "/api/local/session") return response(auth);
    if (path === "/api/memory/owner" && options.method === "POST") {
      created = true;
      return response({ ...record, content: "My local project note" });
    }
    if (path === "/api/memory/owner") return response(summary(created ? [record] : [], "disabled"));
    return null;
  });
  await new Promise(resolve => setTimeout(resolve, 0));
  ui.elements["knowledge-content"].value = "My local project note";
  ui.elements["knowledge-consent"].checked = true;
  ui.elements["knowledge-note-form"].listeners.submit({ preventDefault() {} });
  await new Promise(resolve => setTimeout(resolve, 0));
  const save = ui.calls.find(call => call.path === "/api/memory/owner" && call.options.method === "POST");
  assert.equal(JSON.parse(save.options.body).retention_opt_in, true);
  assert.equal(save.options.headers["X-Local-CSRF"], "csrf");
  assert.match(ui.elements["knowledge-state"].textContent, /Private note saved locally/);
  assert.match(ui.elements["knowledge-index-status"].textContent, /Lexical retrieval remains available/);
  assert.equal(ui.elements["knowledge-index"].disabled, true);
});

test("index inspection and deletion use the selected owner scope", async () => {
  const ui = setup((path, options) => {
    if (path === "/api/local/session") return response(auth);
    if (path === "/api/memory/owner") return response(summary([record], "configured"));
    if (path === "/api/memory/semantic/inspect") return response({ sources: [{ state: "current", indexed_chunks: 1, indexed_at: "2026-10-16T00:00:00+00:00", detail: "Matches current note." }] });
    if (path.startsWith("/api/memory/record?") && options.method === "DELETE") return response(null, 204);
    return null;
  });
  await new Promise(resolve => setTimeout(resolve, 0));
  const selectButton = ui.elements["knowledge-list"].children[0].children[0];
  selectButton.listeners.click();
  ui.elements["knowledge-inspect"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(ui.elements["knowledge-detail"].textContent, /current; 1 chunks; last built 2026-10-16/);
  ui.elements["knowledge-delete"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  const deletion = ui.calls.find(call => call.options.method === "DELETE");
  assert.match(deletion.path, /scope=owner/);
  assert.equal(deletion.options.headers["X-Local-CSRF"], "csrf");
  assert.match(ui.elements["knowledge-state"].textContent, /Private note forgotten/);
});

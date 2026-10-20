import assert from "node:assert/strict";
import test from "node:test";
import { mountOwnerKnowledge } from "../app/webui/static/knowledge.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.children = []; this.text = ""; this.value = ""; this.checked = false; this.disabled = false; this.listeners = {}; this.files = []; this.classList = { add() {}, remove() {} }; }
  get textContent() { return this.text + this.children.map(item => item.textContent).join(""); }
  set textContent(value) { this.text = value; this.children = []; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children = []; this.text = ""; }
  addEventListener(event, fn) { this.listeners[event] = fn; }
}
const ids = ["knowledge-state", "knowledge-index-status", "knowledge-list", "knowledge-detail", "knowledge-note-form",
  "knowledge-source", "knowledge-content", "knowledge-expiry", "knowledge-consent", "knowledge-save",
  "knowledge-upload-form", "knowledge-file", "knowledge-upload", "knowledge-refresh", "knowledge-index",
  "knowledge-inspect", "knowledge-delete", "knowledge-folder", "brain-selection-status", "brain-drop-zone",
  "brain-ingestion-list", "brain-faiss-state", "brain-faiss-install", "brain-faiss-test", "brain-faiss-detail",
  "brain-embedding-state", "brain-embedding-download", "brain-embedding-test", "brain-embedding-detail"];
const response = (payload, status = 200) => ({ ok: status === 200, status, json: async () => payload });
const record = { id: "note-1", scope: "owner", scope_id: "local-owner", source_reference: "notes.md", expires_at: "2026-10-20T00:00:00+00:00" };
const auth = { identity: "local-owner", csrf: "csrf", permissions: ["memory:read", "memory:manage", "memory:index"] };
const summary = (items = [record], state = "disabled") => ({ scope: "owner", scope_id: "local-owner", items,
  semantic: { state, model: state === "configured" ? "local-embed" : null, detail: "optional local capability" } });
function setup(handler, confirmImpl = () => true) {
  const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
  elements["knowledge-expiry"].value = "7";
  const calls = [];
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    const custom = await handler(path, options, calls);
    return custom || response({});
  };
  const documentRef = { getElementById: id => elements[id], createElement: tag => new Element(tag), createTextNode: text => { const node = new Element("#text"); node.textContent = text; return node; } };
  mountOwnerKnowledge({ documentRef, fetchImpl, confirmImpl, now: () => new Date("2026-10-16T00:00:00Z") });
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
  await new Promise(resolve => setTimeout(resolve, 30));
  const save = ui.calls.find(call => call.path === "/api/memory/owner" && call.options.method === "POST");
  assert.equal(JSON.parse(save.options.body).retention_opt_in, true);
  assert.equal(save.options.headers["X-Local-CSRF"], "csrf");
  assert.equal(ui.elements["brain-ingestion-list"].children.length, 1);
  assert.match(ui.elements["brain-ingestion-list"].textContent, /Ready — searchable with local lexical retrieval/);
  assert.match(ui.elements["knowledge-index-status"].textContent, /Lexical retrieval remains available/);
  assert.equal(ui.elements["knowledge-index"].disabled, true);
});

test("Brain accepts a bounded multi-file batch and reports each file through chunking to lexical-ready", async () => {
  let uploads = 0;
  const ui = setup((path, options) => {
    if (path === "/api/local/session") return response(auth);
    if (path.startsWith("/api/memory/owner/upload?")) {
      uploads++;
      return response({ ...record, id: `item-${uploads}`, chunk_count: 1 });
    }
    if (path === "/api/memory/owner") return response(summary([]));
    return null;
  });
  await new Promise(resolve => setTimeout(resolve, 0));
  const firstFile = new Blob(["first note"]); Object.defineProperty(firstFile, "name", { value: "first.md" });
  const secondFile = new Blob(["second note"]); Object.defineProperty(secondFile, "name", { value: "second.py" });
  ui.elements["knowledge-file"].files = [firstFile, secondFile];
  ui.elements["knowledge-consent"].checked = true;
  ui.elements["knowledge-upload-form"].listeners.submit({ preventDefault() {} });
  await new Promise(resolve => setTimeout(resolve, 100));
  assert.equal(uploads, 2);
  assert.equal(ui.elements["brain-ingestion-list"].children.length, 2);
  assert.match(ui.elements["brain-ingestion-list"].textContent, /Ready — searchable with local lexical retrieval/);
  assert.equal(ui.calls.filter(call => call.path.startsWith("/api/memory/owner/upload?")).length, 2);
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

test("optional FAISS pack is reviewed before install and cancellation downloads nothing", async () => {
  const preview = { pack_id: "faiss-cpu", state: "not-installed", supported: true, files: ["faiss.whl", "numpy.whl"], download_bytes: 42,
    manifest_digest: "a".repeat(64), source: "Official PyPI", install_action: "Owner confirmation required" };
  let confirmationText = "";
  let reviewedDetail = "";
  const ui = setup(path => {
    if (path === "/api/local/session") return response(auth);
    if (path === "/api/memory/owner") return response(summary([]));
    if (path === "/api/memory/brain/faiss/preview") return response(preview);
    return null;
  }, question => { confirmationText = question; reviewedDetail = ui.elements["brain-faiss-detail"].textContent; return false; });
  await new Promise(resolve => setTimeout(resolve, 0));
  ui.elements["brain-faiss-install"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(confirmationText, /0\.0 MiB/);
  assert.match(reviewedDetail, /42 bytes/);
  assert.match(confirmationText, new RegExp(preview.manifest_digest));
  assert.equal(ui.calls.some(call => call.path === "/api/memory/brain/faiss/install"), false);
  assert.match(ui.elements["brain-faiss-detail"].textContent, /cancelled.*No files were downloaded/);
});

test("FAISS Test it action reports its self-test result", async () => {
  const ui = setup(path => {
    if (path === "/api/local/session") return response(auth);
    if (path === "/api/memory/owner") return response(summary([]));
    if (path === "/api/memory/brain/faiss/preview") return response({ state: "installed", supported: true, files: [], download_bytes: 0,
      manifest_digest: "b".repeat(64), source: "Official PyPI", install_action: "Installed" });
    if (path === "/api/memory/brain/faiss/self-test") return response({ state: "working", detail: "Temporary local test passed." });
    return null;
  });
  await new Promise(resolve => setTimeout(resolve, 0));
  ui.elements["brain-faiss-test"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(ui.elements["brain-faiss-state"].textContent, /Working/);
  assert.match(ui.elements["brain-faiss-detail"].textContent, /Temporary local test passed/);
});

test("nomic embedding download requires a digest/size preview and owner confirmation", async () => {
  const digest = "sha256:" + "c".repeat(64);
  let confirmation = ""; let reviewed = "";
  let ui;
  ui = setup(path => {
    if (path === "/api/local/session") return response(auth);
    if (path === "/api/memory/owner") return response(summary([]));
    if (path === "/api/memory/brain/faiss/preview") return response({ state: "not-installed", supported: false });
    if (path === "/api/memory/brain/embedding/status") return response({ service_running: true, model_installed: false });
    if (path === "/api/memory/brain/embedding/preview") return response({ model_id: "nomic-embed-text:latest", manifest_digest: digest, manifest_bytes: 100,
      model_installed: false, registry_url: "https://registry.ollama.ai/fixed" });
    return null;
  }, question => { confirmation = question; reviewed = ui.elements["brain-embedding-detail"].textContent; return false; });
  await new Promise(resolve => setTimeout(resolve, 0));
  ui.elements["brain-embedding-download"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(confirmation, /nomic-embed-text:latest/);
  assert.match(confirmation, new RegExp(digest));
  assert.match(reviewed, /100 bytes/);
  assert.equal(ui.calls.some(call => call.path === "/api/memory/brain/embedding/pull"), false);
  assert.match(ui.elements["brain-embedding-detail"].textContent, /cancelled.*No model data was requested/);
});

test("embedding Test it action reports only the local Ollama self-test", async () => {
  const ui = setup(path => {
    if (path === "/api/local/session") return response(auth);
    if (path === "/api/memory/owner") return response(summary([]));
    if (path === "/api/memory/brain/faiss/preview") return response({ state: "not-installed", supported: false });
    if (path === "/api/memory/brain/embedding/status") return response({ service_running: true, model_installed: true });
    if (path === "/api/memory/brain/embedding/self-test") return response({ state: "working", dimensions: 768,
      detail: "Ollama returned a bounded local embedding vector." });
    return null;
  });
  await new Promise(resolve => setTimeout(resolve, 0));
  ui.elements["brain-embedding-test"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(ui.elements["brain-embedding-state"].textContent, /Working/);
  assert.match(ui.elements["brain-embedding-detail"].textContent, /bounded local embedding vector/);
  assert.ok(ui.calls.some(call => call.path === "/api/memory/brain/embedding/self-test"));
});

import assert from "node:assert/strict";
import test from "node:test";
import { mountCapabilityPacks } from "../app/webui/static/capability-packs.mjs";

class Element {
  constructor(tag = "div") { this.tagName = tag; this.children = []; this.listeners = {}; this.disabled = false; this.textContent = ""; }
  setAttribute(name, value) { this[name] = value; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  click() { return this.listeners.click?.(); }
}
function fixture() {
  const els = { "media-capability-packs": new Element(), "media-capability-packs-status": new Element() };
  return { els, createElement: tag => new Element(tag), getElementById: id => els[id] || null };
}
const preview = { pack_id: "eyes", title: "Eyes pack", state: "not-installed", supported: true,
  files: ["pillow.whl", "pytesseract.whl"], download_bytes: 1234, manifest_digest: "a".repeat(64),
  source: "Official PyPI", compatibility: "CPython 3.14, Windows x64", detail: "Tesseract is separate." };
const response = body => ({ ok: true, status: 200, json: async () => body });
const settle = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };

test("pack UI renders observed status and exact reviewed wheel manifest", async () => {
  const documentRef = fixture();
  mountCapabilityPacks({ documentRef, fetchImpl: async () => response({ items: [preview] }) });
  await settle();
  const card = documentRef.els["media-capability-packs"].children[0];
  assert.equal(card.children[1].textContent.startsWith("Not installed"), true);
  assert.equal(card.children[3].children[1].textContent.includes(preview.manifest_digest), true);
  assert.equal(card.children[4].children[0].disabled, false);
  assert.equal(card.children[4].children[1].disabled, true);
});

test("cancelled install makes no write request", async () => {
  const documentRef = fixture(), calls = [];
  mountCapabilityPacks({ documentRef, confirmImpl: () => false, fetchImpl: async (url, options = {}) => {
    calls.push([url, options]); return response({ items: [preview] });
  } });
  await settle();
  const card = documentRef.els["media-capability-packs"].children[0];
  await card.children[4].children[0].click();
  assert.equal(calls.some(([, options]) => options.method === "POST"), false);
  assert.match(documentRef.els["media-capability-packs-status"].textContent, /cancelled.*No files were downloaded/);
});

test("confirmed install binds confirmation to the displayed manifest and CSRF session", async () => {
  const documentRef = fixture(), posts = [];
  mountCapabilityPacks({ documentRef, confirmImpl: message => message.includes(preview.manifest_digest), fetchImpl: async (url, options = {}) => {
    if (url === "/api/local/session") return response({ csrf: "csrf" });
    if (url === "/api/capability-packs/eyes/install") { posts.push([url, options]); return response({ state: "installed" }); }
    return response({ items: [{ ...preview, state: posts.length ? "installed" : "not-installed" }] });
  } });
  await settle();
  await documentRef.els["media-capability-packs"].children[0].children[4].children[0].click();
  await settle();
  assert.equal(posts.length, 1);
  assert.equal(posts[0][1].headers["X-Local-CSRF"], "csrf");
  assert.deepEqual(JSON.parse(posts[0][1].body), { confirmed: true, manifest_digest: preview.manifest_digest });
  assert.match(documentRef.els["media-capability-packs-status"].textContent, /last self-test/);
});

test("self-test action runs only after pack status says installed", async () => {
  const documentRef = fixture(), posts = [];
  const installed = { ...preview, state: "installed" };
  mountCapabilityPacks({ documentRef, fetchImpl: async (url, options = {}) => {
    if (url === "/api/local/session") return response({ csrf: "csrf" });
    if (url.endsWith("/self-test")) { posts.push(url); return response({ state: "working", detail: "OCR test passed." }); }
    return response({ items: [installed] });
  } });
  await settle();
  await documentRef.els["media-capability-packs"].children[0].children[4].children[1].click();
  assert.deepEqual(posts, ["/api/capability-packs/eyes/self-test"]);
  assert.equal(documentRef.els["media-capability-packs-status"].textContent.includes("last self-test"), true);
});

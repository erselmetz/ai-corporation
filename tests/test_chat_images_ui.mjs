import assert from "node:assert/strict";
import test from "node:test";
import { mountChatImages } from "../app/webui/static/chat-images.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.children = []; this.listeners = {}; this.checked = false; this.disabled = false; this.hidden = false; this.value = ""; this.textContent = ""; this.files = []; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children = []; }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  querySelectorAll(selector) { return selector === "input[type=checkbox]:checked" ? this.children.flatMap(row => row.children.flatMap(label => label.children.filter(child => child.tag === "input" && child.checked))) : []; }
}

test("temporary images are unselected by default and require per-turn consent before exposing selected IDs", async () => {
  const ids = ["chat-image-list", "chat-image-file", "chat-image-upload", "chat-image-consent-panel", "chat-image-consent", "chat-image-ocr", "chat-image-status"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(id.includes("consent") || id.includes("ocr") ? "input" : "div")]));
  elements["chat-image-list"] = new Element("list");
  const documentRef = { getElementById: id => elements[id], createElement: tag => new Element(tag) };
  const calls = [];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url, options });
    if (url === "/api/local/session") return { ok: true, json: async () => ({ csrf: "token" }) };
    return { ok: true, json: async () => ({ items: [{ id: "image-1", source: "camera_capture", media_type: "image/jpeg", size_bytes: 24, expires_at: "later" }], provider_transfer_supported: true }) };
  };
  const manager = mountChatImages({ documentRef, fetchImpl, getConversation: () => "chat" });
  await manager.refresh();
  assert.deepEqual(manager.selectedIds(), []);
  const checkbox = elements["chat-image-list"].children[0].children[0].children[0];
  checkbox.checked = true;
  assert.deepEqual(manager.selectedIds(), ["image-1"]);
  assert.equal(manager.consented(), false);
  elements["chat-image-consent"].checked = true;
  assert.equal(manager.consented(), true);
  elements["chat-image-ocr"].checked = true;
  assert.equal(manager.wantsLocalOcr(), true);
  manager.clearConsent();
  assert.equal(manager.consented(), false);
  assert.equal(manager.wantsLocalOcr(), false);
  assert.equal(calls[0].url, "/api/chat/conversations/chat/images");
});

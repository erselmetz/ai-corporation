// Browser fixture: Python/CDP runner; original assertion behavior retained.
﻿import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { mountQuickStart } from "../app/webui/static/quick-start.mjs";

class Element {
  constructor() { this.hidden = false; this.disabled = false; this.textContent = ""; this.listeners = {}; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
}
const response = (body, status = 200) => ({ ok: status === 200, status, json: async () => body });
function setup({ status = { state: "unavailable" }, installed = true, size = null, confirm = false } = {}) {
  const elements = Object.fromEntries(["local-quick-start", "local-quick-start-state", "local-quick-start-action"].map(id => [id, new Element()]));
  const calls = [];
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    if (path === "/api/local/session") return response({ csrf: "csrf" });
    if (path.endsWith("/ollama/status")) return response(status);
    if (path.endsWith("/model-preview")) return size ? response(size) : response({}, 503);
    if (path.endsWith("/ollama/pull")) return { ok: true, body: { getReader: () => ({ read: async () => ({ done: true }) }) } };
    return response({});
  };
  const windowRef = { confirm: () => confirm, location: { assign() {} }, desktopBridge: {
    isOllamaInstalled: async () => installed,
    previewOllamaInstaller: async () => ({ ok: false, message: "No installer metadata" }),
    installOllama: async () => ({ ok: false }),
    onOllamaInstallerProgress: () => () => {},
  } };
  const controller = mountQuickStart({ documentRef: { getElementById: id => elements[id] }, windowRef, fetchImpl, autoInspect: false });
  return { controller, elements, calls };
}

test("shows exact stopped Ollama recovery state and Retry when installation exists", async () => {
  const ui = setup();
  await ui.controller.inspect();
  assert.equal(ui.elements["local-quick-start-state"].textContent, "Ollama is not running. Start it, then press Retry.");
  assert.equal(ui.elements["local-quick-start-action"].textContent, "Retry");
});

test("offers the existing confirmed installer only when Ollama is not installed", async () => {
  const ui = setup({ installed: false });
  await ui.controller.inspect();
  assert.match(ui.elements["local-quick-start-state"].textContent, /Ollama is not installed/);
  assert.equal(ui.elements["local-quick-start-action"].textContent, "Install Ollama");
});

test("shows registry-derived model size and keeps download behind explicit confirmation", async () => {
  const ui = setup({ status: { state: "available", model_installed: false, model_id: "llama3.2:3b" },
    size: { model_id: "llama3.2:3b", manifest_bytes: 1_500_000_000, manifest_digest: `sha256:${"a".repeat(64)}` } });
  await ui.controller.inspect();
  assert.match(ui.elements["local-quick-start-state"].textContent, /Download llama3.2:3b \(about 1.50 GB\)/);
  assert.equal(ui.elements["local-quick-start-action"].textContent, "Download llama3.2:3b");
  assert.equal(ui.calls.some(call => call.path.endsWith("/ollama/pull")), false);
});

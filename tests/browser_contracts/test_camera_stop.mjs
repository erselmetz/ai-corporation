// Browser fixture: Python/CDP runner; original assertion behavior retained.
﻿import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { mountCameraCapture } from "../app/webui/static/camera-capture.mjs";

class Element {
  constructor() { this.listeners = {}; this.disabled = true; this.value = "chat"; this.textContent = ""; }
  addEventListener(name, listener) { this.listeners[name] = listener; }
}

test("camera capture fails closed when the server reports emergency stop", async () => {
  const elements = { "chat-capture-camera": new Element(), "chat-camera-status": new Element(), "chat-conversation": new Element() };
  const documentRef = { getElementById: id => elements[id] };
  let cameraCalls = 0;
  const mediaDevices = { getUserMedia: async () => { cameraCalls += 1; throw new Error("must not start"); } };
  const fetchImpl = async url => url === "/api/local/session"
    ? { ok: true, json: async () => ({ permissions: ["chat:send", "camera:capture"] }) }
    : { ok: true, json: async () => ({ stopped: true }) };
  const ui = mountCameraCapture({ documentRef, fetchImpl, mediaDevices });
  await ui.refreshAuthorization();
  await ui.capture();
  assert.equal(cameraCalls, 0);
  assert.equal(elements["chat-capture-camera"].disabled, true);
  assert.match(elements["chat-camera-status"].textContent, /Emergency stop is active/);
});

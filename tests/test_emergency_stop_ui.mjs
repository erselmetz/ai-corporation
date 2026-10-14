import assert from "node:assert/strict";
import test from "node:test";
import { mountEmergencyStop } from "../app/webui/static/emergency-stop.mjs";

class Element {
  constructor(tag = "div") { this.tag = tag; this.listeners = {}; this.children = []; this.textContent = ""; this.disabled = false; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
}

test("safety panel stops, revokes grants, reports activity, and confirms resume", async () => {
  const elements = Object.fromEntries(["emergency-stop", "emergency-resume", "emergency-state",
    "emergency-grants", "emergency-permissions", "emergency-activity", "capability-microphone-support",
    "capability-microphone-activity", "capability-camera-support", "capability-camera-activity",
    "capability-screen-support", "capability-screen-activity", "capability-playback-support",
    "capability-playback-activity", "capability-vision-support", "capability-automation-support",
    "capability-automation-activity"].map(id => [id, new Element()]));
  const documentRef = { getElementById: id => elements[id], createElement: tag => new Element(tag) };
  const listeners = {};
  const events = [];
  const windowRef = {
    CustomEvent: class { constructor(type) { this.type = type; } },
    addEventListener(name, fn) { listeners[name] = fn; },
    dispatchEvent(event) { events.push(event.type); },
  };
  const requests = [];
  let stopped = false;
  const fetchImpl = async (path, options = {}) => {
    requests.push([path, options]);
    if (path === "/api/local/session") return { ok: true, json: async () => ({ csrf: "csrf" }) };
    if (path === "/api/local/emergency-stop" && !options.method) return { ok: true, json: async () => ({
      stopped, stopped_at: stopped ? "2035-01-01T00:00:00+00:00" : null,
      active_capabilities: ["chat:send"],
      session_grants: [{ grant_id: "grant-1", capability_id: "optional.inspect", scope_type: "principal",
        scope_id: "local-owner", status: "active", expires_at: "2035-01-01T00:01:00+00:00" }],
      capture: { microphone: "page-reported", local_playback: "page-reported", screen: "page-reported", camera: "page-reported" },
    }) };
    if (path === "/api/local/emergency-stop/stop") stopped = true;
    if (path === "/api/local/emergency-stop/resume") stopped = false;
    return { ok: true, json: async () => ({}) };
  };
  const ui = mountEmergencyStop({ documentRef, windowRef, fetchImpl, confirmImpl: () => true,
    browserFeatures: { microphone: true, camera: true, screen: false, playback: true, vision: true } });
  await ui.refresh();
  assert.match(elements["emergency-activity"].textContent, /Screen capture: unknown\. Camera: unknown/);
  assert.match(elements["capability-screen-support"].textContent, /Unsupported/);
  assert.match(elements["capability-automation-support"].textContent, /Unavailable/);
  assert.deepEqual(elements["emergency-permissions"].children.map(row => row.textContent), ["chat:send"]);
  assert.equal(elements["emergency-grants"].children.length, 1);
  assert.match(elements["emergency-grants"].children[0].children[0].textContent,
    /scope principal:local-owner; expires 2035-01-01T00:01:00\+00:00/);
  const revoke = elements["emergency-grants"].children[0].children[1];
  await revoke.listeners.click();
  assert.ok(requests.some(([path]) => path === "/api/capabilities/grants/grant-1/revoke"));

  await ui.stop();
  assert.equal(stopped, true);
  assert.ok(events.includes("ersel:emergency-stop"));
  const stopRequest = requests.find(([path]) => path === "/api/local/emergency-stop/stop");
  assert.equal(stopRequest[1].headers["X-Local-CSRF"], "csrf");

  await listeners["ersel:voice-activity"]({ detail: { microphone: "active", local_playback: "off", remote_request: "possibly-processing" } });
  assert.match(elements["emergency-activity"].textContent, /Microphone: active/);
  assert.equal(elements["capability-microphone-activity"].textContent, "Active");
  assert.match(elements["emergency-activity"].textContent, /request may still be running/);
  listeners["ersel:screen-capture-activity"]({ detail: { state: "denied" } });
  assert.equal(elements["capability-screen-activity"].textContent, "Denied");
  listeners["ersel:camera-activity"]({ detail: { state: "failed" } });
  assert.equal(elements["capability-camera-activity"].textContent, "Failed");

  await ui.resume();
  assert.equal(stopped, false);
  const resumeRequest = requests.find(([path]) => path === "/api/local/emergency-stop/resume");
  assert.equal(JSON.parse(resumeRequest[1].body).confirmed, true);
  assert.ok(events.includes("ersel:emergency-resumed"));
});

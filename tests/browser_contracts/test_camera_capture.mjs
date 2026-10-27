// Browser fixture: Python/CDP runner; original assertion behavior retained.
﻿import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { captureCameraFrame, mountCameraCapture } from "../app/webui/static/camera-capture.mjs";

function fakeCamera({ permissions = true } = {}) {
  let stopped = 0; let mediaOptions; let drawn = 0; let nativePrompts = 0;
  const track = { kind: "video", readyState: "live", stop() { stopped += 1; } };
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
  const mediaDevices = { getUserMedia: async options => { mediaOptions = options; return stream; } };
  const video = { videoWidth: 4000, videoHeight: 3000, play: async () => {}, srcObject: null };
  const canvas = { getContext: () => ({ drawImage: () => { drawn += 1; } }),
    toBlob: callback => callback(new Blob([new Uint8Array([1, 2])], { type: "image/jpeg" })) };
  const desktopBridge = { requestCamera: async () => { nativePrompts += 1; return permissions; } };
  return { mediaDevices, video, canvas, desktopBridge, get stopped() { return stopped; },
    get options() { return mediaOptions; }, get drawn() { return drawn; }, get nativePrompts() { return nativePrompts; } };
}

class Element {
  constructor() { this.listeners = {}; this.disabled = true; this.value = "conversation/1"; this.textContent = ""; }
  addEventListener(name, listener) { this.listeners[name] = listener; }
}

test("one owner-triggered camera frame requests video only, bounds pixels and stops the track", async () => {
  const fake = fakeCamera();
  const result = await captureCameraFrame({ mediaDevices: fake.mediaDevices,
    createVideo: () => fake.video, createCanvas: () => fake.canvas,
    desktopBridge: fake.desktopBridge, now: () => new Date("2026-10-14T12:00:00Z") });
  assert.equal(fake.nativePrompts, 1);
  assert.deepEqual(fake.options, { video: true, audio: false });
  assert.ok(fake.canvas.width * fake.canvas.height <= 8_000_000);
  assert.equal(fake.drawn, 1); assert.equal(fake.stopped, 1);
  assert.equal(fake.video.srcObject, null);
  assert.equal(result.status, "captured"); assert.equal(result.media_type, "image/jpeg");
  assert.equal(result.captured_at, "2026-10-14T12:00:00.000Z");
});

test("camera denial, unsupported input and emergency stop never retain a frame", async () => {
  const denied = fakeCamera({ permissions: false });
  assert.equal((await captureCameraFrame({ mediaDevices: denied.mediaDevices, desktopBridge: denied.desktopBridge })).status, "denied");
  assert.equal(denied.options, undefined);
  assert.equal((await captureCameraFrame({ mediaDevices: {} })).status, "unavailable");
  let blocked = true;
  assert.equal((await captureCameraFrame({ mediaDevices: denied.mediaDevices, blocked: () => blocked,
    desktopBridge: denied.desktopBridge })).status, "stopped");
  blocked = false;
});

test("camera UI requires both scoped permissions and attaches only one frame with CSRF", async () => {
  const listeners = {}; const events = {};
  const elements = { "chat-capture-camera": new Element(), "chat-camera-status": new Element(), "chat-conversation": new Element() };
  const documentRef = { getElementById: id => elements[id], createElement: tag => tag === "video"
    ? { videoWidth: 2, videoHeight: 1, play: async () => {}, srcObject: null }
    : { getContext: () => ({ drawImage() {} }), toBlob: callback => callback(new Blob([new Uint8Array([1])], { type: "image/jpeg" })) } };
  const windowRef = { CustomEvent: class { constructor(type, init) { this.type = type; Object.assign(this, init); } },
    dispatchEvent: event => { events[event.type] = event; }, addEventListener: (name, fn) => { listeners[name] = fn; } };
  const track = { kind: "video", readyState: "live", stop() {} };
  const mediaDevices = { getUserMedia: async options => { assert.deepEqual(options, { video: true, audio: false }); return { getTracks: () => [track], getVideoTracks: () => [track] }; } };
  const requests = [];
  const fetchImpl = async (url, options = {}) => { requests.push({ url, options });
    if (url === "/api/local/session") return { ok: true, json: async () => ({ permissions: ["chat:send", "camera:capture"], csrf: "csrf" }) };
    return { ok: true, json: async () => ({ image: { id: "frame" } }) }; };
  const previous = globalThis.document; globalThis.document = documentRef;
  const ui = mountCameraCapture({ documentRef, windowRef, fetchImpl, mediaDevices });
  await ui.refreshAuthorization(); assert.equal(elements["chat-capture-camera"].disabled, false);
  await ui.capture(); globalThis.document = previous;
  const call = requests.at(-1);
  assert.equal(call.url, "/api/chat/conversations/conversation%2F1/camera-captures");
  assert.equal(call.options.headers["X-Local-CSRF"], "csrf");
  assert.deepEqual(Object.keys(JSON.parse(call.options.body)).sort(), ["captured_at", "data_base64", "media_type"]);
  assert.ok(events["ersel:camera-activity"]); assert.ok(events["ersel:chat-images-changed"]);
});

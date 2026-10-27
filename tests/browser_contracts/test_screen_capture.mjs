// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { captureScreenFrame, mountScreenCapture } from "../app/webui/static/screen-capture.mjs";

function harness({ width = 12000, height = 6000, displaySurface = "monitor",
  blobBytes = 16, blocked = () => false, getDisplayMedia } = {}) {
  let stopped = 0;
  let drawn = null;
  let options = null;
  let encodeCalls = 0;
  const track = {
    readyState: "live",
    getSettings: () => ({ width, height, displaySurface }),
    stop: () => { stopped += 1; },
  };
  const stream = { getVideoTracks: () => [track], getTracks: () => [track] };
  const mediaDevices = {
    getDisplayMedia: async (value) => {
      options = value;
      if (getDisplayMedia) return getDisplayMedia(value, stream);
      return stream;
    },
  };
  const video = { videoWidth: width, videoHeight: height, play: async () => {}, srcObject: null };
  const canvas = {
    getContext: () => ({ drawImage: (_video, x, y, w, h) => { drawn = { x, y, width: w, height: h }; } }),
    toBlob: (callback, type, quality) => {
      encodeCalls += 1;
      callback(new Blob([new Uint8Array(blobBytes)], { type: `${type};q=${quality}` }));
    },
  };
  return {
    run: () => captureScreenFrame({ mediaDevices, createVideo: () => video,
      createCanvas: () => canvas, now: () => new Date("2026-10-14T12:00:00.000Z"), blocked }),
    get stopped() { return stopped; },
    get drawn() { return drawn; },
    get options() { return options; },
    get encodeCalls() { return encodeCalls; },
  };
}

test("captures one bounded frame with user-selected surface and no audio, then stops all tracks", async () => {
  const fake = harness();
  const result = await fake.run();
  assert.deepEqual(fake.options, { video: true, audio: false });
  assert.ok(fake.drawn.width * fake.drawn.height <= 8_000_000);
  assert.ok(fake.drawn.width <= 4096 && fake.drawn.height <= 4096);
  assert.equal(fake.stopped, 1);
  assert.equal(result.status, "captured");
  assert.equal(result.media_type, "image/jpeg");
  assert.equal(result.display_surface, "monitor");
  assert.equal(result.captured_at, "2026-10-14T12:00:00.000Z");
  assert.equal(result.data_base64, "AAAAAAAAAAAAAAAAAAAAAA==");
});

test("unsupported surface types and oversized output fail closed and stop tracks", async () => {
  const unknown = harness({ displaySurface: "unknown" });
  assert.equal((await unknown.run()).status, "unavailable");
  assert.equal(unknown.stopped, 1);
  const oversized = harness({ width: 100, height: 100, blobBytes: 2 * 1024 * 1024 + 1 });
  assert.equal((await oversized.run()).status, "unavailable");
  assert.equal(oversized.encodeCalls, 5);
  assert.equal(oversized.stopped, 1);
});

test("permission cancellation, emergency stop, and unsupported browsers do not retain frames", async () => {
  const denied = harness({ getDisplayMedia: async () => {
    const error = new Error("private system detail"); error.name = "NotAllowedError"; throw error;
  } });
  const deniedResult = await denied.run();
  assert.equal(deniedResult.status, "denied");
  assert.doesNotMatch(deniedResult.message, /private system detail/);

  let stop = false;
  const stopped = harness({ blocked: () => stop, getDisplayMedia: async (_options, stream) => {
    stop = true;
    return stream;
  } });
  assert.equal((await stopped.run()).status, "stopped");
  assert.equal(stopped.stopped, 1);

  assert.equal((await captureScreenFrame({ mediaDevices: {} })).status, "unavailable");
});

test("UI requires both chat permissions and sends only the bounded capture request fields with CSRF", async () => {
  const listeners = {};
  const events = {};
  const elements = {
    "chat-capture-screen": { disabled: true, addEventListener: (name, fn) => { listeners[name] = fn; } },
    "chat-capture-status": { textContent: "" },
    "chat-conversation": { value: "conversation/1", addEventListener: (name, fn) => { listeners[`conversation:${name}`] = fn; } },
  };
  const documentRef = {
    getElementById: id => elements[id],
    createElement: tag => tag === "video"
      ? { videoWidth: 2, videoHeight: 1, play: async () => {}, srcObject: null }
      : { width: 0, height: 0, getContext: () => ({ drawImage() {} }),
          toBlob: callback => callback(new Blob([new Uint8Array([1, 2])], { type: "image/jpeg" })) },
  };
  const windowRef = {
    CustomEvent: class { constructor(type, init) { this.type = type; Object.assign(this, init); } },
    dispatchEvent: event => { events[event.type] = event; },
    addEventListener: (name, fn) => { listeners[`window:${name}`] = fn; },
  };
  const track = { readyState: "live", getSettings: () => ({ displaySurface: "window" }), stop() {} };
  const mediaDevices = { getDisplayMedia: async options => {
    assert.deepEqual(options, { video: true, audio: false });
    return { getVideoTracks: () => [track], getTracks: () => [track] };
  } };
  const requests = [];
  const fetchImpl = async (url, options = {}) => {
    requests.push({ url, options });
    if (url === "/api/local/session") return { ok: true, json: async () => ({ permissions: ["chat:send", "screen:capture"], csrf: "csrf-token" }) };
    return { ok: true, json: async () => ({ image: { id: "image-1" } }) };
  };
  const previousDocument = globalThis.document;
  globalThis.document = documentRef;
  const ui = mountScreenCapture({ documentRef, windowRef, fetchImpl, mediaDevices });
  await ui.refreshAuthorization();
  assert.equal(elements["chat-capture-screen"].disabled, false);
  await ui.capture();
  globalThis.document = previousDocument;
  const upload = requests.at(-1);
  assert.equal(upload.url, "/api/chat/conversations/conversation%2F1/screen-captures");
  assert.equal(upload.options.headers["X-Local-CSRF"], "csrf-token");
  assert.deepEqual(Object.keys(JSON.parse(upload.options.body)).sort(),
    ["captured_at", "data_base64", "display_surface", "media_type"]);
  assert.match(elements["chat-capture-status"].textContent, /Captured window 2x1/);
  assert.ok(events["ersel:screen-capture-activity"]);
});

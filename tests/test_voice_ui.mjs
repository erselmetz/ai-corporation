import assert from "node:assert/strict";
import test from "node:test";
import { encodePcmWav, mountVoiceControls } from "../app/webui/static/voice.mjs";

class Element {
  constructor() { this.listeners = {}; this.value = ""; this.checked = false; this.disabled = false; this.hidden = false; this.textContent = ""; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
}

function harness({ fetchImpl, windowRef, confirmImpl = () => true, setTimeoutImpl, clearTimeoutImpl } = {}) {
  const ids = ["voice-mode", "voice-language", "voice-start", "voice-stop", "voice-transcribe",
    "voice-install-local", "voice-cloud-consent", "voice-budget-form", "voice-budget-cents",
    "voice-budget-save", "voice-budget-state", "voice-state", "voice-stop-playback"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
  elements["voice-mode"].value = "local";
  elements["voice-language"].value = "en-US";
  elements["voice-budget-cents"].value = "5";
  const documentRef = { getElementById: id => elements[id], createElement: () => new Element() };
  const transcripts = [];
  const controller = mountVoiceControls({ documentRef, windowRef, fetchImpl, confirmImpl, setTimeoutImpl, clearTimeoutImpl,
    onTranscript: (text, source) => transcripts.push({ text, source }), canUseChat: () => true });
  return { elements, controller, transcripts };
}

test("WAV encoder fixes the transcription input to mono 16 kHz PCM and 10 seconds", async () => {
  const wav = encodePcmWav(new Float32Array(48_000), 48_000);
  assert.equal(wav.type, "audio/wav");
  assert.equal(wav.size, 32_044);
  const header = new DataView(await wav.arrayBuffer());
  assert.equal(header.getUint32(24, true), 16_000);
  assert.equal(header.getUint16(22, true), 1);
  assert.equal(header.getUint16(34, true), 16);
  assert.equal(header.getUint32(40, true), 32_000);
  assert.throws(() => encodePcmWav(new Float32Array(10), 8_000), /format is unavailable/);
});

test("local mode requires processLocally and never falls back to cloud", async () => {
  let activeRecognition;
  class Recognition {
    static async available(options) { assert.deepEqual(options, { langs: ["en-US"], processLocally: true }); return "available"; }
    static async install() { return true; }
    processLocally = false;
    constructor() { activeRecognition = this; }
    start() { this.started = true; }
    abort() { this.aborted = true; this.onend?.(); }
  }
  const requests = [];
  const ui = harness({ windowRef: { SpeechRecognition: Recognition, desktopBridge: { requestMicrophone: async () => true } },
    fetchImpl: async (path) => { requests.push(path); return { ok: true, json: async () => ({ cloud_budget: { configured: false } }) }; } });
  await ui.elements["voice-start"].listeners.click();
  assert.equal(activeRecognition.processLocally, true);
  activeRecognition.onresult({ results: [[{ transcript: "hello" }]] });
  assert.deepEqual(ui.transcripts, [{ text: "hello", source: "local" }]);
  assert.equal(requests.includes("/api/local/voice/transcribe"), false);
  await ui.elements["voice-stop"].listeners.click();
  assert.equal(activeRecognition.aborted, true);
  activeRecognition.onresult({ results: [[{ transcript: "late result after stop" }]] });
  assert.deepEqual(ui.transcripts, [{ text: "hello", source: "local" }]);
  assert.match(ui.elements["voice-state"].textContent, /stopped/i);
});

test("local microphone capture ends after its ten-second limit", async () => {
  let activeRecognition;
  let onLimit;
  class Recognition {
    static async available() { return "available"; }
    static async install() { return true; }
    processLocally = false;
    constructor() { activeRecognition = this; }
    start() {}
    abort() { this.aborted = true; this.onend?.(); }
  }
  const ui = harness({ windowRef: { SpeechRecognition: Recognition },
    setTimeoutImpl(callback, duration) { assert.equal(duration, 10_000); onLimit = callback; return 1; },
    clearTimeoutImpl() {} });
  await ui.elements["voice-start"].listeners.click();
  onLimit();
  assert.equal(activeRecognition.aborted, true);
  assert.match(ui.elements["voice-state"].textContent, /10-second local capture limit/);
  assert.deepEqual(ui.transcripts, []);
});

test("stopping during local capability detection cancels startup", async () => {
  let resolveAvailability;
  let started = false;
  class Recognition {
    static available() { return new Promise(resolve => { resolveAvailability = resolve; }); }
    static async install() { return true; }
    processLocally = false;
    start() { started = true; }
  }
  const ui = harness({ windowRef: { SpeechRecognition: Recognition } });
  const startup = ui.elements["voice-start"].listeners.click();
  await Promise.resolve();
  await ui.elements["voice-stop"].listeners.click();
  resolveAvailability("available");
  await startup;
  assert.equal(started, false);
  assert.match(ui.elements["voice-state"].textContent, /startup stopped/i);
});

test("emergency stop aborts local capture and blocks a new voice start until resumed", async () => {
  let recognition;
  let starts = 0;
  const listeners = {};
  class Recognition {
    static async available() { return "available"; }
    static async install() { return true; }
    processLocally = false;
    constructor() { recognition = this; }
    start() { starts++; }
    abort() { this.aborted = true; this.onend?.(); }
  }
  const windowRef = {
    SpeechRecognition: Recognition,
    addEventListener(name, callback) { listeners[name] = callback; },
    dispatchEvent() {},
  };
  const ui = harness({ windowRef,
    fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: {} }) }) });
  await ui.elements["voice-start"].listeners.click();
  assert.equal(starts, 1);
  listeners["ersel:emergency-stop"]();
  assert.equal(recognition.aborted, true);
  await ui.elements["voice-start"].listeners.click();
  assert.equal(starts, 1);
  listeners["ersel:emergency-resumed"]();
  await ui.elements["voice-start"].listeners.click();
  assert.equal(starts, 2);
});

test("sensitive local transcript is discarded before it enters chat", async () => {
  let recognition;
  class Recognition {
    static async available() { return "available"; }
    static async install() { return true; }
    processLocally = false;
    constructor() { recognition = this; }
    start() {}
    abort() { this.onend?.(); }
  }
  const ui = harness({ windowRef: { SpeechRecognition: Recognition }, fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: {} }) }) });
  await ui.elements["voice-start"].listeners.click();
  recognition.onresult({ results: [[{ transcript: `AIza${"a".repeat(35)}` }]] });
  assert.deepEqual(ui.transcripts, []);
  assert.match(ui.elements["voice-state"].textContent, /discarded/);
});

test("local voice denial and unsupported language fail closed without cloud fallback", async () => {
  let started = false;
  class DeniedRecognition {
    static async available() { return "available"; }
    static async install() { return true; }
    processLocally = false;
    start() { started = true; }
  }
  const denied = harness({ windowRef: {
    SpeechRecognition: DeniedRecognition,
    desktopBridge: { requestMicrophone: async () => false },
  }, fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: { configured: false } }) }) });
  await denied.elements["voice-start"].listeners.click();
  assert.equal(started, false);
  assert.match(denied.elements["voice-state"].textContent, /not approved/);

  class UnsupportedRecognition {
    static async available() { return "unavailable"; }
    static async install() { return false; }
    start() { started = true; }
  }
  const unsupported = harness({ windowRef: { SpeechRecognition: UnsupportedRecognition },
    fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: { configured: false } }) }) });
  await unsupported.elements["voice-start"].listeners.click();
  assert.equal(started, false);
  assert.match(unsupported.elements["voice-state"].textContent, /No cloud fallback/);
  assert.equal(unsupported.elements["voice-install-local"].hidden, true);
});

test("downloadable local language packs require a separate owner action", async () => {
  let installs = 0;
  let starts = 0;
  class Recognition {
    static async available() { return "downloadable"; }
    static async install(options) { installs += 1; assert.deepEqual(options, { langs: ["en-US"], processLocally: true }); return true; }
    processLocally = false;
    start() { starts += 1; }
  }
  const ui = harness({ windowRef: { SpeechRecognition: Recognition },
    fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: { configured: false } }) }) });
  await ui.elements["voice-start"].listeners.click();
  assert.equal(starts, 0);
  assert.equal(installs, 0);
  assert.equal(ui.elements["voice-install-local"].hidden, false);
  await ui.elements["voice-install-local"].listeners.click();
  assert.equal(installs, 1);
  assert.equal(starts, 0);
  assert.equal(ui.elements["voice-install-local"].hidden, true);
});

test("cloud audio requires one-use consent and places only the reviewed transcript in chat", async () => {
  const paths = [];
  let optionsUsed;
  const budget = { configured: true, ceiling_cents: 5, reserved_cents: 0, remaining_cents: 5 };
  const fetchImpl = async (path, options = {}) => {
    paths.push(path);
    if (path === "/api/local/voice") return { ok: true, json: async () => ({ cloud_budget: budget }) };
    if (path === "/api/local/session") return { ok: true, json: async () => ({ csrf: "csrf" }) };
    if (path === "/api/local/voice/transcribe") {
      optionsUsed = options;
      return { ok: true, json: async () => ({ transcript: "hello cloud", remaining_cents: 4 }) };
    }
    throw new Error(`unexpected request ${path}`);
  };
  class AudioContext {
    constructor() { this.sampleRate = 16_000; this.state = "running"; this.destination = {}; AudioContext.last = this; }
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    createScriptProcessor() { return this.processor = { connect() {}, disconnect() {}, onaudioprocess: null }; }
    createGain() { return { gain: {}, connect() {}, disconnect() {} }; }
    async close() { this.state = "closed"; }
  }
  const tracks = [{ stopped: false, stop() { this.stopped = true; } }];
  const windowRef = { AudioContext, navigator: { mediaDevices: { async getUserMedia(options) { assert.equal(options.video, false); return { getTracks: () => tracks }; } } } };
  const ui = harness({ windowRef, fetchImpl });
  ui.elements["voice-mode"].value = "cloud";
  await ui.elements["voice-start"].listeners.click();
  const samples = new Float32Array(160_000);
  AudioContext.last.processor.onaudioprocess({ inputBuffer: { getChannelData: () => samples } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.elements["voice-transcribe"].hidden, false);
  assert.equal(paths.includes("/api/local/voice/transcribe"), false);
  assert.ok(tracks.every(track => track.stopped));
  await ui.elements["voice-transcribe"].listeners.click();
  assert.match(ui.elements["voice-state"].textContent, /Consent to send/);
  assert.equal(paths.includes("/api/local/voice/transcribe"), false);
  ui.elements["voice-cloud-consent"].checked = true;
  await ui.elements["voice-transcribe"].listeners.click();
  assert.equal(paths.includes("/api/local/voice/transcribe"), true);
  assert.equal(optionsUsed.headers["X-Local-CSRF"], "csrf");
  assert.equal(optionsUsed.headers["X-Cloud-Consent"], "true");
  assert.equal(optionsUsed.body.type, "audio/wav");
  assert.deepEqual(ui.transcripts, [{ text: "hello cloud", source: "gemini" }]);
  assert.equal(ui.elements["voice-cloud-consent"].checked, false);
  assert.match(ui.elements["voice-state"].textContent, /not sent to chat or saved/);
});

test("stopping a cloud transcription stops local waiting and records an unknown provider outcome", async () => {
  const paths = [];
  const budget = { configured: true, ceiling_cents: 2, reserved_cents: 0, remaining_cents: 2 };
  const fetchImpl = async (path, options = {}) => {
    paths.push(path);
    if (path === "/api/local/voice") return { ok: true, json: async () => ({ cloud_budget: budget }) };
    if (path === "/api/local/session") return { ok: true, json: async () => ({ csrf: "csrf" }) };
    if (path === "/api/local/voice/transcribe") return new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
    });
    throw new Error(`unexpected request ${path}`);
  };
  class AudioContext {
    constructor() { this.sampleRate = 16_000; this.state = "running"; this.destination = {}; AudioContext.last = this; }
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    createScriptProcessor() { return this.processor = { connect() {}, disconnect() {}, onaudioprocess: null }; }
    createGain() { return { gain: {}, connect() {}, disconnect() {} }; }
    async close() { this.state = "closed"; }
  }
  const tracks = [{ stop() {} }];
  const ui = harness({ windowRef: { AudioContext,
    navigator: { mediaDevices: { async getUserMedia() { return { getTracks: () => tracks }; } } } }, fetchImpl });
  ui.elements["voice-mode"].value = "cloud";
  await ui.elements["voice-start"].listeners.click();
  AudioContext.last.processor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(160_000) } });
  await new Promise(resolve => setImmediate(resolve));
  ui.elements["voice-cloud-consent"].checked = true;
  const pending = ui.elements["voice-transcribe"].listeners.click();
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(paths.includes("/api/local/voice/transcribe"));
  await ui.elements["voice-stop"].listeners.click();
  await pending;
  assert.deepEqual(ui.transcripts, []);
  assert.match(ui.elements["voice-state"].textContent, /outcome and charge are unknown.*No retry/);
});

test("stopping at the capture-finalization boundary discards audio instead of making it ready to send", async () => {
  const budget = { configured: true, ceiling_cents: 2, reserved_cents: 0, remaining_cents: 2 };
  const requests = [];
  const fetchImpl = async path => {
    requests.push(path);
    if (path === "/api/local/voice") return { ok: true, json: async () => ({ cloud_budget: budget }) };
    return { ok: true, json: async () => ({ csrf: "csrf" }) };
  };
  let releaseClose;
  class AudioContext {
    constructor() { this.sampleRate = 16_000; this.state = "running"; this.destination = {}; AudioContext.last = this; }
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    createScriptProcessor() { return this.processor = { connect() {}, disconnect() {}, onaudioprocess: null }; }
    createGain() { return { gain: {}, connect() {}, disconnect() {} }; }
    close() { this.state = "closed"; return new Promise(resolve => { releaseClose = resolve; }); }
  }
  const ui = harness({ windowRef: { AudioContext,
    navigator: { mediaDevices: { async getUserMedia() { return { getTracks: () => [{ stop() {} }] }; } } } }, fetchImpl });
  await ui.controller.loadBudget();
  ui.elements["voice-mode"].value = "cloud";
  await ui.elements["voice-start"].listeners.click();
  AudioContext.last.processor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(160_000) } });
  await ui.elements["voice-stop"].listeners.click();
  releaseClose();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.elements["voice-transcribe"].hidden, true);
  assert.match(ui.elements["voice-state"].textContent, /stopped and discarded/);
  assert.equal(requests.includes("/api/local/voice/transcribe"), false);
});

test("reply audio uses an installed local voice and can be stopped", () => {
  let spoken;
  let cancelled = 0;
  class Utterance { constructor(text) { this.text = text; } }
  const speechSynthesis = {
    getVoices: () => [{ localService: true, name: "Local voice" }],
    speak(item) { spoken = item; },
    cancel() { cancelled += 1; },
  };
  const ui = harness({ windowRef: { speechSynthesis, SpeechSynthesisUtterance: Utterance },
    fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: { configured: false } }) }) });
  assert.equal(ui.controller.speak("A local answer"), true);
  assert.equal(spoken.text, "A local answer");
  ui.elements["voice-stop-playback"].listeners.click();
  assert.equal(cancelled, 2);
  assert.match(ui.elements["voice-state"].textContent, /playback stopped/);
});

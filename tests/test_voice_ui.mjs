import assert from "node:assert/strict";
import test from "node:test";
import { encodePcmWav, mountVoiceControls } from "../app/webui/static/voice.mjs";

class Element {
  constructor() { this.listeners = {}; this.value = ""; this.checked = false; this.disabled = false; this.hidden = false; this.textContent = ""; this.children = []; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  replaceChildren(...items) { this.children = items; }
  append(...items) { this.children.push(...items); }
}

function harness({ fetchImpl, windowRef, confirmImpl = () => true, setTimeoutImpl, clearTimeoutImpl,
  setIntervalImpl = () => 1, clearIntervalImpl = () => {}, nowImpl = Date.now } = {}) {
  const ids = ["voice-mode", "voice-language", "voice-start", "voice-stop", "voice-transcribe",
    "voice-install-local", "voice-cloud-consent", "voice-budget-form", "voice-budget-cents",
    "voice-budget-save", "voice-budget-state", "voice-state", "voice-stop-playback",
    "voice-local-model", "voice-local-model-state", "voice-cloud-consent-panel",
    "voice-output-language", "voice-output-voice", "voice-output-state"];
  const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
  elements["voice-mode"].value = "local";
  elements["voice-language"].value = "en-US";
  elements["voice-budget-cents"].value = "5";
  elements["voice-output-language"].value = "en-US";
  const documentRef = { getElementById: id => elements[id], createElement: () => new Element() };
  const transcripts = [];
  const controller = mountVoiceControls({ documentRef, windowRef, fetchImpl, confirmImpl, setTimeoutImpl, clearTimeoutImpl, setIntervalImpl, clearIntervalImpl, nowImpl,
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
    start() { this.started = true; this.onstart?.(); }
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
    start() { this.onstart?.(); }
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

test("microphone activity exposes permission, capture duration, and transcription state", async () => {
  let activeRecognition;
  let tick;
  let cleared = false;
  let now = 1_000;
  const events = [];
  class Recognition {
    static async available() { return "available"; }
    static async install() { return true; }
    processLocally = false;
    constructor() { activeRecognition = this; }
    start() {}
    abort() { this.onend?.(); }
  }
  class CustomEvent { constructor(type, options) { this.type = type; this.detail = options.detail; } }
  const windowRef = { SpeechRecognition: Recognition, CustomEvent, dispatchEvent: event => events.push(event) };
  const ui = harness({ windowRef, nowImpl: () => now,
    setIntervalImpl(callback, duration) { assert.equal(duration, 1000); tick = callback; return 7; },
    clearIntervalImpl(id) { assert.equal(id, 7); cleared = true; } });
  await ui.elements["voice-start"].listeners.click();
  assert.equal(events.at(-1).detail.voice_stage, "local-capture-pending");
  assert.equal(events.at(-1).detail.microphone_permission, "requesting");
  assert.equal(events.at(-1).detail.capture_limit_seconds, 10);
  activeRecognition.onstart();
  assert.equal(events.at(-1).detail.voice_stage, "local-capture");
  assert.equal(events.at(-1).detail.microphone_permission, "granted");
  now = 4_500;
  tick();
  assert.equal(events.at(-1).detail.capture_elapsed_seconds, 3);
  activeRecognition.onresult({ results: [[{ transcript: "review this" }]] });
  await ui.elements["voice-stop"].listeners.click();
  assert.deepEqual(ui.transcripts, [{ text: "review this", source: "local" }]);
  assert.equal(events.at(-1).detail.voice_stage, "idle");
  assert.equal(cleared, true);
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

test("clearing a chat cancels pending microphone startup before capture can begin", async () => {
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
  ui.controller.clear();
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
    start() { this.onstart?.(); }
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

test("browser-managed downloadable speech languages require a separate owner action", async () => {
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
  assert.match(ui.elements["voice-state"].textContent, /browser-managed speech language pack/);
  await ui.elements["voice-install-local"].listeners.click();
  assert.equal(installs, 1);
  assert.equal(starts, 0);
  assert.equal(ui.elements["voice-install-local"].hidden, true);
  assert.match(ui.elements["voice-state"].textContent, /Browser speech language pack installed/);
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

test("optional local model is selected explicitly, processes audio locally, and inserts a reviewable draft", async () => {
  const paths = [];
  let requestOptions;
  const localStatus = { runtime: "available", selected_model: null, available_models: ["tiny-en"], state: "model-not-selected" };
  const fetchImpl = async (path, options = {}) => {
    paths.push(path);
    if (path === "/api/local/voice") return { ok: true, json: async () => ({
      cloud_budget: { configured: false, ceiling_cents: 0, remaining_cents: 0 }, local_speech: localStatus,
    }) };
    if (path === "/api/local/session") return { ok: true, json: async () => ({ csrf: "csrf" }) };
    if (path === "/api/local/voice/local-model") {
      requestOptions = options;
      localStatus.selected_model = "tiny-en"; localStatus.state = "ready";
      return { ok: true, json: async () => ({ ...localStatus }) };
    }
    if (path.startsWith("/api/local/voice/transcribe-local?")) {
      requestOptions = options;
      return { ok: true, json: async () => ({ transcript: "hello local model", backend: "local", language: "en-US" }) };
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
  const tracks = [{ stop() { this.stopped = true; } }];
  const ui = harness({ windowRef: { AudioContext, navigator: { mediaDevices: {
    async getUserMedia() { return { getTracks: () => tracks }; },
  } } }, fetchImpl });
  await ui.controller.loadBudget();
  assert.deepEqual(ui.elements["voice-local-model"].children.map(option => option.value), ["", "tiny-en"]);
  ui.elements["voice-local-model"].value = "tiny-en";
  await ui.elements["voice-local-model"].listeners.change();
  assert.equal(requestOptions.headers["X-Local-CSRF"], "csrf");
  assert.equal(JSON.parse(requestOptions.body).model_id, "tiny-en");
  ui.elements["voice-mode"].value = "local-model";
  ui.elements["voice-mode"].listeners.change();
  assert.equal(ui.elements["voice-cloud-consent-panel"].hidden, true);
  assert.equal(ui.elements["voice-start"].disabled, false);
  await ui.elements["voice-start"].listeners.click();
  AudioContext.last.processor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(160_000) } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.elements["voice-transcribe"].hidden, false);
  assert.equal(ui.elements["voice-transcribe"].textContent, "Transcribe locally");
  await ui.elements["voice-transcribe"].listeners.click();
  assert.ok(paths.some(path => path.startsWith("/api/local/voice/transcribe-local?language=en-US")));
  assert.equal(requestOptions.headers["X-Cloud-Consent"], undefined);
  assert.equal(requestOptions.body.type, "audio/wav");
  assert.deepEqual(ui.transcripts, [{ text: "hello local model", source: "local-model" }]);
  assert.match(ui.elements["voice-state"].textContent, /review/);
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

test("reply audio uses an installed local voice and can be stopped", async () => {
  let spoken;
  let cancelled = 0;
  class Utterance { constructor(text) { this.text = text; } }
  const speechSynthesis = {
    getVoices: () => [{ localService: true, voiceURI: "local-voice", name: "Local voice", lang: "en-US" }],
    addEventListener() {},
    speak(item) { spoken = item; },
    cancel() { cancelled += 1; },
  };
  const ui = harness({ windowRef: { speechSynthesis, SpeechSynthesisUtterance: Utterance },
    fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: { configured: false } }) }) });
  assert.match(ui.elements["voice-output-state"].textContent, /Choose an installed local voice/);
  ui.elements["voice-output-voice"].value = "local-voice";
  await ui.elements["voice-output-voice"].listeners.change();
  assert.equal(ui.controller.speak("A local answer"), true);
  assert.equal(spoken.text, "A local answer");
  assert.equal(spoken.voice.voiceURI, "local-voice");
  assert.equal(spoken.lang, "en-US");
  assert.equal(ui.controller.speak("A second reviewed reply"), true);
  assert.match(ui.elements["voice-output-state"].textContent, /1 more replies queued/);
  ui.elements["voice-stop-playback"].listeners.click();
  assert.equal(cancelled, 1);
  assert.match(ui.elements["voice-output-state"].textContent, /stopped.*queued reply text was cleared/i);
  assert.match(ui.elements["voice-state"].textContent, /playback stopped/);
});

test("missing local speech output is visible and does not try an online fallback", () => {
  const ui = harness({ windowRef: {}, fetchImpl: async () => ({ ok: true, json: async () => ({ cloud_budget: {} }) }) });
  assert.match(ui.elements["voice-output-state"].textContent, /unavailable.*no online fallback/i);
  assert.equal(ui.elements["voice-output-voice"].disabled, true);
  assert.equal(ui.controller.speak("A reviewed reply"), false);
  assert.match(ui.elements["voice-state"].textContent, /unavailable/i);
});

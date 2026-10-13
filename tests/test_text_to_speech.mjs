import assert from "node:assert/strict";
import test from "node:test";
import { createOfflineTextToSpeechProvider } from "../app/webui/static/text-to-speech.mjs";

class Utterance {
  constructor(text) { this.text = text; }
}

function harness(voices = []) {
  const spoken = [];
  let cancelled = 0;
  const synthesis = {
    speaking: false,
    pending: false,
    getVoices: () => voices,
    speak(utterance) { spoken.push(utterance); this.speaking = true; },
    cancel() { cancelled++; this.speaking = false; this.pending = false; },
  };
  return {
    provider: createOfflineTextToSpeechProvider({ speechSynthesis: synthesis, SpeechSynthesisUtterance: Utterance }),
    spoken,
    cancelled: () => cancelled,
  };
}

test("provider reports unavailable when device-local speech is absent", () => {
  const provider = createOfflineTextToSpeechProvider({});
  assert.deepEqual(provider.status(), {
    backend: "local", state: "unavailable", selected_voice: null, language: null, voices: [],
  });
  assert.throws(() => provider.speak("hello"), /unavailable/);
});

test("only explicitly local voices are listed and selected for output", () => {
  const { provider, spoken } = harness([
    { localService: true, voiceURI: "device-en", name: "Device English", lang: "en-US" },
    { localService: false, voiceURI: "remote", name: "Remote voice", lang: "en-US" },
  ]);
  assert.equal(provider.status().state, "voice-not-selected");
  assert.deepEqual(provider.voices().map(voice => voice.voiceURI), ["device-en"]);
  assert.throws(() => provider.configure({ voiceURI: "remote", language: "en-US" }), /available local speech voice/);
  const configured = provider.configure({ voiceURI: "device-en", language: "en-US" });
  assert.equal(configured.backend, "local");
  assert.equal(configured.state, "ready");
  assert.equal(configured.selected_voice, "device-en");
  provider.speak("Reviewed reply");
  assert.equal(spoken[0].text, "Reviewed reply");
  assert.equal(spoken[0].voice.voiceURI, "device-en");
  assert.equal(spoken[0].lang, "en-US");
  assert.equal(provider.status().state, "speaking");
});

test("output validates language and bounded text rather than truncating the reply", () => {
  const { provider } = harness([{ localService: true, voiceURI: "device-en", name: "Device English", lang: "en-US" }]);
  provider.configure({ voiceURI: "device-en", language: "en-US" });
  assert.throws(() => provider.configure({ voiceURI: "device-en", language: "en-us" }), /valid speech output language/);
  assert.throws(() => provider.speak("x".repeat(8193)), /8192 UTF-8 bytes/);
  assert.throws(() => provider.speak("  "), /8192 UTF-8 bytes/);
});

test("voice disappearing is reported and stop cancels only local playback", () => {
  const localVoice = { localService: true, voiceURI: "device-en", name: "Device English", lang: "en-US" };
  const { provider, cancelled } = harness([localVoice]);
  provider.configure({ voiceURI: "device-en", language: "en-US" });
  provider.speak("hello");
  assert.equal(provider.stop().state, "ready");
  assert.equal(cancelled(), 2);
  localVoice.localService = false;
  const status = provider.status();
  assert.equal(status.state, "unavailable");
  assert.equal(status.selected_voice, "device-en");
});

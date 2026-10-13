const LANGUAGE_TAG = /^[a-z]{2,3}(?:-[A-Z0-9]{2,8})?$/;
const MAX_SPEECH_TEXT_BYTES = 8192;

/** Device-local Web Speech adapter; never selects or calls an online provider. */
export function createOfflineTextToSpeechProvider(windowRef) {
  const synthesis = windowRef?.speechSynthesis;
  let selectedVoiceURI = "";
  let selectedLanguage = "";
  let outputState = "unavailable";
  let statusListener = () => {};
  let playbackGeneration = 0;

  function publishStatus() { statusListener(status()); }

  function voices() {
    if (!synthesis || typeof synthesis.getVoices !== "function") return [];
    return synthesis.getVoices().filter(voice => voice?.localService === true
      && typeof voice.voiceURI === "string" && voice.voiceURI.length > 0
      && typeof voice.name === "string" && voice.name.length > 0
      && typeof voice.lang === "string" && LANGUAGE_TAG.test(voice.lang));
  }

  function status() {
    const availableVoices = voices();
    const selectionAvailable = availableVoices.some(voice => voice.voiceURI === selectedVoiceURI);
    if (!synthesis || typeof windowRef?.SpeechSynthesisUtterance !== "function" || !availableVoices.length) {
      outputState = "unavailable";
    } else if (selectedVoiceURI && !selectionAvailable) {
      outputState = "selected-voice-unavailable";
      selectedVoiceURI = "";
    } else if (!selectedVoiceURI) {
      outputState = "voice-not-selected";
    } else if (synthesis.speaking || synthesis.pending || outputState === "speaking") {
      outputState = "speaking";
    } else if (outputState !== "failed") {
      outputState = "ready";
    }
    return {
      backend: "local",
      state: outputState,
      selected_voice: selectedVoiceURI || null,
      language: selectedLanguage || null,
      voices: availableVoices.map(voice => ({ voice_uri: voice.voiceURI, name: voice.name, language: voice.lang })),
    };
  }

  function configure({ voiceURI, language }) {
    if (!synthesis || typeof windowRef?.SpeechSynthesisUtterance !== "function") {
      throw new Error("Offline speech output is unavailable on this device.");
    }
    if (typeof language !== "string" || language.length > 16 || !LANGUAGE_TAG.test(language)) {
      throw new Error("Enter a valid speech output language tag.");
    }
    if (typeof voiceURI !== "string" || !voices().some(voice => voice.voiceURI === voiceURI)) {
      throw new Error("Choose an available local speech voice.");
    }
    selectedVoiceURI = voiceURI;
    selectedLanguage = language;
    outputState = "ready";
    return status();
  }

  function speak(text) {
    const current = status();
    if (current.state === "unavailable" || current.state === "selected-voice-unavailable") {
      throw new Error("Offline speech output is unavailable on this device.");
    }
    if (!selectedVoiceURI || !selectedLanguage) throw new Error("Select a local speech voice and language first.");
    if (typeof text !== "string" || !text.trim()
        || new TextEncoder().encode(text).length > MAX_SPEECH_TEXT_BYTES) {
      throw new Error("Speech output text must be between 1 and 8192 UTF-8 bytes.");
    }
    const voice = voices().find(item => item.voiceURI === selectedVoiceURI);
    if (!voice) throw new Error("Selected local speech voice is no longer available.");
    playbackGeneration += 1;
    synthesis.cancel();
    const generation = ++playbackGeneration;
    const utterance = new windowRef.SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.lang = selectedLanguage;
    utterance.onend = () => {
      if (generation !== playbackGeneration) return;
      outputState = "ready";
      publishStatus();
    };
    utterance.onerror = () => {
      if (generation !== playbackGeneration) return;
      outputState = "failed";
      publishStatus();
    };
    outputState = "speaking";
    try { synthesis.speak(utterance); }
    catch {
      outputState = "failed";
      throw new Error("Local speech output failed. No online fallback was used.");
    }
    return status();
  }

  function stop() {
    playbackGeneration += 1;
    synthesis?.cancel?.();
    outputState = selectedVoiceURI ? "ready" : "voice-not-selected";
    return status();
  }

  function setStatusListener(listener) {
    statusListener = typeof listener === "function" ? listener : () => {};
  }

  return { status, voices, configure, speak, stop, setStatusListener };
}

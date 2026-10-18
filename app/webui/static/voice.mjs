const MAX_SECONDS = 10;
const MAX_CAPTURE_MS = MAX_SECONDS * 1000;
const TARGET_RATE = 16_000;
const SENSITIVE = /\bAIza[A-Za-z0-9_-]{20,}\b|\b(?:GEMINI|GOOGLE)_API_KEY\s*=\s*\S+/i;
import { createOfflineTextToSpeechProvider } from "./text-to-speech.mjs";

export function encodePcmWav(samples, sourceRate, { seconds = MAX_SECONDS } = {}) {
  if (!(samples instanceof Float32Array) || !Number.isFinite(sourceRate) || sourceRate < TARGET_RATE) {
    throw new Error("Microphone audio format is unavailable.");
  }
  const maxFrames = Math.floor(sourceRate * seconds);
  const input = samples.subarray(0, maxFrames);
  const frames = Math.floor(input.length * TARGET_RATE / sourceRate);
  if (frames < 1 || frames > TARGET_RATE * MAX_SECONDS) throw new Error("Recording is empty or exceeds 10 seconds.");
  const buffer = new ArrayBuffer(44 + frames * 2);
  const view = new DataView(buffer);
  const write = (offset, value) => {
    for (let index = 0; index < value.length; index++) view.setUint8(offset + index, value.charCodeAt(index));
  };
  write(0, "RIFF"); view.setUint32(4, buffer.byteLength - 8, true); write(8, "WAVE");
  write(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, TARGET_RATE, true);
  view.setUint32(28, TARGET_RATE * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, frames * 2, true);
  for (let index = 0; index < frames; index++) {
    const source = Math.min(input.length - 1, Math.floor(index * sourceRate / TARGET_RATE));
    const value = Math.max(-1, Math.min(1, input[source]));
    view.setInt16(44 + index * 2, value < 0 ? value * 0x8000 : value * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export function mountVoiceControls({
  documentRef = document,
  windowRef = globalThis.window,
  fetchImpl = fetch,
  onTranscript = () => {},
  canUseChat = () => true,
  confirmImpl = globalThis.confirm ?? (() => false),
  setTimeoutImpl = setTimeout,
  clearTimeoutImpl = clearTimeout,
  setIntervalImpl = setInterval,
  clearIntervalImpl = clearInterval,
  nowImpl = Date.now,
} = {}) {
  const element = id => documentRef.getElementById(id);
  const mode = element("voice-mode");
  const language = element("voice-language");
  const start = element("voice-start");
  const stopButton = element("voice-stop");
  const transcribe = element("voice-transcribe");
  const install = element("voice-install-local");
  const consent = element("voice-cloud-consent");
  const budgetForm = element("voice-budget-form");
  const budget = element("voice-budget-cents");
  const budgetSave = element("voice-budget-save");
  const budgetState = element("voice-budget-state");
  const state = element("voice-state");
  const stopPlayback = element("voice-stop-playback");
  const outputLanguage = element("voice-output-language");
  const outputVoice = element("voice-output-voice");
  const outputState = element("voice-output-state");
  const localModel = element("voice-local-model");
  const localModelState = element("voice-local-model-state");
  const cloudConsentPanel = element("voice-cloud-consent-panel");
  const Recognition = windowRef?.SpeechRecognition || windowRef?.webkitSpeechRecognition;
  const speechOutput = createOfflineTextToSpeechProvider(windowRef);
  let recognition = null;
  let stream = null;
  let audioContext = null;
  let processor = null;
  let gain = null;
  let source = null;
  let pieces = [];
  let capturedFrames = 0;
  let recording = false;
  let stage = "idle";
  let audioBlob = null;
  let requestController = null;
  let cloudBudget = null;
  let localSpeechStatus = { state: "backend-unavailable", available_models: [] };
  let captureMode = "cloud";
  let localAvailability = null;
  let emergencyStopped = false;
  let microphoneOutcome = "unknown";
  let remoteOutcomeUnknown = false;
  let localCaptureTimer = null;
  let captureClock = null;
  let captureStartedAt = null;
  let permissionState = "unknown";
  let captureStartup = 0;
  let savedVoicePreference = null;

  function reportActivity() {
    const EventType = windowRef?.CustomEvent || globalThis.CustomEvent;
    if (typeof windowRef?.dispatchEvent !== "function" || typeof EventType !== "function") return;
    windowRef.dispatchEvent(new EventType("ersel:voice-activity", { detail: {
      microphone: ["local-capture", "audio-capture", "audio-stopping"].includes(stage) ? "active" : microphoneOutcome,
      voice_stage: stage,
      microphone_permission: permissionState,
      capture_elapsed_seconds: captureStartedAt === null ? 0 : Math.min(MAX_SECONDS, Math.floor((nowImpl() - captureStartedAt) / 1000)),
      capture_limit_seconds: MAX_SECONDS,
      local_playback: speechOutput.status().state === "speaking" ? "active" : "off",
      remote_request: remoteOutcomeUnknown ? "possibly-processing-after-local-stop"
        : stage === "cloud-request" ? "possibly-processing" : "none",
    } }));
  }

  async function session() {
    const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error("Sign in through Local sign-in before using voice.");
    return response.json();
  }

  async function loadBudget() {
    try {
      const preferencesResponse = await fetchImpl("/api/local/preferences", { credentials: "same-origin", cache: "no-store" });
      if (preferencesResponse.ok) {
        const preferences = (await preferencesResponse.json()).preferences;
        savedVoicePreference = preferences;
        if (language && preferences.locale) language.value = preferences.locale;
        if (outputLanguage && preferences.voice_language) outputLanguage.value = preferences.voice_language;
      }
    } catch { /* Preferences never gate voice safety or typed chat. */ }
    try {
      const response = await fetchImpl("/api/local/voice", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Sign in to inspect cloud voice settings.");
      const payload = await response.json();
      cloudBudget = payload.cloud_budget;
      localSpeechStatus = payload.local_speech || localSpeechStatus;
      if (localModel) {
        const models = Array.isArray(localSpeechStatus.available_models) ? localSpeechStatus.available_models : [];
        localModel.replaceChildren();
        const placeholder = documentRef.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select an installed local model";
        localModel.append(placeholder);
        for (const modelId of models) {
          const option = documentRef.createElement("option");
          option.value = modelId;
          option.textContent = modelId;
          localModel.append(option);
        }
        localModel.value = localSpeechStatus.selected_model || "";
        localModel.disabled = localSpeechStatus.runtime !== "available" || !models.length;
      }
      if (localModelState) localModelState.textContent = localSpeechStatus.runtime !== "available"
        ? "Optional Faster-Whisper runtime or one of its dependencies is unavailable. Browser on-device speech remains available."
        : localSpeechStatus.state === "ready"
          ? `Local model ready: ${localSpeechStatus.selected_model}. No model was downloaded by this app.`
          : `${localSpeechStatus.state}. Add model files to the local speech-models folder, then select one here.`;
      budgetState.textContent = cloudBudget.configured
        ? `App-run cloud request budget: $${(cloudBudget.ceiling_cents / 100).toFixed(2)}; $${(cloudBudget.remaining_cents / 100).toFixed(2)} remains. The app reserves 1¢ per attempt; this is not a provider invoice cap.`
        : "Cloud transcription is off until you set an app-run request budget. This budget does not cap the provider invoice.";
      budget.disabled = cloudBudget.configured;
      budgetSave.disabled = cloudBudget.configured;
      updateOutputStatus();
      return true;
    } catch (error) {
      budgetState.textContent = error.message;
      return false;
    }
  }

  function updateControls() {
    const localMode = mode.value === "local";
    const modelMode = mode.value === "local-model";
    start.disabled = stage !== "idle" || !canUseChat()
      || (localMode ? !Recognition : modelMode
        ? localSpeechStatus.state !== "ready" || !windowRef?.navigator?.mediaDevices?.getUserMedia
        : !windowRef?.navigator?.mediaDevices?.getUserMedia);
    install.hidden = !localMode || !Recognition || !Recognition.available
      || localAvailability !== "downloadable" || stage !== "idle";
    stopButton.hidden = ["idle", "installing"].includes(stage);
    stopButton.disabled = stage === "idle";
    transcribe.hidden = stage !== "audio-ready";
    if (!transcribe.hidden) transcribe.textContent = captureMode === "cloud"
      ? "Transcribe via Gemini (send recording)" : "Transcribe locally";
    const consentMode = ["audio-ready", "audio-preparing", "cloud-request", "local-model-request"].includes(stage)
      ? captureMode : mode.value;
    if (cloudConsentPanel) cloudConsentPanel.hidden = consentMode !== "cloud";
    stopPlayback.disabled = speechOutput.status().state !== "speaking";
    reportActivity();
  }

  function updateOutputStatus(snapshot = speechOutput.status()) {
    if (savedVoicePreference?.voice_mode === "local" && savedVoicePreference.voice_id && !snapshot.selected_voice
      && snapshot.voices.some(voice => voice.voice_uri === savedVoicePreference.voice_id)) {
      try {
        snapshot = speechOutput.configure({
          voiceURI: savedVoicePreference.voice_id,
          language: savedVoicePreference.voice_language || outputLanguage?.value.trim() || "en-US",
        });
      } catch { /* A stale or invalid saved preference stays unselected and visible. */ }
    }
    if (outputVoice) {
      outputVoice.replaceChildren();
      const placeholder = documentRef.createElement("option");
      placeholder.value = "";
      placeholder.textContent = snapshot.voices.length ? "Select a local voice" : "No local voices available";
      outputVoice.append(placeholder);
      for (const voice of snapshot.voices) {
        const option = documentRef.createElement("option");
        option.value = voice.voice_uri;
        option.textContent = `${voice.name} (${voice.language})`;
        outputVoice.append(option);
      }
      outputVoice.value = snapshot.selected_voice || "";
      outputVoice.disabled = snapshot.voices.length === 0;
    }
    if (outputState) {
      const selected = snapshot.voices.find(voice => voice.voice_uri === snapshot.selected_voice);
      const languageCode = outputLanguage?.value.trim() || snapshot.language || "not set";
      const labels = {
        unavailable: "Offline speech output is unavailable on this device; no online fallback is used.",
        "voice-not-selected": "Choose an installed local voice and output language before speaking a reply.",
        "selected-voice-unavailable": "The selected local voice is no longer available. Choose another voice.",
        ready: `Offline device speech is ready: ${selected?.name || "local voice"} (${languageCode}).`,
        speaking: `Speaking locally with ${selected?.name || "the selected voice"} (${languageCode})${snapshot.queued_items ? `; ${snapshot.queued_items} more replies queued` : ""}.`,
        failed: "Local speech output failed. No online fallback was used.",
        stopped: "Local speech stopped and queued reply text was cleared.",
      };
      outputState.textContent = labels[snapshot.state] || "Offline speech output status is unknown.";
    }
    if (stopPlayback) stopPlayback.disabled = snapshot.state !== "speaking";
    reportActivity();
  }

  function configureOutput() {
    if (!outputVoice?.value || !outputLanguage) { updateOutputStatus(); return; }
    try {
      updateOutputStatus(speechOutput.configure({ voiceURI: outputVoice.value, language: outputLanguage.value.trim() }));
      void saveVoicePreference({ voice_mode: "local", voice_language: outputLanguage.value.trim(), voice_id: outputVoice.value });
    } catch (error) {
      updateOutputStatus();
      if (outputState) outputState.textContent = error.message;
    }
  }

  async function saveVoicePreference(changes) {
    try {
      const csrf = (await session()).csrf;
      await fetchImpl("/api/local/preferences", { method: "PUT", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf }, body: JSON.stringify(changes) });
    } catch { /* Voice remains an explicit per-use action. */ }
  }

  speechOutput.setStatusListener(updateOutputStatus);

  function setState(message) { state.textContent = message; }

  function clearCaptureClock() {
    if (captureClock !== null) clearIntervalImpl(captureClock);
    captureClock = null;
    captureStartedAt = null;
  }

  function startCaptureClock() {
    clearCaptureClock();
    captureStartedAt = nowImpl();
    captureClock = setIntervalImpl(reportActivity, 1000);
    reportActivity();
  }

  async function authorizeMicrophone() {
    if (typeof windowRef?.desktopBridge?.requestMicrophone !== "function") return;
    const permitted = await windowRef.desktopBridge.requestMicrophone();
    if (permitted !== true) {
      permissionState = "denied";
      throw new Error("Microphone access was not approved. Typed chat remains available.");
    }
    permissionState = "granted";
  }

  async function beginLocal(startupId) {
    const languageCode = language.value.trim();
    if (!/^[a-z]{2,3}(?:-[A-Z0-9]{2,8})?$/.test(languageCode)) throw new Error("Choose a valid speech language tag.");
    if (typeof Recognition.available !== "function" || typeof Recognition.install !== "function") {
      localAvailability = "unavailable";
      stage = "idle";
      updateControls();
      setState("This browser cannot verify on-device speech support. No remote recognition fallback was used.");
      return;
    }
    const availability = await Recognition.available({ langs: [languageCode], processLocally: true });
    if (emergencyStopped || startupId !== captureStartup) {
      if (startupId === captureStartup) stage = "idle";
      updateControls(); return;
    }
    localAvailability = availability;
    if (availability !== "available") {
      if (availability === "downloadable") {
        setState("A browser-managed speech language pack is available. Choose Install browser speech language pack; speech audio remains on this device.");
      } else {
        setState("On-device speech recognition is unavailable for this language. No cloud fallback was used.");
      }
      stage = "idle";
      updateControls();
      return;
    }
    await authorizeMicrophone();
    if (emergencyStopped || startupId !== captureStartup) {
      if (startupId === captureStartup) stage = "idle";
      updateControls(); return;
    }
    recognition = new Recognition();
    if (!("processLocally" in recognition)) {
      recognition = null;
      stage = "idle";
      updateControls();
      setState("This browser cannot guarantee on-device recognition. No remote fallback was used.");
      return;
    }
    recognition.lang = languageCode;
    recognition.processLocally = true;
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;
    permissionState = "requesting";
    stage = "local-capture-pending";
    updateControls();
    setState(permissionState === "granted"
      ? "Listening locally on this device for up to 10 seconds. Audio is not sent to a service or saved by this app."
      : "Waiting for this browser's microphone permission. Capture is limited to 10 seconds.");
    recognition.onstart = () => {
      if (stage !== "local-capture-pending") return;
      stage = "local-capture";
      permissionState = "granted";
      microphoneOutcome = "active";
      startCaptureClock();
      setState("Listening locally on this device for up to 10 seconds. Audio is not sent to a service or saved by this app.");
      updateControls();
      localCaptureTimer = setTimeoutImpl(() => {
        if (stage !== "local-capture") return;
        void stop();
        setState("The 10-second local capture limit was reached. The transcript was not sent or saved.");
      }, MAX_CAPTURE_MS);
    };
    recognition.onresult = event => {
      if (stage !== "local-capture") return;
      const transcript = event.results?.[0]?.[0]?.transcript?.trim();
      if (!transcript) { setState("No speech was recognized. Nothing was sent or saved."); return; }
      if (SENSITIVE.test(transcript)) { setState("Possible API key or sensitive credential detected. The transcript was discarded."); return; }
      onTranscript(transcript, "local");
      setState("Local transcript added to the message box for review. It was not sent or saved; choose Send to continue.");
    };
    recognition.onerror = event => {
      microphoneOutcome = event.error === "not-allowed" || event.error === "service-not-allowed" ? "denied" : "failed";
      if (microphoneOutcome === "denied") permissionState = "denied";
      else permissionState = "failed";
      clearCaptureClock();
      if (localCaptureTimer !== null) clearTimeoutImpl(localCaptureTimer);
      localCaptureTimer = null;
      stage = "idle";
      setState(event.error === "not-allowed" || event.error === "service-not-allowed"
        ? "Microphone access was denied. Typed chat remains available."
        : "Local speech recognition failed. Nothing was sent or saved; typed chat remains available.");
      updateControls();
    };
    recognition.onend = () => {
      clearCaptureClock();
      if (localCaptureTimer !== null) clearTimeoutImpl(localCaptureTimer);
      localCaptureTimer = null;
      if (["local-capture", "local-capture-pending"].includes(stage)) stage = "idle";
      if (microphoneOutcome === "unknown" || microphoneOutcome === "active") microphoneOutcome = "inactive";
      recognition = null;
      updateControls();
    };
    try {
      recognition.start();
    }
    catch { recognition = null; stage = "idle"; updateControls(); throw new Error("Local speech recognition could not start."); }
  }

  async function installLocalPack() {
    const languageCode = language.value.trim();
    if (!Recognition?.install || !confirmImpl(`Download the browser-managed ${languageCode} speech language pack? Microphone audio will remain local.`)) return;
    stage = "installing";
    updateControls();
    setState("Downloading the selected browser speech language pack. No microphone audio is sent.");
    try {
      const installed = await Recognition.install({ langs: [languageCode], processLocally: true });
      localAvailability = installed ? "available" : "downloadable";
      setState(installed ? "Browser speech language pack installed. Start a new local recording when ready."
        : "The browser speech language pack could not be installed. No cloud fallback was used.");
    } catch {
      setState("The browser speech language pack could not be installed. No cloud fallback was used.");
    } finally { stage = "idle"; updateControls(); }
  }

  async function beginAudioCapture(startupId) {
    captureMode = mode.value;
    if (captureMode === "cloud" && (!cloudBudget?.configured || cloudBudget.remaining_cents < 1)) {
      await loadBudget();
      if (!cloudBudget?.configured || cloudBudget.remaining_cents < 1) {
        throw new Error("Set an available cloud voice ceiling before recording for Gemini.");
      }
    }
    if (emergencyStopped || startupId !== captureStartup) return;
    await authorizeMicrophone();
    if (emergencyStopped || startupId !== captureStartup) return;
    stream = await windowRef.navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false,
    });
    if (emergencyStopped || startupId !== captureStartup) { for (const track of stream.getTracks()) track.stop(); stream = null; return; }
    audioContext = new windowRef.AudioContext();
    source = audioContext.createMediaStreamSource(stream);
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    gain = audioContext.createGain();
    gain.gain.value = 0;
    pieces = [];
    capturedFrames = 0;
    recording = true;
    stage = "audio-capture";
    permissionState = "granted";
    microphoneOutcome = "active";
    startCaptureClock();
    processor.onaudioprocess = event => {
      if (!recording) return;
      const data = event.inputBuffer.getChannelData(0);
      const limit = Math.floor(audioContext.sampleRate * MAX_SECONDS);
      const count = Math.min(data.length, limit - capturedFrames);
      if (count > 0) { pieces.push(new Float32Array(data.subarray(0, count))); capturedFrames += count; }
      if (capturedFrames >= limit) finishCapture();
    };
    source.connect(processor);
    processor.connect(gain);
    gain.connect(audioContext.destination);
    updateControls();
    setState(captureMode === "cloud"
      ? "Recording locally for at most 10 seconds. Nothing is sent until you review cloud consent and choose Transcribe."
      : "Recording locally for at most 10 seconds. Audio stays on this device and is sent only to the explicitly selected local model when you choose Transcribe.");
  }

  function joinedSamples() {
    const samples = new Float32Array(capturedFrames);
    let offset = 0;
    for (const piece of pieces) { samples.set(piece, offset); offset += piece.length; }
    return samples;
  }

  async function stopTracks() {
    recording = false;
    clearCaptureClock();
    try { source?.disconnect(); processor?.disconnect(); gain?.disconnect(); } catch { /* already disconnected */ }
    for (const track of stream?.getTracks?.() || []) track.stop();
    stream = null;
    if (audioContext && audioContext.state !== "closed") {
      try { await audioContext.close(); } catch { /* shutdown is best effort */ }
    }
    audioContext = null; source = null; processor = null; gain = null;
  }

  async function finishCapture() {
    if (stage !== "audio-capture") return;
    stage = "audio-stopping";
    const samples = joinedSamples();
    const rate = audioContext?.sampleRate;
    await stopTracks();
    pieces = []; capturedFrames = 0;
    if (stage !== "audio-stopping") {
      samples.fill(0);
      return;
    }
    try {
      audioBlob = encodePcmWav(samples, rate);
      stage = "audio-ready";
      setState(captureMode === "cloud"
        ? "Recording is held in memory for this turn only. Review cloud consent, then explicitly choose Transcribe to send it to Google Gemini."
        : "Recording is held in memory for this turn only. Choose Transcribe to process it with the selected local model.");
    } catch (error) {
      audioBlob = null; stage = "idle"; setState(error.message);
    }
    updateControls();
  }

  async function transcribeAudio() {
    if (stage !== "audio-ready" || !audioBlob) throw new Error("Record a short clip before transcription.");
    if (captureMode === "cloud" && !consent.checked) throw new Error("Consent to send this recording to Google Gemini for transcription before continuing.");
    stage = "audio-preparing";
    updateControls();
    let csrf;
    try { csrf = (await session()).csrf; }
    catch (error) {
      audioBlob = null; stage = "idle"; updateControls();
      throw error;
    }
    if (stage !== "audio-preparing" || !audioBlob) return;
    requestController = new AbortController();
    const controller = requestController;
    const payload = audioBlob;
    audioBlob = null;
    stage = captureMode === "cloud" ? "cloud-request" : "local-model-request";
    updateControls();
    setState(captureMode === "cloud"
      ? "Sending the confirmed recording to Gemini. The app does not store audio; the provider request can still finish if you stop waiting."
      : "Processing the recording with the selected local model. Audio is not sent to an online provider.");
    if (captureMode === "cloud") consent.checked = false;
    try {
      const endpoint = captureMode === "cloud" ? "/api/local/voice/transcribe"
        : `/api/local/voice/transcribe-local?language=${encodeURIComponent(language.value.trim())}`;
      const response = await fetchImpl(endpoint, {
        method: "POST", credentials: "same-origin", cache: "no-store", signal: controller.signal,
        headers: { "Content-Type": "audio/wav", "X-Local-CSRF": csrf,
          ...(captureMode === "cloud" ? { "X-Cloud-Consent": "true" } : {}) },
        body: payload,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Gemini transcription failed.");
      if (typeof result.transcript !== "string" || !result.transcript.trim()) throw new Error("Gemini returned no transcript.");
      if (captureMode === "cloud") remoteOutcomeUnknown = false;
      if (SENSITIVE.test(result.transcript)) {
        setState("Possible API key or sensitive credential detected. The transcript was discarded.");
      } else {
        onTranscript(result.transcript, captureMode === "cloud" ? "gemini" : "local-model");
        setState(`${captureMode === "cloud" ? "Cloud" : "Local model"} transcript added to the message box for review. It was not sent to chat or saved; choose Send to continue.`);
      }
      if (captureMode === "cloud") {
        cloudBudget = { ...cloudBudget, remaining_cents: result.remaining_cents };
        await loadBudget();
      }
    } catch (error) {
      if (controller.signal.aborted) {
        setState(captureMode === "cloud"
          ? "Stopped waiting locally. Gemini may already have received or processed this recording; the request outcome and charge are unknown. No retry was made."
          : "Stopped waiting locally. Model processing may finish before it notices cancellation. No audio was sent online and no retry was made.");
      } else {
        setState(error.message);
        await loadBudget();
      }
    } finally {
      requestController = null;
      stage = "idle";
      updateControls();
    }
  }

  async function stop() {
    if (["local-capture", "local-capture-pending", "audio-capture", "audio-stopping", "starting"].includes(stage)) {
      microphoneOutcome = "inactive";
    }
    if (localCaptureTimer !== null) clearTimeoutImpl(localCaptureTimer);
    localCaptureTimer = null;
    if (stage === "local-capture" || stage === "local-capture-pending") {
      stage = "idle";
      recognition?.abort();
      recognition = null;
      updateControls();
      setState("Local recording stopped. No transcript was sent or saved.");
    } else if (stage === "audio-capture") {
      await stopTracks(); pieces = []; capturedFrames = 0; stage = "idle";
      updateControls();
      setState("Recording stopped and discarded locally. No audio was sent.");
    } else if (stage === "audio-stopping") {
      stage = "audio-canceling";
      audioBlob = null;
      await stopTracks(); pieces = []; capturedFrames = 0; stage = "idle";
      updateControls(); setState("Recording stopped and discarded locally. No audio was sent.");
    } else if (stage === "audio-ready") {
      audioBlob = null; stage = "idle"; updateControls();
      setState("Local recording discarded. Nothing was sent.");
    } else if (stage === "audio-preparing") {
      audioBlob = null; stage = "idle"; updateControls();
      setState("Local recording discarded before any cloud request. Nothing was sent.");
    } else if (stage === "cloud-request") {
      remoteOutcomeUnknown = true;
      requestController?.abort();
      stopButton.disabled = true;
    } else if (stage === "local-model-request") {
      requestController?.abort();
      stopButton.disabled = true;
    } else if (stage === "starting") {
      captureStartup += 1;
      stage = "idle";
      updateControls();
      setState("Voice startup stopped. No new microphone capture will begin.");
    }
  }

  windowRef?.addEventListener?.("ersel:emergency-stop", () => {
    emergencyStopped = true;
    void stop();
    updateOutputStatus(speechOutput.stop());
    updateControls();
  });
  windowRef?.addEventListener?.("ersel:voice-stop", () => { void stop(); });
  windowRef?.addEventListener?.("ersel:playback-stop", () => {
    updateOutputStatus(speechOutput.stop());
    setState("Local speech playback stopped and queued reply text cleared.");
  });
  windowRef?.addEventListener?.("ersel:emergency-resumed", () => {
    emergencyStopped = false;
    updateControls();
  });

  async function configureBudget(event) {
    event.preventDefault();
    const cents = Number(budget.value);
    if (!Number.isSafeInteger(cents) || cents < 1 || cents > 100) {
      budgetState.textContent = "Enter an app-run request budget from 1 to 100 cents; this is not a provider invoice cap.";
      return;
    }
    try {
      const csrf = (await session()).csrf;
      const response = await fetchImpl("/api/local/voice/cloud-budget", {
        method: "POST", credentials: "same-origin", headers: {
          "Content-Type": "application/json", "X-Local-CSRF": csrf,
        }, body: JSON.stringify({ ceiling_cents: cents }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Cloud voice budget could not be configured.");
      cloudBudget = result;
      await loadBudget();
    } catch (error) { budgetState.textContent = error.message; }
    updateControls();
  }

  function speak(text) {
    try {
      const snapshot = speechOutput.speak(text);
      updateOutputStatus(snapshot);
      setState(snapshot.queued_items
        ? `Reply added to the bounded local speech queue (${snapshot.queued_items} waiting). No text was sent online.`
        : "Speaking the reply with the selected offline device voice. No text was sent online.");
      return true;
    } catch (error) {
      updateOutputStatus();
      setState(error.message || "Local speech output failed. No online fallback was used.");
      return false;
    }
  }

  function clear() {
    if (["starting", "local-capture-pending", "local-capture", "audio-capture", "audio-stopping", "audio-ready", "audio-preparing"].includes(stage)) void stop();
    else if (stage === "cloud-request") requestController?.abort();
    updateOutputStatus(speechOutput.stop());
    stage = "idle"; audioBlob = null; updateControls();
  }

  start.addEventListener("click", async () => {
    if (emergencyStopped) { setState("Emergency stop is active. Resume protected actions before starting voice."); return; }
    if (!canUseChat()) { setState("Start or select an open conversation before using voice."); return; }
    microphoneOutcome = "unknown";
    permissionState = "requesting";
    const startupId = ++captureStartup;
    stage = "starting"; updateControls();
    try {
      if (mode.value === "local") await beginLocal(startupId);
      else await beginAudioCapture(startupId);
    } catch (error) {
      if (startupId !== captureStartup) return;
      stage = "idle";
      microphoneOutcome = error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError"
        ? "denied" : "failed";
      if (microphoneOutcome === "denied") permissionState = "denied";
      else if (permissionState === "requesting") permissionState = "failed";
      setState(error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError"
        ? "Microphone access was denied. Typed chat remains available."
        : error.message || "Voice interaction failed. Typed chat remains available.");
      updateControls();
    }
  });
  stopButton.addEventListener("click", () => { void stop(); });
  transcribe.addEventListener("click", async () => {
    try { await transcribeAudio(); }
    catch (error) { setState(error.message); }
  });
  install.addEventListener("click", () => { void installLocalPack(); });
  budgetForm.addEventListener("submit", configureBudget);
  localModel?.addEventListener("change", async () => {
    if (!localModel.value) return;
    try {
      const csrf = (await session()).csrf;
      const response = await fetchImpl("/api/local/voice/local-model", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
        body: JSON.stringify({ model_id: localModel.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Local speech model could not be selected.");
      localSpeechStatus = result;
      if (localModelState) localModelState.textContent = `Local model selected: ${result.selected_model}. It loads only when you explicitly transcribe.`;
    } catch (error) {
      if (localModelState) localModelState.textContent = error.message || "Local speech model could not be selected.";
    }
    updateControls();
  });
  stopPlayback.addEventListener("click", () => {
    updateOutputStatus(speechOutput.stop());
    setState("Local speech playback stopped.");
  });
  outputVoice?.addEventListener("change", configureOutput);
  outputLanguage?.addEventListener("change", configureOutput);
  windowRef?.speechSynthesis?.addEventListener?.("voiceschanged", () => {
    updateOutputStatus();
    updateControls();
  });
  mode.addEventListener("change", updateControls);
  updateOutputStatus();
  updateControls();
  void loadBudget();
  return { clear, speak, loadBudget, updateControls };
}

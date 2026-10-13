const MAX_SECONDS = 10;
const MAX_CAPTURE_MS = MAX_SECONDS * 1000;
const TARGET_RATE = 16_000;
const SENSITIVE = /\bAIza[A-Za-z0-9_-]{20,}\b|\b(?:GEMINI|GOOGLE)_API_KEY\s*=\s*\S+/i;

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
  const Recognition = windowRef?.SpeechRecognition || windowRef?.webkitSpeechRecognition;
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
  let currentSpeech = null;
  let cloudBudget = null;
  let localAvailability = null;
  let emergencyStopped = false;
  let remoteOutcomeUnknown = false;
  let localCaptureTimer = null;
  let captureStartup = 0;

  function reportActivity() {
    const EventType = windowRef?.CustomEvent || globalThis.CustomEvent;
    if (typeof windowRef?.dispatchEvent !== "function" || typeof EventType !== "function") return;
    windowRef.dispatchEvent(new EventType("ersel:voice-activity", { detail: {
      microphone: ["local-capture", "cloud-capture", "cloud-stopping"].includes(stage) ? "active" : "off",
      local_playback: windowRef?.speechSynthesis?.speaking || windowRef?.speechSynthesis?.pending
        ? "active" : "off",
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
      const response = await fetchImpl("/api/local/voice", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Sign in to inspect cloud voice settings.");
      const payload = await response.json();
      cloudBudget = payload.cloud_budget;
      budgetState.textContent = cloudBudget.configured
        ? `App-run cloud request budget: $${(cloudBudget.ceiling_cents / 100).toFixed(2)}; $${(cloudBudget.remaining_cents / 100).toFixed(2)} remains. The app reserves 1¢ per attempt; this is not a provider invoice cap.`
        : "Cloud transcription is off until you set an app-run request budget. This budget does not cap the provider invoice.";
      budget.disabled = cloudBudget.configured;
      budgetSave.disabled = cloudBudget.configured;
      return true;
    } catch (error) {
      budgetState.textContent = error.message;
      return false;
    }
  }

  function updateControls() {
    const localMode = mode.value === "local";
    start.disabled = stage !== "idle" || !canUseChat()
      || (localMode ? !Recognition : !windowRef?.navigator?.mediaDevices?.getUserMedia);
    install.hidden = !localMode || !Recognition || !Recognition.available
      || localAvailability !== "downloadable" || stage !== "idle";
    stopButton.hidden = ["idle", "starting", "installing"].includes(stage);
    stopButton.disabled = stage === "idle";
    transcribe.hidden = stage !== "cloud-ready";
    stopPlayback.disabled = !windowRef?.speechSynthesis;
    reportActivity();
  }

  function setState(message) { state.textContent = message; }

  async function authorizeMicrophone() {
    if (typeof windowRef?.desktopBridge?.requestMicrophone !== "function") return;
    const permitted = await windowRef.desktopBridge.requestMicrophone();
    if (permitted !== true) throw new Error("Microphone access was not approved. Typed chat remains available.");
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
        setState("This local language pack is downloadable. Select Install local pack; speech audio will still be processed on this device.");
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
    stage = "local-capture";
    updateControls();
    setState("Listening locally on this device. Audio is not sent to a service or saved by this app.");
    recognition.onresult = event => {
      if (stage !== "local-capture") return;
      const transcript = event.results?.[0]?.[0]?.transcript?.trim();
      if (!transcript) { setState("No speech was recognized. Nothing was sent or saved."); return; }
      if (SENSITIVE.test(transcript)) { setState("Possible API key or sensitive credential detected. The transcript was discarded."); return; }
      onTranscript(transcript, "local");
      setState("Local transcript added to the message box for review. It was not sent or saved; choose Send to continue.");
    };
    recognition.onerror = event => {
      setState(event.error === "not-allowed" || event.error === "service-not-allowed"
        ? "Microphone access was denied. Typed chat remains available."
        : "Local speech recognition failed. Nothing was sent or saved; typed chat remains available.");
    };
    recognition.onend = () => {
      if (localCaptureTimer !== null) clearTimeoutImpl(localCaptureTimer);
      localCaptureTimer = null;
      if (stage === "local-capture") stage = "idle";
      recognition = null;
      updateControls();
    };
    try {
      recognition.start();
      localCaptureTimer = setTimeoutImpl(() => {
        if (stage !== "local-capture") return;
        void stop();
        setState("The 10-second local capture limit was reached. The transcript was not sent or saved.");
      }, MAX_CAPTURE_MS);
    }
    catch { recognition = null; stage = "idle"; updateControls(); throw new Error("Local speech recognition could not start."); }
  }

  async function installLocalPack() {
    const languageCode = language.value.trim();
    if (!Recognition?.install || !confirmImpl(`Download the ${languageCode} on-device speech pack? Microphone audio will remain local.`)) return;
    stage = "installing";
    updateControls();
    setState("Downloading the selected on-device language pack. No microphone audio is sent.");
    try {
      const installed = await Recognition.install({ langs: [languageCode], processLocally: true });
      localAvailability = installed ? "available" : "downloadable";
      setState(installed ? "Local language pack installed. Start a new local recording when ready."
        : "The local language pack could not be installed. No cloud fallback was used.");
    } catch {
      setState("The local language pack could not be installed. No cloud fallback was used.");
    } finally { stage = "idle"; updateControls(); }
  }

  async function beginCloudCapture(startupId) {
    if (!cloudBudget?.configured || cloudBudget.remaining_cents < 1) {
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
    stage = "cloud-capture";
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
    setState("Recording locally for at most 10 seconds. Nothing is sent until you review the cloud-consent box and choose Transcribe.");
  }

  function joinedSamples() {
    const samples = new Float32Array(capturedFrames);
    let offset = 0;
    for (const piece of pieces) { samples.set(piece, offset); offset += piece.length; }
    return samples;
  }

  async function stopTracks() {
    recording = false;
    try { source?.disconnect(); processor?.disconnect(); gain?.disconnect(); } catch { /* already disconnected */ }
    for (const track of stream?.getTracks?.() || []) track.stop();
    stream = null;
    if (audioContext && audioContext.state !== "closed") {
      try { await audioContext.close(); } catch { /* shutdown is best effort */ }
    }
    audioContext = null; source = null; processor = null; gain = null;
  }

  async function finishCapture() {
    if (stage !== "cloud-capture") return;
    stage = "cloud-stopping";
    const samples = joinedSamples();
    const rate = audioContext?.sampleRate;
    await stopTracks();
    pieces = []; capturedFrames = 0;
    if (stage !== "cloud-stopping") {
      samples.fill(0);
      return;
    }
    try {
      audioBlob = encodePcmWav(samples, rate);
      stage = "cloud-ready";
      setState("Recording is held in memory for this turn only. Review the cloud-consent notice, then explicitly choose Transcribe to send it to Google Gemini.");
    } catch (error) {
      audioBlob = null; stage = "idle"; setState(error.message);
    }
    updateControls();
  }

  async function transcribeCloud() {
    if (stage !== "cloud-ready" || !audioBlob) throw new Error("Record a short clip before transcription.");
    if (!consent.checked) throw new Error("Consent to send this recording to Google Gemini for transcription before continuing.");
    stage = "cloud-preparing";
    updateControls();
    let csrf;
    try { csrf = (await session()).csrf; }
    catch (error) {
      audioBlob = null; stage = "idle"; updateControls();
      throw error;
    }
    if (stage !== "cloud-preparing" || !audioBlob) return;
    requestController = new AbortController();
    const controller = requestController;
    const payload = audioBlob;
    audioBlob = null;
    stage = "cloud-request";
    updateControls();
    setState("Sending the confirmed recording to Gemini. The app does not store audio; the provider request can still finish if you stop waiting.");
    consent.checked = false;
    try {
      const response = await fetchImpl("/api/local/voice/transcribe", {
        method: "POST", credentials: "same-origin", cache: "no-store", signal: controller.signal,
        headers: { "Content-Type": "audio/wav", "X-Local-CSRF": csrf, "X-Cloud-Consent": "true" },
        body: payload,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Gemini transcription failed.");
      if (typeof result.transcript !== "string" || !result.transcript.trim()) throw new Error("Gemini returned no transcript.");
      remoteOutcomeUnknown = false;
      if (SENSITIVE.test(result.transcript)) {
        setState("Possible API key or sensitive credential detected. The transcript was discarded.");
      } else {
        onTranscript(result.transcript, "gemini");
        setState("Transcript added to the message box for review. It was not sent to chat or saved; choose Send to continue.");
      }
      cloudBudget = { ...cloudBudget, remaining_cents: result.remaining_cents };
      await loadBudget();
    } catch (error) {
      if (controller.signal.aborted) {
        setState("Stopped waiting locally. Gemini may already have received or processed this recording; the request outcome and charge are unknown. No retry was made.");
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
    if (localCaptureTimer !== null) clearTimeoutImpl(localCaptureTimer);
    localCaptureTimer = null;
    if (stage === "local-capture") {
      stage = "idle";
      recognition?.abort();
      recognition = null;
      updateControls();
      setState("Local recording stopped. No transcript was sent or saved.");
    } else if (stage === "cloud-capture") {
      await stopTracks(); pieces = []; capturedFrames = 0; stage = "idle";
      updateControls();
      setState("Recording stopped and discarded locally. No audio was sent.");
    } else if (stage === "cloud-stopping") {
      stage = "cloud-canceling";
      audioBlob = null;
      await stopTracks(); pieces = []; capturedFrames = 0; stage = "idle";
      updateControls(); setState("Recording stopped and discarded locally. No audio was sent.");
    } else if (stage === "cloud-ready") {
      audioBlob = null; stage = "idle"; updateControls();
      setState("Local recording discarded. Nothing was sent.");
    } else if (stage === "cloud-preparing") {
      audioBlob = null; stage = "idle"; updateControls();
      setState("Local recording discarded before any cloud request. Nothing was sent.");
    } else if (stage === "cloud-request") {
      remoteOutcomeUnknown = true;
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
    windowRef?.speechSynthesis?.cancel?.();
    currentSpeech = null;
    updateControls();
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
    if (!windowRef?.speechSynthesis || typeof windowRef.SpeechSynthesisUtterance !== "function") {
      setState("Local speech output is unavailable on this device.");
      return false;
    }
    windowRef.speechSynthesis.cancel();
    currentSpeech = new windowRef.SpeechSynthesisUtterance(text.slice(0, 8192));
    const localVoice = windowRef.speechSynthesis.getVoices().find(voice => voice.localService);
    if (!localVoice) {
      currentSpeech = null;
      setState("No local speech output voice is installed on this device.");
      return false;
    }
    currentSpeech.voice = localVoice;
    currentSpeech.onend = () => { currentSpeech = null; setState("Local speech playback finished."); };
    currentSpeech.onerror = () => { currentSpeech = null; setState("Local speech playback stopped or failed."); };
    windowRef.speechSynthesis.speak(currentSpeech);
    setState("Speaking the reply with the device's local speech engine. No audio was sent.");
    return true;
  }

  function clear() {
    if (stage === "local-capture" || stage === "cloud-capture" || stage === "cloud-stopping" || stage === "cloud-ready") void stop();
    else if (stage === "cloud-request") requestController?.abort();
    windowRef?.speechSynthesis?.cancel?.();
    stage = "idle"; audioBlob = null; updateControls();
  }

  start.addEventListener("click", async () => {
    if (emergencyStopped) { setState("Emergency stop is active. Resume protected actions before starting voice."); return; }
    if (!canUseChat()) { setState("Start or select an open conversation before using voice."); return; }
    const startupId = ++captureStartup;
    stage = "starting"; updateControls();
    try {
      if (mode.value === "local") await beginLocal(startupId);
      else await beginCloudCapture(startupId);
    } catch (error) {
      if (startupId !== captureStartup) return;
      stage = "idle";
      setState(error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError"
        ? "Microphone access was denied. Typed chat remains available."
        : error.message || "Voice interaction failed. Typed chat remains available.");
      updateControls();
    }
  });
  stopButton.addEventListener("click", () => { void stop(); });
  transcribe.addEventListener("click", async () => {
    try { await transcribeCloud(); }
    catch (error) { setState(error.message); }
  });
  install.addEventListener("click", () => { void installLocalPack(); });
  budgetForm.addEventListener("submit", configureBudget);
  stopPlayback.addEventListener("click", () => {
    windowRef?.speechSynthesis?.cancel?.(); currentSpeech = null;
    setState("Local speech playback stopped.");
  });
  mode.addEventListener("change", updateControls);
  updateControls();
  void loadBudget();
  return { clear, speak, loadBudget, updateControls };
}

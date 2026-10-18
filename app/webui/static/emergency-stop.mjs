export function mountEmergencyStop({
  documentRef = document,
  windowRef = globalThis.window,
  fetchImpl = fetch,
  confirmImpl = globalThis.confirm ?? (() => false),
  browserFeatures = null,
} = {}) {
  const stopButton = documentRef.getElementById("emergency-stop");
  if (!stopButton) return null;
  const resumeButton = documentRef.getElementById("emergency-resume");
  const state = documentRef.getElementById("emergency-state");
  const grants = documentRef.getElementById("emergency-grants");
  const permissions = documentRef.getElementById("emergency-permissions");
  const activity = documentRef.getElementById("emergency-activity");
  const microphoneStop = documentRef.getElementById("capability-microphone-stop");
  const microphoneState = documentRef.getElementById("capability-microphone-state");
  let stopped = false;
  let capture = { microphone: "unknown", screen: "unknown", camera: "unknown", local_playback: "unknown", remote_request: "none" };
  let previousStopped = null;

  function features() {
    if (browserFeatures) return browserFeatures;
    const nav = windowRef?.navigator || globalThis.navigator;
    const recognition = windowRef?.SpeechRecognition || windowRef?.webkitSpeechRecognition;
    return {
      microphone: typeof nav?.mediaDevices?.getUserMedia === "function" || typeof recognition === "function",
      camera: typeof nav?.mediaDevices?.getUserMedia === "function",
      screen: typeof nav?.mediaDevices?.getDisplayMedia === "function",
      playback: typeof windowRef?.speechSynthesis?.speak === "function",
      vision: Boolean(documentRef.getElementById("chat-image-file")),
    };
  }

  function setIndicator(name, support, state) {
    text(documentRef.getElementById(`capability-${name}-support`), support);
    text(documentRef.getElementById(`capability-${name}-activity`), state);
  }

  function activityLabel(value) {
    return ({ active: "Active", inactive: "Inactive", off: "Inactive", denied: "Denied",
      unsupported: "Unsupported", unavailable: "Unavailable", failed: "Failed",
      uncertain_stop: "Stop uncertain", unknown: "Unknown" })[value] || "Unknown";
  }

  function renderCapabilities() {
    const available = features();
    text(documentRef.getElementById("capability-microphone-support"), available.microphone ? "Available in this browser" : "Unsupported in this browser");
    text(documentRef.getElementById("capability-camera-support"), available.camera ? "Available in this browser" : "Unsupported in this browser");
    text(documentRef.getElementById("capability-screen-support"), available.screen ? "Available in this browser" : "Unsupported in this browser");
    text(documentRef.getElementById("capability-playback-support"), available.playback ? "Available on this device" : "Unsupported on this device");
    text(documentRef.getElementById("capability-vision-support"), available.vision
      ? "Available in chat; model support varies" : "Not available on this page; open Chat");
    setIndicator("automation", "Unavailable in this app UI", "Inactive");
    setIndicator("microphone", available.microphone ? "Available in this browser" : "Unsupported in this browser", activityLabel(capture.microphone));
    if (microphoneState) {
      const stage = capture.voice_stage || "idle";
      const activeCapture = ["local-capture", "audio-capture", "audio-stopping"].includes(stage);
      const transcribing = ["audio-preparing", "cloud-request", "local-model-request"].includes(stage);
      const permission = ({ unknown: "not checked", requesting: "request pending", granted: "granted", denied: "denied", failed: "check failed" })[capture.microphone_permission] || "unknown";
      const elapsed = Math.min(10, Number.isFinite(capture.capture_elapsed_seconds) ? capture.capture_elapsed_seconds : 0);
      microphoneState.textContent = activeCapture
        ? `Recording (${elapsed}/10 seconds); permission ${permission}.`
        : transcribing ? `Transcribing; microphone inactive; permission ${permission}.`
          : ["starting", "local-capture-pending"].includes(stage) ? `Starting voice; permission ${permission}; capture limit 10 seconds.`
            : `Voice off; permission ${permission}; capture limit 10 seconds.`;
    }
    if (microphoneStop) microphoneStop.hidden = !["starting", "local-capture-pending", "local-capture", "audio-capture", "audio-stopping", "audio-ready", "audio-preparing", "cloud-request", "local-model-request"].includes(capture.voice_stage);
    setIndicator("camera", available.camera ? "Available in this browser" : "Unsupported in this browser", activityLabel(capture.camera));
    setIndicator("screen", available.screen ? "Available in this browser" : "Unsupported in this browser", activityLabel(capture.screen));
    setIndicator("playback", available.playback ? "Available on this device" : "Unsupported on this device", activityLabel(capture.local_playback));
  }

  function text(node, value) { if (node) node.textContent = value; }

  function renderActivity(serverCapture = {}) {
    const resolve = (live, reported) => live !== "unknown" ? live
      : reported === "page-reported" ? "unknown" : (reported || "unknown");
    const microphone = resolve(capture.microphone, serverCapture.microphone);
    const screen = resolve(capture.screen, serverCapture.screen);
    const camera = resolve(capture.camera, serverCapture.camera);
    const playback = resolve(capture.local_playback, serverCapture.local_playback);
    const remote = capture.remote_request === "none" ? "none reported" : capture.remote_request;
    text(activity, `Microphone: ${microphone || "unknown"}. Screen capture: ${screen || "unknown"}. Camera: ${camera || "unknown"}. Local playback: ${playback || "unknown"}. Remote cancellation: ${remote === "none reported" ? "unknown unless a provider confirms" : "unknown; request may still be running"}.`);
    capture = { ...capture, microphone, screen, camera, local_playback: playback };
    renderCapabilities();
  }

  function renderPermissions(items = []) {
    if (!permissions) return;
    permissions.replaceChildren();
    if (!items.length) {
      const empty = documentRef.createElement("li");
      empty.textContent = "Permissions are unavailable until owner sign-in.";
      permissions.append(empty);
      return;
    }
    for (const permission of items) {
      const row = documentRef.createElement("li");
      row.textContent = permission;
      permissions.append(row);
    }
  }

  function renderGrants(items = []) {
    if (!grants) return;
    grants.replaceChildren();
    if (!items.length) {
      const empty = documentRef.createElement("li");
      empty.textContent = "No session grants are active or recorded for this session.";
      grants.append(empty);
      return;
    }
    for (const item of items) {
      const row = documentRef.createElement("li");
      const label = documentRef.createElement("span");
      label.textContent = `${item.capability_id}: ${item.status}; scope ${item.scope_type}:${item.scope_id}; expires ${item.expires_at}`;
      row.append(label);
      if (item.status === "active") {
        const revoke = documentRef.createElement("button");
        revoke.type = "button";
        revoke.textContent = "Revoke";
        revoke.addEventListener("click", () => revokeGrant(item.grant_id));
        row.append(revoke);
      }
      grants.append(row);
    }
  }

  async function csrfToken() {
    const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error("Sign in to manage the emergency stop.");
    return (await response.json()).csrf;
  }

  async function refresh() {
    try {
      const response = await fetchImpl("/api/local/emergency-stop", { credentials: "same-origin", cache: "no-store" });
      if (response.status === 401) throw new Error("Sign in to view safety status.");
      if (!response.ok) throw new Error("Safety status is unavailable.");
      const data = await response.json();
      stopped = data.stopped === true;
      if (previousStopped !== stopped) {
        const EventType = windowRef?.CustomEvent || globalThis.CustomEvent;
        if (typeof EventType === "function") {
          windowRef?.dispatchEvent?.(new EventType(stopped ? "ersel:emergency-stop" : "ersel:emergency-resumed"));
        }
        previousStopped = stopped;
      }
      text(state, stopped
        ? `Emergency stop is active since ${data.stopped_at}. New protected actions are blocked.`
        : "Emergency stop is inactive. Protected actions follow their normal permissions.");
      stopButton.disabled = stopped;
      resumeButton.disabled = !stopped;
      renderGrants(data.session_grants);
      renderPermissions(data.active_capabilities);
      renderActivity(data.capture);
      return data;
    } catch (error) {
      text(state, error.message || "Safety status is unavailable.");
      stopButton.disabled = false;
      resumeButton.disabled = true;
      return null;
    }
  }

  async function post(path, body = {}) {
    const csrf = await csrfToken();
    const response = await fetchImpl(path, {
      method: "POST", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Safety action failed.");
    return payload;
  }

  async function stop() {
    text(state, "Stopping local capture and playback, then blocking new protected actions…");
    windowRef?.dispatchEvent?.(new windowRef.CustomEvent("ersel:emergency-stop"));
    stopButton.disabled = true;
    try {
      await post("/api/local/emergency-stop/stop");
      await refresh();
    } catch (error) {
      text(state, `${error.message} Local capture/playback stop was still requested in this page.`);
      stopButton.disabled = false;
    }
  }

  async function resume() {
    if (!confirmImpl("Resume protected actions for this app process? Any remote work already sent may still be running.")) return;
    resumeButton.disabled = true;
    try {
      await post("/api/local/emergency-stop/resume", { confirmed: true });
      windowRef?.dispatchEvent?.(new windowRef.CustomEvent("ersel:emergency-resumed"));
      await refresh();
    } catch (error) {
      text(state, error.message || "Could not resume protected actions.");
      resumeButton.disabled = false;
    }
  }

  async function revokeGrant(grantId) {
    try {
      await post(`/api/capabilities/grants/${encodeURIComponent(grantId)}/revoke`);
      await refresh();
    } catch (error) { text(state, error.message || "Grant could not be revoked."); }
  }

  windowRef?.addEventListener?.("ersel:voice-activity", event => {
    const previous = [capture.microphone, capture.voice_stage, capture.local_playback, capture.remote_request].join("|");
    capture = { ...capture, ...(event.detail || {}) };
    renderCapabilities();
    if (previous !== [capture.microphone, capture.voice_stage, capture.local_playback, capture.remote_request].join("|")) renderActivity();
  });
  microphoneStop?.addEventListener("click", () => {
    const EventType = windowRef?.Event || globalThis.Event;
    if (typeof EventType === "function") windowRef?.dispatchEvent?.(new EventType("ersel:voice-stop"));
  });
  windowRef?.addEventListener?.("ersel:screen-capture-activity", event => {
    capture = { ...capture, screen: event.detail?.state || "unknown" };
    renderCapabilities();
    renderActivity();
  });
  windowRef?.addEventListener?.("ersel:camera-activity", event => {
    capture = { ...capture, camera: event.detail?.state || "unknown" };
    renderCapabilities();
    renderActivity();
  });
  stopButton.addEventListener("click", () => stop());
  resumeButton.addEventListener("click", () => resume());
  renderCapabilities();
  void refresh();
  return { refresh, stop, resume };
}

if (typeof document !== "undefined") mountEmergencyStop();

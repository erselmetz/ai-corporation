export function mountEmergencyStop({
  documentRef = document,
  windowRef = globalThis.window,
  fetchImpl = fetch,
  confirmImpl = globalThis.confirm ?? (() => false),
} = {}) {
  const stopButton = documentRef.getElementById("emergency-stop");
  if (!stopButton) return null;
  const resumeButton = documentRef.getElementById("emergency-resume");
  const state = documentRef.getElementById("emergency-state");
  const grants = documentRef.getElementById("emergency-grants");
  const activity = documentRef.getElementById("emergency-activity");
  let stopped = false;
  let capture = { microphone: "unknown", screen: "unknown", local_playback: "unknown", remote_request: "none" };
  let previousStopped = null;

  function text(node, value) { if (node) node.textContent = value; }

  function renderActivity(serverCapture = {}) {
    const microphone = capture.microphone === "unknown" ? serverCapture.microphone : capture.microphone;
    const screen = capture.screen === "unknown" ? serverCapture.screen : capture.screen;
    const playback = capture.local_playback === "unknown" ? serverCapture.local_playback : capture.local_playback;
    const remote = capture.remote_request === "none" ? "none reported" : capture.remote_request;
    text(activity, `Microphone: ${microphone || "unknown"}. Screen capture: ${screen || "unknown"}. Camera: not used by this app. Local playback: ${playback || "unknown"}. Remote cancellation: ${remote === "none reported" ? "unknown unless a provider confirms" : "unknown; request may still be running"}.`);
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
      label.textContent = `${item.capability_id}: ${item.status}; expires ${item.expires_at}`;
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
    capture = event.detail || capture;
    return refresh();
  });
  windowRef?.addEventListener?.("ersel:screen-capture-activity", event => {
    capture = { ...capture, screen: event.detail?.state || "unknown" };
    renderActivity();
  });
  stopButton.addEventListener("click", () => stop());
  resumeButton.addEventListener("click", () => resume());
  void refresh();
  return { refresh, stop, resume };
}

if (typeof document !== "undefined") mountEmergencyStop();

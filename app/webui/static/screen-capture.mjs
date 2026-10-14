const MAX_BYTES = 2 * 1024 * 1024;
const MAX_DIMENSION = 4096;
const MAX_PIXELS = 8_000_000;
const SURFACES = new Set(["monitor", "window", "browser"]);

function base64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

function encode(canvas, quality) {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}

export async function captureScreenFrame({
  mediaDevices = globalThis.navigator?.mediaDevices,
  createVideo = () => document.createElement("video"),
  createCanvas = () => document.createElement("canvas"),
  now = () => new Date(),
  blocked = () => false,
  onStream = () => {},
} = {}) {
  if (typeof mediaDevices?.getDisplayMedia !== "function") {
    return { status: "unavailable", message: "This browser does not support screen capture." };
  }
  if (blocked()) return { status: "stopped", message: "Capture was blocked by the emergency stop." };

  let stream;
  let video;
  try {
    // Calling directly from the button handler preserves the user-activation requirement.
    stream = await mediaDevices.getDisplayMedia({ video: true, audio: false });
    onStream(stream);
    if (blocked()) return { status: "stopped", message: "Capture stopped before the frame was read." };
    const track = stream.getVideoTracks?.()[0];
    if (!track || track.readyState === "ended") {
      return { status: "unavailable", message: "The selected display is no longer available." };
    }
    const settings = track.getSettings?.() || {};
    const surface = settings.displaySurface;
    if (!SURFACES.has(surface)) {
      return { status: "unavailable", message: "The selected display type could not be verified." };
    }
    video = createVideo();
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    await video.play();
    if (blocked()) return { status: "stopped", message: "Capture stopped before the frame was read." };
    const sourceWidth = Number(video.videoWidth || settings.width);
    const sourceHeight = Number(video.videoHeight || settings.height);
    if (!Number.isSafeInteger(sourceWidth) || !Number.isSafeInteger(sourceHeight)
        || sourceWidth < 1 || sourceHeight < 1) {
      return { status: "unavailable", message: "The selected display dimensions are unavailable." };
    }
    const scale = Math.min(1, MAX_DIMENSION / sourceWidth, MAX_DIMENSION / sourceHeight,
      Math.sqrt(MAX_PIXELS / (sourceWidth * sourceHeight)));
    const width = Math.max(1, Math.floor(sourceWidth * scale));
    const height = Math.max(1, Math.floor(sourceHeight * scale));
    const canvas = createCanvas();
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) return { status: "unavailable", message: "Image capture is unavailable." };
    context.drawImage(video, 0, 0, width, height);
    const capturedAt = now();
    let blob = null;
    for (const quality of [0.88, 0.78, 0.68, 0.58, 0.48]) {
      blob = await encode(canvas, quality);
      if (blob && blob.size <= MAX_BYTES) break;
    }
    if (!blob || blob.size > MAX_BYTES) {
      return { status: "unavailable", message: "The selected display could not fit the image size limit." };
    }
    if (blocked()) return { status: "stopped", message: "Capture stopped before attachment." };
    const bytes = new Uint8Array(await blob.arrayBuffer());
    return {
      status: "captured",
      media_type: "image/jpeg",
      data_base64: base64(bytes),
      display_surface: surface,
      width,
      height,
      captured_at: capturedAt.toISOString(),
    };
  } catch (error) {
    if (blocked()) return { status: "stopped", message: "Capture was stopped or canceled." };
    const name = error?.name;
    return {
      status: name === "NotAllowedError" || name === "AbortError" ? "denied" : "failed",
      message: name === "NotAllowedError" || name === "AbortError"
        ? "Screen capture was denied or canceled." : "Screen capture is unavailable.",
    };
  } finally {
    if (video) video.srcObject = null;
    for (const track of stream?.getTracks?.() || []) {
      try { track.stop(); } catch { /* continue stopping remaining tracks */ }
    }
    onStream(null);
  }
}

export function mountScreenCapture({
  documentRef = document,
  windowRef = globalThis.window,
  fetchImpl = fetch,
  mediaDevices = globalThis.navigator?.mediaDevices,
} = {}) {
  const button = documentRef.getElementById("chat-capture-screen");
  const state = documentRef.getElementById("chat-capture-status");
  const conversation = documentRef.getElementById("chat-conversation");
  if (!button || !state || !conversation) return null;

  let stopped = false;
  let authorized = false;
  let activeStream = null;
  let busy = false;

  const activity = (value, activityState = "inactive") => {
    state.textContent = value;
    windowRef?.dispatchEvent?.(new windowRef.CustomEvent("ersel:screen-capture-activity", {
      detail: { state: activityState },
    }));
  };
  const update = () => {
    button.disabled = stopped || busy || !authorized || !conversation.value;
  };
  async function refreshAuthorization() {
    try {
      const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) { authorized = false; update(); return; }
      const session = await response.json();
      authorized = Array.isArray(session.permissions)
        && session.permissions.includes("chat:send")
        && session.permissions.includes("screen:capture");
    } catch { authorized = false; }
    update();
  }

  async function capture() {
    if (busy || stopped) return;
    if (!conversation.value) { activity("Start or select an open conversation before capture."); return; }
    if (!authorized) { activity("Sign in with screen:capture and chat:send permissions to capture."); return; }
    const conversationId = conversation.value;
    busy = true;
    update();
    activity("Choose one display or window in the system picker; audio is off.", "unknown");
    const frame = await captureScreenFrame({
      mediaDevices,
      blocked: () => stopped,
      onStream: (stream) => {
        activeStream = stream;
        activity(stream ? "Screen capture active for one frame; audio is off." : "Screen capture is inactive.", stream ? "active" : "inactive");
      },
    });
    activeStream = null;
    if (frame.status !== "captured") {
      activity(frame.message || "Screen capture is unavailable.", frame.status === "stopped" ? "inactive" : frame.status);
      busy = false;
      update();
      return;
    }
    try {
      const sessionResponse = await fetchImpl("/api/local/session", {
        credentials: "same-origin", cache: "no-store",
      });
      if (!sessionResponse.ok) throw new Error("Sign in again before attaching this screen frame.");
      const session = await sessionResponse.json();
      if (stopped) throw new Error("Emergency stop is active; the frame was discarded.");
      const response = await fetchImpl(`/api/chat/conversations/${encodeURIComponent(conversationId)}/screen-captures`, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": session.csrf },
        body: JSON.stringify({
          media_type: frame.media_type,
          data_base64: frame.data_base64,
          display_surface: frame.display_surface,
          captured_at: frame.captured_at,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "The screen frame was not attached.");
      activity(`Captured ${frame.display_surface} ${frame.width}x${frame.height} at ${frame.captured_at}. Attached temporarily; not sent to a Provider.`, "inactive");
    } catch (error) {
      activity(error.message || "The screen frame was not attached.", "failed");
    } finally {
      busy = false;
      update();
    }
  }

  function stop() {
    stopped = true;
    for (const track of activeStream?.getTracks?.() || []) {
      try { track.stop(); } catch { /* best effort */ }
    }
    activeStream = null;
    if (busy) activity("Emergency stop requested; waiting for the system picker to close and discarding any frame.", "uncertain_stop");
    update();
  }
  function resume() { stopped = false; update(); }
  button.addEventListener("click", capture);
  conversation.addEventListener("change", update);
  windowRef?.addEventListener?.("ersel:emergency-stop", stop);
  windowRef?.addEventListener?.("ersel:emergency-resumed", resume);
  void refreshAuthorization();
  return { capture, refreshAuthorization, stop, resume };
}

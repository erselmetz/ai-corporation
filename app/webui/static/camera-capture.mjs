const MAX_BYTES = 2 * 1024 * 1024;
const MAX_DIMENSION = 4096;
const MAX_PIXELS = 8_000_000;

function base64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function encode(canvas, quality) {
  return new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", quality));
}

export async function captureCameraFrame({
  mediaDevices = globalThis.navigator?.mediaDevices,
  createVideo = () => document.createElement("video"),
  createCanvas = () => document.createElement("canvas"),
  now = () => new Date(),
  blocked = () => false,
  onStream = () => {},
  desktopBridge = globalThis.window?.desktopBridge,
} = {}) {
  if (typeof mediaDevices?.getUserMedia !== "function") {
    return { status: "unavailable", message: "This browser does not support camera capture." };
  }
  if (blocked()) return { status: "stopped", message: "Capture was blocked by the emergency stop." };
  let stream;
  let video;
  try {
    if (desktopBridge?.requestCamera && !(await desktopBridge.requestCamera())) {
      return { status: "denied", message: "Camera access was denied." };
    }
    if (blocked()) return { status: "stopped", message: "Capture stopped before camera access." };
    stream = await mediaDevices.getUserMedia({ video: true, audio: false });
    onStream(stream);
    const tracks = stream.getTracks?.() || [];
    const track = stream.getVideoTracks?.()[0];
    if (!track || track.readyState === "ended" || tracks.some(item => item.kind === "audio")) {
      return { status: "unavailable", message: "A video-only camera stream could not be verified." };
    }
    if (blocked()) return { status: "stopped", message: "Capture stopped before the frame was read." };
    video = createVideo();
    video.muted = true; video.playsInline = true; video.srcObject = stream;
    await video.play();
    const sourceWidth = Number(video.videoWidth);
    const sourceHeight = Number(video.videoHeight);
    if (!Number.isSafeInteger(sourceWidth) || !Number.isSafeInteger(sourceHeight)
        || sourceWidth < 1 || sourceHeight < 1) {
      return { status: "unavailable", message: "Camera dimensions are unavailable." };
    }
    const scale = Math.min(1, MAX_DIMENSION / sourceWidth, MAX_DIMENSION / sourceHeight,
      Math.sqrt(MAX_PIXELS / (sourceWidth * sourceHeight)));
    const width = Math.max(1, Math.floor(sourceWidth * scale));
    const height = Math.max(1, Math.floor(sourceHeight * scale));
    const canvas = createCanvas(); canvas.width = width; canvas.height = height;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) return { status: "unavailable", message: "Camera image processing is unavailable." };
    context.drawImage(video, 0, 0, width, height);
    let blob = null;
    for (const quality of [0.88, 0.78, 0.68, 0.58, 0.48]) {
      blob = await encode(canvas, quality);
      if (blob && blob.size <= MAX_BYTES) break;
    }
    if (!blob || blob.size > MAX_BYTES) return { status: "unavailable", message: "Camera frame exceeds the image limit." };
    if (blocked()) return { status: "stopped", message: "Capture stopped before attachment." };
    return { status: "captured", media_type: "image/jpeg", data_base64: base64(new Uint8Array(await blob.arrayBuffer())), captured_at: now().toISOString(), width, height };
  } catch (error) {
    if (blocked()) return { status: "stopped", message: "Capture was stopped or canceled." };
    return { status: error?.name === "NotAllowedError" || error?.name === "AbortError" ? "denied" : "failed",
      message: error?.name === "NotAllowedError" || error?.name === "AbortError" ? "Camera access was denied or canceled." : "Camera capture is unavailable." };
  } finally {
    if (video) video.srcObject = null;
    for (const track of stream?.getTracks?.() || []) { try { track.stop(); } catch { /* stop remaining tracks */ } }
    onStream(null);
  }
}

export function mountCameraCapture({ documentRef = document, windowRef = globalThis.window,
  fetchImpl = fetch, mediaDevices = globalThis.navigator?.mediaDevices } = {}) {
  const button = documentRef.getElementById("chat-capture-camera");
  const state = documentRef.getElementById("chat-camera-status");
  const conversation = documentRef.getElementById("chat-conversation");
  if (!button || !state || !conversation) return null;
  let stopped = false; let authorized = false; let busy = false; let activeStream = null;
  const activity = (text, active = false) => {
    state.textContent = text;
    windowRef?.dispatchEvent?.(new windowRef.CustomEvent("ersel:camera-activity", { detail: { state: active ? "active" : "inactive" } }));
  };
  const update = () => { button.disabled = stopped || busy || !authorized || !conversation.value; };
  async function refreshAuthorization() {
    try {
      const [sessionResponse, stopResponse] = await Promise.all([
        fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" }),
        fetchImpl("/api/local/emergency-stop", { credentials: "same-origin", cache: "no-store" }),
      ]);
      const session = sessionResponse.ok ? await sessionResponse.json() : {};
      const stop = stopResponse.ok ? await stopResponse.json() : null;
      authorized = Array.isArray(session.permissions) && session.permissions.includes("chat:send")
        && session.permissions.includes("camera:capture") && stop !== null;
      if (stop?.stopped === true) {
        stopped = true;
        activity("Emergency stop is active; camera capture is blocked.");
      }
    } catch { authorized = false; }
    update();
  }
  async function capture() {
    if (busy || stopped) return;
    if (!conversation.value) { activity("Start or select an open conversation before capture."); return; }
    if (!authorized) { activity("Sign in with camera:capture and chat:send permissions to capture."); return; }
    try {
      const response = await fetchImpl("/api/local/emergency-stop", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error();
      if ((await response.json()).stopped === true) { stopped = true; update(); activity("Emergency stop is active; camera capture is blocked."); return; }
    } catch { activity("Could not confirm emergency-stop status; camera capture is blocked."); return; }
    busy = true; update();
    activity("Camera permission requested for one video-only frame.");
    const frame = await captureCameraFrame({ mediaDevices, blocked: () => stopped, onStream: stream => {
      activeStream = stream;
      activity(stream ? "Camera capture active: reading one frame, with audio disabled." : "Camera is off.", Boolean(stream));
    } });
    activeStream = null;
    if (frame.status !== "captured" || stopped) { activity(stopped ? "Emergency stop active; camera frame discarded." : frame.message); busy = false; update(); return; }
    try {
      const sessionResponse = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      if (!sessionResponse.ok) throw new Error("Sign in again before attaching this camera frame.");
      const session = await sessionResponse.json();
      if (stopped) throw new Error("Emergency stop is active; the frame was discarded.");
      const response = await fetchImpl(`/api/chat/conversations/${encodeURIComponent(conversation.value)}/camera-captures`, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": session.csrf },
        body: JSON.stringify({ media_type: frame.media_type, data_base64: frame.data_base64, captured_at: frame.captured_at }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "The camera frame was not attached.");
      activity(`Captured one camera frame ${frame.width}x${frame.height} at ${frame.captured_at}. Temporarily attached; not sent until selected and consented.`);
      windowRef?.dispatchEvent?.(new windowRef.CustomEvent("ersel:chat-images-changed"));
    } catch (error) { activity(error.message || "The camera frame was not attached."); }
    finally { busy = false; update(); }
  }
  function stop() {
    stopped = true; for (const track of activeStream?.getTracks?.() || []) { try { track.stop(); } catch { /* best effort */ } }
    activeStream = null; activity("Emergency stop active; capture stopped and frame discarded."); update();
  }
  function resume() { stopped = false; update(); }
  button.addEventListener("click", capture); conversation.addEventListener("change", update);
  windowRef?.addEventListener?.("ersel:emergency-stop", stop);
  windowRef?.addEventListener?.("ersel:emergency-resumed", resume);
  void refreshAuthorization();
  return { capture, refreshAuthorization, stop, resume };
}

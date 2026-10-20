export function mountQuickStart({ documentRef = document, windowRef = window, fetchImpl = fetch, autoInspect = true } = {}) {
  const panel = documentRef.getElementById("local-quick-start");
  const state = documentRef.getElementById("local-quick-start-state");
  const action = documentRef.getElementById("local-quick-start-action");
  const bridge = windowRef.desktopBridge;
  if (!(panel && state && action && bridge)) return null;
  panel.hidden = false;
  let mode = "retry";
  let preview = null;
  let busy = false;
  bridge.onOllamaInstallerProgress?.((progress) => {
    if (mode === "install" && progress.total > 0) {
      state.textContent = `Downloading verified Ollama installer… ${Math.floor(100 * progress.downloaded / progress.total)}%`;
    }
  });
  const csrf = async () => {
    const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error("The local session expired. Restart the app to restore access.");
    const value = await response.json();
    if (typeof value.csrf !== "string") throw new Error("The local session could not be verified.");
    return value.csrf;
  };
  const post = async (path, body = {}) => fetchImpl(path, {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json", "X-Local-CSRF": await csrf() },
    body: JSON.stringify(body),
  });
  async function inspect() {
    busy = true; action.disabled = true; action.textContent = "Checking…"; preview = null;
    action.hidden = false;
    try {
      const response = await post("/api/local/first-run/ollama/status");
      if (!response.ok) throw new Error("Ollama status could not be checked. Press Retry.");
      const result = await response.json();
      if (result.state !== "available") {
        const installed = await bridge.isOllamaInstalled().catch(() => true);
        mode = installed ? "retry" : "install";
        state.textContent = installed
          ? "Ollama is not running. Start it, then press Retry."
          : "Ollama is not installed. Use the existing verified installer if you choose to install it.";
        action.textContent = installed ? "Retry" : "Install Ollama";
        return;
      }
      if (result.model_installed === true) {
        state.textContent = `CPU inference may be slow; actual hardware use and response speed have not been measured.`;
        mode = "none"; action.hidden = true; return;
      }
      mode = "download";
      try {
        const sizeResponse = await post("/api/local/first-run/ollama/model-preview");
        const size = await sizeResponse.json();
        if (!sizeResponse.ok || !Number.isSafeInteger(size.manifest_bytes)) throw new Error();
        preview = size;
        state.textContent = `No model is installed. Download ${size.model_id} (about ${(size.manifest_bytes / 1_000_000_000).toFixed(2)} GB)?`;
        action.textContent = `Download ${size.model_id}`;
      } catch {
        state.textContent = "No model is installed. The download size could not be verified; retry later.";
        action.textContent = "Retry"; mode = "retry";
      }
    } catch (error) {
      state.textContent = error instanceof Error ? error.message : "Ollama status could not be checked. Press Retry.";
      mode = "retry"; action.textContent = "Retry";
    } finally { busy = false; action.disabled = false; }
  }
  async function install() {
    const result = await bridge.previewOllamaInstaller();
    if (!result?.ok || !result.preview) throw new Error(result?.message || "Verified installer details are unavailable.");
    const installed = await bridge.installOllama(result.preview);
    if (installed?.canceled) { state.textContent = "Ollama installation canceled. Nothing was installed."; return; }
    if (!installed?.ok) throw new Error(installed?.message || "The verified Ollama installer could not be started.");
    state.textContent = "The installer finished. Start Ollama, then press Retry.";
    mode = "retry"; action.textContent = "Retry";
  }
  async function download() {
    if (!preview || !windowRef.confirm(`Download ${preview.model_id} (${(preview.manifest_bytes / 1_000_000_000).toFixed(2)} GB) from Ollama?`)) return;
    const response = await fetch("/api/local/first-run/ollama/pull", {
      method: "POST", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": await csrf() },
      body: JSON.stringify({ confirmed: true, manifest_digest: preview.manifest_digest, manifest_bytes: preview.manifest_bytes }),
    });
    if (!response.ok || !response.body) throw new Error("Confirmed download could not start.");
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let pending = "";
    while (true) {
      const { value, done } = await reader.read(); pending += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = pending.split("\n"); pending = lines.pop() || "";
      for (const line of lines) if (line) {
        const event = JSON.parse(line);
        if (event.event === "error") throw new Error(event.message || "Model download failed. Press Retry.");
        if (event.setup_complete === true) { windowRef.location.assign(`/ui/chat?desktop=1&conversation=${encodeURIComponent(event.conversation_id)}`); return; }
        if (event.event === "progress") state.textContent = event.total > 0
          ? `Downloading ${preview.model_id}… ${Math.floor(100 * event.completed / event.total)}%`
          : `Downloading ${preview.model_id}… ${String(event.status || "working")}`;
      }
      if (done) break;
    }
    throw new Error("Download ended before Ollama confirmed the model. Press Retry.");
  }
  action.addEventListener("click", async () => {
    if (busy) return;
    busy = true; action.disabled = true;
    try { if (mode === "install") await install(); else if (mode === "download") await download(); else await inspect(); }
    catch (error) { state.textContent = error instanceof Error ? error.message : "The local action failed. Retry."; }
    finally { busy = false; action.disabled = false; }
  });
  if (autoInspect) void inspect();
  return { inspect, getMode: () => mode };
}

if (typeof document !== "undefined") mountQuickStart();

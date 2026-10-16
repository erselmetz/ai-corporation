"use client";

import { useEffect, useRef, useState } from "react";

type SetupState = { enabled: boolean; completed: boolean; skipped: boolean; credential_needs_reentry: boolean };
type Preview = { model_id: string; manifest_digest: string; manifest_bytes: number; available_space_bytes: number | null; destination: string; registry_url: string };
type InstallerPreview = { version: string; source: string; size_bytes: number; sha256: string; publisher: string };
type DesktopBridge = {
  previewOllamaInstaller: () => Promise<{ ok: boolean; preview?: InstallerPreview; message?: string }>;
  installOllama: (preview: InstallerPreview) => Promise<{ ok: boolean; canceled?: boolean; message?: string }>;
  onOllamaInstallerProgress: (callback: (progress: { downloaded: number; total: number }) => void) => () => void;
};

async function sessionCsrf(): Promise<string> {
  const response = await fetch("/api/local/session", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error("Your local owner session expired. Restart the app to sign in again.");
  const session = await response.json();
  if (typeof session.csrf !== "string") throw new Error("The owner session could not be verified.");
  return session.csrf;
}

async function post(path: string, body: unknown = {}): Promise<Response> {
  const csrf = await sessionCsrf();
  return fetch(path, {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
    body: JSON.stringify(body),
  });
}

export default function FirstRunWizard() {
  const [setup, setSetup] = useState<SetupState | null>(null);
  const [choice, setChoice] = useState<"ollama" | "gemini" | null>(null);
  const [status, setStatus] = useState("Checking whether first-run setup is available…");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [modelInstalled, setModelInstalled] = useState(false);
  const [installerPreview, setInstallerPreview] = useState<InstallerPreview | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [rememberKey, setRememberKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [catalogConfirmed, setCatalogConfirmed] = useState(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const bridge = (window as Window & { desktopBridge?: DesktopBridge }).desktopBridge;
    if (!bridge) return;
    return bridge.onOllamaInstallerProgress((progress) => {
      if (progress.total > 0) setStatus(`Downloading verified Ollama installer… ${Math.floor(100 * progress.downloaded / progress.total)}%`);
    });
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/local/first-run", { credentials: "same-origin", cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return null;
        return response.json() as Promise<SetupState>;
      })
      .then((data) => {
        if (!active) return;
        setSetup(data);
        if (data?.enabled && !data.completed && !data.skipped) {
          setStatus(data.credential_needs_reentry
            ? "Reconnect Gemini to restore chat. The API key was not saved across restart."
            : "Choose a provider for your Coordinator.");
        }
      })
      .catch(() => { if (active) setStatus("First-run setup could not be checked. Retry or open the regular workspace."); });
    return () => { active = false; controller.current?.abort(); };
  }, []);

  async function skip() {
    setBusy(true);
    try {
      const response = await post("/api/local/first-run/skip");
      if (!response.ok) throw new Error("Setup could not be skipped. Retry.");
      setSetup((current) => current ? { ...current, skipped: true } : current);
      setStatus("Setup skipped. You can configure a provider later in Settings.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Setup could not be skipped."); }
    finally { setBusy(false); }
  }

  async function inspectOllama() {
    let serviceMissing = false;
    setBusy(true); setPreview(null); setStatus("Checking the local Ollama service…");
    try {
      const response = await post("/api/local/first-run/ollama/status");
      const result = await response.json();
      if (!response.ok) throw new Error("Ollama status could not be checked.");
      if (result.state !== "available") {
        serviceMissing = true;
        throw new Error("Ollama is not running at 127.0.0.1:11434. If it is installed, start it and retry. Hardware feasibility remains unknown.");
      }
      setModelInstalled(result.model_installed === true);
      setStatus(result.model_installed
        ? "The recommended model is already installed. Confirm it against Ollama's current inventory."
        : "Ollama is running. Fetch the official registry size estimate before choosing whether to download.");
      if (result.model_installed === true) return;
      const sizeResponse = await post("/api/local/first-run/ollama/model-preview");
      const size = await sizeResponse.json();
      if (!sizeResponse.ok) throw new Error(typeof size.detail === "string" ? size.detail : "Model size is unavailable.");
      setPreview(size as Preview);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Ollama check failed. Retry or skip.");
      const bridge = (window as Window & { desktopBridge?: DesktopBridge }).desktopBridge;
      if (serviceMissing && bridge) {
        const result = await bridge.previewOllamaInstaller().catch(() => ({ ok: false, message: "Official installer metadata is unavailable." }));
        if (result.ok && "preview" in result && result.preview) setInstallerPreview(result.preview);
      }
    }
    finally { setBusy(false); }
  }

  async function downloadModel() {
    if (!preview || !window.confirm(`Download ${preview.model_id} (${(preview.manifest_bytes / 1_000_000_000).toFixed(2)} GB, full layer estimate) from Ollama? Partial data may remain if canceled.`)) return;
    const request = new AbortController(); controller.current = request; setBusy(true); setStatus("Downloading the owner-confirmed Ollama model…");
    try {
      const csrf = await sessionCsrf();
      const response = await fetch("/api/local/first-run/ollama/pull", {
        method: "POST", credentials: "same-origin", cache: "no-store", signal: request.signal,
        headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
        body: JSON.stringify({ confirmed: true, manifest_digest: preview.manifest_digest, manifest_bytes: preview.manifest_bytes }),
      });
      if (!response.ok || !response.body) {
        const result = await response.json().catch(() => ({}));
        throw new Error(typeof result.detail === "string" ? result.detail : "Ollama download could not start.");
      }
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let pending = "";
      while (true) {
        const { value, done } = await reader.read(); pending += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = pending.split("\n"); pending = lines.pop() || "";
        for (const line of lines) {
          if (!line) continue;
          const event = JSON.parse(line);
          if (event.event === "error") throw new Error(event.message || "Ollama download failed. Retry or skip.");
          if (event.setup_complete === true) {
            window.location.assign(`/ui/chat?conversation=${encodeURIComponent(event.conversation_id)}`);
            return;
          }
          if (event.event === "progress") setStatus(typeof event.total === "number" && event.total > 0
            ? `Downloading model… ${Math.floor(100 * event.completed / event.total)}%`
            : `Downloading model… ${String(event.status || "working")}`);
        }
        if (done) break;
      }
      throw new Error("The Ollama download ended before installation was confirmed. Retry or skip.");
    } catch (error) {
      setStatus(error instanceof Error && error.name === "AbortError"
        ? "Download canceled. Ollama may retain partial data and can reuse it on retry."
        : error instanceof Error ? error.message : "Ollama download failed. Retry or skip.");
    } finally { controller.current = null; setBusy(false); }
  }

  async function useInstalledModel() {
    setBusy(true); setStatus("Rechecking Ollama's installed-model inventory…");
    try {
      const response = await post("/api/local/first-run/ollama/use-installed", {});
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Installed model could not be confirmed.");
      window.location.assign(`/ui/chat?conversation=${encodeURIComponent(result.conversation_id)}`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Installed model could not be confirmed. Retry or skip."); }
    finally { setBusy(false); }
  }

  async function installOllama() {
    const bridge = (window as Window & { desktopBridge?: DesktopBridge }).desktopBridge;
    if (!bridge || !installerPreview) { setStatus("The verified installer is available only in the Windows desktop app."); return; }
    setBusy(true); setStatus("Waiting for your confirmation in the Windows app…");
    try {
      const result = await bridge.installOllama(installerPreview);
      if (result.canceled) { setStatus("Ollama installation canceled. Nothing was installed."); return; }
      if (!result.ok) throw new Error(result.message || "The verified Ollama installer could not be started.");
      setInstallerPreview(null);
      setStatus("The installer exited. Check the Ollama service, then retry the local check.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Ollama installation failed. Retry or skip."); }
    finally { setBusy(false); }
  }

  async function connectGemini() {
    if (!catalogConfirmed) { setCatalogConfirmed(true); setStatus("Next, click again to send this API key to Google over HTTPS for a model-catalog check. No chat prompt is sent; each Gemini chat turn has separate consent."); return; }
    setBusy(true); setStatus("Checking Gemini model access with Google…");
    try {
      const response = await post("/api/local/first-run/gemini/complete", { api_key: apiKey, remember_key: rememberKey });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Gemini setup failed. Retry or skip.");
      setApiKey("");
      window.location.assign(`/ui/chat?conversation=${encodeURIComponent(result.conversation_id)}`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Gemini setup failed. Retry or skip."); }
    finally { setBusy(false); setCatalogConfirmed(false); }
  }

  if (setup === null) return <section className="first-run-wizard"><h2>Set up your Coordinator</h2><p role="status">{status}</p><button type="button" disabled={busy} onClick={async () => {
    setBusy(true);
    try {
      const response = await fetch("/api/local/first-run", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("First-run state could not be loaded. Check the local owner session.");
      const data = await response.json();
      setSetup(data);
      setStatus(data.credential_needs_reentry ? "Reconnect Gemini; the key was not saved across restart." : "Choose a provider for your Coordinator.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "First-run state could not be loaded."); }
    finally { setBusy(false); }
  }}>Retry setup check</button></section>;
  if (!setup.enabled || setup.completed || setup.skipped) return null;
  return <section className="first-run-wizard" aria-labelledby="first-run-title">
    <p className="eyebrow">OWNER CONTROLLED · FIRST RUN</p>
    <h2 id="first-run-title">Set up your Coordinator</h2>
    <p>Choose one provider. No download, installation, or cloud request starts until you confirm it.</p>
    <div className="first-run-choices">
      <button type="button" disabled={busy} onClick={() => { setChoice("ollama"); void inspectOllama(); }}>Use Ollama (local)</button>
      <button type="button" disabled={busy} onClick={() => { setChoice("gemini"); setPreview(null); setStatus("Enter an API key restricted to Gemini model discovery and generation."); }}>Use Gemini (online)</button>
    </div>
    {choice === "ollama" && <div className="first-run-panel">
      <p>Recommended model: <strong>llama3.2:3b</strong>. GPU and hardware feasibility are unknown; CPU use may be slow.</p>
      {modelInstalled && <div className="first-run-preview"><p>Ollama reports the recommended model as installed. Hardware feasibility remains unknown.</p><button type="button" disabled={busy} onClick={() => void useInstalledModel()}>Use verified installed model</button></div>}
      {preview && <div className="first-run-preview"><p>Verified full layer estimate: <strong>{(preview.manifest_bytes / 1_000_000_000).toFixed(2)} GB</strong></p><p>Available space at the default model location: {preview.available_space_bytes === null ? "unknown (custom OLLAMA_MODELS location is not inspected)" : `${(preview.available_space_bytes / 1_000_000_000).toFixed(2)} GB`}</p><p>Destination: {preview.destination}</p><p>Source: <code>{preview.registry_url}</code></p><button type="button" disabled={busy} onClick={() => void downloadModel()}>Confirm and download model</button></div>}
      {installerPreview && <div className="first-run-preview"><p>Official installer: {installerPreview.publisher} · {installerPreview.version}</p><p>Size: {(installerPreview.size_bytes / 1_000_000).toFixed(1)} MB · SHA-256: <code>{installerPreview.sha256}</code></p><p>Source: <code>{installerPreview.source}</code>. The Windows installer is started without elevation; review any Windows prompt.</p><button type="button" disabled={busy} onClick={() => void installOllama()}>Review and install Ollama</button></div>}
      <button type="button" disabled={busy} onClick={() => void inspectOllama()}>Retry Ollama check</button>
      {busy && <button type="button" onClick={() => controller.current?.abort()}>Cancel download</button>}
    </div>}
    {choice === "gemini" && <div className="first-run-panel">
      <label htmlFor="first-run-gemini-key">Gemini API key</label><input id="first-run-gemini-key" type="password" autoComplete="off" maxLength={4096} value={apiKey} onChange={(event) => { setApiKey(event.target.value); setCatalogConfirmed(false); }} />
      <label className="first-run-opt-in"><input type="checkbox" checked={rememberKey} onChange={(event) => setRememberKey(event.target.checked)} /> Remember this key encrypted for this Windows user (optional DPAPI).</label>
      <p>Without this opt-in, restart requires entering the key again. Each cloud chat turn asks for separate consent.</p>
      <button type="button" disabled={busy || apiKey.length === 0} onClick={() => void connectGemini()}>{catalogConfirmed ? "Send key and finish setup" : "Review Gemini catalog request"}</button>
    </div>}
    <p role="status" aria-live="polite">{status}</p>
    <button type="button" className="first-run-skip" disabled={busy} onClick={() => void skip()}>Skip for now</button>
  </section>;
}

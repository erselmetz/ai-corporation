"use client";

import { useEffect, useState, type FormEvent } from "react";
import { summarizeHardwareProfile } from "./hardware-summary";

type State = "loading" | "ready" | "empty" | "sign-in" | "denied" | "failed" | "unknown";
type Result = { state: State; message: string; source: string; values?: Record<string, string> };
type Payload = Record<string, unknown>;
type CapabilityPack = { pack_id: string; title: string; state: string; supported: boolean; files: string[];
  download_bytes: number; manifest_digest: string; source: string; compatibility: string; detail: string };
type SpeechModelPreview = { model_id: string; revision: string; state: string; download_bytes: number;
  manifest_digest: string; files: { name: string; size: number; digest: string }[]; source: string; note: string };
type CrashReport = { occurredAt: string; source: string; event: string; reason: string; appVersion: string; exitCode: number | null };
type DesktopRecoveryBridge = {
  readCrashReports: () => Promise<{ ok: boolean; localOnly?: boolean; message?: string; reports?: CrashReport[] }>;
  openDiagnosticsFolder: () => Promise<{ ok: boolean; message?: string }>;
  resetAppData: () => Promise<{ ok: boolean; restarting?: boolean; canceled?: boolean; message?: string }>;
};

const initial = (): Result => ({ state: "loading", message: "Loading current values…", source: "" });

function statusText(state: State) {
  return ({ loading: "Loading", ready: "Current", empty: "Not configured", "sign-in": "Sign in required",
    denied: "Permission unavailable", failed: "Could not load", unknown: "Unknown" } satisfies Record<State, string>)[state];
}

async function boundedGet(path: string) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(path, { credentials: "same-origin", cache: "no-store",
      headers: { Accept: "application/json" }, signal: controller.signal });
    return { status: response.status, body: response.ok ? await response.json() as Payload : null };
  } finally {
    window.clearTimeout(timeout);
  }
}

function record(value: unknown): value is Payload {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readError(status: number): Result {
  if (status === 401) return { state: "sign-in", message: "Sign in again, then refresh this page.", source: "Existing owner-protected API" };
  if (status === 403) return { state: "denied", message: "This session lacks the required read permission. Use the linked page or sign in with an authorized owner session.", source: "Existing permission check" };
  return { state: "failed", message: "The source could not be read. Retry or open its page for details.", source: "Existing API response" };
}

async function readSummary(path: string, permission: string, permissions: Set<string>, summarize: (body: Payload) => Result): Promise<Result> {
  if (!permissions.has(permission)) return {
    state: "denied", message: `This session does not have ${permission}. The source page enforces the same permission.`, source: "Owner session permissions",
  };
  try {
    const response = await boundedGet(path);
    if (response.status !== 200 || !record(response.body)) return readError(response.status);
    return summarize(response.body);
  } catch {
    return { state: "failed", message: "The local source did not respond within 2.5 seconds. Retry or open its page.", source: path };
  }
}

function SettingCard({ title, description, result, href, linkLabel }: {
  title: string; description: string; result: Result; href: string; linkLabel: string;
}) {
  return <article className="settings-card">
    <div className="settings-card-heading"><h3>{title}</h3><span className={`settings-state ${result.state}`} role="status">{statusText(result.state)}</span></div>
    <p>{description}</p>
    <p className="settings-message">{result.message}</p>
    {result.values && <dl className="settings-values">{Object.entries(result.values).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
    <small className="settings-source">Source: {result.source}</small>
    <a className="settings-link" href={href}>{linkLabel} <span aria-hidden="true">→</span></a>
  </article>;
}

function CapabilityPackControls({ permissions }: { permissions: string[] }) {
  const [items, setItems] = useState<CapabilityPack[]>([]);
  const [message, setMessage] = useState("Loading optional local capability packs.");
  const [busy, setBusy] = useState<string | null>(null);
  const canManage = permissions.includes("capability-pack:manage");

  async function refresh() {
    if (!canManage) { setMessage("This owner session does not have capability-pack:manage."); return; }
    try {
      const response = await fetch("/api/capability-packs", { credentials: "same-origin", cache: "no-store" });
      const body = await response.json() as Payload;
      if (!response.ok || !Array.isArray(body.items)) throw new Error(response.status === 401 ? "Sign in again to inspect local packs." : response.status === 403 ? "This session cannot manage optional packs." : "Local pack status is unavailable.");
      setItems(body.items as CapabilityPack[]);
      setMessage("Status reflects installed files and the last self-test run in this app process.");
    } catch (error) { setItems([]); setMessage(error instanceof Error ? error.message : "Local pack status is unavailable."); }
  }
  useEffect(() => { void refresh(); }, [canManage]);

  async function action(pack: CapabilityPack, operation: "install" | "self-test") {
    if (busy) return;
    if (operation === "install") {
      const yes = window.confirm(`${pack.title}\n\nSource: ${pack.source}\nWheel files: ${pack.files.join(", ")}\nTotal download: ${pack.download_bytes.toLocaleString()} bytes\nSHA-256 manifest: ${pack.manifest_digest}\n\nInstall these exact wheels in the isolated local app directory?`);
      if (!yes) { setMessage("Installation cancelled. No files were downloaded."); return; }
    }
    setBusy(pack.pack_id); setMessage(operation === "install" ? `Installing ${pack.title} after owner confirmation.` : `Running ${pack.title} self-test.`);
    try {
      const sessionResponse = await fetch("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      const sessionBody = await sessionResponse.json() as Payload;
      if (!sessionResponse.ok || typeof sessionBody.csrf !== "string") throw new Error("Owner session could not be verified. Refresh and retry.");
      const response = await fetch(`/api/capability-packs/${encodeURIComponent(pack.pack_id)}/${operation}`, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": sessionBody.csrf },
        ...(operation === "install" ? { body: JSON.stringify({ confirmed: true, manifest_digest: pack.manifest_digest }) } : {}),
      });
      const body = await response.json() as Payload;
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Capability pack action failed.");
      setMessage(typeof body.detail === "string" ? body.detail : operation === "install" ? "Pinned pack installed. Run its self-test before use." : `Self-test state: ${String(body.state)}.`);
      await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Capability pack action failed."); }
    finally { setBusy(null); }
  }

  return <section className="settings-section" aria-labelledby="capability-packs-heading">
    <div className="section-heading"><div><p className="eyebrow">OPTIONAL LOCAL SOFTWARE</p><h2 id="capability-packs-heading">Capability packs</h2></div>
      <button className="readiness-refresh" type="button" onClick={() => void refresh()} disabled={busy !== null}>Refresh</button></div>
    <p className="settings-intro">Base install remains small. Exact official PyPI wheels, compatibility, total size, and manifest hash are shown before each owner-confirmed isolated install. Tesseract and speech models are separate and are never downloaded here.</p>
    <p className="settings-message" role="status" aria-live="polite">{message}</p>
    <div className="settings-grid">{items.map(pack => <article className="settings-card" key={pack.pack_id}>
      <div className="settings-card-heading"><h3>{pack.title}</h3><span className={`settings-state ${pack.state === "working" ? "ready" : pack.state === "installed" ? "empty" : "unknown"}`}>{pack.state === "working" ? "Working" : pack.state === "installed" ? "Installed" : "Not installed"}</span></div>
      <p>{pack.compatibility}</p><p className="settings-message">{pack.detail}</p>
      <details><summary>Review {pack.download_bytes.toLocaleString()} bytes and pinned files</summary><p>{pack.files.join(", ")}</p><small className="settings-source">{pack.source}. SHA-256 manifest: {pack.manifest_digest}</small></details>
      <div className="capability-pack-actions"><button type="button" disabled={!pack.supported || pack.state !== "not-installed" || busy !== null} onClick={() => void action(pack, "install")}>Review &amp; install</button>
        <button type="button" disabled={pack.state === "not-installed" || busy !== null} onClick={() => void action(pack, "self-test")}>Test it</button></div>
      {pack.pack_id === "voice" && <LocalVoiceOutputTest permissions={permissions} installed={pack.state !== "not-installed"} />}
    </article>)}</div>
  </section>;
}

function LocalVoiceOutputTest({ permissions, installed }: { permissions: string[]; installed: boolean }) {
  const [state, setState] = useState("Local offline speech test has not run.");
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!installed || !permissions.includes("capability-pack:manage")) return;
    void fetch("/api/local/voice/output-status", { credentials: "same-origin", cache: "no-store" })
      .then(async response => response.ok ? await response.json() as Payload : null)
      .then(body => { if (body) { setActive(body.active === true); if (typeof body.detail === "string") setState(body.detail); } })
      .catch(() => setState("Local speech activity is unknown until refreshed."));
  }, [installed, permissions]);
  async function post(path: string) {
    const sessionResponse = await fetch("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    const sessionBody = await sessionResponse.json() as Payload;
    if (!sessionResponse.ok || typeof sessionBody.csrf !== "string") throw new Error("Owner session could not be verified. Refresh and retry.");
    const response = await fetch(path, { method: "POST", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": sessionBody.csrf }, body: "{}" });
    const body = await response.json() as Payload;
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Local speech action failed.");
    return body;
  }
  async function speak() {
    if (busy || !installed || !permissions.includes("capability-pack:manage")) return;
    setBusy(true); setState("Starting a fixed local speech test. No text is sent online.");
    try {
      const result = await post("/api/local/voice/test-output");
      setActive(result.active === true);
      setState(typeof result.detail === "string" ? result.detail : "Local speech test is starting.");
      for (let index = 0; index < 60 && result.active === true; index += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 200));
        const response = await fetch("/api/local/voice/output-status", { credentials: "same-origin", cache: "no-store" });
        const body = await response.json() as Payload;
        if (!response.ok) throw new Error("Local speech status is unavailable.");
        setActive(body.active === true);
        if (typeof body.detail === "string") setState(body.detail);
        if (body.active !== true) break;
      }
    } catch (error) { setActive(false); setState(error instanceof Error ? error.message : "Local speech output failed."); }
    finally { setBusy(false); }
  }
  async function stop() {
    if (busy) return;
    setBusy(true); setState("Sending the one-click emergency stop.");
    try {
      const result = await post("/api/local/emergency-stop/stop");
      setActive(false); setState(result.stopped === true ? "Emergency stop is active; local playback was stopped." : "Stop requested.");
    } catch (error) { setState(error instanceof Error ? error.message : "Emergency stop request failed."); }
    finally { setBusy(false); }
  }
  return <div className="local-voice-test"><p className="settings-message" role="status" aria-live="polite">{active ? "Local speech is active." : state}</p>
    <div className="capability-pack-actions"><button type="button" onClick={() => void speak()} disabled={!installed || busy || active}>Speak local test</button>
      <button type="button" className="danger-action" onClick={() => void stop()} disabled={!active || busy}>Emergency stop</button></div>
  </div>;
}

function SpeechModelControls({ permissions }: { permissions: string[] }) {
  const [preview, setPreview] = useState<SpeechModelPreview | null>(null);
  const [message, setMessage] = useState("Loading local speech model availability.");
  const [busy, setBusy] = useState(false);
  const canManage = permissions.includes("capability-pack:manage");
  async function refresh() {
    if (!canManage) { setPreview(null); setMessage("This owner session does not have capability-pack:manage."); return; }
    try {
      const response = await fetch("/api/local/voice/local-model-preview", { credentials: "same-origin", cache: "no-store" });
      const body = await response.json() as Payload;
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Local speech model status is unavailable.");
      setPreview(body as unknown as SpeechModelPreview);
      setMessage(body.state === "installed" ? "The pinned local model files are installed. Runtime transcription still needs its self-test." : "No speech model files are installed. Nothing downloads until you confirm the exact preview.");
    } catch (error) { setPreview(null); setMessage(error instanceof Error ? error.message : "Local speech model status is unavailable."); }
  }
  useEffect(() => { void refresh(); }, [canManage]);
  async function install() {
    if (!preview || busy || preview.state === "installed") return;
    const files = preview.files.map(file => `${file.name}: ${file.size.toLocaleString()} bytes; ${file.digest}`).join("\n");
    if (!window.confirm(`${preview.model_id}\nRevision: ${preview.revision}\n${preview.note}\n\nSource: ${preview.source}\nTotal: ${preview.download_bytes.toLocaleString()} bytes\nFiles and digests:\n${files}\n\nDownload and select this local model?`)) {
      setMessage("Model download cancelled. No files were downloaded."); return;
    }
    setBusy(true); setMessage("Downloading the explicitly confirmed model files and checking each digest.");
    try {
      const sessionResponse = await fetch("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      const sessionBody = await sessionResponse.json() as Payload;
      if (!sessionResponse.ok || typeof sessionBody.csrf !== "string") throw new Error("Owner session could not be verified. Refresh and retry.");
      const response = await fetch("/api/local/voice/local-model-install", { method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": sessionBody.csrf },
        body: JSON.stringify({ confirmed: true, manifest_digest: preview.manifest_digest }) });
      const body = await response.json() as Payload;
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Local speech model download failed.");
      setMessage(body.model_selected === false
        ? "Model files downloaded and verified, but the local speech runtime is unavailable, so it was not selected. Review the Ears pack and retry the model selection after its runtime is installed."
        : "Model files installed and selected. Open Chat to test local push-to-talk transcription; microphone capture starts only there when you press the button.");
      await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Local speech model download failed."); }
    finally { setBusy(false); }
  }
  return <section className="settings-section" aria-labelledby="speech-model-heading">
    <div className="section-heading"><div><p className="eyebrow">LOCAL SPEECH</p><h2 id="speech-model-heading">Speech recognition model</h2></div>
      <button className="readiness-refresh" type="button" onClick={() => void refresh()} disabled={busy}>Refresh</button></div>
      <article className="settings-card"><div className="settings-card-heading"><h3>Faster-Whisper Tiny</h3><span className={`settings-state ${preview?.state === "installed" ? "ready" : "unknown"}`}>{!preview ? "Unknown" : preview.state === "installed" ? "Installed" : "Not installed"}</span></div>
      <p>{preview?.note || "A compact multilingual CPU model. Speed and recognition quality depend on the machine and language."}</p>
      <p className="settings-message" role="status" aria-live="polite">{message}</p>
      {preview && <details><summary>Review pinned model files and digests</summary><p>{preview.source}; revision {preview.revision}; {preview.download_bytes.toLocaleString()} bytes total.</p><ul>{preview.files.map(file => <li key={file.name}>{file.name}: {file.size.toLocaleString()} bytes; {file.digest}</li>)}</ul><small className="settings-source">Manifest SHA-256: {preview.manifest_digest}</small></details>}
      <div className="capability-pack-actions"><button type="button" onClick={() => void install()} disabled={!preview || preview.state === "installed" || busy}>Review &amp; download model</button><a className="settings-link" href="/ui/chat">Open Chat to test push-to-talk</a></div>
    </article>
  </section>;
}

export default function SettingsPage() {
  const [session, setSession] = useState<Result>({ state: "loading", message: "Checking owner access…", source: "/api/local/session" });
  const [preferences, setPreferences] = useState<Result>(initial);
  const [providers, setProviders] = useState<Result>(initial);
  const [models, setModels] = useState<Result>(initial);
  const [connections, setConnections] = useState<Result>(initial);
  const [policy, setPolicy] = useState<Result>(initial);
  const [capabilities, setCapabilities] = useState<Result>(initial);
  const [resources, setResources] = useState<Result>(initial);
  const [activity, setActivity] = useState<Result>(initial);
  const [hardware, setHardware] = useState<Result>(initial);
  const [ownerPermissions, setOwnerPermissions] = useState<string[]>([]);
  const [checking, setChecking] = useState(false);
  const [crashReports, setCrashReports] = useState<CrashReport[]>([]);
  const [diagnosticsMessage, setDiagnosticsMessage] = useState("Loading local crash reports…");
  const [recoveryMessage, setRecoveryMessage] = useState("");
  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const [lockEnabled, setLockEnabled] = useState<boolean | null>(null);
  const [lockPassword, setLockPassword] = useState("");
  const [lockConfirmation, setLockConfirmation] = useState("");
  const [lockMessage, setLockMessage] = useState("Loading password-lock setting…");
  const [lockBusy, setLockBusy] = useState(false);

  async function refresh() {
    setChecking(true);
    try {
      const response = await boundedGet("/api/local/session");
      if (response.status !== 200 || !record(response.body) || !Array.isArray(response.body.permissions)
        || !response.body.permissions.every(item => typeof item === "string")) {
        const result = response.status === 401 ? readError(401) : readError(response.status);
        setSession(result);
        setPreferences(result); setProviders(result); setModels(result); setConnections(result); setPolicy(result); setCapabilities(result); setResources(result); setActivity(result); setHardware(result);
        return;
      }
      setSession({ state: "ready", message: "Signed-in owner session is active. Access remains limited to the permissions returned by the local session.", source: "/api/local/session",
        values: { "Owner identity": typeof response.body.identity === "string" ? response.body.identity : "Available", "Session permissions": String(response.body.permissions.length) } });
      const permissions = new Set(response.body.permissions as string[]);
      setOwnerPermissions(response.body.permissions as string[]);
      try {
        const lock = await boundedGet("/api/local/desktop-lock");
        if (lock.status === 200 && record(lock.body) && typeof lock.body.enabled === "boolean") {
          setLockEnabled(lock.body.enabled);
          setLockMessage(lock.body.enabled ? "Password required each time the desktop app starts." : "Password prompt is off for this local app; the Electron session remains protected by its per-launch token.");
        } else setLockMessage("Password-lock settings are available only in the packaged desktop app.");
      } catch { setLockMessage("Password-lock status could not be loaded."); }
      const [nextPreferences, nextProviders, nextModels, nextConnections, nextPolicy, nextCapabilities, nextResources, nextActivity, nextHardware] = await Promise.all([
        readSummary("/api/local/preferences", "chat:read", permissions, body => {
          const value = body.preferences;
          if (!record(value) || typeof value.response_mode !== "string" || typeof value.locale !== "string"
            || typeof value.detail_level !== "string" || typeof value.voice_mode !== "string") {
            return { state: "unknown", message: "The saved preferences have an unsupported shape. Open the preference page to inspect them.", source: "/api/local/preferences" };
          }
          return { state: "ready", message: "Saved for this local owner. Presentation choices do not change routing, permissions, assignments, or consent.", source: "/api/local/preferences", values: {
            "Response style": value.response_mode, "Language": value.locale, "Response detail": value.detail_level,
            "Local reply voice": value.voice_mode,
          } };
        }),
        readSummary("/api/providers", "provider:read", permissions, body => {
          if (!Array.isArray(body.items)) return { state: "unknown", message: "Provider records were returned in an unsupported shape.", source: "/api/providers" };
          return { state: body.items.length ? "ready" : "empty", message: `${body.items.length} registered provider record(s). Registration does not establish service availability.`, source: "/api/providers" };
        }),
        readSummary("/api/models", "model:read", permissions, body => {
          if (!Array.isArray(body.items)) return { state: "unknown", message: "Model assignments were returned in an unsupported shape.", source: "/api/models" };
          return { state: body.items.length ? "ready" : "empty", message: `${body.items.length} Agent/model assignment(s). Assignment does not establish availability or hardware fit.`, source: "/api/models" };
        }),
        readSummary("/api/local/provider-connections", "provider-connection:read", permissions, body => {
          if (!Array.isArray(body.items) || !record(body.capacity)) return { state: "unknown", message: "Connection data was returned in an unsupported shape.", source: "/api/local/provider-connections" };
          const slots = body.capacity.global_request_slots;
          return { state: body.items.length ? "ready" : "empty", message: `${body.items.length} connection(s); ${typeof slots === "number" ? `${slots} configured request slot(s)` : "request-slot capacity unknown"}. Hardware feasibility remains unknown.`, source: "/api/local/provider-connections" };
        }),
        readSummary("/api/local/assignment-policy", "assignment-policy:read", permissions, body => {
          if (typeof body.enabled !== "boolean" || !Array.isArray(body.candidates)) return { state: "unknown", message: "Assignment policy was returned in an unsupported shape.", source: "/api/local/assignment-policy" };
          return { state: "ready", message: `Review-only recommendations are ${body.enabled ? "enabled" : "disabled"}; ${body.candidates.length} candidate(s) are configured.`, source: "/api/local/assignment-policy" };
        }),
        readSummary("/api/capabilities/grants", "capability-grant:manage", permissions, body => {
          if (!Array.isArray(body.items)) return { state: "unknown", message: "Session grant data was returned in an unsupported shape.", source: "/api/capabilities/grants" };
          return { state: "ready", message: `${body.items.length} active session-scoped grant(s). This is not a general capability catalogue.`, source: "/api/capabilities/grants" };
        }),
        readSummary("/api/system/monitor", "system:read", permissions, body => {
          if (!Array.isArray(body.resource_capacities) && body.resource_capacities !== null) return { state: "unknown", message: "System data was returned in an unsupported shape.", source: "/api/system/monitor" };
          const capacities = Array.isArray(body.resource_capacities) ? body.resource_capacities : [];
          const remaining = capacities.reduce((total, item) => record(item) && typeof item.remaining === "number" ? total + item.remaining : total, 0);
          return { state: "ready", message: body.resource_capacities === null ? "No resource manager is configured; hardware feasibility is unknown." : `${capacities.length} configured software capacity group(s), ${remaining} remaining slot(s). This does not measure hardware fit.`, source: "/api/system/monitor" };
        }),
        readSummary("/api/activity?limit=1", "activity:read", permissions, body => {
          if (!Array.isArray(body.items)) return { state: "unknown", message: "Activity data was returned in an unsupported shape.", source: "/api/activity?limit=1" };
          const latest = body.items[0];
          return { state: latest ? "ready" : "empty", message: record(latest) && typeof latest.created_at === "string"
            ? `Latest recorded activity timestamp: ${latest.created_at}.` : "No recent activity record is available.", source: "/api/activity?limit=1" };
        }),
        readSummary("/api/system/hardware-profile", "system:read", permissions, summarizeHardwareProfile),
      ]);
      setPreferences(nextPreferences); setProviders(nextProviders); setModels(nextModels); setConnections(nextConnections);
      setPolicy(nextPolicy); setCapabilities(nextCapabilities); setResources(nextResources); setActivity(nextActivity); setHardware(nextHardware);
    } catch {
      const result: Result = { state: "failed", message: "Owner session could not be checked. Confirm the local app is running, then retry or sign in again.", source: "/api/local/session" };
      setSession(result); setPreferences(result); setProviders(result); setModels(result); setConnections(result);
      setPolicy(result); setCapabilities(result); setResources(result); setActivity(result); setHardware(result);
    } finally {
      setChecking(false);
    }
  }

  async function updateLock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lockEnabled === null || lockBusy) return;
    setLockBusy(true); setLockMessage("Updating password lock…");
    try {
      const sessionResponse = await fetch("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      const sessionBody = await sessionResponse.json() as Payload;
      if (!sessionResponse.ok || typeof sessionBody.csrf !== "string") throw new Error("Owner session could not be verified. Refresh and retry.");
      const response = await fetch("/api/local/desktop-lock", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": sessionBody.csrf },
        body: JSON.stringify({ enabled: !lockEnabled, password: lockPassword, confirmation: lockEnabled ? null : lockConfirmation }),
      });
      const result = await response.json() as Payload;
      if (!response.ok || typeof result.enabled !== "boolean") throw new Error(typeof result.detail === "string" ? result.detail : "Password-lock setting was not changed.");
      setLockEnabled(result.enabled); setLockPassword(""); setLockConfirmation("");
      setLockMessage(result.enabled ? "Password lock enabled. The app will require this password at its next launch." : "Password lock disabled. The app will start with its protected local session next time.");
    } catch (error) { setLockMessage(error instanceof Error ? error.message : "Password-lock setting was not changed."); }
    finally { setLockBusy(false); }
  }

  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    const bridge = (window as Window & { desktopBridge?: Partial<DesktopRecoveryBridge> }).desktopBridge;
    if (!bridge?.readCrashReports) {
      setDiagnosticsMessage("Local crash reports are available only in the installed desktop app.");
      return;
    }
    void bridge.readCrashReports().then(result => {
      if (!result.ok || !Array.isArray(result.reports)) {
        setDiagnosticsMessage(result.message || "Sign in with system:read permission to inspect local reports.");
        return;
      }
      setCrashReports(result.reports);
      setDiagnosticsMessage(result.reports.length ? "Reports are stored locally and contain only bounded event metadata." : "No handled crash events have been recorded.");
    }).catch(() => setDiagnosticsMessage("Local crash reports could not be read. Retry from this page."));
  }, []);

  async function openDiagnostics() {
    const bridge = (window as Window & { desktopBridge?: Partial<DesktopRecoveryBridge> }).desktopBridge;
    if (!bridge?.openDiagnosticsFolder) return;
    try {
      const result = await bridge.openDiagnosticsFolder();
      if (!result.ok) setDiagnosticsMessage(result.message || "The local diagnostics folder could not be opened.");
    } catch { setDiagnosticsMessage("The local diagnostics folder could not be opened."); }
  }

  async function resetAppData() {
    const bridge = (window as Window & { desktopBridge?: Partial<DesktopRecoveryBridge> }).desktopBridge;
    if (!bridge?.resetAppData || recoveryBusy) return;
    setRecoveryBusy(true);
    setRecoveryMessage("Waiting for the native confirmation…");
    try {
      const result = await bridge.resetAppData();
      setRecoveryMessage(result.restarting ? "The app is closing. First-run setup will open after local data is removed." : result.message || "Reset was not started.");
    } catch { setRecoveryMessage("Reset could not be started. Your data was kept."); }
    finally { setRecoveryBusy(false); }
  }

  return <main className="settings-page">
      <header className="topbar"><span>OWNER SETTINGS</span><a className="login-link" href="/ui/login">Owner sign in <span aria-hidden="true">↗</span></a></header>
      <div className="settings-heading"><div><p className="eyebrow"><span className="eyebrow-line" /> ONE PLACE · CLEAR PERMISSIONS</p><h1>Settings</h1><p>Everyday preferences stay simple. Advanced controls remain grouped by the systems they manage.</p></div><button className="readiness-refresh" type="button" onClick={() => void refresh()} disabled={checking}>{checking ? "Refreshing…" : "Refresh values"}</button></div>
      <section className="settings-section" aria-labelledby="everyday-heading"><div className="section-heading"><div><p className="eyebrow">OWNER PREFERENCES</p><h2 id="everyday-heading">Everyday use</h2></div></div>
        <SettingCard title="Response preferences" description="Your saved response style, language, detail, and optional local voice preference." result={preferences} href="/ui/preferences" linkLabel="Edit preferences" />
      </section>
      <section className="settings-section" aria-labelledby="advanced-heading"><div className="section-heading"><div><p className="eyebrow">OPERATOR CONTROLS</p><h2 id="advanced-heading">Advanced settings</h2></div></div>
        <p className="settings-intro">Each page loads its own authorized data and keeps its existing confirmations. Credentials are not shown here. A read-only overview never changes provider assignments, permissions, or runtime configuration.</p>
        <div className="settings-grid">
          <SettingCard title="Providers and models" description="Registration and Agent/model assignment counts. Availability is reported separately." result={providers} href="/ui/providers" linkLabel="Manage providers & models" />
          <SettingCard title="Agent assignments" description="Current configured provider/model assignments." result={models} href="/ui/providers" linkLabel="Review assignments" />
          <SettingCard title="Connections and capacity" description="Configured connections and software request-slot capacity; not hardware feasibility." result={connections} href="/ui/provider-connections" linkLabel="Manage connections" />
          <SettingCard title="Assignment recommendations" description="Review-only policy state and candidate count." result={policy} href="/ui/assignment-policy" linkLabel="Review recommendation policy" />
          <SettingCard title="Capability access" description="Current session-scoped grants and owner controls." result={capabilities} href="/desktop/" linkLabel="Review session controls" />
          <SettingCard title="Resources" description="Configured software capacity from the current system snapshot." result={resources} href="/ui/readiness" linkLabel="Open resource evidence" />
          <SettingCard title="Hardware profile and model guidance" description="Read-only local CPU, GPU, memory, and Ollama destination observations with source and time. Values are not stored or uploaded." result={hardware} href="/desktop/settings/" linkLabel="Refresh profile" />
          <SettingCard title="Security and permissions" description="Current owner-session state and existing permission boundaries." result={session} href="/ui/login" linkLabel="Review owner access" />
          <SettingCard title="Diagnostics and activity" description="Recent activity and measured readiness, with safe diagnostics available from Backup & restore." result={activity} href="/ui/activity" linkLabel="Open activity & diagnostics" />
          <SettingCard title="Backup and recovery" description="Encrypted local backup and explicit restore controls." result={{ state: "unknown", message: "No backup is created or inspected from this overview.", source: "Owner-controlled backup page" }} href="/ui/backup" linkLabel="Open backup & restore" />
        </div>
      </section>
      <CapabilityPackControls permissions={ownerPermissions} />
      <SpeechModelControls permissions={ownerPermissions} />
      <section className="settings-section" aria-labelledby="desktop-lock-heading"><div className="section-heading"><div><p className="eyebrow">LOCAL ACCESS</p><h2 id="desktop-lock-heading">Optional password lock</h2></div></div>
        <article className="settings-card"><p>{lockMessage}</p>
          {lockEnabled !== null && <form onSubmit={updateLock}>
            <label htmlFor="desktop-lock-password">{lockEnabled ? "Current owner password" : "New owner password (12+ characters)"}</label>
            <input id="desktop-lock-password" type="password" autoComplete={lockEnabled ? "current-password" : "new-password"} minLength={12} maxLength={1024} required value={lockPassword} onChange={event => setLockPassword(event.target.value)} />
            {!lockEnabled && <><label htmlFor="desktop-lock-confirmation">Confirm new password</label><input id="desktop-lock-confirmation" type="password" autoComplete="new-password" minLength={12} maxLength={1024} required value={lockConfirmation} onChange={event => setLockConfirmation(event.target.value)} /></>}
            <button type="submit" disabled={lockBusy}>{lockBusy ? "Saving…" : lockEnabled ? "Disable password lock" : "Enable password lock"}</button>
          </form>}
        </article>
      </section>
      <section className="settings-section" aria-labelledby="recovery-heading"><div className="section-heading"><div><p className="eyebrow">LOCAL RECOVERY</p><h2 id="recovery-heading">Diagnostics and app data</h2></div></div>
        <article className="settings-card recovery-card">
          <h3>Local crash reports</h3>
          <p>Only handled failure type, source, app version, time, and a bounded exit code are stored. Messages, stack traces, prompts, credentials, paths, and provider responses are excluded. Reports never upload automatically.</p>
          <p className="settings-message" role="status">{diagnosticsMessage}</p>
          {crashReports.length > 0 && <ol className="crash-report-list">{crashReports.map((report, index) => <li key={`${report.occurredAt}-${index}`}>
            <strong>{report.event}</strong> · {report.source} · {report.reason} · {report.appVersion} · {report.occurredAt}{report.exitCode === null ? "" : ` · exit ${report.exitCode}`}
          </li>)}</ol>}
          <button className="readiness-refresh" type="button" onClick={() => void openDiagnostics()}>Open local diagnostics folder</button>
        </article>
        <article className="settings-card recovery-card">
          <h3>Reset app data</h3>
          <p>This removes the local owner credential, database, retained conversations, backups, staged update installers, and crash reports. Export a recovery backup first if you want to keep data. A separate native confirmation is required; the app restarts at first-run setup.</p>
          <button className="readiness-refresh danger-action" type="button" onClick={() => void resetAppData()} disabled={recoveryBusy}>{recoveryBusy ? "Waiting…" : "Reset all app data"}</button>
          {recoveryMessage && <p className="settings-message" role="status">{recoveryMessage}</p>}
        </article>
      </section>
      <footer className="footer"><span>ERSELMETZ AI · SETTINGS</span><span>Only existing authorized APIs are used. Unavailable data stays explicit.</span></footer>
  </main>;
}

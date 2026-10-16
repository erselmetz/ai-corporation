"use client";

import { useEffect, useState } from "react";

type State = "loading" | "ready" | "empty" | "sign-in" | "denied" | "failed" | "unknown";
type Result = { state: State; message: string; source: string; values?: Record<string, string> };
type Payload = Record<string, unknown>;

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
  const [checking, setChecking] = useState(false);

  async function refresh() {
    setChecking(true);
    try {
      const response = await boundedGet("/api/local/session");
      if (response.status !== 200 || !record(response.body) || !Array.isArray(response.body.permissions)
        || !response.body.permissions.every(item => typeof item === "string")) {
        const result = response.status === 401 ? readError(401) : readError(response.status);
        setSession(result);
        setPreferences(result); setProviders(result); setModels(result); setConnections(result); setPolicy(result); setCapabilities(result); setResources(result); setActivity(result);
        return;
      }
      setSession({ state: "ready", message: "Signed-in owner session is active. Access remains limited to the permissions returned by the local session.", source: "/api/local/session",
        values: { "Owner identity": typeof response.body.identity === "string" ? response.body.identity : "Available", "Session permissions": String(response.body.permissions.length) } });
      const permissions = new Set(response.body.permissions as string[]);
      const [nextPreferences, nextProviders, nextModels, nextConnections, nextPolicy, nextCapabilities, nextResources, nextActivity] = await Promise.all([
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
      ]);
      setPreferences(nextPreferences); setProviders(nextProviders); setModels(nextModels); setConnections(nextConnections);
      setPolicy(nextPolicy); setCapabilities(nextCapabilities); setResources(nextResources); setActivity(nextActivity);
    } catch {
      const result: Result = { state: "failed", message: "Owner session could not be checked. Confirm the local app is running, then retry or sign in again.", source: "/api/local/session" };
      setSession(result); setPreferences(result); setProviders(result); setModels(result); setConnections(result);
      setPolicy(result); setCapabilities(result); setResources(result); setActivity(result);
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

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
          <SettingCard title="Security and permissions" description="Current owner-session state and existing permission boundaries." result={session} href="/ui/login" linkLabel="Review owner access" />
          <SettingCard title="Diagnostics and activity" description="Recent activity and measured readiness, with safe diagnostics available from Backup & restore." result={activity} href="/ui/activity" linkLabel="Open activity & diagnostics" />
          <SettingCard title="Backup and recovery" description="Encrypted local backup and explicit restore controls." result={{ state: "unknown", message: "No backup is created or inspected from this overview.", source: "Owner-controlled backup page" }} href="/ui/backup" linkLabel="Open backup & restore" />
        </div>
      </section>
      <footer className="footer"><span>ERSELMETZ AI · SETTINGS</span><span>Only existing authorized APIs are used. Unavailable data stays explicit.</span></footer>
  </main>;
}

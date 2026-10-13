"use client";

import { useEffect, useState } from "react";

type CheckState = "checking" | "ready" | "missing" | "required" | "denied" | "unavailable" | "unknown";
type SetupSnapshot = {
  service: CheckState;
  owner: CheckState;
  chatPermission: CheckState;
  providers: CheckState;
  modelAssignment: CheckState;
  providerAvailability: "unknown";
  optionalCapabilities: "unknown";
};

const initialSetup: SetupSnapshot = {
  service: "checking",
  owner: "checking",
  chatPermission: "checking",
  providers: "checking",
  modelAssignment: "checking",
  providerAvailability: "unknown",
  optionalCapabilities: "unknown",
};

const copy: Record<CheckState | "unknown", string> = {
  checking: "Checking",
  ready: "Ready",
  missing: "Not configured",
  required: "Sign in required",
  denied: "Permission unavailable",
  unavailable: "Unavailable",
  unknown: "Unknown",
};

const workspaces = [
  { title: "Coordinator chat", detail: "Open an owner-authorized conversation with the configured coordinator.", href: "/ui/chat", label: "Open Chat", tone: "cyan" },
  { title: "Organization map", detail: "Inspect the recorded AI organization structure and assignments.", href: "/ui/structure", label: "View structure", tone: "violet" },
  { title: "Workflow map", detail: "Review recorded workflow items and their current evidence.", href: "/ui/workflow-map", label: "View workflows", tone: "amber" },
  { title: "AI team", detail: "See the registered Employees and the Agents assigned to them.", href: "/ui/employees", label: "View AI team", tone: "cyan" },
  { title: "Providers & models", detail: "Review configured services and model assignments.", href: "/ui/providers", label: "Review setup", tone: "violet" },
  { title: "Projects", detail: "Organize work and review its existing Tasks.", href: "/ui/projects", label: "View projects", tone: "amber" },
];

type BoundedResponse = { ok: boolean; status: number; body: unknown };
type ProviderList = { items: Array<{ id?: string }> };
type AgentList = { items: Array<{ provider?: string; model?: string }> };

async function boundedFetch(path: string): Promise<BoundedResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    return {
      ok: response.ok,
      status: response.status,
      body: response.ok ? await response.json() : null,
    };
  } finally {
    window.clearTimeout(timeout);
  }
}

function checkRow(label: string, state: CheckState | "unknown", explanation: string) {
  return <li className="check-row" key={label}>
    <span><strong>{label}</strong><small>{explanation}</small></span>
    <span className={`check-state ${state}`} role="status">{copy[state]}</span>
  </li>;
}

export default function Home() {
  const [setup, setSetup] = useState<SetupSnapshot>(initialSetup);
  const [checking, setChecking] = useState(false);

  async function refreshSetup() {
    setChecking(true);
    setSetup(initialSetup);
    const next: SetupSnapshot = { ...initialSetup };
    try {
      const health = await boundedFetch("/health");
      if (health.ok) {
        const body = health.body;
        next.service = typeof body === "object" && body !== null && "status" in body && body.status === "ok"
          ? "ready" : "unknown";
      } else {
        next.service = "unavailable";
      }
    } catch {
      next.service = "unknown";
    }

    try {
      const session = await boundedFetch("/api/local/session");
      next.owner = session.status === 401 || session.status === 404 ? "required"
        : session.status === 403 ? "denied"
          : session.ok ? "ready" : "unknown";
      if (next.owner !== "ready") {
        next.chatPermission = next.owner;
        next.providers = next.owner === "required" ? "required" : "unknown";
        next.modelAssignment = next.owner === "required" ? "required" : "unknown";
        return;
      }
      const sessionData = session.body;
      next.chatPermission = typeof sessionData === "object" && sessionData !== null
        && "permissions" in sessionData && Array.isArray(sessionData.permissions)
        ? (sessionData.permissions as unknown[]).includes("chat:start")
          && (sessionData.permissions as unknown[]).includes("chat:send") ? "ready" : "denied"
        : "unknown";

      const [providersResponse, agentsResponse] = await Promise.all([
        boundedFetch("/api/providers"),
        boundedFetch("/api/agents"),
      ]);
      if (providersResponse.status === 401 || agentsResponse.status === 401) {
        next.owner = "required";
        next.chatPermission = "required";
      }
      next.providers = providersResponse.status === 403 ? "denied" : "unknown";
      next.modelAssignment = agentsResponse.status === 403 ? "denied" : "unknown";

      const providers = providersResponse.body as ProviderList | null;
      const agents = agentsResponse.body as AgentList | null;
      if (providersResponse.ok) {
        next.providers = Array.isArray(providers?.items) && providers.items.length > 0 ? "ready"
          : Array.isArray(providers?.items) ? "missing" : "unknown";
      }
      if (agentsResponse.ok) {
        if (!Array.isArray(agents?.items) || !providersResponse.ok || !Array.isArray(providers?.items)) {
          next.modelAssignment = "unknown";
        } else {
          const providerIds = new Set(Array.isArray(providers?.items)
            ? providers.items.map((provider: { id?: string }) => provider.id) : []);
          const assigned = agents.items.some((agent: { provider?: string; model?: string }) =>
            typeof agent.provider === "string" && providerIds.has(agent.provider)
            && typeof agent.model === "string" && agent.model.trim().length > 0);
          next.modelAssignment = assigned ? "ready" : "missing";
        }
      }
    } catch {
      if (next.owner === "checking") next.owner = "unknown";
      if (next.chatPermission === "checking") next.chatPermission = "unknown";
      if (next.providers === "checking") next.providers = "unknown";
      if (next.modelAssignment === "checking") next.modelAssignment = "unknown";
    } finally {
      setSetup(next);
      setChecking(false);
    }
  }

  useEffect(() => { void refreshSetup(); }, []);

  return <main className="shell">
    <aside className="rail" aria-label="Main navigation">
      <a className="brand" href="/desktop/"><span className="brand-mark">E</span><span>ERSELMETZ<span className="muted"> AI</span></span></a>
      <p className="rail-label">COMMAND CENTER</p>
      <a className="rail-link active" href="/desktop/">Home</a>
      <a className="rail-link" href="/ui/chat">Chat</a>
      <a className="rail-link" href="/ui/projects">Projects</a>
      <a className="rail-link" href="/ui/employees">AI team</a>
      <a className="rail-link" href="/ui/providers">Providers &amp; models</a>
      <a className="rail-link" href="/ui/tasks">Tasks</a>
      <div className="rail-footer"><span className="pulse" /> LOCAL RUNTIME<br /><small>Loopback only · owner controlled</small></div>
    </aside>
    <section className="main-panel">
      <header className="topbar"><span>YOUR LOCAL WORKSPACE</span><a className="login-link" href="/ui/login">Owner sign in <span aria-hidden="true">↗</span></a></header>
      <div className="hero">
        <div className="eyebrow"><span className="eyebrow-line" /> INSTALL · OPEN · SET UP · CHAT</div>
        <h1>Welcome to ERSELMETZ AI.<br /><span>Your workspace starts here.</span></h1>
        <p>Open Chat to talk with the configured coordinator. If this is your first visit, sign in and review the setup checks below.</p>
        <a className="primary-action" href="/ui/chat">Start Chat <span aria-hidden="true">→</span></a>
        <p className="hero-note">Nothing is downloaded, connected, or reassigned automatically.</p>
        <div className="orbital" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="core">E<span>AI</span></div><i className="node node-one"/><i className="node node-two"/><i className="node node-three"/></div>
      </div>

      <section className="readiness" aria-labelledby="readiness-title">
        <div className="readiness-heading"><div><p className="eyebrow">FIRST RUN · LOCAL CHECKS</p><h2 id="readiness-title">Setup readiness</h2></div>
          <button className="readiness-refresh" type="button" onClick={() => void refreshSetup()} disabled={checking}>{checking ? "Checking…" : "Refresh checks"}</button></div>
        <p className="readiness-intro">Checks are read-only and time out after 2.5 seconds per request. “Unknown” means this app does not have evidence to confirm it.</p>
        <ul className="check-list">
          {checkRow("Local app service", setup.service, "Confirms the local API responds; it does not verify installer integrity.")}
          {checkRow("Owner access", setup.owner, "Checks whether this browser has an active owner session.")}
          {checkRow("Coordinator chat permission", setup.chatPermission, "Confirms the active session includes chat:start and chat:send permissions.")}
          {checkRow("Provider registration", setup.providers, "Shows registered provider records only.")}
          {checkRow("Model assignment", setup.modelAssignment, "Shows whether a registered Agent has a configured provider and model.")}
          {checkRow("Provider availability", "unknown", "No live provider health check is run from this screen.")}
          {checkRow("Installed app verification", "unknown", "The app does not expose installer signature or package-integrity verification.")}
          {checkRow("Installed models", "unknown", "Inventory is not automatic; use the separate local-model page to choose an Agent and explicitly refresh.")}
          {checkRow("Optional capabilities", "unknown", "The current app has no general detector for optional capability packs.")}
        </ul>
        <div className="setup-actions"><a href="/ui/login">Sign in</a><a href="/ui/providers">Review providers &amp; models</a><a href="/ui/local-models">Check local model inventory</a><a href="/ui/employees">Review AI team</a></div>
      </section>

      <section className="guide" aria-labelledby="guide-title">
        <div className="section-heading"><div><p className="eyebrow">GET STARTED</p><h2 id="guide-title">A simple first chat</h2></div><span className="local-tag">● &nbsp; OWNER CONTROLLED</span></div>
        <ol className="guide-steps">
          <li><span>01</span><div><strong>Open the desktop app</strong><p>After installation, use the ERSELMETZ AI desktop or Start Menu shortcut. The installer does not launch the app automatically.</p></div></li>
          <li><span>02</span><div><strong>Start the local services</strong><p>On first start, create and confirm an owner password. Later starts ask for that password before opening the workspace.</p></div></li>
          <li><span>03</span><div><strong>Sign in to the workspace</strong><p>Use the owner password again for the browser session. Protected chat and configuration pages require this separate sign-in.</p></div></li>
          <li><span>04</span><div><strong>Chat with the coordinator</strong><p>Choose Chat and send a message to the configured coordinator. If setup is missing, review provider connections and Agent assignments first.</p></div></li>
          <li><span>05</span><div><strong>Review the AI organization</strong><p>Use AI team to inspect Employees and Agents, and Projects or Tasks to review organized work. This overview does not dispatch Tasks.</p></div></li>
        </ol>
        <details className="operator-guide"><summary>Advanced operator setup</summary><div><p>Use Provider connections to explicitly configure a supported local or online connection, then Providers &amp; models to review registration and Agent assignments. The local-model inventory page supports an explicit bounded check for supported providers; unsupported capabilities remain unknown. This overview never probes providers, downloads models, changes assignments, or grants permissions.</p><div className="setup-actions"><a href="/ui/provider-connections">Provider connections</a><a href="/ui/providers">Provider and model settings</a><a href="/ui/local-models">Local model inventory</a><a href="/ui/employees">Agent assignments</a><a href="/ui/tasks">Task review</a></div></div></details>
      </section>

      <section className="workspaces" aria-labelledby="workspaces-title">
        <div className="section-heading"><div><p className="eyebrow">EXPLORE WHEN YOU NEED IT</p><h2 id="workspaces-title">Your workspace</h2></div><span className="local-tag">● &nbsp; LOCAL APP</span></div>
        <div className="cards">{workspaces.map((item, index) => <article className={`card ${item.tone}`} key={item.title}>
          <div className="card-head"><span className="card-index">0{index + 1}</span><span className="card-arrow" aria-hidden="true">↗</span></div>
          <h3>{item.title}</h3><p>{item.detail}</p><a href={item.href}>{item.label}<span aria-hidden="true"> →</span></a>
        </article>)}</div>
      </section>
      <footer className="footer"><span>ERSELMETZ AI · DESKTOP</span><span>Sign in with the owner account to use protected pages and chat.</span></footer>
    </section>
  </main>;
}

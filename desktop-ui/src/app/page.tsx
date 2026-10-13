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
      <nav className="rail-navigation" aria-label="Main navigation">
        <div className="rail-group"><span className="rail-group-label">PRIMARY</span>
          <a className="rail-link active" aria-current="page" href="/desktop/">Home</a>
          <a className="rail-link" href="/ui/chat">Chat</a>
          <a className="rail-link" href="/ui/projects">Projects</a>
        </div>
        <div className="rail-group"><span className="rail-group-label">AI</span>
          <a className="rail-link" href="/ui/employees">Employees</a>
          <a className="rail-link" href="/ui/positions">Positions</a>
          <a className="rail-link" href="/ui/structure">Organization map</a>
          <a className="rail-link" href="/ui/providers">Providers &amp; models</a>
          <a className="rail-link" href="/ui/memory">Memory</a>
        </div>
        <div className="rail-group"><span className="rail-group-label">OPERATIONS</span>
          <a className="rail-link" href="/ui/tasks">Tasks</a>
          <a className="rail-link" href="/ui/workflows">Workflows</a>
          <a className="rail-link" href="/ui/workflow-map">Workflow map</a>
          <a className="rail-link" href="/ui/activity">Activity</a>
        </div>
        <div className="rail-group"><span className="rail-group-label">SYSTEM</span>
          <a className="rail-link" href="/ui/inventory">Software inventory</a>
          <a className="rail-link" href="/ui/documentation">Documentation</a>
          <a className="rail-link" href="/ui/updates">Updates</a>
          <a className="rail-link" href="/ui/login">Owner sign-in</a>
        </div>
      </nav>
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
      </section>

      <section className="provider-guide" aria-labelledby="provider-guide-title">
        <div className="section-heading"><div><p className="eyebrow">SUPPORTED SETUP · OWNER CONTROLLED</p><h2 id="provider-guide-title">Connect a provider and choose a model</h2></div><span className="local-tag">NO AUTOMATIC CONNECTIONS</span></div>
        <p className="provider-intro">Start with one supported connection. Keep API keys out of ordinary chat; enter credentials only in the dedicated owner-protected connection form. Nothing connects, downloads, or changes an Agent assignment from this guide.</p>
        <div className="provider-options">
          <article className="provider-option"><span className="card-index">LOCAL</span><h3>Use a local Ollama service</h3><p>Start Ollama yourself, then use Provider connections to add its loopback address and explicitly refresh the model catalog. Installed-model checks and model selection are separate owner actions.</p><a href="/ui/provider-connections">Set up local connection <span aria-hidden="true">→</span></a></article>
          <article className="provider-option"><span className="card-index">ONLINE</span><h3>Use Google Gemini</h3><p>Connect from the dedicated setup page with an owner-managed API key. Model discovery is an explicit online check; each Gemini chat turn still requires its separate consent.</p><a href="/ui/online-provider">Set up Gemini <span aria-hidden="true">→</span></a></article>
        </div>
        <p className="preferences-note"><strong>Everyday use:</strong> Chat is available from the main navigation. This version does not yet have a general preferences page; the unified preferences experience remains planned separately.</p>
        <div className="readiness-legend" aria-label="How provider and model readiness terms differ">
          <h3>What each setup signal means</h3>
          <dl>
            <div><dt>Registered provider</dt><dd>A provider record exists. This alone does not mean the service responds.</dd></div>
            <div><dt>Service availability</dt><dd>A supported explicit check returned a result. The home overview does not run one; otherwise availability is unknown.</dd></div>
            <div><dt>Installed model</dt><dd>A supported model inventory check observed it. A configured model name is not inventory evidence.</dd></div>
            <div><dt>Agent assignment</dt><dd>An Agent has a configured provider and model. Assignment does not prove availability, installation, compatibility, or successful execution.</dd></div>
            <div><dt>Software capacity</dt><dd>Request slots bound software concurrency. They do not measure available GPU, VRAM, or RAM.</dd></div>
            <div><dt>Measured hardware evidence</dt><dd>Only a supported runtime measurement can report observed loaded-model memory; absent or unsupported evidence stays unknown and does not guarantee fit.</dd></div>
          </dl>
        </div>
        <details className="operator-guide"><summary>Advanced operator settings</summary><div>
          <p>These pages require owner sign-in and keep their existing confirmation and consent steps. Use them when you need to inspect or change a specific connection, assignment, policy, or supported software item.</p>
          <div className="operator-groups">
            <section><h3>Connections and credentials</h3><a href="/ui/provider-connections">Provider connections</a><small>Configure supported Ollama or Gemini connections; credentials are handled only here.</small></section>
            <section><h3>Provider records and Agent assignments</h3><a href="/ui/providers">Providers &amp; models</a><small>Inspect provider registration and configured Agent/model assignments.</small></section>
            <section><h3>Model inventory and capability guidance</h3><a href="/ui/local-models">Local model inventory</a><a href="/ui/assignment-policy">Review assignment recommendations</a><small>Inventory and recommendations use their own explicit checks and do not prove hardware fit.</small></section>
            <section><h3>Security and access</h3><a href="/ui/login">Owner sign-in</a><small>Protected operator pages remain unavailable without the required owner session.</small></section>
            <section><h3>Resource settings</h3><p>No dedicated resource-settings page is available in this workspace yet. Configured request slots represent software concurrency only.</p></section>
            <section><h3>Diagnostics and activity</h3><a href="/ui/activity">Activity &amp; logs</a><small>Review recorded application activity; missing runtime or hardware evidence remains unknown.</small></section>
            <section><h3>Supported software inventory</h3><a href="/ui/inventory">Software &amp; integrations</a><small>Review the existing scoped inventory and supported lifecycle actions.</small></section>
          </div>
        </div></details>
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

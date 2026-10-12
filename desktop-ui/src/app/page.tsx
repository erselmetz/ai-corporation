"use client";

import { useEffect, useState } from "react";

type SetupState = "checking" | "sign-in" | "forbidden" | "unavailable" | "required" | "partial";
type SetupSnapshot = { state: SetupState; detail: string };

const workspaces = [
  { title: "AI team", detail: "See the registered Employees and the Agents assigned to them.", href: "/ui/employees", label: "View AI team", tone: "cyan" },
  { title: "Providers & models", detail: "Review configured services and model assignments.", href: "/ui/providers", label: "Review setup", tone: "violet" },
  { title: "Projects", detail: "Organize work and review its existing Tasks.", href: "/ui/projects", label: "View projects", tone: "amber" },
];

export default function Home() {
  const [setup, setSetup] = useState<SetupSnapshot>({
    state: "checking",
    detail: "Checking local sign-in and saved configuration. No provider health check will run.",
  });
  const [checking, setChecking] = useState(false);

  async function refreshSetup() {
    setChecking(true);
    setSetup({ state: "checking", detail: "Checking local sign-in and saved configuration. No provider health check will run." });
    try {
      const session = await fetch("/api/local/session", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (session.status === 401 || session.status === 404) {
        setSetup({ state: "sign-in", detail: "Sign in with the local owner account to review setup and use chat." });
        return;
      }
      if (session.status === 403) {
        setSetup({ state: "forbidden", detail: "This local session cannot review setup. Check owner access." });
        return;
      }
      if (!session.ok) throw new Error("Session status could not be read.");

      const responses = await Promise.all([
        fetch("/api/status", { credentials: "same-origin", headers: { Accept: "application/json" } }),
        fetch("/api/providers", { credentials: "same-origin", headers: { Accept: "application/json" } }),
        fetch("/api/agents", { credentials: "same-origin", headers: { Accept: "application/json" } }),
      ]);
      if (responses.some((response) => response.status === 401)) {
        setSetup({ state: "sign-in", detail: "Sign in with the local owner account to review setup and use chat." });
        return;
      }
      if (responses.some((response) => response.status === 403)) {
        setSetup({ state: "forbidden", detail: "This local session cannot review setup. Check owner access." });
        return;
      }
      if (responses.some((response) => !response.ok)) throw new Error("Setup records could not be read.");
      const [status, providers, agents] = await Promise.all(responses.map((response) => response.json()));
      if (!status?.corporation || !status?.node || !Array.isArray(providers?.items) || !Array.isArray(agents?.items)) {
        throw new Error("Setup records could not be read.");
      }
      const providerIds = new Set(providers.items.map((provider: { id?: string }) => provider.id));
      const hasAssignment = agents.items.some((agent: { provider?: string; model?: string }) =>
        typeof agent.provider === "string" && providerIds.has(agent.provider)
        && typeof agent.model === "string" && agent.model.trim().length > 0);
      if (!providers.items.length || !hasAssignment) {
        setSetup({
          state: "required",
          detail: !providers.items.length
            ? "No provider is registered yet. Review provider setup and check the AI team model assignments."
            : "No registered AI team member has a model assignment that matches a configured provider.",
        });
      } else {
        setSetup({
          state: "partial",
          detail: "Provider and model assignments are present. Availability has not been checked; the first chat will confirm whether the selected service can reply.",
        });
      }
    } catch {
      setSetup({
        state: "unavailable",
        detail: "Setup information could not be read. This does not report provider health; refresh to try again.",
      });
    } finally {
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
        <p>Sign in, review the configured provider and model, then start a conversation. The first reply checks whether that service can respond.</p>
        <a className="primary-action" href="/ui/chat">Start Chat <span aria-hidden="true">→</span></a>
        <p className="hero-note">Provider registration does not confirm service health. Nothing is downloaded or reassigned automatically.</p>
        <div className="orbital" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="core">E<span>AI</span></div><i className="node node-one"/><i className="node node-two"/><i className="node node-three"/></div>
      </div>
      <section className="readiness" aria-labelledby="readiness-title">
        <div className="readiness-heading"><div><p className="eyebrow">FIRST RUN</p><h2 id="readiness-title">Before your first chat</h2></div>
          <span className={`readiness-badge ${setup.state}`} role="status" aria-live="polite">{setup.state === "checking" ? "CHECKING" : setup.state === "sign-in" ? "SIGN-IN REQUIRED" : setup.state === "forbidden" ? "ACCESS DENIED" : setup.state === "unavailable" ? "UNAVAILABLE" : setup.state === "required" ? "SETUP REQUIRED" : "PARTIALLY CONFIGURED"}</span></div>
        <p>{setup.detail}</p>
        <div className="readiness-links"><a href="/ui/login">Owner sign in</a><a href="/ui/providers">Providers &amp; models</a><a href="/ui/employees">AI team</a></div>
        <small>Registration shows configuration only. No provider health check, model download, or assignment change runs here.</small>
        <button className="readiness-refresh" type="button" onClick={() => void refreshSetup()} disabled={checking}>{checking ? "Checking…" : "Refresh setup status"}</button>
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

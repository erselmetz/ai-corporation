"use client";

import { useEffect, useState } from "react";

const groups = [
  ["PRIMARY", [["Home", "/desktop/"], ["Chat", "/ui/chat"], ["Projects", "/ui/projects"]]],
  ["AI", [["Employees", "/ui/employees"], ["Positions", "/ui/positions"],
    ["Organization map", "/ui/structure"], ["Interactive system map", "/ui/visualization"],
    ["Providers & models", "/ui/providers"], ["Memory", "/ui/memory"]]],
  ["OPERATIONS", [["Tasks", "/ui/tasks"], ["Workflows", "/ui/workflows"],
    ["Workflow map", "/ui/workflow-map"], ["Activity", "/ui/activity"]]],
  ["SYSTEM", [["Settings", "/desktop/settings/"], ["Software inventory", "/ui/inventory"],
    ["Performance readiness", "/ui/readiness"], ["Backup & restore", "/ui/backup"],
    ["Documentation", "/ui/documentation"], ["Updates", "/ui/updates"],
    ["Owner sign-in", "/ui/login"]]],
] as const;

export default function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const [navigationOpen, setNavigationOpen] = useState(false);

  useEffect(() => {
    let theme = "dark";
    try { theme = window.localStorage.getItem("ersel-chat-theme-v1") === "light" ? "light" : "dark"; }
    catch { /* Private browsing may block local storage. */ }
    document.documentElement.dataset.theme = theme;
    document.body.dataset.theme = theme;
  }, []);

  useEffect(() => {
    if (!navigationOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNavigationOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [navigationOpen]);

  return <div className={`shell${navigationOpen ? " navigation-open" : ""}`}>
    <button className="navigation-toggle" type="button" aria-controls="desktop-navigation"
      aria-expanded={navigationOpen} onClick={() => setNavigationOpen(value => !value)}>
      {navigationOpen ? "Close menu" : "Menu"}
    </button>
    {navigationOpen && <button className="navigation-backdrop" type="button" aria-label="Close navigation"
      onClick={() => setNavigationOpen(false)} />}
    <aside className="rail" id="desktop-navigation" aria-label="Main navigation">
      <a className="brand" href="/desktop/"><span className="brand-mark">E</span><span>ERSELMETZ<span className="muted"> AI</span></span></a>
      <p className="rail-label">COMMAND CENTER</p>
      <nav className="rail-navigation" aria-label="Main navigation">
        {groups.map(([label, links]) => <div className="rail-group" key={label}>
          <span className="rail-group-label">{label}</span>
          {links.map(([title, href]) => <a className="rail-link" href={href} key={href}
            onClick={() => setNavigationOpen(false)}>{title}</a>)}
        </div>)}
      </nav>
      <div className="rail-footer"><span className="pulse" /> LOCAL RUNTIME<br /><small>Loopback only - owner controlled</small></div>
    </aside>
    <section className="main-panel">{children}</section>
  </div>;
}

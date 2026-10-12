const workspaces = [
  { title: "Talk to your CEO", detail: "Start with a request, review the plan, and follow the work.", href: "/ui/chat", label: "Open coordinator chat", tone: "violet" },
  { title: "AI corporation", detail: "Review employees, positions, models, and provider connections.", href: "/ui/structure", label: "View corporation", tone: "cyan" },
  { title: "Workflow map", detail: "See recorded handoffs and the current review state.", href: "/ui/workflow-map", label: "Open workflow map", tone: "amber" },
];

export default function Home() {
  return <main className="shell">
    <aside className="rail" aria-label="Main navigation">
      <a className="brand" href="/desktop/"><span className="brand-mark">E</span><span>ERSELMETZ<span className="muted"> AI</span></span></a>
      <p className="rail-label">COMMAND CENTER</p>
      <a className="rail-link active" href="/desktop/">Overview</a>
      <a className="rail-link" href="/ui/chat">Coordinator chat</a>
      <a className="rail-link" href="/ui/structure">Corporation</a>
      <a className="rail-link" href="/ui/workflow-map">Workflow map</a>
      <a className="rail-link" href="/ui/providers">AI providers</a>
      <a className="rail-link" href="/ui/inventory">System inventory</a>
      <div className="rail-footer"><span className="pulse" /> LOCAL RUNTIME<br /><small>Loopback only · owner controlled</small></div>
    </aside>
    <section className="main-panel">
      <header className="topbar"><span>LOCAL COMMAND CENTER</span><a className="login-link" href="/ui/login">Owner sign in <span aria-hidden="true">↗</span></a></header>
      <div className="hero">
        <div className="eyebrow"><span className="eyebrow-line" /> AI OPERATIONS · YOUR MACHINE</div>
        <h1>Your AI corporation,<br /><span>ready when you are.</span></h1>
        <p>Talk with the coordinator. Review how work is assigned. Keep control of every action.</p>
        <a className="primary-action" href="/ui/chat">Open coordinator chat <span aria-hidden="true">→</span></a>
        <div className="orbital" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="core">E<span>AI</span></div><i className="node node-one"/><i className="node node-two"/><i className="node node-three"/></div>
      </div>
      <section className="workspaces" aria-labelledby="workspaces-title">
        <div className="section-heading"><div><p className="eyebrow">SYSTEM SPACES</p><h2 id="workspaces-title">Where would you like to go?</h2></div><span className="local-tag">● &nbsp; PRIVATE SESSION</span></div>
        <div className="cards">{workspaces.map((item, index) => <article className={`card ${item.tone}`} key={item.title}>
          <div className="card-head"><span className="card-index">0{index + 1}</span><span className="card-arrow" aria-hidden="true">↗</span></div>
          <h3>{item.title}</h3><p>{item.detail}</p><a href={item.href}>{item.label}<span aria-hidden="true"> →</span></a>
        </article>)}</div>
      </section>
      <footer className="footer"><span>ERSELMETZ AI · DESKTOP</span><span>All services stay on this computer unless you connect an online provider.</span></footer>
    </section>
  </main>;
}

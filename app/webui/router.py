from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


def _navigation(active_path: str, *, desktop_settings_available: bool = True) -> str:
    """Render the same concise, route-accurate navigation on every app page."""
    system_links = [
        ("Settings", "/desktop/settings/"), ("Software inventory", "/ui/inventory"),
        ("Performance readiness", "/ui/readiness"), ("Backup &amp; restore", "/ui/backup"),
        ("Documentation", "/ui/documentation"), ("Updates", "/ui/updates"),
        ("Preferences", "/ui/preferences"), ("Owner sign-in", "/ui/login"),
    ]
    if not desktop_settings_available:
        system_links = system_links[1:]
    groups = (
        ("PRIMARY", (("Home", "/ui"), ("Chat", "/ui/chat"), ("Projects", "/ui/projects"))),
        ("AI", (("Agents", "/ui/agents"), ("Employees", "/ui/employees"), ("Positions", "/ui/positions"),
                ("Organization map", "/ui/structure"), ("Providers &amp; models", "/ui/providers"),
                ("Sage Core", "/ui/sage-core"),
                ("3D visualization", "/ui/visualization"), ("Brain", "/ui/knowledge"))),
        ("OPERATIONS", (("Tasks", "/ui/tasks"), ("Workflows", "/ui/workflows"),
                        ("Workflow map", "/ui/workflow-map"), ("Activity", "/ui/activity"),
                        ("Computer automation", "/ui/automation"))),
        ("SYSTEM", tuple(system_links)),
    )
    parts = ['<nav class="navigation" aria-label="Main navigation"><h2>Navigate</h2><ul>']
    for label, links in groups:
        parts.append(f'<li class="navigation-group"><span>{label}</span><ul>')
        for text, href in links:
            current = ' aria-current="page"' if href == active_path else ""
            if href == "/ui/login":
                href += f"?next={active_path}"
            parts.append(f'<li><a href="{href}"{current}>{text}</a></li>')
        parts.append("</ul></li>")
    parts.append("</ul></nav>")
    return "".join(parts)


def _emergency_controls() -> str:
    return '''<section class="safety-panel" aria-labelledby="emergency-title">
      <div><p class="eyebrow">OWNER CONTROLS</p><h2 id="emergency-title">Capability controls</h2>
      <p>Inspect support, current activity, permissions, and session grants. Voice and media stay off until you start them.</p>
      <p id="emergency-state" role="status" aria-live="polite">Loading safety status…</p>
      <ul id="capability-indicators" class="capability-indicators" aria-label="Multimodal support and current activity">
        <li><strong>Microphone</strong><span id="capability-microphone-support">Checking support</span><span id="capability-microphone-activity">Unknown</span><span id="capability-microphone-state">Voice off; permission not checked. Capture limit: 10 seconds.</span><button id="capability-microphone-stop" type="button" hidden>Stop / cancel voice</button><span>Local recognition; cloud transcription needs separate consent.</span></li>
        <li><strong>Camera</strong><span id="capability-camera-support">Checking support</span><span id="capability-camera-activity">Unknown</span><span>One local frame; provider transfer requires per-turn consent.</span></li>
        <li><strong>Screen capture</strong><span id="capability-screen-support">Checking support</span><span id="capability-screen-activity">Unknown</span><span>One local frame; provider transfer requires per-turn consent.</span></li>
        <li><strong>Speech playback</strong><span id="capability-playback-support">Checking support</span><span id="capability-playback-activity">Unknown</span><span id="capability-playback-state">Playback state unknown until chat reports it.</span><button id="capability-playback-stop" type="button" hidden>Stop local playback and clear queue</button><span>Local device voices only; no online fallback.</span></li>
        <li><strong>Vision</strong><span id="capability-vision-support">Checking support</span><span>Inactive until an image is selected</span><span>Images stay temporary; provider transfer requires explicit per-turn consent.</span></li>
        <li><strong>Computer automation</strong><span id="capability-automation-support">Owner-gated; optional pack</span><span id="capability-automation-activity">Inactive</span><span>Exact allowlists, previews, one-action approvals, and emergency stop are on the <a href="/ui/automation">Computer automation</a> page.</span></li>
      </ul>
      <nav class="capability-shortcuts" aria-label="Open supported capability controls"><a href="/ui/chat#voice-panel">Voice controls</a><a href="/ui/chat#chat-capture-camera">Camera capture</a><a href="/ui/chat#chat-capture-screen">Screen capture</a><a href="/ui/chat#chat-images-heading">Vision and images</a></nav>
      <p id="emergency-activity" role="status" aria-live="polite">Microphone, playback, and capture activity are unknown until reported by this page.</p></div>
      <div class="safety-actions"><button id="emergency-stop" type="button" class="danger-action">Stop local protected actions</button>
      <button id="emergency-resume" type="button" disabled>Resume protected actions</button></div>
      <details><summary>Current permissions and session grants</summary>
      <p>Session permissions end at sign-out or session expiry. Temporary grants show their exact scope and expiry and can be revoked here.</p>
      <ul id="emergency-permissions" class="permission-list"></ul><h3>Temporary grants</h3>
      <ul id="emergency-grants" class="grant-list"></ul></details>
      <script type="module" src="/ui/static/emergency-stop.mjs"></script></section>'''


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def corporation_dashboard() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="Start chatting and review the current ERSELMETZ AI setup.">
          <title>Home — ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/dashboard.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">Your local AI workspace</span>
          </header>
          <div class="layout">
            {_navigation("/ui")}
            <main id="dashboard" class="content">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">YOUR LOCAL AI WORKSPACE</p>
                  <h1>Welcome to ERSELMETZ AI</h1>
                  <p class="dashboard-lead">Start a conversation, then explore projects and your AI team when you need them.</p>
                </div>
                <div class="dashboard-actions">
                  <a class="primary-action" href="/ui/chat">Start Chat <span aria-hidden="true">→</span></a>
                  <button id="dashboard-retry" type="button">Refresh status</button>
                </div>
              </div>
              <section class="setup-card" id="setup-panel" aria-labelledby="setup-title">
                <div class="setup-heading"><div><p class="eyebrow">FIRST RUN</p><h2 id="setup-title">Before your first chat</h2></div>
                  <span id="setup-state" class="setup-badge" role="status" aria-live="polite">Checking sign-in…</span></div>
                <p id="setup-detail" class="setup-detail">Checking the available setup information. No provider health check will run.</p>
                <div class="setup-links">
                  <a href="/ui/login?next=/ui">Sign in</a><a href="/ui/providers">Review providers &amp; models</a><a href="/ui/employees">Review AI team</a>
                </div>
                <p class="setup-boundary">Provider registration and model assignments show configuration only. Provider availability is not checked here; no model is downloaded or reassigned. Optional local media packs are managed in Capabilities &amp; privacy; installation requires reviewing and confirming their pinned wheels.</p>
              </section>
              <section class="dashboard-card"><p class="eyebrow">SETTINGS</p><h2>Capabilities &amp; privacy</h2><p class="muted">Review session permissions and protected activity controls.</p><a href="/ui/settings/capabilities">Open settings</a></section>
              <section class="dashboard-card suggestion-panel" aria-labelledby="suggestions-title">
                <div class="dashboard-heading">
                  <div><p class="eyebrow">OWNER CONTROLLED</p><h2 id="suggestions-title">Suggestions</h2>
                    <p class="muted">Read-only suggestions from current local workflow records. They never run actions.</p></div>
                  <button id="suggestions-refresh" type="button">Refresh suggestions</button>
                </div>
                <form id="suggestions-settings" class="suggestion-settings">
                  <label><input id="suggestions-enabled" type="checkbox"> Enable suggestions</label>
                  <label for="suggestions-quiet-start">Quiet period starts</label>
                  <input id="suggestions-quiet-start" type="time">
                  <label for="suggestions-quiet-end">Quiet period ends</label>
                  <input id="suggestions-quiet-end" type="time">
                  <button type="submit">Save suggestion settings</button>
                </form>
                <p class="muted">Quiet periods use this browser’s local time. Data is read only when this page loads or you refresh.</p>
                <p id="suggestions-status" role="status" aria-live="polite">Loading suggestion settings…</p>
                <ul id="suggestions-list" class="suggestion-list"></ul>
              </section>
              <div class="dashboard-grid">
                <section class="dashboard-card" id="status-panel" aria-labelledby="status-title">
                  <h2 id="status-title">Workspace identity</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading status...</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="workforce-panel" aria-labelledby="workforce-title">
                  <h2 id="workforce-title">AI team</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading workforce...</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="providers-panel" aria-labelledby="providers-title">
                  <h2 id="providers-title">Provider setup</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading provider information...</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="tasks-panel" aria-labelledby="tasks-title">
                  <h2 id="tasks-title">Tasks</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading tasks...</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="projects-panel" aria-labelledby="projects-title">
                  <h2 id="projects-title">Projects overview</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading projects...</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="activity-panel" aria-labelledby="activity-title">
                  <h2 id="activity-title">Recent activity</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading activity...</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="chat-panel" aria-labelledby="chat-title">
                  <h2 id="chat-title">Owner chat</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading owner chat…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="system-panel" aria-labelledby="system-title">
                  <h2 id="system-title">System &amp; resources</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading system snapshot…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="approvals-panel" aria-labelledby="approvals-title">
                  <h2 id="approvals-title">Protected-action approvals</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading approvals…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="knowledge-panel" aria-labelledby="knowledge-title">
                  <h2 id="knowledge-title">Corporation knowledge</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading retained knowledge…</p>
                  <div class="section-data" hidden></div>
                </section>
              </div>
            </main>
          </div>
          <script type="module" src="/ui/static/suggestions.mjs"></script>
        </body>
        </html>
        """
    )


@router.get("/ui/documentation", response_class=HTMLResponse, include_in_schema=False)
def documentation_portal_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="Internal Corporation Documentation Portal">
          <title>Documentation Portal â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/documentation.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/documentation")}
            <main class="content documentation-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Read-only Corporation knowledge</p>
                  <h1>Documentation &amp; Knowledge Portal</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                This internal portal reads approved Markdown files from
                <code>corporation_docs/</code> through the protected
                <code>documentation:read</code> API. It is separate from the
                public documentation website in <code>docs/</code>. In default API mode, browser
                sign-in is not configured; an authenticated session is required.
              </p>
              <div class="documentation-layout">
                <section class="management-card" aria-labelledby="documentation-list-title">
                  <div class="section-heading">
                    <h2 id="documentation-list-title">Documents</h2>
                    <button id="documentation-refresh" type="button">Refresh</button>
                  </div>
                  <p id="documentation-list-state" class="section-state" role="status" aria-live="polite">Loading documents...</p>
                  <ul id="documentation-list" class="record-list" aria-label="Documentation records"></ul>
                </section>
                <section class="management-card" aria-labelledby="documentation-detail-heading">
                  <h2 id="documentation-detail-heading">Document</h2>
                  <p id="documentation-detail-state" class="section-state" role="status" aria-live="polite">Select a document to read it.</p>
                  <h3 id="documentation-content-title" hidden></h3>
                  <pre id="documentation-content" class="documentation-content" hidden></pre>
                </section>
              </div>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/activity", response_class=HTMLResponse, include_in_schema=False)
def activity_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI Activity and logs">
          <title>Activity &amp; Logs â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/activity.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/activity")}
            <main class="content activity-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Read-only records</p>
                  <h1>Activity &amp; Logs</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Activity data comes from the protected API. In default API mode, browser sign-in is
                not configured; an authenticated session with activity read
                permission is required.
              </p>
              <section class="management-card" aria-labelledby="activity-list-title">
                <div class="section-heading">
                  <h2 id="activity-list-title">Activity records</h2>
                  <button id="activity-refresh" type="button">Refresh</button>
                </div>
                <p class="muted activity-boundary">
                  Shows only the bounded records returned by the API, not the
                  complete activity history. The API omits log message details.
                </p>
                <div class="activity-filters">
                  <label for="activity-limit">Maximum records</label>
                  <select id="activity-limit" name="limit">
                    <option value="10">10</option>
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100" selected>100</option>
                  </select>
                  <label for="activity-task-id">Task ID (optional)</label>
                  <input id="activity-task-id" name="task_id" autocomplete="off">
                </div>
                <p id="activity-list-state" class="section-state" role="status" aria-live="polite">Loading activity...</p>
                <ol id="activity-list" class="activity-list" aria-label="Activity records"></ol>
              </section>
              <section class="management-card" aria-labelledby="task-progress-title">
                <h2 id="task-progress-title">AI / Task execution progress</h2>
                <p class="muted">Select a Task ID in the filter above and refresh. Task progress requires task:read independently of activity:read. Local chat replies have no browser telemetry. This is a lifecycle snapshot, not a percentage or live stream.</p>
                <p id="task-progress-state" class="section-state" role="status" aria-live="polite"></p>
                <div id="task-progress"></div>
              </section>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/updates", response_class=HTMLResponse, include_in_schema=False)
def updates_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="Curated Corporation software updates">
          <title>Updates / Changelog â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/updates.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/updates")}
            <main class="content updates-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Curated project record</p>
                  <h1>Updates / Changelog</h1>
                </div>
                <button id="updates-refresh" type="button">Refresh</button>
              </div>
              <p class="auth-boundary">
                Curated development and release notes. Owner sign-in and update
                access are required. App update checks run only when you request them.
              </p>
              <details class="management-card" aria-labelledby="trusted-release-title">
                <summary id="trusted-release-title">Signed app updates</summary>
                <p>No background checks run. Select this button to make one owner-requested check against the fixed ERSELMETZ AI GitHub release origin. The app verifies a pinned Ed25519 signature before showing notes or migration details. Preparing an update downloads only a verified Windows x64 installer and creates a local SQLite recovery backup; installation remains a separate manual owner action.</p>
                <button id="release-check" type="button">Check for release now</button>
                <p id="release-state" class="section-state" role="status" aria-live="polite">No release check has been performed.</p>
                <div id="release-preview" hidden>
                  <h3 id="release-version"></h3>
                  <p><strong>Release notes</strong></p><p id="release-notes"></p>
                  <p><strong>Configuration migration preview</strong></p><p id="release-migration"></p>
                  <button id="release-prepare" type="button" disabled>Prepare verified installer and backup</button>
                  <p id="release-prepare-state" role="status" aria-live="polite"></p>
                </div>
              </details>
              <section class="management-card" aria-labelledby="updates-list-title">
                <h2 id="updates-list-title">Curated updates</h2>
                <p id="updates-list-state" class="section-state" role="status" aria-live="polite">Loading updates...</p>
                <ol id="updates-list" class="updates-list" aria-label="Corporation updates"></ol>
              </section>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/employees", response_class=HTMLResponse, include_in_schema=False)
def employee_management_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI employee management">
          <title>Employee Management â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/employees.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/employees")}
            <main class="content employee-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Organization</p>
                  <h1>Employee Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Sign in as the owner to view employees. Adding or changing an
                employee also requires the matching permission.
              </p>
              <div class="employee-layout">
                <section class="employee-card" aria-labelledby="employee-list-title">
                  <div class="section-heading">
                    <h2 id="employee-list-title">Employees</h2>
                    <button id="employee-refresh" type="button">Refresh</button>
                  </div>
                  <p id="employee-list-state" class="section-state" role="status" aria-live="polite">Loading employees...</p>
                  <ul id="employee-list" class="employee-list" aria-label="Employee records"></ul>
                </section>
                <section class="employee-card" aria-labelledby="employee-detail-title">
                  <h2 id="employee-detail-title">Employee details</h2>
                  <p id="employee-detail-state" class="section-state" role="status" aria-live="polite">Select an employee to view details.</p>
                  <div id="employee-detail" class="employee-detail" hidden></div>
                </section>
                <section class="employee-card create-card" aria-labelledby="employee-create-title">
                  <h2 id="employee-create-title">Create employee</h2>
                  <p class="muted">Enter an employee ID, name, and role. Responsibilities are optional. Agent links are managed elsewhere.</p>
                  <form id="employee-create-form">
                    <label for="employee-id">Employee ID</label>
                    <input id="employee-id" name="id" autocomplete="off" required>
                    <label for="employee-name">Name</label>
                    <input id="employee-name" name="name" autocomplete="name" required>
                    <label for="employee-role">Role</label>
                    <input id="employee-role" name="role" required>
                    <label for="employee-responsibilities">Responsibilities (one per line)</label>
                    <textarea id="employee-responsibilities" name="responsibilities" rows="3"></textarea>
                    <button id="employee-create-submit" type="submit">Create employee</button>
                    <p id="employee-create-state" class="section-state" role="status" aria-live="polite"></p>
                  </form>
                </section>
              </div>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/agents", response_class=HTMLResponse, include_in_schema=False)
def agents_page() -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Review and manage ERSELMETZ AI role profiles.">
    <title>Agents - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/agents.mjs"></script></head><body>
    <header class="site-header"><a class="brand" href="/ui">ERSELMETZ AI</a>
    <span class="product-label">Your local AI workspace</span></header><div class="layout">
    {_navigation("/ui/agents")}<main class="content agents-page">
      <div class="dashboard-heading"><div><p class="eyebrow">Organization</p><h1>Agents</h1></div>
        <button id="agent-refresh" type="button">Refresh</button></div>
      <p class="auth-boundary">Agents are role profiles that share the same AI models. Local model work runs one Agent at a time.</p>
      <div class="agent-toolbar"><div id="agent-filters" role="tablist" aria-label="Filter Agents">
        <button id="agent-tab-all" type="button" role="tab" aria-controls="agent-list-view" data-filter="all" aria-selected="true" tabindex="0">All</button>
        <button id="agent-tab-active" type="button" role="tab" aria-controls="agent-list-view" data-filter="active" aria-selected="false" tabindex="-1">Active</button>
        <button id="agent-tab-paused" type="button" role="tab" aria-controls="agent-list-view" data-filter="paused" aria-selected="false" tabindex="-1">Paused</button>
        <button id="agent-tab-error" type="button" role="tab" aria-controls="agent-list-view" data-filter="error" aria-selected="false" tabindex="-1">Error</button>
        <button id="agent-tab-builtin" type="button" role="tab" aria-controls="agent-list-view" data-filter="builtin" aria-selected="false" tabindex="-1">Built-in</button>
      </div><div role="group" aria-label="Agent display">
        <button type="button" data-view="list" aria-pressed="true">List</button>
        <button type="button" data-view="tree" aria-pressed="false">Organization tree</button>
      </div></div>
      <p id="agent-page-state" role="status" aria-live="polite">Loading Agents...</p>
      <div class="agents-workspace"><section id="agent-list-view" role="tabpanel" aria-labelledby="agent-tab-all" tabindex="0" aria-label="Agent list">
        <ul id="agent-list" class="agent-cards"></ul></section>
        <section id="agent-tree-view" hidden aria-label="Existing organization tree">
          <p>The organization tree shows the owner’s recorded Positions and reporting links.</p>
          <p id="agent-tree-state" role="status" aria-live="polite">Open this view to load current organization data.</p>
          <ul id="agent-organization-tree" class="organization-tree" aria-label="Recorded organization positions"></ul>
        </section>
        <aside id="agent-detail-card" class="agent-detail-card" aria-label="Agent details">
          <h2 id="agent-detail-title">Agent details</h2><p id="agent-detail-state">Select an Agent to review its profile.</p>
          <div id="agent-detail-content" hidden></div>
        </aside></div>
      <details class="agent-create"><summary>New Agent</summary>
        <p>Create a custom Agent by copying an existing role profile. Review its permissions before use.</p>
        <form id="agent-create-form"><label for="agent-create-source">Copy profile</label>
          <select id="agent-create-source" required></select><label for="agent-create-name">Agent name</label>
          <input id="agent-create-name" maxlength="128" required>
          <button id="agent-create-submit" type="submit">Create from profile</button>
          <p id="agent-create-state" role="status" aria-live="polite"></p></form>
      </details>
    </main></div></body></html>""")


@router.get("/ui/sage-core", response_class=HTMLResponse, include_in_schema=False)
def sage_core_page() -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="A live view of recorded ERSELMETZ AI Agent states and trace links.">
    <title>Sage Core - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/sage-core.mjs"></script></head><body>
    <header class="site-header"><a class="brand" href="/ui">ERSELMETZ AI</a>
    <span class="product-label">Your local AI workspace</span></header><div class="layout">
    {_navigation("/ui/sage-core")}<main class="content sage-core-page">
      <div class="dashboard-heading"><div><p class="eyebrow">Agent team</p><h1>Sage Core</h1></div>
        <button id="sage-core-refresh" type="button">Refresh</button></div>
      <p class="auth-boundary">Role profiles share the same models; local model work runs one Agent at a time. This view reads current Agent status and recent recorded traces. It cannot start or approve work.</p>
      <p id="sage-core-state" role="status" aria-live="polite">Loading current Agent states...</p>
      <div class="sage-core-controls" role="group" aria-label="Sage Core view">
        <button id="sage-core-map-mode" type="button" aria-pressed="true">Sigil map</button>
        <button id="sage-core-list-mode" type="button" aria-pressed="false">Accessible list</button>
        <label><input id="sage-core-reduced-motion" type="checkbox"> Reduce motion</label></div>
      <div class="sage-core-workspace"><section class="sage-core-display" aria-label="Agent visualization">
        <canvas id="sage-core-canvas" tabindex="0" aria-label="Sage Core Agent map. Use arrow keys to select Agents or switch to the accessible list."></canvas>
        <ul id="sage-core-accessible-list" class="sage-core-list" aria-label="Current Agents and trace links" hidden></ul>
      </section><aside class="sage-core-detail" aria-live="polite">
        <h2 id="sage-core-detail-title">Agent details</h2>
        <div id="sage-core-detail-content">Select an Agent to see its current profile and status.</div>
      </aside></div>
      <p class="muted" id="sage-core-limits">Approval records do not identify a requesting Agent, so no Agent is shown as waiting for approval without that provenance. Animation appears only for a recorded working or waiting state.</p>
    </main></div></body></html>""")


@router.get("/ui/positions", response_class=HTMLResponse, include_in_schema=False)
def position_management_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI position management">
          <title>Organizational Positions â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/positions.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/positions")}
            <main class="content">
              <div class="dashboard-heading">
                <div><p class="eyebrow">Organization</p><h1>Organizational positions</h1></div>
                <a class="back-link" href="/ui/employees">Employee management</a>
              </div>
              <p>Positions describe jobs and reporting lines. Employees and Agent/model
              assignments are managed separately. Titles never grant permissions.</p>
              <p id="position-state" role="status" aria-live="polite"></p>
              <section aria-labelledby="position-list-heading">
                <h2 id="position-list-heading">Positions</h2>
                <button id="position-new" type="button">Add position</button>
                <ul id="position-list" aria-label="Organizational position records"></ul>
              </section>
              <section aria-labelledby="position-editor-heading">
                <h2 id="position-editor-heading">Position details and editor</h2>
                <p id="position-detail-state" role="status" aria-live="polite">Select a position or add one.</p>
                <dl id="position-detail"></dl>
                <h3>Revision history</h3>
                <ol id="position-history" aria-label="Historical position revisions"></ol>
                <form id="position-form" class="ui-form">
                  <label for="position-title">Template</label>
                  <select id="position-title" required></select>
                  <label for="position-responsibilities">Responsibilities (one per line)</label>
                  <textarea id="position-responsibilities" rows="4" required></textarea>
                  <label for="position-reports-to">Reports to (position)</label>
                  <select id="position-reports-to"></select>
                  <label for="position-employee">Occupying Employee (optional)</label>
                  <select id="position-employee"></select>
                  <button id="position-save" type="submit">Create position</button>
                  <button id="position-deactivate" type="button" hidden>Deactivate</button>
                  <button id="position-remove" type="button" hidden>Remove position</button>
                  <p id="position-form-state" role="status" aria-live="polite"></p>
                </form>
              </section>
              <p>Deactivation preserves a position and its revision history. Removal is blocked while
              reporting positions, an Employee assignment, or revision history still references it.
              Resolve those references explicitly before removal. Use Backup &amp; restore
              to keep an encrypted copy of your app data.</p>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/providers", response_class=HTMLResponse, include_in_schema=False)
def provider_model_management_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI Provider and Model management">
          <title>Provider &amp; Model Management â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/providers.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/providers")}
            <main class="content provider-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Configuration</p>
                  <h1>Provider &amp; Model Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Sign in as the owner to view providers and models. Changes
                require the matching permission.
              </p>
              <div class="management-grid">
                <section class="management-card" aria-labelledby="provider-section-title">
                  <div class="section-heading">
                    <h2 id="provider-section-title">Configured Providers</h2>
                    <button id="provider-refresh" type="button">Refresh</button>
                  </div>
                  <p id="provider-list-state" class="section-state" role="status" aria-live="polite">Loading providers...</p>
                  <ul id="provider-list" class="record-list" aria-label="Configured providers"></ul>
                  <section class="management-detail" aria-labelledby="provider-detail-title">
                    <h3 id="provider-detail-title">Provider details</h3>
                    <p id="provider-detail-state" class="section-state" role="status" aria-live="polite">Select a provider to view details.</p>
                    <div id="provider-detail" hidden></div>
                  </section>
                  <section class="management-form" aria-labelledby="provider-create-title">
                    <h3 id="provider-create-title">Create provider</h3>
                    <p class="muted">Add a provider ID and name here. Set up its connection and credentials in Provider connections.</p>
                    <form id="provider-create-form">
                      <label for="provider-id">Provider ID</label>
                      <input id="provider-id" name="id" autocomplete="off" required>
                      <label for="provider-name">Name</label>
                      <input id="provider-name" name="name" required>
                      <button id="provider-create-submit" type="submit">Create provider</button>
                      <p id="provider-create-state" class="section-state" role="status" aria-live="polite"></p>
                    </form>
                  </section>
                </section>
                <section class="management-card" aria-labelledby="model-section-title">
                  <div class="section-heading">
                    <h2 id="model-section-title">Agent Model Assignments</h2>
                    <button id="model-refresh" type="button">Refresh</button>
                  </div>
                  <p class="muted">Assignments identify Agents by the ID returned by the Model API. No Employee/Agent details are modified here.</p>
                  <p id="model-list-state" class="section-state" role="status" aria-live="polite">Loading model assignments...</p>
                  <ul id="model-list" class="record-list" aria-label="Agent model assignments"></ul>
                  <section class="management-detail" aria-labelledby="model-detail-title">
                    <h3 id="model-detail-title">Assignment details</h3>
                    <p id="model-detail-state" class="section-state" role="status" aria-live="polite">Select an assignment to inspect or replace it.</p>
                    <div id="model-detail" hidden></div>
                  </section>
                  <nav class="setup-shortcuts" aria-label="Additional provider setup pages">
                    <h3>More setup</h3>
                    <a href="/ui/local-models">Local models</a>
                    <a href="/ui/provider-connections">Provider connections</a>
                    <a href="/ui/online-provider">Gemini online setup</a>
                    <a href="/ui/assignment-policy">Assignment recommendations</a>
                  </nav>
                </section>
              </div>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/tasks", response_class=HTMLResponse, include_in_schema=False)
def task_management_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI Task management">
          <title>Task Management â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/tasks.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/tasks")}
            <main class="content task-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Work management</p>
                  <h1>Task Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Sign in as the owner to view tasks. Creating or running a task
                also requires the matching permission.
              </p>
              <div class="task-layout">
                <section class="management-card" aria-labelledby="task-list-title">
                  <div class="section-heading">
                    <h2 id="task-list-title">Tasks</h2>
                    <button id="task-refresh" type="button">Refresh</button>
                  </div>
                  <p id="task-list-state" class="section-state" role="status" aria-live="polite">Loading tasks...</p>
                  <ul id="task-list" class="record-list" aria-label="Task records"></ul>
                  <section class="management-detail" aria-labelledby="task-detail-title">
                    <h3 id="task-detail-title">Task details</h3>
                    <p id="task-detail-state" class="section-state" role="status" aria-live="polite">Select a task to view its details.</p>
                    <div id="task-detail" hidden></div>
                  </section>
                  <section class="management-detail" aria-labelledby="task-preview-title">
                    <h3 id="task-preview-title">Routing preview</h3>
                    <p id="task-preview-state" class="section-state" role="status" aria-live="polite">Select a task to preview routing.</p>
                    <div id="task-preview" hidden></div>
                  </section>
                  <section class="management-detail" aria-labelledby="task-dispatch-title">
                    <h3 id="task-dispatch-title">Run a task locally</h3>
                    <p class="muted">Each run needs your confirmation and available local capacity. It uses Ollama on this computer, does not use tools, and never retries. A finished run does not confirm that its result is correct.</p>
                    <p id="task-dispatch-state" class="section-state" role="status" aria-live="polite">Checking dispatch permission...</p>
                    <button id="task-dispatch-refresh" type="button">Refresh dispatch queue</button>
                    <ul id="task-dispatch-queue" class="record-list" aria-label="Dispatch queue and execution states"></ul>
                    <label for="task-dispatch-resolution">Human resolution for a queued or interrupted claim</label>
                    <textarea id="task-dispatch-resolution" rows="3" maxlength="1024" disabled></textarea>
                    <button id="task-dispatch-resolve" type="button" disabled>Resolve selected entry without replay</button>
                  </section>
                </section>
                <section class="management-card" aria-labelledby="task-create-title">
                  <h2 id="task-create-title">Create task</h2>
                  <p class="muted">Task IDs and status are generated by the existing API. Choose no more than one optional routing selector. Routing preview does not execute an Agent or Provider.</p>
                  <form id="task-create-form" class="task-form">
                    <label for="task-title">Title</label>
                    <input id="task-title" name="title" required>
                    <label for="task-description">Description</label>
                    <textarea id="task-description" name="description" rows="4" required></textarea>
                    <label for="task-project-id">Project ID (optional)</label>
                    <input id="task-project-id" name="project_id">
                    <p class="muted task-project-note">The current task persistence does not reliably retain project association after reload.</p>
                    <fieldset>
                      <legend>Optional routing selector (choose at most one)</legend>
                      <label for="task-agent-id">Agent ID</label>
                      <input id="task-agent-id" name="agent_id">
                      <label for="task-role">Employee role</label>
                      <input id="task-role" name="role">
                      <label for="task-capability">Agent capability</label>
                      <input id="task-capability" name="capability">
                    </fieldset>
                    <button id="task-create-submit" type="submit">Create task</button>
                    <p id="task-create-state" class="section-state" role="status" aria-live="polite"></p>
                  </form>
                </section>
              </div>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/projects", response_class=HTMLResponse, include_in_schema=False)
def project_management_page() -> HTMLResponse:
    return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI Project management">
          <title>Project Management â€” ERSELMETZ AI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/projects.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI</a>
            <span class="product-label">ERSELMETZ AI Local App</span>
          </header>
          <div class="layout">
            {_navigation("/ui/projects")}
            <main class="content project-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Work management</p>
                  <h1>Project Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Sign in as the owner to view projects. Creating a project also
                requires the matching permission.
              </p>
              <div class="project-layout">
                <section class="management-card" aria-labelledby="project-list-title">
                  <div class="section-heading">
                    <h2 id="project-list-title">Projects</h2>
                    <button id="project-refresh" type="button">Refresh</button>
                  </div>
                  <p id="project-list-state" class="section-state" role="status" aria-live="polite">Loading projects...</p>
                  <ul id="project-list" class="record-list" aria-label="Project records"></ul>
                  <section class="management-detail" aria-labelledby="project-detail-title">
                    <h3 id="project-detail-title">Project details</h3>
                    <p id="project-detail-state" class="section-state" role="status" aria-live="polite">Select a project to view its details.</p>
                    <div id="project-detail" hidden></div>
                  </section>
                </section>
                <section class="management-card" aria-labelledby="project-create-title">
                  <h2 id="project-create-title">Create project</h2>
                  <p class="muted">The app creates the project ID and status. New projects start without tasks.</p>
                  <form id="project-create-form" class="project-form">
                    <label for="project-name">Name</label>
                    <input id="project-name" name="name" required>
                    <label for="project-description">Description (optional)</label>
                    <textarea id="project-description" name="description" rows="4"></textarea>
                    <button id="project-create-submit" type="submit">Create project</button>
                    <p id="project-create-state" class="section-state" role="status" aria-live="polite"></p>
                  </form>
                </section>
              </div>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/memory", response_class=HTMLResponse, include_in_schema=False)
def memory_page():
    """Compatibility route; Brain is the single user-facing knowledge workspace."""
    return RedirectResponse("/ui/knowledge#advanced-memory", status_code=307)


def _advanced_memory_sections() -> str:
    return """
      <details id="advanced-memory" class="management-card"><summary>Advanced scopes, correction, and search</summary>
      <div><p>Inspect exact conversation, Project, or Corporation scopes. Reads require memory:read; changes require memory:manage and owner authority.</p>
      <section class="management-card"><h2>Inspect stored memory</h2>
      <label for="memory-scope">Scope</label><select id="memory-scope"><option value="owner">My saved knowledge</option><option value="conversation">Conversation</option><option value="project">Project</option><option value="corporation">Corporation publication</option></select>
      <label for="memory-scope-id">Conversation, Project, or Corporation ID</label><input id="memory-scope-id" autocomplete="off">
      <button id="memory-refresh" type="button">Refresh</button>
      <p id="memory-state" role="status" aria-live="polite">Choose a scope and enter its resource ID.</p><ul id="memory-list"></ul></section>
      <section class="management-card"><h2>Inspect, correct, retain, or remove</h2>
      <p id="memory-detail-state" role="status" aria-live="polite"></p>
      <label for="memory-content">Content</label><textarea id="memory-content"></textarea>
      <label for="memory-expiry">Expiry (ISO timestamp with timezone)</label><input id="memory-expiry" type="text">
      <label><input id="memory-consent" type="checkbox">I explicitly consent to retaining this corrected memory until the stated expiry.</label>
      <button id="memory-save" type="button" disabled>Save correction / retention</button><button id="memory-remove" type="button" disabled>Remove memory</button>
      <p>Expired content cannot be restored through this page. Publications preserve their source expiry and stay immutable; owners may withdraw them. Removing a private source does not withdraw an independently published copy. Caller-held copies and backups cannot be revoked by this interface.</p>
      </section>
      <section class="management-card" aria-labelledby="semantic-memory-title"><h2 id="semantic-memory-title">Local semantic memory</h2>
      <p id="semantic-memory-status" role="status" aria-live="polite">Checking local capability...</p>
      <p>Semantic indexing is optional and happens only when you explicitly index an owned retained record. Search is limited to the selected scope. Similarity is a relevance hint, not proof. The Task 53 Documentation Portal remains read-only and is not indexed automatically.</p>
      <button id="semantic-index" type="button" disabled>Index selected owned record</button>
      <label for="semantic-query">Search this selected scope</label><input id="semantic-query" maxlength="1024">
      <button id="semantic-search" type="button">Search</button>
      <p id="semantic-search-state" role="status" aria-live="polite"></p><ol id="semantic-results" aria-label="Semantic retrieval results"></ol>
      </section>
      <section class="management-card" aria-labelledby="memory-relationships-title"><h2 id="memory-relationships-title">Source and retrieval relationships</h2>
      <p>Enter one exact scope above and refresh to inspect only records returned for it. This view does not aggregate other conversations, Projects, or owners. Listed links come from returned scope/provenance fields; semantic matches are retrieval candidates, not verified facts. Record content is hidden here.</p>
      <p id="memory-map-state" role="status" aria-live="polite">Choose a scope and refresh to load its authorized records.</p>
      <div id="memory-map-root" class="memory-map-root" role="group" aria-label="Selected memory scope"></div>
      <ol id="memory-relationship-list" class="memory-map-nodes" aria-label="Memory records and their recorded relationships"></ol>
      </section></div></details>"""


@router.get("/ui/knowledge", response_class=HTMLResponse, include_in_schema=False)
def owner_knowledge_page() -> HTMLResponse:
    return HTMLResponse("""<!doctype html><html lang="en"><head>
      <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Brain - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css"><link rel="stylesheet" href="/ui/static/brain-graph.css">
      <script type="module" src="/ui/static/knowledge.mjs"></script><script type="module" src="/ui/static/memory.mjs"></script></head><body>
      <main class="content brain-page"><nav aria-label="Brain navigation"><a href="/ui/chat">Chat</a> | <a href="/ui/login?next=/ui/knowledge">Owner sign-in</a> | <a href="#advanced-memory">Advanced scopes</a></nav>
      <p class="eyebrow">PRIVATE TO THIS OWNER</p><h1>Brain</h1>
      <p>Save notes or add local files for grounded chat. Items stay on this device, expire within 30 days, and are never shared without per-turn review and consent.</p>
      <section class="management-card" aria-labelledby="knowledge-add-title"><h2 id="knowledge-add-title">Add knowledge</h2>
      <form id="knowledge-note-form"><label for="knowledge-source">Note title</label><input id="knowledge-source" maxlength="128" value="Owner note">
      <label for="knowledge-content">Paste text (up to 8192 UTF-8 bytes)</label><textarea id="knowledge-content" rows="7" maxlength="8192"></textarea>
      <label for="knowledge-expiry">Keep for (days)</label><select id="knowledge-expiry"><option value="1">1 day</option><option value="7">7 days</option><option value="30" selected>30 days</option></select>
      <label><input id="knowledge-consent" type="checkbox"> I consent to store this note locally until its expiry.</label>
      <button id="knowledge-save" type="submit">Save note</button></form>
      <hr><form id="knowledge-upload-form"><label for="knowledge-file">Add files or a folder (UTF-8 text/code, CSV, Markdown, PDF, or DOCX; up to 1 MiB per file)</label>
      <label for="knowledge-file">Choose files</label><input id="knowledge-file" type="file" multiple accept=".txt,.md,.pdf,.docx,.csv,.py,.js,.mjs,.cjs,.ts,.tsx,.jsx,.json,.html,.css,.yaml,.yml,.toml,.sql,.sh,.ps1,.java,.c,.cpp,.go,.rs,.php,.cs,.kt,.swift,.vue,.svelte,.mdx,.rst,.log">
      <label for="knowledge-folder">Choose a folder</label><input id="knowledge-folder" type="file" multiple webkitdirectory directory accept=".txt,.md,.pdf,.docx,.csv,.py,.js,.mjs,.cjs,.ts,.tsx,.jsx,.json,.html,.css,.yaml,.yml,.toml,.sql,.sh,.ps1,.java,.c,.cpp,.go,.rs,.php,.cs,.kt,.swift,.vue,.svelte,.mdx,.rst,.log">
      <div id="brain-drop-zone" class="brain-drop-zone" role="button" tabindex="0" aria-label="Choose files or drop supported files here">Drop files here or use the picker above</div>
      <p id="brain-selection-status" role="status" aria-live="polite">No files selected.</p>
      <button id="knowledge-upload" type="submit">Add selected files</button></form>
      <section aria-labelledby="v3code-brain-import-title"><h3 id="v3code-brain-import-title">Import a legacy v3code Brain</h3>
      <p>Preview a v3code brain.json export up to 12 MiB. The preview reports counts and a digest, not note contents. Import ignores old vectors and knowledge_pack.json, groups chunks into bounded notes, keeps them in this owner-only Brain, requires the retention choice above, and never runs or downloads a model.</p>
      <label for="v3code-brain-file">Choose brain.json</label><input id="v3code-brain-file" type="file" accept=".json,application/json">
      <button id="v3code-brain-preview" type="button" disabled>Preview legacy Brain</button>
      <button id="v3code-brain-import" type="button" disabled>Import previewed notes</button>
      <p id="v3code-brain-state" role="status" aria-live="polite">Choose a v3code brain.json export to begin.</p></section>
      <ol id="brain-ingestion-list" aria-label="File processing status" aria-live="polite"></ol>
      <p id="knowledge-state" role="status" aria-live="polite"></p></section>
      <section class="management-card" aria-labelledby="knowledge-library-title"><h2 id="knowledge-library-title">Saved notes</h2>
      <p id="knowledge-index-status" role="status" aria-live="polite">Checking local semantic index...</p>
      <section class="management-card brain-map-card" aria-labelledby="brain-map-title">
      <h2 id="brain-map-title">Brain map</h2>
      <p>Nodes show your saved sources and their real text chunks. Source groups use file type or note type; lines connect chunks to their source only. Similarity is not measured here.</p>
      <div class="brain-map-controls"><button id="brain-map-view-toggle" type="button" aria-pressed="false">Show 3D map</button>
      <label><input id="brain-map-reduced-motion" type="checkbox"> Reduced motion</label><button id="brain-map-refresh" type="button">Refresh map</button></div>
      <p id="brain-map-status" role="status" aria-live="polite">Loading owner-only Brain map...</p>
      <div id="brain-map-canvas-wrap" hidden><canvas id="brain-map-canvas" aria-label="Brain source and chunk map. Use the source list below to select nodes by keyboard."></canvas></div>
      <p id="brain-map-frame-stats" aria-live="polite"></p><ol id="brain-map-ingestion" aria-label="Current Brain ingestion stages" aria-live="polite"></ol><ol id="brain-map-list" aria-label="All Brain sources and chunks"></ol>
      <section id="brain-map-detail" aria-live="polite"><h3 id="brain-map-detail-title">Select a source or chunk</h3><pre id="brain-map-detail-text"></pre></section>
      </section>
      <section aria-labelledby="brain-semantic-title"><h3 id="brain-semantic-title">Optional local semantic pack</h3>
      <p id="brain-faiss-state" role="status" aria-live="polite">Checking optional FAISS pack status…</p>
      <button id="brain-faiss-install" type="button" disabled>Review FAISS pack</button>
      <button id="brain-faiss-test" type="button" disabled>Test FAISS pack</button>
      <p id="brain-faiss-detail" role="status" aria-live="polite">The pack is separate from the base app. Install requires an explicit confirmation; it does not download an embedding model.</p></section>
      <section aria-labelledby="brain-embedding-title"><h3 id="brain-embedding-title">Local embedding model</h3>
      <p id="brain-embedding-state" role="status" aria-live="polite">Checking local Ollama model status…</p>
      <button id="brain-embedding-download" type="button" disabled>Review nomic-embed-text download</button>
      <button id="brain-embedding-test" type="button" disabled>Test local embeddings</button>
      <p id="brain-embedding-detail" role="status" aria-live="polite">The default is nomic-embed-text:latest. This app will never pull it without your confirmation.</p></section>
      <button id="knowledge-refresh" type="button">Refresh</button><ul id="knowledge-list"></ul>
      <p id="knowledge-detail" role="status" aria-live="polite">Select a note to inspect its index or remove it.</p>
      <button id="knowledge-index" type="button" disabled>Build or refresh local index</button>
      <button id="knowledge-inspect" type="button" disabled>Check index status</button>
      <button id="knowledge-delete" type="button" disabled>Forget selected note</button>
      <p>Indexing is local. When an embedding pack is unavailable, chat uses lexical retrieval. Deleting a note also invalidates its derived index. Use the Chat knowledge control to review exact citations before sending context to a provider.</p></section>
      """ + _advanced_memory_sections() + """
      </main></body></html>""")


@router.get("/ui/automation", response_class=HTMLResponse)
def computer_automation_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Computer automation - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/local-automation.mjs"></script></head><body>
    <main class="content"><nav aria-label="Automation navigation"><a href="/ui/chat">Chat</a> | <a href="/ui/settings/capabilities">Capabilities &amp; privacy</a></nav>
    <p class="eyebrow">OWNER-GATED LOCAL ACTIONS</p><h1>Computer automation</h1>
    <p>Allowlists start empty and last only for this app process. Browser actions use a visible, temporary browser on an exact HTTPS origin. Desktop actions can invoke one exact visible button in an allowlisted Windows app. No shell, keypress, coordinates, or automatic retries.</p>
    <section class="management-card"><h2>Safety status</h2><p id="automation-state" role="status" aria-live="polite">Checking local owner session and automation state.</p>
    <p id="automation-activity">No protected action is reported active.</p><button id="automation-stop" type="button" class="danger-action">Emergency stop protected actions</button></section>
    <section class="management-card"><h2>Visible browser</h2><p>Only exact HTTPS origins you add are available. This setting is volatile and does not grant general site access.</p>
    <label for="automation-origin">HTTPS origin (for example https://example.org)</label><input id="automation-origin" type="url" maxlength="512" autocomplete="url">
    <button id="automation-origin-add" type="button">Allow this origin for this run</button><ul id="automation-origins"></ul>
    <h3>Preview one action</h3><label for="browser-url">Page URL on the allowed origin</label><input id="browser-url" type="url" maxlength="2048">
    <label for="browser-action">Action</label><select id="browser-action"><option value="click">Click a named button/link</option><option value="fill_text">Fill a named text field</option></select>
    <label for="browser-role">Target role</label><select id="browser-role"><option>button</option><option>link</option><option>textbox</option></select>
    <label for="browser-name">Exact accessible name</label><input id="browser-name" maxlength="512">
    <label for="browser-value">Text to fill (only for a text field)</label><input id="browser-value" maxlength="2048">
    <button id="browser-preview" type="button">Inspect and preview</button><pre id="browser-preview-result" aria-live="polite"></pre>
    <button id="browser-run" type="button" hidden>Review exact action, approve, and run once</button></section>
    <section class="management-card"><h2>Windows UI Automation</h2><p>Requires the separately confirmed “Windows UI Automation support” pack. It only lists allowlisted apps and can invoke one exact direct-child button after preview and a fresh approval.</p>
    <label for="desktop-process">Executable name (for example notepad.exe)</label><input id="desktop-process" maxlength="132" autocomplete="off">
    <button id="desktop-process-add" type="button">Allow this app for this run</button><button id="desktop-discover" type="button">Find visible windows</button>
    <ul id="desktop-processes"></ul><label for="desktop-window">Visible window</label><select id="desktop-window"><option value="">Select an allowlisted window</option></select>
    <button id="desktop-buttons" type="button">Inspect available buttons</button><label for="desktop-button">Exact button</label><select id="desktop-button"><option value="">Select an inspected button</option></select>
    <button id="desktop-run" type="button" disabled>Preview, approve and invoke once</button></section>
    <section class="management-card"><h2>Recent automation trace</h2><button id="automation-refresh" type="button">Refresh status and trace</button><ul id="automation-traces"></ul></section>
    </main></body></html>""")


@router.get("/ui/settings/capabilities", response_class=HTMLResponse)
def capability_settings_page():
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Capabilities &amp; privacy - ERSELMETZ AI</title>
    <link rel="stylesheet" href="/ui/static/style.css">
    <link rel="stylesheet" href="/ui/static/chat-ui.css?v=195">
    </head><body><main class="content capability-settings-page">
    <nav aria-label="Settings navigation"><a href="/ui/chat">Chat</a> | <a href="/ui/preferences">Preferences</a> | <a href="/ui">Home</a></nav>
    <p class="eyebrow">SETTINGS</p><h1>Capabilities &amp; privacy</h1>
    <p>Review local capability support, session permissions, and temporary grants. Voice, camera, and screen capture remain off until you start them in Chat. Provider transfer and cloud turns still require separate per-use consent.</p>
    {_emergency_controls()}
    <section class="management-card"><h2>Use a capability in chat</h2>
      <p>Microphone, camera, screen capture, images, and selected knowledge are available from the Chat composer. Each capture is started by you and shows its state in the conversation.</p>
      <a class="primary-action" href="/ui/chat">Open Chat</a>
    </section>
    <section class="management-card" aria-labelledby="media-packs-title"><h2 id="media-packs-title">Optional local capability packs</h2>
      <p>Optional libraries are separate from the base app. Each pack shows exact pinned PyPI wheels and total size before an owner-confirmed, hash-checked isolated install. No speech model or Tesseract engine is included or downloaded. Windows UI Automation uses pywinauto with the existing scoped, exact-button approval service; PyAutoGUI is not used.</p>
      <p id="media-capability-packs-status" role="status" aria-live="polite">Checking pack status.</p>
      <div id="media-capability-packs" class="capability-pack-list"></div>
      <p>Eyes uses the existing bounded local OCR adapter; Tesseract and language data require a separate guided install. Ears uses the existing push-to-talk and local Faster-Whisper adapter; the speech model is selected separately. Voice supports the existing offline browser voice and an optional local Windows runtime. Online speech is not offered here.</p>
    </section></main><script type="module" src="/ui/static/capability-packs.mjs"></script></body></html>""")


@router.get("/ui/chat", response_class=HTMLResponse)
def coordinator_chat_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Chat - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <link rel="stylesheet" href="/ui/static/chat-ui.css?v=195">
    <script type="module" src="/ui/static/chat.mjs?v=195"></script></head><body class="chat-page">
    <main class="chat-app"><aside id="chat-sidebar" class="chat-sidebar" aria-label="Chat navigation">
      <div class="chat-sidebar-top"><a class="chat-brand" href="/ui/chat">ERSELMETZ AI</a><button id="chat-nav-toggle" type="button" aria-label="Collapse sidebar" aria-expanded="true">&#9776;</button></div>
      <label class="chat-search-label"><span class="visually-hidden">Search conversations</span><input id="chat-search" type="search" placeholder="Search chats" autocomplete="off"></label>
      <button id="chat-start" type="button" class="chat-new-button" data-close-navigation>&#43; New chat</button>
      <p class="chat-sidebar-label">Today</p><div id="chat-conversation-list" class="chat-conversation-list" role="group" aria-label="Recent conversations"></div>
      <p class="chat-sidebar-label" id="chat-earlier-label" hidden>Earlier</p><div id="chat-earlier-list" class="chat-conversation-list" role="group" aria-label="Earlier conversations"></div>
      <details id="chat-approval-inbox" class="chat-approval-inbox" hidden>
        <summary>Waiting on you <span id="chat-approval-count" aria-label="Pending approvals">0</span></summary>
        <p id="chat-approval-state" role="status" aria-live="polite">Approval requests have not been loaded.</p>
        <div id="chat-approval-items"></div>
        <button id="chat-approval-refresh" type="button">Refresh approvals</button>
      </details>
      <label class="visually-hidden" for="chat-conversation">Choose conversation</label><select id="chat-conversation" class="visually-hidden"></select>
      <details class="chat-advanced-nav"><summary>Advanced</summary><button id="chat-refresh" type="button" class="chat-sidebar-refresh">Refresh chats</button><button id="chat-close" type="button" class="chat-sidebar-close">Close conversation</button><nav aria-label="Advanced pages">
        <a href="/ui/knowledge">Brain</a><a href="/ui/employees">Employees</a><a href="/ui/positions">Positions</a><a href="/ui/structure">Organization map</a><a href="/ui/providers">Providers &amp; models</a><a href="/ui/visualization">3D visualization</a><a href="/ui/tasks">Tasks</a><a href="/ui/workflows">Workflows</a><a href="/ui/workflow-map">Workflow map</a><a href="/ui/activity">Activity</a><a href="/ui/inventory">Software inventory</a><a href="/ui/readiness">Performance readiness</a><a href="/ui/backup">Backup &amp; restore</a><a href="/ui/documentation">Documentation</a><a href="/ui/updates">Updates</a><a href="/ui/preferences">Preferences</a><a href="/ui/settings/capabilities">Capabilities &amp; privacy</a><a href="/ui/employee-chat">Employee chat</a><a href="/ui/login?next=/ui/chat">Owner sign-in</a>
      </nav></details><a class="chat-settings-link" href="/ui/settings/capabilities">Settings</a>
    </aside><section class="chat-workspace">
    <header class="chat-header">
      <button id="chat-menu-button" type="button" aria-label="Open navigation" aria-expanded="false">&#9776;</button>
      <a class="chat-header-brand" href="/ui/chat">ERSELMETZ AI</a>
      <span id="chat-header-model" class="chat-header-model" aria-live="polite"></span>
      <div class="chat-workspace-selectors" aria-label="Window workspace">
        <label for="workspace-model"><span class="visually-hidden">Window model</span><select id="workspace-model" aria-label="Window model"><option value="">Agent default model</option></select></label>
        <label for="chat-agent"><span class="visually-hidden">Window Agent</span><select id="chat-agent" aria-label="Window Agent"></select></label>
        <label for="workspace-project"><span class="visually-hidden">Window project</span><select id="workspace-project" aria-label="Window project"><option value="">Personal</option></select></label>
      </div>
      <label class="chat-autonomy-chip" for="chat-autonomy-level">Autonomy <select id="chat-autonomy-level" aria-label="Chat autonomy level"><option value="chat_only">Chat only</option><option value="auto_safe">Auto for safe actions</option><option value="ask_every_action">Ask before every action</option></select></label>
      <button id="chat-emergency-stop" class="chat-emergency-stop" type="button" aria-label="Emergency stop protected activity" title="Stop protected activity" hidden>&#9632;</button>
      </header>
    <div class="chat-body">
    <div class="chat-quick-start" id="local-quick-start" aria-label="Local model status" hidden><p id="local-quick-start-state" role="status" aria-live="polite">Checking Ollama at 127.0.0.1:11434&hellip;</p><button id="local-quick-start-action" type="button">Retry</button></div>
    <section class="panel" id="response-preferences-summary" aria-label="Current response preferences" hidden><p id="response-preferences-label">Loading owner response preferences...</p><a href="/ui/preferences">Change preferences</a></section>
    <p id="chat-identity" class="visually-hidden"></p><p id="chat-state" role="status" aria-live="polite" class="chat-inline-state"></p>
    <section id="chat-empty-state" class="chat-empty-state" aria-label="Start a conversation"><h1>How can I help?</h1>
      <div class="chat-examples"><button type="button" data-chat-example="Explain a topic simply">Explain a topic simply</button><button type="button" data-chat-example="Help me plan a project">Help me plan a project</button><button type="button" data-chat-example="Review a piece of code">Review a piece of code</button></div>
    </section>
    <section id="chat-history" aria-label="Conversation messages" aria-live="polite"></section>
    <div id="cloud-consent-panel" class="chat-consent-inline" hidden><p id="workspace-cloud-brief" hidden></p><label><input id="cloud-consent" type="checkbox"> I consent to send this message and the selected context shown above to Google Gemini for this reply only.</label></div>
    <div class="chat-compose-row"><details id="chat-settings" class="chat-settings-popover"><summary aria-label="Add image, camera, screen capture, or knowledge">&#43;</summary><div class="chat-settings-content">
      <details id="workspace-brief-panel" hidden><summary>Project brief</summary><p>Saved locally for this project's chats. It is reference text, not permission to act. Cloud replies require a fresh review and consent.</p><label for="workspace-brief">Project instructions and context</label><textarea id="workspace-brief" maxlength="2000" rows="4"></textarea><button id="workspace-brief-save" type="button">Save project brief</button></details>
      <button id="chat-add-image-action" type="button">Add image <span>Attach an image for this reply.</span></button>
      <button id="chat-camera-action" type="button">Camera <span>Capture one frame only when you choose.</span></button>
      <button id="chat-screen-action" type="button">Screen capture <span>Choose one display or window for this reply.</span></button>
      <label class="chat-knowledge-toggle"><input id="chat-knowledge-menu-toggle" type="checkbox"> Use my knowledge <span>Choose exact scopes and preview before sending.</span></label>
      <label class="chat-delegate-toggle"><input id="chat-delegate-once" type="checkbox"> Let the Coordinator assign one Agent for this reply <span>Sends this text to two local models in sequence. No tools, Brain data, cloud route, or repeat handoff.</span></label>
      <details class="chat-advanced"><summary>More chat options</summary>
      <p class="chat-advanced-links"><a href="/ui/settings/capabilities">Capabilities &amp; privacy</a> · <a href="/ui/providers">Providers &amp; models</a> · <a href="/ui/preferences">Response preferences</a></p>
      <button id="chat-theme-toggle" type="button">Switch to light theme</button>
    <details class="chat-advanced" id="chat-route-panel"><summary>Optional model suggestion (checked only when requested)</summary>
      <p>Prompt difficulty is uncertain. Suggestions use a local heuristic and observed installed/configured models; they do not prove quality or hardware fit. The configured model remains the default.</p>
      <button id="chat-route-check" type="button">Check suggestions for this prompt</button>
      <label for="chat-route-select">Optional route for this turn only</label><select id="chat-route-select" disabled><option value="">Use configured model</option></select>
      <p id="chat-route-state" role="status" aria-live="polite">No route check has run. No prompt has been sent to another provider.</p>
    </details>
    <details class="chat-advanced" id="chat-reviewed-tools"><summary>Reviewed read-only tools (off by default)</summary>
    <p>Only the calculator and one exact file selected from the read-only corporation_docs portal are available here. Results are untrusted input. Web search, arbitrary file access, code execution, and side effects are unavailable.</p>
    <fieldset><legend>Use a tool for this message only</legend>
      <label><input id="chat-tool-calculator-enabled" type="checkbox"> Calculate an expression</label>
      <label for="chat-tool-calculator-expression">Arithmetic expression</label><input id="chat-tool-calculator-expression" maxlength="256" placeholder="(12 + 8) * 3">
      <label><input id="chat-tool-document-enabled" type="checkbox"> Search one selected local documentation file</label>
      <label for="chat-tool-document-id">File from corporation_docs</label><select id="chat-tool-document-id"><option value="">Load documents after opening this section</option></select>
      <label for="chat-tool-document-query">Terms to find (max 160 characters)</label><input id="chat-tool-document-query" maxlength="160">
    </fieldset>
    <p id="chat-tools-state" role="status" aria-live="polite">Tools stay off until selected. Documentation lookup requires documentation:read and never leaves the local app unless this turn is explicitly consented to Gemini.</p>
    </details>
    <details class="chat-advanced" id="chat-knowledge-panel"><summary>Knowledge (off by default)</summary>
    <label><input id="chat-knowledge-enabled" type="checkbox"> Use my knowledge for this conversation</label>
    <fieldset id="chat-knowledge-scopes" disabled><legend>Select exact knowledge scopes</legend>
      <label><input id="chat-knowledge-owner" type="checkbox"> My saved notes</label>
      <label><input id="chat-knowledge-conversation" type="checkbox"> Retained notes in this conversation</label>
      <label><input id="chat-knowledge-extra-enabled" type="checkbox"> One Project or Corporation scope</label>
      <label for="chat-knowledge-extra-scope">Additional scope</label><select id="chat-knowledge-extra-scope"><option value="project">Project</option><option value="corporation">Corporation</option></select>
      <label for="chat-knowledge-extra-id">Exact Project or Corporation ID</label><input id="chat-knowledge-extra-id" maxlength="256">
    </fieldset>
    <button id="chat-knowledge-preview" type="button" disabled>Preview knowledge for this message</button>
    <p id="chat-knowledge-state" role="status" aria-live="polite">Knowledge retrieval is off. Choose each scope explicitly; no knowledge is added automatically.</p>
    <section id="chat-knowledge-preview-result" aria-label="Exact selected knowledge preview" hidden></section>
    <label><input id="chat-capture-local-prompt" type="checkbox" disabled> Include the exact assembled prompt for this local-model reply only (contains chat history and any selected notes).</label>
    </details>
    <p id="chat-input-provenance" role="status" aria-live="polite" hidden></p>
    <button id="chat-capture-screen" type="button" disabled>Capture display once</button>
    <p id="chat-capture-status" role="status" aria-live="polite">Screen capture is off. Choose a display/window only when you request a one-frame capture.</p>
    <button id="chat-capture-camera" type="button" disabled>Capture camera once</button>
    <p id="chat-camera-status" role="status" aria-live="polite">Camera is off. Capture one frame only when you choose this action.</p>
    <section class="panel" aria-labelledby="chat-images-heading">
      <h2 id="chat-images-heading">Temporary images</h2>
      <label for="chat-image-file">Attach JPEG or PNG (up to 2 MiB)</label><input id="chat-image-file" type="file" accept="image/jpeg,image/png">
      <button id="chat-image-upload" type="button">Attach selected image</button><div id="chat-image-list" aria-live="polite"></div>
      <div id="chat-image-transfer-preview" class="chat-image-transfer-preview" hidden></div>
      <div id="chat-image-consent-panel" hidden>
        <label><input id="chat-image-consent" type="checkbox"> For this reply only, send the selected image(s) and recent conversation context to the provider shown above.</label>
        <label><input id="chat-image-ocr" type="checkbox"> Run optional local OCR and include its text as untrusted image evidence.</label>
      </div>
      <p id="chat-image-status" role="status" aria-live="polite">No temporary images attached.</p>
    </section>
    <button id="chat-stop-request" type="button" disabled hidden>Stop waiting (remote outcome may be unknown)</button>
    <button id="chat-stop-display" type="button" disabled hidden>Stop display (generation continues)</button>
    <details class="chat-advanced"><summary>Optional voice input and reply audio</summary>
    <section class="panel" id="voice-panel" aria-labelledby="voice-heading">
    <h2 id="voice-heading">Optional voice input and reply audio</h2>
    <p>Voice is off until you start it. Each microphone session is started explicitly and stops after at most 10 seconds. Local speech uses on-device recognition only and never falls back to cloud.
    Cloud transcription is optional, sends a recording to Google Gemini only after per-use consent, and is limited to 10 seconds.
    The app keeps no audio after the request; transcripts go into the message box for review and are not sent to chat until you choose Send.
    Gemini API may retain request data under Google's account tier and policy. This app cannot configure or verify provider retention, or cap Google's final invoice; its budget only limits this app's requests.
    Check your Google account policy first. Do not record passwords, API keys, or other sensitive information.</p>
    <label for="voice-mode">Speech processing</label><select id="voice-mode">
      <option value="local" selected>Browser on-device speech recognition (no cloud fallback)</option>
      <option value="local-model">Optional local Faster-Whisper model</option>
      <option value="cloud">Cloud transcription through Google Gemini (consent and ceiling required)</option>
    </select>
    <label for="voice-language">Recognition language tag</label><input id="voice-language" value="en-US" maxlength="16">
    <label for="voice-local-model">Installed local speech model</label><select id="voice-local-model" disabled><option value="">Checking local model folder…</option></select>
    <p id="voice-local-model-state" role="status" aria-live="polite">Optional Faster-Whisper is not installed by default.</p>
    <button id="voice-start" type="button" disabled>Start voice</button>
    <button id="voice-install-local" type="button" hidden>Install browser speech language pack</button><p class="muted">This optional language pack is managed by the browser for on-device speech. Other local media packs require explicit owner confirmation in <a href="/ui/settings/capabilities">Capabilities &amp; privacy</a>.</p>
    <button id="voice-transcribe" type="button" hidden>Transcribe via Gemini (send recording)</button>
    <button id="voice-stop" type="button" hidden>Stop / discard voice request</button>
    <p id="voice-cloud-consent-panel"><label><input id="voice-cloud-consent" type="checkbox">
    For this recording only, I consent to send the audio to Google Gemini for transcription. Google's account data practices are controlled by the connected account, not this app. A stopped request may still be processed remotely.</label></p>
    <form id="voice-budget-form">
      <label for="voice-budget-cents">Cloud voice app-run budget (US cents; 1-100; not a provider billing cap)</label>
      <input id="voice-budget-cents" type="number" min="1" max="100" step="1" value="5">
      <button id="voice-budget-save" type="submit">Set cloud ceiling</button>
    </form>
    <p id="voice-budget-state" role="status" aria-live="polite">Cloud transcription is off until you set a per-run spending ceiling.</p>
    <h3>Offline reply speech</h3>
    <p>Uses only local voices exposed by this device's browser. Choose the output language and voice explicitly. Reply speech is local only; no online service is available to receive chat text. Clicking another reply while playback is active adds it to a small bounded queue. Stop and clear the queue at any time. Speech output grants no action permission.</p>
    <label for="voice-output-language">Reply speech language tag</label><input id="voice-output-language" value="en-US" maxlength="16">
    <label for="voice-output-voice">Local reply voice</label><select id="voice-output-voice" disabled><option value="">Checking local voices…</option></select>
    <p id="voice-output-state" role="status" aria-live="polite">Checking local speech output availability. No online fallback is used.</p>
    <button id="voice-stop-playback" type="button" disabled>Stop and clear local speech queue</button>
    <p id="voice-state" role="status" aria-live="polite">Typed chat remains available while voice is disabled.</p>
    </section></details>
    <details class="chat-advanced"><summary>Study an approved GitHub repository</summary>
    <section class="panel" aria-labelledby="repository-study-heading">
    <h2 id="repository-study-heading">Study an approved GitHub repository</h2>
    <p>Uses only the configured repository allowlist and bounded GitHub reads. Source content is untrusted;
    it is not sent to a chat model, installed, or executed. Results are evidence for human review, not approval.</p>
    <form id="repository-study-form">
    <label for="repository-study-objective">Capability or integration goal</label>
    <textarea id="repository-study-objective" maxlength="1024" required></textarea>
    <label for="repository-study-owner">GitHub owner</label><input id="repository-study-owner" maxlength="100" required>
    <label for="repository-study-name">Repository</label><input id="repository-study-name" maxlength="100" required>
    <button id="repository-study-submit" type="submit" disabled>Study repository</button>
    </form>
    <p id="repository-study-state" role="status" aria-live="polite"></p>
    <pre id="repository-study-result" aria-live="polite"></pre>
    </section></details>
    <details class="chat-advanced"><summary>Review a chat proposal</summary>
    <section class="panel" aria-labelledby="chat-task-proposal-heading">
    <h2 id="chat-task-proposal-heading">Review a chat proposal</h2>
    <p>Only an explicitly confirmed proposal creates a pending Task. It does not execute work.
    The local-owner flow has a separate <code>chat-task:create</code> permission.</p>
    <label for="chat-task-source">Completed coordinator proposal</label><select id="chat-task-source"></select>
    <label for="chat-task-objective">Objective / Task title</label><input id="chat-task-objective" maxlength="1024">
    <label for="chat-task-agent">Responsible Agent</label><select id="chat-task-agent"></select>
    <label for="chat-task-project">Project ID</label><input id="chat-task-project" maxlength="256">
    <label for="chat-task-context-query">Optional authorized context query</label><input id="chat-task-context-query" maxlength="1024">
    <label for="chat-task-context-scope">Context scope</label><select id="chat-task-context-scope">
    <option value="">No additional retained context</option><option value="conversation">Conversation</option>
    <option value="project">Project</option><option value="corporation">Corporation</option></select>
    <label for="chat-task-context-id">Context scope ID</label><input id="chat-task-context-id" maxlength="256">
    <label for="chat-task-outcome">Expected outcome</label><textarea id="chat-task-outcome" maxlength="1024"></textarea>
    <label for="chat-task-verification">Verification method</label><textarea id="chat-task-verification" maxlength="1024"></textarea>
    <label for="chat-task-evidence">Expected evidence</label><textarea id="chat-task-evidence" maxlength="1024"></textarea>
    <button id="chat-task-prepare" type="button">Prepare proposal for review</button>
    <p id="chat-task-state" role="status" aria-live="polite"></p>
    <pre id="chat-task-review" aria-live="polite"></pre>
    <button id="chat-task-confirm" type="button" disabled>Confirm and create pending Task</button>
    </section></details>
    <details class="chat-advanced"><summary>Conversation and provider details</summary>
    <p>History is in memory and is lost when the app restarts. Up to 100 conversations and 200 messages
    per conversation are retained for this run. Configured loopback Ollama can stream responses;
    the Stop display control does not cancel provider generation; Stop waiting interrupts this app's request but cannot confirm remote cancellation. For the default local Agent, Ollama and llama3.2:3b must already be available;
    use Local model setup to refresh installed models and explicitly select one. Do not paste API keys here; configure Gemini in its separate online setup page.</p></details>
    </details></div></details>
    <form id="chat-form" class="chat-composer">
    <label class="visually-hidden" for="chat-input">Message (up to 8192 UTF-8 bytes)</label>
    <textarea id="chat-input" rows="1" maxlength="8192" required placeholder="Message ERSELMETZ AI&#8230;" aria-label="Message ERSELMETZ AI"></textarea>
    <button id="chat-mic" type="button" aria-label="Start voice input">&#127908;</button>
    <button id="chat-send" type="submit" aria-label="Send message">Send</button></form></div>
    </div></section></main></body></html>""")


@router.get("/ui/inventory", response_class=HTMLResponse, include_in_schema=False)
def inventory_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Software inventory - ERSELMETZ AI</title>
    <link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/inventory.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui">Dashboard</a> |
    <a href="/ui/providers">Providers</a> | <a href="/ui/login?next=/ui/inventory">Local sign-in / sign-out</a></nav>
    <p class="eyebrow">Local software inventory</p><h1>Software &amp; integration inventory</h1>
    <p>This page reports supported app/runtime/provider sources and provides a tightly scoped
    owner-confirmed lifecycle for Microsoft VS Code through the user-scope WinGet adapter.
    Existing installs not initiated by ERSELMETZ AI remain read-only.
    Unknown means the source could not verify a value.</p>
    <button id="inventory-refresh" type="button">Refresh inventory</button>
    <p id="inventory-status" role="status" aria-live="polite">Sign in, then load the inventory.</p>
    <div id="inventory-records" class="dashboard-grid" aria-live="polite"></div>
    <section class="management-card" aria-labelledby="software-manager-title">
      <h2 id="software-manager-title">Supported software lifecycle</h2>
      <p id="software-manager-state" role="status" aria-live="polite">Sign in to inspect supported software.</p>
      <dl id="software-manager-details"></dl>
      <div id="software-manager-controls" hidden>
        <label for="software-action">Operation</label>
        <select id="software-action"><option value="install">Install</option><option value="update">Update</option><option value="version">Change target version (upgrade only)</option><option value="pin">Pin version</option><option value="unpin">Remove version pin</option><option value="remove">Remove software</option></select>
        <label for="software-version">Exact version (required for install, update, change and pin)</label>
        <input id="software-version" inputmode="decimal" maxlength="32" autocomplete="off">
        <button id="software-preview" type="button">Preview operation</button>
      </div>
      <div id="software-preview-panel" hidden>
        <h3>Review this exact operation</h3><dl id="software-preview-details"></dl>
        <button id="software-confirm" type="button">Confirm this operation</button>
      </div>
      <p id="software-operation-result" role="status" aria-live="polite"></p>
      <ul id="software-manager-limitations"></ul>
    </section>
    <section class="management-card"><h2>Inspection limits</h2><ul id="inventory-limitations"></ul></section>
    </main><script type="module" src="/ui/static/quick-start.mjs"></script></body></html>""")


@router.get("/ui/preferences", response_class=HTMLResponse)
def owner_preferences_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Response preferences - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/preferences.mjs"></script></head><body>
    <main class="content"><nav aria-label="Preferences navigation"><a href="/ui">Home</a> | <a href="/ui/chat">Chat</a> | <a href="/ui/login?next=/ui/preferences">Owner sign-in</a></nav>
    <p class="eyebrow">OWNER SETTINGS</p><h1>Response preferences</h1>
    <p>Autonomy controls decide whether reviewed safe actions may run. They never grant permissions, enable Operator, approve cloud transfer, or bypass spending limits.</p>
    <form id="preferences-form">
      <label for="preference-mode">Response style</label><select id="preference-mode"><option value="balanced">Balanced</option><option value="concise">Concise</option><option value="friendly">Friendly</option><option value="formal">Formal</option><option value="technical">Technical</option></select>
      <label for="preference-locale">Response locale</label><select id="preference-locale"><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option><option value="fil-PH">Filipino</option></select>
      <label for="preference-detail">Response detail</label><select id="preference-detail"><option value="brief">Brief</option><option value="standard">Standard</option><option value="detailed">Detailed</option></select>
      <label for="preference-autonomy">Chat autonomy</label><select id="preference-autonomy"><option value="chat_only">Chat only</option><option value="auto_safe">Auto for safe actions (default)</option><option value="ask_every_action">Ask before every action</option></select>
      <label for="preference-voice-mode">Optional reply speech preference</label><select id="preference-voice-mode"><option value="off">Off</option><option value="local">Local device voice when manually requested</option></select>
      <label for="preference-voice-language">Local voice language</label><select id="preference-voice-language"><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option><option value="fil-PH">Filipino</option></select>
      <label for="preference-voice-id">Local voice identifier (optional)</label><input id="preference-voice-id" maxlength="160" autocomplete="off">
      <button type="submit">Save preferences</button><button id="preferences-reset" type="button">Reset to defaults</button><a id="preferences-export" href="/api/local/preferences/export">Export preferences JSON</a>
    </form><p id="preferences-state" role="status" aria-live="polite"></p>
    <p id="preferences-retention">Preferences are stored locally in the application database until reset or that database is removed. They contain presentation choices only; chat content and credentials are not stored.</p>
    </main></body></html>""")


@router.get("/ui/backup", response_class=HTMLResponse)
def backup_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Backup &amp; restore - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/backup.mjs"></script></head><body>
    <main class="content"><nav aria-label="Backup navigation"><a href="/ui">Home</a> | <a href="/ui/login?next=/ui/backup">Owner sign-in</a></nav>
    <p class="eyebrow">LOCAL OWNER CONTROL</p><h1>Backup &amp; restore</h1>
    <p>Encrypted local backup files use a passphrase you choose. The app never stores or recovers it. Keep the file and passphrase together safely; losing the passphrase makes the backup unreadable.</p>
    <section class="management-card"><h2>Preview and export</h2>
      <button id="diagnostics-export" type="button">Export safe diagnostics</button>
      <p>Diagnostics contain application, Python, platform, and schema metadata only. They exclude records, logs, credentials, local paths, provider checks, and model or hardware claims.</p>
      <label><input id="backup-private" type="checkbox"> Include private app data (Tasks, projects, conversations, messages, and memory)</label>
      <button id="backup-preview" type="button">Preview included data</button><pre id="backup-preview-result" aria-live="polite"></pre>
      <label for="backup-passphrase">Backup passphrase (12–1024 characters)</label><input id="backup-passphrase" type="password" minlength="12" maxlength="1024" autocomplete="new-password">
      <button id="backup-export" type="button">Create encrypted backup</button>
    </section>
    <section class="management-card"><h2>Inspect and restore</h2>
      <label for="backup-file">Choose an ERSELMETZ AI backup file</label><input id="backup-file" type="file" accept=".erselbackup,application/vnd.erselmetz.backup">
      <label for="restore-passphrase">Backup passphrase</label><input id="restore-passphrase" type="password" minlength="12" maxlength="1024" autocomplete="current-password">
      <button id="backup-inspect" type="button">Verify and preview backup</button><pre id="backup-inspect-result" aria-live="polite"></pre>
      <label for="restore-confirmation">Type RESTORE to confirm</label><input id="restore-confirmation" maxlength="16" autocomplete="off">
      <button id="backup-restore" type="button" class="danger-action">Restore backup</button>
    </section>
    <section class="management-card"><h2>Limits</h2><p>Restore creates an encrypted pre-restore copy in the local ERSELMETZ AI backups folder. Restart the app after restore. Retention and deletion are owner-managed. Provider account data, API credentials held outside this database, downloaded model files, and remote data cannot be exported or erased here. No cloud destination is available.</p></section>
    <p id="backup-state" role="status" aria-live="polite"></p></main></body></html>""")


@router.get("/ui/readiness", response_class=HTMLResponse)
def readiness_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Performance readiness - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/readiness.mjs"></script></head><body>
    <main class="content"><nav aria-label="Readiness navigation"><a href="/ui">Home</a> | <a href="/ui/visualization">Rendering evidence</a> | <a href="/ui/login?next=/ui/readiness">Owner sign-in</a></nav>
    <p class="eyebrow">LOCAL EVIDENCE</p><h1>Performance readiness</h1>
    <p>Refresh returns a response-only snapshot of this app run's setup time, current process memory, recorded model assignments, and prior queue claims. It is not persisted. It never runs a model, changes work, or estimates hardware fit.</p>
    <button id="readiness-refresh" type="button">Refresh evidence</button>
    <p id="readiness-state" role="status" aria-live="polite">Evidence has not been requested.</p>
    <pre id="readiness-report" aria-live="polite"></pre>
    <p>Rendering evidence is measured on this device in the 3D visualization page. Model workload performance and hardware fit remain UNKNOWN until a measured, owner-selected workload and supported hardware profile exist. Missing evidence is not a readiness result.</p>
    </main></body></html>""")


@router.get("/ui/employee-chat", response_class=HTMLResponse)
def employee_chat_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Individual Employee chat - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/employee-chat.mjs"></script></head><body>
    <main class="content chat-content"><nav aria-label="Chat navigation">
    <a href="/ui">Dashboard</a> | <a href="/ui/login?next=/ui/employee-chat">Local sign-in / sign-out</a> |
    <a href="/ui/employees">Employees</a> | <a href="/ui/chat">Coordinator chat</a></nav>
    <h1>Individual Employee chat</h1>
    <p>Each conversation captures one registered Employee and the Agent assigned when it starts.
    Messages and history are isolated per conversation and owner. Reassignments do not move an
    existing conversation; start a new one to use a changed Agent connection. Chats do not create
    Tasks, execute tools, or include Employee profiles or Task content automatically.</p>
    <p>Conversation text is stored only when you select local history retention. Retained chat is unencrypted in the local app database until you explicitly delete it; no cloud sync is used.</p>
    <label><input id="individual-chat-retain" type="checkbox"> Retain this conversation on this Windows profile so it can be reviewed after restart</label>
    <label for="individual-employee">Employee with an assigned Agent</label>
    <select id="individual-employee"></select>
    <button id="individual-chat-new" type="button">Start individual conversation</button>
    <label for="individual-conversation">Your individual conversations</label>
    <select id="individual-conversation"></select>
    <button id="individual-chat-refresh" type="button">Refresh</button>
    <button id="individual-chat-close" type="button" disabled>Close conversation</button>
    <button id="individual-chat-delete-history" type="button" disabled>Delete retained history</button>
    <p id="individual-chat-identity"></p>
    <p id="individual-chat-state" role="status" aria-live="polite"></p>
    <section id="individual-chat-history" aria-label="Individual conversation messages" aria-live="polite"></section>
    <form id="individual-chat-form">
      <label for="individual-chat-input">Message (up to 8192 UTF-8 bytes)</label>
      <textarea id="individual-chat-input" rows="4" maxlength="8192" required></textarea>
      <button id="individual-chat-send" type="submit" disabled>Send</button>
      <button id="individual-chat-stop-display" type="button" disabled hidden>Stop display (generation continues)</button>
    </form>
    <p id="individual-cloud-consent-panel" hidden><label><input id="individual-cloud-consent" type="checkbox">
    I consent to send this message and recent history from this individual conversation to Google Gemini for this reply.</label></p>
    <p>Unretained history is held in memory for this app run only. Retained history is read-only after restart. Gemini requires per-turn consent and remains
    subject to its connection expiry, request limit, and owner-managed billing controls.</p>
    </main></body></html>""")


@router.get("/ui/local-models", response_class=HTMLResponse)
def local_model_setup_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Local model setup - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/local-models.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/chat">Coordinator chat</a> | <a href="/ui/employee-chat">Individual Employee chat</a> | <a href="/ui/assignment-policy">Assignment recommendations</a> | <a href="/ui/login?next=/ui/local-models">Local sign-in / sign-out</a></nav>
    <h1>Local Agent model setup</h1><p>Available only with explicit local-owner access. Refresh checks the
    configured supported loopback provider without downloading or generating anything.</p>
    <label for="model-agent">Existing Agent</label><select id="model-agent"></select>
    <button id="model-refresh" type="button">Refresh installed models</button>
    <p id="model-state" role="status" aria-live="polite"></p><p id="model-evidence"></p>
    <label for="model-installed">Installed model</label><select id="model-installed" disabled></select>
    <button id="model-select" type="button" disabled>Preview and select for Agent</button>
    <p>Installation and service availability do not prove hardware capacity, compatibility or future
    execution success. Selection is rechecked and rejected while the Agent has active work. The
    confirmation previews assigned Tasks and owner conversations. A changed assignment affects only
    future calls; old conversation history and Task ownership remain unchanged. Changes apply to this
    app run only.</p>
    </main></body></html>""")


@router.get("/ui/assignment-policy", response_class=HTMLResponse)
def assignment_policy_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Assignment policy - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/assignment-policy.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui">Dashboard</a> | <a href="/ui/local-models">Manual Agent model setup</a> | <a href="/ui/online-provider">Gemini setup</a> | <a href="/ui/login?next=/ui/assignment-policy">Local sign-in / sign-out</a></nav>
    <h1>Model recommendations</h1>
    <p>Available only through explicit local-owner access. Recommendations are disabled until you save an owner-approved policy. They never change an Agent assignment, connect a provider, send data, or grant online consent.</p>
    <details><summary>Advanced policy configuration</summary>
    <p>Supply a fresh inventory snapshot (at most 24 hours old), traceable capability evidence (tested evidence must be at most 30 days old), registered provider IDs, and an explicit budget in one owner-defined unit. A declaration is shown as unknown and never qualifies a model.</p>
    <details><summary>Policy JSON shape</summary><pre>{
  "enabled": true,
  "allowed_provider_ids": ["YOUR_REGISTERED_PROVIDER"],
  "online_enabled": false,
  "budget_limit": "1",
  "budget_unit": "owner-defined units per request",
  "candidates": [{
    "provider_id": "YOUR_REGISTERED_PROVIDER",
    "model_id": "YOUR_INVENTORIED_MODEL",
    "inventory_kind": "local",
    "inventory_models": ["YOUR_INVENTORIED_MODEL"],
    "inventory_reference": "source-reference",
    "inventory_observed_at": "2026-10-04T12:00:00+00:00",
    "estimated_cost": "0",
    "evidence": [{
      "capability": "EXACT_AGENT_CAPABILITY",
      "kind": "tested",
      "supports": true,
      "reference": "test-report-reference",
      "observed_at": "2026-10-04T12:00:00+00:00"
    }]
  }]
}</pre><p>Replace every example identifier and timestamp with current owner-reviewed facts. The example is not evidence of an installed model, tested competence, provider access, zero cost, or available capacity. Do not paste credentials.</p></details>
    <label for="assignment-policy-config">Owner-approved policy JSON</label>
    <textarea id="assignment-policy-config" rows="22" spellcheck="false" autocomplete="off"></textarea>
    <p><button id="assignment-policy-save" type="button">Save and enable recommendations</button>
    <button id="assignment-policy-disable" type="button">Disable recommendations</button></p></details>
    <p><button id="assignment-policy-preview" type="button">Refresh preview</button></p>
    <p>Manual assignments always remain authoritative. Use Manual Agent model setup to override a recommendation with its impact preview and confirmation. Disabling clears the saved policy data and is the complete undo because this policy never applies assignments; any separately confirmed manual change can be reversed only through the existing manual setup flow.</p>
    <p id="assignment-policy-state" role="status" aria-live="polite"></p>
    <pre id="assignment-policy-results" tabindex="0" role="region" aria-label="Recommendation preview" aria-live="polite">No preview loaded yet.</pre>
    </main></body></html>""")


@router.get("/ui/online-provider", response_class=HTMLResponse)
def local_online_provider_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Gemini online setup - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/online-provider.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/chat">Coordinator chat</a> | <a href="/ui/assignment-policy">Assignment recommendations</a> | <a href="/ui/login?next=/ui/online-provider">Local sign-in / sign-out</a></nav>
    <h1>Gemini online setup</h1>
    <p>Google receives the message, recent conversation history, and configured chat context only
    when you check the separate consent box for a chat turn. Setup sends a key only to the fixed
    Google Gemini API endpoint to list models; it never enters ordinary chat history.</p>
    <p>Only the standard Google AIza API-key format is accepted. Model discovery is an explicit
    connection check; unsupported formats are rejected before any provider call. To rotate a
    connected key, disconnect and erase it first, then enter and explicitly reconnect the new key.
    Per-turn cloud consent and the request limits below remain in force.</p>
    <label for="gemini-key">Restricted Gemini API key</label><input id="gemini-key" type="password" autocomplete="off" maxlength="4096">
    <button id="gemini-discover" type="button">Verify key and list models</button>
    <p id="gemini-state" role="status" aria-live="polite"></p><p id="gemini-usage"></p>
    <label for="gemini-agent">Agent</label><select id="gemini-agent"></select>
    <label for="gemini-model">Model with generation support</label><select id="gemini-model" disabled></select>
    <button id="gemini-connect" type="button" disabled>Preview and connect Gemini to Agent</button>
    <button id="gemini-refresh" type="button" disabled>Refresh models</button>
    <button id="gemini-disconnect" type="button" disabled>Disconnect and erase key</button>
    <button id="gemini-clear" type="button" disabled>Erase staged key</button>
    <p>API calls can incur Google account charges. This app limits generation to five requests per
    API key per app run, one at a time, with at most 1,024 output tokens per request and no retries.
    That is a request/output cap, not a dollar cap. Set account billing limits and alerts in Google
    AI Studio / Cloud; outside use of the same key is not counted here. The key stays in memory for
    up to one hour or until disconnect/app restart. Restrict it to the Gemini API before use.</p>
    </main></body></html>""")


@router.get("/ui/workflows", response_class=HTMLResponse)
def workflows_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Workflow review - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/workflows.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/provider-connections">Provider connections</a> |
    <a href="/ui/login?next=/ui/workflows">Local sign-in / sign-out</a></nav>
    <h1>Workflow review and owner report</h1>
    <p>Workflow state is separate from Task state. Agent review is advisory and never replaces
    owner approval. Cancellation is unsupported once a provider call has started. State is held
    in this app process only. Spend figures are owner-declared ceilings, not provider billing.</p>
    <p id="workflow-status" role="status">Loading workflows...</p>
    <div id="workflow-list"></div></main></body></html>""")


@router.get("/ui/structure", response_class=HTMLResponse)
def structure_map_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Corporation structure - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/structure.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/positions">Positions</a> |
    <a href="/ui/login?next=/ui/structure">Local sign-in / sign-out</a></nav>
    <h1>Corporation structure</h1>
    <p>Shows only recorded positions, reporting links and Agent/model assignments. Missing,
    unassigned, forbidden and stale records are labelled; nothing here indicates live activity.</p>
    <p id="structure-status" role="status">Loading structure...</p>
    <button id="structure-refresh" type="button">Refresh</button>
    <nav aria-label="Reporting structure"><ul id="structure-tree"></ul></nav>
    <section aria-live="polite"><h2>Details</h2><div id="structure-detail">Select a position.</div></section>
    </main></body></html>""")


@router.get("/ui/workflow-map", response_class=HTMLResponse)
def workflow_map_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Workflow map - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/workflow-map.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/workflows">Workflows</a> |
    <a href="/ui/structure">Corporation structure</a> |
    <a href="/ui/login?next=/ui/workflow-map">Local sign-in / sign-out</a></nav>
    <h1>Workflow map</h1>
    <p>Operational handoff and delegation links are listed separately from organizational reporting
    links. Agent responses, assignment source, recorded rationale, review, and owner verification are
    shown only when supported by workflow records. Missing rationale and uncertain outcomes stay explicit.</p>
    <p id="workflow-map-status" role="status">Loading workflow map...</p>
    <button id="workflow-map-refresh" type="button">Refresh</button>
    <section aria-label="Workflow work items"><div id="workflow-map-list"></div></section>
    <section aria-label="Organizational reporting links"><h2>Organizational reporting links</h2>
    <ul id="workflow-map-org"></ul></section>
    <section aria-live="polite"><h2>Details</h2><div id="workflow-map-detail">Select a work item.</div></section>
    </main></body></html>""")

@router.get("/ui/visualization", response_class=HTMLResponse)
def visualization_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Corporation visualization - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/visualization.mjs"></script></head><body>
    <main class="content viz-content"><nav><a href="/ui/chat">Coordinator chat</a> |
    <a href="/ui/providers">Provider &amp; model setup</a> |
    <a href="/ui/structure">Structure list</a> | <a href="/ui/workflow-map">Workflow list</a> |
    <a href="/ui/login?next=/ui/visualization">Local sign-in / sign-out</a></nav>
    <h1>Corporation visualization</h1>
    <p>Explore current, authorized Corporation, organization, Project, Task, workflow, Provider/model,
    Agent capability, software resource, and retained-knowledge records. Only source-backed relationships
    are drawn. Provider registration is not availability; capability declarations do not grant authority;
    request slots do not establish hardware fit; memory content is not shown. The map cannot start or
    approve work.</p>
    <p id="viz-status" role="status" tabindex="0" aria-label="Map loading and source status">Loading...</p>
    <div role="group" aria-label="View controls">
    <button id="viz-mode-3d" type="button" aria-pressed="true">3D globe</button>
    <button id="viz-mode-list" type="button" aria-pressed="false">List view</button>
    <button id="viz-refresh" type="button">Refresh</button>
    <button id="viz-rotate-left" type="button">Rotate left</button>
    <button id="viz-rotate-right" type="button">Rotate right</button>
    <button id="viz-zoom-in" type="button">Zoom in</button>
    <button id="viz-zoom-out" type="button">Zoom out</button>
    <button id="viz-pan-left" type="button">Pan left</button>
    <button id="viz-pan-right" type="button">Pan right</button>
    <button id="viz-pan-up" type="button">Pan up</button>
    <button id="viz-pan-down" type="button">Pan down</button>
    <button id="viz-frame-measure" type="button">Measure 300 frames</button>
    <label><input id="viz-effects" type="checkbox" checked> Visual effects</label>
    <label><input id="viz-reduce-motion" type="checkbox"> Reduce motion</label></div>
    <fieldset class="viz-layers"><legend>Visible map layers</legend>
    <label><input id="viz-layer-organization" type="checkbox" checked> Corporation, positions, Employees, Agents</label>
    <label><input id="viz-layer-projects" type="checkbox" checked> Projects</label>
    <label><input id="viz-layer-tasks" type="checkbox" checked> Tasks</label>
    <label><input id="viz-layer-workflows" type="checkbox" checked> Workflows and execution evidence</label>
    <label><input id="viz-layer-providers" type="checkbox" checked> Providers and model assignments</label>
    <label><input id="viz-layer-capabilities" type="checkbox" checked> Agent capability declarations</label>
    <label><input id="viz-layer-resources" type="checkbox" checked> Software slot budgets</label>
    <label><input id="viz-layer-knowledge" type="checkbox" checked> Retained knowledge metadata</label></fieldset>
    <label for="viz-search">Find records by name, ID, type, or state</label>
    <input id="viz-search" type="search" maxlength="120" autocomplete="off">
    <p>The globe is a visual layout, not a geographic map or measured organizational position. Recorded links are drawn between their source-backed records only. Drag to orbit; hold Shift and drag to pan; use the labeled controls for keyboard access. Filter layers or search names and IDs to inspect records beyond the 60-node render cap. Current APIs expose no department records. Separate source snapshots may have different timestamps and are not atomic.</p>
    <canvas id="viz-canvas" class="viz-canvas" tabindex="0" role="img" aria-label="3D organizational globe, not geographic"></canvas>
    <section id="viz-list" aria-label="Accessible list view of the same records and relationships" hidden></section>
    <p id="viz-cost" role="status"></p>
    <p id="viz-frame-metric" role="status">Frame pacing: not measured on this device.</p>
    <section aria-live="polite"><h2>Details</h2><div id="viz-detail">Select a node.</div></section>
    <section id="viz-evidence" aria-labelledby="viz-evidence-title">
    <h2 id="viz-evidence-title">Authorized map evidence</h2>
    <p>Model associations use recorded Agent IDs. Knowledge provenance is shown as source metadata, not inferred graph links. Slot counts are software limits, not hardware capacity.</p>
    <div id="viz-evidence-data"></div></section>
    </main></body></html>""")

@router.get("/ui/provider-connections", response_class=HTMLResponse)
def provider_connections_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Provider connections - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/provider-connections.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/providers">Provider management</a> |
    <a href="/ui/local-models">Local model setup</a> |
    <a href="/ui/online-provider">Gemini setup</a> |
    <a href="/ui/login?next=/ui/provider-connections">Local sign-in / sign-out</a></nav>
    <h1>Provider connections</h1>
    <p>Connections and credentials are held only in this app process. Ollama endpoints must be
    loopback HTTP. Gemini model discovery is an explicit online request; each Gemini turn still
    requires its own consent and uses the existing five-request/output-token caps. Those caps are
    not a dollar ceiling. Set account billing limits outside this app. Hardware feasibility remains
    UNKNOWN; request slots limit software concurrency only.</p>
    <div class="ui-form"><label for="connection-type">Provider type</label>
    <select id="connection-type"><option value="ollama">Local Ollama</option><option value="gemini">Google Gemini</option></select>
    <label for="connection-id">Connection ID</label><input id="connection-id" maxlength="48" autocomplete="off">
    <label for="connection-name">Display name</label><input id="connection-name" maxlength="256" autocomplete="off">
    <div id="connection-url-field"><label for="connection-url">Loopback Ollama URL</label>
    <input id="connection-url" value="http://127.0.0.1:11434" maxlength="2048" autocomplete="off"></div>
    <div id="connection-key-field" hidden><label for="connection-key">Restricted Gemini API key</label>
    <input id="connection-key" type="password" maxlength="4096" autocomplete="off"></div>
    <label for="connection-slots">In-flight request slots</label>
    <input id="connection-slots" type="number" min="1" max="16" value="1">
    <button id="connection-add" type="button">Add and verify connection</button></div>
    <p id="connection-state" role="status" aria-live="polite"></p>
    <h2>Configured connections</h2><ul id="connection-list"></ul>
    <div class="ui-form"><label for="assignment-provider">Connection</label><select id="assignment-provider"></select>
    <button id="connection-refresh" type="button">Refresh catalog and status</button>
    <button id="connection-remove" type="button">Remove connection</button>
    <label for="assignment-agent">Agent</label><select id="assignment-agent"></select>
    <label for="assignment-model">Supported model</label><select id="assignment-model"></select>
    <button id="assignment-save" type="button">Preview and assign</button></div>
    <h2>Local model runtime</h2>
    <p>Ollama reports loaded models and memory only after they are loaded. The check latency below
    is not inference latency. Hardware capacity and whether an unloaded model fits remain UNKNOWN.
    Loading sends no prompt; explicit load/unload is bounded by this connection's configured request
    slots and blocked while that model has active work. Loaded memory is counted once per provider/model,
    even when Agents share it.</p>
    <label for="model-keep-alive">Load keep-alive seconds (1-86400)</label>
    <input id="model-keep-alive" type="number" min="1" max="86400" value="300">
    <p><button id="model-runtime-refresh" type="button">Refresh loaded-model status</button>
    <button id="model-load" type="button" disabled>Load selected model</button>
    <button id="model-unload" type="button" disabled>Unload selected model</button></p>
    <p id="model-runtime-state" role="status" aria-live="polite"></p>
    <pre id="model-runtime-evidence" aria-live="polite"></pre>
    </main></body></html>""")

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def corporation_dashboard() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION executive dashboard">
          <title>Dashboard — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/dashboard.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="#dashboard" aria-current="page">Dashboard</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
                <li><a href="/ui/memory">Memory</a></li>
                <li><a href="/ui/documentation">Documentation portal</a></li>
                <li><a href="/ui/updates">Updates / changelog</a></li>
              </ul>
            </nav>
            <main id="dashboard" class="content">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Executive overview</p>
                  <h1>Corporation dashboard</h1>
                </div>
                <button id="dashboard-retry" type="button">Retry data loading</button>
              </div>
              <p class="auth-boundary">
                Dashboard data comes from protected Corporation APIs. Protected data requires an authenticated session with the relevant read
                permissions. In explicitly configured local mode, use Local sign-in.
                The default API still rejects access without an authentication backend.
              </p>
              <div class="dashboard-grid">
                <section class="dashboard-card" id="status-panel" aria-labelledby="status-title">
                  <h2 id="status-title">Corporation overview</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading status…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="workforce-panel" aria-labelledby="workforce-title">
                  <h2 id="workforce-title">Workforce overview</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading workforce…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="providers-panel" aria-labelledby="providers-title">
                  <h2 id="providers-title">Providers &amp; model assignments</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading provider information…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="tasks-panel" aria-labelledby="tasks-title">
                  <h2 id="tasks-title">Tasks overview</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading tasks…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="projects-panel" aria-labelledby="projects-title">
                  <h2 id="projects-title">Projects overview</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading projects…</p>
                  <div class="section-data" hidden></div>
                </section>
                <section class="dashboard-card" id="activity-panel" aria-labelledby="activity-title">
                  <h2 id="activity-title">Recent activity</h2>
                  <p class="section-state" role="status" aria-live="polite">Loading activity…</p>
                  <div class="section-data" hidden></div>
                </section>
              </div>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/documentation", response_class=HTMLResponse, include_in_schema=False)
def documentation_portal_page() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="Internal Corporation Documentation Portal">
          <title>Documentation Portal — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/documentation.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
                <li><a href="/ui/memory">Memory</a></li>
                <li><a href="/ui/documentation" aria-current="page">Documentation portal</a></li>
                <li><a href="/ui/updates">Updates / changelog</a></li>
              </ul>
            </nav>
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
                  <p id="documentation-list-state" class="section-state" role="status" aria-live="polite">Loading documents…</p>
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
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION Activity and logs">
          <title>Activity &amp; Logs — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/activity.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity" aria-current="page">Activity &amp; logs</a></li>
                <li><a href="/ui/documentation">Documentation portal</a></li>
                <li><a href="/ui/updates">Updates / changelog</a></li>
              </ul>
            </nav>
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
                <p id="activity-list-state" class="section-state" role="status" aria-live="polite">Loading activity…</p>
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
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="Curated Corporation software updates">
          <title>Updates / Changelog — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/updates.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
                <li><a href="/ui/memory">Memory</a></li>
                <li><a href="/ui/documentation">Documentation portal</a></li>
                <li><a href="/ui/updates" aria-current="page">Updates / changelog</a></li>
              </ul>
            </nav>
            <main class="content updates-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Curated project record</p>
                  <h1>Updates / Changelog</h1>
                </div>
                <button id="updates-refresh" type="button">Refresh</button>
              </div>
              <p class="auth-boundary">
                This read-only page shows manually maintained, verified
                development updates and release records. It is separate from
                the public project updates page in <code>docs/</code>. Entries
                are not inferred from roadmap tasks or Git history. In default API mode, browser
                sign-in is not configured; an authenticated session with
                <code>updates:read</code> permission is required.
              </p>
              <section class="management-card" aria-labelledby="updates-list-title">
                <h2 id="updates-list-title">Curated updates</h2>
                <p id="updates-list-state" class="section-state" role="status" aria-live="polite">Loading updates…</p>
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
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION employee management">
          <title>Employee Management — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/employees.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="/ui/employee-chat">Individual Employee chat</a></li>
                <li><a href="/ui/employees" aria-current="page">Employee management</a></li>
                <li><a href="/ui/positions">Organizational positions</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
                <li><a href="/ui/memory">Memory</a></li>
                <li><a href="/ui/documentation">Documentation portal</a></li>
                <li><a href="/ui/updates">Updates / changelog</a></li>
              </ul>
            </nav>
            <main class="content employee-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Organization</p>
                  <h1>Employee Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Employee data and actions use protected APIs. In default API mode, browser sign-in is
                not configured; an authenticated session with employee read or
                manage permission is required.
              </p>
              <div class="employee-layout">
                <section class="employee-card" aria-labelledby="employee-list-title">
                  <div class="section-heading">
                    <h2 id="employee-list-title">Employees</h2>
                    <button id="employee-refresh" type="button">Refresh</button>
                  </div>
                  <p id="employee-list-state" class="section-state" role="status" aria-live="polite">Loading employees…</p>
                  <ul id="employee-list" class="employee-list" aria-label="Employee records"></ul>
                </section>
                <section class="employee-card" aria-labelledby="employee-detail-title">
                  <h2 id="employee-detail-title">Employee details</h2>
                  <p id="employee-detail-state" class="section-state" role="status" aria-live="polite">Select an employee to view details.</p>
                  <div id="employee-detail" class="employee-detail" hidden></div>
                </section>
                <section class="employee-card create-card" aria-labelledby="employee-create-title">
                  <h2 id="employee-create-title">Create employee</h2>
                  <p class="muted">The current API requires an Employee ID, name, and role. Responsibilities are optional; Agent association is not supported here.</p>
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


@router.get("/ui/positions", response_class=HTMLResponse, include_in_schema=False)
def position_management_page() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION position management">
          <title>Organizational Positions — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/positions.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/positions" aria-current="page">Organizational positions</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
              </ul>
            </nav>
            <main class="content">
              <div class="dashboard-heading">
                <div><p class="eyebrow">Organization</p><h1>Organizational positions</h1></div>
                <a class="back-link" href="/ui/employees">Employee management</a>
              </div>
              <p>Positions are separate from Employee identity and technical Agent/model assignment.
              Position titles do not grant permissions. Records and revision history are in memory for
              this app run only.</p>
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
                <form id="position-form">
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
              Resolve those references explicitly before removal. Data is lost when this app process
              restarts; no durable organizational store is configured.</p>
            </main>
          </div>
        </body>
        </html>
        """
    )


@router.get("/ui/providers", response_class=HTMLResponse, include_in_schema=False)
def provider_model_management_page() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION Provider and Model management">
          <title>Provider &amp; Model Management — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/providers.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers" aria-current="page">Provider &amp; Model management</a></li>
                <li><a href="/ui/provider-connections">Local / online provider connections</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
                <li><a href="/ui/memory">Memory</a></li>
                <li><a href="/ui/documentation">Documentation portal</a></li>
                <li><a href="/ui/updates">Updates / changelog</a></li>
              </ul>
            </nav>
            <main class="content provider-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Configuration</p>
                  <h1>Provider &amp; Model Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Provider and model data/actions use protected APIs. In default API mode, browser
                sign-in is not configured; authenticated sessions require
                provider/model read or manage permissions.
              </p>
              <div class="management-grid">
                <section class="management-card" aria-labelledby="provider-section-title">
                  <div class="section-heading">
                    <h2 id="provider-section-title">Configured Providers</h2>
                    <button id="provider-refresh" type="button">Refresh</button>
                  </div>
                  <p id="provider-list-state" class="section-state" role="status" aria-live="polite">Loading providers…</p>
                  <ul id="provider-list" class="record-list" aria-label="Configured providers"></ul>
                  <section class="management-detail" aria-labelledby="provider-detail-title">
                    <h3 id="provider-detail-title">Provider details</h3>
                    <p id="provider-detail-state" class="section-state" role="status" aria-live="polite">Select a provider to view details.</p>
                    <div id="provider-detail" hidden></div>
                  </section>
                  <section class="management-form" aria-labelledby="provider-create-title">
                    <h3 id="provider-create-title">Create provider</h3>
                    <p class="muted">Only the current API's Provider ID and name are accepted. Credentials and provider configuration are not supported here.</p>
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
                  <p id="model-list-state" class="section-state" role="status" aria-live="polite">Loading model assignments…</p>
                  <ul id="model-list" class="record-list" aria-label="Agent model assignments"></ul>
                  <section class="management-detail" aria-labelledby="model-detail-title">
                    <h3 id="model-detail-title">Assignment details</h3>
                    <p id="model-detail-state" class="section-state" role="status" aria-live="polite">Select an assignment to inspect or replace it.</p>
                    <div id="model-detail" hidden></div>
                  </section>
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
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION Task management">
          <title>Task Management — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/tasks.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks" aria-current="page">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
                <li><a href="/ui/memory">Memory</a></li>
                <li><a href="/ui/documentation">Documentation portal</a></li>
                <li><a href="/ui/updates">Updates / changelog</a></li>
              </ul>
            </nav>
            <main class="content task-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Work management</p>
                  <h1>Task Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Task records and actions use protected APIs. Browser sign-in
                is not configured; an authenticated session with task read or
                create permission is required.
              </p>
              <div class="task-layout">
                <section class="management-card" aria-labelledby="task-list-title">
                  <div class="section-heading">
                    <h2 id="task-list-title">Tasks</h2>
                    <button id="task-refresh" type="button">Refresh</button>
                  </div>
                  <p id="task-list-state" class="section-state" role="status" aria-live="polite">Loading tasks…</p>
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
                    <h3 id="task-dispatch-title">Controlled worker dispatch</h3>
                    <p class="muted">Each dispatch requires a separate owner confirmation and configured Task 68 slot budgets. This path uses loopback Ollama only, does not execute Tools, and never retries. Completed execution is not proof that expected outcomes were verified.</p>
                    <p id="task-dispatch-state" class="section-state" role="status" aria-live="polite">Checking dispatch permission…</p>
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
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION Project management">
          <title>Project Management — ERSELMETZ AI CORPORATION</title>
          <link rel="stylesheet" href="/ui/static/style.css">
          <script type="module" src="/ui/static/projects.mjs"></script>
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Corporation Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Corporation navigation">
              <h2>Navigation</h2>
              <ul>
                <li><a href="/ui">Dashboard</a></li>
                <li><a href="/ui/login">Local sign-in / sign-out</a></li>
                <li><a href="/ui/chat">Coordinator chat</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects" aria-current="page">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
                <li><a href="/ui/memory">Memory</a></li>
                <li><a href="/ui/documentation">Documentation portal</a></li>
                <li><a href="/ui/updates">Updates / changelog</a></li>
              </ul>
            </nav>
            <main class="content project-page">
              <div class="dashboard-heading">
                <div>
                  <p class="eyebrow">Work management</p>
                  <h1>Project Management</h1>
                </div>
                <a class="back-link" href="/ui">Back to dashboard</a>
              </div>
              <p class="auth-boundary">
                Project records and creation use protected APIs. In default API mode, browser
                sign-in is not configured; an authenticated session with
                project read or create permission is required.
              </p>
              <div class="project-layout">
                <section class="management-card" aria-labelledby="project-list-title">
                  <div class="section-heading">
                    <h2 id="project-list-title">Projects</h2>
                    <button id="project-refresh" type="button">Refresh</button>
                  </div>
                  <p id="project-list-state" class="section-state" role="status" aria-live="polite">Loading projects…</p>
                  <ul id="project-list" class="record-list" aria-label="Project records"></ul>
                  <section class="management-detail" aria-labelledby="project-detail-title">
                    <h3 id="project-detail-title">Project details</h3>
                    <p id="project-detail-state" class="section-state" role="status" aria-live="polite">Select a project to view its details.</p>
                    <div id="project-detail" hidden></div>
                  </section>
                </section>
                <section class="management-card" aria-labelledby="project-create-title">
                  <h2 id="project-create-title">Create project</h2>
                  <p class="muted">The API generates the Project ID and status. Creation does not add Tasks or other entities.</p>
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
def memory_page() -> HTMLResponse:
    return HTMLResponse("""<!doctype html><html lang="en"><head>
      <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Memory — ERSELMETZ AI CORPORATION</title><link rel="stylesheet" href="/ui/static/style.css">
      <script type="module" src="/ui/static/memory.mjs"></script></head><body>
      <main class="content"><a href="/ui">Back to dashboard</a><h1>Memory management</h1>
      <p>In default API mode, browser sign-in is not configured. Reads require memory:read; changes require memory:manage and owner authority. Owner identity comes from the authenticated session.</p>
      <section class="management-card"><h2>Inspect stored memory</h2>
      <label for="memory-scope">Scope</label><select id="memory-scope"><option value="conversation">Conversation</option><option value="project">Project</option><option value="corporation">Corporation publication</option></select>
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
      </section></main></body></html>""")


@router.get("/ui/chat", response_class=HTMLResponse)
def coordinator_chat_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Coordinator chat - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/chat.mjs"></script></head><body>
    <main class="content chat-content"><nav aria-label="Chat navigation">
    <a href="/ui">Dashboard</a> | <a href="/ui/login">Local sign-in / sign-out</a> | <a href="/ui/employee-chat">Individual Employee chat</a> | <a href="/ui/local-models">Agent model setup</a> | <a href="/ui/online-provider">Gemini online setup</a></nav>
    <h1>Corporation coordinator chat</h1>
    <p>Talk to a selected registered Agent. Replies are conversation text; they do not create Tasks,
    execute tools, or change the corporation. This is the first step toward the planned CEO workspace.</p>
    <label for="chat-agent">Coordinator and configured model</label><select id="chat-agent"></select>
    <button id="chat-start" type="button">New conversation</button>
    <label for="chat-conversation">Your conversations for this app run</label><select id="chat-conversation"></select>
    <button id="chat-refresh" type="button">Refresh list</button><button id="chat-close" type="button">Close conversation</button>
    <p id="chat-identity"></p><p id="chat-state" role="status" aria-live="polite"></p>
    <section id="chat-history" aria-label="Conversation messages" aria-live="polite"></section>
    <form id="chat-form"><label for="chat-input">Message (up to 8192 UTF-8 bytes)</label>
    <textarea id="chat-input" rows="4" maxlength="8192" required></textarea>
    <button id="chat-send" type="submit">Send</button></form>
    <section class="panel" aria-labelledby="chat-task-proposal-heading">
    <h2 id="chat-task-proposal-heading">Review a coordinator proposal</h2>
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
    </section>
    <p>History is in memory and is lost when the app restarts. Up to 100 conversations and 200 messages
    per conversation are retained for this run. The current provider contract does not stream or
    cancel requests. For the default local Agent, Ollama and llama3.2:3b must already be available;
    use Local model setup to refresh installed models and explicitly select one. Do not paste API keys here; configure Gemini in its separate online setup page.</p>
    <p id="cloud-consent-panel" hidden><label><input id="cloud-consent" type="checkbox">
    I consent to send this message, recent conversation history, and configured chat context to Google Gemini for this reply.</label></p>
    </main></body></html>""")


@router.get("/ui/employee-chat", response_class=HTMLResponse)
def employee_chat_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Individual Employee chat - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/employee-chat.mjs"></script></head><body>
    <main class="content chat-content"><nav aria-label="Chat navigation">
    <a href="/ui">Dashboard</a> | <a href="/ui/login">Local sign-in / sign-out</a> |
    <a href="/ui/employees">Employees</a> | <a href="/ui/chat">Coordinator chat</a></nav>
    <h1>Individual Employee chat</h1>
    <p>Each conversation captures one registered Employee and the Agent assigned when it starts.
    Messages and history are isolated per conversation and owner. Reassignments do not move an
    existing conversation; start a new one to use a changed Agent connection. Chats do not create
    Tasks, execute tools, or include Employee profiles or Task content automatically.</p>
    <label for="individual-employee">Employee with an assigned Agent</label>
    <select id="individual-employee"></select>
    <button id="individual-chat-new" type="button">Start individual conversation</button>
    <label for="individual-conversation">Your individual conversations for this app run</label>
    <select id="individual-conversation"></select>
    <button id="individual-chat-refresh" type="button">Refresh</button>
    <button id="individual-chat-close" type="button" disabled>Close conversation</button>
    <p id="individual-chat-identity"></p>
    <p id="individual-chat-state" role="status" aria-live="polite"></p>
    <section id="individual-chat-history" aria-label="Individual conversation messages" aria-live="polite"></section>
    <form id="individual-chat-form">
      <label for="individual-chat-input">Message (up to 8192 UTF-8 bytes)</label>
      <textarea id="individual-chat-input" rows="4" maxlength="8192" required></textarea>
      <button id="individual-chat-send" type="submit" disabled>Send</button>
    </form>
    <p id="individual-cloud-consent-panel" hidden><label><input id="individual-cloud-consent" type="checkbox">
    I consent to send this message and recent history from this individual conversation to Google Gemini for this reply.</label></p>
    <p>History is held in memory for this app run only. Gemini requires per-turn consent and remains
    subject to its connection expiry, request limit, and owner-managed billing controls.</p>
    </main></body></html>""")


@router.get("/ui/local-models", response_class=HTMLResponse)
def local_model_setup_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Local model setup - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/local-models.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/chat">Coordinator chat</a> | <a href="/ui/employee-chat">Individual Employee chat</a> | <a href="/ui/assignment-policy">Assignment recommendations</a> | <a href="/ui/login">Local sign-in / sign-out</a></nav>
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
    <main class="content"><nav><a href="/ui">Dashboard</a> | <a href="/ui/local-models">Manual Agent model setup</a> | <a href="/ui/online-provider">Gemini setup</a> | <a href="/ui/login">Local sign-in / sign-out</a></nav>
    <h1>Capability-based assignment recommendations</h1>
    <p>Available only through explicit local-owner access. Recommendations are disabled until you save an owner-approved policy. They never change an Agent assignment, connect a provider, send data, or grant online consent.</p>
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
    <button id="assignment-policy-disable" type="button">Disable recommendations</button>
    <button id="assignment-policy-preview" type="button">Refresh preview</button></p>
    <p id="assignment-policy-state" role="status" aria-live="polite"></p>
    <pre id="assignment-policy-results" aria-live="polite"></pre>
    <p>Manual assignments always remain authoritative. Use Manual Agent model setup to override a recommendation with its impact preview and confirmation. Disabling clears the saved policy data and is the complete undo because this policy never applies assignments; any separately confirmed manual change can be reversed only through the existing manual setup flow.</p>
    </main></body></html>""")


@router.get("/ui/online-provider", response_class=HTMLResponse)
def local_online_provider_page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Gemini online setup - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
    <script type="module" src="/ui/static/online-provider.mjs"></script></head><body>
    <main class="content"><nav><a href="/ui/chat">Coordinator chat</a> | <a href="/ui/assignment-policy">Assignment recommendations</a> | <a href="/ui/login">Local sign-in / sign-out</a></nav>
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
    <a href="/ui/login">Local sign-in / sign-out</a></nav>
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
    <a href="/ui/login">Local sign-in / sign-out</a></nav>
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
    <a href="/ui/login">Local sign-in / sign-out</a></nav>
    <h1>Workflow map</h1>
    <p>Operational handoff and delegation links are listed separately from organizational reporting
    links. Only recorded state and evidence are shown; there is no progress estimate or live activity.</p>
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
    <a href="/ui/login">Local sign-in / sign-out</a></nav>
    <h1>Corporation visualization</h1>
    <p>A 3D view of recorded positions, reporting links and workflow items. Only recorded state is drawn;
    a node pulses once only when a refresh finds its recorded state changed. Nothing here can start or
    approve work.</p>
    <p id="viz-status" role="status">Loading...</p>
    <div role="group" aria-label="View controls">
    <button id="viz-mode-3d" type="button" aria-pressed="true">3D view</button>
    <button id="viz-mode-list" type="button" aria-pressed="false">List view</button>
    <button id="viz-refresh" type="button">Refresh</button>
    <button id="viz-rotate-left" type="button">Rotate left</button>
    <button id="viz-rotate-right" type="button">Rotate right</button>
    <label><input id="viz-effects" type="checkbox" checked> Visual effects</label>
    <label><input id="viz-reduce-motion" type="checkbox"> Reduce motion</label></div>
    <canvas id="viz-canvas" class="viz-canvas" tabindex="0" role="img" aria-label="3D map"></canvas>
    <section id="viz-list" aria-label="List view" hidden></section>
    <p id="viz-cost" role="status"></p>
    <section aria-live="polite"><h2>Details</h2><div id="viz-detail">Select a node.</div></section>
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
    <a href="/ui/login">Local sign-in / sign-out</a></nav>
    <h1>Provider connections</h1>
    <p>Connections and credentials are held only in this app process. Ollama endpoints must be
    loopback HTTP. Gemini model discovery is an explicit online request; each Gemini turn still
    requires its own consent and uses the existing five-request/output-token caps. Those caps are
    not a dollar ceiling. Set account billing limits outside this app. Hardware feasibility remains
    UNKNOWN; request slots limit software concurrency only.</p>
    <label for="connection-type">Provider type</label>
    <select id="connection-type"><option value="ollama">Local Ollama</option><option value="gemini">Google Gemini</option></select>
    <label for="connection-id">Connection ID</label><input id="connection-id" maxlength="48" autocomplete="off">
    <label for="connection-name">Display name</label><input id="connection-name" maxlength="256" autocomplete="off">
    <div id="connection-url-field"><label for="connection-url">Loopback Ollama URL</label>
    <input id="connection-url" value="http://127.0.0.1:11434" maxlength="2048" autocomplete="off"></div>
    <div id="connection-key-field" hidden><label for="connection-key">Restricted Gemini API key</label>
    <input id="connection-key" type="password" maxlength="4096" autocomplete="off"></div>
    <label for="connection-slots">In-flight request slots</label>
    <input id="connection-slots" type="number" min="1" max="16" value="1">
    <button id="connection-add" type="button">Add and verify connection</button>
    <p id="connection-state" role="status" aria-live="polite"></p>
    <h2>Configured connections</h2><ul id="connection-list"></ul>
    <label for="assignment-provider">Connection</label><select id="assignment-provider"></select>
    <button id="connection-refresh" type="button">Refresh catalog and status</button>
    <button id="connection-remove" type="button">Remove connection</button>
    <label for="assignment-agent">Agent</label><select id="assignment-agent"></select>
    <label for="assignment-model">Supported model</label><select id="assignment-model"></select>
    <button id="assignment-save" type="button">Preview and assign</button>
    <h2>Local model runtime</h2>
    <p>Ollama reports loaded models and memory only after they are loaded. The check latency below
    is not inference latency. Hardware capacity and whether an unloaded model fits remain UNKNOWN.
    Loading sends no prompt; explicit load/unload is bounded by this connection's configured request
    slots and blocked while that model has active work. Loaded memory is counted once per provider/model,
    even when Agents share it.</p>
    <label for="model-keep-alive">Load keep-alive seconds (1–86400)</label>
    <input id="model-keep-alive" type="number" min="1" max="86400" value="300">
    <p><button id="model-runtime-refresh" type="button">Refresh loaded-model status</button>
    <button id="model-load" type="button" disabled>Load selected model</button>
    <button id="model-unload" type="button" disabled>Unload selected model</button></p>
    <p id="model-runtime-state" role="status" aria-live="polite"></p>
    <pre id="model-runtime-evidence" aria-live="polite"></pre>
    </main></body></html>""")

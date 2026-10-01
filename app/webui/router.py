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
                <li><a href="#dashboard" aria-current="page">Dashboard</a></li>
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
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
                Dashboard data comes from protected Corporation APIs. No browser
                sign-in flow is configured yet; protected data requires an
                authenticated session with the relevant read permissions.
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
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
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
                public documentation website in <code>docs/</code>. Browser
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
                Activity data comes from the protected API. Browser sign-in is
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
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
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
                are not inferred from roadmap tasks or Git history. Browser
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
                <li><a href="/ui/employees" aria-current="page">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
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
                Employee data and actions use protected APIs. Browser sign-in is
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
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers" aria-current="page">Provider &amp; Model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
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
                Provider and model data/actions use protected APIs. Browser
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
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks" aria-current="page">Task management</a></li>
                <li><a href="/ui/projects">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
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
                <li><a href="/ui/employees">Employee management</a></li>
                <li><a href="/ui/providers">Provider &amp; model management</a></li>
                <li><a href="/ui/tasks">Task management</a></li>
                <li><a href="/ui/projects" aria-current="page">Project management</a></li>
                <li><a href="/ui/activity">Activity &amp; logs</a></li>
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
                Project records and creation use protected APIs. Browser
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

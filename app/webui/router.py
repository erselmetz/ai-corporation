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
                <li><span aria-disabled="true">Employee management — planned</span></li>
                <li><span aria-disabled="true">Provider &amp; model — planned</span></li>
                <li><span aria-disabled="true">Task management — planned</span></li>
                <li><span aria-disabled="true">Projects — planned</span></li>
                <li><span aria-disabled="true">Activity — planned</span></li>
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

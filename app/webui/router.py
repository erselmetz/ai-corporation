from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def web_ui_shell() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="description" content="ERSELMETZ AI CORPORATION Web UI foundation">
          <title>ERSELMETZ AI CORPORATION — Web UI</title>
          <link rel="stylesheet" href="/ui/static/style.css">
        </head>
        <body>
          <header class="site-header">
            <a class="brand" href="/ui">ERSELMETZ AI CORPORATION</a>
            <span class="product-label">Web UI</span>
          </header>
          <div class="layout">
            <nav class="navigation" aria-label="Future Corporation sections">
              <h2>Navigation</h2>
              <ul>
                <li><a href="#overview" aria-current="page">Overview</a></li>
                <li><span aria-disabled="true">Dashboard — planned</span></li>
                <li><span aria-disabled="true">Management — planned</span></li>
                <li><span aria-disabled="true">Activity — planned</span></li>
              </ul>
            </nav>
            <main id="overview" class="content">
              <p class="eyebrow">Foundation</p>
              <h1>Web UI foundation is operational</h1>
              <p>This is the initial Corporation Web UI shell. It does not display or change Corporation data.</p>
              <p>Public shell and navigation are separate from protected Corporation information and actions. Future pages must use the existing authentication, authorization, and Application Service boundary.</p>
            </main>
          </div>
        </body>
        </html>
        """
    )

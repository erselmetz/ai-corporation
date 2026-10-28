# Task 229 pre-change audit

Source: 8ef6857646abab0c5eab452f42422a48d3d64426. Clean main, one local Task 228 commit ahead of origin/main. No implementation changed before this report.

## Browser entry points

| Path | Behavior | Disposition |
|---|---|---|
| app/qt_desktop/shell.py:open_page | Advanced/Settings posts a launch ticket then calls injected webbrowser.open | Replace with keyed native windows |
| app/desktop_launcher.py:DesktopLauncher.open_ui | Legacy Tk Start/Restart/Open local UI opens /ui/login | Disable legacy app-page opening; native entry is authoritative |
| app/application/services/native_tools.py | Owner-approved open_url tool opens requested http/https sites | Keep intentional exact-action tool |
| tools/packaged_advanced_check.py, tools/qt_shell_check.py | QA drives browser/launch-ticket contract | Retire/port after native acceptance |
| app/webui/static/local-login.mjs, quick-start.mjs | Browser navigation within HTML app | Remove in Phase C |

No production os.startfile, QDesktopServices.openUrl, pywebview or embedded Qt web engine calls found. Build explicitly excludes QtWebEngine. Chromium automation and web-reading integrations are tool capabilities, not app navigation; retain their existing consent boundaries. Public docs remain static and separate.

## Listener and authentication

Qt main constructs NativeSession -> LocalApplicationController.start -> pre-bound AF_INET socket on 127.0.0.1:0 -> in-process Uvicorn server thread. The listening PID is the Python/packaged app itself, not a Node process. NativeSession uses httpx over that listener with Origin and an ephemeral HttpOnly session token/cookie; protected writes additionally require X-Local-CSRF. API dependencies enforce permissions, ownership, grants, approvals, spend/resource limits and Stop.

create_app mounts /ui/static and includes app.webui.router; create_local_app adds login, first-run HTML and shared-navigation middleware. POST /api/local/advanced-launch requires chat:read and CSRF, mints 30-second random ticket bounded to 16 pending tickets and source session. GET /local/advanced-launch pops it, checks loopback/origin/session/expiry, creates or reuses owner cookie, redirects303 with no-store/no-referrer. It is removed in Phase A. Native startup token is separate from this browser launch ticket. Phase C replaces native TCP transport with an in-process dispatcher retaining the same route/dependency/middleware policy chain; no listening socket.

## Complete HTML route inventory

“Used” below means reachable in source/navigation/tests; no owner usage telemetry exists. It does not claim real user usage. All routes are owner-facing app pages, with advanced purpose where specified.

| Route | Source | Purpose / reachability | Tier / migration |
|---|---|---|
| `/ui` | app/webui/router.py:64 | Dashboard duplicates shell; navigation reachable | 3 retire HTML surface; preserve guarded backend |
| `/ui/activity` | app/webui/router.py:244 | activity page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/agents` | app/webui/router.py:443 | agents page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/assignment-policy` | app/webui/router.py:1347 | assignment policy page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/automation` | app/webui/router.py:933 | Duplicate native exact desktop/tool controls; hide old HTML | 3 retire HTML surface; preserve guarded backend |
| `/ui/backup` | app/webui/router.py:1241 | backup page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/chat` | app/webui/router.py:988 | coordinator chat page; source/navigation reachable, observed usage unknown | Existing native shell/widget parity |
| `/ui/documentation` | app/webui/router.py:185 | documentation portal page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/employee-chat` | app/webui/router.py:1285 | Port owned Employee conversation controls in native viewer; do not silently remove service | 3 retire HTML surface; preserve guarded backend |
| `/ui/employees` | app/webui/router.py:372 | employee management page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/inventory` | app/webui/router.py:1179 | inventory page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/knowledge` | app/webui/router.py:872 | owner knowledge page; source/navigation reachable, observed usage unknown | Existing native shell/widget parity |
| `/ui/local-models` | app/webui/router.py:1325 | local model setup page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/login` | app/local.py:377 | login page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/memory` | app/webui/router.py:833 | Alias to Brain advanced scopes; replace with native Brain settings | 3 retire HTML surface; preserve guarded backend |
| `/ui/online-provider` | app/webui/router.py:1392 | local online provider page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/positions` | app/webui/router.py:518 | position management page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/preferences` | app/webui/router.py:1218 | owner preferences page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/projects` | app/webui/router.py:766 | project management page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/provider-connections` | app/webui/router.py:1534 | provider connections page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/providers` | app/webui/router.py:584 | provider model management page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/readiness` | app/webui/router.py:1269 | readiness page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/sage-core` | app/webui/router.py:489 | Technical core status; fold into Activity native detail | 3 retire HTML surface; preserve guarded backend |
| `/ui/settings/capabilities` | app/webui/router.py:964 | capability settings page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/structure` | app/webui/router.py:1440 | structure map page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/tasks` | app/webui/router.py:672 | task management page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/updates` | app/webui/router.py:314 | updates page; source/navigation reachable, observed usage unknown | 1 native management |
| `/ui/visualization` | app/webui/router.py:1479 | visualization page; source/navigation reachable, observed usage unknown | Existing native shell/widget parity |
| `/ui/workflow-map` | app/webui/router.py:1458 | workflow map page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |
| `/ui/workflows` | app/webui/router.py:1424 | workflows page; source/navigation reachable, observed usage unknown | 2 declarative native table/detail |

Approvals has no standalone /ui route: controls are embedded in capability/automation/chat pages. It still gets a native Tier1 window. Org/workflow maps use declarative lists/details initially; no fabricated graph data. Projects is an additional Tier2 page. Employee chat remains a separate native owner conversation workflow, not a read-only replacement.

## Plan and test accounting

A: disable external app-page launch and remove tickets; safe native migration notices until B. Explicit online-docs click only opens https://ai.erselmetz.com. No web engine dependency (size cost zero).

B: native Tier1 forms/actions plus reusable schema tables/details; permission-checked requests, no direct registries. Offline Markdown native rendering, link auto-opening disabled. Separate singleton windows.

C: remove HTML/static/browser-only implementation and obsolete QA after documenting each retained/ported/retired test. Existing public-docs browser tests remain relevant to public site; external browser-tool tests remain relevant. In-process dispatch uses the existing authenticated API policy handlers without TCP rather than bypassing checks. Optional integration API remains explicit command-line only, never auto-started by desktop.

Baseline previous checkpoint: full 2051 passed/3 skipped; final affected 381 passed (overlap), plus one final collected regression after full run. Counts will be freshly collected and mapped before removal. Real Ollama checks and netstat PID proof required; unavailable paths remain Unverified.

Legacy safety tag already exists; do not move it. Three local phase commits/tags task-229a/b/c. No push/deploy.

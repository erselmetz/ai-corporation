# Task 213 UI review evidence

Status: final visuals approved by the owner on 2026-10-23. Automated acceptance evidence is recorded below; the local checkpoint is task-213-ui-foundation-polish. Tasks 214-217 remain separate scope. No push or deployment is authorized.

## Current architecture and multi-window blockers

- The packaged Electron app opens the Python-served `/ui/chat` page. Next.js is a static export for Home and Settings; most operations pages are Python-served HTML with browser modules. Both use `app/webui/static/design-tokens.css`, copied into the Next build by `desktop-ui/scripts/sync-design-tokens.mjs`.
- Electron already takes a single-instance lock and starts one loopback Python sidecar. It holds one `applicationWindow` reference. A second app launch focuses that window, closing it quits the app, and media/IPC trust checks compare against that one window. Tasks 214-216 require a window registry and per-window authorization before multiple windows can safely exist.
- The Electron bootstrap installs one HttpOnly owner session cookie in the default session. A shared owner login is supported; per-window workspace identity, selection state, approval provenance, and restoration are not represented yet.
- Chat already reserves the shared `ResourceManager` through `CorporationApplicationService.owned_chat_agent_execution`. The existing optional wait is bounded (16 waiters / 30 seconds); it does not expose per-workspace queue positions or cancellation ownership. Task 216 must extend that existing path. The general SQLite connection does not enable WAL; the optional vector store does. Project-scoped Brain access exists, but Chat conversation creation currently selects an Agent without a project ID.

## Reproducible visual evidence

Run `npm.cmd run ui:build --prefix desktop`, then:

```powershell
.\.venv\Scripts\python.exe tools/task213_visual_matrix.py --output desktop/task213-review/recheck --baselines tests/visual_baselines/task213
```

The script uses an isolated SQLite profile and deterministic fake provider. The initial seven-screen matrix (Home, Chat, Agents, Projects, Memory, Tasks, Settings) captured 168 screenshots in dark/light at 480, 768, 1280, and 1920 CSS pixels with 100%, 125%, and 150% device-scale factors. It checks document overflow, WCAG-tagged axe runs at 480/1280 and 100%, mobile menu Enter/Escape handling, and long unbroken text on Chat/Agents/Settings. Twelve 100%-scale screenshots are checked against `tests/visual_baselines/task213` with a bounded pixel tolerance to ignore 1-2-channel renderer dithering. The broader audit adds Employees, Positions, Providers, Activity, Inventory, Backup, Capabilities & privacy, Documentation, Updates, and Readiness. Device-scale simulation does not prove actual Windows display scaling.

Local before/after files (ignored review artifacts, not a public release):

| Finding | Before | After |
| --- | --- | --- |
| Chat light heading and sidebar controls had unreadable contrast | `desktop/task213-review/before/chat-light-480-100.png` | `desktop/task213-review/review-normal/chat-light-480-100.png` |
| Agents light was still rendered in dark colors | `desktop/task213-review/before/agents-light-480-100.png` | `desktop/task213-review/review-normal/agents-light-480-100.png` |
| Settings light mixed dark cards and faded labels | `desktop/task213-review/before/settings-light-480-100.png` | `desktop/task213-review/review-normal/settings-light-480-100.png` |
| Home light had faded intro and unreadable readiness cards | `desktop/task213-review/expanded/home-light-480-100.png` | `desktop/task213-review/review-normal/home-light-480-100.png` |
| Memory labels and fields ran together at narrow width | `desktop/task213-review/expanded/memory-light-480-100.png` | `desktop/task213-review/review-normal/memory-light-480-100.png` |
| Capabilities light cards made status text unreadable | `desktop/task213-review/broad-pass/capabilities-light-480-100.png` | `desktop/task213-review/focused-capabilities/capabilities-light-480-100.png` |
| Employee form labels and fields sat in cramped columns at 480 px | `desktop/task213-review/broad-pass/employees-light-480-100.png` | `desktop/task213-review/focused-capabilities/employees-light-480-100.png` |

The fixes extend the canonical design tokens with light surfaces, apply shared surface/text/input colors across both UI stacks, give direct management-card fields a shared stacked layout, fix Chat's named conversation groups and light sidebar contrast, and let the compact Next navigation close with Escape. A saved appearance control in Settings now carries the existing Chat theme preference across Next and Python local pages; the route test checks Settings to Agents, Chat, and Home. The owner approved this visual direction for continued work; that was not a completion acceptance. Protected actions, provider routing, auth, and consent were not changed.

The Task and Project pages still displayed stale static claims that browser sign-in was unavailable even in local mode. Their copy now states the owner permission directly; the Task page also replaces internal “Task 68 slot budgets” wording with the actual local-run behavior. The underlying permission, confirmation, capacity, Ollama-only, no-tools, and no-retry rules are unchanged. The broader page audit also reviewed the remaining legacy copy without changing permissions.

The first broader run exposed a serious axe color-contrast failure on the light Capabilities & privacy page: its status cards kept a dark-only background while text inherited the light palette. The shared card background now uses the raised-surface token. A focused 16-screenshot rerun passed axe at 480 and 1280 CSS pixels. Employee form fields now stack below their labels on narrow windows; documentation, update, and success/error text use shared light/dark tokens. The latest 35-screen normal-state rerun passes the expanded checks.

## Automated validation and limits

- Latest full Python suite in an isolated LOCALAPPDATA profile: **1,422 passed, 5 skipped, 0 failed**, two dependency deprecation warnings. Three existing local Ollama integration checks ran successfully. This does not prove packaged-app acceptance. Skips: three Windows symlink checks without privilege and two Pillow checks without PIL. The subsequent shared form/status markup passed **13 WebUI tests**.
- Browser modules: **289 passed**. Electron: **38 passed**. Public docs: **21 passed**. Next production/type build passed. Diff integrity passed.
- Next was patched from 16.4.0 to exact 16.4.2 after the build reported a security advisory. The current desktop-ui dependency audit reports **zero vulnerabilities**. No automated upgrade agent or codemod was run.
- The earlier key-screen matrix captured **408 screenshots** across 17 screens, four widths and three simulated display scales. The latest normal-state matrix covers **35 screens / 140 screenshots**, light/dark at 480/1280 pixels, with 12 baseline comparisons. It passes overflow, serious/critical axe, mobile navigation, visible keyboard focus, local links, long-word stress and layout-shift checks. Final error and offline matrices each passed **140 screenshots**; the loading matrix passed **70 screenshots**. Together the latest four state matrices cover **490 screenshots**. Each matrix records its checks in matrix.json under desktop/task213-review/review-normal, review-error-fixed, review-offline and review-loading-clean.
- An initial loading run emitted Playwright cancellation callbacks during teardown. Aborting held requests before context closure fixed the harness cleanup; the subsequent 70-image rerun exited cleanly.
- The ordinary-profile Python run was affected by the owner's running installed app lock and optional FAISS state. Isolated reruns passed; the owner's app and data were not changed.

## Fixes established by the expanded audit

Shared native controls, surfaces, fields, lists and status text use canonical tokens across both UI stacks. Page-specific layout variants remain. The audit also corrected light contrast in Sage Core and Capabilities, invisible Chat composer focus, stale Agent actions after refresh failure, narrow Employee/Position/provider forms, optional wizard contrast, and layout shifts caused by growing status/option lists. Raw review objects now render inert readable text; the intentional advanced policy editor remains collapsed. Consent, exact approval digests, authentication, routing and resource admission are preserved.

The 3D map source-status area has a fixed reserved height and keyboard-accessible scrolling so multi-source errors cannot move the map and controls. Loading tests intentionally hold requests; offline and error tests deliberately fail read requests. These are deterministic UI evidence, not live-network reliability results.

## Final visual review

The owner approved the design direction. The owner approved the final before/after visuals on 2026-10-23. Current after screenshots:

- [Chat dark](D:/source/AI/ai-corporation/desktop/task213-review/review-normal/chat-dark-1280-100.png)
- [Chat light, narrow](D:/source/AI/ai-corporation/desktop/task213-review/review-normal/chat-light-480-100.png)
- [Agents light](D:/source/AI/ai-corporation/desktop/task213-review/review-normal/agents-light-1280-100.png)
- [Settings light](D:/source/AI/ai-corporation/desktop/task213-review/review-normal/settings-light-1280-100.png)

Unverified follow-up: packaged Electron theme persistence, actual Windows display scaling, assistive technology, exhaustive keyboard interactions in every dynamic dialog, representative users, and hardware/provider workloads. Simulated scale and Tab traversal do not prove these integrations. No whole-app accessibility certification is claimed.

Task 213 is accepted for its scoped local UI foundation; the checkpoint tag is task-213-ui-foundation-polish. Tasks 214-217 are planned and unimplemented. Preserved installer changes are unrelated and must remain outside the Task 213 checkpoint. No push or deployment was performed.

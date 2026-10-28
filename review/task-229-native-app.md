# Task 229 - native app, without browser UI

Task 229 is source-complete in three local phases. No push, deployment, new web engine, Node dependency or new packaged release was performed. The existing `legacy-electron-ui` tag was confirmed and preserved.

## Outcome and architecture

- Settings and Advanced open native Qt singleton windows, focused on repeated navigation. Owner access and encrypted Backup/restore have dedicated native dialogs. Tier2 uses a shared declarative searchable table, readable detail panel and typed, explicitly confirmed actions.
- `NativeSession` uses `InProcessController` / `PolicyTransport`. This invokes the same ASGI application-service handlers, authentication, permission dependencies, CSRF/origin rules, ownership, exact-action approvals, cloud previews/consent, resource/spend admission and Stop checks. It does not bind or listen on a TCP socket. The internal `http://127.0.0.1:1` envelope is a virtual routing identity, not a running server or destination contacted by the facade.
- Native authority is held in-process; nothing transfers it to a browser. Lock synchronously stops protected work, blocks authentication even with a previously captured session token, and removes client authority. Password verification unlocks the session; it does not resume stopped operations.
- The optional integration API remains an explicit standalone command (`python -m app.local`), off in the desktop and labelled off in Settings. It binds only loopback and requires owner authentication/session token plus existing request verification. The legacy launcher entry now delegates to Qt; it no longer starts its old Tk/browser UI.
- App `/ui` routes, HTML templates, static client assets, one-time launch-ticket routes and browser-only QA scripts are removed. Swagger/ReDoc HTML pages are disabled. No embedded webview bridge was needed: added web engine size cost is zero.
- Only the deliberate Open online docs click opens `https://ai.erselmetz.com`. Existing explicitly approved external `open_url` and intentional web-tool services remain separate from app navigation. Offline documentation uses a native Markdown widget that cannot load remote images or follow links.
- The public static site remains independent and Python-generated. Tasks223-227 now explicitly record that their browser Advanced allowance is superseded by Task229. Their historical evidence was not rewritten as new native evidence.

## Page migration and retirements

Pre-change source, route purpose/reachability and browser entry-point inventory: [audit](task-229-audit.md). There is no owner usage telemetry; “reachable” never means observed owner use.

| Old page / capability | Final native destination | Tier and status |
|---|---|---|
| Settings / capabilities | Settings, Privacy and capabilities, Capability policy, Session grants, Local speech, Brain embedding | Tier1; AI-verified controls; live Settings navigation verified |
| Providers, provider connections, local models, online provider | Providers / Provider connections, Local models, Online providers | Tier1; native forms; installed local Ollama discovery Verified real; paid/cloud tests Unverified |
| Agents | Native Agent list/profile, pause/reset/duplicate forms | Tier1; AI-verified only |
| Approvals (previously embedded controls) | Native Approvals plus existing scoped inline chat/tool review | Tier1; native control AI-verified; live local tool approval Verified real |
| Activity | Native protected activity list/detail; chat keeps observed native steps | Tier1; navigation Verified real; no invented aggregation |
| Backup & restore | Dedicated encrypted export, inspect and restore dialog | Tier1; AI-verified only; existing backend crypto/restore regressions retained |
| Updates | Native curated updates, explicit trusted check and verified-installer preparation | Tier1; AI-verified only; no actual update downloaded or installed |
| Owner login | Native startup password dialog and Owner access / Lock now window | Tier1; actual startup Verified real; lock/old-token denial AI-verified |
| Employees, Positions, Projects, Tasks | Declarative native search/table/detail/action windows | Tier2; AI-verified controls; real read navigation verified |
| Workflows, Workflow map, Organization map | Workflows, Workflow map, Structure tables/details | Tier2; real-data list fallback; no invented graph or execution |
| Software inventory, Performance readiness | Software inventory, Readiness | Tier2; native guarded readers |
| Preferences | Typed native preferences forms / reset | Tier2; actual guarded writes tested in-process |
| Documentation | Native offline protected Markdown reader | Tier2; no HTML rendering or network assets |
| Coordinator Chat / Brain / 3D visualization | Existing native three-pane chat and shared full-window projected-3D/list widget | Existing native; live chat and Brain feed Verified real; deterministic regressions retained |
| Employee chat | Native Employee conversation list/detail/start/send | Additional native workflow; AI-verified forms, no new cloud-generation claim |
| Home dashboard | Native shell / Advanced navigation | Tier3: duplicate HTML dashboard retired |
| Memory HTML alias | Existing native Brain inspect/forget/retention controls and Brain settings | Tier3: HTML alias retired; guarded scope/backend tests retained |
| Sage Core HTML | Native Sage Core read-only detail | Tier3 HTML retired; underlying real-data reader retained |
| Automation HTML | Native exact desktop controls and native Automation allowlist forms | Tier3 HTML retired; no automatic site or desktop action |
| Raw JSON assignment-policy editor | Read-only native Assignment recommendations and explicit Disable action | Tier3 editor retired: it exposed technical evidence-authoring JSON rather than a safe native owner form. Policy backend tests remain; no new evidence-authoring workflow is claimed |
| Legacy Brain-import HTML / browser-only speech setup | Hidden legacy HTML; current native Brain file/note intake and local speech settings | Tier3: legacy import/browser speech surfaces retired. Import backend provenance/preview tests remain; no claim that a new legacy-import widget was built |

Maps use the permitted table/detail fallback. Existing permissions deliberately deny some actions, including `project:create` for the shipped owner session; the UI reports the denial rather than elevating authority. Capability/workspace approvals remain scoped; chat-specific approval is kept in the owning chat, not flattened into cross-window authority.

## Safety and dead-control checks

The Settings/Advanced sweep patches `webbrowser.open`, `QDesktopServices.openUrl` and `os.startfile` to fail; clicks every navigation action; confirms native window/singleton focus; and separately checks the explicit online-docs destination. Actual startup runs with the same browser tripwires.

The native schema sweep opens every action dialog, checks explicit confirmation defaults, and cancels without submitting protected actions. Typed submission, secret-field clearing, search/detail behavior, offline resource denial, native lock, old-token rejection, origin/CSRF/default-deny/Stop, concurrent in-process streaming and actual protected readers have regressions. This is not a claim that destructive or paid operations were all executed. Action confirmation is disabled while a request is pending; failure requires another explicit confirmation. Approval digests are not invented or silently substituted.

Backup Restore requires an inspected file, the confirmation word, its passphrase, and unchanged bytes from that inspection; a changed file is rejected before dispatch. Existing server inspection, encryption, owner permissions and restart gating remain authoritative.

## Windows evidence

Actual desktop `app.qt_desktop.__main__.main`, including QLockFile/local IPC and a visible registered native window:

```text
Command: netstat -ano
App PID: 12732
LISTENING entries for app PID:
(no matching LISTENING entries)
```

A separate visible native journey also had no listener (PID12224). Installed local `qwen3.5:4b` digest is recorded in [evidence](task-229-evidence.json). No model was installed or downloaded.

| Journey | Result |
|---|---|
| Actual native startup / browser tripwires / no TCP listener | Verified real |
| Local Ollama chat | Verified real; 24,288.79 ms |
| Native Brain note feed | Verified real; one retained user chunk in isolated QA profile |
| Real model tool proposal, explicit approval, calculate 17*19 | Verified real; receipt323, completed in 17,805.41 ms |
| Settings / all then-current Advanced windows / local-provider discovery | Verified real; protected native reads and local catalog available |
| Native typed forms, failure/cancel/consent gates, lock, backup changed-file rejection | AI-verified only |
| Physical mic/camera/screen, paid Gemini, real FreeLLMAPI, assistive technology, clean Windows user | Unverified |
| New packaged Task229 executable / installer / update installation | Unverified; not built or installed |
| Known broken mandatory Task229 source checks | None remaining after fixes |

Important: the older Task227 packaged EXE still contains its historical browser implementation. This source checkpoint does not silently replace that artifact or an installed shortcut. Run `native_entry.py` from the updated source; rebuild a package before claiming packaged parity.

## Tests and accounting

| Check | Actual result |
|---|---|
| Full Python suite: `.venv/Scripts/python.exe -m pytest -q` | 1,746 passed, 3 skipped, 4 warnings; 766.70 seconds; 1,749 collected |
| Final affected native checks (including final Backup regression) | 14 passed, 1 warning; 26.59 seconds |
| Final public docs/browser/integrity and coverage ledger | 48 passed; 28.06 seconds |
| Final combined native/docs acceptance after error-display refinement | 62 passed, 1 warning; 46.82 seconds |
| Compilation, generated roadmap check, diff integrity | Passed |
| Existing shell screenshot baseline images | 18 retained; no rebaselining; suite passed |
| Expanded native window screenshot matrix | 396 grabs: 33 windows x 2 sizes x 2 themes x 3 DPI scales |

The three skips are the existing Windows symbolic-link privilege cases in `test_documentation_api.py` (two) and `test_sandbox_source.py` (one). Warnings are existing Starlette/Qt deprecations. No essential failure became a skip.

Before HTML removal: 2,053 collected. Explicitly retired: 308 app HTML/client cases (284 browser-module cases, 20 other HTML/browser cases, four HTML-only cases inside mixed suites). Added: four facade cases and one final Backup regression. Final source: 1,750 collected. The last Backup case was added after full-suite collection and passed in the final affected run; overlapping check counts are not added together as a larger full-suite result. Final native refinements were also rechecked there. [Per-file/per-case retirement ledger](task-229-coverage-migration.json) preserves all removed case identities/reasons and links replacements; historical Task227 coverage history remains intact. Backend, permissions, consent, spend, resource, tool, public-site and intentional browser-tool regressions remain.

Initial failures were corrected: a TestClient fixture lacked a loopback client identity; the custom ASGI scope initially needed lowercase header names; two tests still expected deleted HTML assets; and a native test incorrectly assumed project:create authority. No permission was added to make that test pass. A final native error-formatting test uses a structured fake response; the local API's deliberate validation-error sanitization remains unchanged.

Local screenshot index: `task229-review/screenshot-matrix.json`. Examples: [Providers dark125](../task229-review/release-screenshots/dark-1.25/Providers-960.png), [Owner access light150](../task229-review/release-screenshots/light-1.5/Owner-sign-in-700.png), [actual app entry](../task229-review/startup/actual-entry.png), [live chat and Brain](../task229-review/live/chat-brain.png), [approved Agent result](../task229-review/live/agent-result.png). Fixture screenshots are AI-verified only. Logs and raw QA data stay local/ignored; their results and identities are recorded in committed evidence.

## Checkpoints

- Phase A: `99cb467`, tag `task-229a`; no browser app navigation/tickets.
- Phase B: `5709e49`, tag `task-229b`; native management windows.
- Phase C: tag `task-229c`; remove HTML/listener, complete verification/accounting.

Exact Phase C source/deletion identity is recorded in `task-229-source-manifest.json` (self excluded). No push/deploy. No next roadmap task started.

# Task 223 — PySide6 shell and window foundation

2026-10-25, local only. Parent: `4e31c7c` (Task 222). The earlier Tk shell and
unfinished native-Brain work remain separate historical/WIP artifacts. This phase
implements the revised **223** contract; it does not claim 224–227 completion.

## Decision and measured spike

Reuse the Python authentication, chat/workspace, retained knowledge, resource,
approval/consent and update/backup services. Replace the main shell with native Qt.
Keep existing Python-served organization/provider/backup pages in Advanced.

Two transport options were reported before implementation: a service facade that
explicitly reuses every permission/approval/consent/spend layer, or authenticated
loopback HTTP preserving the existing route checks. **Loopback HTTP was chosen**;
one Python process owns the Qt windows and one backend thread. The shell never
calls provider inference or domain registries around application guards.

`tools/qt_tk_brain_spike.py` ran visible 880×680 windows at DPR 1 on the installed
Radeon RX 570 Series (driver 31.0.21925.1001), Python 3.14, PySide6 6.12.0. Both
renderers used the same deterministic synthetic sphere and changing projection.
The benchmark is explicitly synthetic, never presented as application Brain data.

| Renderer | Nodes | Repaint FPS | Mean frame | P95 frame |
| --- | ---: | ---: | ---: | ---: |
| QPainter, antialiased radial glow | 300 | 81.83 | 12.22 ms | 13.63 ms |
| QPainter, antialiased radial glow | 2,000 | 13.58 | 73.63 ms | 76.23 ms |
| customtkinter/Tk Canvas, three glow rings | 300 | 41.53 | 24.08 ms | 24.83 ms |
| customtkinter/Tk Canvas, three glow rings | 2,000 | 6.44 | 155.29 ms | 159.91 ms |

These are CPU/event-loop repaint throughput, not GPU or display-present FPS. Qt's
soft translucent glow looks smoother; Tk has stepped, opaque rings. At 2,000 nodes
both become visually overcrowded; 224 must use bounded grouping/caching and a list
fallback. **Use PySide6: no blocker was found.** Raw JSON and PNGs are in the local
ignored `task223-review/spike/`; committed evidence is in the adjacent summary.

## Implemented

- Three resizable gold/dark panes, a persistent chat pane and per-window chat tabs.
  Ctrl+B hides the sidebar and gives Brain/chat equal widths. Ctrl+N and a second
  launch create another chat window in the same process. Models/agents/projects
  belong to each conversation; changing an existing assignment starts another tab.
- One authoritative QLockFile with a same-user QLocalServer activation channel.
  The secondary process sends only a bounded fixed new-chat command and waits for
  acknowledgement. It starts no backend. The legacy backend controller uses the
  already-owned Qt lease rather than acquiring a second application lock.
- Separate singleton Settings and Advanced launcher windows: reopening focuses
  the existing Qt window. Existing Advanced content opens in the default browser;
  browser tab/window placement remains controlled by that browser.
- Authenticated, CSRF-protected Advanced launch minting; allowlisted pages only;
  30-second, one-use ticket; browser session cookie is HttpOnly/SameSite=Strict.
  Source-session expiry/logout invalidates pending tickets. Tokens are not the
  desktop's long-lived cookie, no redirect destination is accepted from a caller,
  responses are no-store/no-referrer, and all API permissions/approvals remain.
- Shared Qt palette/type/spacing/radius/motion tokens, visible keyboard focus,
  accessible names, word-wrapped plain-text labels and chat insertion, designed
  loading/offline/empty/error states, light theme and reduced-motion preferences.
  No internal JSON editor exists in this shell. No automatic model downloads.
- Existing native startup command now enters Qt, with an actionable Qt dependency
  check. `requirements-desktop.txt` pins Essentials; the shell imports no
  QtWebEngine or GPL-only add-on module. Node-dependent legacy sources remain
  until native parity/coverage is verified in 227.

Native Brain graphics/intake are **224**; the current center is an honest empty/
informational state, not invented activity. The file/folder controls currently
lead to Advanced intake. Knowledge pack/math are **225**. Native bounded-loop
controls, queue/cancel, devices, stops and rename/delete are **226**. Safe restore,
artifact smoke/update checks and Node removal are **227**. Closing a window with
an active reply currently asks it to finish; this is not a verified cancellation
implementation. Full parity and the final no-Node claim remain outstanding.

## Evidence

`tools/qt_shell_check.py` exercised an actual visible Qt window and installed local
`qwen3.5:4b` through the authenticated API in an isolated profile. It returned
“Hello! How can I help you today?” in **20,538.35 ms**. It also passed Ctrl+N
isolation, singleton Settings/Advanced, a separate browser-cookie exchange and
replay denial, and Ctrl+B equal panes. An explicit final source rerun after UI polish/thread-delivery fixes returned the same reply in **10,363.68 ms**; both runs are retained, without a steady-state performance claim. No cloud calls, model downloads or device captures.

`tools/qt_process_check.py` additionally launched the actual compatibility entry
point twice: the second invocation exited successfully, two visible chat windows
belonged to the same application worker PID, that worker had no child processes,
and closing both exited gracefully. Windows' source virtual-environment launcher
is a separate redirector parent; it is not a second UI/backend. The final packaged
one-process boundary still requires its own 227 artifact check. The first smoke
attempt inspected the redirector PID instead of the GUI worker; process-tree
inspection corrected that checker rather than weakening the two-window assertion.

`tools/qt_layout_check.py` produced 12 widget grabs: two sizes, light/dark and
`QT_SCALE_FACTOR=1/1.25/1.5`, with long Taglish fixtures. The chat/composer stayed
visible with at least 250 logical-pixel width at the 800×580 minimum. At 150%, the
large light window was clamped by the available physical screen to 1283×707;
the recorded actual sizes are retained. These exercise Qt scaling, not a claim
that Windows desktop settings or assistive technology were changed/tested.

Source screenshots: `task223-review/shell.png`, `settings.png`, `advanced.png`,
`sidebar-hidden.png`, plus the layout directory. The layout fixture performs no
model inference or actions. Final baseline/comparison matrix and dead-control
coverage remain 227 work; these are early source grabs.

Verification: full Python **1,475 passed / 3 Windows symlink privilege skips /
0 failed**, 229.37 seconds, two dependency deprecation warnings. Ten new
Advanced/Qt cases cover expiry/replay/CSRF/origin/logout denial, window isolation,
singleton windows and a real subprocess activation handoff. A final focused rerun
also covers plain-text presentation and preserving stream-error failure state
after completion. Initial focus-test timing was repaired by waiting for native
Windows focus to settle, without relaxing its shortcut/geometry assertions.

The full suite used `OLLAMA_TEST_MODEL=qwen3.5:4b`; existing ignored TypeScript and
export fixtures were linked from the main worktree for legacy source regressions.
No packaged Electron or native artifact claim. No tests retired in this phase.
Final Qt/Advanced/local-access rerun: **23 passed**. Legacy browser-module suite:
**295 passed**; Electron source suite: **44 passed**; public docs: **23 passed**.
Python documentation-integrity CLI and `git diff --check` passed. No packaged
Electron work and no deployment. `requirements-desktop-dev.txt` records pytest-qt,
the benchmark-only Tk comparison, and the process-inspection dependency.

## Licensing

No repository license was silently selected. The application's own copyright/
license stays distinct from Qt's LGPLv3 terms. [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)
records the module scope and distribution requirements: exact notices/licenses,
replaceable dynamic libraries, corresponding library source or a compliant offer,
and replacement/relinking/debugging rights with applicable installation information.
Task 227 must verify the actual bundle; source-mode success is not license-package
completion. References: [Qt obligations](https://www.qt.io/development/open-source-lgpl-obligations)
and [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).

Local phase checkpoint: `task-223-pyside6-shell`. No push or deployment.

Screenshots: [shell](task-223-qt-assets/shell.png), [Settings](task-223-qt-assets/settings.png), [Advanced](task-223-qt-assets/advanced.png), [sidebar hidden](task-223-qt-assets/sidebar-hidden.png). Synthetic spike appearance: [Qt](task-223-qt-assets/qt-300.png), [Tk](task-223-qt-assets/tk-300.png).

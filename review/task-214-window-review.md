# Task 214 shared-backend window evidence

Base: Task 213 `118d1c7`. Local checkpoint: `task-214-shared-backend-windows`.

## Behavior and boundaries

The existing single-instance Electron shell now owns an explicit window registry. Second launch and the native Ctrl+N input event create chat windows without spawning another backend. Settings opens in a separate, nonmodal singleton window. A new window creates its own empty chat rather than adopting another window's latest conversation.

Only known live windows with the exact app origin can use workspace IPC; main-frame identity is compared with Electron's actual `webContents.mainFrame`. Native camera/microphone confirmations remain per use, with one-use grants keyed to the requesting WebContents and removed on close. Renderer isolation, denied popup navigation, owner cookies, loopback origin, backend authentication and CSRF checks remain intact.

`desktop/workspaces.json` in the app data directory stores at most ten window descriptors: geometry plus conversation/agent/model/project identifiers. Prompts, messages, tokens, approvals, tools, consent and action state are excluded. Restore validates identifiers and clamps geometry to the current primary work area. It does not send a model turn or replay an action. Existing retention rules apply: an unavailable/unretained conversation opens a new empty chat with a visible explanation. Retention is never silently enabled. Project/model descriptor fields are supported here; the independent selectors and server-enforced workspace/project association remain Task 215.

## Reproduction and real evidence

`node tools/task214_electron_check.cjs` uses an already cached Electron 44.7.0 runtime, verified against its dependency SHA-256 before local extraction. It never downloads Electron. Each run uses a fresh isolated profile and port 18874, leaving owner data untouched. The script exercises real Electron main/renderer processes and the Python sidecar; it performs no model turn, paid call, install or cloud transfer.

Latest source-mode run passed direct chat, distinct window IDs, native Ctrl+N event handling, separate singleton Settings, second-launch creation in the same main process, unchanged backend listener PID, and restoration of all four open windows after restart. Evidence and screenshots are in ignored `desktop/task214-review/`. The tested main PID was 16432 and backend listener PID 21000. This is source-mode evidence against a dirty Task 214 worktree based on Task 213, not a packaged build identity.

The first real check exposed an incorrect assumption that Electron WebFrameMain provides `isMainFrame`; actual main-frame object identity fixed the denied bridge. Browser CDP keyboard injection did not reach Electron's native input event, so the check now uses Electron `sendInputEvent`. It verifies the real native event handler, not a physical keyboard session. A subsequent harness error used `require` in an isolated evaluation context; moving listener inspection to the test process fixed it.

## Validation

Full Python: **1422 passed, 5 skipped, 0 failed**, two deprecation warnings. Skips: three unavailable Windows symlink checks and two unavailable Pillow checks. Browser modules: **292 passed**; Electron: **43 passed**; public docs: **21 passed**. JavaScript syntax and diff integrity passed. Focused window tests cover singleton/close/restart behavior, bounds, malformed state, untrusted/stale windows, external navigation, settings-to-chat routing, and excluded replay/secrets. Chat tests cover read-only conversation restore and new-window conversation separation. Existing source-contract tests follow the extracted registry and per-window grants rather than assuming one global window.

## Unverified and separate scope

Packaged installer restart, multiple monitors, actual Windows scaling, physical keyboard/camera/microphone, clean Windows accounts, retained production conversations and concurrent real model workloads remain unverified. Task 215 adds server-enforced per-window selection/approval/project isolation; Task 216 adds visible queue/device ownership; Task 217 owns real concurrent workload QA. This phase makes no claim that those later contracts are complete. Unrelated installer edits are preserved outside the checkpoint. No push or deployment.

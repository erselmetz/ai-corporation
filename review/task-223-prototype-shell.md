# Task 223 prototype shell — partial, failed phase gate

Date: 2026-10-25 (Asia/Manila). Local only. No push, deployment, model download, or live generation call was performed.

The owner authorized Tasks 223–227 in the attached request, with a reuse/replace/Advanced table before implementation, one local commit/tag per passing phase, and a stop on a failed phase. The table was delivered before code changes. Prototype Python files are UX references; their setup comments and unsafe tool implementations were not executed or ported.

| Decision | Implementation direction |
| --- | --- |
| Reuse | Auth, permissions, conversation/workspace services, model discovery, Brain controllers/storage/map, approvals, traces, Stop and backup services. |
| Replace | Main chat composition with resizable sidebar/Brain/chat, conversation tabs, Ctrl+B/Ctrl+N and original amber/dark styling. |
| Advanced | Existing organization, Employees, Positions, Workflows, Providers, inventory, backup, preferences and Brain settings in separate windows. |

## Outcome and phase status

| Phase | Status | Evidence or remaining work |
| --- | --- | --- |
| 223 | **Broken verification gate; implementation partial** | Six real source-mode Electron checks passed, but the full Python suite failed. No completion checkpoint/tag. |
| 224 | **Unverified — not started** | Current shell reuses the existing Brain map/list. Requested core/user layers, source clustering, anchored Forget card, app-wide ingestion and ingestion/search changes remain undelivered. |
| 225 | **Unverified — not started** | Shipped pack, instant replies, math expansion and prefix comparison remain undelivered. |
| 226 | **Unverified — not started** | Bounded tool loop, per-tab model improvements, actual thinking controls/stream and expanded hardened tools remain undelivered. |
| 227 | **Unverified — not started** | Five-file/folder ten-question evaluation, real Ollama runs, adversarial tool evaluation and RX 570 measurement were not performed. |

The shell is reviewable local work, not a claim of full prototype parity. Steps displays existing observed trace text; multi-step/thinking controls are explicitly labeled planned rather than presented as working. Existing optional model, Agent and project selectors are moved without changing their services. Conversation search is retained in Advanced; rename/pin/delete menus remain on the conversation strip. Existing Memory-to-Brain integration was already present in the starting dirty tree and is not attributed to this phase.

## Actual checks

| Command | Result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | **1 failed, 1,445 passed, 3 skipped**, 280.68 seconds, two deprecation warnings. Started before implementation and completed during work. |
| `node --test tests/*.mjs` | **295 passed**, zero failed/skipped. |
| `npm.cmd test --prefix desktop` | **44 passed**, zero failed/skipped. |
| `npm.cmd test --prefix docs` | **21 passed**, zero failed/skipped. Roadmap enumeration expectations were updated for five newly authorized planned contracts. |
| `npm.cmd run ui:build --prefix desktop` | Production build, TypeScript and static export passed. |
| `node tools/task223_shell_check.cjs` | Passed six checks in installed local Electron 44.7.0 source mode with an isolated temporary profile; no renderer page errors. |
| `git diff --check` | Passed. |

The Electron check proves mounting Brain/intake beside live chat, Ctrl+N adding exactly one conversation tab without opening a window, equal Brain/chat widths with Ctrl+B, keyboard split adjustment, an actual local consented note save, and a separate Advanced Brain settings window. It uses a synthetic test note in an isolated profile, not the owner's retained data. No model answer is requested. Advanced popup regression also proves same-origin route allowlisting, external/file/API URL rejection, registration and sandboxing.

The failed test is `tests/test_image_processing.py::test_resize_convert_and_redact_with_optional_pillow`. The child image worker returned nonzero on resize; the service reported `Image processing failed or the image is malformed`. A focused rerun with `-rs` **skipped** because `PIL.Image` could not be imported (`No module named 'PIL'`). A direct interpreter import also failed. This does not establish the original failure's root cause or repair it. No dependency was installed, removed, or replaced by this work. The failure remains unresolved and was not converted into a passing gate. The original three skip identities were not captured by the initial non-`-rs` invocation.

## Screenshots and limitations

- [Full three-pane source-mode shell](../desktop/task223-review/shell-full.png)
- [Sidebar hidden, equal Brain/chat panes](../desktop/task223-review/shell-hidden.png)
- [Machine-readable UI result](../desktop/task223-review/result.json)

These are real source-mode Electron screenshots and synthetic local data, not packaged-installation, representative-user, accessibility-device, live-model, or GPU-performance evidence. Narrow-screen layout and pointer dragging are not established by the six automated UI checks. The existing Brain map retains its explicit list/3D toggle; the requested visualization is Phase 224. New intake still uses the existing size/chunking/indexing contract, not Phase 224's requested contract. No five-file/folder retrieval benchmark or prefix score thresholds are claimed.

## Source identity, exact incremental scope and handoff

Starting branch: `main`; HEAD: `75145cda27461b6d228a6b18dbadc6ea44688268`. There were already two local commits ahead of the tracking ref and extensive tracked/untracked changes at session start. They were preserved. Nothing was staged.

Changed existing files, incremental to that dirty starting state:

- `app/webui/router.py`: three Chat asset references only.
- `desktop/workspaces.cjs`: allowlisted separate Advanced windows, bounded window count and renderer-owned Ctrl+N in chat.
- `desktop/test/workspaces.test.cjs`: replace the old Ctrl+N-window expectation with the authorized tab behavior; retain explicit window/Settings tests.
- `docs/tasks-data.mjs`: five owner-authorized planned contracts and groups, with failed/partial Task 223 evidence.
- `docs/test/site.test.mjs`, `docs/test/tasks-page.test.mjs`: exact roadmap counts/order/status expectations for those contracts.

New files: `app/webui/static/prototype-shell.mjs`, `app/webui/static/prototype-shell.css`, `desktop/test/prototype-shell.test.cjs`, `tools/task223_shell_check.cjs`, and this evidence record.

The local [source manifest](../desktop/task223-review/source-manifest.json) hashes the ten implementation/test/roadmap files. The [incremental patch](../desktop/task223-review/incremental.patch) separates this work from pre-existing modifications; its SHA-256 is `d52add039f72fc4fbca1e307ababf8fbb98a05dc7247a1db26e4a45b789be67a`. Baseline copies are in the temporary directory recorded in the manifest. Review artifacts under `desktop/task223-review` are local generated evidence.

No phase commit or tag was created because the phase gate failed. A standalone commit would also need careful prerequisite review: this shell reuses workspace/Brain changes already present in the dirty tree, including untracked files, which must not be silently absorbed into its checkpoint. Resume by diagnosing the Pillow parent/child environment discrepancy, then finish Phase 223 acceptance and review the exact prerequisite/diff scope before its local commit/tag. Do not start Phase 224 until that checkpoint passes. Never push or deploy under this request.

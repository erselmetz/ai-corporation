# Task 222 — local stabilization before the Python rewrite

Date: 2026-10-25 (Asia/Manila). Base: `e7ea9844567c74b8e7b4ac1a43a282b96bfd19a0`.
Local safety tag `legacy-electron-ui` points to that starting commit. The historical
Tk experiment is preserved; it does **not** fulfill the revised PySide6 contract.
Work was isolated on `codex/task-222-stabilization` in the adjacent Task 222 worktree
to preserve unfinished native-Brain changes in the main worktree. No push,
deployment, package installation, model download or packaged Electron debugging.

## Stabilization outcome

The installed `qwen3.5:4b` consumed its bounded answer budget on native thinking,
leaving no final answer. A local diagnostic with `num_predict=32` returned empty
content and 120 thinking bytes with default thinking (1,911.03 ms); `think:false`
returned `OK`, two evaluated tokens (562.37 ms). The existing answer-only backend
now disables unrequested thinking only when model metadata permits disabling it.
Named-level-only thinking metadata is preserved. Token/time limits, prompts,
approval/consent/spend checks, and routing remain unchanged. The local-only path
also rejects known cloud model identifiers or remote model metadata before
transferring a prompt. There is no fallback or automatic retry.

The metadata probe is loopback-only, bounded to five seconds and 256 KiB. Unknown
metadata retains the previous behavior; it does not assert a model is safe, fast or
compatible. The live rerun was an explicit second evaluation after the fix, not
hidden retries. No broader RAG-quality implementation was added during stabilization.

## Live backend evidence

Runner: `tools/task222_live_check.py`. Ollama was already running at
`127.0.0.1:11434`; the runner checks availability before calls and stops if it
disappears. The installed local model was `qwen3.5:4b`, digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
The dedicated evaluation used no `llama3.2:3b` inference or cloud stub. Authentication, owner-scoped
knowledge consent and ResourceManager were used in an isolated temporary profile.

| Check | Before fix | Explicit rerun after fix |
| --- | --- | --- |
| Task 202 correct role choices | 0/5; all timed out | 5/5 |
| Choice mean wall time | 30,053.87 ms | 3,499.15 ms |
| Actual documents ingested | 5/5 | 5/5 |
| Task 196 completed responses | 0/10 | 10/10 |
| Expected source in retrieval preview | 6/10 | 8/10 |
| Strict accepted-string matches | 0/10 | 7/10 |
| Answers with inline numeric citations | 0/10 | 1/10 |
| RAG mean wall time | 30,220.89 ms | 5,838.33 ms |

The five unchanged real files were `desktop/requirements-build.txt` (21 bytes),
`requirements-knowledge.txt` (139), `review/task-223-native-python.md` (4,230),
`review/task-214-window-review.md` (4,347), and
`review/task-223-prototype-shell.md` (7,697). These are actual repository documents,
not synthetic notes. Historical prose was treated as retrieved data, not instructions.
Two questions per document used fresh conversations. Hashes, individual questions,
retrieval sources, acceptance strings, elapsed times, errors and source identity are
recorded in [the committed summary](task-222-live-summary.json). Raw answer/trace
logs remain in ignored local `task222-review/` files. String matching measures a
narrow factual check, not a judged correctness score; one numeric citation does not
establish that its attribution is correct. Retrieval is lexical-only here with an
existing 1,800-byte context bound. Quality remains **partial**, not release-ready.

Task 202 exercised five selection decisions, not five delegated action executions
or their final answers. Task 198 hands-free checks loaded the installed Eyes/Ears/
Voice libraries and enumerated the default microphone. Tesseract/language data are
not configured. No recording, screenshot/camera capture, OCR, transcription,
speaker playback or physical Stop test occurred; those remain **Unverified**.
Ollama's `/api/ps` reported 3,135,252,724 loaded bytes and the same VRAM byte count;
this does not establish RX 570 rendering performance or hardware compatibility.

## Documentation integrity and roadmap

The post-100 roadmap is now a strict JSON-compatible array within its existing
static JavaScript module. Escaped Windows paths and UTF-8 serialization are fixed
at source, not masked by browser replacements. Damaged Unicode in architecture
and updates pages, lost known separators, and a duplicate roadmap HTML ID are fixed.
`.editorconfig` records UTF-8/LF for documentation; UTF-16 runtime requirements are
not bulk-reencoded. `tools/docs_integrity.py` and pytest regressions reject invalid
UTF-8, known mojibake, damaged separators, duplicate canonical task numbers,
duplicate current update entries and duplicate HTML IDs.

Tasks 180/184 now each have one current public update article and expandable
History, with old anchors preserved. Repeated current curated updates for
176/177/180/182/183/184 are merged into one authoritative record with validated
history; the roadmap displays that history too. The update reader accepts only
the explicit optional historical schema, still rejects unknown fields, and emits
one current update per record. No arbitrary fields are exposed through its API.

Task **197 exists** with historical source graph evidence. Tasks **204/205/206 did
not exist** in the starting roadmap; explicit `not_done`, scope-undefined entries
now state that accurately. Tasks **213–221 are superseded by 223–227**, retaining
history. Absent 220/221 have no invented implementation claims. Task 223 is planned
again under the owner's Qt contract; the earlier Tk checkpoint is historical.
Task 194's packaged-startup blocker is **“superseded by the Python shell
(Tasks 223-227); not fixed”**. It was not debugged, retested or promoted.

The release-readiness table in Task 222's `docs/tasks-data.mjs` record covers each
declared authorization capability plus product journeys. Axes use **Source-verified**,
**Packaged-verified**, **Real-device-verified**, or **Unverified**. A source catalog/
deny-by-default policy check proves that boundary only; it does not certify the
capability's end-to-end behavior. All packaged/device axes remain Unverified in
this checkpoint. Existing historical statuses are not evidence of a new artifact.

## Node inventory — retain until native parity

| Current dependency | Python replacement or retire decision (223–227) |
| --- | --- |
| `desktop/` Electron main, preload, window/workspace/session managers | PySide6 window manager, QLockFile/local socket, same backend; port trust/isolation/restore tests before retirement |
| `desktop-ui/` Next.js/React/TypeScript pages, tokens and build | Qt main shell/shared widgets/theme; preserve existing Python Advanced web pages rather than rewriting them |
| `desktop/package.json`, electron-builder/NSIS and desktop build/backend scripts | PyInstaller one-folder or Nuitka; per-user Inno Setup/NSIS; Python build stamp/smoke; retire Electron-specific packing after parity |
| Root start/build scripts and experimental Python builder | Review/replace for Qt packaging in 227; current Tk build command is not a verified release |
| `tests/*.mjs` browser modules (295 checks) | Port user-facing contracts to pytest/pytest-qt; retire DOM-only rendering mechanics with a per-category rationale after native equivalents pass |
| `desktop/test/` (44 checks, including TS hardware helper) | Port one-process lifecycle, origin/trust, device consent, restore, signing/build stamp/recovery behavior; retire Electron IPC/isolation implementation assertions only after native equivalents |
| Next static export/type build; `tools/task214_electron_check.cjs` and other Electron review runners | Python native source/artifact smoke plus screenshot/DPI/window matrix; retire obsolete Electron-only UI checks in 227 |
| Python Playwright imports in `app/integrations/browser_inspection.py`, `scoped_browser_automation.py`, re-exported by `integrations/__init__.py` | **Final no-Node blocker**: replace browser capability with an approved Python-native boundary or explicitly retire it; preserve permission/approval behavior and coverage before removal |
| `requirements.txt` Playwright + bundled Node (greenlet/pyee support deps) | Remove only after its callers are replaced/retired; final dependency/artifact scan in 227 |
| Existing Python-served `app/webui` Advanced pages | Keep, loopback browser/pywebview with short-lived one-use launch token exchanged for cookie; fail closed |
| Python update verification/recovery policy and Electron UI hooks | Keep verified installer policy; replace native prompts/install hooks; preserve opt-in checks, signatures, data and local-only failure metadata |
| `docs/package.json`, `server.mjs`, Node test runner, `tasks-data.mjs`, `vercel.json` | JSON/Python-generated source and static public output; Python integrity already added; port route/site tests before retiring Node deployment tooling |
| `node_modules`, package lockfiles, unused Node build scripts | Retire only in final 227 commit/tag after parity and coverage accounting |

Public browser JavaScript can remain in static pages; the final desktop/build must
not require Node. No production domain, hosting configuration or deployed file was
changed. This inventory does not authorize deleting current sources now.

## Next-phase decisions and assignments

The two backend options are: (1) an in-process application-service facade with
the **same** authentication/permission/approval/consent/spend boundaries explicitly
reused, or (2) the existing authenticated loopback HTTP API, retaining its route
checks and isolation at the cost of HTTP/session lifecycle overhead. A facade must
not call registries around existing guards. Task 222 does not choose or implement
a new boundary; Task 223 chooses after the Qt/Tk spike and inspection.

PySide6 is the default, with measured Qt-vs-Tk 300/2,000-node FPS/look evidence on
this PC required before committing the new shell. Licensing review should inventory
the exact Qt modules: some are LGPLv3, some GPL-only. For LGPL distribution, retain
replaceable dynamically linked Qt libraries, notices/license text, corresponding
library source or a compliant offer, and the user's ability to replace/relink and
debug library modifications, including required installation information. Verify
the chosen bundle's exact obligations before shipping. The application's own code
does not automatically become LGPL; its repository license remains an owner choice.
Keep that license separate from `THIRD_PARTY_NOTICES` and Qt source/notice delivery.
No project license was selected or changed. Sources: [Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations)
and [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).

| Phase | Assigned carry-over scope |
| --- | --- |
| 223 | Lock, true chat windows/Ctrl+N, Settings/Advanced singleton windows, theme, DPI, keyboard/accessibility |
| 224 | Shared full-window Brain/3D real-data widget, anchored node card, list fallback, Esc/back |
| 225 | Knowledge pack, instant replies, exact math tools, prefixed embeddings; no new carry-over assignment |
| 226 | ResourceManager queue/cancel, exclusive mic/camera/screen indicator, global/window stops, URL approval/rules, rename/delete reproduction/fix, truthful tool replies |
| 227 | Safe restore, screenshot matrix/dead controls, packaging/update checks, coverage ports/retirements, Node removal, measured package/startup/memory/FPS |

## Verification and checkpoint

Final results are recorded below after the regression gate. Commands run in the
isolated worktree using the main repository's existing Python environment. Existing
`desktop-ui/node_modules` and `out` were linked read-only for legacy source tests;
no Node install or packaged Electron launch was performed. Initial worktree checks
exposed missing ignored build/dependency fixtures, three mocks that assumed chat
was the first request before the new metadata probe, and the strict Updates reader
rejecting history. Those causes were repaired without reducing behavioral checks.

Final gate and local commit/tag verification are recorded with the results below. No push or deploy.

The earlier full-suite runs did execute three inherited integration tests pinned
to the still-installed `llama3.2:3b`. That does not change the dedicated qwen dataset
above, but it was a test-selection defect relative to the owner's instruction.
Those three tests now select a reported installed local chat model via their
fixture, reject retiring llama3.2 and cloud identifiers, and honor explicit
`OLLAMA_TEST_MODEL`. The final full-suite command sets `qwen3.5:4b`; the focused
fixture/integrity rerun passed all 12 tests. No model was installed or removed.

| Suite | Earlier observation | Final gate |
| --- | --- | --- |
| Full Python | Initial stabilization pass: 1,454 passed, 5 failed, 4 skipped; failures repaired | 1,465 passed, 3 skipped, 0 failed; 206.40 s; live fixtures explicitly qwen3.5:4b |
| Browser modules | Historical 295 checks | 295 passed, 0 failed |
| Electron source tests | First isolated attempt: 42 passed, one module failed to load missing ignored TypeScript dependency | 44 passed, 0 failed after linking existing dependencies |
| Public docs | Historical 21 checks | 23 passed, 0 failed (two added status/history/readiness cases) |
| Docs UTF-8/uniqueness | No independent Python check before stabilization | 8 pytest cases, plus Python integrity CLI |

No tests were retired in 222. No packaged Electron startup, Task 203 frame-time
measurement or new Next production build was run; those UI/artifact measurements
are replaced by the native 227 gate. Existing source exports were used only as
legacy regression fixtures. Full logs are local ignored `task222-*.log`; the
committed summary records the reproducible live measurements.

The three final skips are Windows symlink-creation privilege limits: two
documentation-root/escape cases and one sandbox workspace-link case. No provider,
approval or failed functional check was converted into a skip. Two dependency
deprecation warnings remain (Starlette/AnyIO aliases).

Final commands:

```powershell
$env:OLLAMA_TEST_MODEL='qwen3.5:4b'
D:/source/AI/ai-corporation/.venv/Scripts/python.exe -m pytest -q -rs
node --test tests/*.mjs
npm.cmd test --prefix desktop
npm.cmd test --prefix docs
D:/source/AI/ai-corporation/.venv/Scripts/python.exe tools/docs_integrity.py
git diff --check
```

The Python collection contains 1,468 cases including three skips; stabilization
adds 16 cases (eight documentation integrity, three provider capture, five update
history) and two public-docs cases. Browser/Electron coverage counts are unchanged.
This is the coverage baseline to port/account for in 227; no tests were silently
removed. Public docs expose 226 authoritative records, including nine superseded
and three not-done scope gaps. Next dependency-ready migration phase: **223**, with
the Qt/Tk benchmark and backend-boundary decision before the new shell commit.

Checkpoint: one local commit tagged `task-222-stabilization`; the tag identifies
the complete reviewed source, including this report. Main-worktree native-Brain
WIP is outside that commit and is preserved separately; it is not covered by this
isolated checkpoint's full-suite claim. `legacy-electron-ui` remains at the base.

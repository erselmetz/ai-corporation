# Task 226 — native resources, Stop and truthful actions

Local work on `codex/task-226-native-runtime`, based on Task 225 checkpoint
`b228e076727c26774dfa7e4270e3114a4d048f2d`. Source runtime checkpoint:
`task-226-native-runtime`, local only, 2026-10-27. This is scoped development
acceptance, not a complete product, packaged or physical-media certification.
The additional table-answer quality probe remains failed, and model quality
remains partial. No push, deployment or Node retirement is claimed.

Implemented source contract:

- Window-bound cancellation generations, visible ResourceManager queue, separate
  control workers, per-window/global Stop and explicit Resume without replay.
  Independent Agent work cannot borrow another allocation. Explicit nested local
  embeddings can temporarily retarget the same allocation while reserving its
  parent route's capacity.
- Conversation rename (F2/button) and confirmed delete, with owner/workspace
  checks and version-3 retained-history title migration. The initial F2 regression
  was reproduced in `task226-review-rename-before.log` before the fix.
- Guarded native tools use existing principal permissions, Agent allowlists,
  capability authorization, exact approval digests and guarded runtime callbacks.
  File roots are explicit and window/workspace bound. Writes show a complete diff
  and reject stale targets. Windows parent directories remain pinned during
  replacement. Web retrieval pins public DNS results, verifies TLS against the
  original hostname, revalidates redirects, blocks private destinations, bounds
  bytes and treats results as untrusted.
- Deterministic `open youtube` proposes the exact HTTPS destination without a
  model call. Browser handoff reports submitted/unverified, never page loading.
  The shipped Coordinator profile now explicitly allows `native.open_url`;
  principal permission and per-action approval remain mandatory. Existing
  owner-edited profiles are not silently overwritten. Paused Agents cannot use
  native tools.
- Local Ollama Agent loop: at most five total model/tool operations, one tool per
  step, canonical duplicate blocking, bounded results/context, explicit `num_ctx`,
  actual optional native/tagged thinking, no resource allocation held during review,
  conversation reservation while pending, raw user/final history only, authoritative
  IO receipts retained if a later step fails. No cloud fallback.
- Native chat fails closed on unverified local model metadata; every embedding
  batch checks local model metadata before sending private text. Remote aliases
  cannot use these local paths.
- Refresh preserves an unavailable model and its conversation until the owner
  explicitly chooses a replacement. Reproduced two failing Qt tests before fixing
  refresh fallback and the thinking checkbox that previously had no effect outside
  Agent mode. The five-test shell rerun passed. Observed logs wrap and retain the
  most recent 200 items rather than growing indefinitely.
- Native one-shot camera/screen/microphone controls now request exact backend
  approval before reserving ownership or opening a device. Images stay in memory,
  display a local preview and require a separate transfer confirmation. Microphone
  drafts require an installed local Whisper runtime and owner review before using
  text in the composer; they do not auto-send. Stop closes adapters/previews and
  ownership is retained until actual release. Qwen image routing preserves original
  Agent assignment and uses the existing ephemeral-attachment consent boundary.
  Local speech and SentenceTransformer embeddings share ResourceManager admission.
- Desktop click/type is implemented with the existing semantic Windows UI
  Automation service, rather than introducing global coordinate/key injection.
  This preserves exact process, HWND, window-title and control identity, permission,
  target-state digest, approval, action-count and Stop boundaries. Single-line
  Unicode replacement uses ValuePattern.SetValue directly; passwords, read-only
  fields, Enter/shortcuts and arbitrary coordinates are unsupported. The owner
  explicitly permits an executable for this process and selects a control; each
  invocation/replacement needs exact approval. Native Agent tools delegate to that
  same approval/service, without internally approving or double-consuming it.
  Operator remains paused by default; existing owner-edited profiles are preserved.
- Private Brain use is opt-in per message, with exact excerpt/digest preview before
  model submission and actual-record highlights after retrieval. Raw history retains
  only the user request and response. Native history omits oldest completed pairs
  when needed to fit the existing byte cap. The explicit local reply selector allows
  30/60/90 seconds only with model-runtime management authority; total-turn/token
  limits remain unchanged. Markdown tables retain headers/rows and bounded adjacent
  source prose. A private/native 4 KB excerpt budget replaces the legacy 1.8 KB
  excerpt budget; owner/revision/expiry/digest checks remain in place.

Evidence collected on this PC on 2026-10-26–27:

- `tools/qt_runtime_check.py`: visible Qt + real local `qwen3.5:4b`, weights digest
  `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
  Exact YouTube destination reviewed and cancelled; no browser launched. Model
  proposed calculator `17 * 19`, waited for approval, observed `323`, then answered.
  Proposal 7,173.38 ms; total 11,452.30 ms including automated approval, three
  operations. Raw-history read verified through the owning workspace header.
  Generated JSON/screenshots: `task226-review/source-runtime-check.json` and PNGs.
- Seven deterministic public-web network-boundary tests passed.
- Twenty focused shared-resource/native-Agent/tool checks passed after restoring
  independent Agent allocation isolation.
- Two authenticated HTTP integration tests passed against a fake TCP Ollama,
  including explicit context options, real role messages, owned raw history and
  missing-window/tool-capability rejection.
- Initial full Python run: **1,581 passed, 28 failed, 3 skipped**, 253.26 seconds.
  The shared-allocation regression and absent-runtime assumptions in small
  embedded apps were fixed. Native headers remain rejected when no native runtime
  exists. The affected 65-test sweep subsequently passed. A fresh full run is
  subsequently completed below; the initial failing run is not accepted evidence.
- Fresh full Python run after the fixes: **1,611 passed, 3 skipped**, four warnings,
  239.54 seconds (`task226-review-full-python-recheck.log`). The three skips remain
  Windows symlink-privilege limitations. Legacy browser modules **295 passed**,
  Electron source tests **44 passed**, public documentation tests **23 passed**.
  These counts also precede the capture/RAG/desktop work above and are not final
  acceptance for current source. They precede Task 227 port/retirement accounting
  and do not establish
  packaged Electron or Python verification.
- Real two-window source check (`tools/qt_queue_check.py`): the second Qwen
  request was observed waiting while the first window used local Nomic embeddings.
  Cancelling the waiting window took 436.37 ms; its conversation retained zero
  messages, Resume advanced generation to 1, no action replayed and the first
  window finished. Final shared queue was empty. Generated evidence is
  `task226-review/source-queue-check.json` and `two-window-queue.png`.
- Source capture/HTTP/Qt adapter, local-vision, speech/resource and preview tests
  passed in focused runs. No physical camera/microphone capture, live Whisper
  transcription or real clipboard modification is claimed. Qt Multimedia requires
  Addons at runtime; final packaging must audit the actual Qt/FFmpeg components and
  exclude unused WebEngine/GPL-only modules. See the Qt documentation for
  [in-memory capture](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QImageCapture.html)
  and [audio source stop](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QAudioSource.html).
- `tools/qt_desktop_action_check.py`: real authenticated source API, Windows UIA
  and a disposable application-owned Win32 fixture, never an existing user app.
  Exact Unicode replacement was independently read back; the approved button's
  counter advanced once. API receipts correctly retain an unverified application
  outcome even when dispatch succeeds. Initial real run exposed an existing
  `tuple(RECT)` TypeError that fake backends did not cover; fixed to explicit
  rectangle fields. Each COM-using worker initializes its apartment. Generated
  evidence: `task226-review/source-desktop-action-check.json`, desktop screenshot;
  18 Qt/scoped-desktop regressions and the native delegation regression passed.
- Frozen Task 224 source-retrieval rerun: seven real-document inputs, **39 current
  table-aware chunks**, ten unchanged questions, installed Nomic digest
  `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`.
  Prefixed semantic at threshold .35: recall@5 **.70**, MRR **.650**; same source,
  chunker and threshold with BM25/RRF (k=60): **.80**, **.675**. This is expected-
  source retrieval, not held-out tuning or answer accuracy. Earlier Task 225
  36-chunk measurements remain unchanged and are not a like-for-like comparison.
  Tool: `tools/native_hybrid_check.py`; JSON: `task226-review/hybrid-comparison.json`.
- **Real private-Brain answer check is still failing.** Same 9,006-byte repository
  document (`review/task-223-qt-shell.md`, SHA256
  `7c5323144883f3137db7f9ccf96a7bd856950354b764d7ec6d18db733e073552`),
  same question: “Which UI toolkit won the comparison, and how many nodes were
  tested?” Qwen repeatedly omits 300 nodes, sometimes omits citations or confuses
  FPS with milliseconds, even after the approved excerpts contain the complete
  table. An observed reply took **23,512.48 ms** with the explicit 60-second
  limit and still fails the unchanged factual/citation assertions. Earlier failures
  include irrelevant retrieval, the 30-second deadline and incomplete table context;
  each has a distinct retained failure JSON/log under `task226-review/`. Retrieval
  and transport fixes do not establish answer quality. No successful answer or
  quality improvement is claimed. Tool: `tools/qt_brain_chat_check.py`.

Final source acceptance and retained limitations:

- Full Python on the final runtime/Qt source: **1,646 passed, 3 skipped, 4 warnings,
  310.20 seconds** (`task226-review-full-python-stop-final.log`). The three skips
  are the existing Windows symlink-privilege limitations, not failed functional
  checks. Previous full run: 1,640 passed / 2 failed / 3 skipped; both obsolete
  expectations were repaired: the bridge now returns a real context trace and an
  interrupted provider stream becomes failed, rather than remaining pending.
- Final retained legacy source suites: browser modules **295 passed**, Electron
  **44 passed**, documentation **23 passed**. Python documentation-integrity and
  diff checks passed. These 362 Node-run cases are the explicit before-retirement
  inventory for Task 227, not packaged Electron evidence. No coverage was removed.
- A new adversarial write test first failed because model wording claimed extra
  actions after one approved write. Final reports after side effects now use the
  authoritative receipts, excluding unperformed actions. The targeted Agent/
  broker/HTTP gate passed ten tests. Read-only math can retain model explanations
  alongside actual tool observations.
- Two keyboard Stop regressions were reproduced before the fix: child dialogs
  did not route to their chat, and Settings did not receive global Stop. Stop now
  follows the owning dialog chain; Ctrl+Shift+. works app-wide and repeated Ctrl+.
  always stops, never resumes. Resume remains an explicit control. The 14-test
  Qt Stop/capture/desktop/Brain-preview gate passed.
- Closed private previews clear their widgets and schedule deletion. Finished Qt
  capture adapters release their image/device objects after actual stop. Image
  cleanup failure cannot mask a received response or cause automatic resubmission;
  it is reported while backend attachment expiry remains in force.
- Native requests use temperature 0 by default and present selected chunks of one
  source in document order. Selection is still relevance-based; over-budget native
  chunks are omitted whole rather than severing table rows. The unchanged table
  question still failed after these changes (30,188.09 ms, omitted 300); this is
  retained as a failed quality probe, not relabeled a passing test.
- A broader real API measurement used the seven frozen real-document inputs and
  ten unchanged questions, with one independent conversation per question. All ten
  replies completed, **9 contained the expected named fact, 9 used valid citation
  markers, 7 cited the canonical expected source**. Named-fact token matching is
  not full semantic accuracy. Manual content review found a missed ChromaDB source,
  unnecessary CSRF hedging and an unsupported historical Pillow failure cause.
  Exact initial excerpt content was not serialized in this first ten-answer
  report, so its citation counts do not establish support for every claim; future
  runs record previews. Baseline rank/mode metadata is separately labeled and
  current expected-source ranks are computed from the actual selected sources.
- Scope/authority/history/queue/Stop/adapter contracts are source-verified; the
  additional quality failure is not a transport or permission pass. Physical
  camera/microphone, live local Whisper, real clipboard modification, assistive
  technology and installed artifact remain **Unverified**. Full source hashes and
  the answer/retrieval measurements are retained in adjacent JSON evidence.

Task 227 is next: descriptor-only restore, screenshot/dead-control matrix,
coverage port/retirement accounting, Python packaging/installer/update checks,
packaged smoke/performance measurements, static documentation tooling conversion,
and Node/Electron/Next.js removal only after parity. Model-quality limitations
remain visible in that final report. No tests are retired by Task 226.

# Task 227 — Python packaging and Node retirement

Local Windows evidence, 28 October 2026. No push, deployment, signing or public
release is authorized. Local checkpoint: `task-227-no-node`; the final committed
artifact's exact identity is recorded in the local build/smoke output.

## Delivered behavior

The main shell uses PySide6 in one Python process. A second launch activates the
existing process and opens a separate chat window. Settings and Advanced focus
their existing windows. Window descriptors restore without saving drafts,
messages, pending approvals or executable actions. Retained history remains
read-only; expired or unretained conversations open empty. No model substitution
or action replay is introduced.

Chat, the shared real-data Brain widget, bounded Agent tools, Settings and Advanced
launching precede removal of Electron/Next.js sources. The final application and
build use Python, PySide6, PyInstaller and Inno Setup. Python CDP adapters use an
installed Chromium browser for explicitly authorized browser operations and tests;
they require no Node, Playwright or WebGL. Existing permission, exact approval,
consent, ownership, resource allocation and Stop layers remain in place.

The 111 retired tracked files and their hashes are recorded in
`task-227-retired-files.json`. Generated legacy artifacts in the main checkout
will be preserved separately during the final merge, rather than deleted with
source. The five pre-existing native-desktop work-in-progress paths are excluded
from this change.

## Verification and coverage

| Check | Observed result |
| --- | --- |
| Full Python runtime suite | 2,003 passed, 3 skipped, 4 warnings; 424.21 s |
| Final entry-point regression suite | 8 passed; startup failure exit status propagates |
| Final docs/coverage/no-Node/entry checks | 57 passed, 1 warning; 27.39 s after roadmap regeneration |
| Native action sweep | 52 selected tests passed; 76 distinct created actions activated; zero recorded gaps |
| Screenshots | 18 widget.grab baselines: dark/light, 100/125/150% Qt scale, three sizes |
| Source process restore | Two windows restored; zero protected-operation attempts with fail-closed sentinels |
| Packaged restore | Second launch exits 0; two windows share one UI/backend PID; singleton dialogs; unsent draft absent after restart |
| Installer | Actual isolated review install/uninstall; visible chat; real descriptors and data sentinel retained; legacy-folder mixing rejected |
| Python browser boundaries | 17 passed, including real HTTP tripwires, exact approved POST, blocked workers/popups/WebSockets and offline resources |
| Static browser journeys | Python/CDP sign-in, chat, close/logout and public-page checks passed |

The three full-suite skips require Windows symbolic-link privileges unavailable
to this account. The screenshot matrix uses separate Qt scale processes; the
physical display clamps some large high-DPI windows. This is not certification
at three separately configured Windows display settings or assistive-technology
certification.

Before migration, the separate Node suites contained **362 cases**: 295 browser,
44 Electron and 23 docs. Every case has an explicit mapping or retirement reason
in `task-227-coverage-migration.json`. Of the 295 browser cases, 284 preserved
contracts run under Python/CDP and 11 obsolete 3D-renderer cases are retired.
Useful model, permission, provenance and list behavior remains covered. The
preserved JavaScript fake-DOM assertions are not misrepresented as physical UI
tests. Electron-only bootstrap, installer and obsolete shell behavior has explicit
replacement or retirement records. The old Python desktop-runtime file's 12
cases became three retained security cases and nine documented obsolete cases.
The full-suite count includes Python-collected migrated cases; these numbers must
not be added again to the full-suite total.

## Measured local artifact

Parity-review executable:
`dist/native/20261028-020053-883c9299/ERSELMETZ-AI/ERSELMETZ-AI.exe`.
Its stamp identifies base commit
`977b738e58cf50bcc16077e7921c49cc2b35ca8b`, source digest
`883c9299d322544d1d53227c7039bac235867a76a5fc43245b163786379677e5`,
and `review_build: true`. It is not a clean committed release artifact.

| Measurement | Result |
| --- | --- |
| One-folder bytes | 161,836,637 |
| Visible, accessible chat startup | 4,765.47 ms |
| Working set after idle | 178.85 MiB |
| Child processes at idle | 0 |
| Node/Playwright forbidden artifact entries | 0 |
| Isolated unsigned review installer | 54,539,851 bytes |
| Shared Brain, 300 real tracked chunks | 142.93 uncapped repaint FPS; mean 7.00 ms, p95 7.73 ms |
| Shared Brain, 2,000 real tracked chunks | 23.58 uncapped repaint FPS; mean 42.40 ms, p95 47.10 ms |

Brain measurements are CPU/event-loop QPainter repaint throughput at 880×680,
DPR 1 on this RX 570 PC, not GPU-present FPS. The production timer caps animation
at approximately 30 FPS. The pre-223 Qt/Tk spike was completed before that phase's
commit: Qt 81.83/13.58 FPS and Tk 41.53/6.44 FPS at 300/2,000 synthetic nodes.
Qt had smoother antialiasing/glow; Tk used coarser overlapping circles. Those
fixtures differ from the current real-chunk benchmark, so they establish no
direct before/after performance gain. See Task 223 and 224 evidence.

Earlier Node-free review artifacts also passed real qwen3.5:4b chat and an
approved Agent calculator turn (17×19 → 323), exact YouTube cancellation and an
actual approved browser handoff. The handoff receipt says only that the default
browser accepted the URL; page loading remains unverified. The QA browser used a
fresh owned profile and a process-local override, without changing Windows
defaults or attaching to the owner's browser.

The final parity artifact also opened Preferences through Advanced in a fresh
owned Chrome profile. The browser's protected API returned 200; a separate
unauthenticated request was denied. No cookie, CSRF value or launch ticket was
read into the report. Ticket expiry/replay remain separately source-tested.

## Fresh real-model measurements

Five frozen real repository files (21–7,697 bytes) and a selected folder containing
two real files produced 39 chunks. Retired files are recovered from the fixed
Task 223 Git commit, with exact original Windows-checkout SHA-256 validation;
the corpus is not silently replaced with easier documents after source removal.
Ten current qwen3.5:4b answers completed: **9/10 named-fact token matches, 9/10
valid citation-marker replies, 7/10 expected-source citations**. The vector
database question incorrectly said no database was found. These are reproducible
limited checks, not a semantic accuracy score or proof that every claim is cited.

At threshold 0.35, nomic-embed-text source recall@5 was **0.80 without prefixes
versus 0.70 with prefixes**, with MRR 0.80 versus 0.70. This measured regression is
retained. In the separate prefixed semantic/hybrid comparison, recall@5 was
**0.70 versus 0.80**, and MRR **0.650 versus 0.675**. Questions/thresholds were not
held out; no general improvement claim follows. Both arms used current chunking.

Real qwen Agent checks used the existing appropriate profiles: Coordinator for
calculator failure, Researcher for the localhost public-reader tripwire, Developer
for an explicitly permitted injection-file read. Division by zero returned a
failed receipt. The reader received exact inline approval but blocked localhost
before any tripwire request. The injection file's browser instruction caused no
browser tool execution; the only receipt was the permitted file read. Streaming
Stop was issued after an actual model chunk and the worker returned in 35.74 ms.
The initial QA script incorrectly used Coordinator for Researcher's reader;
the existing allowlist denied it. The script was corrected to select the right
profile, without broadening any profile or permission. Its earlier refusal and
denial logs remain local evidence. Real checks are source API checks, separately
identified from packaged UI journeys.

## Architecture, updates and licensing

Task 223 evaluated an in-process service facade versus the existing loopback HTTP
API and retained the latter: it reuses the same authenticated application-service,
permission, approval, consent and spend boundaries. Existing Advanced pages remain
Python-served on loopback, with a 30-second one-use launch ticket exchanged for an
HttpOnly SameSite session cookie. No Advanced page is rewritten as a native shell
page. Source regressions prove expiry/replay/session denial; packaged dialog
launching and the measured Preferences journey do not certify every Advanced page.

Updates remain opt-in, with trusted-manifest signature and installer hash checks;
there is no startup update request, automatic download, signing or publishing.
Deterministic trusted-release tests establish those contracts; no new signed
public update has been published. Frozen inner/outer build stamps must match.
Failure metadata is bounded and local only: categories and stage, without chat
text, secret material, stack traces, paths or upload.

PySide6 is used under its LGPL option. Preserve copyright/license notices,
dynamic-library replacement and the recipient's LGPL rights, including applicable
reverse-engineering rights for debugging library modifications. Provide the
required corresponding library source or a legally valid source offer and build
information when distributing. See [Qt's LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations)
and [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).
The bundle carries LGPL/GPL texts, copied installed-distribution notices and an
exact third-party source index. Actual FFmpeg DLL exports report LGPL 2.1 or later,
without `--enable-gpl` or `--enable-nonfree`; only the five intended Qt DLLs are
included. This local inventory is not a completed public-distribution review or
source offer. The repository must distinguish its owner-selected application
license from third-party licenses and must not assert exclusive rights over those
dependencies. No application license is selected on the owner's behalf.

Public docs now use JSON plus a Python-generated static module and an allowlisted
Python preview server. Static-host configuration requires no Node build. Local
checks do not prove that the unchanged live ai.erselmetz.com deployment changed;
no deployment was performed.

## Honest limits

Physical microphone/camera/speaker, clean separate Windows accounts, live Gemini,
assistive technology and representative-owner studies remain unverified. Fake
providers establish contract behavior only. The optional Pillow image editor is
explicitly unavailable in the frozen app: spawning its Python worker would launch
the GUI executable again, and decoding in-process would discard its hard timeout.
Source-mode isolated editing and reviewed image attachments/captures are separate.

Real question-answer measurements are token/citation checks, not full semantic
accuracy. Task 226's unchanged table question still failed to include the required
300-node fact despite complete context; that quality failure is preserved and
must not be reported as perfect retrieval or answer accuracy.

## Reproduction and checkpoint

Use the repository virtual environment's Python. The full-suite command was
`python -m pytest`; the final targeted run selected public-doc/browser/integrity,
no-Node, coverage-migration and native-build-stamp tests. Run
`python tools/generate_docs.py --check` to verify the generated static roadmap.
The native action run uses `tools/qt_action_audit.py` as a pytest plugin with
`--qt-action-report`; screenshots use `tools/qt_screenshot_matrix.py`.
`tools/native_prefix_check.py`, `native_hybrid_check.py`,
`native_brain_answers_check.py` and `native_safety_check.py` accept `--output` and
require the already-installed local models. No download or paid call is implied.

`tools/build_native.py` refuses an uncommitted final source tree; `--review`
explicitly marks parity artifacts. `tools/smoke_native.py --require-no-node`,
`audit_native_artifact.py`, `packaged_chat_check.py`, `packaged_browser_check.py`,
`packaged_restore_check.py` and `packaged_advanced_check.py` establish the separately
named journeys. `tools/build_installer.py` requires an explicit Inno compiler.
`tools/installer_smoke.py` installs only the isolated review AppId and never
overwrites an existing review installation. Exact artifact stamps and measured
results are in `task-227-real-evidence.json`; LF-normalized source hashes and the
retired-path list provide the review handoff.

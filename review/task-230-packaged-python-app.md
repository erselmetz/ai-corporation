# Task 230 - local packaged native Python app

Date: 2026-10-29, Asia/Manila. LOCAL ONLY: no push/deploy, certificate purchase, signing or public release. This is an unsigned local build, not a signed production release.

## Outcome and verification boundary

The native Task229 Python app is packaged as a windowed PyInstaller one-folder application with a per-user Inno installer. Real current-user installation, first-run chat, automatic installed-model selection, native Settings/About, approved external URL, three-file Brain intake, restart, private Eyes pack installation/self-test, uninstall retention, reinstall recovery and explicit disposable-data removal were exercised.

**A fresh Windows account or Windows Sandbox was not available.** The process is not elevated and WindowsSandbox.exe is absent. A fresh app profile on the existing account is explicitly not equivalent. Clean-account/clean-machine compatibility, physical mic/camera/speakers, signed Internet-download behavior and SmartScreen reputation remain **Unverified**. Task completion here is the development/packaged checkpoint with those coverage limits, not clean-account certification.

## Compatibility and optional packs

The [pre-code report](task-230-toolchain-and-packs.md) was written before changing application/build code. Exact official release metadata is preserved in [wheel evidence](task-230-wheel-compatibility.json). CPython3.14.7 Windows x64, PySide6 Essentials/Addons/shiboken6 6.12.0, PyInstaller6.22.3 and all39 audited package versions have compatible wheels. Optional pinned filenames, sizes and SHA-256 values matched official metadata. No Python downgrade or unsupported-version decision gate was triggered. Nuitka was not installed/selected.

Chosen option: private per-user, ABI-matched, hash-verified wheels through the existing owner-confirmed preview; no pip resolver, source compilation, .pth execution or separate interpreter. Base builds explicitly exclude optional image/inference libraries. Compared alternatives and download sizes are in the pre-code report. Availability of wheels is not frozen execution proof for the untested Ears/Voice/FAISS packs.

Eyes was actually installed through the frozen app's native preview/confirmation UI with manifest `1ac7f211694df42df6cd788fece5c1d0515dce9d87cb52cd68bd7ca1b3988c2e`. The in-app self-test successfully imported required Pillow, mss, OpenCV, NumPy and pytesseract modules. It reports **installed**, not OCR-working: Tesseract is not on PATH and its executable/language data are separate. No screen/camera/microphone data was captured to establish this result. Physical media and OCR remain Unverified.

## Implementation

- Retained one-folder `--onedir --windowed` PyInstaller, exact inner/outer build-stamp checks, Qt-only plugins and no app HTML, Node, browser engine or default listening API.
- Added native About showing version/commit/review identity and bounded `native-events.json`. Application event/failure records accept only whitelisted metadata; no arbitrary prompt, file path, exception text or secret fields. Existing local-only failure handling remains.
- Installer uses `PrivilegesRequired=lowest`, per-user Start menu shortcut/data and a separate Review install identity for safe QA. Silent uninstall always retains data. Interactive uninstall asks explicitly, default No, before removing the known data folder; linked/reparse trees are refused. No alternate/custom-profile directory is recursively removed. Default installer setup logging is disabled; no app telemetry is uploaded.
- Added isolated clean-source QA installer support (`--isolated`) so final-source EXE bytes can be installed/tested without replacing production registration/shortcuts/data.
- Hardened smoke checks for PE GUI subsystem, real accessible chat within60 seconds, alive after2 seconds, no app-PID LISTENING entries, no browser/console child and no Node artifacts.
- Added native UIA journey and safe installer retention/removal checks; no backend test endpoint or frozen QA bypass was introduced.
- Fixed a discovered UI defect: automatic list refresh erased action results, including pack self-test failures. Results now stay visible, and the selected record is retained. A regression checks that a failed self-test remains failed even when inventory says installed.

[Unsigned/SmartScreen notes and signing plan](../packaging/SIGNING.md): downloaded unsigned files may show an unrecognized-app/unknown-publisher warning or be blocked by policy. No protection was disabled and no signature was faked. Local builds without Internet marking do not prove SmartScreen reputation.

## Real current-user checks

| Check | Result |
|---|---|
| Silent Review install into owned temporary location, no elevation, separate Start menu shortcut | Packaged-verified |
| Windowed GUI, straight to chat, auto-selected installed qwen3.5:4b, hello reply | Packaged-verified / Verified real on this Windows account |
| Native Settings and About version/commit equal installed stamp | Packaged-verified |
| Additional genuine local model reply | Verified real;12,394.92 ms; hello itself is shipped exact-match guidance and is not counted as inference |
| Three real files: root README, packaging README, requirements.txt | Verified real;7/7/1 saved chunks,15 total; file sizes/hashes in evidence |
| Exact https://www.youtube.com/ preview and one approval | Verified real browser handoff; page loading not claimed |
| Eyes private-wheel owner preview/install and self-test inside frozen EXE | Packaged-verified imports; OCR/hardware Unverified |
| Silent uninstall retains windows and real Brain data | Packaged-verified; window bytes unchanged and15 Brain rows retained |
| Reinstall/restart recovers data | Packaged-verified; same Brain content hash and native list shows recovered files |
| Explicit interactive remove-data option | Verified real only against marked disposable Review data; production data never targeted |
| Fresh Windows user / Windows Sandbox | Unverified; unavailable in this session |
| Ears/Voice/FAISS frozen execution; mic/camera/speakers | Unverified |

Review artifact used for the UI journeys:
`dist/native/20261029-005209-15685a42/ERSELMETZ-AI/ERSELMETZ-AI.exe`.
It is correctly marked review, parent commit67f07ec, source digest15685a425e4fe288e8adef3dae38b2361a9fbb11c716f31af62d04102992978d. It is not falsely described as the final clean-source commit.

## Measurements and netstat

| Measurement | Actual value / boundary |
|---|---|
| Review installer |54,449,592 bytes (51.93 MiB) |
| Review one-folder base payload |161,187,419 bytes (153.72 MiB), excluding optional packs/data and installer-generated uninstaller |
| First frozen process + fresh profile visible-chat confirmation |11,858.59 ms; process remained alive;60-second deadline |
| Initial idle working set |176.86 MiB |
| After three-file Brain intake |220.34 MiB |
| Frozen Eyes self-test working set |212.70 MiB |
| Default app TCP listeners |0 |
| Default startup children / Node files / WebEngine binaries |0 /0 /0 |

The first-process startup is a fresh app profile, not a cold reboot: OS file caches were not flushed. Measurements during competing UI tests are not substituted for this controlled startup value. Final clean artifact/installer sizes and smoke timings are recorded separately in the local final artifact record after the exact commit is created.

```text
Command: netstat -ano
App PID:6620 (first frozen smoke)
LISTENING entries for app PID:
(no matching entries)

Installed frozen pack self-test PID:8324
Installed frozen local-model PID:4092
LISTENING entries for either app PID:
(no matching entries)
```

Ollama's own port11434 belongs to its separate service; it is not an app listener. Browser handoff was allowed only after the explicit tool approval, separately from default startup.

## Checks and evidence

- Full Python suite: **1751 passed,3 skipped,4 warnings,495.21 seconds**. Skips are the existing three Windows symbolic-link privilege cases; warnings are existing Starlette/Qt deprecations.
- Final native/build/installer affected suite: **24 passed,1 warning,21.43 seconds**.
- Final public docs/browser/integrity checks: **47 passed,22.68 seconds**.
- Earlier result-retention regressions:11 passed; earlier packaging focused checks21 passed. Counts overlap; do not add them as a larger suite.
- Existing18 native screenshot baselines retained and passed; no rebaselining.
- Actual Inno compilation, unsigned signature inspection, source generation/UTF-8/diff checks and real packaged smoke/journeys. Compiler signature verified; application/installer remain unsigned.

QA harness issues were repaired rather than called app defects: native modal windows appear as UIA children; file-picker buttons share names; file input uses the real dialog's keyboard path; Qt's virtualized list needs scrolling and Windows paths are case-insensitive. Screenshot capture is isolated from the UIA controller's COM initialization. The actual result-refresh defect was fixed in product code. No test was weakened into a skip or permission elevated to pass.

Structured committed [evidence](task-230-evidence.json) records exact review identities, measurements and limitations. Raw QA outputs/screenshots stay local under `task230-review/`. Examples: [native About](../task230-review/installed-basic-retry/about.png), [exact URL approval](../task230-review/installed-basic-retry/url-approval.png), [Brain intake](../task230-review/installed-feed-three/brain-fed.png), [frozen pack self-test](../task230-review/installed-pack-result/pack-self-test.png).

A clean-source one-folder build and both normal/isolated installers are produced **after** the one Task230 commit so their embedded commit is exact. Their final hashes, installed size, netstat and smoke/retention results are recorded in `task230-review/final-artifact.json`. The local tag `task-230-packaged-python-app` is created only after that final artifact gate passes. No source edit, push or deployment follows the verified checkpoint.

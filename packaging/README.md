# Native Windows packaging and recovery

The declared candidate version is read from the repository-root `VERSION` file.
For this source it is `1.0.0-rc.1`; `tools/build_native.py --version` rejects a
different value so the executable, installer and About identity cannot drift.

The application is a PySide6 shell and an authenticated in-process policy facade in one
Python process. It does not require Node, npm, Electron, Next.js, Playwright or
an embedded browser. Advanced windows are native Qt. The default app starts no TCP
listener and dispatches guarded application operations in-process.

## Build locally

Use the project Python environment and install `requirements.txt`,
`requirements-desktop.txt`, and `requirements-build.txt`. No model is downloaded
by these scripts. Install an Inno Setup compiler separately and verify its source
and signature before using it.

```powershell
.\.venv\Scripts\python.exe tools\build_native.py
.\.venv\Scripts\python.exe tools\smoke_native.py <one-folder-exe> --require-no-node --output <local-report.json>
.\.venv\Scripts\python.exe tools\build_installer.py <one-folder-directory> --compiler <ISCC.exe> --output <new-output-directory>
```

Final builds require committed source. `--review` explicitly permits an
uncommitted review artifact, adds its source digest and review marker, and uses a
separate installer identity with no production shortcut. Review installers are
not releases. Every build uses a new output directory and preserves prior output.

The executable requires matching inner and outer build stamps. Missing,
malformed or mismatched stamps fail closed. Keep `build-stamp.json` beside the
executable and the complete `_internal` folder; do not copy only the EXE.

The Qt GUI hook collects the Windows platform and required image plugins. Unused
PDF, virtual-keyboard, QML/Quick, WebEngine and other add-on modules are excluded.
Audit each resulting artifact rather than assuming installed SDK contents match
the bundle. `THIRD_PARTY_NOTICES.md` states the LGPL and source obligations.

## Installation, data and updates

Installation is per user under `%LOCALAPPDATA%\Programs\ERSELMETZ AI`.
Application data remains separate under `%LOCALAPPDATA%\ERSELMETZ AI`; SQLite is
in `projects\ai_corporation.db`. Uninstall keeps that data by default. Interactive uninstall offers an explicit, default-No remove-data choice; silent uninstall always keeps data. Linked/junction data trees are kept rather than followed. A local
review installer uses a separate AppId and install directory.

Owner locks remain enforced on launch. Native in-process sessions never transfer
authority to a browser. No launch tickets or app HTML are bundled. Cloud consent, permissions, exact-action
approvals, resource limits and emergency stops remain backend requirements.

Saved windows contain selection identifiers, titles and geometry only. Restart
does not replay messages, tools, model calls or captures. Retained conversation
history opens read-only; unavailable or unretained conversations open empty.

Update checks are owner-triggered from Advanced → Updates, never automatic at
startup. The existing pinned-origin signed-manifest and installer-hash checks
remain required; preparing an update requires separate management permission and
creates a recovery backup. No signing key, published installer or release is
created by a local build. An unsigned local installer is not a verified update.

Startup failure records are local and bounded to twenty whitelisted records.
They contain timestamps, stages and categories, not messages, stacks, file paths,
chat content or secrets. Review-only startup logging is opt-in QA instrumentation
and is absent from clean final builds. Nothing is uploaded automatically.

## Recovery

Use Advanced → Backup before changing application data. Keep existing backups
and prior artifacts until the replacement has been verified. Do not delete the
data folder to repair a missing provider or model. Start Ollama separately and
choose an installed local model; there is no silent fallback or automatic model
installation.

The optional source-mode Pillow image editor uses a separate, time-limited
decoder. It is deliberately unavailable in this single-process native bundle;
the package does not relaunch its GUI EXE as a decoder or drop that hard timeout.
Ordinary image attachments and consented one-shot capture/transfer remain separate
features. Optional local inference/speech stacks are not silently downloaded or
presented as verified when absent.

The local `legacy-electron-ui` tag preserves the old source. Restoring that tag
requires its old development dependencies and does not make its superseded
packaged-startup blocker fixed. It is a recovery reference, not the current build.

Task 230 produces new local one-folder artifacts from the native Task 229 source.
Older Task 227 artifacts retain their historical browser implementation; do not
confuse them with the new build. See the Task 230 report for exact artifact identity.

The native About window shows the checked version and source commit. Bounded
`native-events.json` and `native-failures.json` in the app data folder contain only
whitelisted timestamps, event/stage categories and build identity; no prompt,
path, exception text or secret is accepted. Nothing is uploaded.

Optional Eyes/Ears/Voice/FAISS packs use private per-user folders and exact
CPython 3.14 Windows x64 wheels with the existing owner digest/SHA-256 preview.
No pip invocation, dependency resolver, source build or embedded second Python
is launched. They are excluded from the base build. Frozen imports/DLLs are
verified per pack; successful Eyes loading does not certify audio hardware.
See [unsigned builds and signing plan](SIGNING.md).

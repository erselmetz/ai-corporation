# Windows desktop package

## Supported target and distribution boundary

| Target or mode | Current status |
| --- | --- |
| Windows 11 x64 per-user NSIS installer | Local acceptance-tested target only; not a signed or publicly supported release |
| Windows 10, Windows ARM64, macOS, Linux, portable archives, and app stores | Unverified and not currently supported or claimed |
| Repository-based Python CLI and Task 126 launcher | Separate development entry points; neither is managed by the Electron installer |

Task 129's clean-install evidence applies only to Windows 11 x64 and the exact
local artifact `desktop/release/task129/ERSELMETZ-AI-Setup-0.1.0-win-x64.exe`
(SHA-256
`206A36D5C94FD76B2696C01F95CD842C24E3A79FD05FEB7FDB45F3DA101DC091`). That
ignored local artifact is not a public download or an update feed. The installer
is unsigned by Windows Authenticode, so Windows may display an unknown-publisher
warning. Task 167 adds in-app Ed25519 verification of a fixed GitHub Releases
origin and signed artifact digest; this does not provide Authenticode publisher
identity or mean that a public release has been published.

The packaged installer is per-user, does not request elevation, creates Start
Menu and Desktop shortcuts, and does not start the app after installation. The
build requires a Windows x64 checkout, Python 3.14 x64 in the repository's
`.venv`, Node.js 22.12 or later, network access to the pinned package
registries, and the repository's locked Python and Node dependencies. The
installed app uses Windows current-user DPAPI and loopback services; other OS
targets have not been evaluated for those behaviors.

There is no automatic updater or background release polling. The protected
Updates page checks only
`https://api.github.com/repos/erselmetz/ai-corporation/releases/latest` after the
owner selects **Check for release now**; this is a one-check opt-in and is not
persisted as a recurring subscription. It verifies a detached Ed25519 signature using the
public key pinned in the app. The owner can explicitly prepare a newer
compatible signed Windows x64 installer; the app rechecks its SHA-256, creates
a verified SQLite online backup, and saves the installer under
`%LOCALAPPDATA%\ERSELMETZ AI\updates`. The owner closes the app and runs the
installer manually. Release notes and the signed configuration migration
preview appear before preparation. No signed public release is claimed until
the owner publishes matching signed assets. The generated PEM signing key is
stored outside this repository under `%LOCALAPPDATA%\ERSELMETZ AI\release-signing`.
It is unencrypted at rest; its directory ACL is limited to the current Windows
user and SYSTEM. Keep an encrypted offline backup and rotate the key if this
profile is exposed. A recovery backup covers only the application
SQLite database. Reinstalling a previous installer and restoring data are
manual; compatibility with a prior version after a future schema migration is
not guaranteed. Task 129 verified reinstall of the same local version and
preservation of the owner verifier.
To repeat owner setup, remove only
`%LOCALAPPDATA%\ERSELMETZ AI\owner-credential.dpapi`; this leaves app data
in place. Back up and remove remaining app data separately only when the owner
intends a full reset.

Task 127 adds a per-user Electron installer for Windows x64. It opens the
existing FastAPI application on `http://127.0.0.1:8765`; the Next.js UI is a
static export mounted at `/desktop/`. There is no production Next.js server,
external font/CDN dependency, or public documentation-site connection. Existing
Python APIs and chat/provider pages remain the source of runtime behavior.

## Build

Build from a Windows checkout with Python 3.14 x64 and Node.js 22.12 or later:

```powershell
npm --prefix desktop-ui ci
npm --prefix desktop-ui run build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File desktop/scripts/build-backend.ps1
npm --prefix desktop ci
powershell.exe -NoProfile -ExecutionPolicy Bypass -File desktop/scripts/build-installer.ps1
```

The build packages the existing Python environment using the pinned PyInstaller
build tool and creates `desktop/release/ERSELMETZ-AI-Setup-0.1.0-win-x64.exe`.
The NSIS installer is per-user, unsigned, does not request elevation, creates
Start Menu/Desktop shortcuts, and does not launch the application after install.
This output is for local development/testing. Windows may show an unsigned-app
warning. Distribute a signed build only after establishing an owner-controlled
signing and release process.

The installed Electron main process starts the Python sidecar, which binds only
to `127.0.0.1:8765`; it serves both `/api` and the static `/desktop/` export
from that one origin. A port or ownership conflict fails closed. Close the
desktop window to request graceful backend shutdown. The command-line and
Task 126 Python launchers remain separate entry points and are not managed by
this Electron controller.

## Owner access and stored data

On first launch, create and confirm an owner password of 12–1024 characters.
The existing credential store protects only its salted verifier with Windows
DPAPI for the current Windows user. The password is passed to the Python sidecar
over its private standard-input pipe; it is not put on a command line,
environment variable, or persistent log. The desktop process uses that same
verified owner password with the existing local-login contract to establish the
normal HttpOnly owner session; it adds no identity or permission. Browser
sessions are cleared on app exit.

In the current source, a new desktop owner then sees the Task 176 Ollama/Gemini
wizard. Ollama installer metadata is read from the official `ollama/ollama`
GitHub release, the reviewed SHA-256 and size are checked before the installer
is run, and a native confirmation precedes download and launch. The installer
is started without elevation. The model size is previewed from the Ollama
registry manifest before the separate explicit model-download confirmation.
Gemini catalog discovery requires an explicit action; each chat turn retains
its separate cloud-consent gate. Setup metadata and the existing model
assignment/1-1-1 software slot limits are saved in SQLite. A Gemini key remains
memory-only unless the owner opts into current-user DPAPI storage. Without that
opt-in, the key must be re-entered after restart. Keys are not stored in SQLite
or included in SQLite backups. The coordinator assignment and slots are
restored on startup when saved configuration is available.

Task 176 automated validation passed: Python 1,270 passed / 6 skipped / 0 failed,
175 browser modules, 16 public docs, and 21 Electron tests. Manual clean-profile
Windows acceptance has NOT been performed: real Ollama installation/download/chat,
Gemini chat, DPAPI restart persistence, and recovery checks remain pending. This
implementation does not qualify hardware/GPU compatibility,
provider-account billing, or every Windows/Ollama environment. Gemini remains
chat-only for controlled Task dispatch; the existing Ollama-only dispatch and
Task 170 release-review boundaries remain unchanged. The general standalone
API remains fail-closed and does not mount the desktop first-run routes.

The installer does not configure automatic updates. Install a later trusted
version manually. The uninstaller asks whether to keep `%LOCALAPPDATA%\ERSELMETZ AI`;
the default Yes preserves the owner verifier and application data for a later
reinstall, while No removes that data folder. To repeat owner setup while
keeping other data, exit the application and remove only
`%LOCALAPPDATA%\ERSELMETZ AI\owner-credential.dpapi`. For a full reset while
the app is installed, use the confirmed Settings action described below.

Task 185 adds an explicit data choice in the per-user NSIS uninstaller. The
prompt defaults to **Yes, keep local data**; choosing **No** removes the fixed
`%LOCALAPPDATA%\ERSELMETZ AI` folder, including the owner verifier, database,
backups, staged update installers, and local crash reports. The installed app's
Settings page also has a separate **Reset all app data** action, guarded by the
existing `backup:restore` owner permission and a native confirmation defaulting
to Cancel. It stops the local sidecar, waits for the app process to release its
files, clears only that per-user data folder, and relaunches at first-run setup.
Export a recovery backup first if you need to keep durable records.

Handled Electron main-process failures, renderer process loss, and abnormal
backend exits may be recorded in
`%LOCALAPPDATA%\ERSELMETZ AI\diagnostics\crash-reports.json`. The report is
capped at eight records and 8 KiB, and stores only a timestamp, fixed event and
component names, bounded reason, app version, and optional bounded exit code.
It omits raw error text and stacks, prompts, credentials, provider responses,
and paths. The owner can inspect records in Settings or open the local folder;
the app never uploads them. Hard termination and power loss cannot be recorded.

The release/update trust design requires an owner-selected Windows publisher
identity and owner-controlled Authenticode certificate before any public signed
installer release. The private key must stay outside the repository; a release
must be SHA-256 signed with a trusted timestamp and verified with SignTool,
alongside the existing pinned Ed25519 manifest and exact artifact digest. The
current installer remains unsigned. No publisher, certificate, or paid account
was selected or acquired; no public signed artifact exists.

The packaged backend database is at %LOCALAPPDATA%\ERSELMETZ AI\projects\ai_corporation.db. It contains local positions, configured slot limits, short-lived proposal review metadata, and Employee conversations only when the owner explicitly selects Retain this conversation. Retained chat is unencrypted and remains until explicitly deleted from Employee Chat or the app data folder is removed. Recovered Employee conversations are read-only; uncertain turns are never replayed. SQLite schema upgrades are additive and transactional: a failed migration rolls back without advancing the schema version. The existing encrypted Backup & Restore flow can include private records only after explicit selection; use it before manual recovery or app-data removal. Active slot allocations, provider credentials, and capability grants are not persisted.

Voice controls are available only after selecting a chat conversation. Local
recognition requires a supported on-device Chromium language pack; it never
falls back to a remote service. Installing a language pack is an explicit
download action. Cloud transcription is disabled until the owner sets a
one-run ceiling, requires a separate consent for each recording, sends only a
maximum ten-second inline WAV request to Gemini, and reserves one cent per
attempt against an in-memory cap. Google pricing and account billing remain
outside the app's control; the local ceiling limits app-authorized requests,
not the provider account as a whole. Google Gemini API retention depends on the
connected account tier and settings; the app cannot configure or verify that
provider-side retention. Recordings are not stored by the app, and
the transcript is not sent to chat until the owner reviews and submits it.
Stopping a cloud request stops local waiting only; the provider may continue.
Reply audio uses an installed device-local speech voice when one is available.

The packaged service suppresses Uvicorn request/error logs; Electron does not
write passwords, requests, responses, or persistent application logs. Startup
errors presented in the desktop window are fixed, bounded messages. Diagnostic
Smoke-test profiles use temporary credentials and are removed when the test
finishes. Installer and backend build outputs remain under `desktop/release/`
and `desktop/build/` for inspection and are ignored by Git.

Task 168 adds the owner-protected **Backup & restore** page from the desktop
navigation. Encrypted backups are saved locally; private app records are
excluded unless explicitly selected. A restore creates an encrypted recovery
copy under `%LOCALAPPDATA%\ERSELMETZ AI\backups` and requires an app restart.
The passphrase is never stored or recoverable. Provider data, credentials held
outside the SQLite database, model files, and remote data are not covered.

Task 169 adds the owner-only **Performance readiness** page. It reports local
app-factory setup time, current process working-set/RSS where supported,
recorded model assignments, and prior queue claims for inspection. It does not
run a model or replay operations. Rendering evidence stays in the visualization
page; model workload and hardware fit remain UNKNOWN without measured evidence.

## Verification

Run deterministic tests with `npm --prefix desktop test` and the Python tests
`python -m pytest tests/test_desktop_runtime.py tests/test_desktop_launcher.py
tests/test_local_access.py tests/test_local_chat_browser.py`. After building the
installer, `python desktop/scripts/smoke-backend.py` exercises the frozen
sidecar; `python desktop/scripts/smoke-installer.py` installs and runs the real
NSIS package in a temporary profile, tests owner setup/sign-in, stop/restart,
uninstall preservation and reinstall recovery. These tests use no live model or
provider calls.

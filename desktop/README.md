# Windows desktop package

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
environment variable, or persistent log. Starting the service on later launches
requires the owner password, and the existing browser owner sign-in is still
required for protected pages and actions. Browser sessions are cleared on app
exit. Provider credentials and runtime state retain the existing application
lifecycle and are not made durable by this package.

The installer does not configure automatic updates. Install a later trusted
version manually. Uninstall leaves `%LOCALAPPDATA%\ERSELMETZ AI` in place,
including the owner verifier and application data, so reinstall can recover the
same profile. To reset owner setup, exit the application and remove only
`%LOCALAPPDATA%\ERSELMETZ AI\owner-credential.dpapi`. Remove the remaining
application data only as a separate, intentional Windows user action after
backup; it may contain durable app records.

The packaged service suppresses Uvicorn request/error logs; Electron does not
write passwords, requests, responses, or persistent application logs. Startup
errors presented in the desktop window are fixed, bounded messages. Diagnostic
Smoke-test profiles use temporary credentials and are removed when the test
finishes. Installer and backend build outputs remain under `desktop/release/`
and `desktop/build/` for inspection and are ignored by Git.

## Verification

Run deterministic tests with `npm --prefix desktop test` and the Python tests
`python -m pytest tests/test_desktop_runtime.py tests/test_desktop_launcher.py
tests/test_local_access.py tests/test_local_chat_browser.py`. After building the
installer, `python desktop/scripts/smoke-backend.py` exercises the frozen
sidecar; `python desktop/scripts/smoke-installer.py` installs and runs the real
NSIS package in a temporary profile, tests owner setup/sign-in, stop/restart,
uninstall preservation and reinstall recovery. These tests use no live model or
provider calls.

# ERSELMETZ AI

The native entry point now opens the **PySide6 three-pane shell** (`app.qt_desktop`, Task 223). It uses one Python process, independent chat windows and the existing authenticated loopback API. Install `requirements-desktop.txt` alongside backend requirements for source mode. Native Brain/intake, pack/math, agent/device controls and packaging/Node removal remain Tasks 224–227. Legacy sources and Python Playwright still remain until parity; the final app/build is not yet Node-free. See [Task 223 evidence](review/task-223-qt-shell.md).

ERSELMETZ AI is a local-first desktop workspace for coordinating AI providers, models, people, projects and Tasks through a Python backend and an Electron interface.

> **Screenshot placeholder:** capture the Command Center after the clean-profile Windows acceptance run.

## Install and first run

Download the Windows desktop installer from the project release page. The current installer is unsigned and is not a stable-release build; see [desktop distribution notes](desktop/README.md).

Current-source Electron builds open Coordinator Chat directly. A per-launch local session is created by Electron; if an owner password lock is already configured, it remains required. Local Ollama startup only discovers already installed models and does not download or install them. The chat page reports missing/stopped Ollama and offers the existing owner-confirmed setup actions. Gemini is optional in Settings; every cloud turn still requires separate consent, and keys stay in memory unless Windows-user DPAPI storage is explicitly enabled. Clean Windows-profile and packaged-release acceptance remains pending; an older locally generated installer must be rebuilt to include current source changes.

## What works today

- Local owner authentication, permission-checked APIs, and a loopback-only desktop backend.
- Coordinator and individual Employee chat, with explicit cloud consent for Gemini turns.
- Provider/model configuration, Task and Project management, organization and workflow maps, memory, and operator settings.
- Local SQLite persistence for corporate positions and configured slot limits; pending proposals become unusable after restart, and Employee chat retention is owner-opt-in and read-only after restart.
- Explicit local Ollama Task dispatch under its existing confirmation and capacity rules. Gemini remains chat-only for that dispatch path.
- SQLite persistence for supported configuration and Task data. Gemini credentials are excluded from SQLite and backups.

These features are scoped foundations. Provider registration, a model name, or configured software slots do not prove model quality, hardware feasibility, or successful inference.

## Known limits and roadmap status

Tasks 213–221 are superseded by the revised pure-Python Tasks 223–227; their original evidence is retained as history. Task 222 records the local stabilization checkpoint. Task 197 exists; absent Tasks 204–206 now have explicit not-done, scope-undefined records. Task 212 still has no published definition. Task 223 now has a separate Qt source checkpoint; the earlier Tk experiment remains historical. See [the roadmap](docs/tasks.html) for the current phase assignments.

The Task 222 live rerun used installed local qwen3.5:4b. Five agent-choice questions selected the expected roles (selection only, no delegated action execution). Five unchanged repository documents ingested successfully; ten questions produced ten responses, eight expected-source retrievals, seven strict fact-string matches and one inline numeric citation. RAG quality remains partial. Installed Eyes/Ears/Voice library checks did not verify OCR, recording, transcription or playback. Packaged Electron startup is superseded, not fixed; RX 570 FPS and the future Qt artifact remain unverified. See [the measured report](review/task-222-stabilization.md).

Task 208's deterministic routing, existing backend permissions, approvals, cloud consent, bounded runtime and stop controls remain in force. Tasks 134, 170, 193 and 194 remain deferred; Task 190 remains design-only and grants no code-execution authority. Historical validation is retained in task records and implementation history.

On the packaged Windows app, SQLite data is stored at %LOCALAPPDATA%\ERSELMETZ AI\projects\ai_corporation.db. Retained Employee chat is unencrypted, requires an explicit per-conversation choice, stays on this profile until deleted, and is read-only after restart. The owner can review and explicitly delete retained chat in Employee Chat; use the encrypted Backup & Restore page before manually removing the app data folder. Credentials and active resource allocations are not persisted.

The application does not provide distributed Task execution control, automatic cloud fallback, or verified GPU compatibility. Live Gemini calls, Ollama model downloads, and clean-profile Windows installer behavior are not covered by deterministic tests.

## Development

- Python backend: `app/`
- Electron desktop shell: `desktop/`
- Next.js static desktop UI: `desktop-ui/`
- Authoritative roadmap: [`docs/tasks-data.mjs`](docs/tasks-data.mjs)
- Current task pages: [`docs/tasks.html`](docs/tasks.html)
- Development updates: [`corporation_updates.json`](corporation_updates.json)
- Installer and recovery notes: [`desktop/README.md`](desktop/README.md)
- Preserved technical and task history: [`docs/implementation-history.md`](docs/implementation-history.md)

Run Python tests with `.venv\\Scripts\\python.exe -m pytest`. Run desktop tests with `npm.cmd test` from `desktop/`; build the static desktop UI with `npm.cmd run ui:build` from `desktop/`.

## License

No license has been published yet. The repository license choice requires owner confirmation.

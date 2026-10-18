# ERSELMETZ AI

ERSELMETZ AI is a local-first desktop workspace for coordinating AI providers, models, people, projects and Tasks through a Python backend and an Electron interface.

> **Screenshot placeholder:** capture the Command Center after the clean-profile Windows acceptance run.

## Install and first run

Download the Windows desktop installer from the project release page. The current installer is unsigned and is not a stable-release build; see [desktop distribution notes](desktop/README.md).

On first launch of a build made from the current source, create an owner password. The new first-run wizard offers:

- **Ollama (local):** check the loopback service, review the official installer and model download details, then explicitly confirm installation/download.
- **Gemini (online):** enter a supported API key and explicitly request the model catalog. Each cloud chat turn still requires separate consent. The key stays in memory unless you opt into Windows-user DPAPI storage.

After setup, the app assigns the existing Coordinator and opens a conversation. If no provider is ready, choose **Skip for now** and configure it later. The first-run path is still awaiting clean Windows-profile acceptance; an older locally generated installer must be rebuilt to include these changes. Hardware/GPU compatibility remains unknown unless verified directly.

## What works today

- Local owner authentication, permission-checked APIs, and a loopback-only desktop backend.
- Coordinator and individual Employee chat, with explicit cloud consent for Gemini turns.
- Provider/model configuration, Task and Project management, organization and workflow maps, memory, and operator settings.
- Local SQLite persistence for corporate positions and configured slot limits; pending proposals become unusable after restart, and Employee chat retention is owner-opt-in and read-only after restart.
- Explicit local Ollama Task dispatch under its existing confirmation and capacity rules. Gemini remains chat-only for that dispatch path.
- SQLite persistence for supported configuration and Task data. Gemini credentials are excluded from SQLite and backups.

These features are scoped foundations. Provider registration, a model name, or configured software slots do not prove model quality, hardware feasibility, or successful inference.

## Known limits and roadmap status

Tasks 1–174 are recorded as complete except Tasks 134 and 170, which remain deferred and incomplete; Task 179 is the completed public roadmap sync. Task 176 passed revised AI-run development acceptance, including isolated packaged first-run/restart/recovery smoke and current-user filesystem ACL inspection. Separate-account, real Gemini, installer/model-download, and offline-provider integration coverage remain unverified follow-up. Task 177 passed one real local Ollama retrieval/trace check, which does not establish general answer or citation quality. Task 178 passed packaged Windows native-window resize checks. Tasks 180–184 have implementation progress; Task 180 remains planned pending automated evidence review, Task 184 remains planned pending its process-boundary acceptance review, and Tasks 182–183 remain planned pending their AI-run evidence review. Task 175 completed its AI-run usability/accessibility regression evaluation; representative-owner and assistive-technology studies remain optional follow-up, and no conformance claim is made. Tasks 181, 185–189 remain planned; Task 190 is design-only. See [the roadmap](docs/roadmap.html) and [all task records](docs/tasks.html).

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

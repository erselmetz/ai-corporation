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
- Explicit local Ollama Task dispatch under its existing confirmation and capacity rules. Gemini remains chat-only for that dispatch path.
- SQLite persistence for supported configuration and Task data. Gemini credentials are excluded from SQLite and backups.

These features are scoped foundations. Provider registration, a model name, or configured software slots do not prove model quality, hardware feasibility, or successful inference.

## Known limits and roadmap status

Tasks 1–133, 135–169 and 171–174 are recorded complete in the roadmap. Tasks 134 and 170 remain deferred and incomplete. Task 175 remains planned pending representative owner and accessibility/device evaluation. Task 176 is implemented and automated validation passed; its roadmap status remains planned until manual clean-profile Windows acceptance is recorded.

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

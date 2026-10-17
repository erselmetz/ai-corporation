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

Tasks 1–174 are recorded as complete except Tasks 134 and 170, which remain deferred and incomplete. Task 177 is complete after a real local Ollama turn demonstrated the answer trace and retrieved source; this single turn does not establish general answer or citation quality. Task 178 is complete after the corrected packaged Windows app passed native-window resize checks across the Next.js and Python routes, including the narrow navigation toggle and first-run transition. Task 182's reviewed local tools and Task 183's visible chat plan/trace have implementation progress but remain planned pending manual owner checks. Task 176 remains planned pending clean-profile Windows acceptance; Task 175 remains planned until the setup journey is accepted and representative usability/accessibility evidence is gathered. Task 179 (this docs sync) is complete. Tasks 180–189 are planned; Task 190 is design-only. See [the roadmap](docs/roadmap.html) and [all task records](docs/tasks.html).

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

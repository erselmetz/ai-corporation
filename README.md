# ERSELMETZ AI

Current release candidate: **1.0.0-rc.1**. This is an unsigned, local-first
Windows release candidate, not a signed public-production release. See the
[release notes](docs/V1_RELEASE_NOTES.md), [security boundary](SECURITY.md), and
[API stability policy](docs/API_STABILITY.md).

ERSELMETZ AI is a local-first desktop workspace for coordinating AI Employees,
technical Agents, local or online providers, models, projects, Tasks and scoped
knowledge. The native three-pane shell uses **PySide6**, with one Python process
and one authenticated in-process backend, with no TCP listener by default. Each chat window has independent model,
Agent, Project and conversation selection.

## Run from source

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt
.\.venv\Scripts\python.exe native_entry.py
```

Start Ollama separately and choose an already installed local model. Startup does
not download models or call a paid provider. Gemini remains optional and requires
its existing configuration and per-turn cloud consent. An existing owner password
lock remains required. Settings and Advanced are separate singleton windows;
Advanced opens native Qt record/detail/action windows. Owner access is native;
no browser session handoff or HTML app pages remain. The explicit Open online docs
button opens https://ai.erselmetz.com only on click.

Optional OpenAI-compatible text endpoints, including **Free pool (FreeLLMAPI)**,
are configured in Provider connections. They are cloud destinations even on
loopback, off by default, and require an exact redacted outbound preview and fresh
approval. The native “Ask the free pool?” action is one turn only and keeps the
local model selection. No router is bundled or installed. See the
[separate-install guide and limits](docs/free-pool.html). Connection settings and
keys last for this process only; call/token allowances do not cap an external
invoice. Real router quality and the packaged cloud-endpoint workflow remain unverified.
Task 230 local-installer checks do not certify cloud-provider behavior.

The Brain shares one native projected-3D/list widget between its embedded and
full-window views. File intake and private context use explicit previews. Local
chat and the bounded Agent loop keep backend permissions, exact-action approvals,
resource queues, cancellation, stop controls and honest tool receipts.

## Data and known limits

Per-user data is under `%LOCALAPPDATA%\ERSELMETZ AI`. Uninstall keeps it by
default. Saved windows contain metadata only and never replay work. Retained
history is read-only after restart. Use Advanced → Backup before changing data.

Passing source tests does not prove provider quality or physical-device behavior.
The real local retrieval checks still include missed facts and a failed table
answer probe; no perfect-RAG or general answer-accuracy claim is made. Live paid
Gemini, physical microphone/camera behavior, assistive technology and a separate
clean Windows account remain unverified unless an exact report says otherwise.

Tasks 213–221 remain as superseded history. Their V1-relevant UI, native-window,
workspace-isolation and resource-control outcomes are carried by Tasks 223–230;
the original Electron/multi-window acceptance wording is not claimed. Task 227
covers restore, Python-only verification, packaging and legacy retirement;
Tasks 229–230 cover the listener-free native shell and current-user packaged
Windows evidence. Consult the canonical roadmap for exact evidence and limits.

## Local packaged build

Task 230 supplies a native one-folder PyInstaller build and per-user unsigned
installer. About shows its checked version and exact commit. See the
[packaged verification report](review/task-230-packaged-python-app.md) for artifact
identities, real local checks, measurements and the unverified fresh-account gate.
An isolated current-user profile is not a clean Windows-account test.

## Development and packaging

- Backend/domain services: `app/`.
- Native UI and theme: `app/qt_desktop/`; authenticated bridge: `app/native_desktop/session.py`.
- Public static site and canonical roadmap: [docs/tasks-data.json](docs/tasks-data.json).
- Generate/check browser data: `python tools/generate_docs.py --check`.
- Python, Qt and browser checks: `.venv\Scripts\python.exe -m pytest`.
- Public source integrity: `python tools/docs_integrity.py`.
- Installer, build stamps, recovery and update boundaries: [packaging notes](packaging/README.md).
- Scope, results and limits: [implementation history](docs/implementation-history.md) and `review/`.

Browser verification uses Python/CDP and an installed Chrome or Edge with an
isolated profile. It does not use Node or Playwright. Browser JavaScript remains
necessary only for the static public site; it is not a
Node runtime or build dependency. No deployment is performed by the Python docs
preview/generation tools.

## License

No application-wide license has been published. The owner must choose that
license separately. PySide6 does not make this whole repository LGPL. The exact
bundled libraries retain their licenses and distribution/source obligations;
see [third-party notices](THIRD_PARTY_NOTICES.md). Local QA artifacts are not a
public release or a claim that every distribution obligation has been fulfilled.

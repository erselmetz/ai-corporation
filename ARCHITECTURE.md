# ERSELMETZ AI CORPORATION — Current Architecture and Roadmap

## Product definition

**ERSELMETZ AI CORPORATION is an actual software system implementing a virtual/simulated AI organization.** “Virtual/simulated organization” describes the domain being modeled; it does not mean that the software system itself is imaginary.

This document separates the implemented Tasks 1–90 foundations from future architecture. Source code is authoritative if implementation and documentation disagree.

## Implemented system at a glance

```text
Browser / API client
  ↓
FastAPI
  ├── Public Web UI dashboard (/ui) + static assets
  └── Protected API routes → Authentication → Authorization
                                              ↓
                              CorporationApplicationService
                                              ↓
                                     Corporation Core
                                     ├── Orchestrator ─ task logs
                                     ├── TaskRegistry ─ SQLite tasks
                                     ├── ProjectRegistry ─ SQLite projects
                                     ├── EmployeeChatService ─ Conversation / Message records (in-memory)
                                     └── TaskRouter
                                           ├── explicit Agent assignment
                                           ├── required Employee role ─ Employee ─ Agent
                                           └── required capability ─ Agent
                                                     │
                                                     ▼
                                                  Provider
                                                     │
                                                     ▼
                                                   Model

Startup identity:
Corporation + Node → RuntimeContext → context validation

Standalone foundations, not wired into task execution:
Tool / ToolRegistry / explicit MCPToolClient adapter
ApprovalRequest / ApprovalRegistry
ClientRequest / BusinessLayer adapter
```

The CLI also uses `CorporationApplicationService` for application operations. This interface-neutral service is the application boundary for Corporation status, Employee, Agent, Provider, Model assignment, Task, Project, and Activity use cases. It coordinates existing management services and the Orchestrator and returns summaries rather than exposing registries as an interface contract. FastAPI resource routes use this boundary; the service has no HTTP, CLI, or database-driver logic, and the existing Core remains responsible for domain behavior and persistence. Task 55 adds in-memory Conversation/Message Core records. Task 56 adds the standalone Core `EmployeeChatService`, constructed with existing Employee and Agent registries, with no Conversation Application Service, API, or UI integration. It owns in-memory conversations, resolves exactly one explicit Employee/Agent selection at creation, captures fixed target IDs and scope, and returns immutable snapshots. Supplied messages and lifecycle outcomes reuse Task 55 rules; the service does not generate responses, invoke the Orchestrator/Providers, access memory or SQLite, or create Tasks. Employee reassignment does not retarget an existing conversation; a new conversation can select the new assignment.

The FastAPI application in `app.api` serves a public dashboard at `/ui`, Corporation management pages, and app-owned static assets below `/ui/static`. Browser modules request protected Corporation data only from existing API endpoints; they do not access registries, SQLite, providers, or other Core internals. `/` and `/health` remain public; resource routes use application-service dependencies and do not directly manipulate internal registries. Authentication uses an injectable backend and rejects by default. Authorization checks the authenticated principal's required permission. A production identity provider and browser sign-in/session implementation are not configured; UI pages therefore report authentication-required, forbidden, or other failures and never represent failures as empty data. The public Node.js documentation site in `docs/` remains a separate application.

### API boundary

The Task API implements:

- `GET /api/tasks` and `GET /api/tasks/{task_id}` with `task:read`.
- `POST /api/tasks` with `task:create`.
- `POST /api/tasks/{task_id}/dry-run` with `task:read`.

Task creation accepts existing title, description, optional project ID, and one existing routing selector (Agent ID, role, or capability). It delegates Task ID generation to the Orchestrator/Application Service. Task responses use explicit Pydantic schemas containing ID, title, description, project ID, status, assigned Agent, required role, and required capability; internal result/error fields and registry objects are not included. A Task's project relationship is represented by ID, but `TaskRegistry` currently does not persist or reload `project_id`.

Dry-run returns the current routing preview via the Application Service. It does not execute an Agent or Provider and does not mutate Task state. The API does not expose unrestricted task execution or Task lifecycle mutation endpoints. Missing Tasks and referenced Projects return 404; invalid routing/domain options return 400; request schema validation uses FastAPI/Pydantic 422 responses.

The Project API provides authenticated list/detail/create operations through the Application Service and existing ProjectRegistry. The Activity API provides `GET /api/activity` with `activity:read`; it returns at most 100 newest-first Task log summaries by default, optionally filtered by `task_id`. It exposes only the existing log ID, Task ID, event, and timestamp; the stored message is omitted. There is no individual-log retrieval or Activity mutation endpoint.

Task 46 adds the FastAPI Web UI foundation; Task 47 adds a compact read-only dashboard at `/ui`. Task 48 adds Employee Management at `/ui/employees`. It lists Employees and fetches details through `GET /api/employees` and `GET /api/employees/{employee_id}` (`employee:read`), creates with `POST /api/employees` and removes with `DELETE /api/employees/{employee_id}` (`employee:manage`). The existing create schema requires caller-supplied `id`, `name`, and `role`, and optionally accepts responsibilities; it does not accept or modify an Agent association. Removal requires explicit browser confirmation and follows the existing API behavior.

Task 49 adds Provider and Model Management at `/ui/providers`. Provider list/detail reads use `GET /api/providers` and `GET /api/providers/{provider_id}` with `provider:read`; creation uses `POST /api/providers` with exactly `id` / `name`, and removal uses `DELETE /api/providers/{provider_id}`, both requiring `provider:manage`. Provider responses expose only ID and configured type. Model assignments use `GET /api/models` and `GET /api/models/{agent_id}` with `model:read`; replacement uses `PUT /api/models/{agent_id}` with exactly `provider_id` / `model_id` and requires `model:manage`. Assignments identify Agents by ID only. No credential/configuration fields, Employee or Agent mutation, or direct Core access is introduced.

Management pages use same-origin browser requests and preserve API authorization. No browser sign-in/session mechanism is configured, so the relevant authenticated session and distinct read/manage permissions remain prerequisites for protected data/actions. Failures retain distinct authentication, permission, validation/conflict, missing-record, and general states.

Task 50 adds Task Management at `/ui/tasks`. The page uses `GET /api/tasks` and `GET /api/tasks/{task_id}` (`task:read`), `POST /api/tasks` (`task:create`), and the existing non-mutating `POST /api/tasks/{task_id}/dry-run` (`task:read`). Creation accepts only title, description, optional project ID, and at most one Agent ID, role, or capability selector; the API generates Task ID and status. The API has no Task DELETE route or lifecycle mutation actions, and the UI does not invent them. Project association persistence remains limited by the existing TaskRegistry.

Task 51 adds Project Management at `/ui/projects`. The page uses `GET /api/projects` and `GET /api/projects/{project_id}` with `project:read`, and `POST /api/projects` with `project:create`. Project responses contain only ID, name, description, and status; creation sends only name and optional description, with ID and status generated by the API. The existing API exposes no Project deletion or lifecycle endpoint, so the UI adds neither. It clears stale list and detail data after failed list refreshes and distinguishes an empty list from request failures.

Task 52 adds the read-only Activity / Logs page at `/ui/activity`. It uses only `GET /api/activity` with `activity:read`, the supported `limit` (1–100; default 100) and optional `task_id` query parameters. Its bounded records expose only ID, Task ID, event, and timestamp; the page does not claim to show the complete history. The API has no detail endpoint and omits log message text. Refresh clears old records while loading and after failure.

Task 53 adds the read-only Corporation Documentation Portal at `/ui/documentation`, separate from the public `docs/` website. Its protected `GET /api/documentation` returns `{ "items": [{ "id": "...", "title": "..." }] }`; `GET /api/documentation/{document_id}` returns `{ "id": "...", "title": "...", "content": "..." }`. Both require `documentation:read` and use a replaceable Documentation Application Service source. The default source reads only regular, top-level UTF-8 `.md` files from the repository-root `corporation_docs/`; IDs are validated filename stems, titles use the first Markdown H1 or a readable filename fallback, and content remains Markdown text. Resolved files must remain directly under the configured root, and symlink targets are not exposed. The browser uses same-origin API calls and text rendering, with explicit auth, permission, missing-document, loading, empty, and general-error states; it does not access files or internal persistence directly. The portal is a curated file-based documentation interface, not an AI-managed Knowledge System. It has no write or publication API.

Task 54 adds the read-only internal Updates / Changelog page at `/ui/updates`. Protected `GET /api/updates` requires `updates:read` and returns `{ "items": [{ "date": "YYYY-MM-DD", "type": "development|release", "title": "...", "summary": "..." }] }` through a replaceable Updates Application Service source. The default source reads the fixed repository-root `corporation_updates.json` manifest, validates its complete entry shape, and returns entries newest-first. This version-controlled source is maintained manually; entries are added only for verified changes, and dates or versions are not derived from Git history. The browser uses same-origin API requests and text rendering, distinguishes loading, empty, authentication, forbidden, and general errors, and clears stale entries on failed refresh. The Corporation page and manifest are separate from the public `docs/updates.html` milestone summary. There is no write, release, or publishing API.

Other resource permissions are similarly minimal: `corporation:read`, `employee:read` / `employee:manage`, `agent:read`, `provider:read` / `provider:manage`, `model:read` / `model:manage`, `project:read` / `project:create`, `activity:read`, `documentation:read`, and `updates:read`. These are route permission requirements, not a configured user/role management system. The default authentication backend rejects requests until an application supplies an authentication backend.

### Identity and runtime

- **Corporation** is the identity of the modeled organization.
- **Node / Installation** identifies a participating software or physical installation and contains a `corporation_id`.
- **Runtime Context** carries Corporation and Node IDs. `RuntimeConfig` turns configured IDs into a context; `RuntimeInitializer` validates that both identities exist and the Node belongs to the selected Corporation.
- In the current startup path, local identity IDs (`corp_local`, `node_local`) are configured directly in code. Corporation and Node registries are in-memory registries; durable installation identity/configuration and network participation are not implemented.

### Organization and AI execution

Keep these entities separate:

| Concept | Implemented responsibility |
|---|---|
| **Employee** | Organizational identity, role, responsibilities, optional associated Agent |
| **Agent** | Technical identity with role metadata, capabilities, permissions metadata, and Provider/Model identifiers |
| **Provider** | Interface for generating a response; only Ollama is implemented and registered by current startup |
| **Model** | Identifier supplied to the Agent's selected Provider |

Therefore, **Employee != Agent != Provider != Model**. The Employee registry and Agent registry are in-memory. Provider registry is in-memory. Model management updates an Agent's in-memory Provider/Model assignment; durable administration/configuration is not provided.

The Ollama integration sends a prompt to the configured Ollama HTTP endpoint. Other providers shown in older conceptual diagrams are not implemented integrations.

### Tasks, persistence, and lifecycle

A Task has `pending`, `running`, `completed`, or `failed` status and can carry:

- `assigned_agent` for an explicit Agent assignment;
- `required_role` for an Employee-role requirement;
- `required_capability` for a capability requirement.

`TaskRegistry` inserts, reloads, and updates these routing fields in SQLite. Database initialization adds `required_role` and `required_capability` with `ALTER TABLE` when an existing `tasks` table lacks them. Existing task rows are retained and read with NULL routing requirements.

The Orchestrator creates tasks, routes and executes them, persists task state, and logs task-created/started/completed/failed events. A successful route during ordinary execution assigns the selected Agent before execution. A routing failure during ordinary execution marks the Task failed; a dry-run routing failure is surfaced as a `RoutingError`.

SQLite currently stores Tasks, Projects, task logs, agent memory, and project memory in the configured database file. **Known limitation:** TaskRegistry persists/reloads `project_id` for new or updated Tasks; historical rows with unstored associations remain null and are not inferred. Employee, Agent, Provider, model assignment, approval, tool, Corporation, and Node registries are not persisted as complete administration subsystems.

### Deterministic Task Router

Task creation stores role/capability intent and does not eagerly resolve it into an Agent assignment. The deterministic priority is:

1. **Explicit assigned Agent** — resolve the exact assigned Agent; an invalid explicit assignment fails.
2. **Required Role** — find a registered Employee with an exact role match, then use its associated Agent.
3. **Required Capability** — find a registered Agent with the exact capability.
4. **Routing failure** — raise `RoutingError` if no suitable Agent is found.

When no Employee matches the requested role, routing can continue to a capability requirement if one is present. A matching Employee without an Agent produces a routing error. Task creation via the CLI accepts mutually exclusive routing options; a task with no requirement is permitted but cannot route unless an override supplies a route.

Routing is deterministic and does not use AI/LLM reasoning. There is no automatic fallback Agent.

### Dry-run

`dry-run TASK-ID` uses the Task's persisted routing requirements. It reports the selected Agent/Employee, Provider, Model, route method, and ready status without calling the Provider. A dry-run does not change task status, result, error, `assigned_agent`, or stored routing requirements.

An explicit dry-run override (`--agent`, `--role`, or `--capability`) is applied only to that routing request. It does not mutate or persist the Task.

### Command interface and management

The interactive CLI includes status and listing commands; Employee management; Provider management; Model assignment/replacement; Agent listing; Task creation; and dry-run. Task syntax is:

```text
task <description> --agent <id>
task <description> --role <role>
task <description> --capability <capability>
dry-run <task_id> [--agent <id> | --role <role> | --capability <capability>]
```

Employee, Provider, and Model management operates on the current in-memory registries/runtime. The Task routing requirements are persisted.

### Other implemented foundations

- **Client/business layer:** `ClientRequest` validates basic required text fields; `BusinessLayer` translates a request into an Orchestrator Task. This is an application-level adapter, not an HTTP service or complete external intake system.
- **Tools:** an abstract `Tool` base class and in-memory `ToolRegistry` establish a registry foundation. There are no concrete built-in tools, Agent-to-tool execution path, or enforced permission policy.
- **Human approval:** `ApprovalRequest` and `ApprovalRegistry` model pending/approved/rejected requests in memory. Approval is not persisted and is not integrated as a gate around task execution or sensitive actions.

### Integration Proposal foundation (Task 26)

The `app.integrations` package establishes concepts for future controlled integration work:

- **IntegrationSource** separates an external source description (`source_type`, `location`, optional project name) from Corporation Agents, Employees, Providers, and Models. The source type is a string so future adapters can add types without changing the proposal model.
- **IntegrationProposal** describes the requested purpose, source, optional `source_discovery_id`, evaluation/approach/risk notes, timestamps, lifecycle status, and an attached existing `ApprovalRequest`. Its lifecycle status is read-only; transitions are controlled by an explicit transition method.
- **IntegrationRegistry** stores proposals in memory. Proposal and execution persistence is deliberately deferred; it uses no second database and introduces no SQLite schema changes.
- **IntegrationExecutionRecord** is a separate audit/state record, not an executor. It can only be created for a proposal whose linked ApprovalRequest has been approved. The record does not clone sources, execute external code, write project files, or integrate changes. Proposal status `APPROVED` is distinct from `INTEGRATED`; marking a proposal integrated requires a completed record linked to that proposal.
- **IntegrationCapability** names possible future scopes. Requested scopes are descriptions only, not grants. No integration tool, unrestricted write/delete, commit, push, or execution privilege is provided.

### Public GitHub source discovery (Task 27)

`SourceDiscovery` is an adapter boundary that accepts an `IntegrationSource` and returns a typed `SourceDiscoveryResult`. `GitHubRepositoryDiscovery` implements the first adapter for `github_repository` sources; additional source adapters can be added independently.

The GitHub adapter accepts only HTTPS `github.com/{owner}/{repository}` URLs (with optional `.git` suffix/trailing slash), validates path components, rejects credentials, ports, query/fragment strings, encoded paths, other hosts, and other protocols, and never requests the user-supplied URL. It builds requests only to fixed `https://api.github.com/repos/...` endpoints and disables redirects. Public repository metadata, latest-release metadata when available, and README availability/size plus an excerpt capped at 2,000 characters for README content up to 64 KiB are returned in typed result objects. Repository-not-found, private repository, rate-limit, API, network, invalid-source, and malformed-response cases use explicit discovery exceptions. Optional README/release 404s are represented as unavailable.

The README excerpt is untrusted plain text; it is not interpreted as instructions or executed. Discovery performs no clone, package installation, shell invocation, source-code execution, semantic analysis, evaluation, sandboxing, project write, approval, or integration. No GitHub authentication token is required or configured. HTTP uses the existing `httpx` dependency. Discovery does not mutate the proposal lifecycle; a future proposal may refer to the result via `source_discovery_id`. No CLI or persistence is added for discovery in this task.

The implemented progression is Discovery → Analysis/Learning → Evaluation → Proposal Generation → Sandbox Foundation. Task 27 implements public GitHub information discovery. Proposals and sandboxes remain separate domains rather than being represented as Tasks or passed through the Task Router.

### Bounded source analysis / learning (Task 28)

`SourceAnalyzer` is a source-agnostic adapter boundary that accepts a previously created `SourceDiscoveryResult` and returns a typed `SourceAnalysisResult`. `GitHubRepositoryAnalyzer` is the first adapter. The result refers to its source via `source_discovery_id`, is separate from `IntegrationProposal` and `IntegrationExecutionRecord`, and does not transition or create proposals.

The GitHub analyzer requests the recursive tree for the already validated repository owner/name and discovered default branch from the fixed GitHub API host. It inventories relevant documentation, source, test, configuration, license, and dependency-manifest paths, then fetches bounded text only for selected documentation and dependency manifests. It records detected languages, top-level directories, tests, manifests, frameworks mentioned in inspected text, and evidence-linked documentary purpose/potential-capability observations. These observations are not verified capabilities, compatibility scores, risk/security scores, or integration recommendations. No LLM is used.

Limits are explicit: at most 50 relevant files, tree paths no deeper than 8 segments, at most 4 documentation files read, at most 48 KiB per content file, at most 256 KiB of decoded source text, and at most 2 MiB for the tree response. Retrieval uses streamed API responses, bounded response reads, 10-second request timeouts, and disabled redirects. Truncated or over-limit results are marked incomplete with notes. Missing optional files are recorded rather than treated as successful content reads. The analyzer reads files as UTF-8 text only and never imports or executes them.

The analyzer accepts only a public `github_repository` discovery result, verifies its URL/owner/repository identity, and sends requests only to fixed `api.github.com` endpoints. External files remain untrusted data. No cloning, package installation, shell execution, project writes, configuration changes, commits, pushes, proposal approval, or integration occurs. Results remain in memory; no persistence or CLI command is added because discovery results themselves are not currently stored by the application.

### Evidence-backed source evaluation (Task 29)

`SourceEvaluator` is the evaluation boundary; `GitHubRepositoryEvaluator` accepts an existing `SourceDiscoveryResult` and its corresponding `SourceAnalysisResult` and returns a typed `EvaluationResult`. It validates the discovery linkage and repository identity, performs no network requests, and does not read the proposal registry or mutate proposals. Findings identify category, status (`supported`, `concern`, `unknown`, or `not_applicable`), summary, discovery linkage, and evidence references tied to fields/paths from Tasks 27–28.

Evaluation covers capability fit, architecture/interface compatibility, known dependency-manifest presence and dependency uncertainty, license metadata, bounded security signals, repository maintenance signals, and integration complexity. Security findings distinguish `observed`, `not_observed`, and `unknown`; "not observed" only describes the bounded information and is not a security assurance. Maintenance facts such as a release or push timestamp are reported without an unsupported activity rating. Unknown interfaces, runtime requirements, dependencies, risks, or incomplete analysis remain explicitly unknown.

The result communicates key strengths, concerns, unknowns, integration requirements, completeness, and notes. It has no quality score, ranking, acceptance/rejection decision, legal advice, or integration recommendation. External documentation remains untrusted data. Evaluation executes no code, runs no commands, installs no packages, clones nothing, changes no local/Git state, creates/transitions no `IntegrationProposal`, and grants no approval. Evaluation results are in-memory only; no CLI or persistence is added.

### Evidence-backed integration proposal generation (Task 30)

`ProposalGenerator` consumes already-produced `SourceDiscoveryResult`, `SourceAnalysisResult`, and `EvaluationResult` values; `GitHubIntegrationProposalGenerator` validates their source and stage linkage and returns an `IntegrationProposal`. It performs no source discovery, analysis, evaluation, registry mutation, or network access. Proposals retain `source_discovery_id`, `source_analysis_id`, and `source_evaluation_id`, plus structured fields for intended capabilities, findings, strengths, concerns, unknowns, dependencies, license/security information, requirements, implementation considerations, and evidence references. Missing evidence is preserved as unknown rather than inferred.

Generated proposals describe a possible purpose and an adapter-oriented approach for a future reviewed effort. They advance through the existing lifecycle to `PROPOSED` and stop there; generation does not imply approval or create an approval request. The caller may explicitly register the returned proposal with the existing `IntegrationRegistry`; no second registry is introduced. The proposal is a plan only: generation does not execute repository code or commands, install dependencies, clone a repository, modify ERSELMETZ or Git state, activate capabilities, or integrate anything. Review and human approval remain separate controlled stages.

The implemented stages are **Discover** (Task 27) → **Analyze/Learn** (Task 28) → **Evaluate** (Task 29) → **Proposal Generation** (Task 30). Proposals preserve evidence and unknowns; they do not rank candidates, score quality, approve, or execute. Sandboxing, testing, review, separate human approval, and integration remain later stages.

### Integration sandbox foundation (Task 31)

`IntegrationSandbox` is a typed, in-memory sandbox record linked to an existing `PROPOSED` `IntegrationProposal` and its `source_discovery_id`. `IntegrationSandboxRegistry` supports explicit creation, lookup, listing, validated state transitions, and destruction. Creation does not mutate the proposal lifecycle and does not alter `IntegrationRegistry`, `IntegrationExecutionRecord`, or any persisted state.

Sandbox status is `CONFIGURED`, `READY`, `RUNNING`, `COMPLETED`, `FAILED`, or `DESTROYED`. Foundation-supported transitions include `CONFIGURED → READY` and explicit destruction from configured/ready. Execution transitions are reserved for a future isolated executor; the Task 32 execution boundary still cannot move a sandbox to `RUNNING`, and a direct transition raises `SandboxExecutionNotImplementedError`. `READY` and the presence of policy metadata are not proof of isolation.

`SandboxIsolationPolicy` is configuration metadata with restrictive defaults: read-only filesystem, disabled network and process access, minimal environment, no credentials, and bounded memory/CPU/process/disk limits. These values describe an intended future boundary only. Task 31 provides no enforcement: no filesystem or network isolation, resource limits, host modification, process/container/VM creation, repository cloning, package installation, or external-code execution. Sandbox records are in-memory; there is no CLI, persistence, approval, or integration path in this task.

The implemented stages are **Discover** (Task 27) → **Analyze/Learn** (Task 28) → **Evaluate** (Task 29) → **Proposal Generation** (Task 30) → **Sandbox Foundation** (Task 31) → **Sandbox Execution Boundary** (Task 32). An actual isolated backend must provide real enforcement before execution; testing, review, human approval, and integration remain separate stages.

### Sandbox execution boundary (Task 32)

`SandboxExecutionRequest` contains sandbox/proposal IDs, a normalized relative workspace entrypoint, string arguments, timeout, environment mode, and requested resource limits. Absolute paths, traversal components, drive paths, backslashes, NUL values, mismatched IDs, non-ready sandboxes, and requests beyond the sandbox's configured limits are rejected. Requests have no environment-variable or credential injection field.

`SandboxExecutor` is the execution boundary and `SandboxBackend` is the future isolated-runtime contract (`prepare`, `execute`, `collect_result`, and `cleanup`). `UnavailableSandboxBackend` identifies itself as `none`, unavailable, and non-enforcing. `UnavailableSandboxExecutor` does not invoke even a backend claiming availability/enforcement in this foundation-only task: a valid request produces a `BLOCKED` result with `isolation_backend="none"`, no exit code or execution measurements, and leaves the sandbox at `READY`. No `RUNNING` transition or fake completed result is produced.

The request/result models, abstractions, and policy checks are not isolation enforcement. Task 32 adds no host subprocess, shell, Docker/Podman, VM, package installation, repository clone/download, execution, network access, filesystem isolation, resource enforcement, credential injection, CLI, persistence, approval, or integration. A future task must add a genuinely isolated backend and explicitly implement its lifecycle/cleanup behavior before any external code can run.

Task 32 established the **Sandbox Execution Boundary**; Task 33 adds the optional Docker runtime described below.

### Docker sandbox backend (Task 33)

`DockerSandboxBackend` implements `SandboxBackend` using the optional official Docker Python SDK. It is loaded lazily; the SDK is not a declared base dependency and is never installed automatically. If the SDK, Linux Docker daemon, or backend safety checks are unavailable, execution fails closed. `DockerSandboxExecutor` routes operations through the existing executor/backend contracts and `IntegrationSandboxRegistry`; it transitions a registered sandbox to `RUNNING` only after container creation, then to `COMPLETED` or `FAILED` after result collection and cleanup. A container's removal does not destroy the sandbox record.

`SandboxImagePolicy` requires an explicitly approved, SHA-256 digest-pinned image and a configured default. The backend verifies the image is already available locally with the Docker image API and never pulls an image. The entrypoint is a normalized relative workspace path converted to a container path; arguments are passed as a list, never through a host shell. The image must contain the executable/source material; Task 33 adds no source checkout, archive download, or host mount.

Container creation explicitly requests network disabled (`network_mode="none"`), a read-only root filesystem, no host mounts, no Docker socket, no credentials or inherited host environment, `privileged=False`, a non-root numeric user, all Linux capabilities dropped, `no-new-privileges`, memory and CPU caps, a PID limit, and a writable-layer size limit. It requests a bounded temporary filesystem and applies the requested timeout through Docker's wait API. If Docker cannot apply any requested resource/isolation option or the local image is missing, creation is blocked; there is no fallback to subprocess or host execution. The SDK is optional: install the Docker Python SDK explicitly in the chosen environment to enable this backend. A compatible Docker daemon and approved image must also be configured.

Execution output, status, exit code where available, duration, timestamps, backend identity, and notes populate `SandboxExecutionResult`. Timeout triggers container kill, output collection, and cleanup. Cleanup is attempted after success, nonzero exit, timeout, and exceptions; cleanup failure is surfaced as a failed execution result. Execution records remain a separate audit concern; proposals are never approved or integrated by Docker execution.

**Docker container isolation is the current execution mechanism for the sandbox backend when configured, but sandbox execution is still an experimentation layer and does not imply approval or integration.**

Implemented path: Integration Sandbox → SandboxExecutor → SandboxBackend → DockerSandboxBackend → Disposable isolated container. Testing, review, human approval, and integration remain separate stages.

### Controlled source staging (Task 34)

`SourceStager` defines an inert source-preparation boundary. `GitHubSourceStager` accepts only a validated public-GitHub `SourceDiscoveryResult` and downloads from the fixed GitHub API tarball endpoint over HTTPS. It disables automatic redirects and accepts only validated HTTPS codeload archive redirects for the same repository. Its HTTP client does not inherit proxy settings from the host environment. It uses no Git credentials, host secrets, shell, subprocess, or Docker operations.

Archive bytes and members are bounded. Before any workspace is created, the stager validates archive member paths, types, counts, declared file sizes, aggregate expanded size, and path depth. Absolute/traversal paths, duplicate/conflicting entries, symlinks, hardlinks, and special files are rejected. Files are written only into a dedicated temporary workspace outside the project repository; file creation does not follow links. A failed attempt removes its partial workspace and returns a `BLOCKED` result without a workspace reference. Successful results link to `source_discovery_id` (and optional sandbox ID), include file/byte counts, completeness, timestamps, notes, and SHA-256 digests for the archive and staged contents. Digests provide identity/integrity tracking, not trust or approval. Results and workspace lifecycle are not persisted.

Staging never executes source or README instructions, installs dependencies, modifies repository/Git state, changes proposal lifecycle, or automatically integrates anything. It only prepares bounded, untrusted source data for a later explicitly controlled sandbox workflow. `INCOMPLETE` is reserved in the result model; current staging is atomic and either completes within bounds or is blocked.

### Sandbox/source binding (Task 35)

`SandboxSourceBindingRegistry` creates an in-memory typed reference joining a successful `SourceStagingResult` to the registered `IntegrationSandbox` and its `IntegrationProposal`. It checks proposal/sandbox/discovery/staging IDs, requires a complete `STAGED` result with valid hashes, and validates that the workspace is a real, non-symlink directory directly inside the configured staging root, has the staging-ID-derived directory name, and does not overlap the project repository. The staging root is explicit configuration, not taken from the result path.

Before binding, it recalculates the Task 34 canonical SHA-256 over sorted relative file paths, contents, and sizes, and checks the file count and total bytes against staging metadata. Symlinks, non-regular files, hard-linked files, missing paths, out-of-root paths, and changed contents fail closed. The binding preserves both staged-content and archive hashes; matching hashes identify bytes but do not establish trust or approval. The registry is in-memory only.

Binding does not transition proposal, sandbox, or task lifecycle, call the `SandboxExecutor` or Docker backend, execute source, install dependencies, or mount a host path. It supplies a validated source reference for a future, separate execution task; the Docker backend remains responsible for isolation and does not download source.

Implemented path: GitHub Source → Discovery → Analysis/Learning → Evaluation → Proposal → Sandbox → Controlled Source Staging → Sandbox Source Binding → Sandbox Executor → Docker Backend → Isolated Container. Staging prepares data; binding validates and associates it; execution remains a separate future operation. Sandbox execution remains experimentation and does not imply proposal approval or integration.

### Execution preparation (Task 36)

`ExecutionPreparationRegistry` resolves proposals, sandboxes, and source bindings through their existing in-memory registries and consumes the Task 34 staging result. It returns an immutable `ExecutionPreparation` with `READY`, `BLOCKED`, or `INVALID` status, IDs for the proposal/sandbox/discovery/staging/binding, the controlled workspace reference, source/archive hashes, file/byte counts, prepared time, validated isolation-policy snapshot, and validation/limitation notes.

Preparation requires consistent registered IDs and complete `STAGED` material. It verifies the workspace remains a real direct child of the configured staging root, does not overlap the project, matches its staging-derived name, and still matches Task 35’s canonical SHA-256, file count, and byte total. `verify_workspace` allows a future execution layer to repeat that check just before use. The immutable record captures the source identity observed at preparation time; its path/hash must not be treated as current without revalidation. Hash agreement establishes identity, not safety, trust, or approval.

The preparation request has no entrypoint/command, host environment, or credential field. Preparation validates the sandbox’s typed isolation policy and requires no credentials and a non-inheriting environment mode. It never calls `SandboxExecutor`, `SandboxBackend`, or Docker; it executes no source, installs nothing, and changes neither proposal nor sandbox lifecycle. This is readiness metadata only. The existing executor remains the separate execution boundary and continues to block where actual execution is not implemented; Docker remains a future isolation backend operation.

Pipeline distinction: **Source Staging** prepares controlled source material → **Sandbox Source Binding** associates it with a sandbox → **Execution Preparation** validates that a future experiment can be requested → **Sandbox Executor** remains the execution boundary → **Docker Backend** provides isolation when a future execution backend is enabled.

## Tasks 1–89 completion scope

Tasks 1–89 are complete as the current foundation. Their implemented areas include:

- Task and Project domain/registry foundations.
- Task lifecycle, orchestration, logging, and SQLite persistence.
- Agent, Employee, Provider, and Model domain boundaries.
- Agent capability lookup and Employee-role lookup.
- Ollama execution integration and Provider interface.
- Employee and Provider management foundations.
- Model assignment/replacement management for the in-memory Agent.
- Tool abstraction and registry foundation.
- Human approval request/status foundation, extended with recorded decision identity and time.
- Client request validation and business-layer Task translation.
- Corporation and Node identity models and registries.
- Runtime identity configuration, context validation, and startup wiring.
- Interactive Corporation command interface and management/listing commands.
- Deterministic explicit-Agent, role, and capability routing.
- Dry-run execution and CLI routing options.
- Persistent role/capability requirements with additive SQLite migration and reload.
- Integration source/proposal models, controlled lifecycle, proposal registry, and approval-gated execution record foundation.
- Public GitHub repository metadata discovery through a source-adapter abstraction.
- Bounded GitHub repository structure/documentation analysis through a source-analyzer abstraction.
- Evidence-backed source evaluation based on existing discovery and analysis results.
- Evidence-based proposal generation from existing discovery, analysis, and evaluation results.
- In-memory integration sandbox metadata, policy definitions, and controlled lifecycle foundation.
- Typed sandbox execution requests/results, executor/backend boundaries, and blocked behavior without an isolated backend.
- Optional Docker sandbox execution backend with an explicit image policy, enforced container controls, bounded runtime, and cleanup.
- Controlled staging of validated public GitHub source archives into a bounded temporary workspace, without execution or project modification.
- Integrity-checked in-memory binding of a staged workspace to its proposal and registered sandbox, without lifecycle changes or execution.
- Immutable readiness preparation that revalidates staged-source identity, sandbox policy, and existing proposal/sandbox/binding relationships without accepting execution commands or host credentials.
- Application Service and FastAPI authentication/authorization foundations, plus Corporation status, Employee/Agent, Provider/Model assignment, and Task APIs. The Task API supports read, create, and non-mutating dry-run only; it does not expose HTTP execution or lifecycle mutation.
- Project list/detail/create and bounded, read-only Task Activity APIs using explicit summaries and the existing persistence/logging infrastructure.
- a FastAPI-served Corporation Web UI foundation, read-only dashboard at `/ui`, Employee Management at `/ui/employees`, and Provider/Model Management at `/ui/providers`, with CSS and browser modules under `/ui/static/`. The dashboard and management pages consume only existing protected APIs and preserve their authentication and permission checks. Browser authentication is not configured, so protected data/actions require an authenticated session; pages clearly render per-resource failure states meanwhile.
- Provider administration through the existing `provider:read` / `provider:manage` endpoints, limited to the supported ID/name create contract and safe ID/type responses; model assignment viewing/replacement through `model:read` / `model:manage` with the supported Agent ID and provider/model identifiers.
- Task Management at `/ui/tasks`, using the protected Task list/detail/create and non-mutating dry-run APIs; no Task deletion or lifecycle mutation action is exposed because the API does not support one.
- Project Management at `/ui/projects`, using the protected Project list/detail/create APIs and their `project:read` / `project:create` permissions. Creation accepts only name and optional description; no deletion or lifecycle action is exposed because the API does not support one.
- Activity / Logs at `/ui/activity`, using only the existing protected bounded Activity endpoint with `activity:read`; the UI displays the API's safe summary fields and does not add detail or mutation operations.
- The read-only Documentation Portal at `/ui/documentation`, with protected document-list and document-content APIs requiring `documentation:read`. Its replaceable application-service source reads only top-level UTF-8 Markdown files from `corporation_docs/`; it validates filename-based IDs, rejects symlink/path escapes, and keeps browser access within the API boundary. The internal portal remains separate from the public `docs/` website and is not an AI-managed knowledge system.
- The read-only Updates / Changelog page at `/ui/updates`, with protected `GET /api/updates` requiring `updates:read`. Its replaceable application-service source reads a fixed, manually maintained `corporation_updates.json` manifest containing verified, explicitly dated development or release records; it does not infer updates from Git history and remains separate from the public `docs/updates.html` project summary.
- In-memory Conversation and Message records with explicit message lifecycle transitions and open/closed Conversation state. Closing rejects outstanding pending Messages, and closed Conversations reject new ones.
- Individual Employee Chat Core service over those records with a fixed Employee/Agent target, explicit scope, and immutable snapshots. Messages and lifecycle outcomes are supplied explicitly; there is no automatic response generation, persistence, context retrieval, provider interaction, Conversation API/UI, or Task conversion.
- Optional synchronous Provider availability results, defaulting to UNKNOWN when no supported check exists; Ollama has a bounded service-only check that is distinct from model readiness and resource capacity.
- Review-only model-candidate selection from explicit caller-supplied capability, policy, availability, and cost facts; existing assignment and execution paths are unchanged.
- Bounded caller-driven multi-Agent collaboration records with explicit participant roles, one-way handoffs, shared context snapshots, metadata-only Task audit events, and no Provider calls or Task lifecycle mutation.
- On-demand immutable monitoring reports over local Task, Provider-registration, and configured resource-capacity snapshots, with bounded factual failure/capacity signals and no Provider probes or runtime changes.
- Persisted routing/execution-stage failure categories, UNKNOWN for legacy unclassified failures, and bounded failure summaries without raw exception text.
- One-call caller-selected Agent diagnostics over bounded caller-supplied sanitized evidence, with citations validated against supplied references.
- Caller-authored in-memory maintenance proposals linked to Task 77 diagnostics, with explicit bounded change, scope, and risk fields.
- Bounded application of caller-supplied unified diffs to explicitly selected existing UTF-8 files inside a disposable temporary copy, with patch/source digests and explicit cleanup; no source or test execution, Provider call, Task creation/execution, assignment change, or Git operation.
- Caller-selected Python test files executed against a separate temporary copy of the selected Task 79 workspace, with bounded runtime/output, a reduced environment, and immutable actual-result reports; no shell, dependency installation, Task execution, Provider calls, or persistence.
- One-call, caller-selected Agent code reviews over bounded caller-supplied sanitized evidence, with severity/area classifications and citations restricted to supplied references; reports are advisory and are not approvals.
- A separate Docker-only maintenance test path that transfers only registered Task 79 workspace files into an ephemeral, no-network/no-host-mount container and blocks rather than falling back to host execution.
- An in-memory maintenance approval workflow that presents the exact patch diff and binds the decision to its registered workspace, patch hash, and source hash; authenticated API reviewers require `maintenance:approve`, and their principal identity/time are recorded.
- Authorized local Git checkpoint commits from exact approved Task 79 workspaces, recorded on dedicated `maintenance-checkpoints/<workspace-id>` branches without checkout, push, merge, or changes to the active index/worktree.
- A bounded, caller-driven maintenance workflow record linking an existing Task 76 failure to its Task 77 diagnostic, Task 78 proposal, Task 79 workspace, one Task 80/82 test report, and a Task 81 review of evidence that includes the exact patch. A passing test and recorded review make the workflow eligible for Task 83 approval; findings remain advisory. Task 83 approval and Task 84 checkpoint actions remain separate and are only recorded after matching the same workspace and hashes. Workflow snapshots are in-memory (maximum 100), while metadata-only stage audit events use the existing Task log. A failed test is terminal for that workflow; there are no automatic retries, background stages, Task creation/execution, API/UI, or patch application.

Task 79's temporary copy is not a security sandbox. It accepts no file additions/deletions/renames. Task 81 reviews only caller-supplied evidence and does not retrieve workspace files or execute tests; human approval and Git checkpoint workflows remain separate.

Task 80 runs only explicitly selected Python test files already present in a registered Task 79 workspace, using a separate temporary copy and a bounded pytest subprocess. It caps test files and combined output, limits runtime to 120 seconds, uses a reduced environment, and returns an immutable actual-result report without persistence. This does not provide OS-level isolation: selected test code still runs with the current user's permissions. Task 82 adds a separate Docker-only path; it does not silently change Task 80's behavior.

Task 81's `CorporationApplicationService.review_proposed_changes()` makes one call through the explicitly selected registered Agent and reviews only 1–20 caller-supplied `DiagnosticEvidence` items, bounded to 32 KiB total. The supplied content is sent to that Agent's configured Provider; callers must sanitize the evidence and authorize its disclosure before submission. No source files, workspace, Task state, logs, or test reports are retrieved automatically. The immutable in-memory report classifies findings by severity and review area, validates citations against supplied reference IDs, and includes a SHA-256 digest of the exact evidence tuple for later workflow linkage. Findings are advisory, may be incorrect, and an empty result is not approval. The operation does not execute tests or Tasks, modify patches or assignments, change proposal/approval state, persist results, or add API/UI. Task 83 adds a separate human approval workflow; Task 84 adds a separately authorized local checkpoint operation.

Task 82's `CorporationApplicationService.run_sandboxed_tests()` runs explicitly selected Python tests from a registered Task 79 workspace only through a caller-configured Docker image pinned by an immutable digest and already present locally; images are never pulled automatically. The image must provide `/bin/sleep`, `python3`, and pytest. At most 20 workspace files and 16 MiB are transferred through Docker's archive API into a writable, `noexec` tmpfs; the container has no host mounts, network, injected environment credentials, or writable root filesystem, and runs as UID 65534 with all capabilities dropped and `no-new-privileges`. Memory, process count, temporary storage, runtime (at most 60 seconds), and captured output (64 KiB) are bounded. Containers are removed after execution; reports are immutable in-memory results and are not persisted. Missing Docker, an unapproved/missing image, unsupported controls, staging failure, or cleanup failure never falls back to Task 80's host-permission subprocess. Docker daemon and image integrity remain trusted prerequisites; this is not protection against a compromised Docker daemon or host administrator. Test code has no host paths mounted and cannot modify host files through this boundary; the Docker daemon still performs its normal ephemeral container bookkeeping. No active Corporation records are changed, and no API/UI is added.

Task 83's `CorporationApplicationService.request_maintenance_approval()` creates a bounded in-memory review request for a registered Task 79 workspace and exposes its exact caller-supplied unified diff, proposal/workspace IDs, changed files, and patch/source SHA-256 digests. Reviewers use the authenticated `/api/maintenance/approvals` endpoints; the configured authentication backend must grant `maintenance:approve` only to human reviewers, and the authenticated principal identity and UTC decision time are recorded. The default backend rejects requests. Approval and rejection are one-way decisions from PENDING; decision requests must echo both digests, and an approval is valid only for the same still-registered workspace and exact patch/source hashes. `require_approved_maintenance_workspace()` provides a fail-closed check for later consumers. Requests and reports are in-memory and bounded to 100; Task 83 itself applies no patch, runs no Git operation, and executes no Task.

Task 84's `CorporationApplicationService.create_maintenance_checkpoint()` consumes only a still-registered Task 79 workspace with Task 83 approval for the exact patch/source hashes. Its authenticated `/api/maintenance/checkpoints` routes require the distinct `maintenance:checkpoint` permission; the authenticated creator identity is recorded in the immutable in-memory checkpoint report and local commit message. The source digest and unified diff are revalidated, selected files must already be tracked regular files, and the repository must have an existing HEAD plus a clean worktree and index. Git operations use an isolated temporary index and atomically create a local `maintenance-checkpoints/<workspace-id>` branch pointing to a new commit whose parent is the observed HEAD. The active checkout, worktree, and index are not changed; the operation does not switch branches, push, merge, run tests or Tasks, call Providers, or change runtime assignments/resources. Git hooks and filesystem-monitor hooks are disabled for these plumbing operations; repositories configured to require signed commits fail closed rather than bypassing that policy. The branch and commit persist in the local Git repository, while API checkpoint reports are in-memory and capped at 100. Recovery is an explicit human operation using `git revert` after the checkpoint is later integrated; Task 85 records the checkpoint only after it exists and does not perform or authorize the operation.

## Controlled Self-Maintenance (Task 85)

`CorporationApplicationService.start_maintenance_workflow()` and the `record_maintenance_*()` methods maintain a bounded, caller-driven progression from an existing failed Task and Task 76 failure summary. Callers invoke each existing stage separately, then record its result in order: Task 77 diagnostic → Task 78 proposal → Task 79 patch workspace → one Task 80 or Task 82 test report → Task 81 review. A review is accepted only when its evidence digest matches the Task 81 report and its evidence contains the exact workspace diff. Findings remain advisory; only a PASSED test and a recorded review make the workflow ready to request Task 83 approval.

Task 85 records the Task 83 pending request and final human decision only after verifying the existing approval service's workspace and patch/source hashes. It records a Task 84 checkpoint only after verifying the registered checkpoint and the same approval/hash linkage. It does not call Providers, run tests, request or decide approvals, create checkpoints, apply patches, create or execute Tasks, change assignments, or reserve resources. Test failures terminate that workflow; no automatic retry, scheduler, recursive orchestration, API/UI, or new database schema is added. Snapshots are immutable and in-memory, capped at 100 workflows and nine events each; metadata-only stage events are written through the existing Task log. Workflow state cannot be resumed after process restart, although its audit events remain in the Task log. At Task 85 completion, Tasks 86–100 remained planned.

Task 85 leaves Task 70 controlled execution/admission, Task 71 configured resource-awareness, Task 72 provider availability, and Task 73 review-only candidate selection unchanged. It makes no routing or candidate-selection decision and adds no autonomous capability.

## MCP Integration (Task 86)

`MCPToolClient` is an opt-in synchronous adapter over the existing `Tool` and `ToolRegistry` contracts. It connects only to explicitly configured local stdio or in-process MCP servers; a frozen tool-name allowlist limits discovery, and callers explicitly register and invoke selected tools. JSON inputs and text/structured results are bounded, requests have a maximum 30-second timeout, custom child-process environments are rejected, and expected server/protocol failures do not expose raw exception details. Each operation opens and closes its own MCP client connection.

The adapter is not wired to Agents, Task execution, APIs, or UI. It creates or executes no Tasks and performs no background discovery, polling, or application-level retry. Local MCP servers remain trusted processes running with host permissions; this integration is not an OS sandbox. At Task 86 completion, Tasks 87–100 remained planned.

## GitHub Integration (Task 87)

`GitHubRepositoryInspectionService` reuses Task 27's public repository discovery behind the authenticated `GET /api/github/repositories/{owner}/{repository}` route. Each application instance must be configured with an explicit immutable set of `GitHubRepositoryScope` entries; the route separately requires `github:read`. The default scope set is empty and the default authentication backend rejects requests. Repositories outside scope and missing/private repositories return the same not-found response without contacting GitHub for out-of-scope requests.

The operation is read-only and returns selected public metadata; it omits README text. It does not accept credentials, inspect private repositories, create branches/commits/pull requests, or change GitHub state. There are no separate approval records: the caller permission and repository allowlist are the confirmed access gates. The endpoint is not connected to Agents, Tasks, or automatic maintenance. At Task 87 completion, Tasks 88–100 remained planned.

## Browser/Web Research (Task 88)

`WebResearchClient` retrieves one caller-supplied page URL per explicit call. It requires an immutable exact-host allowlist, which defaults to empty; subdomains are not implicitly allowed. It accepts HTTPS page URLs without credentials, query strings, fragments, or non-default ports, disables environment proxy settings and redirects, and makes no search, crawl, or follow-up requests. Requests have a 10-second timeout and a 512 KiB response limit. Only HTML and plain text are accepted; extracted text is limited to 20,000 characters.

Results are immutable `WebResearchDocument` records classified as `UNTRUSTED_EVIDENCE`. Retrieved text remains data, even if it contains instruction-like language; the client does not interpret it, invoke a Provider, create or execute Tasks, or make Agent calls. HTML script, style, and other non-content elements are excluded from extracted text. Task 88 has no API/UI, persistence, browser automation, background polling, or automatic research loop; callers explicitly supply each URL.

## Coding Tool Integration (Task 89)

`CodingToolProposalService` invokes exactly one explicitly selected, registered `MCPTool`. The tool must declare `instruction` and `files` inputs; callers supply the bounded instruction and immutable tuple of selected path/content pairs. The serialized input is limited to 16 KiB, with at most eight files and 4 KiB per file. The MCP tool must return a unified diff limited to 65,536 bytes and 10,000 lines; output headers must target only the selected files. The service returns an immutable `CodingToolProposal` with source and patch digests and does not apply the diff, create a workspace, run tests, or call the review workflow. A caller may separately use Task 79 and later Task 80/81; these are not invoked automatically.

This adapter makes a selected MCP call explicit but does not sandbox the MCP server. A local stdio/in-process coding server remains trusted and may have host permissions, as documented for Task 86. Only caller-supplied source files are sent; there is no filesystem discovery, Agent/Provider call, Task creation/execution, persistence, API/UI, or automatic retry.

## Computer-Use Capability (Task 90)

`ReadOnlyBrowserInspector` accepts one caller-supplied URL and reuses Task 88's exact-host HTTPS allowlist and bounded retrieval. It strips scripts, styles, resource-bearing and event attributes, and non-content active elements before rendering the remaining static markup in a fresh headless Chromium context. JavaScript, downloads, browser-generated requests, and local-file access are disabled; the context closes after each explicit call. Results are immutable, bounded, and classified as untrusted evidence, with user-visible safeguards included.

This is a read-only static inspection capability, not general browser or computer control. It exposes no clicks, keyboard input, downloads, filesystem access, browser persistence, API/UI, Agent/Provider calls, Task creation/execution, or background polling. At Task 90 completion, Tasks 91–100 remain planned.

## External Service Integration (Task 91)

`GeminiModelCatalogAdapter` performs explicit, on-demand, read-only model listing against Google's fixed Gemini API models endpoint. A trusted backend supplies `GeminiAPIConfiguration`; the API key is sent only in the `x-goog-api-key` header, is omitted from configuration representations, and is never placed in URLs, audit events, errors, or returned model records. The adapter disables redirects and environment proxies, uses a 10-second timeout per request, caps each response at 512 KiB, and follows at most five model-list pages of at most 100 records each. It does not retry failed requests.

The immutable result contains only model IDs, an allowlist of service-advertised capability names, a pagination-completeness flag, and a metadata-only audit event. Missing capability metadata remains UNKNOWN (`None`); unrecognized capability names are omitted. Audit metadata is returned with successes and sanitized failures, and is not automatically persisted. Listing does not generate content, establish model suitability or future execution success, choose/assign a model, invoke an Agent or Task, or change existing Provider behavior. No chat-based key entry, general credential store, API/UI, or background polling is added. At Task 91 completion, Tasks 92–100 remain planned.

## Capability Registry (Task 92)

`CapabilityRegistry` builds an immutable, read-only inventory from existing Agent declarations, registered Tool metadata, the non-granting `IntegrationCapability` scope enum, and an optional caller-supplied `GeminiModelCatalogResult`. Evidence labels distinguish agent-declared, tool-registered, scope-only, and service-reported records. Ownership identifies the source Agent, Tool, integration pipeline, or Gemini service/model; it is not a human principal or authorization. Requirements are included only where the source defines them; `None` means the source supplied no requirement metadata.

Snapshots preserve source timestamps for Gemini data, report model count and incomplete pagination, cap records at 2,000, and identify that independent registries are read sequentially rather than atomically. Gemini models without allowlisted method metadata do not create inferred capability entries; model count and completeness remain visible. The registry never calls Gemini, persists or registers definitions, alters source registries, grants access, invokes Tools, changes Agent/model assignments, ranks candidates, or executes Tasks. Provider availability and Task 73 selection remain separate. No API/UI, durable state, or background refresh is added. At Task 92 completion, Tasks 93–100 remained planned.

This is a grouped capability summary, not a claim that every long-term capability is production-complete. See limitations above; particularly, historical Task project associations may be unknown, registry/configuration persistence is limited, tools and approvals are not wired to task execution, integration proposals are not persisted, there is no integration executor, and only Ollama is implemented as a provider.

## Capability Discovery (Task 93)

`CorporationApplicationService.discover_capabilities()` accepts an immutable tuple of up to 100 caller-supplied `CapabilityCandidate` records and returns a bounded immutable report. Candidates include caller-provided identifiers, descriptions, and source references; references are retained as text and are never followed or fetched. The report identifies its input as caller-supplied and labels its limitations explicitly. Empty candidate tuples are valid, candidate identifiers must be unique, and the input order is preserved without ranking.

This is manual candidate intake, not autonomous search: candidates and source references are not independently verified. Discovery does not evaluate fit or risk, select or register capabilities, grant permissions, activate tools or services, call Providers, modify runtime registries, or execute Tasks. It is in-memory only and has no API/UI or persistence. Task 94 owns capability evaluation; Tasks 94–100 remain planned.

## Future / planned roadmap

None of the following should be represented as implemented until code provides it:

- Richer workflow orchestration, dependency scheduling, and multi-Agent collaboration.
- AI-based, semantic, or policy-aware task routing; dynamic selection and advanced Provider/Model selection.
- Agent-to-Agent communication.
- Additional Provider integrations beyond Ollama.
- Durable organization, Agent, Employee, Provider, and model configuration management.
- A Software Reliability Engineer / QA guardian and richer evaluation.
- Production identity/authentication, authorization policy and permission administration, and encryption.
- Offline Mode, durable queues, synchronization, and conflict resolution.
- Node discovery and networking among independent Corporation installations.
- Richer Tool and MCP integration, concrete tools, and controlled tool execution.
- Open-source coding/editing, repository mapping, terminal, interactive browser/computer-control, voice, and Git/GitHub workflow integrations.
- Git/GitHub automation.
- Controlled self-improvement and a sandbox/evaluation pipeline.
- External integration stages beyond Task 36 execution preparation: sandbox execution of staged source, dependency installation, testing, review, approval orchestration, integrate, and monitor.

### Open-source ecosystem direction

ERSELMETZ AI CORPORATION should not unnecessarily recreate mature open-source agent and coding infrastructure. Its intended role is the **governance + organization + orchestration + identity + task management + routing + approval + coordination layer**. Suitable existing projects, protocols, and tools may be integrated for specialized coding/editing, repository mapping, terminal execution, browser/computer interaction, MCP/tool integration, voice/computer control, and Git/GitHub workflows. Such examples describe a direction only; no such integration is implied to exist today.

### Controlled self-improvement

The intended controlled improvement path is:

**Discover → Analyze/Learn → Evaluate → Proposal → Sandbox Foundation → Controlled Source Staging → Sandbox Executor → Docker Sandbox Backend → Disposable Container → Test → Review → Approve → Integrate → Monitor**

Unrestricted autonomous self-modification is **not** the current design. Future changes must be controlled, testable, auditable, and subject to appropriate approval boundaries.

The `IntegrationCapability` enum defines possible request scopes: `READ_SOURCE`, `ANALYZE_SOURCE`, `RUN_SANDBOX`, `WRITE_PROJECT`, `RUN_TESTS`, `REQUEST_APPROVAL`, and `INTEGRATE`. Execution records can describe requested scopes, but Task 26 grants or enforces none of them; Task 31's policy and Task 32's abstractions alone enforce no isolation. Task 33 requests Docker isolation controls and fails closed when those controls cannot be applied. Container execution remains experimentation only; it does not approve or integrate a proposal. Delete, commit, and push authority are not provided by the integration foundation. Human/orchestrator approval must remain explicit before any future integration execution.

## Development rule

Before implementing a future milestone, inspect the actual implementation and tests for the affected area. Treat this architecture as a description of current behavior plus clearly labeled direction—not as evidence that planned behavior already exists.

## Chat Context (Task 57)

Added caller-supplied context bounded to 8192 UTF-8 bytes per conversation, with atomic replacement, isolation, and clearing on successful closure; no retrieval, persistence, provider calls, or chat API/UI.

The Core service has no authenticated principal contract; only trusted in-process callers may supply and read context and must enforce authorization and relevance before calling it. No external context endpoint is exposed. Context is untrusted text, excluded from conversation snapshots, and cannot fetch runtime resources. Failed validation or unsuccessful closure preserves existing context. Successful closure removes service-owned context; caller-held strings cannot be revoked. Retention is in-memory for the open conversation or service lifetime. The Task 53 portal remains file-based and read-only.

## Corporation Chat (Task 58)

Added local Corporation Chat CLI commands with explicit coordinator Agent identity, Orchestrator-mediated replies, bounded prompts, isolated conversation history, and recorded response failures; no automatic Task creation or Web/API chat.

In the trusted local shell: `chat start <id> <agent>`, `chat send <id> <text>`, `chat get <id>`, and `chat close <id>`. The Application Service owns the organization chat service. Runtime Corporation identity is required; coordinator identity stays fixed. Sending is explicit and may call the configured provider through Orchestrator.run_agent. No Task is created or executed. Messages and replies are limited to 8192 UTF-8 bytes; provider prompt input uses at most 16 recent completed messages and rejects totals over 32768 bytes before recording a new message. History remains in-memory until the service ends; persistent conversation memory is future work. JSON serialization separates supplied data structurally but is not a guarantee against model prompt injection; replies never trigger tools or execution. Provider failures expose only a generic error and mark the submitted message failed. No browser authentication or HTTP permissions are added. The Task 53 portal remains read-only and file-based.

## Corporation Task Creation via Chat (Task 59)

Added immutable chat-to-Task reviews of completed user messages with explicit project and Agent routing; human CONFIRM creates a pending persisted Task without execution, and consumed reviews cannot be replayed.

Local commands: `chat review-task <chat-id> <message-id> <title> <project-id> <agent-id>` prints the source text, title, explicit Agent route, project, and pending initial status. `chat confirm-task <review-id> CONFIRM` is the separate human confirmation step. IDs appear with chat messages. Only completed user messages from an open conversation can be reviewed; model replies are not Task sources. Reviews capture immutable fields and validate existing projects/Agents before review and again before confirmation. Creation uses the existing Orchestrator persistence and TASK_CREATED log; ordinary Task inspection exposes subsequent lifecycle. No provider or Task execution occurs during review/confirmation. The trusted local operator is the reviewer; there is no Web/API approval or identity administration. Reviews are in-memory and consumed before creation, including uncertain persistence/logging failures, requiring human inspection rather than automatic retry. This is not a transactional recovery guarantee. The file-based read-only Task 53 portal and default-deny HTTP authentication remain unchanged.

## AI Activity Visualization (Task 60)

Added permission-aware Task lifecycle progress to the Activity page using protected Task detail reads, with explicit pending/running/completed/failed states, separate access errors, stale-response rejection, and no fabricated provider telemetry.

At `/ui/activity`, enter a Task ID in the existing filter and refresh to inspect its current execution lifecycle and assigned Agent. This uses only `GET /api/tasks/{task_id}` with `task:read`; activity records independently require `activity:read`. Authentication remains fail-closed and browser sign-in is not configured. Progress is a manually refreshed snapshot, not a stream, percentage, queue position, or provider health claim. Failed requests clear old progress; changing the selected Task invalidates in-flight responses. Task result/error contents are not displayed in this panel. Synchronous local chat has no browser telemetry; no chat progress API or provider instrumentation is added. No runtime, persistence, or dependencies changed. The Task 53 portal stays file-based and read-only; public docs remain separate from runtime.

## Memory Architecture (Task 61)

Defined immutable scoped memory records with explicit owners, note/summary types, required provenance and expiry, retention opt-in, and exact owner/scope retrieval checks without automatic sharing or storage.

MemoryRecord supports explicit conversation or project scope; owner, scope ID, record ID, and source ID are nonempty bounded identifiers. Content is caller-supplied untrusted text capped at 8192 UTF-8 bytes. Records require retention_opt_in=True and timezone-aware creation/expiry timestamps with expiry after creation. require_memory_access requires the exact owner and scope, rejects expired records at the expiry boundary, and accepts an explicit clock for deterministic testing. It has no administrator bypass, implicit cross-scope lookup, or sharing. Trusted application callers must bind owner identity to their authenticated/local authority and validate source/resource references; these Core contracts do not authenticate a supplied string. No conversation records are automatically converted to memory and no storage, database migration, HTTP/UI route, provider call, or retention cleanup is added. Existing legacy Agent/Project stores remain separate and are not claimed to enforce these new rules. Task 62 implements explicit persistent conversation notes; knowledge sharing remains unavailable.

## Persistent Conversation Memory (Task 62)

Added explicitly opted-in SQLite conversation memory with immutable bounded records, owner/conversation-scoped retrieval, expiry enforcement, explicit deletion and scoped cleanup, and corrupt-data rejection; chat messages are never saved automatically.

ConversationMemoryStore uses an additive conversation_memory table in the existing SQLite database; no legacy rows or schemas are replaced. The application chat service exposes explicit retain_message for completed messages with caller-supplied memory ID, trusted owner ID, retention consent, current time, and required expiry. Retained content is a note with source message ID, not an automatic transcript archive. Records are append-only; duplicate IDs cannot overwrite owners or content. Retrieval requires the exact owner and conversation and rejects expired or malformed records. Explicit forget permits withdrawal; purge_expired physically removes only validated expired records in a requested owner/conversation scope. Expiry always denies retrieval even before cleanup; cleanup is explicit, not scheduled. Retained notes survive chat closure until expiry or deletion; service-owned temporary context still clears on closure. Retrieval remains possible after service restart by stable IDs. No HTTP/UI memory route or background capture is added. Trusted callers enforce owner identity and source access. SQLite is plaintext; physical secure erasure and backup deletion are not claimed. Existing legacy Agent/Project stores remain separate. Provider execution and Task creation are not involved.

## Project Knowledge (Task 63)

Added private owner-scoped durable Project Knowledge with explicit Task provenance and verified project associations; reused retention/access rules and added non-destructive Task project-ID persistence without inferring historical links.

CorporationApplicationService.project_knowledge provides explicit retention/retrieval/deletion of project-scoped MemoryRecord notes or summaries. The source ID must identify a registered Task with the same verified project ID, checked both at retention and retrieval. Exact owner/project access and mandatory consent/expiry reuse the scoped memory policy. Project knowledge is private to its explicit owner, not shared automatically with all Project users. SQLite storage shares controlled mechanics with conversation memory but uses a distinct project_knowledge table, leaving legacy project_memory unchanged. No automatic extraction, provider call, Task execution, UI, or HTTP endpoint is added. The necessary project-ID persistence prerequisite uses an additive nullable tasks.project_id column and saves/reloads/updates known associations. Historical rows remain null because their original project association was never stored; knowledge linking to such Tasks fails closed instead of inferring ownership. Existing rows are preserved and the migration is idempotent. The Task 53 documentation source remains file-based and read-only.

## Corporation Knowledge (Task 64)

Added explicit owner-approved Corporation Knowledge publication to bounded named-reader lists, with copied provenance and inherited expiry, deny-by-default scoped reads, owner revocation/withdrawal, and atomic durable publication; private memory is never shared automatically.

CorporationApplicationService.corporation_knowledge requires configured Corporation identity. Publishing explicitly retrieves an owner-authorized conversation or Project memory source through existing services; Project/Task provenance is checked before publication. Publication requires separate publication_opt_in=True and 1–100 distinct named reader IDs; wildcard access and implicit membership/admin access are unavailable. Content, source memory ID, scope/resource reference, original source timestamp, type, and expiry are copied into an immutable snapshot. Publication cannot extend source expiry. Records, provenance, and grants commit together or roll back together in additive SQLite tables. Reads require the exact Corporation plus the owner or a named reader and reject expired/corrupt records. Only the owner may revoke an individual grant or withdraw the entire publication, including after expiry. Caller-held copies cannot be revoked. A publication is a separately consented copy: deleting its private source does not automatically withdraw the publication, and withdrawing publication does not delete its private source. Trusted callers bind actor IDs to actual authenticated/local identity. No knowledge HTTP/UI routes, provider calls, Task execution, automatic promotion, or scheduled cleanup are added. Legacy stores and the read-only file-based Task 53 portal remain unchanged.

## Memory Management UI (Task 65)

Added authorized memory inspection, owner correction and explicit retention, revision-conflict protection, expired-record removal, and owner withdrawal of immutable published knowledge through scoped API services and a browser page; default authentication remains fail-closed.

The /ui/memory page uses protected /api/memory services. memory:read permits scoped inspection; memory:manage also requires record ownership for mutations. The server binds owners/readers to authenticated identity and denies access by default. Lists contain metadata only (50 records by default, maximum 100), including expired records whose content cannot be read or restored. Active private notes can be corrected or retained with explicit consent and a future timezone-aware expiry; source references remain intact and stale revisions are rejected. Published knowledge is an immutable snapshot: named readers can inspect it, while its owner can withdraw it. Removing a private source does not withdraw separately consented publication; deletion cannot revoke caller-held copies or backups. This page adds no automatic capture, provider execution, semantic retrieval, or changes to the file-based read-only Documentation Portal. Browser authentication remains unconfigured.

## Context Retrieval (Task 66)

Added bounded deterministic Context Retrieval over explicitly selected authorized memory scopes, with source references, provenance, expiry and revision traces, live scoped access rechecks, and explicit candidate/result/byte limit indicators.

ContextRetrievalService is available through application_service.context_retrieval(). Trusted callers supply the authenticated actor, one exact conversation/project/Corporation scope, a timezone-aware current time, and a keyword query. It uses case-folded word matching, ranks by distinct matched terms with memory-ID tie breaking, and does not broaden access or scope. Queries are limited to 1024 UTF-8 bytes and 32 distinct terms; retrieval scans at most 100 authorized records, returns at most 10 matches (default 5), and bounds serialized hit payloads to 32768 bytes. Candidate-limit reporting is conservative when exactly 100 records are returned; results are not a complete-history or semantic-search guarantee. Expired records are excluded, project associations are verified, named-reader grants are rechecked, and corrupt data fails explicitly. Immutable results carry original references, expiry, and revision; caller-held snapshots cannot be revoked and must be retrieved again before later use. Retrieved content remains untrusted knowledge, not instructions. No provider execution, automatic chat injection, new HTTP/UI route, dependency, or change to the file-based read-only Documentation Portal is added.

## Improved Task Planning (Task 67)

Added immutable review-only Task plans for explicitly selected Tasks in one Project, with validated dependency graphs and deterministic order, actual lifecycle snapshots, authorized traced context, and caller-defined outcome/evidence criteria that remain unverified.

The application_service.task_planning() service builds in-memory review plans for 1 to 50 existing Tasks within one exact Project. Dependencies must be explicitly selected; missing Tasks, duplicate/self dependencies, cross-project links and cycles are rejected. Each Task requires 1 to 10 bounded expected-outcome, verification-method and expected-evidence criteria. Completed lifecycle status never proves those criteria: all plan outcomes remain unverified. Plans show deterministic dependency order and currently unmet prerequisites, but do not enforce execution eligibility. Optional context requires an explicit query, authorized scope and resource ID through Task 66; Project context must match the planned Project. Trusted callers authorize selected Tasks and bind actor identity. Plans and context are immutable snapshots and must be rebuilt before later use. No Task creation, execution, provider call, persistence, queue, new HTTP/UI route or change to the file-based read-only Documentation Portal is added. Existing Task summaries and execution behavior are preserved.

## Resource Manager (Task 68)

Added explicitly configured local execution-slot accounting with immutable global/provider/model capacity snapshots, atomic allocation/release, exhausted-capacity rejection, and unknown hardware/health reporting; existing execution paths remain unchanged.

application_service.resource_manager(limits) configures a local manager once; later calls return the same instance. No limits are inferred and an unconfigured manager is unavailable. ResourceLimits requires a global limit plus immutable unique provider and exact provider/model limits (1 to 100 entries each); every slot limit is an integer from 1 to 10000. Configured providers must be registered; model identifiers are configuration, not claims of discovered model availability. Explicit allocations consume one global, provider and model slot atomically; unknown/unconfigured resources, duplicate IDs and exhausted capacity are rejected without changing counters. Release requires an active allocation and remains possible after provider removal. Snapshots distinguish provider registration from unknown health and hardware capacity. Allocation IDs cannot be reused within this manager and lifetime ID history is bounded to 10000; accounting is in-memory and is not preserved across restart. Trusted application callers configure and manage allocations. Existing executions outside the manager are not tracked or gated; no automatic integration, queue, scheduler, hardware polling, provider call, persistence, new API/UI, dependency or change to sandbox policies or the read-only Documentation Portal is introduced.

## Execution Queue (Task 69)

Added a durable Corporation-scoped FIFO execution queue with atomic explicit claims, immutable lifecycle snapshots, persisted Task-outcome acknowledgement, and confirmed human resolution; interrupted claims are never automatically replayed.

application_service.execution_queue() exposes the configured Corporation queue through the Orchestrator. Additive SQLite storage preserves insertion sequence, unique entry/Task membership and claim IDs. Trusted callers explicitly enqueue existing pending Tasks, inspect bounded FIFO snapshots (default 50, maximum 100), claim the next pending entry, and acknowledge a matching worker/claim only after the persisted Task is completed or failed. Queue lifecycle is separate from Task lifecycle and never proves acceptance criteria. A FIFO head whose Task changed externally blocks new claims until explicit human resolution. Claimed entries survive restart and are not replayed; abandon requires literal confirmation and a bounded recorded resolution, preserves claim metadata, and does not alter the Task. Duplicate membership, duplicate claims, invalid transitions, backwards/naive times and malformed stored records are rejected. Queue entries and Task membership are retained; this foundation provides no cleanup, requeue, retry, automatic worker, provider call, scheduling, parallel runtime, new API/UI or exactly-once external-execution guarantee. Existing executions are unchanged, caller authority is enforced by the trusted application boundary, and the Documentation Portal remains file-based/read-only.

## Controlled Concurrency (Task 70)

Added an explicitly configured local controlled-execution path using existing Orchestrator routing and global/provider/model slot budgets, with duplicate-Task admission protection, nonblocking capacity rejection, and finally cleanup on success or failure; direct execution remains unchanged.

After explicit resource configuration, application_service.execute_controlled_task(task_id) admits pending Tasks only. Missing Tasks and existing RoutingError failures consume no capacity: dry-run routing happens before reservation. Admission coordinates duplicate Task IDs within one controller and reserves global/provider/model slots before invoking the existing Orchestrator. Finally cleanup releases allocations after success, provider failure or runtime failure; no automatic retry occurs if persistence failure leaves a Task running. The controller is constructed during resource configuration before concurrent calls begin. It coordinates only its local process/service instance and provides no distributed or multi-process coordination. Legacy/direct execution paths are intentionally outside its coordination. Registry and resource-configuration mutations performed outside the controlled path are not synchronized; correct use requires completing explicit resource configuration before concurrent controlled calls and keeping external configuration changes coordinated by the caller. The controlled path adds no registry/configuration mutation, queue worker, retry/replay, dependency enforcement, provider-routing override, API/UI or new dependency. Tests use deterministic fake providers; no live Ollama is required. Public docs remain separate and the Documentation Portal stays file-based/read-only.

## Model Resource Awareness (Task 71)

Added bounded immutable model resource assessments from configured global/provider/model admission slots and provider registration, including the existing historical allocation-ID budget; snapshots reserve nothing and keep hardware feasibility and provider health unknown.

application_service.assess_model_resources accepts an explicit immutable tuple of 1 to 100 unique ModelCandidate values and preserves caller order without ranking candidates. Assessments expose registered/missing providers, configured/unconfigured global/provider/model Capacity values, fresh-unique-ID admission eligibility and explicit exhaustion/unknown reasons. Capacity is configured admission accounting, not physical compute feasibility. ResourceSnapshot now has a trailing optional allocation_id_history_capacity field; old positional construction remains compatible and absent history is unknown/ineligible. ResourceManager populates it atomically using the existing Capacity abstraction and authoritative historical ID count. Release restores active execution slots but never restores the monotonic distinct-ID budget; at the existing 10000-ID limit, allocation_history_exhausted prevents eligibility even with all active slots free. No allocation/release rule or earlier snapshot field changed. Task 71 consumes public snapshots and public provider registration, never private manager fields or duplicate history arithmetic. Eligibility concerns only a fresh unique allocation ID; reused IDs remain prohibited by Task 68. Assessments are non-reserving local snapshots that may become stale immediately. Refresh before decisions; Task 70 remains authoritative for atomic admission. Eligibility does not guarantee execution, hardware feasibility, provider health, model loading or preference over another model. No hardware polling, provider call, Agent assignment change, Task rerouting, intelligent selection, scheduling, queue worker, retry, API/UI or new dependency is added. Existing direct execution remains unchanged.

## Provider Availability (Task 72)

Provider availability is optional and checked only on explicit application-service request through the registered provider. Providers without a supported check return an immutable UNKNOWN result; registration never implies availability. Ollama checks the lightweight service tags endpoint with a bounded timeout and does not generate text. Expected request/status failures become sanitized UNAVAILABLE results; unexpected programming defects remain visible. Results describe provider/service availability only—not installed-model readiness, inference success, hardware feasibility, or configured Task resource capacity. Checks do not execute Tasks, reserve Task 70 slots, or modify Agent/model assignments. Task 71 configured admission-slot awareness remains separate.

## Intelligent Model Routing (Task 73)

`application_service.select_model_candidate` accepts an immutable tuple of up to 100 unique model candidates wrapped with caller-supplied capability declarations, policy tags, Task 72 availability state, and optional non-negative finite `Decimal` cost estimates. Caller-supplied constraints may require capabilities/tags, restrict provider IDs, set a maximum cost, and explicitly opt into UNKNOWN availability. The first eligible candidate in caller order is selected; there is no ranking or hidden default preference. A cost limit excludes candidates without an estimate; without a cost limit, estimates do not affect eligibility. Cost estimates and policy/capability declarations are trusted caller inputs, must share one caller-defined unit, and are not independently verified. Missing providers and UNAVAILABLE candidates are always excluded. Task 71 admission assessment accompanies each candidate but does not filter selection; hardware feasibility remains unknown. This is a review-only result: it does not alter Agent/model assignments, execute Tasks, call providers, or make Task 70 admission decisions.

## Multi-Agent Collaboration (Task 74)

`application_service.task_collaboration()` exposes a local, in-memory, caller-driven collaboration record service for an existing pending Task. The caller explicitly supplies 2–10 distinct registered Agents in order; each participant role must exactly match that Agent's registered role. The first participant is active, and each may hand off once to only the next listed participant. The final participant explicitly completes or fails the collaboration. Each action names the acting Agent, and non-active participants cannot impersonate the current participant. The trusted caller owns the initial context; the collaboration session owns the shared append-only record; and each handoff/completion entry is attributed to the active Agent. Participant failures use explicit reason codes and terminate the collaboration without changing Task status.

Collaboration only records supplied content; it never calls Providers, recursively invokes Agents, creates Tasks, changes assignments, or changes Task lifecycle. Existing TaskLogger records start, handoff, completion, and failure metadata against the Task without putting context/output text in audit logs. Collaboration state/context is in-memory and is lost on process restart; durable audit events do not contain enough data to reconstruct it. The trusted Core/Application Service boundary remains responsible for caller authorization; no collaboration API/UI or new persistence is added.

## System Monitoring (Task 75)

`application_service.monitor_system()` returns an on-demand immutable report over current local Task status, Provider registration, and configured resource-capacity snapshots. It reports failed Task IDs (up to 100, with an omitted count) and exhausted configured capacity as factual signals, without adding alert rankings or policy thresholds. Provider availability remains UNKNOWN because monitoring performs no Provider probes; hardware feasibility also remains unknown. Unconfigured capacity is reported as absent. Task error text is not included. Sources are sampled independently, so observations can change while the report is being collected and the report does not reserve capacity. Reports are not cached or persisted, and monitoring does not execute Tasks, modify assignments, poll in the background, remediate, or add API/UI.

## Error Detection (Task 76)

Task failures caught at the routing and Agent/Provider execution stages are stored as `routing` or `execution` categories. These identify the stage where failure was caught, not its root cause. The additive SQLite migration marks historical failed Tasks without a category as `unknown`; in-memory failed Tasks with no category also report `unknown`. `application_service.detect_failures()` returns immutable, bounded summaries containing Task IDs and category codes only, with total and omitted counts. It never exposes Task.error or exception/log message text. It does not change Task lifecycle, retry, or execute work.

## Diagnostic Agent (Task 77)

`application_service.diagnose_failure(agent_id, failure, evidence)` performs one call through the caller-selected registered Agent, using only a current Task 76 failure record and 1–20 explicit caller-supplied sanitized evidence items. The trusted caller is responsible for removing secrets and exception text before constructing `DiagnosticEvidence`. Each evidence item is bounded to 8192 UTF-8 bytes and total evidence to 32768 bytes. The bounded structured response permits at most 10 findings and unknowns; every finding must cite reference IDs present in that request. The result contains the failure and selected Agent IDs, cited findings, and unknowns—not the supplied evidence itself. Citations are checked for reference identity, not truth; generated diagnostics require human review. No Task.error, logs, or other records are retrieved automatically. No Task creation/execution, assignment changes, retries, remediation, persistence, or API/UI are added. Tasks 78+ maintenance proposals and automated changes remain separate.

# ERSELMETZ AI CORPORATION — Current Architecture and Roadmap

## Product definition

**ERSELMETZ AI CORPORATION is an actual software system implementing a virtual/simulated AI organization.** “Virtual/simulated organization” describes the domain being modeled; it does not mean that the software system itself is imaginary.

This document separates the implemented Tasks 1–50 foundations from future architecture. Source code is authoritative if implementation and documentation disagree.

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
Tool / ToolRegistry
ApprovalRequest / ApprovalRegistry
ClientRequest / BusinessLayer adapter
```

The CLI also uses `CorporationApplicationService` for application operations. This interface-neutral service is the application boundary for Corporation status, Employee, Agent, Provider, Model assignment, Task, Project, and Activity use cases. It coordinates existing management services and the Orchestrator and returns summaries rather than exposing registries as an interface contract. FastAPI resource routes use this boundary; the service has no HTTP, CLI, or database-driver logic, and the existing Core remains responsible for domain behavior and persistence.

The FastAPI application in `app.api` serves a public dashboard at `/ui`, Employee Management at `/ui/employees`, and app-owned static assets below `/ui/static`. Browser modules request protected Corporation data only from existing API endpoints; they do not access registries, SQLite, providers, or other Core internals. `/` and `/health` remain public; resource routes use the shared application-service dependency and do not directly manipulate `TaskRegistry`, `ProjectRegistry`, `TaskLogger`, or other internal registries. Authentication uses an injectable backend and rejects by default. Authorization checks the authenticated principal's required permission. A production identity provider and browser sign-in/session implementation are not configured; UI pages therefore report authentication-required, forbidden, or other failures and never represent failures as empty data. The public Node.js documentation site in `docs/` remains a separate application.

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

Management pages use same-origin browser requests and preserve API authorization. No browser sign-in/session mechanism is configured, so the relevant authenticated session and distinct read/manage permissions remain prerequisites for protected data/actions. Failures retain distinct authentication, permission, validation/conflict, missing-record, and general states. Tasks 51–54 remain planned and cover Project, Activity, Corporation documentation, and updates interfaces.

Task 50 adds Task Management at `/ui/tasks`. The page uses `GET /api/tasks` and `GET /api/tasks/{task_id}` (`task:read`), `POST /api/tasks` (`task:create`), and the existing non-mutating `POST /api/tasks/{task_id}/dry-run` (`task:read`). Creation accepts only title, description, optional project ID, and at most one Agent ID, role, or capability selector; the API generates Task ID and status. The API has no Task DELETE route or lifecycle mutation actions, and the UI does not invent them. Project association persistence remains limited by the existing TaskRegistry. Tasks 51–54 remain planned.

Other resource permissions are similarly minimal: `corporation:read`, `employee:read` / `employee:manage`, `agent:read`, `provider:read` / `provider:manage`, `model:read` / `model:manage`, `project:read` / `project:create`, and `activity:read`. These are route permission requirements, not a configured user/role management system. The default authentication backend rejects requests until an application supplies an authentication backend.

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

SQLite currently stores Tasks, Projects, task logs, agent memory, and project memory in the configured database file. **Known limitation:** TaskRegistry does not persist/reload `project_id`, even though it is present on the Task model. Employee, Agent, Provider, model assignment, approval, tool, Corporation, and Node registries are not persisted as complete administration subsystems.

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

## Tasks 1–50 completion scope

Tasks 1–50 are complete as the current foundation. Their implemented areas include:

- Task and Project domain/registry foundations.
- Task lifecycle, orchestration, logging, and SQLite persistence.
- Agent, Employee, Provider, and Model domain boundaries.
- Agent capability lookup and Employee-role lookup.
- Ollama execution integration and Provider interface.
- Employee and Provider management foundations.
- Model assignment/replacement management for the in-memory Agent.
- Tool abstraction and registry foundation.
- Human approval request/status foundation.
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

This is a grouped capability summary, not a claim that every long-term capability is production-complete. See limitations above; particularly, project ID persistence is incomplete, registry/configuration persistence is limited, tools and approvals are not wired to task execution, integration proposals are not persisted, there is no integration executor, and only Ollama is implemented as a provider. Tasks 51–54 cover future Project, Activity, Corporation documentation, and updates interfaces; they are not part of Task 50.

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
- Open-source coding/editing, repository mapping, terminal, browser/computer-control, voice, and Git/GitHub workflow integrations.
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

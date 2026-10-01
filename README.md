# ERSELMETZ AI CORPORATION

**ERSELMETZ AI CORPORATION is an actual software system implementing a virtual/simulated AI organization.** The organization is the system's domain model and operating concept; the software implements its current capabilities.

The current application includes a local Python command-line system and a FastAPI interface. It models a Corporation and installation Node, an Orchestrator, Employees, technical Agents, a Provider/Model execution boundary, persisted Tasks, deterministic routing, and dry-run inspection.

> **Implementation status:** Tasks 1–63 are complete as foundations. Tasks 27–30 add public GitHub discovery, bounded source analysis/learning, evidence-backed evaluation, and proposal generation; Tasks 31–33 add sandbox foundations and a Docker execution backend; Tasks 34–36 add controlled source staging, verified sandbox binding, and immutable execution preparation without executing staged source. Tasks 37–45 establish the Application Service/API foundation and authorized Corporation status, Employee/Agent, Provider/Model, Task, Project, and Activity APIs. Task 46 provides the FastAPI-served Web UI foundation; Task 47 adds a read-only executive dashboard; Task 48 adds Employee Management; Task 49 adds Provider and Model Assignment management; Task 50 adds Task Management; Task 51 adds Project Management; Task 52 adds the read-only Activity / Logs UI; Task 53 adds the read-only Documentation Portal over approved Markdown files; Task 54 adds a protected, read-only Corporation Updates page backed by a manually curated manifest; Task 55 adds in-memory Conversation and Message records with a controlled message lifecycle. Task 56 adds an in-memory Individual Employee Chat Core service with an explicit Employee/Agent target and immutable conversation snapshots. Individual Employee Chat still records messages and outcomes explicitly. Task 57 adds bounded caller-supplied context; Task 58 adds local Corporation Chat with explicit Orchestrator-mediated replies; Task 59 adds reviewed and confirmed creation of pending Tasks; Task 60 adds permission-aware Task lifecycle snapshots on the Activity page. Explicit owner-scoped persistent conversation notes are available with consent and expiry. Conversation Web API/UI and automatic transcript archiving remain unavailable. Browser authentication is not configured, so protected data and actions require an authenticated session with the relevant permissions. Tasks 64–100 remain planned. These remain foundations, not production-complete subsystems.

## Current architecture

```text
Corporation identity
└── Node / installation identity
    └── Runtime Context (validated Corporation + Node IDs)

Browser / API client
  ↓
FastAPI
  ├── Public Web UI dashboard (/ui) + app-owned static assets
  └── Protected API routes → Authentication → Authorization
                                              ↓
                              CorporationApplicationService
                                              ↓
                                     Corporation Core
                                     ├── Orchestrator
                                     ├── Task/Project registries
                                     └── Task Router → Agent → Provider → Model
```

The `/ui` dashboard is a public presentation route. Its browser module requests Corporation data only from the existing protected API read endpoints; it does not read or change Core data itself. Each API keeps its existing authentication and permission checks. The default authentication backend rejects requests, and no browser sign-in/session integration is configured, so the dashboard reports authentication-required, forbidden, and other loading failures instead of treating them as empty results. Existing list APIs provide the displayed complete list counts; task timestamps and provider availability are not provided, so the dashboard does not claim recent tasks or provider health. Future UI actions and pages must preserve the same boundary. The standalone public Node.js documentation site in `docs/` remains a separate application and is not the Corporation Web UI.

Employee Management is served at `/ui/employees`. It lists and views Employees with `employee:read`, and creates/removes them using the existing endpoints requiring `employee:manage`. Employee creation requires a caller-supplied ID, name, and role; responsibilities are optional. The API does not accept Agent association changes through this workflow. Removal requires explicit confirmation. Browser sign-in is not configured, so these protected operations require an authenticated session; the page does not bypass API permissions.

Provider and Model Management is served at `/ui/providers`. It lists and views Providers, creates them using only the existing `id` / `name` request, and removes them after confirmation. Provider reads require `provider:read`; create/delete require `provider:manage`. The page also lists and views Agent model assignments and replaces an assignment using only `provider_id` / `model_id`; reads require `model:read`, and replacements require `model:manage`. Assignment records identify Agents by `agent_id`; the API provides no corresponding Employee/name field. Provider responses expose only ID and configured type. No credentials or arbitrary provider configuration are accepted or displayed. Both workflows call the existing same-origin protected APIs; browser sign-in/session authentication is not configured.

Task Management is served at `/ui/tasks`. It lists and displays Task records, creates Tasks using the existing title/description and optional project/routing fields, and offers the existing read-authorized routing dry-run. Reads and dry-run require `task:read`; creation requires `task:create`. The API generates Task IDs/status. At most one of `agent_id`, `role`, or `capability` may be selected for creation. There is no Task deletion endpoint or lifecycle mutation API, so the UI offers neither deletion nor start/complete/cancel actions. The dry-run previews routing without executing an Agent/Provider or changing Task state. The known TaskRegistry project-association persistence limitation still applies. Browser sign-in/session authentication is not configured.

Project Management is served at `/ui/projects`. It lists and displays Projects using `GET /api/projects` and `GET /api/projects/{project_id}` (`project:read`), and creates Projects using `POST /api/projects` (`project:create`) with only `name` and optional `description`. The API generates the Project ID and status. The UI does not offer deletion or lifecycle actions because no such Project API endpoint exists. Failed loads clear stale Project data and are shown separately from an empty list. Browser sign-in/session authentication is not configured.

Activity / Logs is served at `/ui/activity`. It displays only the fields returned by `GET /api/activity` (`activity:read`): record ID, Task ID, event, and timestamp. The page uses the supported `limit` parameter (1–100; default 100) and optional `task_id` filter, clearly states that results are bounded and not a complete history, and offers manual refresh. The API has no detail endpoint and omits message text; the UI adds no detail or mutation route. Failed refreshes clear previously displayed records. Browser sign-in/session authentication is not configured.

The internal Documentation Portal is served at `/ui/documentation`. Its protected `GET /api/documentation` and `GET /api/documentation/{document_id}` routes require `documentation:read` and use the documentation application-service boundary. The default file source exposes only top-level UTF-8 Markdown files in the repository-root `corporation_docs/` directory, with validated filename-stem IDs; it rejects invalid IDs and symlink/path escapes. The browser displays Markdown as text and cannot access the filesystem directly. This internal portal is separate from the standalone public documentation website in `docs/`, and is not an AI-managed knowledge system.

Conversation Foundation defines Core-only in-memory `Conversation` and `Message` records. Messages transition from pending to completed or failed; an open conversation can be closed only when it has no pending messages, and a closed conversation rejects additional messages. These records are not persisted, do not call a Provider, and are not connected to Tasks. Task 56 adds `EmployeeChatService` over those records. Callers supply a conversation ID and exactly one Employee ID or Agent ID; an Employee must have an assigned, registered Agent. The service captures fixed Employee/Agent IDs and an explicit employee or agent scope, records ordered messages and explicit lifecycle outcomes, and returns immutable snapshots. It has no role-based routing, retargeting, automatic replies, or runtime API/UI integration. Task 57 adds explicit caller-supplied context: up to 8192 UTF-8 bytes per conversation, atomically replaced or cleared with empty text and deleted on successful closure. Trusted Core callers must supply relevant, authorized text without secrets or internal runtime data. Context is excluded from conversation snapshots, never retrieved automatically, and never treated as executable instructions. Caller-retained strings cannot be revoked. Reviewed chat-to-Task conversion is available locally as described below.

The CLI also uses CorporationApplicationService for application operations.

SQLite stores tasks, projects, task logs, agent memory, and project memory.

The FastAPI resource routes call `CorporationApplicationService`; they do not directly access Core registries. Current API resources include Corporation status; Employee/Agent; Provider/Model assignment; Task; Project; and read-only Activity. The Activity API exposes bounded task-log summaries and omits message text. The Task API supports `GET /api/tasks`, `GET /api/tasks/{task_id}`, `POST /api/tasks`, and `POST /api/tasks/{task_id}/dry-run`. Creation delegates ID generation to Core and preserves the existing project and routing requirements. Responses use explicit schemas and omit internal Task fields. The dry-run inspects routing without executing an Agent/Provider or mutating Task state. There is no HTTP task-execution endpoint or lifecycle-mutation endpoint.

API authentication and authorization are injectable foundations. The default authentication backend rejects requests; a production identity/authentication provider is not configured here. Protected routes require their declared permissions. See [Current architecture and roadmap](./ARCHITECTURE.md) and the [public documentation site](./docs/index.html) for the current API boundary and broader limitations.

These are distinct concepts: **Employee != Agent != Provider != Model**.

- A **Corporation** identifies the organization. A **Node** identifies a software/physical installation and references its Corporation. `RuntimeContext` carries both IDs; startup uses configured-in-code local IDs and validates that the Node belongs to the Corporation.
- An **Employee** is an organizational identity with a role and responsibilities. It may be associated with an **Agent**, the technical execution identity carrying capabilities, permissions metadata, and provider/model identifiers.
- A **Provider** implements the interface used to generate a response. The current runtime registers an **Ollama** provider; the provider registry is in-memory. An Agent's **Model** is a configured identifier passed to that provider.
- A **Task** has a lifecycle (`pending`, `running`, `completed`, `failed`), an optional explicit `assigned_agent`, and optional persisted `required_role` and `required_capability`.
- The **Task Router** performs deterministic routing; the **Orchestrator** creates tasks, routes and executes them, records task logs, and supports dry-run results.
- **Tools** and **Human Approval** have small standalone foundations, described under [Current capabilities and limitations](#current-capabilities-and-limitations); they are not integrated into task execution.

## Current routing behavior

Task creation preserves the request rather than resolving employee roles or capabilities immediately:

| Request | Stored task routing fields |
|---|---|
| `task "..." --agent local_worker` | `assigned_agent = local_worker` |
| `task "..." --role "Local AI Worker"` | `required_role = "Local AI Worker"` |
| `task "..." --capability summarization` | `required_capability = summarization` |

Role and capability requirements are nullable SQLite columns, migrated additively when absent, and loaded back into Tasks. They are not converted into `assigned_agent` during creation.

The router's priority is:

1. Explicit `assigned_agent`
2. `required_role`, resolved against registered Employees and their associated Agents
3. `required_capability`, matched against Agent capabilities
4. `RoutingError` if no suitable Agent can be found

If a required role has no matching Employee, routing may continue to a requested capability; a matching Employee without an Agent is an error. Routing is deterministic and registry-order based. There is **no AI/LLM-based agent selection and no automatic fallback Agent**.

`dry-run TASK-ID` routes from the stored Task requirements and reports the selected Employee/Agent, Provider, Model, route, and ready status without invoking the AI provider or changing Task state. A CLI routing option can override routing for that dry-run only; it does not update the stored Task.

## Current capabilities and limitations

Implemented foundations include:

- Task creation, execution lifecycle, task logs, and SQLite task persistence.
- SQLite persistence for Projects, task logs, and agent/project memory.
- Agent registration and capability lookup; Employee registration, lookup by exact role, and in-process Employee management.
- Provider registry and Provider/Model management commands; Ollama is the only implemented provider integration.
- Deterministic explicit-Agent, Employee-role, and Agent-capability routing.
- Task 24 routing CLI options and Task 25 persisted routing requirements, additive schema migration, restart loading, and non-mutating dry-run overrides.
- Corporation/Node identity models, in-process registries, runtime context validation, and startup wiring.
- A client request model and a small business-layer adapter that turns requests into Tasks.
- A `Tool` abstract base class and in-memory `ToolRegistry`.
- In-memory approval request objects and a registry with pending/approve/reject state transitions.
- An Integration Proposal domain model, extensible source descriptor, deterministic lifecycle, in-memory registry, and approval-gated execution record.
- Public GitHub repository metadata discovery through the official public REST API, with bounded README excerpts and structured discovery errors.
- Bounded public GitHub structure/documentation analysis, returning typed facts and evidence-linked observations from a previously discovered repository.
- Evidence-backed external source evaluation that identifies strengths, concerns, unknowns, and follow-up requirements without ranking or approving a project.
- An in-memory integration sandbox foundation with explicit proposal/discovery linkage, restrictive isolation-policy metadata, and validated lifecycle states; it does not execute code or enforce isolation.
- Sandbox execution request/result models, executor/backend abstractions, request-policy validation, and an unavailable-backend response; no backend executes work.
- An optional Docker sandbox backend with an explicit digest-pinned image allowlist, isolated container settings, resource/time limits, and deterministic cleanup; the Docker Python SDK is optional and must be installed explicitly.
- Bounded staging of validated public GitHub source archives into a dedicated temporary workspace outside the project repository; archive paths/types and byte/file/depth limits are checked before writes, with SHA-256 identity metadata and cleanup on failure.
- An in-memory sandbox/source binding that verifies staging, proposal, sandbox, discovery, controlled workspace, and SHA-256 content identity without changing lifecycle state or enabling execution.
- An immutable execution-preparation record that revalidates proposal/sandbox/staging/binding linkage, workspace ownership and integrity, policy metadata, and resource identity without accepting commands or host environment values.

Important current limits:

- Startup configures one local Corporation, one Node, one Employee/Agent, and an Ollama Provider in code. Corporation, Node, Employee, Agent, Provider, and model-management state is not generally persisted as an administration/configuration system.
- The CLI task execution path can invoke the configured Ollama model. Dry-run does not invoke it.
- Tool definitions are not connected to Agents, permissions are not enforced by a tool-execution policy, and there are no concrete built-in tools.
- Approval requests are in-memory only and are not connected to task actions or execution gates.
- Integration proposals, source analyses, evaluations, sandboxes, staging results, and execution records are in-memory only. GitHub source analysis is structural/documentary and bounded; it does not determine suitability. Task 30 can transform earlier evidence into a traceable `PROPOSED` IntegrationProposal. Tasks 31–33 provide sandbox/executor boundaries and optional Docker execution when configured; Task 34 stages bounded GitHub archive contents as inert data in a dedicated temporary workspace. Staging does not execute source, install dependencies, modify the project, or transition proposal lifecycle. SHA-256 supports identity/integrity tracking, not trust or approval. Docker is the only execution backend; there is no host-process fallback. Execution remains sandbox experimentation and does not imply proposal approval or integration.
- The client/business layer is a small API-level adapter, not an HTTP server or a fully integrated external intake workflow.
- `TaskRegistry` now persists and reloads known `Task.project_id` values. Historical Tasks whose associations were never stored retain null project IDs; no association is inferred.
- Node networking/discovery, authentication, authorization, encryption, synchronization, and offline queueing are not implemented.

## Completed and planned work

**Completed:** Tasks 1–34 established the software/domain foundation: task and project management, Agents, Employees, Provider/Model boundaries and management, orchestration and lifecycle logging, tool and approval foundations, client/business request translation, Corporation/Node identity and runtime validation, the command interface, deterministic routing, dry-run, persisted role/capability requirements, the Integration Proposal lifecycle/approval boundary foundation, public GitHub source discovery, bounded GitHub source analysis/learning, evidence-backed external source evaluation, evidence-based proposal generation, sandbox/executor safety boundaries, an optional Docker sandbox backend, and controlled GitHub source staging.

**Future / planned:** dependency installation, sandbox testing, review, human approval workflow, controlled integration, monitoring; richer orchestration; AI-based or semantic routing; advanced Provider/Model selection; multi-Agent collaboration and Agent-to-Agent communication; independent-installation networking and Node Discovery; Authentication, Authorization, and Encryption; Offline Mode, Synchronization, and Conflict Resolution; a Software Reliability Engineer / QA guardian; controlled self-improvement; open-source ecosystem integrations; Git/GitHub workflow automation; and richer Tool/MCP integration.

Task 26 adds internal proposal/source/lifecycle models, an in-memory proposal registry, and a record-only execution object that requires an approved proposal. Task 27 discovers public GitHub repository metadata. Task 28 analyzes a discovered repository's bounded file tree, documentation, and dependency manifests. Task 29 evaluates the supplied discovery and analysis results into evidence-backed strengths, concerns, unknowns, and follow-up requirements. It does not rank projects, provide a numeric score, make an integration recommendation, approve, create a proposal, or integrate anything. These results remain in memory.

The analyzer inspects at most 50 relevant tree files, reads at most four documentation files, limits each retrieved file to 48 KiB, limits retrieved source text to 256 KiB, caps the tree response at 2 MiB, and bounds traversal depth. Limits or truncation are recorded in the result. Facts such as file paths are distinct from evidence-linked observations about purpose/frameworks/potential capabilities.

Evaluation distinguishes evidence-backed findings from unknowns. License metadata is reported without legal advice; dependencies are not installed/resolved; security observations are limited to bounded analyzed material and do not establish that a project is secure. Evaluation is decision support only; integration still requires separate design, review, and human approval.

The implemented stages are **Discover** (Task 27) → **Analyze/Learn** (Task 28) → **Evaluate** (Task 29) → **Proposal Generation** (Task 30) → **Sandbox Foundation** (Task 31) → **Sandbox Execution Boundary** (Task 32) → **Docker Sandbox Backend** (Task 33) → **Controlled Source Staging** (Task 34) → **Sandbox Source Binding** (Task 35) → **Execution Preparation** (Task 36) → **Sandbox Executor** → **Docker Backend**. Staging prepares bounded inert source; binding associates and verifies it against the sandbox; execution preparation resolves registered proposal/sandbox/binding records, validates their linkage and sandbox policy, and rechecks the canonical content digest/file count/bytes. It emits an immutable in-memory readiness record containing source identity and policy metadata, plus a `verify_workspace` operation for a fresh check before future use. The request accepts no command, host environment, or credential reference. None of these preparation steps execute code, transition lifecycle, install dependencies, or run Docker. A matching SHA-256 establishes identity only, not trust or approval. Docker remains the isolation backend for a future separate execution operation; there is no host-process fallback.

### Open-source ecosystem direction

The Corporation should not unnecessarily reinvent mature open-source agent and coding infrastructure. Its intended role is the **governance, organization, orchestration, identity, task management, routing, approval, and coordination layer**. Where appropriate, existing projects and protocols may provide specialized coding/editing, repository mapping, terminal execution, browser/computer interaction, MCP/tool integration, voice/computer control, and Git/GitHub workflows. These are integration directions, not claims of current integration.

### Controlled self-improvement direction

Future improvement should follow a controlled path:

**Discover → Analyze/Learn → Evaluate → Proposal → Sandbox Foundation → Controlled Source Staging → Sandbox Executor → Docker Sandbox Backend → Disposable Container → Test → Review → Approve → Integrate → Monitor**

Unrestricted autonomous self-modification is not the current design. Any future improvement mechanism must be controlled, testable, auditable, and subject to appropriate approval boundaries.

## Documentation

- [Architecture and roadmap](./ARCHITECTURE.md)
- [Public documentation website](./docs/index.html)

The documentation site is a standalone Node.js presentation website in `docs/`. Run it independently with `cd docs` and `npm start` (Node.js 18+); it does not connect to the Corporation runtime.

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

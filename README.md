# ERSELMETZ AI CORPORATION

**ERSELMETZ AI CORPORATION is an actual software system implementing a virtual/simulated AI organization.** The organization is the system's domain model and operating concept; the software implements its current capabilities.

The current application includes a local Python command-line system and a FastAPI interface. It models a Corporation and installation Node, an Orchestrator, Employees, technical Agents, a Provider/Model execution boundary, persisted Tasks, deterministic routing, and dry-run inspection.

> **Implementation status:** Tasks 1–53 are complete as foundations. Tasks 27–30 add public GitHub discovery, bounded source analysis/learning, evidence-backed evaluation, and proposal generation; Tasks 31–33 add sandbox foundations and a Docker execution backend; Tasks 34–36 add controlled source staging, verified sandbox binding, and immutable execution preparation without executing staged source. Tasks 37–45 establish the Application Service/API foundation and authorized Corporation status, Employee/Agent, Provider/Model, Task, Project, and Activity APIs. Task 46 provides the FastAPI-served Web UI foundation; Task 47 adds a read-only executive dashboard; Task 48 adds Employee Management; Task 49 adds Provider and Model Assignment management; Task 50 adds Task Management; Task 51 adds Project Management; Task 52 adds the read-only Activity / Logs UI; Task 53 adds the read-only Documentation Portal over approved Markdown files. Browser authentication is not configured, so protected data and actions require an authenticated session with the relevant permissions. Task 54 remains planned. These remain foundations, not production-complete subsystems.

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
- `TaskRegistry` currently does not persist or reload `Task.project_id`. This known persistence gap remains.
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

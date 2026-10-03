# ERSELMETZ AI CORPORATION

**ERSELMETZ AI CORPORATION is an actual software system implementing a virtual/simulated AI organization.** The organization is the system's domain model and operating concept; the software implements its current capabilities.

The current application includes a local Python command-line system and a FastAPI interface. It models a Corporation and installation Node, an Orchestrator, Employees, technical Agents, a Provider/Model execution boundary, persisted Tasks, deterministic routing, and dry-run inspection.

> **Implementation status:** Tasks 1–100 are complete as foundations. Tasks 27–30 add public GitHub discovery, bounded source analysis/learning, evidence-backed evaluation, and proposal generation; Tasks 31–33 add sandbox foundations and a Docker execution backend; Tasks 34–36 add controlled source staging, verified sandbox binding, and immutable execution preparation without executing staged source. Tasks 37–45 establish the Application Service/API foundation and authorized Corporation status, Employee/Agent, Provider/Model, Task, Project, and Activity APIs. Task 46 provides the FastAPI-served Web UI foundation; Task 47 adds a read-only executive dashboard; Task 48 adds Employee Management; Task 49 adds Provider and Model Assignment management; Task 50 adds Task Management; Task 51 adds Project Management; Task 52 adds the read-only Activity / Logs UI; Task 53 adds the read-only Documentation Portal over approved Markdown files; Task 54 adds a protected, read-only Corporation Updates page backed by a manually curated manifest; Task 55 adds in-memory Conversation and Message records with a controlled message lifecycle. Task 56 adds an in-memory Individual Employee Chat Core service with an explicit Employee/Agent target and immutable conversation snapshots. Individual Employee Chat still records messages and outcomes explicitly. Task 57 adds bounded caller-supplied context; Task 58 adds local Corporation Chat with explicit Orchestrator-mediated replies; Task 59 adds reviewed and confirmed creation of pending Tasks; Task 60 adds permission-aware Task lifecycle snapshots on the Activity page. Explicit owner-scoped persistent conversation notes are available with consent and expiry. Task 72 adds optional, on-demand provider/service availability checks. Task 73 adds explicit review-only model candidate selection using caller-supplied capability, policy, availability, and cost data; assignments and Task execution remain unchanged. Task 74 adds bounded caller-driven Agent handoff records without Provider calls or Task lifecycle changes. Task 75 adds an on-demand read-only report over local Task, Provider-registration, and configured resource-capacity snapshots; it never probes Providers or changes runtime state. Task 76 adds persisted routing/execution-stage failure categories and a bounded safe report that omits raw exception details; historical unclassified failures remain UNKNOWN. Task 77 adds one-call Agent diagnostics over only explicitly supplied sanitized evidence. Task 78 adds caller-authored review-only maintenance proposals linked to diagnostics. Task 79 applies caller-supplied diffs only to explicitly selected files in a disposable temporary copy; it executes no code or tests, changes no source or runtime state, and is not a security sandbox. Task 80 runs caller-selected pytest files against a second temporary copy, returning bounded actual results; test code is not OS-sandboxed. Task 81 adds one-call advisory Agent reviews over bounded caller-supplied sanitized evidence, without automatic file/test retrieval, execution, approval, mutation, or persistence. Task 82 adds a separate Docker-only test path that stages only the registered Task 79 workspace into a bounded ephemeral container with no host mounts, networking, or injected credentials; existing Task 80 host-permission execution remains unchanged. Task 83 adds authenticated in-memory review and approval of an exact maintenance patch/source hash pair. Task 84 creates local Git checkpoint commits on dedicated branches from exactly approved workspaces, requiring separate `maintenance:checkpoint` authorization and a clean worktree/index; it never checks out, pushes, or merges, and recovery uses `git revert`. Task 85 adds a bounded caller-driven record linking existing diagnostics, proposals, patches, passing tests, review evidence, human decisions, and checkpoints without invoking those stages; failed tests terminate a workflow and metadata-only audit events use existing Task logs. Task 86 adds an explicit synchronous MCP client for selected local stdio/in-process tools, with a frozen allowlist, explicit ToolRegistry registration, bounded JSON inputs and text/structured results, sanitized errors, and per-call timeouts; it is not wired to Agents, Tasks, APIs, or UI, and local MCP servers are not OS-sandboxed. Task 87 adds authenticated read-only GitHub repository inspection requiring github:read and an explicit repository allowlist; it reuses public discovery, hides out-of-scope and missing/private repositories, omits README text, and performs no remote writes, Task execution, or Agent calls. Task 88 adds explicit HTTPS research retrieval through an exact-host allowlist and returns immutable untrusted-evidence records; it performs no search, crawling, Agent/Provider calls, or Task execution. Task 89 adds a bounded MCP coding-tool adapter that sends only caller-selected file contents and returns path-limited immutable diff proposals; it applies no patches, executes no code, and triggers no tests/review. Selected MCP servers remain trusted host processes. Task 90 adds caller-driven read-only browser inspection of fetched allowlisted HTTPS pages, rendering sanitized static content in ephemeral Chromium with scripts, page-provided styles/resources, user interaction, downloads, local-file access, and browser network requests disabled. It is a safeguarded inspection foundation, not general computer control. Task 91 adds bounded, read-only Gemini model discovery using a trusted backend API-key configuration, filtered capabilities, and metadata-only audit events; it does not generate content or select/assign models. Task 92 adds a read-only capability inventory aggregated from existing Agent, Tool, integration-scope, and caller-supplied Gemini catalog sources; it grants no access, makes no external discovery request or execution call, and does not mutate assignments. Task 93 adds bounded intake of caller-supplied capability candidates without independently verifying or activating them. Task 94 adds a bounded deterministic review of caller-supplied evidence for candidate fit, risks, and operational requirements; it reports evidence coverage without verifying claims or approving adoption. Task 95 adds a bounded in-memory record linking a candidate/evaluation to passing tests, exact-patch review, patch-specific human approval, and a checkpoint. Artifact linkages remain partly caller-asserted; this workflow invokes none of those stages and never activates capabilities. Task 96 adds a bounded in-memory Corporation plan from caller-supplied priorities, constraints, rationales, and source references. It preserves caller priority order and does not infer, rank, inspect Projects/Tasks, schedule, or execute work; references are not independently verified. Task 97 adds a bounded read-only report linking caller-selected Task 96 priorities and registered Employee responsibilities to actual Task 85/95 workflow snapshots with source-specific patch approval states. It does not infer role fit, generalize Task 95 patch approval to capability adoption, change assignments, claim queue work, schedule or execute Tasks, or persist. Task 98 adds caller-authored review-only Employee headcount targets and role/responsibility change proposals linked to a Task 96 priority and checked against current Employee records; targets are not reconciled with role-change proposals, and changes are not applied or approved. It does not change Agent/model assignments or Task 71 resource capacity. Task 99 adds a bounded review-only report of capability workflow progress and currently verifiable artifact consistency without invoking stages or adopting capabilities. Task 100 adds an immutable read-only Platform Overview of Corporation/Node identity, existing registry counts, and bounded capability metadata; absent sources are UNAVAILABLE or UNKNOWN only where evidenced, and neither registry presence nor capability declarations imply readiness. It makes no Provider/network calls, executes no Tasks, changes no assignments/resources, persists no report, and adds no API/UI. The numbered roadmap is complete as foundations; post-100 platform gaps remain planned. Owned coordinator browser chat is available in explicitly configured local mode (Task 103); automatic transcript archiving remains unavailable. Default API browser authentication is not configured, so protected data and actions require an authenticated session with the relevant permissions. These remain foundations, not production-complete subsystems.

Task 81 sends review evidence to the selected Agent's configured Provider; callers must sanitize the evidence and authorize its disclosure.

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

**Future / planned:** dependency installation, sandbox testing, review, human approval workflow, controlled integration, monitoring; richer orchestration; AI-based or semantic routing; advanced Provider/Model selection; multi-Agent collaboration and Agent-to-Agent communication; independent-installation networking and Node Discovery; Authentication, Authorization, and Encryption; Offline Mode, Synchronization, and Conflict Resolution; a Software Reliability Engineer / QA guardian; controlled self-improvement; open-source ecosystem integrations; Git/GitHub workflow automation; and additional Tool/MCP integrations.

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
application_service.assess_model_resources accepts an explicit immutable tuple of 1 to 100 unique ModelCandidate values and preserves caller order without ranking candidates. Assessments expose registered/missing providers, configured/unconfigured global/provider/model Capacity values, fresh-unique-ID admission eligibility and explicit exhaustion/unknown reasons. Capacity is configured admission accounting, not physical compute feasibility. ResourceSnapshot now has a trailing optional allocation_id_history_capacity field; old positional construction remains compatible and absent history is unknown/ineligible. ResourceManager populates it atomically using the existing Capacity abstraction and authoritative historical ID count. Release restores active execution slots but never restores the monotonic distinct-ID budget; at the existing 10000-ID limit, allocation_history_exhausted prevents eligibility even with all active slots free. No allocation/release rule or earlier snapshot field changed. Task 71 consumes public snapshots and public provider registration, never private manager fields or duplicate history arithmetic. Eligibility concerns only a fresh unique allocation ID; reused IDs remain prohibited by Task 68. Assessments are non-reserving local snapshots that may become stale immediately. Refresh before decisions; Task 70 remains authoritative for atomic admission. Eligibility does not guarantee execution, hardware feasibility, provider health, model loading or preference over another model. No hardware polling, provider call, Agent assignment change, Task rerouting, intelligent selection, scheduling, queue worker, retry, API/UI or new dependency is added. Existing direct execution remains unchanged.

## Provider Availability (Task 72)

Provider availability is optional and checked only on explicit application-service request through the registered provider. Providers without a supported check return an immutable UNKNOWN result; registration never implies availability. Ollama checks the lightweight service tags endpoint with a bounded timeout and does not generate text. Expected request/status failures become sanitized UNAVAILABLE results; unexpected programming defects remain visible. Results describe provider/service availability only—not installed-model readiness, inference success, hardware feasibility, or configured Task resource capacity. Checks do not execute Tasks, reserve Task 70 slots, or modify Agent/model assignments. Task 71 configured admission-slot awareness remains separate.

## Intelligent Model Routing (Task 73)

`application_service.select_model_candidate` accepts an immutable tuple of up to 100 unique model candidates wrapped with caller-supplied capability declarations, policy tags, Task 72 availability state, and optional non-negative finite `Decimal` cost estimates. Caller-supplied constraints may require capabilities/tags, restrict provider IDs, set a maximum cost, and explicitly opt into UNKNOWN availability. The first eligible candidate in caller order is selected; there is no ranking or hidden default preference. A cost limit excludes candidates without an estimate; without a cost limit, estimates do not affect eligibility. Cost estimates and policy/capability declarations are trusted caller inputs, must share one caller-defined unit, and are not independently verified. Missing providers and UNAVAILABLE candidates are always excluded. Task 71 admission assessment accompanies each candidate but does not filter selection; hardware feasibility remains unknown. This is a review-only result: it does not alter Agent/model assignments, execute Tasks, call providers, or make Task 70 admission decisions.

## Multi-Agent Collaboration (Task 74)

`application_service.task_collaboration()` exposes a local, in-memory, caller-driven collaboration record service for an existing pending Task. The caller explicitly supplies 2–10 distinct registered Agents in order; each participant role must exactly match that Agent's registered role. The first participant is active, and each may hand off once to only the next listed participant. The final participant explicitly completes or fails the collaboration. Each action names the acting Agent, and non-active participants cannot impersonate the current participant. The trusted caller owns the initial context; the collaboration session owns the shared append-only record; and each handoff/completion entry is attributed to the active Agent. Participant failures use explicit reason codes and terminate the collaboration without changing Task status.

Collaboration only records supplied content; it never calls Providers, recursively invokes Agents, creates Tasks, changes assignments, or changes Task lifecycle. Existing TaskLogger records start, handoff, completion, and failure metadata against the Task without putting context/output text in audit logs. Collaboration state/context is in-memory and is lost on process restart; durable audit events do not contain enough data to reconstruct it. The trusted Core/Application Service boundary remains responsible for caller authorization; no collaboration API/UI or new persistence is added.

## System Monitoring (Task 75)

`application_service.monitor_system()` returns an on-demand immutable report over current local Task status, Provider registration, and configured resource-capacity snapshots. It reports failed Task IDs (up to 100, with an omitted count) and exhausted configured capacity as factual signals, without adding alert rankings or policy thresholds. Provider availability remains UNKNOWN because monitoring performs no Provider probes; hardware feasibility also remains unknown. Unconfigured capacity is reported as absent. Task error text is not included. Sources are sampled independently and can change while the report is being collected; the report does not reserve capacity. Reports are not cached or persisted, and monitoring does not execute Tasks, modify assignments, poll in the background, remediate, or add API/UI.

## Error Detection (Task 76)

Routing failures and exceptions caught during Agent/Provider execution are recorded on failed Tasks as the stage categories `routing` and `execution`. These categories identify where failure was caught, not the root cause. Existing failed Tasks without structured categories are migrated as `unknown`; in-memory failed Tasks without a category also report `unknown`. `application_service.detect_failures()` returns immutable summaries bounded to 100 Task IDs of at most 256 UTF-8 bytes each, with total and omitted counts. It exposes only Task IDs and category codes, never Task.error or exception/log message text. The failure report does not retry, execute, or change Tasks.

## Diagnostic Agent (Task 77)

`application_service.diagnose_failure(agent_id, failure, evidence)` performs one call through the caller-selected registered Agent, using only a current Task 76 failure record and 1–20 explicit caller-supplied sanitized evidence items. The trusted caller is responsible for removing secrets and exception text before constructing `DiagnosticEvidence`. Each evidence item is bounded to 8192 UTF-8 bytes and total evidence to 32768 bytes. The bounded structured response permits at most 10 findings and unknowns; every finding must cite reference IDs present in that request. The result contains the failure and Agent IDs, cited findings, and unknowns—not the supplied evidence itself. Citations are checked for reference identity, not truth; generated diagnostics require human review. No Task.error, logs, or other records are retrieved automatically. No Task creation/execution, assignment changes, retries, remediation, persistence, or API/UI are added.

## Local owner Web UI (Task 102)

Start the explicitly configured local app from the repository root:

```powershell
python -m app.local
```

Choose and confirm a password of at least 12 characters at the hidden prompts.
Open `http://127.0.0.1:8000/ui/login`, sign in, and view the dashboard. Use that exact
address; localhost aliases/other hosts are rejected unless explicitly configured.
Use `--port 8001` if needed. Ctrl+C stops the app. Password and sessions are
in-memory for this run; restart invalidates sessions and prompts for a new password.

Task 102 initially granted existing read permissions. Task 103 adds separate
coordinator-chat permissions. Management forms may remain visible, but
create/change/delete and maintenance actions are denied. The normal
`app.api.app:app` remains rejecting by default; do not launch local mode via a
reverse proxy or expose it remotely. Startup still uses the existing runtime and
SQLite initialization; do not treat reads as proof of a configured provider/model.
No installer, background startup, OS service, or automatic provider call is added.

Local access uses hashed password verification, bounded attempts, opaque expiring
HttpOnly SameSite=Strict session cookies, logout revocation, loopback peer/Host
validation, and exact-Origin plus session CSRF checks on writes. Cookies are not
Secure because this explicitly loopback-only mode uses HTTP; TLS/remote access is
out of scope. It does not protect against malware or another process under the
same OS user. Sign-in request validation omits submitted passwords from errors.


## Owned coordinator browser chat (Task 103)

Start `python -m app.local`, sign in at `http://127.0.0.1:8000/ui/login`, and open
**Coordinator chat** (`/ui/chat`). Choose an actual registered Agent and select
**New conversation**, then type a message and **Send**. The default Local Worker
uses Ollama with `llama3.2:3b`; that service and model must already be available.
This milestone does not install, download, discover, or automatically select models.
The UI shows the actual Agent/provider/model and safe service/model failure guidance.

Chat uses the existing CorporationChatService through a separate principal-owned
Application Service facade. The API provides owned list/create/get/send/close at
`/api/chat/conversations`, with distinct `chat:read`, `chat:start`, `chat:send`, and
`chat:close` permissions. Explicit local mode grants those permissions alongside
its existing reads; default API authentication still rejects access. Server-generated
IDs and ownership checks hide other owners' conversations, including trusted CLI
chat records. Local cookie-authenticated chat writes require session CSRF and Origin.

Messages/replies retain the existing 8192-byte limit and 32768-byte prompt limit.
This facade retains up to 100 conversations per service run and 200 messages per
conversation, including failed messages; closing does not free that retained history.
History and ownership are in memory and do not survive restart. No automatic memory
retention occurs. Per-conversation local locks reject overlapping get/send/close
requests with 409; they provide no distributed or multi-process coordination.
External registry/configuration mutations are not synchronized; a detected provider/
model reassignment requires a new conversation and configurations should remain
stable during calls. Separate conversations may call the provider concurrently;
chat does not reserve Task 68 slots or use Task 70 controlled Task execution.

Sending explicitly calls the selected configured provider through the existing
Orchestrator, returns a complete response, and never executes generated instructions.
The current provider contract has no streaming or true cancellation; closing the page
or signing out does not cancel a request already admitted. Failures record a failed
user message and expose a safe error; network failures can leave an uncertain outcome,
so the UI reads the current conversation without automatically replaying the turn.
Replies are rendered as plain text, including any HTML. No tools, Task creation/
execution, assignment changes, cloud fallback, automatic retries, deployment, or
maintenance action is triggered. Keep API credentials out of ordinary chat.
The CEO label/hierarchy, workforce delegation and richer onboarding remain planned.

# ERSELMETZ AI

**ERSELMETZ AI is an actual software system implementing a virtual/simulated AI organization.** The organization is the system's domain model and operating concept; the software implements its current capabilities.

## Getting started as a user

For everyday use, install and open the Windows desktop app from the trusted
installer, then follow its first-start owner-password setup. On later launches,
enter that password to start the local service, then sign in to ERSELMETZ AI with
the same owner password. The app stays on this computer unless you explicitly
connect an online provider.

From Home, check the setup card. It reports whether a provider and an AI team
member's model assignment are configured; it does not run a provider health check
or claim that the assigned model is installed or ready. If setup is missing, open
**Providers & models** to review the current configuration. For Ollama, use its
local model setup page to explicitly refresh its installed-model list and select
a model only after reviewing the confirmation.

Choose **Start Chat**, select a registered AI team member, choose **New
conversation**, then write a message and press **Send**. The first reply checks
whether its configured service can respond. If it cannot, read the error and
check the configured provider/model. Chat does not run
generated instructions. Gemini is optional: connect it from its setup page and
review each separate consent prompt before sending chat content online.

Projects, Tasks, the AI team, activity, and other controls are available from the
navigation when needed. The rest of this README describes developer/operator
architecture, configuration, and implementation details; ordinary use of the
installed desktop app does not require running development commands in a
terminal. Installer build, recovery, and implementation details are in
[`desktop/README.md`](desktop/README.md).

The current application includes a local Python command-line system and a FastAPI interface. It models a Corporation and installation Node, an Orchestrator, Employees, technical Agents, a Provider/Model execution boundary, persisted Tasks, deterministic routing, and dry-run inspection.

> **Implementation status:** Tasks 1–100 are complete as foundations. Tasks 27–30 add public GitHub discovery, bounded source analysis/learning, evidence-backed evaluation, and proposal generation; Tasks 31–33 add sandbox foundations and a Docker execution backend; Tasks 34–36 add controlled source staging, verified sandbox binding, and immutable execution preparation without executing staged source. Tasks 37–45 establish the Application Service/API foundation and authorized Corporation status, Employee/Agent, Provider/Model, Task, Project, and Activity APIs. Task 46 provides the FastAPI-served Web UI foundation; Task 47 adds a read-only executive dashboard; Task 48 adds Employee Management; Task 49 adds Provider and Model Assignment management; Task 50 adds Task Management; Task 51 adds Project Management; Task 52 adds the read-only Activity / Logs UI; Task 53 adds the read-only Documentation Portal over approved Markdown files; Task 54 adds a protected, read-only Corporation Updates page backed by a manually curated manifest; Task 55 adds in-memory Conversation and Message records with a controlled message lifecycle. Task 56 adds an in-memory Individual Employee Chat Core service with an explicit Employee/Agent target and immutable conversation snapshots. Individual Employee Chat still records messages and outcomes explicitly. Task 57 adds bounded caller-supplied context; Task 58 adds local Corporation Chat with explicit Orchestrator-mediated replies; Task 59 adds reviewed and confirmed creation of pending Tasks; Task 60 adds permission-aware Task lifecycle snapshots on the Activity page. Explicit owner-scoped persistent conversation notes are available with consent and expiry. Task 72 adds optional, on-demand provider/service availability checks. Task 73 adds explicit review-only model candidate selection using caller-supplied capability, policy, availability, and cost data; assignments and Task execution remain unchanged. Task 74 adds bounded caller-driven Agent handoff records without Provider calls or Task lifecycle changes. Task 75 adds an on-demand read-only report over local Task, Provider-registration, and configured resource-capacity snapshots; it never probes Providers or changes runtime state. Task 76 adds persisted routing/execution-stage failure categories and a bounded safe report that omits raw exception details; historical unclassified failures remain UNKNOWN. Task 77 adds one-call Agent diagnostics over only explicitly supplied sanitized evidence. Task 78 adds caller-authored review-only maintenance proposals linked to diagnostics. Task 79 applies caller-supplied diffs only to explicitly selected files in a disposable temporary copy; it executes no code or tests, changes no source or runtime state, and is not a security sandbox. Task 80 runs caller-selected pytest files against a second temporary copy, returning bounded actual results; test code is not OS-sandboxed. Task 81 adds one-call advisory Agent reviews over bounded caller-supplied sanitized evidence, without automatic file/test retrieval, execution, approval, mutation, or persistence. Task 82 adds a separate Docker-only test path that stages only the registered Task 79 workspace into a bounded ephemeral container with no host mounts, networking, or injected credentials; existing Task 80 host-permission execution remains unchanged. Task 83 adds authenticated in-memory review and approval of an exact maintenance patch/source hash pair. Task 84 creates local Git checkpoint commits on dedicated branches from exactly approved workspaces, requiring separate `maintenance:checkpoint` authorization and a clean worktree/index; it never checks out, pushes, or merges, and recovery uses `git revert`. Task 85 adds a bounded caller-driven record linking existing diagnostics, proposals, patches, passing tests, review evidence, human decisions, and checkpoints without invoking those stages; failed tests terminate a workflow and metadata-only audit events use existing Task logs. Task 86 adds an explicit synchronous MCP client for selected local stdio/in-process tools, with a frozen allowlist, explicit ToolRegistry registration, bounded JSON inputs and text/structured results, sanitized errors, and per-call timeouts; it is not wired to Agents, Tasks, APIs, or UI, and local MCP servers are not OS-sandboxed. Task 87 adds authenticated read-only GitHub repository inspection requiring github:read and an explicit repository allowlist; it reuses public discovery, hides out-of-scope and missing/private repositories, omits README text, and performs no remote writes, Task execution, or Agent calls. Task 88 adds explicit HTTPS research retrieval through an exact-host allowlist and returns immutable untrusted-evidence records; it performs no search, crawling, Agent/Provider calls, or Task execution. Task 89 adds a bounded MCP coding-tool adapter that sends only caller-selected file contents and returns path-limited immutable diff proposals; it applies no patches, executes no code, and triggers no tests/review. Selected MCP servers remain trusted host processes. Task 90 adds caller-driven read-only browser inspection of fetched allowlisted HTTPS pages, rendering sanitized static content in ephemeral Chromium with scripts, page-provided styles/resources, user interaction, downloads, local-file access, and browser network requests disabled. It is a safeguarded inspection foundation, not general computer control. Task 91 adds bounded, read-only Gemini model discovery using a trusted backend API-key configuration, filtered capabilities, and metadata-only audit events; it does not generate content or select/assign models. Task 92 adds a read-only capability inventory aggregated from existing Agent, Tool, integration-scope, and caller-supplied Gemini catalog sources; it grants no access, makes no external discovery request or execution call, and does not mutate assignments. Task 93 adds bounded intake of caller-supplied capability candidates without independently verifying or activating them. Task 94 adds a bounded deterministic review of caller-supplied evidence for candidate fit, risks, and operational requirements; it reports evidence coverage without verifying claims or approving adoption. Task 95 adds a bounded in-memory record linking a candidate/evaluation to passing tests, exact-patch review, patch-specific human approval, and a checkpoint. Artifact linkages remain partly caller-asserted; this workflow invokes none of those stages and never activates capabilities. Task 96 adds a bounded in-memory Corporation plan from caller-supplied priorities, constraints, rationales, and source references. It preserves caller priority order and does not infer, rank, inspect Projects/Tasks, schedule, or execute work; references are not independently verified. Task 97 adds a bounded read-only report linking caller-selected Task 96 priorities and registered Employee responsibilities to actual Task 85/95 workflow snapshots with source-specific patch approval states. It does not infer role fit, generalize Task 95 patch approval to capability adoption, change assignments, claim queue work, schedule or execute Tasks, or persist. Task 98 adds caller-authored review-only Employee headcount targets and role/responsibility change proposals linked to a Task 96 priority and checked against current Employee records; targets are not reconciled with role-change proposals, and changes are not applied or approved. It does not change Agent/model assignments or Task 71 resource capacity. Task 99 adds a bounded review-only report of capability workflow progress and currently verifiable artifact consistency without invoking stages or adopting capabilities. Task 100 adds an immutable read-only Platform Overview of Corporation/Node identity, existing registry counts, and bounded capability metadata; absent sources are UNAVAILABLE or UNKNOWN only where evidenced, and neither registry presence nor capability declarations imply readiness. It makes no Provider/network calls, executes no Tasks, changes no assignments/resources, persists no report, and adds no API/UI. Tasks 1-130 are completed milestone foundations. Task 131 documents the current packaging and distribution boundary. Tasks 132-133 and 135-169 are verified foundations; Task 134 remains deferred and incomplete; Task 170 is deferred and incomplete; Tasks 171-173 are complete scoped milestones; Tasks 174-175 remain planned expansions and do not describe implemented behavior. Task 130 adds optional local semantic indexing over explicitly retained knowledge, preserves lexical retrieval, and leaves automatic chat injection disabled. Owned coordinator browser chat is available in explicitly configured local mode (Task 103); automatic transcript archiving remains unavailable. Default API browser authentication is not configured, so protected data and actions require an authenticated session with the relevant permissions. These remain foundations, not production-complete subsystems.

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

The `/ui` dashboard is a presentation route. Task 160 adds protected panels for authorized open coordinator conversations, active Tasks and Projects, pending approval metadata, system/resource snapshots, and Corporation-scope knowledge metadata. Browser code uses only same-origin protected APIs and does not read or change Core data directly; each API keeps its own authentication and permission checks. The default authentication backend rejects requests, and no browser sign-in/session integration is configured by default, so the dashboard shows authentication, permission, empty, and loading states instead of treating failures as empty results. Most freshness labels report when the browser last read an API and turn stale after 60 seconds; Task and Project source timestamps are unavailable. The system snapshot has its own `observed_at` value. Approval entries are informational, knowledge content and private Conversation/Project memory are omitted, provider availability remains unknown unless checked separately, and software request slots do not indicate hardware capacity. Refresh is explicit and does not call Providers. The standalone public Node.js documentation site in `docs/` remains a separate application and is not the Corporation Web UI.

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

The /ui/memory page uses protected /api/memory services. memory:read permits scoped inspection; memory:manage also requires record ownership for mutations. The server binds owners/readers to authenticated identity and denies access by default. Lists contain metadata only (50 records by default, maximum 100), including expired records whose content cannot be read or restored. Active private notes can be corrected or retained with explicit consent and a future timezone-aware expiry; source references remain intact and stale revisions are rejected. Published knowledge is an immutable snapshot: named readers can inspect it, while its owner can withdraw it. Removing a private source does not withdraw separately consented publication; deletion cannot revoke caller-held copies or backups. This page adds explicit owner-selected local semantic indexing and scoped search only when the optional capability is configured. It adds no automatic capture, Provider execution, or changes to the file-based read-only Documentation Portal. Browser authentication remains unconfigured.

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

On Windows, double-click `launch_erselmetz_ai.pyw` from the repository root to
open the Task 126 lifecycle controller. The first run asks you to create and
confirm an owner password; later runs ask you to enter that password in the GUI.
The launcher stores only a salted PBKDF2 verifier protected by Windows DPAPI for
the current Windows account. It opens the browser at the existing local sign-in
page after the backend passes its health check; browser authentication is still
required. Use the GUI to check health, stop or restart the managed backend.
The launcher requires Windows, the repository checkout, and a Python environment
with Tkinter and the project dependencies. Task 127 adds a per-user Windows
Electron installer; see [desktop/README.md](desktop/README.md) for installation,
owner setup, update, data-preservation, and recovery details.

The existing command-line fallback remains available from the repository root:

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
The GUI holds a current-user launcher lease and owns exactly one in-process
Uvicorn thread on `127.0.0.1:8000`, using a socket it binds before startup. It never adopts or kills another process. If the
port is occupied, it reports the conflict and leaves the existing listener
untouched. Stop and window close request graceful shutdown; the window remains
open if the backend has not stopped. Logs shown by the launcher contain only
bounded lifecycle events; raw server exceptions and request content are omitted.

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
Replies are rendered as plain text, including any HTML. Replies alone do not
create Tasks, execute tools, change assignments, use cloud fallback, retry
automatically, deploy, or trigger maintenance. A separate, permission-gated
review flow can turn a completed coordinator message into a canonical proposal;
only explicit owner confirmation creates a pending Task, and it never executes.
Keep API credentials out of ordinary chat.
The CEO label/hierarchy, workforce delegation and richer onboarding remain planned.


The shared post-100 implementation checklist is authoritative in
`docs/tasks-data.mjs` (`post100Tasks` and `roadmapRules`) and displayed on the
public `docs/tasks.html`: Tasks 101-133 and Tasks 135-169 are verified complete; Task 134 is deferred and incomplete; Task 170 is deferred and incomplete; Tasks 171-174 are complete; Task 175 remains planned. Task 129 provides clean-install evidence for the
local Windows 11 x64 Electron package; it does not claim production completeness.
Every task has dependencies, acceptance checks, exclusions and explicit decision
gates; completed post-100 records include checkpoint and validation evidence.
The P00-P15 Markdown plan is supplementary. Use the same contracts for any
implementing AI, preserve concurrent work, and do not treat a published plan as
approval to implement future actions.

## Task 104 - Local installed-model setup

After explicit local login, open `/ui/local-models` (also linked from coordinator
chat), choose an existing coordinator and click Refresh installed models. The
provider abstraction currently supports bounded Ollama `/api/tags` inventory for
configured loopback HTTP only; unsupported providers return UNKNOWN. Missing or
unavailable inventory has safe guidance. Installation and service availability
are distinct from hardware feasibility, compatibility and execution readiness.

The owner approved a separate `local-model:select` permission; general
`model:manage` and other management writes stay denied. Local GET inventory uses
`model:read`; local PUT selection requires that separate permission plus session
CSRF/Origin protection. These routes exist only in `create_local_app`; the default
API stays rejecting and has no local setup routes. Selection freshly rechecks the
installed identifier for the coordinator's existing provider. No provider switch,
download, automatic assignment, generation, Task execution or capacity reservation
is performed by setup. Changes persist for this app run only.

Inventory disables redirects/environment proxies, uses 2-second HTTP timeouts,
and checks a 3-second elapsed deadline between response chunks (not a hard
interrupt guarantee). Responses are capped at 256 KiB decoded bytes, 100 models
and 256 UTF-8 bytes per model identifier; malformed/oversized observations are
UNKNOWN, and provider failures are sanitized. Refresh is explicit, without polling.

A shared admission guard rejects selection while an owned browser-chat request
for that coordinator is active, and rejects new sends/starts during selection.
Independent conversations can still send concurrently. Cleanup releases the guard
after provider failure. Existing conversation history and model identity remain
intact; after an assignment change, start new chat. This coordinates only one
process/service instance; CLI/direct execution, general management and external
registry changes remain unsynchronized and must not mutate config concurrently.

Task 104 validation: 20 focused / 91 affected Python tests; full Python suite
896 passed / 3 Windows symlink skips; 99 browser-module tests; 12 public-docs
tests; real Chromium login/refresh/select/new-model chat/mobile checks with a
fake provider; compilation/import, JavaScript syntax and diff checks passed.
Pylance/pyright unavailable. New tests use no live Ollama; the full suite retained
its existing optional provider integration checks. Checkpoint tag
`task-104-local-model-setup` identifies this single reviewed Task 104 commit.
Task 105 adds explicitly consented Gemini coordinator chat through the existing
Provider/Orchestrator path. The restricted key is held only in process memory for
up to one hour, generation is limited to five attempts per key per app run and
1,024 output tokens per request, and no retries occur. There is no app-enforced
dollar cap; owners must set Google account billing limits and alerts. The online
setup exists only in explicit local-owner mode; the default API remains fail-closed.
Validation for Task 105: 911 Python tests passed / 3 skipped; 115 browser and
public-docs JavaScript tests passed. New tests used deterministic fakes only.
Pylance/pyright availability and compilation/diff checks are recorded in
`docs/tasks-data.mjs`.

Task 106 blocks recognized Gemini API-key pastes in coordinator chat both in
the browser and at the API boundary, before message history or provider
submission. It guides the owner to the existing separate Gemini setup page.
Online setup accepts only the standard Google AIza key shape and rejects
unsupported formats before catalog/network calls. Chat detection is best-effort for that key shape and common
`GEMINI_API_KEY` / `GOOGLE_API_KEY` assignments; it is not a general secret
scanner. Rotating a connected key requires disconnect/erase and explicit
rediscovery/reconnection. Existing per-turn cloud consent and Task 105 request
and spend limitations remain unchanged.
Validation: 13 focused Python tests, 10 coordinator-chat/online-setup JavaScript
tests, and 13 public-docs tests passed. New provider tests use deterministic fakes.
Task 107 completed the bounded ephemeral positions foundation. Task 108 adds
manual connection previews and owner-scoped individual Employee chat. Task 109
adds disabled-by-default, review-only model assignment recommendations.
Task 110 adds a separate, permission-gated coordinator-proposal review flow.
Task 111 adds explicitly confirmed, bounded local worker dispatch. Planned Task
112 adds independently configured local/online provider connections, provider
catalog/status visibility, explicit Agent/Employee assignments, and concurrency
limited to configured request slots; it is next.

## Task 107 - Editable corporation positions

The local-owner UI at `/ui/positions` manages a bounded in-memory registry of
organization positions, responsibilities, Employee references, reporting
relationships, activation state, and revision history. The default API remains
rejecting. Position reads and writes have separate `position:read` and
`position:manage` permissions, granted only in explicit local-owner mode; a
position title grants no authority. Position data is not persisted and is lost
on process restart. Employee IDs remain distinct from Agent/model assignment,
and position records are not linked to Tasks or workflow execution. Cycles,
stale revisions, and deletion of referenced/history-bearing positions are
rejected. A reader without `employee:read` can still view positions; existing
Employee references remain intact, but Employee choices are unavailable.
Validation: 45 focused Python regressions, 3 position UI tests, and 13 public
documentation tests passed; the evidence and limitations are recorded in
`docs/tasks-data.mjs`.

## Task 108 - Manual connection assignment and individual Employee chat

Local owners preview the affected Agent identity, old/new model, privacy boundary,
assigned Tasks, coordinator conversations, and individual Employee conversations
before confirming a local-model or Gemini assignment. Missing preview data blocks
the change. Supported application-service paths reject assignment while the Agent
is executing; Task execution also verifies the assignment selected at dispatch
before sending it to a Provider, so a race fails the Task rather than changing its
connection silently. Existing Task Agent IDs and conversation identity/history
remain fixed. Stale individual chats reject sends and require a new conversation.

The `/ui/employee-chat` page and `/api/employee-chat/conversations` endpoints
provide bounded, process-local conversations scoped to the authenticated
principal. Separate `employee-chat:read/start/send/close` permissions are
available only in explicit local-owner mode; the default API remains rejecting.
Chats require a registered Employee with an assigned registered Agent, isolate
conversation histories, and send only the current request plus recent chat
history. Employee profiles and Task context are not included automatically.
Gemini chat retains per-turn consent and rejects recognized key pastes before
saving or sending them. Replies render as plain text, and failed replies are not
automatically retried.

The existing single-Gemini-Agent lifecycle remains: disconnect before switching
Agents. Conversations and their histories are lost on restart. Assignment guards
cover the supported in-process application-service paths, not direct registry
mutations, external processes, or multiple app instances. Validation: 62 focused
Python regressions and 150 expanded directly affected Python regressions passed
with one existing Starlette deprecation warning; no tests were skipped. Twelve
browser-module tests and 13 public-docs tests passed with deterministic fakes.
Pylance reported no problems in changed Python files.

## Task 109 - Capability-based assignment policy

The explicit local-owner page at `/ui/assignment-policy` configures a
principal-scoped, process-local recommendation policy. It is disabled by
default and requires a separate `assignment-policy:manage` permission, an
explicit save/enable action, provider allowlists, a budget limit and a
caller-defined unit. Preview is read-only and deterministic in owner-supplied
candidate order. It requires a registered provider, candidate membership in a
fresh owner-recorded inventory, fully configured eligible Task 71 capacity,
and fresh positive tested evidence for every capability declared by an Agent.
Positive declarations alone, absent evidence, stale evidence, unknown budget,
and capacity/access failures are surfaced with reasons and unknowns rather
than generating recommendations. Model names and installed state never count
as competence proof.

Inventory is limited to 24 hours and tested evidence to 30 days. Provider
inventory and evidence references, capability outcomes, and cost estimates are
owner-supplied and not independently verified. Estimates use the policy's
owner-defined unit and are not provider billing quotes. Hardware feasibility,
provider health, compatibility, performance and execution readiness remain
unknown. Online candidates require a separate policy opt-in; recommendations
do not connect providers, call a model, transfer data, reserve capacity or
grant Gemini consent.

Manual assignments always remain authoritative. To override a suggestion,
use the existing local-model/Gemini setup flow and its Task 108 preview and
confirmation. Disabling the policy clears its stored configuration and is its
complete undo because it never applies assignments; any separately confirmed manual change must be reversed
through the existing manual setup flow. Policy state disappears on restart.
Focused validation and checkpoint evidence are recorded in
`docs/tasks-data.mjs`.

## Task 110 - Chat proposals and pending Task review

In explicit local-owner mode, the coordinator chat page can prepare a
principal-scoped proposal from a completed coordinator message. Before
confirmation, it displays the objective, responsible Agent, Project, the
authorized retained-memory context (or that none was selected), expected
outcome, verification method, expected evidence, and canonical Task fields.
Optional context retrieval is owner-filtered to the selected scope and is
repeated before confirmation. The application rechecks the source conversation
and message, coordinator, Agent, Project, context, and a 15-minute expiry.

The exact server-generated proposal digest must be explicitly confirmed by the
same authenticated principal. A distinct `chat-task:create` permission
authorizes only this flow; local-owner mode does not gain general
`task:create`. Confirmation consumes the proposal before creating one pending
Task through existing Task persistence. It never executes a Task or tool.
Proposals are bounded, in-memory records and are lost on restart. Duplicate,
edited, stale, expired, cross-owner, and replayed confirmations fail closed.
The Task description keeps outcome/evidence and provenance references, not a
copy of retained-memory content. See `docs/tasks-data.mjs` for validation,
limitations, and the checkpoint tag.

## Task 111 - Controlled worker dispatch

In explicit local-owner mode, Task Management exposes a separate
`task:dispatch` permission-gated path to dispatch one pending Task. Each run
requires explicit confirmation, a valid current Agent route, an existing
Project when associated, and available global/provider/model slots from the
existing Task 68 `ResourceManager`. It reuses the durable FIFO queue and
controlled execution path; route changes, invalid queue state, and exhausted
capacity fail closed. Only a configured loopback Ollama Provider is supported.
Cloud Providers, Tools, dependent Tasks, autonomous workflows, automatic
retries, and queue replay are not part of this task.

The UI shows actual queue claim/execution states and whether a Task result or
error was recorded, not whether its expected outcome or evidence was verified.
Queued or interrupted claims require an explicit human resolution; abandoning
an entry does not alter the Task or re-run work. The queue is durable, but
does not provide cross-process coordination or exactly-once execution.

The standard local launcher does not configure ResourceManager budgets and has
no budget setup UI, so dispatch remains unavailable there until the embedding
host explicitly configures global, provider, and model capacity. Validation,
limitations, and checkpoint tag are recorded in `docs/tasks-data.mjs`.

## Task 112 - Multiple provider connections and explicit assignment

The local-owner page at `/ui/provider-connections` supports independently named
loopback Ollama and Gemini connections. Connection-scoped credentials remain in
memory, and APIs/status never return the Gemini key. Ollama URLs must be
loopback HTTP; Gemini catalog discovery is explicit and each chat turn still
requires separate cloud consent. Owners preview and confirm Agent/model changes;
Employees use their assigned Agent. Existing coordinator and Employee chats
reject changed route snapshots rather than silently switching providers.

Catalogs show their source, check time, state and software request-slot limits.
Local catalogs older than five minutes report stale; missing/future timestamps
remain UNKNOWN. Fresh empty catalogs report empty, and empty/stale catalogs
cannot be assigned. Global, per-connection and per-model request admission is
bounded;
capacity errors are explicit and no fallback/retry occurs. Hardware feasibility
remains UNKNOWN. Gemini retains the existing one-request and five-generation
attempt/output-token bounds, which are not a dollar spend ceiling; owners must
manage account billing externally. Paid workflow execution still requires a
verified spend ceiling. Connections and credentials are process-local, only
Ollama/Gemini are supported, and external registry/multi-process coordination
is outside scope.

Validation: 88 focused Python regressions, 6 corporation update-record tests,
16 provider/chat browser tests, and 14 public documentation tests passed with
deterministic fakes; the Python runs reported one existing Starlette
deprecation warning each. Pylance reported no
diagnostics in the new provider service/API; pre-existing unused-parameter/import
warnings remain in unchanged lines of existing files. No live or paid provider
calls were made. The full Python suite was not rerun; the Task 111 checkpoint
documents two unrelated model-assignment failures. Checkpoint tag
`task-112-multiple-provider-connections`.
## Task 121 - Chat-driven GitHub study

Coordinator chat can request a bounded repository study only for an exact
repository already allowed by the embedding host, with an open conversation
owned by the caller and both `chat:send` and `github:read`. The study resolves
the default branch to a commit and analyzes source from that immutable revision.
It reuses existing discovery, source analysis, evaluation and unapproved
proposal services; untrusted report content is rendered as text. Repository
source is not sent to an AI Provider, installed or executed, and the chat
transcript is not read or stored by the study. Incomplete evidence or an unknown
license requests more information; otherwise the result remains a proposal for
human review, not approval.

Validation: 90 focused Python regressions, 13 coordinator chat UI tests, all 144
browser-module tests and all 14 public documentation tests passed. The full
Python suite had 1025 passed, 6 skipped and 2 pre-existing model-assignment
failures (`test_model_set_command` and
`test_model_replacement_uses_existing_assignment_service`). No live GitHub or
paid/provider calls. Limitations: the app's repository allowlist is empty unless
configured by its embedding host; GitHub metadata is timestamped separately
from the commit-pinned source analysis. Checkpoint tag
`task-121-chat-driven-github-study`.

## Task 122 - Isolated adaptation workspace and validation

The local-owner-only `POST /api/maintenance/experiments` path applies an exact,
bounded unified diff only to explicitly supplied files in a disposable workspace.
It binds source/patch hashes, file scope, time/resource limits, selected Python
checks, test results, advisory review and recovery limits. Tests use the existing
Docker sandbox with an embedding-host allowlisted, locally available digest-pinned
image; missing isolation returns BLOCKED. Network, host mounts, automatic image
pulls, arbitrary commands, active-install edits and automatic approval/integration
are excluded. A reviewer must be a different Agent ID from the diagnostic author;
online review requires per-request cloud consent. Records are process-local and
lost on restart or disposal; source hashes do not attest a repository commit, and
different Agents may share a provider/model. The default image policy is empty.
Validation and baseline suite failures are recorded in the Task 122 contract.
Checkpoint tag `task-122-isolated-adaptation-validation`.

## Task 123 - Approved local activation and verified Git recovery

After isolated tests and independent review, the local owner can activate only
the exact approved patch through `POST /api/maintenance/experiments/{id}/activate`.
The uploaded source files must still match the configured application checkout;
the approval must bind the same source and patch hashes, follow the recorded test
and review, and be no more than 24 hours old. Critical/high review findings block
activation. The service requires a clean checkout at the checkpoint parent, makes
the supported Git checkpoint, then fast-forwards the local checkout. The response
records affected files, dependency/configuration/data classifications, hashes,
test/review evidence, approval and checkpoint provenance.

Owner-triggered recovery is available only while that exact activation remains
clean `HEAD`; it creates a Git revert commit. Partial or uncertain activation
preserves checkpoint provenance and requires checkout inspection. Coordination
and evidence are process-local. Activation does not restart the running Python
process, verify runtime health, install dependencies, migrate data, deploy the
website, or reverse external side effects. No model weights are trained or
changed. Validation and limitations are in `docs/tasks-data.mjs`; checkpoint
tag `task-123-approved-local-activation`.

## Task 124 - Read-only software and integration inventory

The explicit local-owner mode now serves `/ui/inventory` and the protected
`GET /api/local/inventory` with `inventory:read`. It reports the running app,
the current Python runtime, the fixed application Git checkout, and configured
Ollama/Gemini provider connections as separate records. Records show their source,
version or revision when verified, status, management ownership and dependent
workflow/Agent assignments. The checkout adapter uses only fixed Git metadata
commands with one-second timeouts; absent or unsupported evidence remains
`unknown`, stale provider catalogs remain `stale`, and no configured connection
is represented as `not_configured`.

This is not a Windows installed-program scanner. It does not traverse arbitrary
directories, inspect credential stores, query package managers or remote services,
or install/update/remove software. Python is externally managed; provider
credentials remain in memory and are not serialized into inventory responses.
Inventory records are bounded and sequential rather than an atomic snapshot.
The default API stays fail-closed and does not mount the local-owner inventory
route. Task 124 inventory remains read-only; Task 125 adds a separate fixed-package lifecycle adapter.
Checkpoint tag `task-124-read-only-software-inventory`.

## Task 125 - Managed software lifecycle

The local-owner-only `/ui/inventory` page now includes a narrowly scoped
Microsoft VS Code manager backed by the fixed `Microsoft.VisualStudioCode`
WinGet ID and `winget` source. It supports only the current user's VS Code
setup, never requests elevation, refuses to run from an elevated process, and
keeps existing or untracked installs read-only. Each install, update, exact
version change, pin/unpin, or removal requires a fresh five-minute preview and
an explicit same-origin owner confirmation bound to the exact source, version,
manifest installer hash, scope, and affected-data summary. The default API
does not mount these routes and remains fail-closed.

The app records only installs it initiated and a bounded audit of actual
outcomes. Failed or uncertain operations are not retried automatically.
Recovery is offered only for a previously recorded version still verified in
the WinGet catalog, and requires a new preview and confirmation. Uninstall
never requests purge or user-data cleanup; the preview shows the installation
directory that will be removed and requires the owner to move any work stored
there. VS Code settings, profiles and extensions are not read or removed.
Package operations are Windows-only and coordinated within one app process;
external package-manager changes and other app instances are outside that
coordination. Tests use deterministic fake package managers; no install,
upgrade, pin, or uninstall was performed during Task 125 validation. See
`docs/tasks-data.mjs` for verified test evidence and remaining limitations.

## Task 126 - One-click local application lifecycle

The Windows double-click entry point `launch_erselmetz_ai.pyw` opens a small
Tkinter control window for the existing FastAPI/Web UI. The GUI owns one Uvicorn
server thread and binds an exclusive socket only to `127.0.0.1:8000` before
startup. It opens the browser only after `/health` responds, and offers explicit
health, stop, and restart controls. A current-user exclusive lease prevents a
second managed GUI instance. Port conflicts, startup failures, and slow shutdown are reported with safe fixed messages; the launcher never adopts,
signals, or kills another process. Closing the window requests graceful stop.

First-run setup confirms an owner password of 12–1024 characters. A salted
PBKDF2 verifier is protected with current-user Windows DPAPI and saved under
`%LOCALAPPDATA%`; the raw password is not written to disk or command-line
arguments. Each later GUI start/restart requires the owner to enter it again,
and the Web UI still requires its separate explicit sign-in. Browser sessions
remain in memory and are invalidated on backend restart. The GUI displays only
a bounded list of redacted lifecycle events. If the saved owner verifier is lost or corrupt, remove only `%LOCALAPPDATA%\ERSELMETZ AI\owner-credential.dpapi` to repeat GUI setup; app data remains. This is a repository launcher,
not an installed executable; it requires a Windows Python environment with
Tkinter and project dependencies. Task 127 now packages an Electron 44.7 shell
and Next.js 16.4 static export with the Python 3.14 x64 backend. FastAPI serves
the exported UI at `/desktop/` on the same `127.0.0.1:8765` origin as its APIs;
there is no production Next.js server. The per-user installer is unsigned,
does not elevate, has no auto-updater, and preserves
`%LOCALAPPDATA%\ERSELMETZ AI` on uninstall. Owner setup uses the existing
current-user DPAPI verifier; the raw password travels to the sidecar through a
private stdin pipe. Request/error logs are suppressed and no persistent desktop
logs are written. Updates use manual trusted reinstalls. Provider/model and AI
behavior remain the existing Python application's behavior; package validation
did not make live model calls. See [desktop/README.md](desktop/README.md) for
build, install, and recovery instructions. Existing CLI startup and the Task 126
Python launcher remain separate and are not managed by Electron.
Checkpoint tag `task-127-windows-electron-installer`.

## Optional voice interaction (Task 128)

The coordinator chat offers explicit local on-device speech recognition, optional
Gemini 3.5 Transcribe, and local speech playback. Typed chat remains available.
Local recognition requires verified `processLocally` support and an installed
language pack; unsupported devices never fall back to cloud. Gemini accepts only
explicitly consented, mono 16 kHz PCM WAV clips up to 10 seconds and sends audio
inline without the Files API. The transcript appears in the message box for
review and is not submitted until the owner chooses Send. Possible API-key text
is discarded. Electron microphone access requires a native one-use audio-only
confirmation.

Audio is not persisted by the app and the process-local cloud request budget
reserves one cent per attempt, up to the configured 1–100 cent app-run limit.
This limits requests initiated through this app; it is not a guaranteed provider
invoice cap. Gemini provider-side retention and account billing are external and
cannot be configured or verified here. Stopping local capture/playback is
immediate, but aborting a cloud transcription or model wait does not prove remote
cancellation; its outcome and charge may be unknown and the app never retries.
Validation uses deterministic fakes only; no microphone or live paid provider
request was used. See the Task 128 evidence and limitations in the public task
roadmap.

## Windows Electron executable and installer (Task 127)

`desktop/release/ERSELMETZ-AI-Setup-0.1.0-win-x64.exe` is a per-user NSIS
installer with desktop and Start Menu shortcuts. The installed Electron main
process launches a frozen Python sidecar and serves a static Next.js export from
the FastAPI app. Electron enables context isolation and renderer sandboxing,
disables renderer Node integration, exposes only setup/start/status through the
preload bridge, denies permissions and new windows, and keeps application
navigation on the owned loopback origin. The sidecar binds exclusively to
`127.0.0.1:8765`; port conflicts fail closed. Closing the Electron window
requests graceful service shutdown. The Python CLI and `.pyw` launcher retain
their existing independent behavior.

The current installer is unsigned and is intended for local development and
testing. It has no auto-updater and makes no release-signing claim. Install
updates manually from a trusted installer. Uninstall preserves
`%LOCALAPPDATA%\ERSELMETZ AI`, including the DPAPI owner verifier and application
data; reinstall recovers the same owner profile. Raw startup passwords are sent
only over the private Electron-to-Python stdin pipe, not command arguments,
environment variables or logs. Browser sessions are cleared on exit, provider
credentials keep their existing in-memory lifecycle, and Uvicorn logs are
suppressed. See [desktop/README.md](desktop/README.md).

### Supported packaging and distribution boundary (Task 131)

Only the local Windows 11 x64 per-user installer has clean-install acceptance
evidence; it is unsigned and not a publicly supported release. Windows 10,
Windows ARM64, macOS, Linux, portable packages, and app stores remain unverified
and are not claimed as supported. There is no public download source or
automatic updater; updates are manual reinstalls from an owner-verified
installer. Uninstall/reinstall recovery was verified for the same local version
and preserved current-user data. Cross-version migration, downgrade, and
database rollback are not verified. See [the distribution support matrix and
recovery boundaries](desktop/README.md#supported-target-and-distribution-boundary).

## Task 118 - Durable chat history

Owners can opt a conversation into local durable history (/api/chat/history) with a 1 hour to 90 day expiry, review uncertain turns after a restart and delete stored history. Recovered conversations are read-only, interrupted turns are never replayed, and stored text is unencrypted at rest.

## Task 119 - Local model resource and loading controls

The local provider-connections UI reports Ollama's currently loaded models and runtime-reported memory/VRAM, and supports explicit load/unload with an owner confirmation. Load and unload require a fresh installed-model catalog and runtime snapshot, use the configured global/provider/model request-slot gate, and are blocked while that model has active work. Ollama load/unload requests have a five-minute timeout. Loaded models are keyed by provider/model, not Agent assignment count. Physical memory capacity and pre-load fit remain UNKNOWN; runtime-probe and operation duration are not inference latency. Non-Ollama lifecycle operations remain unsupported.

## Task 117 - Owned knowledge and chat context controls

Owner-scoped chat can now use retained knowledge only on explicit request. A completed message is retained only with explicit consent and an expiry of 1 minute to 30 days (POST /api/chat/conversations/{id}/retained); nothing is retained automatically. A send may carry an explicit context request (query, scope, limit up to 3); matching authorized records are added to that turn as untrusted reference data and the reply carries a source trace (memory id, scope, revision, expiry, origin, matched terms). Conversation GET re-checks each trace as current, changed, expired or unavailable without caching content. Withdrawal (DELETE) deletes the stored record and states that text already sent to a provider, earlier replies and prepared Task proposals are not recalled. Conversation-scope context cannot cross conversations; cloud consent still applies to the whole turn including retrieved context.

Task 117 chat context remains explicitly requested and lexically retrieved; semantic indexing/search is a separate optional path introduced in Task 130. Traces remain process-local; retained content and derived local embeddings are not encrypted. Neither path automatically retains transcripts or injects context into chat.

## Optional semantic memory and RAG (Task 130)

Semantic memory extends explicitly retained conversation, Project, and
Corporation knowledge. The existing deterministic lexical context retrieval
remains available and unchanged. An owner must select one accessible retained
record and explicitly index it; there is no transcript capture, generated-answer
learning, whole-database scan, arbitrary file indexing, or automatic chat
injection. The read-only Task 53 Documentation Portal stays separate and is not
indexed by this phase.

This capability is optional and is not included in the base requirements or
Windows installer. In a Python environment that supports the optional packages,
install `requirements-knowledge.txt`, place an embedding model in a local
directory yourself, and configure `ERSELMETZ_KNOWLEDGE_EMBEDDING_MODEL` to that
directory and `ERSELMETZ_KNOWLEDGE_VECTOR_DIR` to a writable local index
directory before starting the app. The app loads only local model files and
does not download models. If configuration or dependencies are missing, the
base app continues to start and the Memory page reports the capability as
disabled or unavailable.

Indexing uses deterministic text chunks bounded to 1,200 characters with 120
characters of overlap, up to 16 chunks per retained record. A vector stores
embeddings and bounded provenance metadata, not copied source text. Each search
is restricted to the selected conversation, Project, or Corporation scope and
rechecks current owner/read access, expiry, source revision, and provenance in
the authoritative memory store. Updating, withdrawing, revoking, or deleting a
record removes its derived vectors when the local store is available. Results
show source reference and relevance ordering; similarity does not establish
truth. Prepared RAG context is bounded and labels retrieved text as untrusted
reference data. Retrieval and context preparation never call a Provider or
create a Task.

The default API remains fail-closed. Semantic search requires `memory:read`,
and explicit indexing has the separate `memory:index` permission. Data and
derived embeddings are stored locally and are not encrypted at rest. Deleting
the source database does not guarantee secure erasure from storage media or
backups; the configured vector directory must also be removed by the owner when
desired. The current installer omits this optional dependency group, indexing
is limited to already-retained memory records, and semantic retrieval is not
automatically merged into ordinary chat or Task planning.

## Task 163 - Original assistant identity

The read-only Documentation Portal now includes the approved ERSELMETZ AI assistant identity profile: a calm, direct, evidence-led coordinator that communicates in the user's language, including English, Filipino, or natural Taglish. It distinguishes proposals, approvals, dispatch, execution, and verified completion; it does not claim human identity, fictional imitation, unsupported work, or permissions. This is a documentation contract only; runtime prompts and response behavior have not changed, and later preferences cannot override its authorization boundary.

## Task 162 - Three-dimensional map review

Task 162 retains the existing same-origin vendored Three.js renderer and adds no rendering dependency or framework migration. The current scene is capped at 60 nodes, uses a fixed pixel ratio of 1 and low-power preference, and renders on demand except for a short state-change pulse. Future expansion is gated on p95 frame intervals at or below 16.7 ms and p99 at or below 33.3 ms over 300 frames in three runs on a published minimum desktop profile, both idle and during local inference. At the 60-node cap, `renderer.info` must report at most 128 geometries, 4 textures, and 240 render calls. A WCAG 2.2 AA review must verify an equivalent keyboard-accessible list with all nodes, links and details, visible focus, no color-only status, usable 200% zoom, immediate reduced-motion fallback, and usable WebGL failure fallback. Structure, workflow, and resource timestamps remain independent; model assignments have no source timestamp, and the page does not represent a single atomic snapshot. WebGL is required for 3D, with the list as fallback. These are future acceptance gates, not achieved measurements: no minimum hardware profile or physical-device/assistive-technology benchmark exists. The current displayed cost covers only synchronous `renderer.render` calls and does not report frame pacing or GPU completion.

## Task 116 - Accessible 3D visualization

The `/ui/visualization` page renders the verified structure and workflow maps as a 3D-first Three.js scene (vendored three 0.186.1, MIT, served same-origin). Scene size is capped at 60 nodes, rendering is on demand, only recorded positions, assignments, states and edges are drawn, and a node pulses only when a refresh shows a recorded state change. An accessible list view is user-selectable and is used automatically for reduced motion or when WebGL fails. Effects can be disabled and render cost is displayed. The scene is read-only with no execution authority.

Limitations: Render cost is measured on the user device only (no CI benchmark against local inference); real WebGL is not exercised in Node tests; the map updates on refresh only, with no live event stream; data is process-local.

## Task 115 - Workflow map and progress evidence

A read-only snapshot map is at `/ui/workflow-map` (`GET /api/local/workflows/map`, local-owner `workflow:read`). Operational delegation/handoff links are listed apart from organizational reporting links; snapshots are timestamped and marked stale after 60 seconds; disconnects keep the last snapshot labelled stale. Selecting a work item shows recorded review and owner-approval evidence. Prompts, outputs, secrets and raw errors are omitted; Agent ids need `agent:read`. There are no progress percentages or live event streams. Validation: 7 Python and 5 browser tests, 111 browser-module tests and the public docs suite passed; the full Python suite had 979 passed, 3 skipped and 2 unrelated pre-existing failures. Checkpoint tag `task-115-workflow-map-progress-evidence`.

## Task 114 - Corporation structure map

A read-only tree of recorded positions is available at `/ui/structure` (`GET /api/structure-map`, `position:read`). Reporting links, employees and Agent/model assignments come only from actual records; missing, unassigned and forbidden data is labelled, and selecting a node refetches current details and flags stale or vanished positions. Nothing is inferred or animated and there is no graph or 3D view yet. Validation: 5 Python and 3 browser structure tests, 106 browser-module tests and the public docs suite passed; the full Python suite had 972 passed, 3 skipped and 2 unrelated pre-existing failures. Checkpoint tag `task-114-corporation-structure-map`.

## Task 113 - Workflow review and owner reporting

`/api/local/workflows` (local-owner mode only; separate `workflow:read` and
`workflow:manage` permissions) manages process-local workflows that are
separate from Task lifecycle and only reference a Task id. Items are planner,
worker or reviewer work with source-linked handoffs and states waiting, running,
blocked, failed, review, reviewed, approved and interrupted. Delegation is
bounded to depth 3 and 10 child items (lower limits allowed). A reviewer must be
a different Agent, and review never replaces owner approval, which requires
explicit confirmation and verification evidence.

Routing is local-first by default and owner-selectable online-first; it picks
the first eligible destination and never skips a busy one. Online work needs
per-turn cloud consent plus an owner-declared request cost and workflow spend
ceiling; otherwise it is blocked and reported UNKNOWN. These figures are
owner-declared, not provider-verified billing. Fallback is off by default and
only goes to a pre-authorized destination that passes its own consent, budget and
capacity checks. Quota rejection is surfaced without retry. One retry occurs
only when the provider confirms work did not start; timeouts and uncertain
outcomes are never retried. Pause blocks new starts, interruption leaves an
unknown outcome until the owner requeues, and cancellation of a started call is
unsupported. `/ui/workflows` is a read-only report.

Validation: 14 workflow Python tests (deterministic two-local/three-online
fakes), 2 workflow browser tests, all 103 browser-module tests and the public
documentation suite passed; the full Python suite had 967 passed, 3 skipped and
2 unrelated pre-existing model-assignment failures. No live or paid calls.
Limitations: state is process-local and the Agent-to-destination mapping is not
independently verified. Checkpoint tag `task-113-workflow-review-reporting`.

## Command center release acceptance (Task 129)

A clean Windows 11 x64 build was installed from a fresh temporary profile. The
Task 129 installer is available at
`desktop/release/task129/ERSELMETZ-AI-Setup-0.1.0-win-x64.exe` (SHA-256
`206A36D5C94FD76B2696C01F95CD842C24E3A79FD05FEB7FDB45F3DA101DC091`). The
frozen-sidecar and actual Electron installer smokes passed owner setup/sign-in,
restart, graceful shutdown, protected chat/provider page access, uninstall data
retention and reinstall recovery. The Next.js static build passed. Validation also
passed 159 browser-module tests, 5 Electron security tests and 14 public docs
tests. The full Python suite had 1093 passed and 3 skipped, with the two
previously recorded model-assignment failures.

No live Ollama/Gemini/provider calls, model inference or microphone capture were
used. Physical hardware capacity and concurrent mixed-provider inference remain
UNKNOWN; only Windows 11 x64 was acceptance-tested. The installer is unsigned,
manual-update only, and not publicly distributed. The build-time Electron
dependency audit reported 8 moderate advisories; `node_modules` is not packaged.
This checkpoint verifies a local install workflow, not production completeness or
unrestricted autonomous behavior.


## Guided first-run setup (Task 132)

After install, open the desktop or Start Menu shortcut; the installer does not launch the app. The native startup window asks you to create and confirm an owner password on first run and to enter it on later starts. After the workspace opens, sign in again in the UI to create the protected browser session, then open Chat. The Electron home screen provides this chat-first path plus bounded, read-only checks for the local API, owner session, chat permission, registered providers, and configured Agent model assignments. Each request has a 2.5-second timeout. Provider availability, installer integrity, installed models, and optional capability packs remain explicitly UNKNOWN on this overview; the supported local-model inventory is a separate owner-initiated check. Beginner first-chat and organization guidance is separated from expandable operator setup. The overview does not connect providers, download models, change assignments, grant permissions, or dispatch Tasks.
Checkpoint: task-132-guided-first-run-setup.

## Provider and model setup guidance (Task 133)

The Electron home page now gives owners a beginner path for the supported local Ollama and online Google Gemini connections, then explains how provider registration, service availability, installed model inventory, Agent assignment, software request-slot capacity, and observed loaded-model memory differ. API credentials belong only in the dedicated owner-protected connection setup, never ordinary chat. The overview does not connect or check providers, change assignments, or claim hardware fit. Advanced operator pages group existing connection, provider/model, local inventory, capability recommendation, owner access, activity, and software inventory flows. No separate resource-settings page exists; request slots limit software concurrency only. Task 171 now provides the unified preferences hub and operator-control overview; the Electron installer was not rebuilt for that source UI change. Task 172 adds the evidence-backed corporation and execution map in the Python Web UI, reachable from Electron navigation. Task 173 adds a selected-scope memory relationship explorer with explicit semantic search and source-revision rechecks; it does not aggregate private scopes or inject results into chat.
Checkpoint: task-133-provider-model-setup-guidance.

## Semantic retrieval quality evaluation (Task 135)

A versioned synthetic fixture evaluates explicit Task 130 retrieval with Recall@5, Precision@5, and mean reciprocal rank (MRR). Fixture thresholds are 1.0 for each metric, 1.0 for unchanged lexical Recall@5, and zero leakage of stale, expired, or unauthorized records. The versioned test and expected report are stored at tests/fixtures/semantic_retrieval_v1.json and tests/fixtures/semantic_retrieval_v1_report.json; false-positive and false-negative examples use synthetic record IDs only. These results validate deterministic retrieval contracts; they do not measure the relevance quality of a production embedding model. Task 134 is deferred and incomplete; its unresolved pack-source trust and isolated loading boundary do not block this independent evaluation.

## Hybrid lexical and semantic retrieval (Task 136)

The context retrieval application service provides an explicit `retrieve_hybrid(..., ranking_policy="rrf-v1")` operation. It combines bounded lexical and Task 130 semantic candidate ranks with explainable per-source contributions and rechecks current ownership, scope, revision, expiry, and provenance before returning results. If the optional vector capability is unavailable, the operation reports lexical-only mode. Existing lexical retrieval remains the default; chat injection and routing are unchanged. RRF is selected as a deterministic opt-in policy, while the Task 135 synthetic fixture is not evidence of production-model relevance. Checkpoint: `task-136-hybrid-lexical-semantic-retrieval`.


## Semantic index lifecycle and observability (Task 137)

The memory service exposes permission-gated, bounded synchronous rebuild, inspection, and cleanup for derived semantic vectors. Calls require explicit retained source IDs, validate ownership and scope, and return bounded per-source progress/failure, stale/missing counts, and configured vector-store usage when measurable. Cleanup removes only validated derived vectors and never deletes authoritative memory; failures leave the authoritative source intact. No secure-erasure guarantee is made. The operation caps each request at 10 selected source IDs. The deterministic fake-adapter benchmark is not a local embedding latency claim. Checkpoint: task-137-semantic-index-lifecycle-observability.


## Owner-reviewed AI knowledge proposals (Task 138)

The local-owner API accepts one explicitly selected retained Conversation or Project memory source and an explicitly selected Agent only when it is assigned to the configured loopback Ollama provider. Generated summaries and claims are untrusted drafts; every claim must cite an exact source excerpt. The review response binds the source revision, expiry, destination scope, exact proposal and digest. Accept/reject/more-information are explicit owner decisions. Acceptance rechecks the source revision and creates one retained summary in the same private scope, with the source expiry; it does not share or publish the result. Proposals live only in bounded process memory for up to 15 minutes. No cloud provider, repository/file ingestion, transcript retention or portal write is added. Checkpoint: task-138-owner-reviewed-knowledge-proposals.


## Versioned documentation review (Task 139)

Owner-authorized drafts and append-only versions are stored in a dedicated local SQLite workflow, separate from published Markdown and the read-only Task 53 Documentation Portal. Edits use expected-version conflict checks; approval records the reviewer and time for the exact current version and SHA-256 digest. Diffs and provenance remain in version history, and recovery creates a new draft from an earlier version. History is bounded to 100 documents and 50 versions per document, with no automatic pruning. Approval does not publish; no AI direct writes or portal migration are enabled.


## Central capability permission model (Task 140)

The application now has an immutable capability catalog separate from capability inventory. Each definition records a stable identity, scope type, required permission, risk level, and disabled-by-default metadata. The centralized authorization service denies unknown capabilities, missing permissions, and scope mismatches. Existing permission strings remain canonical compatibility grants, existing resource ownership remains enforced by domain services, and default API authentication remains rejecting. This establishes shared checks for APIs and trusted application-service boundaries; Task 141 adds a separate grant lifecycle; no graphical grant-management screen is included.

## Capability grants and enable/disable policy (Task 141)

Authenticated local owners can explicitly enable eligible low-risk capabilities and issue or revoke short-lived grants limited to their own principal scope. Grants expire within one hour and become unusable after revocation, disablement, logout, or session expiry. Snapshots expose grantor, capability, scope, session, expiry, status, and session-only persistence. Both enablement and grant records are process-local; there is no configured persistent grant mode. Existing Task 140 permission strings remain unchanged, and these controls do not silently migrate or revoke compatibility permissions. High-risk, moderate-risk, unknown, and non-principal capabilities cannot receive grants. Checkpoint: task-141-capability-grants-session-policy.

## Action risk levels and approval policy (Task 142)

The application service exposes an exact-action approval service for trusted callers: low-risk actions need no approval record; moderate and high risks require an owner confirmation, and irreversible actions are elevated to high risk. A review record binds an action ID and readable summary, target reference and current-state digest, scope, payload digest, policy version, actor, and at most five minutes of expiry. The local owner can inspect and explicitly confirm the exact digest through protected read/approve routes. Before the guarded callback runs, the service rechecks current capability authority, exact binding, expiry, and target state, then consumes the approval once. A changed target becomes stale; failed callbacks do not make approvals reusable. Checkpoint: task-142-action-risk-approval-policy.

## Capability audit and sensitive-data controls (Task 143)

Capability permission decisions and the Task 141–142 grant/approval lifecycle write fixed metadata-only records to the existing local SQLite database. Records are pruned after 30 days and capped at 10,000; the explicitly authorized `capability-audit:read` endpoint returns at most 200 events per request. All actor identifiers are hashed into opaque references and unsafe references omitted. Raw prompts, credentials, screenshots, audio, action payloads, approval summaries, and raw error text are not stored. This is local operational history, not tamper-proof evidence: the database is not encrypted at rest and retention is not secure erasure. Checkpoint: task-143-capability-audit-retention.

## Emergency stop and capture indicators (Task 144)

The explicitly configured local app now has an owner-controlled, process-local emergency stop panel on Home and Chat. It blocks new state-changing local API requests while preserving status reads, sign-out, explicit session-grant revocation, Stop, and separately confirmed Resume. The current chat page stops microphone capture and local speech playback; aborting a model or Gemini request only stops this app's wait, and remote completion remains unknown. The panel shows current-session permissions and grant expiry/revocation state, plus page-reported microphone/playback activity. This app does not use screen or camera capture. The stop latch resets on process restart; there is no distributed stop, replay, or claim of remote cancellation. Existing adapters keep their own bounded request timeouts. Checkpoint: task-144-emergency-stop-capture-indicators.

## Bounded speech input contracts (Task 145)

Speech input now has a backend-neutral contract for mono 16 kHz, 16-bit PCM WAV with a ten-second and 320,044-byte maximum. Language tags and transcript size are validated; audio and transcript text are omitted from object representations to avoid accidental diagnostic leakage. Browser microphone capture remains per-use and visible, with a matching ten-second local recognition limit, explicit stop/cancel behavior, and no silent cloud fallback. The Python backend does not access microphone hardware. Cancellation cannot interrupt work already running inside a browser engine or remote provider. Checkpoint: task-145-bounded-speech-input-contracts.

## Optional local speech recognition (Task 146)

An optional faster-whisper adapter is available only when its runtime is already installed and an owner-supplied model directory is present under the fixed local `speech-models` data folder. The UI lists supported local folders and requires explicit model selection; the model loads only when the owner chooses local transcription. Runtime and model files are not bundled, installed, or downloaded; the packaged Electron sidecar therefore does not provide this backend, and there is no UI installer for it. Loading uses a local path, CPU/int8, and local-files-only mode. Audio remains in bounded, wipeable request memory and is not sent to a cloud provider or written to disk by this adapter. The transcript enters the editable chat draft and is never submitted automatically. The upstream [faster-whisper project](https://github.com/SYSTRAN/faster-whisper) is MIT-licensed, but each model has its own license. CTranslate2 and audio/array runtime dependencies plus independently sized model files create a nontrivial optional footprint. Language coverage depends on the selected model. Tests use deterministic injected model fakes; no installed runtime, model quality, hardware fit, or latency is claimed. Task 134 remains deferred; this feature does not install or manage capability packs. Checkpoint: task-146-optional-local-speech-recognition.

## Reviewed speech input in conversations (Task 147)

The chat draft reports whether inserted speech came from browser on-device recognition, the selected local model, or Google Gemini after its per-recording cloud consent. Voice text is appended after existing typed text and remains editable; users still choose Send explicitly, and Gemini chat keeps its separate existing per-turn consent. The accessible source note applies only to the transcript insertion, not typed text or later edits, and clears after a successful send. This provenance is a transient UI indicator, not stored conversation metadata. No audio or transcript-source metadata is persisted. Checkpoint: task-147-reviewed-speech-input-in-conversations.

## Offline text-to-speech provider foundation (Task 148)

Reply playback uses an explicit local-only adapter over the browser/device Web Speech synthesis API. The voice selector lists only voices reported as local by the platform; the operator separately selects a speech output language. Availability, voice inventory, and language support depend on the operating system/browser, and the selected settings last only for the page session. Speaking remains an explicit presentation action on a reply, with a local playback status and stop control. It grants no action permission and never sends text to an online service or silently falls back to one. Checkpoint: task-148-offline-text-to-speech-provider.

## Bounded local voice queue and playback control (Task 149)

Clicking Speak on replies during playback adds them to a sequential, page-memory queue capped at three pending replies and 16 KiB of queued UTF-8 text; each spoken reply is capped at 8 KiB. Stop interrupts local playback and clears queued text. The UI identifies output as local. Remote voices are excluded, so chat text is not sent online and no remote cancellation or retry is claimed. No online adapter or external speech runtime was selected because this task has no verified provider/model license, privacy, retention, and quality evidence. Task 134 remains deferred; this feature uses only device-provided voices and does not activate capability packs. Device voices and packaged availability remain platform-dependent. Checkpoint: task-149-bounded-local-voice-queue-controls.

## Explicit screen capture provider (Task 151)

The local chat UI offers one caller-triggered display/window capture through the browser display-capture API and an Electron-owned native source chooser. Capture requires both `chat:send` and `screen:capture`; unsupported or canceled choices fail closed. One frame is downscaled to at most 4096 pixels per side and 8 megapixels, encoded as JPEG under 2 MiB, then attached to an open owner conversation using Task 150 retention. It is not sent to a Provider, indexed, or persisted. The app does not capture in the background, crop regions, redact content, or capture camera input. The native chooser is limited to 24 reported sources and cannot be programmatically dismissed. Deterministic fakes were used; no live screen hardware was tested. Checkpoint: `task-151-explicit-screen-capture-provider`.

## Optional image processing adapters (Task 152)

`CorporationApplicationService.image_processing()` exposes an optional Pillow adapter without importing Pillow during application startup. Pillow is pinned separately in `requirements-image-processing.txt`; it is not a core or packaged dependency and is never installed automatically. A bounded child worker supports downscaling, PNG/JPEG conversion, and caller-specified solid-black pixel rectangles. Input/output are limited to 2 MiB, dimensions to 4096 pixels per side and 8 megapixels, decoded pixel storage to 32 MiB, and processing time to five seconds. Re-encoding removes source text metadata. The worker shares the user's OS permissions and is not a sandbox. Redaction is limited to caller-provided rectangles and does not guarantee anonymization. Results remain in memory; this task adds no API, UI, attachment, Provider transfer, package lifecycle, or automatic install. Pillow's MIT-CMU license and image-processing API were selected over OpenCV's heavier setup for this bounded scope. A synthetic 8 MP local resize measured 271 ms, not a hardware guarantee. Checkpoint: `task-152-bounded-optional-image-processing`.

## Bounded image input and vision context (Task 150)

Authenticated chat owners can explicitly attach PNG or JPEG files to an open conversation through the API. Each file is capped at 2 MiB, 4096 pixels per dimension and 8 megapixels; each conversation holds at most four images, while the process-wide temporary store is capped at 20 MiB. Attachments are process-memory only, expire after 15 minutes on the next image operation, and are removed on explicit deletion, conversation close, or process restart. Only safe metadata is returned; bytes are not persisted, indexed, added to messages, or passed to a Provider. Provider transfer is unsupported here and remains denied until a future task provides explicit per-use Provider selection and consent. No upload UI, screen/camera capture, image transformation, complete image decoding, or secure-erasure guarantee is included. Checkpoint: task-150-bounded-image-input-vision-context.


## OCR provider contract (Task 153)

`CorporationApplicationService.ocr()` constructs the provider-neutral OCR service without selecting or loading an engine. It accepts an existing temporary Task 150 attachment, checks its digest, type, dimensions, and byte cap, and returns the image ID, upload/capture provenance, source SHA-256, requested language, confidence, pixel boxes, and bounded OCR text. Region count, per-region and total text, language tags, error text, and processing deadline are limited. Unsupported language, unavailable provider, low confidence, success, timeout, and sanitized failure are distinct outcomes. OCR results are marked untrusted and are not submitted to chat or interpreted as instructions. Only deterministic fake providers are tested; no OCR engine, API/UI, image transfer, or live accuracy claim is included. A provider must honor its supplied deadline; one active call per service instance prevents runaway thread creation, and a hung call keeps that instance unavailable until it exits. Checkpoint: `task-153-bounded-ocr-provider-contract`.


## Optional local Tesseract OCR (Task 154)

`TesseractLocalProvider` is an optional subprocess adapter for an owner-configured absolute executable path and optional tessdata directory. It checks engine and installed language availability, reads a bounded TSV response, and maps each word's confidence and pixel box into Task 153's provenance-bearing OCR contract. The image is passed over stdin; commands use an argument list with `shell=False`, output is size-checked, execution has a timeout, and raw engine diagnostics are never returned. It writes no image temporary file and performs no installation or download. The engine and traineddata must be installed separately. Tesseract is Apache-2.0; the official installation guide identifies the engine and language data as separate requirements. [Tesseract installation](https://github.com/tesseract-ocr/tessdoc/blob/main/Installation.md) and [engine license](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE). The `pytesseract` project is a wrapper that still requires the Tesseract executable ([official README](https://github.com/madmaze/pytesseract)); EasyOCR's official setup uses PyTorch and downloads model weights by default ([official README](https://github.com/JaidedAI/EasyOCR)). Those alternatives are not installed or activated. Tests use fake subprocess results; no live Tesseract engine or OCR quality was tested. Checkpoint: `task-154-explicit-optional-tesseract-backend`.

## One-use camera and vision chat (Task 155)

The authenticated coordinator chat can attach an owner-uploaded or explicitly captured single camera frame to a one-use multimodal turn. Camera capture requires both `chat:send` and `camera:capture`; the browser requests video only, bounds the JPEG to Task 150 limits, and immediately stops every track. Electron adds a native allow-once dialog and a 15-second video-only permission grant. A visible indicator reports the current page's capture activity.

Images remain in the Task 150 process-memory store until explicit removal, close, restart, or lazy 15-minute expiry. They are unselected by default, and are sent only after per-turn owner consent to the configured loopback Ollama provider or explicitly connected Gemini provider; Gemini also requires the existing per-turn cloud consent. Selected images are removed after the provider attempt. Both adapters bound request/response data, use timeouts, disable redirects, and do not retry. An endpoint accepting image transport does not prove the assigned model has vision capability; that model may reject the request.

Optional OCR runs only through the explicitly configured local Task 154 Tesseract executable and language data. OCR output is bounded, provenance-bound, marked untrusted, and appears only in the current provider prompt; status metadata is returned to the owner. OCR does not create instructions or actions. Tests use deterministic media, provider, and OCR fakes: no live camera, Ollama/Gemini model call, or Tesseract accuracy is claimed. Unselected attachments may remain in process memory for up to the 15-minute TTL; provider-side retention after the explicitly consented request is outside this app's control. Task 134 remains deferred and incomplete; Tasks 166-169 are complete, Task 170 is deferred; Task 174 is complete; Task 175 is next.

## Scoped browser automation (Task 156)

The optional `ScopedBrowserAutomation` integration extends the separate read-only Task 90 inspector with only owner-approved clicks on native buttons/links and text fills on non-sensitive textboxes. Its constructor requires a deny-by-default policy containing exact HTTPS origins and an action allowlist; it accepts no wildcard, custom port, URL credentials, or query/fragment values. Every mutation is previewed and requires the existing one-use high-risk action approval bound to the exact payload and current page/target digest. The digest is rechecked immediately before dispatch. Per-session actions are capped at ten and each browser step is time-limited.

Each request uses a fresh headless Playwright context with no cookies, stored credentials, local-file access, downloads, or WebSocket connections. Requests to origins outside the exact configured origin are blocked; same-origin non-GET/HEAD requests are blocked during page load/inspection and allowed only during an explicitly approved click or fill. Same-origin GET/HEAD requests and approved site handlers may still have side effects, so the adapter reports the remote outcome as unknown and does not retry. DNS-to-address pinning is not implemented; only a trusted public HTTPS origin should be configured. The provider has no API route, UI, chat-tool wiring, or configured site policy yet. Tests use deterministic browser fakes and do not access a live site or exercise Chromium network isolation. Checkpoint: `task-156-scoped-browser-automation`.
## Scoped desktop automation (Task 157)

`ScopedDesktopAutomation` is a Python integration over the optional Windows UI Automation (UIA) backend. The separate `desktop/requirements-desktop-automation.txt` pins pywinauto 0.6.9; installing it is manual, and the base runtime and installer do not add it. A service instance requires a constructor-supplied exact executable-name allowlist, which is empty by default. A request identifies one process ID, window handle/title, and a direct-child UIA Button by exact automation ID and accessible name. The adapter exposes only the native Invoke pattern, never coordinates, global keys, text entry, screenshots, or broad desktop enumeration.

Preview inspects the target without invoking it. Dispatch requires the existing one-use high-risk owner approval bound to the exact request and current target digest. Per-session actions are capped at ten, only one action can run in the process at once, the caller wait is bounded to ten seconds, and `activity_snapshot()` exposes process-local state. Emergency stop prevents new work and is rechecked before dispatch. A timed-out in-flight UIA call cannot be cancelled; its result remains unknown, the action is never retried, and overlap stays blocked until the worker exits. Tests use a deterministic backend fake; no live desktop target or real UIA behavior was exercised. Checkpoint: `task-157-scoped-desktop-automation`.
## Automation review traces (Task 158)

Approved browser and desktop action executions now create owner-scoped metadata traces through `AutomationTraceService`. Each record binds the actor, one-use action approval ID, policy version, sanitized target and action, before SHA-256 evidence digest, result category, remote outcome, and timing. Trace records are immutable, in-memory, limited to 200 records and a 24-hour maximum retention; records expire or may be evicted when capacity is full. No page text, typed value, window title, raw exception, or image bytes are stored.

The after phase stays `unknown` for Tasks 156 and 157 because neither integration can verify remote effects safely. Owner-scoped inspection and `simulate_replay()` show the saved phases without invoking an adapter. Screenshot IDs are accepted only through an explicitly injected consent validator and remain opaque references; no default validator or screenshot capture exists. This adds no API/UI or persistent audit store. Checkpoint: `task-158-automation-review-traces`.


## Task 164 - Owner response preferences

The explicitly configured local app now provides authenticated owner preferences for bounded response style, locale, detail level, and optional local speech voice/language. Choices are stored in a versioned additive SQLite table and can be reset or exported as JSON. Local chat includes the allowlisted presentation preferences in its provider prompt; models may not follow them. They do not alter Agent/provider assignments, routing, permissions, approvals, execution, microphone capture, speech playback, or cloud consent. Preferences are unencrypted, contain no chat content or credentials, and remain until reset or removal of the local database.

## Task 165 - Coordinator presence and workflow evidence

The coordinator chat identity and protected workflow map now present recorded worker assignments, handoffs, review/approval evidence, and truthful missing/uncertain/blocked/failed states. Agent names and roles appear only when the caller has `agent:read`; missing registry entries and unavailable/denied detail remain distinct. The existing workflow model does not store assignment rationale, so the UI identifies the Agent-ID source and says rationale is not recorded. It does not add orchestration or claim external outcomes. Workflow data remains process-local and snapshot-based. Checkpoint: `task-165-coordinator-presence-orchestration`.

## Task 166 - Opt-in workflow suggestions

The local dashboard can show a bounded set of deterministic review prompts from current in-memory workflow records. Suggestions are off by default; owners can enable them, configure a daily quiet interval in browser-local time, refresh explicitly, inspect source state and last-change time, and dismiss. Dismissal stores only a bounded identifier in owner-scoped local SQLite. Suggestions omit prompts, outputs, workflow titles, and provider error details. They never call an Agent/Provider, create or dispatch a Task, or run tools/actions. Checkpoint: `task-166-opt-in-proactive-suggestions`.

## Task 167 - Trusted updates and configuration migration

The owner can explicitly check the fixed `erselmetz/ai-corporation` GitHub Releases origin from the protected Updates page. The app verifies a detached Ed25519 signature with its pinned public key before showing signed release notes, installer SHA-256, and a configuration-version preview. Preparing an available update requires `updates:manage` and same-origin CSRF; it rechecks the signed release, streams the Windows x64 installer to `%LOCALAPPDATA%\ERSELMETZ AI\updates`, verifies its digest, and creates a SQLite online-backup under `updates\backups`. The owner manually runs the installer after closing the app. No automatic download, installation, retry, downgrade, or rollback is performed.

Legacy database schema version 0 is migrated additively to version 1 in one SQLite transaction; the version is advanced only after successful initialization. A database from a newer schema is rejected before mutation. The initial release migration contract remains 1 to 1 and performs no data transform. The release signing private key stays outside the repository at `%LOCALAPPDATA%\ERSELMETZ AI\release-signing\update-ed25519-private.pem`; the release owner must keep a protected offline backup. `desktop/scripts/sign-release-manifest.cjs` signs artifact metadata for a manually published GitHub release. The installer remains unsigned by Windows Authenticode, and no public release is claimed until signed assets are published. Recovery copies only the application SQLite database; reinstalling a previous app version and restoring the database remain manual, and compatibility with future schema changes is not guaranteed. Checkpoint: `task-167-trusted-updates-config-migration`.

## Task 168 - Encrypted diagnostics, backup, and restore

The owner-only local Backup & Restore page can export safe diagnostics metadata and encrypted `.erselbackup` files. AES-256-GCM encrypts the backup using a Scrypt-derived key from a passphrase the app never stores. The default selection includes only allowlisted owner preferences, suggestion settings, and software pins; private Tasks, Projects, chats, messages, memory, and other app state require a separate opt-in. Common credential patterns are redacted from text; credential-named or unsupported fields/tables and binary values fail closed.

Owners inspect the data selection before export, then choose a local save destination. Restore verifies encryption/integrity, schema, row counts, and SQLite `quick_check`, creates an encrypted pre-restore copy under the local ERSELMETZ AI backups folder, and requires a restart. There is no passphrase recovery, cloud destination, automatic backup retention, or delete/erase action. Provider account data, credentials held outside SQLite, model files, and remote data cannot be exported, restored, or erased here. Pattern-based credential redaction cannot detect every possible secret; review private-data backups before sharing. Checkpoint: `task-168-encrypted-data-portability`.

## Task 169 - Crash recovery and measured performance readiness

The owner-only Performance Readiness page reports local app-factory setup time, current process working set, recorded Agent model assignments, and queue claims that predate this app run. Older claims are outcome-unknown and require inspection; another process may still own one. Existing chat recovery remains read-only, and no operation is replayed. The page does not run a model or alter configuration. Rendering measurements remain on the local visualization page; model workload and hardware fit stay UNKNOWN without measured workload evidence. No hardware matrix or support thresholds are published. Checkpoint: `task-169-crash-recovery-performance-readiness`.

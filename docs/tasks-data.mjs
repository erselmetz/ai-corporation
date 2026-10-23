export const foundationTaskGroups = [
  {
    name: "Foundation",
    range: "1–25",
    tasks: [
      ["Start Line — Project foundation", "Set up the Python application, package layout, and initial project structure."],
      ["Task Lifecycle & Management", "Define Task states and registries, execute work through the Orchestrator, log lifecycle events, and persist Tasks in SQLite."],
      ["AI Agent System", "Create technical Agent identities with role metadata, capabilities, and Provider/Model references."],
      ["Provider & Model System", "Establish the Provider response interface and Model identifiers; Ollama is the currently registered Provider."],
      ["AI Employee System", "Represent organizational Employees separately from technical Agents, with roles, responsibilities, and optional Agent association."],
      ["Orchestrator Intelligence", "Coordinate task creation, routing, execution, lifecycle updates, persistence, and task logs."],
      ["Tool System Foundation", "Add the abstract Tool contract and in-memory ToolRegistry; tool execution is not yet wired to Agents."],
      ["Human Approval Foundation", "Model in-memory approval requests and pending/approved/rejected states without claiming an execution gate."],
      ["Client / Business Layer", "Validate basic client requests and translate them into Orchestrator Tasks through a small application adapter."],
      ["Corporation Identity", "Represent the identity of the modeled organization with a Corporation domain model and registry."],
      ["Node / Installation Identity", "Represent a participating software or physical installation as a Node with its own identity."],
      ["Corporation–Node Relationship", "Associate each Node with a Corporation and validate that relationship at runtime initialization."],
      ["Runtime Context", "Carry validated Corporation and Node IDs together as the context for a running installation."],
      ["Runtime Initialization", "Load configured local identities, validate their relationship, and establish runtime context during startup."],
      ["Runtime Identity Configuration", "Use configured-in-code local Corporation and Node IDs; durable identity administration is future work."],
      ["Runtime Startup Integration", "Wire identity initialization and validation into the existing application startup path."],
      ["Employee / Agent Organization", "Register Employees and Agents separately, and resolve Employee roles to their associated Agents."],
      ["Task Routing", "Route deterministically by explicit Agent, matching Employee role, or Agent capability; fail when no route exists."],
      ["Dry-Run Execution", "Preview the selected route, Employee/Agent, Provider, and Model without calling a Provider or mutating Task state."],
      ["Corporation Command Interface", "Provide an interactive local command interface for status and the implemented Corporation operations."],
      ["AI Employee Management", "Support in-process Employee listing and management through the Corporation command interface."],
      ["Provider Management", "List and manage configured Providers in the current in-memory runtime."],
      ["Model Assignment & Replacement", "Update an Agent's in-memory Provider and Model assignment through management commands."],
      ["Task Routing CLI Integration", "Accept mutually exclusive explicit-Agent, Employee-role, and capability options when creating or dry-running Tasks."],
      ["Task Routing Requirements & Persistence", "Persist and reload nullable role/capability routing requirements with additive SQLite migration; keep dry-run overrides non-mutating."]
    ]
  },
  {
    name: "Integration / Sandbox",
    range: "26–36",
    tasks: [
      ["Integration & Adaptation Foundation", "Define external-source, IntegrationProposal, lifecycle, in-memory registry, and approval-gated execution-record foundations."],
      ["External Source Discovery", "Discover public GitHub repository metadata through fixed REST API endpoints and return bounded, typed results."],
      ["Source Analysis / Learning", "Inspect bounded repository structure, documentation, and manifests; keep evidence-linked observations distinct from facts."],
      ["External Source Evaluation", "Summarize evidence-backed strengths, concerns, unknowns, and requirements without scores, ranking, or approval."],
      ["Integration Proposal Generation", "Generate a traceable proposal from discovery, analysis, and evaluation; it stops in PROPOSED state."],
      ["Sandbox Foundation", "Model proposal-linked sandboxes, lifecycle, and restrictive isolation-policy metadata; policy alone does not enforce isolation."],
      ["Sandbox Execution Boundary", "Define typed execution requests/results and executor/backend interfaces; block requests if no isolated backend is available."],
      ["Docker Sandbox Backend", "Provide an optional Docker execution backend configured to fail closed when required isolation controls are unavailable."],
      ["Sandbox Source Staging", "Stage bounded public GitHub archives as inert files in a controlled temporary workspace without executing them."],
      ["Sandbox Staged-Source Binding", "Bind a staged workspace to its registered proposal and sandbox after checking linkage and canonical content integrity."],
      ["Sandbox Execution Preparation", "Create immutable readiness metadata after revalidating source, relationships, workspace, and policy; do not execute code."]
    ]
  },
  {
    name: "Web/API Corporation Interface",
    range: "37–54",
    tasks: [
      ["Core/API Architecture", "Establish the CorporationApplicationService boundary used by external interfaces; API routes do not access registries directly."],
      ["FastAPI Foundation", "Provide the standalone FastAPI interface and preserve public root and health endpoints."],
      ["API Authentication & Authorization Foundation", "Add injectable authentication and permission dependencies; the default backend rejects requests."],
      ["Corporation Status API", "Expose Corporation and Node identity through the authorized GET /api/status resource."],
      ["Employee/Agent API", "Expose authorized Employee list/detail/create/delete and Agent list/detail resources using explicit response schemas."],
      ["Provider & Model API", "Expose authorized Provider management and Agent Provider/Model assignment read/replacement operations."],
      ["Task API", "Expose authorized Task list/detail/create and non-mutating dry-run; HTTP execution and lifecycle mutation are not exposed."],
      ["Project API", "Expose authenticated Project list, detail, and creation operations through CorporationApplicationService."],
      ["Activity & Logs API", "Expose bounded, authenticated, read-only Task activity summaries through the Application Service."],
      ["Web UI Foundation", "Serve a presentation-only Corporation Web UI shell and static assets through FastAPI; protect future data and actions with the existing security boundary."],
      ["Corporation Dashboard", "Provide a compact read-only dashboard using existing protected Corporation APIs; preserve authentication, show explicit data-loading states, and do not invent provider health or task recency."],
      ["Employee Management UI", "List, inspect, create, and remove Employees through the existing protected Employee API; do not create or modify Agents."],
      ["Provider & Model UI", "Provide interface workflows for Provider setup and Agent Model assignment."],
      ["Task Management UI", "Provide a user interface for task creation, routing, and lifecycle inspection."],
      ["Project Management UI", "List and inspect Projects and create them through the existing protected Project API; do not invent deletion or lifecycle actions."],
      ["Activity / Logs UI", "Display the existing protected Activity API's bounded safe summaries with supported limits, optional Task filtering, and refresh; do not add detail or mutation operations."],
      ["Documentation Portal — Corporation-integrated documentation and knowledge portal", "Provide a read-only internal portal for top-level UTF-8 Markdown files in corporation_docs/ through protected list/detail APIs; keep it separate from the public docs website and future AI-managed Knowledge System."],
      ["Updates / Changelog Page", "Provide a read-only Corporation UI for manually curated, explicitly dated development updates and release records from a maintained manifest."]
    ]
  },
  {
    name: "AI Interaction",
    range: "55–60",
    tasks: [
      ["Conversation Foundation", "Define in-memory conversation/message records, controlled message lifecycle, and the boundary between chat and Task execution without adding persistence or chat interfaces."],
      ["Individual Employee Chat", "Support conversations directed to a selected Employee/Agent with explicit identity and scope."],
      ["Chat Context", "Supply bounded, relevant context to a conversation while respecting access and retention rules."],
      ["Corporation Chat", "Add an organization-level conversation interface coordinated by the Corporation Orchestrator."],
      ["Corporation Task Creation via Chat", "Allow reviewed chat requests to become explicit Tasks with visible routing and lifecycle."],
      ["AI Activity Visualization", "Show meaningful, permission-aware progress for ongoing AI and task activity."]
    ]
  },
  {
    name: "Memory & Intelligence",
    range: "61–67",
    tasks: [
      ["Memory Architecture", "Define memory types, ownership, retention, retrieval, and separation across conversations and projects."],
      ["Persistent Conversation Memory", "Persist and retrieve conversation memory under explicit lifecycle and privacy controls."],
      ["Project Knowledge", "Organize durable, project-scoped knowledge and link it to relevant work."],
      ["Corporation Knowledge", "Manage shared organizational knowledge with provenance and access boundaries."],
      ["Memory Management UI", "Let authorized users inspect, correct, retain, and remove stored memory."],
      ["Context Retrieval", "Retrieve relevant knowledge with traceable sources and appropriate scope limits."],
      ["Improved Task Planning", "Expand task planning to account for dependencies, context, and verifiable outcomes."]
    ]
  },
  {
    name: "Multi-Agent & Resource Management",
    range: "68–74",
    tasks: [
      ["Resource Manager", "Track provider/model and execution capacity against configured resource limits."],
      ["Execution Queue", "Queue work durably and expose task ordering and lifecycle to the Orchestrator."],
      ["Controlled Concurrency", "Bound parallel execution and coordinate access to shared resources."],
      ["Model Resource Awareness", "Make model choice and scheduling aware of available compute and provider limits."],
      ["Provider Availability", "Track provider health and availability without treating transient failures as success."],
      ["Intelligent Model Routing", "Select suitable models under explicit capability, policy, availability, and cost constraints."],
      ["Multi-Agent Collaboration", "Coordinate multiple Agents on a task with explicit handoffs, shared context, and auditability."]
    ]
  },
  {
    name: "Controlled Self-Maintenance",
    range: "75–85",
    tasks: [
      ["System Monitoring", "Observe system health and report actionable signals without changing runtime state."],
      ["Error Detection", "Identify and classify failures with enough context for safe diagnosis."],
      ["Diagnostic Agent", "Use a bounded diagnostic role to investigate reported issues and cite evidence."],
      ["Maintenance Proposals", "Turn diagnostics into reviewable maintenance proposals with scope and risk."],
      ["Automated Patch Development", "Develop proposed changes in an isolated, disposable work area."],
      ["Automated Testing Workflow", "Run explicitly selected tests and report the actual results for a proposed change."],
      ["Automated Code Review", "Review proposed changes for correctness, regressions, and policy compliance."],
      ["Maintenance Sandbox", "Keep maintenance experiments isolated from the active Corporation and host state."],
      ["Human Approval Workflow", "Require explicit human review and approval before protected changes are applied."],
      ["Git Checkpoint Integration", "Record reviewable Git checkpoints with clear authorization and recovery boundaries."],
      ["Controlled Self-Maintenance", "Orchestrate a bounded, auditable maintenance flow without unrestricted self-modification."]
    ]
  },
  {
    name: "External Capabilities",
    range: "86–95",
    tasks: [
      ["MCP Integration", "Integrate selected Model Context Protocol capabilities behind controlled tool and policy boundaries."],
      ["GitHub Integration", "Add authorized GitHub workflows with explicit repository scopes and review gates."],
      ["Browser/Web Research Capability", "Enable controlled research workflows that distinguish retrieved evidence from instructions."],
      ["Coding Tool Integration", "Connect mature coding tools through a bounded execution and review interface."],
      ["Computer-Use Capability", "Explore permissioned computer interaction with explicit user-visible safeguards."],
      ["External Service Integration", "Connect selected services through scoped credentials and auditable adapters."],
      ["Capability Registry", "Describe available capabilities, ownership, requirements, and policy boundaries."],
      ["Capability Discovery", "Identify candidate capabilities without granting or activating them automatically."],
      ["Capability Evaluation", "Evaluate evidence, risks, fit, and operational requirements before adoption."],
      ["Controlled Capability Integration", "Integrate approved capabilities through testing, review, and explicit change control."]
    ]
  },
  {
    name: "Long-Term Corporation Evolution",
    range: "96–100",
    tasks: [
      ["Corporation Planning System", "Support transparent organization-level planning with traceable priorities and constraints."],
      ["Organization-Level Orchestration", "Coordinate work across organizational responsibilities and approved workflows."],
      ["Adaptive Workforce", "Adjust organizational capacity and role assignments under explicit governance."],
      ["Self-Improvement Pipeline", "Evolve the controlled proposal, sandbox, testing, review, and approval pipeline."],
      ["ERSELMETZ AI Platform", "Develop a coherent, governed platform for operating a virtual/simulated AI organization."]
    ]
  }
];

let nextNumber = 1;
export const foundationTasks = foundationTaskGroups.flatMap((group) =>
  group.tasks.map(([title, description]) => {
    const number = nextNumber++;
    return {
      number,
      title,
      description,
      category: group.name,
      status: number <= 100 ? "completed" : "planned",
    };
  })
);

// Authoritative post-100 behavior contracts. Planned entries do not authorize execution.
export const post100Tasks = [
  {
    "number": 101,
    "title": "Post-100 readiness review",
    "description": "Inspect the Task 100 implementation and define the first usable local checkpoints.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      100
    ],
    "acceptance": [
      "Map existing services, interface gaps and security boundaries to evidence.",
      "Define local access, owned chat and model-setup checkpoints without runtime changes."
    ],
    "outOfScope": [
      "Runtime execution or provider checks; production-readiness certification."
    ],
    "decisions": [],
    "area": "P00",
    "checkpoint": "f4e5b54",
    "validation": [
      "Source inspection; public documentation tests passed."
    ],
    "limitations": [
      "Source review only; no fresh full-suite or live-runtime readiness proof."
    ]
  },
  {
    "number": 102,
    "title": "Local owner browser access",
    "description": "Provide explicitly enabled loopback password login, expiring sessions and existing read permissions.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      101
    ],
    "acceptance": [
      "Default API still rejects access; local mode requires explicit configuration.",
      "Wrong-password limits, expiry, logout, Host/Origin, CSRF and permission denials are tested.",
      "Document startup/stop and ephemeral password/session behavior."
    ],
    "outOfScope": [
      "Remote/multi-user login, management authority, installer or provider calls."
    ],
    "decisions": [],
    "area": "P01a",
    "checkpoint": "1552893",
    "validation": [
      "12 focused tests; 868 Python passed / 3 Windows symlink skips; 88 browser-module and 8 docs tests passed.",
      "Compilation/import and diff checks passed; Pylance/pyright unavailable."
    ],
    "limitations": [
      "Loopback HTTP; one owner; one-hour in-memory sessions; no persistent credential store or one-click installer."
    ]
  },
  {
    "number": 103,
    "title": "Owned coordinator browser chat",
    "description": "Provide principal-owned list/create/get/send/close and plain-text chat with the selected registered Agent.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      102
    ],
    "acceptance": [
      "Conversation IDs are generated by the server; other-owner and CLI conversations are hidden.",
      "Explicit Send uses existing CorporationChatService and Orchestrator; safe failure history never auto-replays.",
      "Verify duplicate-request denial, byte/history bounds, actual model identity, CSRF and inert HTML rendering.",
      "Verify sign-in, send, close, logout and narrow-screen layout in a real browser with a fake provider."
    ],
    "outOfScope": [
      "Task/tool execution, automatic delegation, assignment changes, slot reservations or model discovery."
    ],
    "decisions": [],
    "area": "P02a",
    "checkpoint": "d1ca364",
    "validation": [
      "7 focused tests and 110 affected regressions; actual Chromium flow passed.",
      "876 Python passed / 3 Windows symlink skips; 94 browser-module and 8 docs tests passed.",
      "Full suite included 3 existing optional live Ollama checks; new chat tests use fake providers.",
      "Compilation/import and diff checks passed; Pylance/pyright unavailable."
    ],
    "limitations": [
      "In-memory history: 100 conversations and 200 messages each; restart loses history.",
      "Local instance locks only; external configuration mutations are not synchronized.",
      "No streaming or true cancellation; default chat needs existing Ollama and llama3.2:3b."
    ]
  },
  {
    "number": 104,
    "title": "Local model discovery and coordinator selection",
    "description": "Show supported local provider inventory and let an authorized owner explicitly select an installed coordinator model.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      102,
      103
    ],
    "acceptance": [
      "Explicit refresh uses bounded provider-abstraction checks and records source/time.",
      "Show installed, configured, available and unknown states separately; missing service/model has actionable UI guidance.",
      "Selection revalidates the installed identifier, preserves in-flight conversation identity and needs separate management authorization.",
      "Fake inventory tests cover missing service, malformed/oversized responses, stale selection and unauthorized mutation."
    ],
    "outOfScope": [
      "Model downloads, arbitrary file/network scans, cloud fallback or capability-fit claims."
    ],
    "decisions": [
      "Owner approved local-model:select in explicit local mode, busy-request rejection and new conversations after assignment changes on 2026-10-04."
    ],
    "area": "P03a",
    "checkpoint": "task-104-local-model-setup",
    "validation": [
      "20 focused and 91 affected Python tests passed; full Python suite 896 passed / 3 Windows symlink skips.",
      "99 browser-module tests and 12 docs tests passed; real Chromium login, inventory refresh, selection, new-model chat and mobile layout passed with a fake provider.",
      "Compilation/import, JavaScript syntax and diff checks passed; Pylance/pyright unavailable."
    ],
    "limitations": [
      "Ollama loopback inventory only; explicit refresh; 256 KiB response / 100 models / 256 UTF-8 bytes per identifier. HTTP operations have 2-second timeouts and a 3-second elapsed deadline checked between chunks, not a hard interrupt guarantee.",
      "Installed and service-available do not prove hardware feasibility, compatibility or future execution; execution readiness stays unknown.",
      "Selection persists only for this app run. Guard coordinates one owned-chat service instance; CLI, direct management, external registry mutation and other processes remain unsynchronized.",
      "No downloads, generation during inventory/selection, Task/resource reservation, cloud fallback or Task 105 behavior."
    ]
  },
  {
    "number": 105,
    "title": "First official online chat provider",
    "description": "Integrate one owner-selected official provider for explicitly permitted online generation.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      104
    ],
    "acceptance": [
      "Reuse Provider abstractions and existing integration/catalog services where applicable.",
      "Backend-held credentials, bounded checks/generation, sanitized failures and disconnect are implemented.",
      "Show selected provider/model and capture cloud-data consent and supported request/spend limits.",
      "Deterministic adapter tests verify no silent cloud transfer or fallback."
    ],
    "outOfScope": [
      "Consumer website login as API access; assuming ChatGPT or Copilot subscriptions include generic API access."
    ],
    "decisions": [
      "Resolved for Task 105: Gemini is the first official online provider. Its restricted API key stays in process memory for at most one hour, is never persisted, and can be erased explicitly; the default API remains unchanged.",
      "Resolved for Task 105: each Gemini chat turn requires explicit consent to send that message, recent history and configured context. Five generation attempts per key per app run, at most 1,024 output tokens per call, one request at a time, a 20-second timeout and no retries are the supported local limits. No dollar cap is claimed; owners must configure Google billing limits and alerts.",
      "Each additional provider needs its own supported contract; Gemini, OpenAI and Copilot are candidates, not guaranteed integrations."
    ],
    "area": "P04a",
    "checkpoint": "task-105-gemini-online-chat",
    "validation": [
      "Focused Task 105/provider/model/owned-chat regressions and update-manifest checks: 94 passed; deterministic chat/setup UI plus all browser and public-docs JavaScript tests: 115 passed.",
      "Full Python suite: 911 passed, 3 skipped. No live Gemini or Ollama calls were required by new tests.",
      "Python compilation and git diff --check passed; Pylance/pyright was not available in the environment."
    ],
    "limitations": [
      "The restricted key exists only in one local app process for up to one hour; per-key attempt counts reset on app restart. The app cannot count usage from other applications or enforce a dollar spend cap.",
      "Gemini coordinator configuration and the connection manager coordinate only one process/service instance. External registry/configuration changes and other processes are unsynchronized.",
      "After credential expiry, the coordinator retains its selected assignment but cannot generate until the owner explicitly disconnects to restore its prior assignment and reconnects.",
      "Only the official Gemini API is implemented. Consumer website subscriptions, other cloud providers, automatic assignment, fallback and production identity configuration are not included."
    ]
  },
  {
    "number": 106,
    "title": "Secure chat-driven connection onboarding",
    "description": "Offer a secure connection form from chat and guide supported provider/model setup without putting keys into transcripts.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      105
    ],
    "acceptance": [
      "Secrets go directly to the backend credential path, never to model context, chat history, assets or logs.",
      "Connection test, permitted-use/budget choices, rotation and disconnect have explicit outcomes.",
      "Recognized accidental key pastes are intercepted before persistence/model submission and surface recovery guidance.",
      "Test redaction limitations and ensure unsupported credentials cannot trigger connection or paid work."
    ],
    "outOfScope": [
      "Perfect secret detection; ordinary chat text granting unrestricted paid work or cloud access."
    ],
    "decisions": [
      "Resolved for Task 106 under the owner's 2026-10-04 instruction: accept only the standard Google AIza key shape and reject unsupported formats before catalog/network calls; detect the same key shape plus GEMINI_API_KEY/GOOGLE_API_KEY assignments in chat, with explicit best-effort limits. Keep the dedicated local setup form as the only credential path and do not expand credential retention. Connection testing remains explicit model discovery; rotating a connected credential requires disconnect/erase and a fresh explicit connection. Per-turn consent, Task 105 request limits and owner-managed Google billing limits remain unchanged."
    ],
    "area": "P04b",
    "checkpoint": "task-106-secure-chat-onboarding",
    "validation": [
      "Focused chat, Gemini setup and API Python regressions: 13 passed; coordinator-chat and online-setup JavaScript tests: 10 passed.",
      "Public documentation JavaScript tests: 13 passed; new provider tests use deterministic fakes and made no live calls."
    ],
    "limitations": [
      "Only the standard Google AIza key shape is accepted by online setup. Chat detection also recognizes common Gemini/Google environment-variable assignments but remains best-effort; other formats must not be entered in chat.",
      "The existing dedicated Gemini form performs explicit model discovery and connection; connected-key rotation requires explicit disconnect/erase followed by rediscovery and reconnect. No editable dollar cap is available; owners must configure Google billing limits/alerts."
    ]
  },
  {
    "number": 107,
    "title": "Editable corporation positions",
    "description": "Manage actual organizational positions, responsibilities and reporting references through authorized UI operations.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      104
    ],
    "acceptance": [
      "Offer editable templates: Architect, Developer, Researcher, Reasoning Analyst, QA Engineer, Security, Code Reviewer, Project Manager, Technical Writer and UI/UX.",
      "Add/edit/deactivate/remove are authorized; referenced active work must be resolved before removal.",
      "Keep Employee identity separate from technical Agent and model; role titles never grant authority.",
      "Test reference validation, denial, conflicts and preservation of historical job provenance."
    ],
    "outOfScope": [
      "Automatic permission grants, fabricated CEO hierarchy or silent deletion of active-job references."
    ],
    "decisions": [
      "Resolved under the owner's 2026-10-04 instruction: keep position records ephemeral (no schema or migration), grant only separate position:read and position:manage permissions in explicit local-owner mode, and never derive Agent/model or other authority from a position title. Keep Employee IDs separate from Agent identity; reject cycles and stale revisions, preserve revisions, and prevent deletion while an Employee, reporting position or revision history references the position. Existing Task/workflow records remain unlinked."
    ],
    "area": "P05a",
    "checkpoint": "task-107-editable-corporation-positions",
    "validation": [
      "Focused position, Employee, local-authentication and Web UI Python regressions: 45 passed.",
      "Position-management UI tests: 3 passed; public documentation JavaScript tests: 13 passed. New UI behavior was tested with deterministic same-origin API fakes."
    ],
    "limitations": [
      "Positions and up to 100 revisions per record exist only in one application-service process; restart loses them. The registry is capped at 100 positions.",
      "Position records are not linked to Task/workflow execution. Removal guards protect position-tree references, Employee occupancy and retained revisions, but cannot report unrelated active jobs.",
      "Employee IDs are referenced without changing Employee role/responsibilities or Agent/model assignment. Position titles grant no permissions."
    ]
  },
  {
    "number": 108,
    "title": "Manual AI connection assignment and individual chat",
    "description": "Assign supported connections/models to organizational Agents and open isolated individual Employee chats.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      105,
      107
    ],
    "acceptance": [
      "Owner previews identity, model, privacy and affected work before reassignment.",
      "Existing job provenance remains fixed; new assignment never silently changes an active job/conversation.",
      "Individual chat checks authenticated ownership and selected Employee/Agent identity.",
      "Test local/online reassignment, removed connections, stale references and isolation."
    ],
    "outOfScope": [
      "Automatic role-fit claims, live-job rerouting or unapproved cloud context transfer."
    ],
    "decisions": [
      "Resolved under the Task 108 owner instruction: keep connection assignment manual and require an explicit preview/confirmation; preserve existing Task Agent IDs and conversation assignment snapshots, reject stale in-flight task assignments rather than silently switching providers, and require new conversations after a connection change. Keep individual chat in explicitly configured local-owner mode under separate employee-chat permissions, with no profile/Task context transfer and per-turn Gemini consent. Preserve the existing one-Gemini-Agent connection flow; disconnect and reconnect to switch Agents rather than expanding provider lifecycle or authority."
    ],
    "area": "P05b / P02b",
    "checkpoint": "task-108-manual-ai-connection-assignment-individual-chat",
    "validation": [
      "Focused Employee chat API/service, assignment/concurrency, coordinator chat, local model, Gemini setup, Employee/Agent API, and local-owner Python regressions: 62 passed; one existing Starlette deprecation warning.",
      "Expanded directly affected Python integration/regression suite: 150 passed, no skips; one existing Starlette deprecation warning.",
      "Employee chat, local model assignment, and Gemini setup browser-module tests: 12 passed; public documentation tests: 13 passed. New behavior used deterministic same-origin API/provider fakes and no live/paid provider calls.",
      "Pylance reported no problems in changed Python files."
    ],
    "limitations": [
      "Individual conversations are bounded, owner-scoped, process-local records (maximum 100 conversations and 200 messages per conversation); restart loses history. A changed or removed Employee/Agent/provider assignment prevents sending on the old snapshot; the owner must start a new conversation.",
      "The Gemini setup retains its existing single-Agent connection and five generation-attempts-per-key-per-run limit. Switching Agents requires explicit disconnect/reconnect. Each Gemini turn still needs consent; only recent chat history and the current request are sent, never Employee profiles or Task content automatically.",
      "Task/Agent execution and assignment guards coordinate through the in-process AgentRegistry and supported application-service paths only. Direct registry/Agent mutation, external processes and multiple application instances are not synchronized. Failed pre-provider task assignment checks fail the Task rather than rerouting it."
    ]
  },
  {
    "number": 109,
    "title": "Capability-based assignment policy",
    "description": "Suggest or apply eligible role-to-model assignments under a separately enabled owner-approved policy.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      106,
      108
    ],
    "acceptance": [
      "Use traceable declared/tested capability evidence, freshness, capacity, access and budget constraints.",
      "Show rationale and unknowns; leave unsupported roles unassigned.",
      "Preserve manual assignments unless policy explicitly permits changes; offer override/disable and defined undo.",
      "Test two-local/three-online inventory examples with deterministic supported/fake connections without requiring five live model copies."
    ],
    "outOfScope": [
      "Model size/name or installed status as proof of job competence; automatic cloud consent."
    ],
    "decisions": [
      "Resolved conservatively: provide review-only recommendations, disabled by default and enabled only by an explicit local-owner policy save/confirmation. Require fresh traceable inventory references (24 hours), fresh positive tested capability references (30 days), registered/explicitly allowed providers, fully configured Task 71 admission capacity, and explicit owner-unit budgets. Treat declarations, stale evidence, provider health, model compatibility, hardware feasibility and execution readiness as unknown; no model name or installation proves competence. Online candidates require a separate policy opt-in and never connect, send data, or imply chat consent. Preserve manual assignments as authoritative; manual override continues through Task 108's existing preview/confirmation flow. Undo is disabling the non-mutating policy, which also clears its stored configuration; there is no assignment rollback because policy never applies one."
    ],
    "area": "P15",
    "checkpoint": "task-109-capability-based-assignment-policy",
    "validation": [
      "Focused assignment-policy/API/local-owner/Web UI Python regressions: 30 passed; one existing Starlette deprecation warning.",
      "Expanded assignment, dispatch, owned-chat, local-model, Gemini, resource-capacity and routing Python regressions: 184 passed, no skips; one existing Starlette deprecation warning.",
      "Assignment-policy and directly affected local-model/Gemini browser-module tests: 13 passed with deterministic fakes and no provider-generation calls.",
      "Public documentation JavaScript tests: 13 passed.",
      "Pylance reported no problems in changed Python files; diff whitespace and JSON validation passed. No live/paid provider calls were made."
    ],
    "limitations": [
      "Policy configuration, evidence, and recommendations are bounded process-local records, scoped by authenticated principal, and are lost on restart. Inventory, evidence references, and cost estimates are owner-supplied and not independently verified.",
      "Only tested positive capability evidence no older than 30 days qualifies; declarations are shown as unknown. Inventory records are limited to 24 hours and caller-reported timestamps do not prove live availability.",
      "All Task 71 admission dimensions must be configured and eligible; capacity reports are non-reserving and do not establish hardware feasibility, provider health, compatibility, performance, or execution readiness.",
      "Suggestions never modify assignments, reserve capacity, call Providers, connect online models, transfer data, or grant cloud consent. Manual assignments remain authoritative; online access and billing estimates are not independently verified."
    ]
  },
  {
    "number": 110,
    "title": "Chat proposals and pending Task review",
    "description": "Turn a coordinator proposal into an owner-reviewed pending Task using existing planning/review services.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      103,
      109
    ],
    "acceptance": [
      "Show objective, responsible Agent, authorized context, expected outcome and evidence before confirmation.",
      "Generate canonical fields at the application boundary and revalidate exact confirmed proposal.",
      "Only explicit authorized confirmation creates a pending Task; no execution occurs.",
      "Test edited/stale/reused proposals, scope denial and duplicate creation prevention."
    ],
    "outOfScope": [
      "Generated text directly executing tools, running Tasks or approving itself."
    ],
    "decisions": [
      "Resolved conservatively: proposals are bounded, principal-scoped in-memory records with a 15-minute expiry; no separate durable proposal store or migration is added. Confirmation is bound to the authenticated principal and exact server-generated proposal digest, and rechecks the open source conversation/message, coordinator, responsible Agent, Project, and any explicitly retrieved owner-authorized memory context. A dedicated chat-task:create permission authorizes only this proposal flow; explicit local-owner mode grants it while general task:create remains denied. Successful confirmation consumes the proposal before creating a pending Task, preventing retries after uncertain creation outcomes; no Task or tool execution occurs."
    ],
    "area": "P06a",
    "checkpoint": "task-110-chat-proposals-pending-task-review",
    "validation": [
      "Focused Task proposal, local access, legacy chat-task review, owned-chat and default updates-manifest regressions: 36 passed, one existing Starlette deprecation warning.",
      "Coordinator chat browser-module tests: 9 passed with deterministic request fakes.",
      "Public documentation JavaScript tests: 13 passed, none skipped.",
      "Full Python suite: 937 passed, 2 failed, 3 skipped. The unrelated model-assignment tests test_model_set_command and test_model_replacement_uses_existing_assignment_service also fail when run in isolation; neither test or its implementation files are changed by Task 110.",
      "Proposal API tests cover exact-digest mismatch, confirmation replay, duplicate proposal creation, stale closed conversations, cross-owner denial, mismatched Project context scope, default permission denial, and pending-only creation with no additional provider call."
    ],
    "limitations": [
      "Unconfirmed proposals are process-local, principal-scoped and expire after 15 minutes; they are lost on restart. At most 100 pending proposals per owner and 8 owners are retained, and 1,000 distinct proposal creations are allowed per app run.",
      "Authorized memory context is optional; the completed coordinator message is the required source. Selected context is owner-filtered, displayed with provenance and re-retrieved at confirmation. The durable Task description retains context references, not copied memory text.",
      "Task creation uses the existing Task/Project persistence and does not store a structured outcome record or add a durable confirmer field; the authenticated confirmation identity and reviewed outcomes/evidence are included in the proposal response and canonical Task description.",
      "Only the new chat-task:create permission authorizes this path in local-owner mode; it does not grant general task:create. Proposal state and confirmation deduplication are process-local and do not synchronize across multiple app instances or direct registry/database mutations."
    ]
  },
  {
    "number": 111,
    "title": "Controlled worker dispatch",
    "description": "Allow an authorized owner to dispatch approved pending work through the existing queue and controlled-execution services.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      110
    ],
    "acceptance": [
      "Validate assigned work, context and configured budgets before admission.",
      "Reuse Task 68 slots, Task 69 queue contracts and Task 70 cleanup rather than inventing a second executor.",
      "Show actual claim/execution/evidence states; interrupted or uncertain actions require explicit resolution.",
      "Test duplicate claims, exhausted slots, provider failures, cleanup and unauthorized execution."
    ],
    "outOfScope": [
      "Silent replay, unlimited recursive delegation or distributed/exactly-once guarantees."
    ],
    "decisions": [
      "Resolved conservatively: only a principal with task:dispatch can explicitly dispatch one pending Task, after route/context and existing Task 68 budgets pass preflight. Dispatch is loopback Ollama only; cloud Providers and Tools remain unavailable. There is no automatic retry or replay. A queued or interrupted claim requires explicit human resolution, and recorded execution state is not outcome verification."
    ],
    "area": "P06b",
    "checkpoint": "task-111-controlled-worker-dispatch",
    "validation": [
      "Focused dispatch API, durable queue, controlled-execution and local-access regressions: 38 passed with one existing Starlette deprecation warning.",
      "Task Management browser-module tests: 13 passed with deterministic API/session fakes and no skips.",
      "Public documentation tests: 14 passed with no skips; the shared-worktree run also exercised the pending later-roadmap direction test.",
      "Full Python suite: 943 passed, 2 failed, and 6 skipped. The failures are the same unrelated model-assignment tests documented in Task 110; neither their tests nor implementation files changed in Task 111.",
      "Pylance reported no problems in the nine changed Python files checked. No live or paid Provider calls were made."
    ],
    "limitations": [
      "The default local launcher does not configure Task 68 slot budgets or expose a budget setup UI. Dispatch fails closed until an embedding host configures the existing ResourceManager with explicit global, provider and model capacity.",
      "Dispatch supports only a configured loopback Ollama provider and does not execute Tools, cloud Providers, dependent Tasks or autonomous workflows.",
      "Queue claims survive restart, but uncertain or interrupted work is never resumed or replayed automatically. Human resolution abandons queue membership and does not alter Task state.",
      "The UI displays at most the oldest 100 queue records. Queue and Task outcomes indicate execution state only; acceptance criteria and evidence remain unverified.",
      "The queue and application locks do not provide cross-process coordination or exactly-once execution. Direct registry/database mutations and multiple application instances are outside the supported dispatch boundary.",
      "The full Python suite retains two unrelated failures from the Task 110 checkpoint: test_model_set_command and test_model_replacement_uses_existing_assignment_service. Both were previously reproduced in isolation.",
      "Concurrent planned-roadmap edits for Task 112 and later remain unstaged and are preserved for their separate roadmap checkpoint."
    ]
  },
  {
    "number": 112,
    "title": "Multiple provider connections and explicit assignment",
    "description": "Support independently configured local/online provider connections, catalog/status visibility and explicit Agent/Employee assignments across supported providers.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      104,
      105,
      108,
      109,
      111
    ],
    "acceptance": [
      "Allow multiple independently identified connections, including multiple connections for one provider; scope each endpoint and credential to its connection and never expose secrets through APIs, UI, logs or errors.",
      "Show connection health and provider-supported model catalogs with source/freshness; distinguish unsupported, stale, empty, unavailable, unknown and not-configured states without inferring readiness.",
      "Let the owner preview and explicitly confirm a supported provider/model assignment for an Agent/Employee; new conversations use the selected connection while existing conversations retain their route snapshots and authorization checks.",
      "Permit concurrent requests across assigned Employees/Agents only within configured global/provider/model request-slot limits; when applicable capacity is absent or unverifiable, block admission and report UNKNOWN rather than assuming capacity.",
      "Route only to the explicitly selected connection; surface safe unavailable/over-capacity errors without automatic fallback, reassignment, retry or silent provider switching.",
      "Use deterministic fakes for two local and three online connections to verify catalogs, distinct models, authorization, assignment snapshots, concurrency limits and secret non-disclosure without live or paid calls."
    ],
    "outOfScope": [
      "Provider-side model downloads, automatic routing/fallback/round-robin, delegated workflows, autonomous Agent execution or self-adaptation."
    ],
    "decisions": [
      "Use only explicitly owner-configured connections and assignments; keep existing assignments and conversations unchanged unless the owner confirms a new assignment.",
      "Online connections remain opt-in and require connection-scoped credentials, per-turn consent, and the existing bounded call/output behavior. These bounds are not a dollar spend ceiling; this task does not claim monetary spend enforcement, and future paid workflow execution remains gated on a verified ceiling.",
      "Do not infer health, model support, capacity or hardware feasibility from configuration alone. Missing or unsupported evidence remains UNKNOWN, and provider failures never trigger silent fallback."
    ],
    "area": "Provider connections",
    "checkpoint": "task-112-multiple-provider-connections",
    "validation": [
      "Focused Python provider-connection, local/online provider, consent, assignment, chat and Ollama regressions: 88 passed with one existing Starlette deprecation warning; no skips.",
      "Corporation update-record regressions: 6 passed with one existing Starlette deprecation warning; no skips.",
      "Provider, Employee chat and multi-provider browser-module regressions: 16 passed with deterministic API/session fakes; no skips.",
      "Public documentation suite: 14 passed with no skips. Pylance reported no errors or diagnostics in the new provider service/API; only pre-existing unused-parameter/import warnings remain in unchanged lines of existing files. Tests made no live or paid provider calls."
    ],
    "limitations": [
      "Provider connection records, online credentials and chat conversations are process-local; restart clears them. Only loopback Ollama and Gemini are supported; other provider types are rejected.",
      "Catalog freshness for local connections expires after five minutes; stale and empty catalogs cannot be assigned. Gemini credentials expire after one hour, and the existing one-request and five-generation-attempt/output-token bounds remain in force.",
      "Request slots bound software concurrency only; hardware feasibility and dollar spend remain unknown. Existing request/output caps are not a monetary guarantee; owners must manage billing externally, and paid workflow execution still requires a verified spend ceiling.",
      "Assignments are owner-confirmed per Agent; Employee chat follows that Employee's assigned Agent. Existing chats fail closed when assignment/connection snapshots become stale and require a new conversation.",
      "Locks and credentials are process-local and do not coordinate direct registry mutations, external processes or multiple application instances. The complete Python suite was not rerun; its last Task 111 checkpoint recorded two unrelated model-assignment failures."
    ]
  },
  {
    "number": 113,
    "title": "Workflow review and owner reporting",
    "description": "Coordinate bounded planner/worker/reviewer handoffs and display verified outcomes to the owner.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      111,
      112
    ],
    "acceptance": [
      "Model workflow lifecycle separately from Task lifecycle and acceptance evidence.",
      "Show waiting/running/blocked/failed/review states and source-linked handoffs.",
      "Review does not substitute for owner approval; success requires actual verification evidence.",
      "Test pause/resume/interruption/recovery and unsupported cancellation truthfully.",
      "Route among multiple separately configured local/online providers and Agents; bound delegation to depth 3 and 10 child work items per workflow, with configured lower limits allowed.",
      "Use at most one automatic retry, only when the provider confirms that work did not start; never auto-retry quota rejection, timeout or an uncertain outcome. Reviewers must be a different Agent from the worker and cannot approve their own work.",
      "Default routing preference to local-first and allow the owner to choose online-first. Require an enforceable per-run/provider spend ceiling before paid calls; if cost or quota cannot be verified, block and report UNKNOWN.",
      "Keep fallback disabled by default; permit it only to a specifically pre-authorized destination with its own capacity, budget and cloud-data consent. Surface quota exhaustion without silent switching.",
      "Use deterministic two-local/three-online scenarios to verify shared-model concurrency, preference order, budget limits, quota exhaustion, bounded delegation/retry and explicitly authorized fallback without live or paid providers."
    ],
    "outOfScope": [
      "Changing legacy execution semantics or dependency enforcement without an approved contract."
    ],
    "decisions": [
      "Keep dependency admission, dispatch bounds, pause/cancel/resume and approval rules explicit. This planned multi-provider workflow extends Task 108 without rewriting its completed one-Gemini-Agent limitation; apply bounded role/delegation/retry rules, local-first by default, owner-selectable online-first, explicit spend ceilings and quota handling, and pre-authorized fallback only.",
      "Resolved conservatively: workflow state is a separate process-local service that only references a Task id, never mutating Task lifecycle. A configured request cost and per-workflow spend ceiling are owner-declared; because the provider cannot verify billing, online work is blocked and reported UNKNOWN unless both are declared. Routing picks the first eligible destination by preference and never skips a busy one; cancellation is reported unsupported."
    ],
    "area": "P06c",
    "checkpoint": "task-113-workflow-review-reporting",
    "validation": [
      "New workflow service/API/permission tests: 14 passed, covering two-local/three-online fakes, shared-model concurrency, preference order, spend ceilings, quota exhaustion, bounded delegation, single retry, uncertain outcomes, authorized fallback, pause/resume/interruption/recovery, reviewer separation, unsupported cancellation and owner approval; no live or paid calls.",
      "Workflow report browser-module tests: 2 passed, plus all 103 browser-module tests passed. Public documentation suite passed. Pylance reported no diagnostics in the new service, API and tests.",
      "Full Python suite: 967 passed, 3 skipped (pre-existing conditional skips), and the same 2 unrelated pre-existing model-assignment failures (test_model_set_command, test_model_replacement_uses_existing_assignment_service)."
    ],
    "limitations": [
      "Workflows are process-local and cleared on restart; there is no durable recovery. Interrupted work is only marked interrupted with an unknown outcome and requires explicit owner requeue.",
      "Destinations, per-request costs and spend ceilings are owner-declared and are not verified against provider billing; no Task lifecycle, queue or dependency state is changed by workflows.",
      "Cancellation of a started provider call is unsupported. Pause only prevents new items from starting. Workflows are driven through the local-owner API; the owner page is a read-only report, and Agent-to-destination mapping is not independently verified.",
      "Limited to loopback Ollama and Gemini connections registered by Task 112; hardware feasibility remains unknown and multi-instance coordination is out of scope."
    ]
  },
  {
    "number": 114,
    "title": "Corporation structure map",
    "description": "Show actual positions, reporting relationships and Agent/model assignments with authorized detail views.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      107,
      108
    ],
    "acceptance": [
      "Graph/list comes from real authorized records and distinguishes missing/unassigned identities.",
      "Selecting a node opens current details; stale and forbidden data are visible.",
      "Provide keyboard-accessible equivalent list/tree views."
    ],
    "outOfScope": [
      "Invented reporting relationships or animated nodes implying actual activity."
    ],
    "decisions": [
      "Resolved conservatively: a keyboard-accessible tree with an equivalent flat detail view is implemented over actual position, employee and Agent records. A graph or 3D visualization is deferred to the later visualization tasks; nothing is animated and no reporting relationship is inferred."
    ],
    "area": "P07a",
    "checkpoint": "task-114-corporation-structure-map",
    "validation": [
      "New structure-map Python tests: 5 passed, covering recorded root/linked/missing reporting, unassigned/missing/assigned employee and Agent states, unavailable Provider, forbidden sections, 401/403 and permission-limited responses.",
      "Structure browser-module tests: 3 passed, plus all 106 browser-module tests passed; public documentation suite passed.",
      "Full Python suite: 972 passed, 3 skipped (pre-existing conditional skips), and the same 2 unrelated pre-existing model-assignment failures (test_model_set_command, test_model_replacement_uses_existing_assignment_service). No live or paid calls."
    ],
    "limitations": [
      "Read-only, point-in-time tree of recorded positions; there is no graph, 3D view, live updates or activity indication. Staleness is detected only on refresh or selection by revision comparison.",
      "Employee and Agent detail is shown only with employee:read and agent:read; otherwise those sections are labelled forbidden. Missing parents or records are labelled, never inferred."
    ]
  },
  {
    "number": 115,
    "title": "Workflow map and progress evidence",
    "description": "Visualize actual workflow dependencies, handoffs, status and linked evidence.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      113
    ],
    "acceptance": [
      "Separate operational workflow edges from organizational reporting edges.",
      "Show refresh timestamp, stale/disconnected/error states and actual outcome evidence.",
      "Selecting a node respects resource permissions; secrets/raw errors are omitted.",
      "Test handoff/state changes, reconnect behavior and empty versus failed data."
    ],
    "outOfScope": [
      "Fabricated progress percentages, queue positions or agent activity."
    ],
    "decisions": ["Resolved conservatively: freshness is a point-in-time snapshot contract. The map carries a server generated_at and a 60-second stale_after_seconds; the page refetches only on explicit refresh or node selection, marks a snapshot stale after 60 seconds, and keeps the last snapshot labelled stale if the connection drops. Retention is the existing process-local workflow state and event list; no event stream, push channel or persistence was introduced. Operational delegation/handoff edges are returned separately from organizational reporting edges, and no link between a work item and a position is inferred."],
    "area": "P07b",
    "checkpoint": "task-115-workflow-map-progress-evidence",
    "validation": ["New workflow-map Python tests: 7 passed, covering separate operational and reporting edges, content/raw-error/secret omission, outcome evidence, state changes, forbidden Agent/position masking, empty data, the freshness contract and the local API 401/403 paths.","Workflow-map browser-module tests: 5 passed, covering separate lists, stale and empty snapshots, selection and state changes, forbidden labels, disconnect retaining a stale snapshot and 401/403/500 errors; all 111 browser-module tests passed and the public documentation suite passed. Pylance reported no diagnostics in the new service and tests.","Full Python suite: 979 passed, 3 skipped (pre-existing conditional skips), and the same 2 unrelated pre-existing model-assignment failures (test_model_set_command, test_model_replacement_uses_existing_assignment_service). No live or paid calls."],
    "limitations": ["Read-only list/tree rendering of point-in-time snapshots; there is no graph, 3D view, event stream or live push, and workflow state remains process-local and cleared on restart.","Prompts and outputs are never returned; only whether output exists, bounded reasons, and reviewer/owner evidence text are shown. Agent and destination identifiers are masked without agent:read, and reporting links without position:read.","Work items are not linked to positions or employees because no recorded relationship exists; staleness is a client-side age check against the snapshot timestamp."]
  },
  {
    "number": 116,
    "title": "Accessible Jarvis-style visualization",
    "description": "Add a Three.js 3D-first corporation/workflow presentation over the validated maps.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      114,
      115
    ],
    "acceptance": [
      "Make the Three.js 3D corporation/workflow map the primary visual experience; keep an accessible 2D/list equivalent only as a user-selectable, reduced-motion or WebGL fallback.",
      "Use animation only for verified live state changes; provide reduced-motion controls and graceful graphics fallback.",
      "Measure rendering cost alongside local inference; cap scene size and allow disabling effects."
    ],
    "outOfScope": [
      "Decorative activity presented as real work; UI effects acquiring execution authority."
    ],
    "decisions": [
      "Owner approved Three.js for a 3D-first primary map; retain accessible 2D/list and reduced-motion alternatives and validate performance before enabling effects by default."
    ],
    "area": "P07c",
    "checkpoint": "task-116-accessible-3d-visualization",
    "validation": ["tests/test_visualization_ui.mjs: 9 passed (scene model cap/edges/layout, changed-state detection, real Three.js scene build without a renderer, render-cost sampling, default 3D, reduced-motion and WebGL-failure list fallback, pulse only on verified change, keyboard selection, 403/disconnected sections).","tests/test_visualization_page.py: 2 passed (page, CSP and same-origin vendored Three.js with license).","All browser-module tests 120 passed; docs tests passed; full Python suite 981 passed, 3 skipped, 2 unrelated pre-existing failures (test_model_set_command, test_model_replacement_uses_existing_assignment_service)."],
    "limitations": ["Rendering cost is measured only on the user device and shown in the page; no benchmark against local inference was run in CI. Real WebGL is not exercised in Node tests.","The map updates only on explicit refresh; there is no live event stream, so pulses reflect changes between refreshes. Data remains process-local.","The 3D scene is read-only and carries no execution authority."]
  },
  {
    "number": 117,
    "title": "Owned knowledge and chat context controls",
    "description": "Expose supported knowledge retention/retrieval controls and source traces in owner-scoped conversations.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      103,
      108
    ],
    "acceptance": [
      "Retention requires explicit consent, expiry and correct owner/scope/provenance.",
      "Authorized retrieved sources and freshness are visible; untrusted content cannot grant actions.",
      "Correction/removal/withdrawal describe actual deletion and revocation limits.",
      "Test ownership, expiry, stale revisions, scope boundaries and no automatic transcript retention."
    ],
    "outOfScope": [
      "Treating GitHub study as weight training; changing the Task 53 read-only file portal."
    ],
    "decisions": [
      "Approve any new chat-context injection and retention defaults before implementation."
    ],
    "area": "P08",
    "checkpoint": "task-117-owned-chat-knowledge",
    "validation": ["tests/test_chat_knowledge.py: 7 passed (no automatic retention or injection; consent and bounded expiry; explicit traced untrusted context creating no Tasks; expiry, withdrawal and changed-revision freshness; cross-conversation and foreign-owner boundaries; permissions and secret-paste guard).","Full Python suite 988 passed, 3 skipped, 2 unrelated pre-existing failures (test_model_set_command, test_model_replacement_uses_existing_assignment_service); docs tests passed."],
    "limitations": ["API only: there are no browser controls yet.","Lexical matching only; traces are process-local and cleared on restart; retained records use the existing local database and are not encrypted.","Withdrawal cannot recall text already sent to a provider, earlier replies or prepared Task proposals."]
  },
  {
    "number": 118,
    "title": "Durable conversation history and recovery",
    "description": "Add explicitly consented durable conversation history with truthful restart and interrupted-turn behavior.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      117
    ],
    "acceptance": [
      "Owner controls retention/deletion; schema migrations preserve provenance and isolate readers.",
      "On restart identify pending/uncertain turns and require review rather than automatic replay.",
      "Test retention opt-out, expiry, restart, deletion scope and interrupted persistence."
    ],
    "outOfScope": [
      "Persisting credentials or silently re-executing an interrupted request."
    ],
    "decisions": [
      "Resolved conservatively: storage is the existing local SQLite database; history is per-conversation opt-in (default off) with an owner-chosen expiry of 1 hour to 90 days, at most 200 stored conversations per owner; stored text is not encrypted at rest (documented) and credentials are never stored; versioned migrations v1 to v2 preserve rows and provenance; restart recovery is read-only, pending turns show as uncertain and must be reviewed (becoming interrupted), never replayed."
    ],
    "area": "P02c / P08",
    "checkpoint": "task-118-durable-chat-history",
    "validation": [
      "tests/test_chat_history.py (10 tests): opt-out default, consent and bounded expiry, restart read-only recovery without replay, uncertain-turn review, expiry purge, deletion scope and owner isolation, pre-call persistence failure fails closed, post-call failure leaves an uncertain turn, v1 to v2 migration, permission denial.",
      "Full Python suite: 998 passed, 3 skipped, 2 unrelated pre-existing failures (test_model_set_command, test_model_replacement_uses_existing_assignment_service); 120 browser tests and 14 docs tests passed."
    ],
    "limitations": [
      "Stored text is unencrypted at rest; history is API-only with no browser panel yet.",
      "Single process: live versus uncertain is decided from in-process state, so a second process sharing the database would see live turns as uncertain.",
      "Recovered conversations are read-only; deleting history does not remove Task 117 retained knowledge or recall text already sent to a provider."
    ]
  },
  {
    "number": 119,
    "title": "Local model resource and loading controls",
    "description": "Expose configured budgets and supported model loading controls with actual hardware/runtime evidence.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      104,
      111
    ],
    "acceptance": [
      "Keep slot eligibility, provider health, installed/loaded model and measured hardware feasibility distinct.",
      "Authorized load/unload/settings changes respect active work and actual provider support.",
      "Show measured/unknown memory and latency; test capacity and unavailable telemetry with fakes.",
      "Allow multiple Employees/Agents to share a configured provider/model without treating each assignment as a separate loaded copy; account for shared loaded-model memory once and each actual concurrent request against provider/model slots.",
      "Admit or load models concurrently only within configured slot budgets and fresh provider/runtime hardware evidence; when physical capacity is unknown, label it UNKNOWN and do not claim the model fits."
    ],
    "outOfScope": [
      "Extracting only a job-specific part of a dense LLM; configured slots as proof of GPU/VRAM fit."
    ],
    "decisions": [
      "Resolved conservatively: query Ollama's supported /api/ps telemetry and keep memory/VRAM measurements distinct from unknown physical capacity and fit; probe latency and operation latency are measured but inference latency stays unknown. Expose load/unload only for configured loopback Ollama, only after fresh installed-catalog and loaded-runtime checks, and only through a separate model-runtime:manage permission. Operations send an empty prompt solely to invoke Ollama's load/unload semantics, use a bounded owner-selected keep-alive, are capped at five minutes, consume configured provider/global/model request slots, and are rejected while the model has active work. Count loaded models once per provider/model, irrespective of Agent assignments. Other providers report lifecycle controls unsupported; no third-party system telemetry, model-part extraction, or unsupported quantization/offload is claimed."
    ],
    "area": "P09",
    "checkpoint": "task-119-local-model-resource-controls",
    "validation": [
      "tests/test_local_models.py: Ollama runtime memory/VRAM/context telemetry, bounded explicit load/unload request semantics, and malformed or unavailable evidence with deterministic HTTP fakes.",
      "tests/test_provider_connections.py: runtime and load/unload behavior, shared model accounting, slot admission, active-work rejection, connection responsiveness during model operations, unavailable telemetry, unsupported Gemini operations, and authenticated API permissions.",
      "tests/test_provider_connections_ui.mjs: 4 tests covering runtime evidence, UNKNOWN hardware/inference claims, CSRF-protected load/unload, confirmation, and distinct permission gating.",
      "Full Python suite: 1001 passed, 6 skipped, 2 unrelated pre-existing failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service).",
      "All browser-module tests: 139 passed; public docs suite: 14 passed. Pylance reported no diagnostics in changed production Python files. No live or paid provider calls."
    ],
    "limitations": [
      "Physical total/available memory and pre-load hardware fit remain UNKNOWN; Ollama-reported loaded-model memory and VRAM are post-load runtime measurements only.",
      "The measured probe and operation durations are not inference latency. No inference benchmark, quality tradeoff, CPU/GPU offload, quantization control, or dense-model part loading is provided.",
      "Load/unload is available only for configured loopback Ollama connections and requests time out after five minutes; other providers expose UNKNOWN runtime telemetry and no lifecycle controls.",
      "Provider request-slot settings are process-local software limits. They do not reserve physical memory, and direct registry changes or multiple app instances are outside the coordination guarantee."
    ]
  },
  {
    "number": 120,
    "title": "Supported streaming and truthful Stop controls",
    "description": "Stream verified provider output into coordinator and Employee chat while keeping interruption and Stop semantics truthful.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      103,
      119
    ],
    "acceptance": [
      "Show chunk progress only from actual Ollama output; unsupported providers retain buffered chat and cannot use streaming routes.",
      "Label Stop as display-only; keep consuming the stream and never claim that provider generation was cancelled.",
      "Persist only the verified final assistant reply; interrupted streams leave user input pending/uncertain without persisting partial assistant text or automatic replay.",
      "Keep streaming within authenticated owner/conversation/Agent boundaries, request-slot limits, bounded protocol/output buffers and provider timeouts."
    ],
    "outOfScope": [
      "Provider cancellation, stopping generation, replay/retry, saving partial assistant output, or enabling streaming for an unvalidated provider."
    ],
    "decisions": [
      "Conservative implementation: only the explicitly validated loopback Ollama provider streams. Stop suppresses displayed chunks while draining to a verified completion; it is not cancellation. On disconnect/error, partial assistant text remains transient and the user turn stays pending/uncertain for explicit owner recovery. Unsupported providers keep buffered behavior."
    ],
    "area": "P02d",
    "checkpoint": "task-120-supported-streaming-truthful-stop",
    "validation": [
      "Focused provider, streaming, chat ownership and history regressions: 79 passed.",
      "Focused coordinator/Employee/provider chat UI tests: 17 passed.",
      "All browser-module tests: 142 passed; public documentation tests: 14 passed.",
      "Full Python suite: 1014 passed, 6 skipped, 2 known unrelated pre-existing failures: test_model_set_command and test_model_replacement_uses_existing_assignment_service.",
      "Pylance reported no diagnostics in the checked Ollama provider, owned Employee chat service and Employee chat API files. No live or paid provider calls."
    ],
    "limitations": [
      "Only configured loopback Ollama is validated for streaming. Gemini and other providers remain buffered; this task does not add cancellation.",
      "Stop only hides later chunks in the UI while the provider stream continues to be consumed; a successful completion is still persisted.",
      "A stream that errors or disconnects leaves a pending/uncertain user turn and no persisted partial assistant response; there is no automatic replay.",
      "The full Python suite retains two unrelated pre-existing model-assignment test failures."
    ]
  },
  {
    "number": 121,
    "title": "Chat-driven GitHub study and research",
    "description": "Accept an explicit repository study request in coordinator chat and return a bounded, source-linked adoption assessment.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      103,
      113
    ],
    "acceptance": [
      "Coordinator chat exposes an explicit objective and owner/repository form; the API requires an open conversation owned by the authenticated principal plus chat:send and github:read.",
      "Preserve the configured exact-repository allowlist; resolve the default branch once to a commit and analyze its immutable tree SHA.",
      "Reuse bounded GitHub discovery, repository analysis, evaluation, and proposal services; report license, dependency manifests, detected languages/frameworks, maintenance metadata, fit, risks, unknowns, and source citations.",
      "Render untrusted source-derived results as text, return a proposal for human review or request more information, and never install, execute, or send source content to an AI provider."
    ],
    "outOfScope": [
      "Search/discovery outside configured repository scope, arbitrary-host research, automatic downloads/install/execution, AI-provider synthesis, or source instructions authorizing actions."
    ],
    "decisions": [
      "Reuse only the existing explicit GitHub repository allowlist, official GitHub API discovery/analyzer, evaluator, and unapproved proposal generator. Do not add search or arbitrary-host retrieval. Require both chat:send and github:read; study an open owned conversation without reading, persisting, or forwarding its transcript. The analyzer resolves the default branch to a commit and queries its immutable tree. Propose only for complete pinned analysis with a known license; otherwise request more information. All proposals remain unapproved."
    ],
    "area": "P10",
    "checkpoint": "task-121-chat-driven-github-study",
    "validation": [
      "Focused repository study, pinned source analysis, evaluator, GitHub inspection and local-owner permission regressions: 90 passed using deterministic fakes.",
      "Coordinator chat UI tests: 13 passed, including same-origin CSRF, explicit scope, inert untrusted output, and denial without github:read.",
      "All 144 browser-module tests and all 14 public documentation tests passed.",
      "Full Python suite: 1025 passed, 6 skipped, and 2 pre-existing model-assignment failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service). No live GitHub or paid/provider calls."
    ],
    "limitations": [
      "The installed app has an empty GitHub repository allowlist unless the embedding host configures the existing GitHub inspection service; no allowlist management UI or environment setting is added.",
      "Only GitHub repositories are analyzed. Arbitrary external-host documentation research and search are excluded.",
      "Commit-pinned source analysis is paired with separately timestamped repository metadata; GitHub metadata is not itself a commit snapshot.",
      "Evaluation and proposals are deterministic decision support, not a semantic AI recommendation, verified compatibility result, human approval, or installation."
    ]
  },
  {
    "number": 122,
    "title": "Isolated adaptation workspace and validation",
    "description": "Develop a selected authorized adaptation in a disposable isolated work area using existing maintenance stages.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      121
    ],
    "acceptance": [
      "Bind exact source/patch identity, allowed files/actions and time/resource limits.",
      "Use an actually enforced supported isolation backend; report unsupported isolation explicitly.",
      "Run scoped tests and code/security review, then present diff, evidence and recovery limits.",
      "Test malicious source, denied scope, failing tests and interrupted experiments.",
      "Require traceable test evidence and an independent review record for proposed changes; preserve the active installation and runtime while experiments run.",
      "Treat proposed software, workflow and approved memory improvements as controlled artifacts; do not train or rewrite model weights."
    ],
    "outOfScope": [
      "Editing active source/runtime or approving/integrating a proposed patch automatically."
    ],
    "decisions": [
      "Owner authorization is the separate local-owner maintenance:experiment permission. Source and exact patch are explicitly supplied and hashed; only selected Python files run through the existing Docker sandbox with an embedding-host approved digest-pinned image. Missing isolation is BLOCKED. Review uses a different Agent ID, requires per-request cloud consent when online, and never approves or integrates."
    ],
    "area": "P11a",
    "checkpoint": "task-122-isolated-adaptation-validation",
    "validation": [
      "Focused Task 122 experiment tests: 12 passed.",
      "Directly affected maintenance, sandbox, authorization, and API regression tests: 166 passed.",
      "Final focused experiment, code-review, and local-access tests after security-review prompt coverage: 33 passed.",
      "Full Python suite: 1043 passed, 3 skipped, 2 known unrelated model-assignment failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service), matching the Task 121 baseline.",
      "Public documentation tests and Python compilation checks passed; git diff --check passed.",
      "No live Docker, Ollama, or paid/cloud provider calls; Docker behavior uses deterministic backend fakes."
    ],
    "limitations": [
      "Default sandbox image policy is empty; the embedding host must configure an allowlisted, locally available digest-pinned image and supported Docker daemon or tests report BLOCKED.",
      "Experiment workspaces, test/review reports, and ownership are process-local; disposal or restart removes them, with no automatic backup or rollback.",
      "Source identity hashes explicitly uploaded selected files; it does not attest a repository commit or prove semantic alignment with proposal text.",
      "Independent review means a distinct Agent ID from the diagnostic author; Agents may share an underlying model/provider. Review remains advisory.",
      "The two full-suite model-assignment failures are pre-existing and unrelated to Task 122."
    ]
  },
  {
    "number": 123,
    "title": "Approved integration and verified recovery",
    "description": "Apply an exact owner-approved adaptation through bounded change control and verify the active result.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      122
    ],
    "acceptance": [
      "Revalidate source/patch/test/review/approval links before applying the change; source files must still match the configured local Git checkout.",
      "Show changed files, dependency/configuration/data classifications, test/review evidence, and the supported Git checkpoint.",
      "Verify the exact checkpoint is the local checkout HEAD after activation; record failure or uncertainty and expose only the tested local Git recovery operation.",
      "Test expired or stale approvals, partial activation failure, and the boundary that external actions cannot be reversed.",
      "Activate only the exact owner-approved artifact after passing scoped tests and independent review with no critical/high findings; require a clean checkout at the checkpoint parent and an approval made after test/review within 24 hours.",
      "Report runtime restart/health and website deployment as not performed; these require a separate explicit operational path. Self-maintenance never automatically trains or changes model weights."
    ],
    "outOfScope": [
      "Self-expanding authority, unrestricted self-modification, runtime restart, website deployment, external side effects, or universal rollback guarantees."
    ],
    "decisions": [
      "Resolved conservatively: activation is limited to a fast-forward of the configured local Git checkout after exact artifact gates; recovery is an owner-triggered Git revert only while that activation is clean HEAD. The running process and website are not restarted or deployed, and external effects are outside recovery scope."
    ],
    "area": "P11b",
    "checkpoint": "task-123-approved-local-activation",
    "validation": [
      "Focused Task 123 activation tests cover exact source/patch/test/review/approval binding, 24-hour approval expiry, stale-source rejection, checkpoint fast-forward, simulated Git failure, and tested Git revert recovery.",
      "Focused maintenance, checkpoint, approval, workflow and local-owner authorization regressions: 57 passed.",
      "Full Python suite: 1048 passed, 3 skipped, and 2 pre-existing unrelated model-assignment failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service), matching the Task 121 baseline.",
      "All 14 public documentation tests passed; Python compilation and git diff --check passed. pyright/Pylance diagnostics were unavailable. No live Docker, Ollama, or cloud/provider calls; deterministic fakes were used."
    ],
    "limitations": [
      "Activation and evidence coordination are process-local; evidence is lost when the API process restarts, while the Git checkpoint/activation commits remain in the repository.",
      "Activation requires the configured source repository to be clean and at the checkpoint parent; external edits and separate processes are not coordinated by the process-local lock.",
      "The API fast-forwards local source but does not restart the running Python process or verify post-restart runtime health. The owner must handle restart separately.",
      "Git recovery is available only while the exact activation commit remains clean HEAD; it cannot reverse website deployment, data migrations, provider calls, or other external side effects."
    ]
  },
  {
    "number": 124,
    "title": "Software and integration inventory panel",
    "description": "Show supported installed applications, repository checkouts, integrations and service versions as separate records.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      123
    ],
    "acceptance": [
      "Use bounded supported inventory adapters and show source, version/revision, status and dependent workflows.",
      "Distinguish system-owned installations from externally managed software and unknown detection.",
      "Test stale/missing inventory and unauthorized inspection."
    ],
    "outOfScope": [
      "Scanning arbitrary credential stores or taking ownership of all PC software."
    ],
    "decisions": [
      "Initial supported sources are the running app, current Python runtime, fixed application checkout, and configured provider connections; no OS-wide software scanning."
    ],
    "area": "P12a",
    "checkpoint": "task-124-read-only-software-inventory",
    "validation": [
      "Focused inventory, local-auth and Web UI Python tests: 28 passed; coverage includes owner authorization, supported-source boundaries, stale and missing inventory, bounded records, and safe omission of credentials and filesystem paths.",
      "Full Python suite: 1054 passed, 3 skipped, 2 pre-existing unrelated failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service); the same failures were recorded before Task 124.",
      "Browser-module suite: 147 passed. Public documentation suite: 14 passed. Python compileall, JavaScript syntax check, git diff --check and full scope/security review passed."
    ],
    "limitations": [
      "Only the running application, current Python runtime, fixed source checkout and configured Ollama/Gemini connections are inspected; installed Windows programs, arbitrary directories, package managers, credentials and remote services are not scanned.",
      "Inventory is a bounded sequential snapshot. Externally managed software is informational, and no install/update/remove action is provided; those actions remain planned under Task 125."
    ]
  },
  {
    "number": 125,
    "title": "Managed install update version and remove",
    "description": "Manage one explicitly supported software adapter with preview, permission checks and data-preserving recovery.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      124
    ],
    "acceptance": [
      "Preview source/version and affected dependents before install/update/pin/change/remove.",
      "Preserve user work/configuration and externally managed installations; destructive/privileged actions require appropriate approval.",
      "Record actual result and offer only verified supported recovery.",
      "Test version changes, denied actions, partial failure and uninstall data-preservation behavior."
    ],
    "outOfScope": [
      "Running arbitrary GitHub installers or assuming every repository is an installable app."
    ],
    "decisions": [
      "Resolved narrowly to Microsoft Visual Studio Code through the official WinGet source, exact Microsoft.VisualStudioCode package ID, user-setup installer only, and current-user scope. Existing/untracked installs remain read-only. Install, update, forward-only exact-version change, pin/unpin and removal each require a fresh five-minute preview bound to source, version/hash, scope and observed package state, then a separate local-owner confirmation. Elevated application processes are denied; no privilege escalation is requested. Removal never requests purge or user-data cleanup and presents the install directory for owner inspection. Only exact reinstall after removal is offered as recovery when the catalog still verifies the previous version; downgrade/rollback after update is not claimed."
    ],
    "area": "P12b",
    "checkpoint": "task-125-managed-vscode-user-lifecycle",
    "validation": [
      "Focused managed-software, inventory and local-owner authentication regressions: 29 passed; 11 new deterministic managed-software tests cover forward version change, denied external install/pin mutation, rejected downgrade, partial failure, confirmation expiry/replay, pin/unpin, removal data preservation and verified recovery.",
      "All browser-module tests: 148 passed, including inert preview/confirmation UI and same-origin CSRF coverage. Public documentation tests: 14 passed.",
      "Full Python suite: 1065 passed, 3 skipped, and 2 pre-existing unrelated failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service), matching the recorded Task 124 baseline. No live package changes, model calls or provider calls.",
      "Python compile/import checks, JavaScript syntax checks and git diff --check passed. Read-only WinGet discovery on this machine identified the pre-existing VS Code as externally managed, verified its user-setup source manifest/hash and install directory, and performed no install/update/pin/remove action."
    ],
    "limitations": [
      "Windows only; only Microsoft.VisualStudioCode from the WinGet source is supported. Existing installations, external pins and machine-scope copies are not adopted or modified. Other packages and arbitrary GitHub installers remain out of scope.",
      "The app does not inspect user-data directories or files within the install directory. VS Code settings/profiles/extensions are not passed to cleanup; the owner must move any personal work stored inside the displayed application directory before removal. Other installer side effects remain package-controlled.",
      "Managed-install provenance is durable in the existing SQLite database, but previews/confirmations and coordination are process-local. This does not coordinate separate app processes, WinGet calls or external package-manager changes; detected version/state conflicts fail closed.",
      "Only forward upgrades are supported. WinGet downgrade/rollback after update is not treated as verified recovery. Exact prior-version reinstall is offered only after removal and still requires a new preview and owner confirmation."
    ]
  },
  {
    "number": 126,
    "title": "One-click local application lifecycle",
    "description": "Provide a supported startup/health/stop/restart flow for the existing Python backend and Web UI.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      103,
      104
    ],
    "acceptance": [
      "Open the local UI without routine CMD use and preserve explicit owner authentication.",
      "Provide a GUI first-run owner setup flow and subsequent GUI startup; do not require command-line password creation on every run.",
      "Handle port conflicts, startup failure, service ownership, shutdown and redacted logs.",
      "Test clean start/stop/restart and prevent accidental remote exposure or duplicate unmanaged services."
    ],
    "outOfScope": [
      "Remote deployment or rewriting the backend for a desktop framework."
    ],
    "decisions": [
      "Resolved to a double-clickable Windows .pyw controller that owns one in-process Uvicorn server thread and a socket pre-bound only to 127.0.0.1:8000. A current-user file lease prevents a second managed GUI controller; the controller never scans for, adopts, signals, or kills another process, and a port conflict fails closed. The first GUI run creates an owner-chosen password and stores only a salted PBKDF2 verifier protected by current-Windows-user DPAPI. Every later GUI start/restart requires that owner password; the backend still requires a separate browser sign-in. Stop and window close request graceful shutdown and never force-kill the service."
    ],
    "area": "P01b / P13a",
    "checkpoint": "task-126-local-application-lifecycle",
    "validation": [
      "Eleven deterministic lifecycle and credential tests passed, covering clean start/health/stop/restart, preserved owner login, current-user exclusive lease behavior, second-controller exclusion, port conflict without taking over another listener, loopback-only binding, safe startup failure, real Windows DPAPI round-trip, first-run password validation and corrupted credential fail-closed behavior.",
      "The combined lifecycle/credential/local-access regression selection passed 24 tests. Full Python suite: 1076 passed, 3 skipped and the same 2 pre-existing unrelated model-assignment failures; public documentation tests passed. Browser-module tests were not rerun because no browser implementation changed. No live model/provider calls, package actions or remote listener were used.",
      "Python compilation/import, launcher entry-point compilation, update-manifest JSON parsing and git diff --check passed. Pylance/pyright diagnostics were unavailable in the environment."
    ],
    "limitations": [
      "The launcher requires Windows, the current Python environment with Tkinter and the repository checkout; it is not an installed executable. Electron packaging and runtime/dependency bundling are Task 127.",
      "The GUI owns one Uvicorn server thread inside its current process on fixed 127.0.0.1:8000. It cannot manage a CLI-started server, another app process or services on other ports. Port conflicts are reported and the existing listener is left untouched.",
      "The owner enters the password in the GUI on every start/restart and still signs in through the Web UI. DPAPI protects only a salted verifier; sessions, provider credentials and runtime state keep their existing lifecycle. The launcher does not persist raw passwords or application logs. Lost/corrupt verifier recovery is an explicit owner action: remove only `%LOCALAPPDATA%\ERSELMETZ AI\owner-credential.dpapi` and repeat GUI setup; application data is retained."
    ]
  },
  {
    "number": 127,
    "title": "Windows executable and installer",
    "description": "Package the shared Web UI and Python backend into an owner-approved desktop distribution.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      126
    ],
    "acceptance": [
      "Package the owner-approved Electron desktop shell with a Next.js static-export UI and the existing Python backend/API/AI control services; serve the UI and API from the same loopback origin without a separate production Next.js server.",
      "Keep Node privileges in Electron main/preload, with context isolation, renderer sandboxing and a narrow desktop bridge; document supported runtime/dependency versions.",
      "A clean supported Windows installation can complete GUI first-run owner setup, configure supported local/online providers, launch, authenticate, use chat, stop and restart without routine CMD.",
      "Define updates, credential storage, logs, uninstall and user-data preservation; validate packaging and recovery."
    ],
    "outOfScope": [
      "Using the public Vercel documentation site as the Python runtime host."
    ],
    "decisions": [
      "Electron 44.7.0 is the Windows shell; Next.js 16.4.0/React 19.3.0 is exported statically under /desktop/ and served by the existing FastAPI app. Python 3.14 x64 is packaged as a PyInstaller sidecar. The installer is per-user, unsigned, has no elevation helper, no auto-updater, and preserves %LOCALAPPDATA% data when uninstalled. Owner credentials use the existing current-user DPAPI verifier; startup secrets travel over a private child-process stdin pipe."
    ],
    "area": "P13b",
    "checkpoint": "task-127-windows-electron-installer",
    "validation": [
      "Built the Next.js static export and Windows x64 NSIS package; installed it into a fresh temporary per-user profile. The real installer smoke passed first-run owner setup, owner browser sign-in, existing chat/provider page access, graceful stop, restart with owner verification and session invalidation, uninstall preserving DPAPI owner data, and reinstall recovery. No provider credentials or live model response were used.",
      "The frozen Python sidecar smoke passed setup, loopback health, static UI/API origin, local login, existing chat/provider routes, stop/restart, and retained DPAPI verifier. Focused desktop/runtime/launcher/local-access and existing chat browser regressions passed 28 tests; all 148 existing browser-module tests passed; Electron security tests passed 4; public docs tests passed 14. Full Python suite: 1083 passed, 3 skipped, and the same two pre-existing unrelated failures in test_model_set_command and test_model_replacement_uses_existing_assignment_service.",
      "Electron security checks confirm context isolation, renderer sandboxing, disabled Node integration, a three-operation preload bridge, denied permissions and new windows, and owned local navigation. Installer inspection confirms per-user NSIS, no elevation helper, no auto-update configuration, and unsigned output. Python compilation/import and git diff --check passed. Pylance/pyright were unavailable."
    ],
    "limitations": [
      "This is an unsigned local Windows x64 installer, not a signed public release. Updates are manual reinstallations; no update feed or background updater exists. Uninstall intentionally preserves %LOCALAPPDATA%\\ERSELMETZ AI, including the DPAPI owner verifier and application data.",
      "The desktop controller uses only 127.0.0.1:8765 and coordinates its own managed service instance. It fails closed on port/ownership conflicts and does not adopt, terminate, or coordinate with direct Python CLI, Task 126 launcher, another process, or other ports. Existing web/API routes and provider capabilities are reused; this task adds no provider, model, self-maintenance, voice, queue, or orchestration behavior.",
      "Automated packaging verification used temporary credentials and deterministic page/service checks. No Ollama/Gemini credential was configured, and no live provider/model generation was attempted. The installer smoke visited chat and provider pages but does not establish production readiness or AI response quality.",
      "Building requires the existing Python 3.14 x64 project environment, Node.js 22.12 or newer, network access to pinned package registries, Windows, and the repository checkout. The current installer is development-only and is not a production signed or auto-updating distribution.",
      "npm audit reports no vulnerabilities in either runtime dependency set. The Electron build-tool dependency graph reports 8 moderate advisories in its transitive sprintf-js/roarr/@electron/get chain; these are build-only dependencies and are not packaged into the installed app. The pinned toolchain was retained and the finding is recorded for a separate dependency update."
    ]
  },
  {
    "number": 128,
    "title": "Optional voice interaction",
    "description": "Add explicitly enabled speech input/output while preserving typed chat and the same action gates. Local app audio retention is set to none; optional Gemini cloud transcription requires per-use consent and a configured app-run request budget.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      127
    ],
    "acceptance": [
      "Visible microphone/recording controls and clear start/stop behavior.",
      "Offer explicit local or cloud speech processing choices with per-use consent, a configured app-run request budget and an explicit zero app-side audio-retention policy; disclose that provider-side billing and retention are controlled externally. Local processing is the default where supported.",
      "Spoken requests use identical authorization/approval checks; typed chat remains fully usable.",
      "Test microphone denial, disabled voice, errors and sensitive-content handling.",
      "Let the owner interrupt capture, playback and speech requests; distinguish stopping local recording/audio from confirmed provider cancellation, and never report unconfirmed remote cancellation as successful.",
      "Test interruption at capture, transcription, model generation and playback stages, including providers without cancellation support and quota/budget exhaustion."
    ],
    "outOfScope": [
      "Always-on recording or voice bypassing action approval."
    ],
    "decisions": [
      "Use verified browser on-device speech recognition only; unsupported local recognition has no cloud fallback. Offer optional Gemini 3.5 Transcribe for 16 kHz mono PCM WAV clips up to 10 seconds, inline only (no Files API), after one-use consent and a 1–100 US-cent app-run budget reserving one cent per attempted provider request. This app-side ceiling bounds its own requests but cannot enforce the connected Google account's final invoice.",
      "App-side audio retention is configured to none; captured audio stays in memory and is discarded after use or cancellation. Gemini API provider-side logging/retention depends on the connected account tier and settings and cannot be configured or verified by this app, so the consent notice discloses this boundary. Local reply audio uses an installed local speech voice only.",
      "Stop interrupts local capture/playback and local waiting. Gemini transcription and model-generation requests have no confirmed provider cancellation; stopped remote outcomes remain unknown, consume the local request reservation and are never retried automatically."
    ],
    "area": "P14",
    "checkpoint": "task-128-optional-voice-interaction",
    "validation": [
      "Focused deterministic voice, owner-auth, Gemini setup, chat and context regressions: 45 passed. All 159 browser-module tests passed. Electron security suite: 5 passed. Static Next.js desktop build, Python compilation, and an isolated frozen-sidecar build/voice-route authentication smoke passed.",
      "Full Python suite: 1093 passed, 3 skipped, and the same 2 pre-existing baseline failures recorded at Task 127 (test_model_set_command and test_model_replacement_uses_existing_assignment_service). No live Gemini/Ollama or microphone session was used.",
      "Public documentation tests: 14 passed. git diff --check and reviewed security/scope diff passed. Pylance/pyright were unavailable."
    ],
    "limitations": [
      "Cloud budget is a process-local app request ceiling with a one-cent reservation per attempt, not an enforceable cap on Google's account billing. Provider prices, account tier, quotas and retention are external and may change; Google request retention cannot be set or verified by this app. Only inline audio is sent; no provider Files/Interactions storage API is used.",
      "On-device speech recognition and local speech output depend on browser/OS support and installed language/voice packs. Unsupported local recognition does not fall back to cloud. No live microphone or paid provider calls were used in tests.",
      "Remote Gemini or chat provider cancellation is unsupported; stopping the local wait cannot establish whether a remote request completed or was charged.",
      "The Task 127 installer artifact was not rebuilt; the frozen backend was rebuilt and smoke-tested in an isolated temporary directory. Clean-install/release verification remains Task 129."
    ]
  },
  {
    "number": 129,
    "title": "Command center usability and release acceptance",
    "description": "Verify the supported owner workflows on a clean local installation and publish actual readiness evidence.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [
      104,
      105,
      106,
      107,
      108,
      109,
      110,
      111,
      112,
      113,
      114,
      115,
      116,
      117,
      118,
      119,
      120,
      121,
      122,
      123,
      124,
      125,
      126,
      127,
      128
    ],
    "acceptance": [
      "Exercise supported onboarding, local/approved online chat, positions, reviewed dispatch, evidence/maps, approved adaptation, software management and desktop lifecycle.",
      "Test the Electron/Next.js desktop build, 3D-first maps with accessible fallback, unauthorized access, isolation, resource exhaustion, restart/recovery and secret handling.",
      "Verify multiple Employees sharing models and concurrent local/online work under configured provider/model slots and measured hardware limits; report UNKNOWN when capacity evidence is absent.",
      "Report tested providers/models/platforms, budgets, skipped/unsupported capabilities and unresolved decisions.",
      "Update docs/status only for demonstrated outcomes and checkpoint the verified release."
    ],
    "outOfScope": [
      "Marking unresolved gates complete or claiming unrestricted autonomous Jarvis behavior."
    ],
    "decisions": [
      "Acceptance target: the documented local Windows 11 x64 installer. Other operating systems, live-provider execution, measured hardware capacity, production signing and automatic updates remain deferred."
    ],
    "area": "Release acceptance",
    "checkpoint": "task-129-command-center-release-acceptance",
    "validation": [
      "Release target: clean local Windows 11 x64 package built with Python 3.14.7, Node.js 24.19.0, Electron 44.7.0 and Next.js 16.4.0; the unsigned NSIS installer was installed from a fresh temporary profile.",
      "Installer SHA-256: 206A36D5C94FD76B2696C01F95CD842C24E3A79FD05FEB7FDB45F3DA101DC091. The Task 129 local artifact is desktop/release/task129/ERSELMETZ-AI-Setup-0.1.0-win-x64.exe.",
      "Next.js static production build and isolated PyInstaller backend build passed. Frozen-sidecar smoke passed first-run owner setup, HttpOnly owner session, chat/provider page availability, DPAPI verifier retention, restart and graceful shutdown.",
      "Actual installed-Electron smoke passed first-run setup/sign-in, owner password verification on restart, protected chat/provider pages, graceful close, uninstall data retention and reinstall recovery.",
      "Deterministic regressions: 159 browser-module tests, 5 Electron security tests and 14 public documentation tests passed. Full Python suite: 1093 passed, 3 skipped, and the two previously recorded failures in test_model_set_command and test_model_replacement_uses_existing_assignment_service.",
      "npm ci reported 8 moderate advisories in the build-time Electron dependency tree; desktop packaging does not include node_modules."
    ],
    "limitations": [
      "Only a local Windows 11 x64 install was release-tested. Linux, macOS, other Windows versions and public distribution were not tested.",
      "No live Ollama/Gemini/provider request, API credential, microphone capture or model inference was used. Chat/provider pages and provider behavior were tested with existing deterministic fakes, not live services.",
      "No physical GPU/VRAM/RAM measurement or concurrent multi-Employee mixed local/online inference benchmark was performed. Hardware feasibility and live execution capacity remain UNKNOWN; configured slots are not a hardware-capacity guarantee.",
      "The installer is unsigned, has no automatic updater, and is a local acceptance artifact rather than a production-signed or publicly distributed release.",
      "The full Python suite retains the same two previously recorded model-assignment failures; 3 tests were skipped. Eight moderate advisories were reported for the build-time Electron dependency tree.",
      "This checkpoint does not claim production completeness, unrestricted autonomous operation, or unrestricted self-maintenance."
    ]
  },
  {
    "number": 130,
    "title": "Optional vector memory and RAG foundation",
    "description": "Add explicit, local semantic indexing and scoped retrieval over already-approved memory while preserving deterministic context behavior.",
    "category": "Post-100 Usable Command Center",
    "status": "completed",
    "dependsOn": [117, 129],
    "acceptance": [
      "Add replaceable embedding and vector-store abstractions with an optional local implementation; missing optional dependencies do not prevent core startup and models are never downloaded automatically.",
      "Chunk explicitly selected retained conversation, Project, or Corporation knowledge with deterministic bounded chunks and safe provenance metadata; never scan arbitrary files, all database records, transcripts, credentials or generated responses.",
      "Require explicit owner indexing, enforce exact scope on search, recheck current owner/reader access, revision and expiry before returning any chunk, and invalidate derived vectors on source correction, deletion, withdrawal or reader revocation.",
      "Preserve existing lexical retrieval and provide bounded provenance-tagged RAG context as untrusted reference data; do not call Providers or inject context automatically.",
      "Expose truthful capability state and explicit indexing/scoped search through existing authenticated application/API/UI boundaries; default API authentication remains fail-closed.",
      "Use deterministic fake embedding/vector adapters in tests. Verify chunking, indexing, retrieval, limits, provenance, scope isolation, stale/revoked/expired sources, unavailable backend, auth, and no provider/task side effects.",
      "Document optional installation/configuration, local storage/privacy limits, supported scopes, provenance, limitations and the separate read-only Task 53 documentation portal."
    ],
    "outOfScope": [
      "Automatic transcript retention or generated-answer learning; arbitrary filesystem or automatic whole-database indexing; editing or publishing documentation; automatic chat/planning injection; Provider generation; model selection/routing; Voice, Vision, Automation or 3D Brain work."
    ],
    "decisions": [],
    "area": "P16",
    "checkpoint": "task-130-semantic-memory-rag-foundation",
    "validation": [
      "Focused semantic-memory and directly affected context, conversation, Project, Corporation-knowledge and memory-management regressions: 104 passed. New deterministic semantic tests: 12 passed; memory UI browser-module tests: 12 passed.",
      "Full Python suite: 1107 passed, 3 skipped, and the same two pre-existing model-assignment failures in test_model_set_command and test_model_replacement_uses_existing_assignment_service.",
      "The optional Sentence Transformers and Chroma adapters were contract-tested with deterministic stubs. No model download, internet use by the feature, live Ollama, GPU, or Provider generation was used.",
      "Public documentation site tests: 14 passed, including task-count, completion-state, overview-page and link checks."
    ],
    "limitations": [
      "The desktop installer does not bundle optional semantic dependencies; actual Chroma/Sentence Transformers package integration and installed-model performance were not tested in this checkpoint.",
      "Indexing is explicit and limited to retained conversation, Project, and Corporation memory. Documentation files, arbitrary paths, whole-database scans and automatic chat/planning injection are not supported.",
      "SQLite content and local derived vectors are unencrypted at rest. Owners must manage the configured vector directory alongside SQLite; physical secure erasure and backup deletion are not guaranteed.",
      "The deterministic fake embedding provider validates ranking/scope contracts but is not a substitute for evaluating a production embedding model's relevance quality."
    ]
  },
  {
    "number": 131,
    "title": "Supported packaging and distribution strategy",
    "description": "Define supported distribution targets, prerequisites, trust, and upgrade boundaries beyond the currently verified Windows installer.",
    "category": "Phase A - Install and Onboarding",
    "status": "completed",
    "dependsOn": [
      127,
      129
    ],
    "acceptance": [
      "Document supported and unsupported targets, install modes, prerequisites, update source, signature expectations, and recovery boundaries.",
      "Keep Windows x64 evidence distinct from future platform support."
    ],
    "outOfScope": [
      "Do not claim one-click installation or production readiness.",
      "Do not install or change packages in this planning task."
    ],
    "decisions": [],
    "area": "P17",
    "checkpoint": "task-131-supported-packaging-distribution-strategy",
    "validation": [
      "Documented target support, install modes, build prerequisites, update source, signing expectations, and recovery limits in desktop/README.md and the public Architecture page.",
      "Task 129 artifact/hash and clean-install evidence remain the only verified installer target; no other platform is claimed.",
      "Public docs site tests: 15 passed; update manifest/API tests: 6 passed. Node syntax, manifest JSON parsing, and git diff --check passed."
    ],
    "limitations": [
      "Only Windows 11 x64 has local acceptance evidence. The installer is unsigned and not publicly distributed; no signed-release process, public update source, automatic updater, cross-version migration, downgrade, or database rollback is verified."
    ]
  },
  {
    "number": 132,
    "title": "Guided first-run setup and capability detection",
    "description": "Guide a new owner through a clear first-run path, explaining how to open and use ERSELMETZ AI, complete minimum setup, and truthfully detect supported providers, models, permissions, and optional capabilities.",
    "category": "Phase A - Install and Onboarding",
    "status": "completed",
    "dependsOn": [
      104,
      112,
      119,
      124,
      126,
      131
    ],
    "acceptance": [
      "Show install health, detected configuration, missing prerequisites, and UNKNOWN states from bounded supported checks.",
      "Provide the shortest supported path from opening the app to usable chat without routine terminal commands.",
      "Separate beginner-facing setup guidance from advanced operator configuration and explain common chat and organization workflows."
    ],
    "outOfScope": [
      "Do not download models, connect providers, or change assignments without explicit owner action.",
      "Core startup remains usable when optional capabilities are absent."
    ],
    "decisions": [],
    "area": "P17",
    "checkpoint": "task-132-guided-first-run-setup",
    "validation": ["Next.js static production build passed; 3 deterministic onboarding tests and 5 existing Electron security tests passed; public docs suite passed (15 tests); syntax, JSON and diff checks passed."],
    "limitations": ["The overview confirms the local service process, not installer signature or package integrity. Provider availability, installed model inventory, and optional capability packs remain UNKNOWN until existing supported explicit checks are run; model inventory is available separately in local-owner mode. No live provider check, model download, installer rebuild, or packaged-install smoke was performed for this UI-only checkpoint."]
  },
  {
    "number": 133,
    "title": "Provider and model setup guidance",
    "description": "Explain supported provider/model setup and readiness through clear beginner guidance and a distinct advanced operator settings area using existing adapters and owner-managed credentials.",
    "category": "Phase A - Install and Onboarding",
    "status": "completed",
    "dependsOn": [
      72,
      104,
      112,
      132
    ],
    "acceptance": [
      "Distinguish registration, service availability, installed models, assignment, software capacity, and measured hardware evidence.",
      "Give sanitized guidance without requesting secrets in ordinary chat.",
      "Make routine chat and basic preferences easy to find while grouping provider, model, connection, capability, security, resource, and diagnostic controls for operators."
    ],
    "outOfScope": [
      "Do not add unsupported providers or equate availability with execution feasibility."
    ],
    "decisions": [],
    "area": "P17",
    "checkpoint": "task-133-provider-model-setup-guidance",
    "validation": ["Next.js static production build passed; 4 deterministic onboarding and provider-guidance tests and 5 Electron security tests passed; public documentation tests passed; roadmap, manifest, syntax and diff checks passed."],
    "limitations": ["Guidance covers only the existing Ollama and Google Gemini setup paths. The home screen does not make provider calls, verify hardware fit, edit credentials, or mutate assignments. There is no dedicated resource-settings page; configured request slots represent software concurrency only. No general preferences page exists yet; Task 171 remains the planned unified-preferences scope. The Electron installer was not rebuilt; a fresh package is required to include these UI source changes."]
  },
  {
    "number": 134,
    "title": "Optional capability pack lifecycle",
    "description": "Manage separately declared optional capability packs with versioned manifests, explicit preview/confirmation, and graceful unavailable states.",
    "category": "Phase A - Install and Onboarding",
    "status": "deferred",
    "dependsOn": [
      131,
      132,
      133
    ],
    "acceptance": [
      "Keep the base installation independent of heavy vision, speech, knowledge, and automation packages.",
      "Show source, version, dependency impact, state, and removal/recovery behavior before changes."
    ],
    "outOfScope": [
      "Do not install every candidate library or allow arbitrary package execution.",
      "Package presence grants no capability permissions."
    ],
    "decisions": [
      "Define package source trust and rollback guarantees during implementation review."
    ],
    "area": "P17",
    "checkpoint": null,
    "validation": [],
    "limitations": ["Deferred before implementation because the current packaged runtime has no verified first-party pack artifact source, publisher trust anchor, or isolated runtime-loading boundary. This task remains incomplete. Task 152 uses a separately installed optional dependency and does not install or manage capability packs, so it does not require this lifecycle."]
  },
  {
    "number": 135,
    "title": "Semantic retrieval quality evaluation",
    "description": "Evaluate Task 130 semantic retrieval against a versioned, permission-safe test set with measurable relevance and failure reporting.",
    "category": "Phase B - Knowledge and RAG",
    "status": "completed",
    "dependsOn": [
      66,
      117,
      130
    ],
    "acceptance": [
      "Use deterministic fixtures for lexical, semantic, stale, expired, and unauthorized records.",
      "Report relevance and false-positive/negative examples without exposing private source content."
    ],
    "outOfScope": [
      "Do not claim model quality from fake-provider contract tests.",
      "Do not auto-change thresholds or index content."
    ],
    "decisions": [],
    "area": "P18",
    "checkpoint": "task-135-semantic-retrieval-evaluation",
    "validation": [
      "Resolved evaluation policy: use Recall@5, Precision@5, and mean reciprocal rank (MRR) for synthetic relevance cases with a 1.0 threshold for each, lexical Recall@5 of 1.0, and zero stale, expired, or unauthorized record leakage. These are fixture-contract thresholds, not production-model quality claims.",
      "Versioned deterministic fixture tests passed for semantic paraphrase/exact relevance, unchanged lexical retrieval, stale revision rejection, expiry rejection, and unauthorized-owner isolation. Recall@5 1.0, Precision@5 1.0, MRR 1.0, lexical Recall@5 1.0, and zero excluded-record leaks on the synthetic fixture.",
      "Focused Task 130 semantic memory, context retrieval, and chat knowledge regressions plus Task 135: 36 passed. Update manifest tests: 6 passed; public documentation tests: 15 passed. Full Python suite: 1105 passed, 6 skipped, with two unrelated existing failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service."
    ],
    "limitations": [
      "The versioned fixture and expected report use deterministic synthetic embeddings; they do not measure relevance quality of Sentence Transformers or any production embedding model. The full Python suite still has two unrelated existing model-assignment failures documented in validation."
    ]
  },
  {
    "number": 136,
    "title": "Hybrid lexical and semantic retrieval",
    "description": "Combine existing deterministic lexical retrieval with Task 130 semantic candidates under explicit, explainable ranking policy.",
    "category": "Phase B - Knowledge and RAG",
    "status": "completed",
    "dependsOn": [
      66,
      117,
      130,
      135
    ],
    "acceptance": [
      "Preserve exact ownership, scope, revision, expiry, provenance, and result-size checks.",
      "Expose bounded ranking contributions; retain lexical-only operation when vectors are unavailable."
    ],
    "outOfScope": [
      "Do not inject results into chat automatically or change routing."
    ],
    "decisions": [
      "Use an opt-in per-call rrf-v1 reciprocal-rank policy. The Task 135 synthetic fixture validates access/retrieval contracts but does not establish real-model ranking quality; the existing lexical default remains unchanged."
    ],
    "area": "P18",
    "checkpoint": "task-136-hybrid-lexical-semantic-retrieval",
    "validation": [
      "Focused context, semantic-memory, and Task 135 evaluation regressions: 31 passed.",
      "The hybrid call requires explicit rrf-v1 selection, reports bounded lexical/semantic contributions, rechecks current provenance and revision, and falls back to lexical-only when the optional vector capability is unavailable. Existing lexical retrieval and chat/routing behavior are unchanged.",
      "Full Python suite: 1107 passed, 6 skipped, 2 failed in the same unrelated pre-existing model-assignment tests: tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service."
    ],
    "limitations": [
      "Hybrid retrieval is an explicit application-service capability and is not automatically injected into chat or routing. RRF is opt-in per call; the synthetic Task 135 fixture makes no production embedding relevance claim."
    ]
  },
  {
    "number": 137,
    "title": "Semantic index lifecycle and observability",
    "description": "Provide bounded rebuild, consistency inspection, cleanup, and recovery for derived Task 130 vectors.",
    "category": "Phase B - Knowledge and RAG",
    "status": "completed",
    "dependsOn": [
      65,
      130,
      135
    ],
    "acceptance": [
      "Rebuild only explicitly retained authorized sources and show progress, failure, stale counts, and storage use.",
      "Preserve authoritative memory if vector operations fail."
    ],
    "outOfScope": [
      "Do not promise secure erasure of disk blocks/backups or scan arbitrary files/all database rows."
    ],
    "decisions": [
      "Use a synchronous bounded operation: a deterministic fake-adapter benchmark indexed 10 short retained sources in approximately 0.011 seconds total (maximum single-source time approximately 0.0021 seconds), and the repository has no durable job infrastructure. The benchmark does not measure local embedding-model latency. Rebuild accepts at most 10 explicit source IDs; reports per-source completion/failure; inspection and cleanup are limited to the same explicit selection."
    ],
    "area": "P18",
    "checkpoint": "task-137-semantic-index-lifecycle-observability",
    "validation": [
      "Focused semantic memory, context retrieval, and retrieval evaluation regressions: 35 passed.",
      "Lifecycle API operations use the existing memory:index permission, operate only on explicit retained authorized source IDs, expose bounded progress/failure/stale counts/storage usage, and preserve authoritative memory when vector operations fail. Cleanup removes derived vectors only; it makes no secure-erasure claim.",
      "Full Python suite: 1111 passed, 6 skipped, and 2 failed in the same unrelated pre-existing model-assignment tests: tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service."
    ],
    "limitations": [
      "Operations are synchronous and bounded to 10 explicit source IDs; there is no durable background job or cross-process coordination.",
      "The performance measurement used a deterministic fake adapter and is not a local embedding-runtime performance claim. Storage usage is a bounded measurement of the configured vector directory and can be unavailable when the scan is incomplete."
    ]
  },
  {
    "number": 138,
    "title": "Owner-reviewed AI knowledge proposals",
    "description": "Let an AI prepare provenance-bound knowledge proposals from an owner-selected source for explicit human review and acceptance.",
    "category": "Phase B - Knowledge and RAG",
    "status": "completed",
    "dependsOn": [
      121,
      130,
      135
    ],
    "acceptance": [
      "Show source revision, claims/excerpts, confidence limits, destination scope, expiry, and exact changes.",
      "Acceptance creates only explicitly retained/versioned knowledge; rejection or more-information is valid."
    ],
    "outOfScope": [
      "Do not retain transcripts, ingest repositories, or train model weights automatically.",
      "Untrusted source text cannot expand permissions."
    ],
    "decisions": [
      "Limit sources to one owner-selected retained Conversation or Project memory record; exclude transcripts not separately retained, repositories, arbitrary files, and published Corporation scope. Use only the owner-selected existing Agent when it is assigned to the configured loopback Ollama provider; reject cloud and unknown providers. No cloud consent flow is introduced because online generation is out of scope. Proposals expire within 15 minutes or at source expiry, whichever comes first, and acceptance creates a new retained summary only in the exact source scope and scope ID."
    ],
    "area": "P18",
    "checkpoint": "task-138-owner-reviewed-knowledge-proposals",
    "validation": [
      "Focused knowledge-proposal, memory-management API, semantic-memory, and existing coordinator Task proposal regressions: 42 passed.",
      "The owner reviews exact generated content, excerpt-backed claims, source revision, expiry, destination scope, and proposal digest. Acceptance rechecks current owner access and source revision before creating one retained private summary; reject and more-information outcomes write nothing. Cloud Providers and arbitrary external content are excluded, and proposals are process-local/short-lived.",
      "Full Python suite: 1118 passed, 6 skipped, and 2 failed in the same unrelated pre-existing model-assignment tests: tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service. Public docs and update-manifest checks, compilation/import, and diff checks passed."
    ],
    "limitations": [
      "Generation is limited to explicitly requested local loopback Ollama use through an existing Agent assignment. It was tested with deterministic fake generation; no live Ollama request or quality claim was made.",
      "Pending proposals are held in bounded process memory for at most 15 minutes and are lost on restart. The accepted summary retains the same private scope and expiry; publication, chat transcript retention, arbitrary sources, UI, and documentation-portal writes are not implemented."
    ]
  },
  {
    "number": 139,
    "title": "Versioned documentation review workflow",
    "description": "Add draft, review, approval, version history, and recovery for proposed documentation while preserving the Task 53 portal boundary until migration is approved.",
    "category": "Phase B - Knowledge and RAG",
    "status": "completed",
    "dependsOn": [
      53,
      130,
      138
    ],
    "acceptance": [
      "Keep drafts separate from published documents and require approval of each exact version.",
      "Record provenance, reviewer, approval time, diff, version, and recovery evidence."
    ],
    "outOfScope": [
      "Do not give AI direct write access to published Markdown or auto-publish."
    ],
    "decisions": [
      "Drafts and append-only version history are stored in dedicated tables in the local SQLite database, separate from published Markdown and the Task 53 portal.",
      "Optimistic expected-version checks prevent stale edits; every edit/recovery creates an unapproved version, and approval binds the current version and SHA-256 digest.",
      "History is retained without automatic pruning, bounded to 100 draft documents and 50 versions per document; reaching a limit fails closed. Recovery copies an earlier version into a new version.",
      "Portal migration remains unapproved. No publication endpoint, AI direct write, filesystem path selection, or automatic publishing is provided."
    ],
    "area": "P18",
    "checkpoint": "task-139-versioned-documentation-review",
    "validation": [
      "Documentation review and existing read-only documentation API tests: 15 passed, 2 skipped.",
      "Draft ownership, exact-version approval, digest mismatch, stale edit conflict, reviewer/time provenance, diffs, append-only recovery, separate permission, and published-route read-only behavior were verified.",
      "Full Python suite: 1123 passed, 6 skipped, and the same two pre-existing unrelated model-assignment failures: tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service. Public docs tests: 15 passed; update-manifest tests: 6 passed; Python compilation and diff checks passed."
    ],
    "limitations": [
      "Review approval records owner approval only; it does not publish or change files in corporation_docs or the public docs site. Portal migration requires a later explicit design and task.",
      "The local SQLite history has no automatic retention cleanup and is bounded by fixed document/version counts; no secure-erasure guarantee is made. Multi-process write contention relies on SQLite transactions and expected-version checks."
    ]
  },
  {
    "number": 140,
    "title": "Central capability permission model",
    "description": "Define and enforce centralized least-privilege authorization for existing and future optional capabilities.",
    "category": "Phase C - Capability Governance",
    "status": "completed",
    "dependsOn": [
      92,
      102
    ],
    "acceptance": [
      "Represent capability identity, scope, permissions, risk, and deny-by-default state independently from inventory.",
      "Enforce authorization in application services as well as UI."
    ],
    "outOfScope": [
      "Inventory declarations and organizational titles grant no authority.",
      "Do not broaden default API authentication."
    ],
    "decisions": [
      "Preserve existing AuthenticatedPrincipal permission strings and route meanings as canonical compatibility grants. Require every route permission to map to a centrally declared capability; unknown capabilities deny access.",
      "Capability definitions are separate from Task 92 inventory and contain a stable ID, required permission, scope type, risk level, and disabled-by-default metadata. Existing resource-owner checks remain in their domain services; no role/title/inventory-based grants or permission migration are introduced."
    ],
    "area": "P19",
    "checkpoint": "task-140-central-capability-permissions",
    "validation": [
      "Capability authorization, API, local-owner, documentation API/review tests: 38 passed, 2 skipped.",
      "Unknown capability, missing grant, wrong scope type, foreign principal scope, explicit permission compatibility, risk metadata, and direct application-service authorization were verified. Existing API permission strings and default rejecting authentication remain unchanged.",
      "Full Python suite: 1127 passed, 6 skipped, with the same two pre-existing unrelated failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service. Public docs tests: 15 passed; update-manifest tests: 6 passed; Python compilation and diff checks passed."
    ],
    "limitations": [
      "This task centralizes declared permissions and enforcement helpers but does not add grant creation/revocation, persistence, UI management, or per-resource grant storage; those remain Task 141 scope.",
      "Non-principal resource ownership and state are still verified by the existing domain services; the policy checks the declared capability, permission, and scope type. Inventory descriptions remain non-authoritative."
    ]
  },
  {
    "number": 141,
    "title": "Capability grants and enable/disable policy",
    "description": "Add explicit per-capability enablement and revocable session-scoped grants, with owner-configured persistent policy only where the capability permits it, under Task 140.",
    "category": "Phase C - Capability Governance",
    "status": "completed",
    "dependsOn": [
      140
    ],
    "acceptance": [
      "Show grantor, capability scope, session or explicitly configured persistent policy, expiry, and revocation status.",
      "Default to disabled unless the owner explicitly configures a safe policy."
    ],
    "outOfScope": [
      "Do not create grants implicitly from login, title, Agent role, or installed package."
    ],
    "decisions": [
      "Use only bounded process-local owner-managed settings and short-lived principal-scoped grants. Grantable capabilities must be explicitly marked low-risk and session-grantable; owner enablement is required before issuing a grant. High-risk, moderate-risk, unknown, non-principal, and already-held legacy permissions cannot receive an additional grant.",
      "No persistent grant mode is configured. Policy toggles are process-local and default disabled; grants last at most one hour and are invalidated on revocation, disablement, logout, or session expiry. Existing Task 140 permission strings remain compatible and are not silently migrated or revoked by this grant policy."
    ],
    "area": "P19",
    "checkpoint": "task-141-capability-grants-session-policy",
    "validation": [
      "Capability grant, authorization, and local access focused tests: 19 passed.",
      "Verified disabled-by-default policy, CSRF-protected owner enablement, principal-scoped session grant, exact expiry, duplicate prevention, explicit revocation, disablement revocation, and denial for high-risk or foreign-scope grants. Grant snapshots expose grantor, capability, scope, session, expiry, status, and session-only persistence.",
      "Full Python suite: 1129 passed, 6 skipped, with the same two pre-existing unrelated failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service. Public docs tests: 15 passed; update-manifest tests: 6 passed; Python compilation and git diff checks passed."
    ],
    "limitations": [
      "Grant and enablement history exists only in bounded process memory and is lost on restart. No persistent policy is configured because no capability has a reviewed persistence mode yet.",
      "This API exposes owner controls and inspectable snapshots; it does not add a dedicated graphical management screen. Existing compatibility permissions remain unchanged by grant toggles."
    ]
  },
  {
    "number": 142,
    "title": "Action risk levels and approval policy",
    "description": "Classify capability actions by impact and require matching owner confirmation for protected or high-impact work.",
    "category": "Phase C - Capability Governance",
    "status": "completed",
    "dependsOn": [
      83,
      140,
      141
    ],
    "acceptance": [
      "Bind approvals to exact action, target, scope, policy version, and expiry.",
      "Recheck authorization and target state immediately before execution."
    ],
    "outOfScope": [
      "A chat instruction, prior approval, or model output is not a reusable grant.",
      "Never auto-approve irreversible actions."
    ],
    "decisions": [
      "Use the Task 140 low/moderate/high catalog. Low-risk actions do not create approval records; moderate and high-risk actions require a separate explicit owner confirmation. Irreversible operations are elevated to high risk.",
      "Bind a process-local, single-use approval to the exact action ID and human-readable summary, target reference and current-state digest, scope, payload digest, policy version, owner identity, and a maximum five-minute expiry. Recheck current capability authorization and target digest immediately before a one-time trusted application callback. Do not create approvals implicitly from chat/model output and do not automatically retry an action callback after a failure."
    ],
    "area": "P19",
    "checkpoint": "task-142-action-risk-approval-policy",
    "validation": [
      "Focused Task 142 approval, Task 141 grants, central authorization, local access, maintenance approval, and coordinator proposal regressions: 32 passed.",
      "Verified low-risk bypass, moderate/high review, irreversible elevation, exact action/target/scope/payload/policy digest binding, explicit CSRF-protected local owner confirmation, five-minute expiry, fresh authorization and target-state checks, stale-target rejection, and single-use consumption without replay.",
      "Full Python suite: 1133 passed, 6 skipped, with the same two pre-existing unrelated failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service. Public docs tests: 15 passed; update-manifest tests: 6 passed; Python compilation and git diff checks passed."
    ],
    "limitations": [
      "The approval service is process-local and only protects trusted application callers that route an operation through its guarded callback. Existing action-specific approval flows are unchanged; this checkpoint does not claim every application action is automatically governed.",
      "No action-creation API, generic executor, UI screen, persistence, audit history, distributed lock, or durable recovery is added. A failed operation callback consumes its approval and requires a new owner-reviewed request."
    ]
  },
  {
    "number": 143,
    "title": "Capability audit and sensitive-data controls",
    "description": "Record bounded authorized audit events and minimize sensitive capability inputs, outputs, and retained evidence.",
    "category": "Phase C - Capability Governance",
    "status": "completed",
    "dependsOn": [
      140,
      141
    ],
    "acceptance": [
      "Audit actor, capability, permission decision, action/result state, timestamps, and safe references.",
      "Redact credentials and bound retention and inspection access."
    ],
    "outOfScope": [
      "Do not persist raw screenshots, audio, credentials, or prompts by default.",
      "Do not claim tamper-proof audit without evidence."
    ],
    "decisions": [
      "Use the existing local SQLite database for metadata-only audit events, with a 30-day retention window, a 10,000-event hard cap, and at most 200 events per owner inspection. This is durable local operational history, not tamper-proof evidence; the database is not encrypted at rest. Store fixed actor/capability/permission/action/result/time fields and validated safe references only. Hash all actor identifiers into opaque references, and omit unsafe references."
    ],
    "area": "P19",
    "checkpoint": "task-143-capability-audit-retention",
    "validation": [
      "Focused capability audit, grant, approval, authorization, and local access regressions: 28 passed.",
      "Audit tests verify fixed metadata-only storage, opaque hashing of every actor identifier including token-shaped values, omitted unsafe references, 30-day pruning, hard event/inspection bounds, explicit local-owner inspection permission, and grant lifecycle events.",
      "Full Python suite: 1138 passed, 6 skipped, with the same two pre-existing unrelated failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service."
    ],
    "limitations": [
      "The SQLite audit database is local and unencrypted at rest; retention is logical deletion, not secure erasure. There is no tamper-proof guarantee, remote aggregation, audit UI, or storage recovery certification.",
      "Only fixed metadata is recorded. Raw prompts, credentials, audio, screenshots, action payloads, approval summaries, and raw error text are not retained. Inspection is limited to an explicit high-risk capability permission and at most 200 records per request."
    ]
  },
  {
    "number": 144,
    "title": "Emergency stop, expiry, and capture indicators",
    "description": "Provide visible stop/revoke controls and truthful activity indicators for screen, camera, microphone, and running actions.",
    "category": "Phase C - Capability Governance",
    "status": "completed",
    "dependsOn": [
      140,
      141,
      142,
      143
    ],
    "acceptance": [
      "Stop prevents new protected actions and interrupts local capture/playback within documented bounds.",
      "Show active capability, grant expiry, capture state, and uncertain remote cancellation.",
      "Enforce action timeouts and recheck revoked/expired grants."
    ],
    "outOfScope": [
      "Do not claim remote work stopped without provider evidence.",
      "No always-on screen, camera, or microphone by default."
    ],
    "decisions": [
      "Use an explicit process-local stop latch for the current configured local app. The latch resets on process restart because this app does not persist capture state or replay actions. Permit status reads, sign-out, explicit grant revocation, stop, and separately confirmed resume while stopped; block other state-changing requests. A stop aborts browser-local microphone capture and playback in the current page and stops this app's wait on in-flight model/transcription requests, but remote completion/cancellation remains UNKNOWN. Recheck authentication and expiring/revoked session grants on every protected request. Existing provider request timeouts remain authoritative; no generic action executor or camera/screen capture is introduced."
    ],
    "area": "P19",
    "checkpoint": "task-144-emergency-stop-capture-indicators",
    "validation": [
      "Focused Task 144 stop, grant, voice, authorization, and audit regressions: 30 passed.",
      "Browser-module regression tests: 165 passed, including emergency panel interactions, microphone stop/restart gating, speech playback stop, and unknown provider outcome after abort.",
      "Full Python suite: 1141 passed, 6 skipped, with the same two pre-existing unrelated failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service."
    ],
    "limitations": [
      "The stop latch coordinates one configured local application process only and resets after restart. It does not provide cross-process control or confirm that local/online provider work stopped after request cancellation.",
      "Microphone/playback status is reported by the current browser page; screen and camera capture are not used by this app. No always-on capture or persistent stop history is added. Existing action/provider timeouts remain bounded by their own adapters; this is not a universal timeout controller."
    ]
  },
  {
    "number": 145,
    "title": "Audio input and speech recognition contracts",
    "description": "Define backend-neutral audio capture and speech-to-text interfaces with explicit microphone lifecycle, limits, and governance checks.",
    "category": "Phase D - Voice and Speech",
    "status": "completed",
    "dependsOn": [
      128,
      140,
      141,
      144
    ],
    "acceptance": [
      "Bound format, duration, sampling, memory lifetime, cancellation, and safe errors.",
      "Require explicit grant and visible recording indicator."
    ],
    "outOfScope": [
      "No always-on microphone or silent local-to-cloud fallback."
    ],
    "decisions": [
      "Keep browser/device microphone capture explicit per use, limit every recording to ten seconds, and retain the existing browser permission prompt and visible status. Define the backend-neutral Python input/provider contract for mono 16 kHz 16-bit PCM WAV; do not add microphone hardware access to the Python API. Cancellation stops capture and app-side waiting, with no automatic retry or cloud fallback."
    ],
    "area": "P20",
    "checkpoint": "task-145-bounded-speech-input-contracts",
    "validation": [
      "Focused deterministic speech input contract tests: 8 passed.",
      "Browser voice tests passed, including the ten-second local capture limit, explicit local recognition, cancellation, and no cloud fallback."
    ],
    "limitations": [
      "The browser/OS controls microphone permission and provides the local recognition engine. Cancellation can stop the app's capture or wait, but cannot interrupt an operation already running inside the browser or remote provider."
    ]
  },
  {
    "number": 146,
    "title": "Optional local speech-to-text backend",
    "description": "Add one optional local speech-to-text backend, evaluating faster-whisper as the preferred candidate.",
    "category": "Phase D - Voice and Speech",
    "status": "completed",
    "dependsOn": [
      145
    ],
    "acceptance": [
      "Detect missing model/runtime and load only explicitly selected local models.",
      "Keep dependencies optional and tests deterministic."
    ],
    "outOfScope": [
      "Do not require faster-whisper and openai-whisper together.",
      "Do not download models automatically."
    ],
    "decisions": [
      "Evaluated faster-whisper as the single optional backend. Its upstream project is MIT-licensed, but model licenses remain model-specific. The native CTranslate2 runtime, audio/array libraries, and independently sized model files create a nontrivial distribution footprint, so none are bundled or made required. Model language coverage is selected-model-specific. Use it only when faster-whisper is already installed and the owner has placed a supported model directory directly inside the fixed local speech-models folder. Because Task 134 is deferred for lack of a verified pack source/trust/loading boundary, this backend does not install, catalog, download, or activate third-party packs; it reads only owner-present files and requires explicit model selection. Model loading is lazy, CPU/int8, local-files-only, and tested through deterministic injected fakes. No online fallback or automatic model download is provided."
    ],
    "area": "P20",
    "checkpoint": "task-146-optional-local-speech-recognition",
    "validation": [
      "Focused local speech backend/API and Task 145/voice/emergency-stop regression tests: 22 passed.",
      "Browser voice-module tests: 13 passed, including explicit local model selection, local-only request routing, editable transcript handoff, and no cloud budget/consent use.",
      "Full Python suite: 1157 passed, 6 skipped, with the same two unrelated model-assignment failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service.",
      "Full browser-module suite: 168 passed. Public documentation site tests: 15 passed; update-manifest tests: 6 passed. Python compilation and git diff --check passed."
    ],
    "limitations": [
      "The optional faster-whisper/native runtime and model are not bundled or installed by the application. The packaged Electron sidecar therefore does not provide this backend unless a separately supported packaging route is introduced; there is currently no UI installer for the runtime/model. Only owner-present model directories with required files are listed; each model's license must be checked by its owner, and model quality, language coverage, hardware fit, and latency are not certified. Cancellation is cooperative between model segments and cannot guarantee interruption while native model code is running.",
      "Task 134 remains deferred and incomplete; this backend avoids its missing pack lifecycle by reading a fixed owner-managed folder without adding install, trust, catalog, or activation operations."
    ]
  },
  {
    "number": 147,
    "title": "Reviewed speech input in conversations",
    "description": "Connect governed local transcription to chat with language/model configuration and mandatory review before sending.",
    "category": "Phase D - Voice and Speech",
    "status": "completed",
    "dependsOn": [
      128,
      145,
      146
    ],
    "acceptance": [
      "Allow transcript correction and explicit Send while preserving typed chat and provenance.",
      "Distinguish local from consented online transcription."
    ],
    "outOfScope": [
      "Do not auto-submit transcripts or store raw audio.",
      "Preserve existing Gemini consent semantics."
    ],
    "decisions": [
      "Keep transcript provenance as an accessible, transient client-side label on the editable draft: distinguish browser on-device, explicitly selected local model, and Google Gemini online transcription after that recording's required consent. Append recognized text after any typed draft without changing it; sending still requires the existing explicit Send action and existing per-turn Gemini chat consent. The source label describes the insertion origin only, not typed text or later edits, and is cleared after successful send. Raw audio and transcript-source metadata are not persisted in conversation history; the message API schema and existing Conversation/Message lifecycle remain unchanged."
    ],
    "area": "P20",
    "checkpoint": "task-147-reviewed-speech-input-in-conversations",
    "validation": [
      "Focused chat UI and voice-module tests: 29 passed, including typed-draft preservation, source labels for local/local-model/consented online transcription, and no automatic send.",
      "Full browser-module suite: 169 passed. Public documentation site tests: 15 passed; update-manifest tests: 6 passed. Python runtime code was unchanged in this task."
    ],
    "limitations": [
      "Provenance is a temporary UI indicator of transcript insertion, not persisted message metadata. It does not identify individual text ranges after editing and is cleared after successful send. The browser remains responsible for microphone permission; raw audio remains ephemeral under the existing Task 145/146 routes."
    ]
  },
  {
    "number": 148,
    "title": "Offline text-to-speech provider foundation",
    "description": "Define a text-to-speech provider boundary with an offline backend and explicit voice/output configuration.",
    "category": "Phase D - Voice and Speech",
    "status": "completed",
    "dependsOn": [
      128,
      140,
      141,
      144
    ],
    "acceptance": [
      "Expose backend, voice, language, output state, and unavailable states.",
      "Keep speech generation separate from action permissions."
    ],
    "outOfScope": [
      "Do not silently fall back from local to online speech."
    ],
    "decisions": [
      "Use the existing browser/device Web Speech synthesis API as the offline adapter, but expose only voices explicitly reported with localService=true. Voice availability and language depend on the operating system/browser. Do not add another runtime or online adapter; packaged builds expose only what their browser engine reports locally. Voice output is an explicit user-triggered presentation action and grants no Task, Tool, permission, or other action authority."
    ],
    "area": "P20",
    "checkpoint": "task-148-offline-text-to-speech-provider",
    "validation": [
      "Focused offline TTS provider and voice UI tests: 18 passed, including explicit local voice/language selection, bounded text, unavailable and disappearing voice states, and stop behavior.",
      "Full browser-module suite: 174 passed. Directly affected WebUI route tests: 12 passed. Public documentation site tests: 15 passed; update-manifest tests: 6 passed. Python compilation and git diff --check passed."
    ],
    "limitations": [
      "The provider relies on voices exposed by the browser/operating system and explicitly filters to localService=true. Voice inventory, supported languages, naturalness, and availability in a packaged distribution vary by device and were not certified. Selected voice/language settings are page-local and are not persisted. No online fallback or audio transfer is implemented."
    ]
  },
  {
    "number": 149,
    "title": "Optional natural voices and playback control",
    "description": "Add explicitly selected optional local or online natural-voice adapters with bounded queue, playback, interruption, and stop controls.",
    "category": "Phase D - Voice and Speech",
    "status": "completed",
    "dependsOn": [
      134,
      142,
      143,
      144,
      148
    ],
    "acceptance": [
      "Label local versus online and require consent before cloud text transfer.",
      "Bound queued text/playback and report uncertain remote cancellation without retry."
    ],
    "outOfScope": [
      "Do not require pyttsx3, Coqui, Kokoro, and edge-tts together.",
      "Speech output grants no action authority."
    ],
    "decisions": [
      "Use the existing browser/device Web Speech synthesis adapter and allow only explicitly selected voices reported as local. Do not package or install a model/runtime or add an online provider in this task: no provider/model has verified license, privacy, retention, and quality evidence. Remote voices remain unavailable; therefore this implementation sends no chat text online and has no remote cancellation/retry behavior. The platform's voice quality and terms are not certified by this app."
    ],
    "area": "P20",
    "checkpoint": "task-149-bounded-local-voice-queue-controls",
    "validation": [
      "Focused local TTS queue/provider and voice UI tests: 19 passed, covering explicit local selection, local-only voice filtering, bounded sequential queue, queue overflow, interruption/clear, unavailable voices, and no online fallback.",
      "Full browser-module suite: 175 passed. Directly affected WebUI route and update-manifest tests: 18 passed. Public documentation site tests: 15 passed. Python compilation and git diff --check passed."
    ],
    "limitations": [
      "This checkpoint implements only the local adapter. It uses device-provided voices and does not depend on or activate Task 134 capability packs; Task 134 remains deferred and incomplete. No cloud speech provider, cloud-consent flow, or remote cancellation outcome exists; a future online adapter needs a separately reviewed provider, retention, privacy, and consent contract. Voice quality, language inventory, legal terms, and packaged availability depend on the device/browser and are not certified. Queueing is page-memory only, limited to three pending replies and 16 KiB total queued UTF-8 text, and Stop discards the queue."
    ]
  },
  {
    "number": 150,
    "title": "Bounded image input and vision context",
    "description": "Define authorized image records and explicit conversation attachment with bounded, provenance-aware lifecycle.",
    "category": "Phase E - Vision",
    "status": "completed",
    "dependsOn": [
      117,
      128,
      140,
      141,
      144
    ],
    "acceptance": [
      "Validate type, dimensions, bytes, source, retention, and conversation scope.",
      "Keep images ephemeral by default and require explicit provider transfer selection."
    ],
    "outOfScope": [
      "No silent screen/camera capture or image indexing into Task 130."
    ],
    "decisions": [
      "Use only explicit authenticated user uploads, keep bytes in bounded process memory, make attachments expire after 15 minutes with lazy cleanup on the next image operation, and remove them on explicit deletion, conversation close, or process restart. Never persist or index them. No Provider transfer is implemented or authorized in this task; later vision transfer must name a selected Provider and require explicit per-use consent."
    ],
    "area": "P21",
    "checkpoint": "task-150-bounded-image-input-vision-context",
    "validation": [
      "Focused chat-image, owned-chat, local-access, emergency-stop, and local-voice regressions: 35 passed, covering type/dimension/byte/count/global-memory bounds, owner and conversation isolation, expiry/removal/close cleanup, Provider non-transfer, and preserved stop behavior.",
      "Full Python suite: 1161 passed, 6 skipped, with two unrelated existing failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service. Public documentation suite: 15 passed; update-manifest tests: 6 passed; Python compilation and git diff --check passed."
    ],
    "limitations": [
      "Only bounded PNG/JPEG header metadata is inspected; image bytes are not fully decoded or transformed. The store is process-local and not durable or securely erased; expiry cleanup is lazy on image operations. No UI upload control or vision-capable Provider integration is added. Provider transfer remains unavailable until a later task implements explicit per-use selection and consent. The full Python run also reproduces two unrelated model-assignment test failures documented before Task 150; neither affected files changed in this task."
    ]
  },
  {
    "number": 151,
    "title": "Explicit screen capture provider",
    "description": "Capture one user-selected display or window frame from the chat UI through the platform's native chooser and a replaceable, permission-gated adapter.",
    "category": "Phase E - Vision",
    "status": "completed",
    "dependsOn": [
      144,
      150
    ],
    "acceptance": [
      "Show capture indicator and the selected supported display/window/browser surface; region cropping remains unsupported.",
      "Return bounded timestamped evidence; fail closed when permission/support is absent."
    ],
    "outOfScope": [
      "Do not poll or capture in background."
    ],
    "decisions": [
      "Use browser getDisplayMedia with an Electron-owned native chooser; no new mss dependency.",
      "The current picker selects a display/window/browser surface; in-app region cropping is unsupported."
    ],
    "area": "P21",
    "checkpoint": "task-151-explicit-screen-capture-provider",
    "validation": [
      "Focused chat-image, local-access, emergency-stop, and screen-capture Python/browser/Electron tests passed.",
      "Full Python suite: 1162 passed, 6 skipped; two previously recorded unrelated model-assignment tests still fail.",
      "Full browser-module suite: 179 passed; Electron tests: 12 passed; public documentation tests: 15 passed; update-manifest tests: 6 passed.",
      "Python compilation and git diff --check passed."
    ],
    "limitations": [
      "Capture is a caller-triggered single frame, downscaled to at most 4096 pixels per side and 8 megapixels, JPEG-encoded to at most 2 MiB, then attached to an open owner conversation for the existing 15-minute process-memory lifetime.",
      "Capture requires both chat:send and screen:capture. The selected frame is not sent to a Provider, indexed, or persisted. No OCR, region crop, redaction, background capture, or camera input is included.",
      "The custom Electron chooser is limited to 24 reported sources; unsupported APIs, unknown selected surface types, cancellation, permission denial, chooser errors, and emergency stop fail closed. Region selection is not available, and the native picker cannot be programmatically dismissed by the app.",
      "Capture behavior is tested with deterministic fakes; no live screen or display hardware was exercised."
    ]
  },
  {
    "number": 152,
    "title": "Optional image processing adapters",
    "description": "Provide optional bounded image resize, conversion, and redaction adapters using an evaluated Pillow/OpenCV path.",
    "category": "Phase E - Vision",
    "status": "completed",
    "dependsOn": [
      150
    ],
    "acceptance": [
      "Cap dimensions, decoded bytes, processing time, and output size.",
      "Keep processing optional and independent of core startup."
    ],
    "outOfScope": [
      "Do not make Pillow/OpenCV mandatory or claim complete redaction without tests."
    ],
    "decisions": [
      "Use Pillow as a separately installed optional dependency: its mature Python image API and MIT-CMU license fit the bounded resize/re-encode needs with less setup than OpenCV. Do not add an application package lifecycle or a mandatory runtime dependency. Task 134 remains deferred; this adapter does not install or manage packages."
    ],
    "area": "P21",
    "checkpoint": "task-152-bounded-optional-image-processing",
    "validation": [
      "Focused image-processing and Task 150 attachment regressions: 13 passed; synthetic 8-megapixel local resize completed in 271 ms inside the bounded worker.",
      "Full Python suite: 1170 passed, 6 skipped; two previously recorded unrelated model-assignment failures remain.",
      "Python compilation, public documentation suite, update-manifest tests, and git diff --check passed."
    ],
    "limitations": [
      "Pillow is absent from core requirements and packaged runtime. The optional requirements-image-processing.txt file must be installed manually; no app install UI, capability-pack lifecycle, API, or chat integration was added.",
      "Processing runs in a child process with a five-second maximum timeout, but that process shares the user's OS permissions and is not a security sandbox. Inputs and outputs are capped at 2 MiB, dimensions at 4096 by 4096 and 8 megapixels, and decoded pixel storage at 32 MiB.",
      "Redaction only blacks out caller-specified pixel rectangles and strips metadata on re-encode. It does not detect sensitive content or guarantee complete anonymization. Results are returned in memory and are not attached or sent to a Provider automatically."
    ]
  },
  {
    "number": 153,
    "title": "OCR provider abstraction",
    "description": "Define a replaceable OCR provider contract with language, confidence, bounding-box, and source-image provenance.",
    "category": "Phase E - Vision",
    "status": "completed",
    "dependsOn": [150, 152],
    "acceptance": ["Bound region count, output text, processing time, and errors.", "Distinguish unsupported, unavailable, low-confidence, and success."],
    "outOfScope": ["OCR output is untrusted data, not an action instruction. No OCR engine, UI/API, chat submission, or provider transfer is included."],
    "decisions": ["Use a provider protocol plus an in-memory service over existing owner-scoped Task 150 image attachments. Validate source digest, dimensions, language tags, confidence, pixel boxes, and bounded text. Enforce a maximum five-second call deadline; serialize each service instance so a stuck provider cannot spawn unbounded work."],
    "area": "P21",
    "checkpoint": "task-153-bounded-ocr-provider-contract",
    "validation": ["Focused OCR contract and image attachment regressions: 13 passed.", "Full Python suite: 1180 passed, 6 skipped; two previously recorded unrelated model-assignment failures remain.", "Public documentation tests: 15 passed; Python compilation and git diff --check passed."],
    "limitations": ["No OCR backend is configured or bundled. The replaceable provider contract is tested with deterministic fakes only; OCR accuracy, language coverage, and real engine performance are not claimed.", "A provider must honor its supplied deadline. The service returns at the configured timeout and permits only one active provider call per service instance; a hung daemon call keeps that instance unavailable until it exits. OCR text is explicitly untrusted and is not used as an instruction."]
  },
  {
    "number": 154,
    "title": "Optional local OCR backend",
    "description": "Implement an explicitly configured local OCR provider and report external Tesseract installation requirements.",
    "category": "Phase E - Vision",
    "status": "completed",
    "dependsOn": [153],
    "acceptance": ["Detect missing engine/language packs without breaking core startup.", "Keep pytesseract/Tesseract and EasyOCR optional alternatives.", "Test permissions, malformed image, timeout, and sanitized failure."],
    "outOfScope": ["Do not silently download OCR models or binaries. No bundled engine, model installation, API/UI, or chat auto-submit."],
    "decisions": ["Select the Tesseract CLI as the first optional backend. Its Apache-2.0 engine is invoked only at an explicitly configured absolute path, over stdin/stdout, without a shell or image temp files. The binary and chosen traineddata language files must be installed separately by the owner. Task 134 remains deferred; this manually configured backend does not depend on its package lifecycle. Do not add the pytesseract wrapper or EasyOCR/Torch dependencies: the former still requires the external engine and the latter defaults to downloading model weights."],
    "area": "P21",
    "checkpoint": "task-154-explicit-optional-tesseract-backend",
    "validation": ["Focused Tesseract, OCR contract, Task 150 image, Task 152 processing, and update regressions: 34 passed.", "Full Python suite: 1185 passed, 6 skipped; two previously recorded unrelated model-assignment failures remain.", "Public documentation tests: 15 passed; Python compilation and git diff --check passed."],
    "limitations": ["No Tesseract binary or traineddata is bundled, downloaded, or installed. Recognition is tested with deterministic subprocess fakes; no live engine accuracy, language coverage, or hardware performance is claimed.", "The explicitly configured engine runs with the application's OS privileges. Command execution uses no shell and no image files on disk, but it is not an OS sandbox. Only a bounded TSV output and bounded OCR result are accepted."]
  },
  {
    "number": 155,
    "title": "Explicit camera input and vision chat integration",
    "description": "Add one-use owner-authorized camera capture and attach selected imagery/OCR evidence within Task 150 limits.",
    "category": "Phase E - Vision",
    "status": "completed",
    "dependsOn": [
      144,
      150,
      153
    ],
    "acceptance": [
      "Show a visible camera indicator and capture action; discard unretained image after use.",
      "Require image/provider consent and label OCR as untrusted."
    ],
    "outOfScope": [
      "No continuous camera access or automatic image retention."
    ],
    "decisions": [
      "Use explicit one-frame browser camera access, plus a native allow-once prompt in Electron. Keep the video-only camera grant for at most 15 seconds and attach no more than one bounded frame per action. Store captures in the Task 150 owner-scoped process-memory store. A selected image is sent only on a non-streaming chat turn after explicit per-turn consent; discard selected images after provider completion or failure. Optional OCR uses only an explicitly configured local Task 154 Tesseract path, is labeled untrusted, and its text is not persisted. Use the existing bounded Gemini connection adapter for explicitly consented cloud vision, and the loopback Ollama adapter for local vision transport. Gemini image turns require both the one-turn image consent and the existing one-turn cloud consent. The assigned model's vision ability is not preflighted."
    ],
    "area": "P21",
    "checkpoint": "task-155-one-use-camera-vision-chat",
    "validation": [
      "Task 155 focused API, one-use image consent/discard, OCR provenance, and deterministic Ollama/Gemini image payload tests: 8 passed. Directly affected chat-image, local-access, capability, and capture regressions: 30 passed.",
      "Browser-module suite: 184 passed; Electron suite: 14 passed; public documentation suite: 15 passed; Python compilation and git diff --check passed.",
      "Full Python suite: 1191 passed, 8 skipped; two previously recorded unrelated model-assignment failures remain (test_model_set_command and test_model_replacement_uses_existing_assignment_service)."
    ],
    "limitations": [
      "Camera permission prompts, actual device capture, live Ollama or Gemini vision inference, and real Tesseract OCR are not exercised by deterministic tests. Camera availability and browser/Electron permission behavior vary by platform. A registered loopback Ollama endpoint accepts image payloads while a selected text-only model may still reject or mishandle them; model-level vision capability is not verified and no fallback or retry occurs.",
      "Unselected temporary attachments remain owner-scoped in process memory until removal, conversation close, process restart, or lazy 15-minute expiry. Selected images are removed after one provider attempt. The app cannot control a provider's own retention after transmission. The API remains loopback/authenticated; no continuous camera capture, automatic image retention, or new provider class is added. Gemini data retention after its explicitly consented request remains controlled by Google's account policy. Task 134 remains deferred and incomplete."
    ]
  },
  {
    "number": 156,
    "title": "Scoped browser automation provider",
    "description": "Add bounded Playwright browser actions extending Task 90 read-only inspection only under explicit grants and exact site policy.",
    "category": "Phase F - Controlled Automation",
    "status": "completed",
    "dependsOn": [
      90,
      140,
      141,
      142,
      144
    ],
    "acceptance": [
      "Use deny-by-default origins, operation allowlists, action limits, and timeouts.",
      "Preview targets; require confirmation for high-impact changes.",
      "Preserve existing read-only behavior."
    ],
    "outOfScope": [
      "No arbitrary browsing, downloads, local files, credentials, or unrestricted script execution."
    ],
    "decisions": [
      "Use the already installed Playwright sync adapter. Keep exact HTTPS origin and operation policy constructor-supplied and empty by default; restrict actions to exact-role native button/link click or non-sensitive textbox fill. Every mutation uses the existing one-use high-risk owner approval, and every target is re-read against its digest before dispatch."
    ],
    "area": "P22",
    "checkpoint": "task-156-scoped-browser-automation",
    "validation": [
      "Focused scoped-browser, existing read-only inspection, capability authorization/approval/audit/grant, emergency-stop, and local-owner regressions: 46 passed.",
      "Full Python suite: 1203 passed, 6 skipped; the two previously recorded unrelated failures remain (test_model_set_command and test_model_replacement_uses_existing_assignment_service). No live site or download was used."
    ],
    "limitations": [
      "The adapter is an API/service foundation only; no route, UI, chat tool, or site policy is configured by default. Allowed page scripts execute for the owner-selected origin; HTTP requests outside that exact origin and all WebSockets are blocked. Same-origin non-GET/HEAD requests are blocked during page load/inspection and allowed only during approved action dispatch. Same-origin GET/HEAD requests and approved page handlers may still cause site-side effects whose completion remains unknown. The browser context has no stored cookies or credentials, does not access files, and does not retain screenshots. DNS-to-address pinning is not implemented, so site policy must name a trusted public HTTPS origin. Per-session action counts and approvals are process-local; no cross-process coordination exists."
    ]
  },
  {
    "number": 157,
    "title": "Scoped desktop automation provider",
    "description": "Add an optional Windows UI Automation action adapter for individually approved semantic controls with visible state and bounded recovery.",
    "category": "Phase F - Controlled Automation",
    "status": "completed",
    "dependsOn": [
      140,
      141,
      142,
      144
    ],
    "acceptance": [
      "Require a one-use owner approval bound to the exact process, window, control, target digest, and action.",
      "Require an exact executable allowlist, visible enabled native Button target, bounded caller timeout, activity indicator, and emergency-stop handling.",
      "Provide read-only preview before any action."
    ],
    "outOfScope": [
      "No unrestricted keyboard/mouse control, coordinate targeting, text entry, screenshots, launches, or background enumeration.",
      "No API/UI/chat wiring or default allowed process.",
      "open-interpreter requires separate capability/security evaluation."
    ],
    "decisions": [
      "Use Windows UI Automation through the optional pywinauto UIA backend. It targets one direct-child native Button by exact process ID/name, window handle/title, automation ID, and accessible name. It exposes only Invoke; it sends no coordinates or keyboard input. pyautogui is excluded because coordinate/global input has a broader target boundary. The optional pywinauto 0.6.9 requirement is installed manually and is not added to core or the packaged runtime."
    ],
    "area": "P22",
    "checkpoint": "task-157-scoped-desktop-automation",
    "validation": [
      "Focused desktop/browser capability, approval, authorization, and local-owner tests: 36 passed. Deterministic backend fakes only; no live desktop window was inspected or changed.",
      "Windows UI Automation optional dependency pywinauto 0.6.9 and comtypes 1.4.17 import successfully under Python 3.14.",
      "Full Python suite: 1212 passed, 6 skipped; the same two previously recorded unrelated model-assignment failures remain (test_model_set_command and test_model_replacement_uses_existing_assignment_service). Public documentation tests: 15 passed; Python compilation and git diff checks passed."
    ],
    "limitations": [
      "The integration is a Python service foundation only; there is no route, UI, chat tool, default process policy, or bundled optional dependency. It invokes only direct-child native UIA Buttons in one exact allowed executable and visible window. A timed-out in-flight UIA call cannot be remotely cancelled; its outcome remains unknown, the action is never retried, and the local controller remains occupied until that call exits. Windows UIA provider behavior has not been tested against a live desktop application. Process IDs, approvals, action counts, and activity state are process-local."
    ]
  },
  {
    "number": 158,
    "title": "Automation review and debug traces",
    "description": "Record bounded, owner-scoped before/action/after metadata for approved browser and desktop actions, with evidence digests and safe recovery guidance.",
    "category": "Phase F - Controlled Automation",
    "status": "completed",
    "dependsOn": [
      143,
      144,
      156,
      157
    ],
    "acceptance": [
      "Bind the actor, one-use action approval reference, policy version, sanitized target/action, outcome, and timing.",
      "Expose before/action/after phases; keep the after state UNKNOWN unless a read-only digest is explicitly available.",
      "Allow owner-scoped inspection and replay simulation without calling an action adapter or repeating external effects.",
      "Retain at most 200 in-memory records for no more than one day and accept screenshot IDs only through a consent validator."
    ],
    "outOfScope": [
      "No automatic retry/replay, persistent trace database, API/UI, screenshot capture, or raw media storage."
    ],
    "decisions": [
      "Use an in-memory metadata-only AutomationTraceService. Its grant_id is the one-use action approval ID; high-risk actions do not use Task 141 low-risk session-grant records. Store digests and allowlisted outcome categories, never page text, typed values, window titles, or raw errors.",
      "After-state remains UNKNOWN for Task 156/157 because neither adapter can safely verify remote effects. Replay simulation returns stored phases and never invokes browser/desktop automation.",
      "Screenshot references default to disabled and store opaque IDs only when an injected validator confirms owner consent and expiry. The trace store does not capture or retain image bytes."
    ],
    "area": "P22",
    "checkpoint": "task-158-automation-review-traces",
    "validation": [
      "Focused trace-store, scoped browser/desktop, capability authorization/approval/audit/grant, emergency-stop, and local-owner regressions: 57 passed.",
      "Deterministic tests cover owner isolation, expiry/capacity, safe replay simulation, unknown outcomes, secret-free metadata, and consent-validated screenshot references. No live browser/site or desktop action was used. Full Python suite: 1219 passed, 6 skipped, with the two previously recorded unrelated failures in test_model_set_command and test_model_replacement_uses_existing_assignment_service. Public documentation suite: 15 passed; Python compilation and git diff --check passed."
    ],
    "limitations": [
      "Records are process-local and disappear on restart or after expiry/eviction; there is no API/UI or durable audit trail. Task 156/157 after-state remains UNKNOWN and remote completion is not asserted. Screenshot reference use is unavailable unless a consent validator is explicitly supplied; the service stores no screenshots or media."
    ]
  },
  {
    "number": 159,
    "title": "Shared visual design system",
    "description": "Unify Python Web UI and Electron into a coherent application shell with shared accessible visual tokens, navigation, page layouts, forms, and interaction patterns.",
    "category": "Phase G - Command Center UI and Visualization",
    "status": "completed",
    "dependsOn": [
      47,
      127,
      129
    ],
    "acceptance": [
      "Apply shared typography, color, spacing, navigation, page structure, forms, buttons, feedback, loading, empty, denied, and error states consistently across primary screens.",
      "Preserve service boundaries, keyboard access, responsive layout, and reduced motion; replace legacy pages that visibly diverge from the shared system."
    ],
    "outOfScope": [
      "No framework migration or decorative activity claims."
    ],
    "decisions": [
      "Use the Python-served token sheet as canonical; synchronize legacy Electron CSS aliases at static-export build time because Next.js cannot resolve an absolute runtime CSS URL as an import."
    ],
    "area": "P23",
    "checkpoint": "task-159-shared-visual-design-system",
    "validation": [
      "Next.js production static build and TypeScript check passed after canonical token synchronization.",
      "Focused Web UI and desktop runtime tests: 20 passed, including token endpoint, generated-token parity, static export assets, and grouped navigation.",
      "Dashboard, visualization, and camera browser-module regressions: 20 passed; public documentation tests: 13 passed. Full Python suite excluding the baseline-invalid tests/test_automation_traces.py: 1214 passed, 5 skipped, with the two previously recorded unrelated model-assignment failures. The unfiltered full-suite run stops at collection on that file's existing `rom __future__` syntax error. Changed Python tests compile; git diff --check passed."
    ],
    "limitations": [
      "The shared visual system covers the primary Web UI shell and Electron home. Older deep pages retain specialized layout rules where replacing them would expand beyond this checkpoint; they consume the same global tokens and control/focus states.",
      "The packaged installer was not rebuilt; an installed copy requires a new installer build to include these source UI changes."
    ]
  },
  {
    "number": 160,
    "title": "Operational command-center dashboard",
    "description": "Present authorized current chat, active Projects and Tasks, Agent/Employee assignments, Providers, resources, approvals, system status, and recent memory/knowledge activity with timestamps and stale/unknown indicators.",
    "category": "Phase G - Command Center UI and Visualization",
    "status": "completed",
    "dependsOn": [
      113,
      114,
      115,
      129,
      159
    ],
    "acceptance": [
      "Use protected APIs and show source/freshness for organization, project/task execution, provider/model, system, memory/knowledge, and approval summaries.",
      "Keep permissions distinct and provide empty, offline, denied, stale, and error states."
    ],
    "outOfScope": [
      "Do not invent activity or call Providers from presentation code."
    ],
    "decisions": [
      "Dashboard refresh remains explicit because source freshness/load measurements are unavailable; combined panels use the oldest successful client read time and mark it stale after 60 seconds without background API polling.",
      "Expose corporation-scoped retained knowledge metadata only, and omit private Conversation/Project memory and message contents.",
      "Expose a protected system:read snapshot and preserve each source resource's existing read permission; approval entries are review metadata only."
    ],
    "area": "P23",
    "checkpoint": "task-160-operational-command-center-dashboard",
    "validation": [
      "Focused dashboard, protected API, memory, local access, capability, chat, and activity regressions: 72 passed. Dashboard module tests: 9 passed.",
      "Full deterministic Python suite excluding the pre-existing syntactically invalid tests/test_automation_traces.py: 1216 passed, 5 skipped, with the two previously recorded failures in tests/test_command_interface.py::test_model_set_command and tests/test_provider_model_api.py::test_model_replacement_uses_existing_assignment_service.",
      "Public documentation/task-roadmap/update-manifest tests: 13 passed; dashboard module tests: 9 passed. Python compilation and git diff --check passed."
    ],
    "limitations": [
      "Freshness on most panels is the time the browser last read that protected API; task/project APIs do not provide source-update timestamps. The system panel also displays the server snapshot observed_at.",
      "Approval panel displays pending approval metadata only and provides no decision controls. Conversation panel lists bounded open-conversation identifiers and coordinator labels, not messages.",
      "Knowledge panel lists only the ten latest corporation-scope memory metadata records after memory:read authorization; private Conversation/Project memories and content are omitted.",
      "System provider availability remains UNKNOWN unless separately checked; configured request slots do not establish hardware capacity or feasibility."
    ]
  },
  {
    "number": 161,
    "title": "Knowledge and resource visualization",
    "description": "Extend actual corporation/workflow maps with authorized knowledge provenance, provider/model assignment, and resource snapshots.",
    "category": "Phase G - Command Center UI and Visualization",
    "status": "completed",
    "dependsOn": [
      114,
      115,
      130,
      160
    ],
    "acceptance": [
      "Use only authorized records and distinguish association from inference.",
      "Provide equivalent labeled 2D/list views, keyboard selection, and reduced motion."
    ],
    "outOfScope": [
      "Do not expose private memory or equate slots with hardware readiness."
    ],
    "decisions": [
      "Map source reads keep their existing independent permissions: structure, Agent, model assignment, Provider registration, workflow, Corporation memory, and system/resource snapshots are not combined into a new privileged API.",
      "Model assignments are associated only by exact recorded Agent ID; resource budgets match exact provider/model IDs. Knowledge provenance is shown as a source record, not as an inferred graph edge."
    ],
    "area": "P23",
    "checkpoint": "task-161-knowledge-resource-visualization",
    "validation": [
      "Focused protected Python map, provenance, resource, access, and page regressions: 66 passed.",
      "Visualization, structure-list, and workflow-map Node tests: 20 passed; public docs/task/update-manifest suite: 13 passed.",
      "Full Python suite excluding the pre-existing syntactically invalid tests/test_automation_traces.py: 1219 passed, 5 skipped, and the two previously recorded unrelated model-assignment failures; the Task 161 updates-manifest regression passed after correcting the entry schema.",
    ],
    "limitations": [
      "Corporation knowledge is limited to the ten latest records returned by the existing memory:read scoped list and exposes provenance metadata only; private Conversation/Project memory and content are not shown.",
      "Provider registration is labeled only where provider:read is authorized; a model assignment does not imply provider availability. System capacities are software slot limits, not hardware fit.",
      "Structure/workflow edges remain only their recorded reporting/delegation/handoff links. Resource association requires an exact provider/model match; no relationship is inferred from similar names or roles.",
      "Model assignment API records have no source update timestamp. Structure/workflow timestamps and the system observed_at are displayed independently; reads are not one atomic cross-service snapshot."
    ]
  },
  {
    "number": 162,
    "title": "Three-dimensional map architecture and performance review",
    "description": "Assess the Task 116 Three.js layer before further 3D expansion and define data, performance, accessibility, and fallback limits.",
    "category": "Phase G - Command Center UI and Visualization",
    "status": "completed",
    "dependsOn": [
      116,
      159,
      160,
      161
    ],
    "acceptance": [
      "Review current use, supported hardware, data freshness, interaction, reduced motion, and 2D fallback.",
      "Retain the existing vendored Three.js path unless measured reference-device results fail these gates; do not assume a framework migration."
    ],
    "outOfScope": [
      "Do not add a new 3D dependency before this review."
    ],
    "decisions": [
      "Performance gate: on a published minimum desktop profile, measure at least 300 animation-frame intervals in each of three runs, both idle and during local inference; require p95 <= 16.7 ms and p99 <= 33.3 ms. Measure requestAnimationFrame intervals, not only synchronous renderer.render duration.",
      "Renderer-resource gate at the 60-node cap: renderer.info reports <= 128 geometries, <= 4 textures, and <= 240 render calls, with effects on and off after refresh/settling.",
      "Freshness and hardware decision: show structure, workflow, and resource timestamps independently; model assignments without source timestamps remain undated, and the UI must not imply an atomic multi-source snapshot. WebGL-capable browser/device support is required for 3D; the list remains the functional fallback, and no minimum hardware profile is currently claimed.",
      "Accessibility gate: WCAG 2.2 AA review; all nodes, links, and details are available in the equivalent labeled list; every action is keyboard reachable with visible focus; status is not conveyed by color alone; content works at 200% zoom; reduced motion immediately selects the list and prevents pulses; WebGL failure leaves the list usable."
    ],
    "area": "P23",
    "checkpoint": "task-162-three-dimensional-map-review",
    "validation": [
      "Reviewed the existing scene model, Three.js renderer, visualization controls, vendored library boundary, and deterministic scene/UI tests.",
      "Public documentation, task-roadmap, and update-manifest tests: 13 passed; no physical-device benchmark was run because the minimum supported desktop profile is not yet specified."
    ],
    "limitations": [
      "The current hard cap is 60 scene nodes; renderer pixel ratio is fixed at 1, power preference is low-power, and rendering is on demand apart from a bounded 800 ms state-change pulse.",
      "The displayed render-cost metric averages at most 30 synchronous WebGLRenderer.render call durations; it is not frame pacing, GPU completion time, or an end-to-end performance benchmark. renderer.info counters and a browser/device memory measurement are not currently exposed.",
      "No minimum desktop CPU/GPU profile or physical-device benchmark is recorded. The frame and renderer-resource values above are acceptance gates for future expansion, not achieved measurements or supported-hardware claims.",
      "Automated UI tests verify keyboard/list/reduced-motion/WebGL-fallback behavior, but no screen-reader or WCAG audit against a real browser/assistive-technology combination is claimed."
    ]
  },
  {
    "number": 163,
    "title": "Original ERSELMETZ AI assistant identity",
    "description": "Define an original central assistant profile that is calm, strategic, concise, trustworthy, and distinct from copyrighted identities.",
    "category": "Phase H - ERSELMETZ AI Persona",
    "status": "completed",
    "dependsOn": [
      103,
      113,
      159
    ],
    "acceptance": [
      "Document identity, role boundaries, language, and disclosure independently from authorization.",
      "Check examples for clarity, truthfulness, and language expectations."
    ],
    "outOfScope": [
      "Do not copy any fictional character name, voice, dialogue, or protected identity."
    ],
    "decisions": [
      "The owner-approved profile is a read-only product contract in corporation_docs/assistant-identity.md, surfaced by the existing Documentation Portal; it does not change runtime prompts or conversation behavior.",
      "ERSELMETZ AI is the original assistant name and identity. The role is central coordinator and truthful explainer; response language follows the conversation and may use English, Filipino, or natural Taglish.",
      "Service evidence determines claims and Agent attribution. Persona, title, and conversational instructions do not grant permissions, consent, approvals, assignments, or execution authority; the separate authorization system remains authoritative."
    ],
    "area": "P24",
    "checkpoint": "task-163-original-assistant-identity",
    "validation": [
      "Read-only Documentation Portal API regressions: 11 passed, 2 skipped.",
      "Reviewed English and Taglish examples for concise language, truthful status/attribution, non-impersonation, and separation of identity from authorization."
    ],
    "limitations": [
      "This task defines the product identity in documentation only. Runtime prompt composition, response preferences, and orchestration presentation remain unchanged and are handled by later tasks.",
      "The examples are policy illustrations, not measured model behavior or a guarantee that every configured Provider follows the profile."
    ]
  },
  {
    "number": 164,
    "title": "Response modes and owner preferences",
    "description": "Allow owners to select bounded response styles, locale, and privacy-conscious preferences, including optional voice preferences, without changing capability permissions.",
    "category": "Phase H - ERSELMETZ AI Persona",
    "status": "completed",
    "dependsOn": [
      103,
      118,
      140,
      163
    ],
    "acceptance": [
      "Persist allowlisted response mode, locale, detail level, and optional local voice preferences for the authenticated owner; provide reset and JSON export.",
      "Apply a bounded presentation-preference object to local chat prompts without changing Provider/Agent selection, routing, approval, permissions, consent, or execution."
    ],
    "outOfScope": [
      "Do not grant access or consent from persona selection."
    ],
    "decisions": [],
    "area": "P24",
    "checkpoint": "task-164-owner-response-preferences",
    "validation": [
      "Focused owner preference, authentication, chat prompt, and compatibility regressions: 50 passed.",
      "Chat browser module tests: 16 passed; focused owner, auth, chat, memory, and voice regressions: 71 passed; public docs tests: 13 passed. Full Python suite excluding the pre-existing syntax-invalid automation-trace file: 1,228 passed, 3 skipped, and 2 known unrelated baseline failures.",
      "Python compilation, JavaScript syntax checks, and git diff --check passed."
    ],
    "limitations": [
      "Preferences are stored unencrypted in the local SQLite database until reset or database removal; they contain presentation settings only, not chat content or credentials.",
      "The exported file contains only the current version, local owner identity, selected settings, and retention notice; it is not an import/restore feature.",
      "Optional voice preferences store a local voice identifier and language. They do not start microphone capture or speech playback, grant consent, enable cloud transcription, or guarantee the voice remains installed.",
      "Presentation preferences are a bounded provider-prompt hint and may not be followed by a model. No response-quality guarantee is made."
    ]
  },
  {
    "number": 165,
    "title": "Coordinator presence and orchestration presentation",
    "description": "Present coordinator identity, worker assignments, handoffs, and verified outcomes through existing orchestration services.",
    "category": "Phase H - ERSELMETZ AI Persona",
    "status": "completed",
    "dependsOn": [
      113,
      115,
      160,
      163
    ],
    "acceptance": [
      "Show responding Agent, assignment reason, status, and evidence source.",
      "Represent missing, uncertain, blocked, and failed states accurately."
    ],
    "outOfScope": [
      "Do not simulate Agents or assert work without service evidence."
    ],
    "decisions": [
      "Presentation uses the existing protected workflow-map snapshot and coordinator chat identity; no new orchestration, assignment, or execution behavior is introduced.",
      "The current workflow service does not record assignment rationale. The UI identifies the recorded source as the work-item Agent ID and displays the rationale as not recorded rather than inferring it.",
      "Agent names and roles are resolved only when the caller has agent:read. Missing registry records, unavailable registry capability, and denied detail access remain distinct."
    ],
    "area": "P24",
    "checkpoint": "task-165-coordinator-presence-orchestration",
    "validation": [
      "Workflow review/map and related Python regressions: 22 passed; workflow, dashboard, chat and related browser module tests: 34 passed; full browser-module suite: 190 passed.",
      "Full Python suite excluding the pre-existing syntax-invalid tests/test_automation_traces.py: 1,229 passed, 3 skipped, and 2 known unrelated baseline failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service).",
      "Public docs and update-manifest tests: 15 passed; Python application compilation, JavaScript syntax checks, and git diff --check passed."
    ],
    "limitations": [
      "Workflow presentation uses existing process-local snapshots and their freshness rules; it is not a live event stream.",
      "The existing workflow service has no assignment-reason field, so no rationale can be displayed beyond the recorded Agent-ID source.",
      "Detailed Agent identity is permission-gated. Workflow output and owner verification are shown only as recorded evidence; they do not guarantee quality or independently prove external effects."
    ]
  },
  {
    "number": 166,
    "title": "Opt-in proactive suggestions",
    "description": "Offer bounded recommendations from authorized current signals while requiring explicit owner action for protected operations.",
    "category": "Phase H - ERSELMETZ AI Persona",
    "status": "completed",
    "dependsOn": [
      140,
      142,
      143,
      160,
      163,
      165
    ],
    "acceptance": [
      "Let owners disable suggestions, configure quiet periods, inspect reasons, and dismiss.",
      "Show source/freshness; no implicit tool, provider, Task, or system action."
    ],
    "outOfScope": [
      "No background execution, unbounded polling, or self-granted authority."
    ],
    "decisions": [
      "Suggestions are disabled by default and use only existing process-local workflow records readable under workflow:read. Fixed rules surface blocked, failed, interrupted, review-pending, and active uncertain outcomes; raw prompts, outputs, titles, and provider error details are omitted.",
      "Evaluation occurs only when the dashboard loads or the owner explicitly refreshes. No background timer, notification, provider/model call, task query, or task/action execution is used.",
      "A recurring quiet period is a local-browser-time HH:MM interval. Dismissal stores only a bounded suggestion identifier in the owner-scoped local SQLite settings; stale dismissal identifiers are pruned against current results."
    ],
    "area": "P24",
    "checkpoint": "task-166-opt-in-proactive-suggestions",
    "validation": [
      "Focused suggestion, owner preference, local access, workflow, capability authorization, and Web UI regressions: 63 passed.",
      "Suggestion, dashboard, and workflow browser-module tests: 20 passed; complete browser-module suite: 194 passed.",
      "Full Python suite excluding the pre-existing syntax-invalid tests/test_automation_traces.py: 1,236 passed, 3 skipped, and 2 known unrelated baseline failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service).",
      "Python application compilation, JavaScript syntax checks, git diff --check, and public docs/update-manifest tests are recorded after the roadmap update."
    ],
    "limitations": [
      "Workflow records are process-local. Suggestions describe the state observed during the page request; event timestamps expose the last recorded change when available, but no cross-process synchronization or history is added.",
      "Suggestions are deterministic review prompts, not generated analysis or proof that the recommended next step is correct. The owner must inspect source records and decide what to do.",
      "Owner settings and dismissals are stored unencrypted in the local SQLite database until reset or database removal. Quiet periods use the browser's local time and are not notifications or background suppression."
    ]
  },
  {
    "number": 167,
    "title": "Trusted updates and configuration migration",
    "description": "Add an owner-visible, integrity-checked update path with versioned configuration migration and tested recovery.",
    "category": "Phase I - Productization and Stable Release",
    "status": "completed",
    "dependsOn": [
      126,
      127,
      129,
      131
    ],
    "acceptance": [
      "Verify origin/integrity, show release notes/migration preview, and preserve recoverable state.",
      "Test interruption, incompatibility, rollback limits, and user-data preservation."
    ],
    "outOfScope": [
      "No silent updates or destructive migration."
    ],
    "decisions": [],
    "area": "P25",
    "checkpoint": "task-167-trusted-updates-config-migration",
    "validation": [
      "Trusted-release, update API, and local-access Python tests: 27 passed using deterministic signed manifests and mocked GitHub responses.",
      "Updates and signed-release browser-module tests: 9 passed; desktop package tests: 16 passed, including external-key manifest signing.",
      "Full browser-module suite: 197 passed; public documentation site suite: 15 passed.",
      "Complete Python suite excluding the pre-existing syntax-invalid tests/test_automation_traces.py: 1,241 passed, 6 skipped, and 2 known unrelated baseline failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service).",
      "Python compileall, JavaScript syntax checks, and git diff --check passed."
    ],
    "limitations": [
      "The signed update channel is not active until the owner publishes a matching GitHub release, manifest, detached signature, and Windows x64 installer. The generated PEM signing key is unencrypted at rest; its directory ACL is restricted to the current Windows user and SYSTEM. Keep an encrypted offline backup and rotate the key if this profile is exposed.",
      "The installer is not Windows Authenticode-signed. The Ed25519 manifest verifies release origin and artifact integrity inside this app but does not provide Windows publisher identity.",
      "Installation is manual. Recovery backs up only the application SQLite database; reinstall and data restoration are manual, and restoring an older database after a future schema change is not guaranteed. The current migration contract stays at configuration version 1 with no data transform."
    ]
  },
  {
    "number": 168,
    "title": "Diagnostics export backup and restore",
    "description": "Provide explicit owner-controlled diagnostic export and backup/restore for supported configuration, memory, and app state.",
    "category": "Phase I - Productization and Stable Release",
    "status": "completed",
    "dependsOn": [
      118,
      130,
      143,
      167
    ],
    "acceptance": [
      "Preview included/excluded data, redact credentials, verify integrity, and test bounded restore.",
      "Document data that cannot be restored, erased, or exported from providers."
    ],
    "outOfScope": [
      "Do not export secrets/private data by default or claim success without restore verification."
    ],
    "decisions": [],
    "area": "P25",
    "checkpoint": "task-168-encrypted-data-portability",
    "validation": [
      "Focused portability, local access/permissions, preferences, managed software, memory/knowledge, project/task, local chat, and trusted-update regressions: 127 passed.",
      "Full deterministic Python suite excluding the pre-existing syntax-invalid tests/test_automation_traces.py: 1,250 passed, 6 skipped, and 2 pre-existing unrelated failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service).",
      "Browser modules: 200 passed; desktop package tests: 16 passed; public documentation tests: 15 passed; Next.js static build and TypeScript checks, Python compilation, JavaScript syntax, and git diff --check passed."
    ],
    "limitations": [
      "Only an encrypted local file is supported. AES-256-GCM uses a passphrase-derived Scrypt key; the passphrase is not stored and cannot be recovered. Export uses a local save picker when available, otherwise the browser's configured download destination; no cloud destination or automatic retention policy exists.",
      "By default only allowlisted owner preferences, suggestion settings, and software pins are included. Private application records require explicit opt-in. Common credential patterns are redacted from text; credential-named and unsupported database fields/tables fail closed. Pattern-based redaction cannot identify every possible secret, so owners should inspect privately opted-in files before sharing them.",
      "Restore accepts only the current configuration schema and a bounded supported database size, verifies encrypted integrity, SQLite quick_check and row counts, creates an encrypted pre-restore copy in the owner-managed local backups folder, and requires app restart. External provider/account data, credentials held outside SQLite, models, and remote records cannot be exported, restored, or erased by this feature."
    ]
  },
  {
    "number": 169,
    "title": "Crash recovery and measured performance readiness",
    "description": "Improve safe restart recovery and measure startup, memory, rendering, and model workloads before hardware-aware recommendations.",
    "category": "Phase I - Productization and Stable Release",
    "status": "completed",
    "dependsOn": [
      119,
      126,
      129,
      160,
      162
    ],
    "acceptance": [
      "Detect interrupted local operations and report uncertain outcomes without replay.",
      "Record platform/model/workload conditions and report UNKNOWN when evidence is absent."
    ],
    "outOfScope": [
      "Do not infer guaranteed hardware fit from model labels, telemetry, or slots."
    ],
    "decisions": [
      "Publish no numerical hardware-support thresholds until repeatable measurements exist across explicit minimum hardware profiles; keep unmeasured model workload and hardware fit UNKNOWN."
    ],
    "area": "P25",
    "checkpoint": "task-169-crash-recovery-performance-readiness",
    "validation": [
      "Focused readiness evidence, system monitoring, execution queue, chat history, and local access regressions: 39 passed.",
      "Readiness and Three.js browser modules: 13 passed; Python visualization page: 2 passed; desktop tests: 16 passed; public docs tests: 15 passed; Next.js static build and TypeScript checks passed.",
      "Full deterministic Python suite excluding pre-existing syntax-invalid tests/test_automation_traces.py: 1,253 passed, 6 skipped, and the same 2 unrelated baseline failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service)."
    ],
    "limitations": [
      "Startup timing covers only create_local_app factory setup; it excludes Python import/process launch, ASGI lifespan, and Electron startup. Process memory is a current OS working-set/RSS snapshot and excludes GPU memory and other processes.",
      "Rendering evidence stays on the local visualization page, which reports only synchronous WebGL render timing; the readiness API does not collect frame pacing, GPU completion, or assistive-technology measurements.",
      "No model inference benchmark was run. The configured Ollama inventory check was unavailable on this machine; assignments are recorded as conditions only, while model workload and hardware fit remain UNKNOWN. No thresholds or hardware readiness recommendations are published.",
      "Preexisting claimed queue entries are surfaced as outcome-unknown for owner inspection. Another process may still own a claim; the report does not decide or resolve it. Existing interrupted chat history remains read-only and is never replayed."
    ]
  },
  {
    "number": 170,
    "title": "Security audit and stable release acceptance",
    "description": "Complete an independent security/privacy review, end-user documentation, and evidence-based release checklist for supported targets.",
    "category": "Phase I - Productization and Stable Release",
    "status": "deferred",
    "dependsOn": [
      139,
      144,
      149,
      155,
      158,
      162,
      166,
      167,
      168,
      169
    ],
    "acceptance": [
      "Validate clean onboarding, permissions, update/recovery, privacy, and accessibility on the explicitly listed target. Deferred capability packs remain unavailable and are not installed or dynamically loaded.",
      "Publish tested platforms/providers, risks, skipped checks, limits, and recovery guidance.",
      "Complete an independent security/privacy review by a reviewer who did not author the implementation; record the reviewed commit, scope, findings, severity, and disposition.",
      "Call stable only for demonstrated targets and capabilities."
    ],
    "outOfScope": [
      "Do not add or claim the deferred Task 134 capability-pack lifecycle as part of this release.",
      "Do not mark unknown providers, hardware, autonomy, or platforms as ready."
    ],
    "decisions": [
      "Keep Task 134 deferred and exclude app-managed capability-pack installation/loading from the supported release until a verified artifact source, publisher trust anchor, and isolated loading boundary exist.",
      "No stable-release claim is permitted until the independent review is completed and its findings are dispositioned."
    ],
    "area": "P25",
    "checkpoint": null,
    "validation": [],
    "limitations": [
      "Task 134 remains deferred and incomplete. No app-managed capability-pack install, update, removal, or dynamic loading is supported or claimed.",
      "No independent security/privacy reviewer is available. At the owner's direction, Task 170 is deferred and remains incomplete; the product is not declared a stable release.",
      "The documented Windows 11 x64 installer is a local acceptance-tested unsigned artifact, not a public production release. No live provider/model workload or hardware-fit profile is release-verified."
    ]
  },
  {
    "number": 171,
    "title": "Unified settings and operator controls",
    "description": "Provide one coherent settings experience that keeps everyday preferences simple and advanced system controls discoverable and safely separated.",
    "category": "Phase J - Settings and Operator Controls",
    "status": "completed",
    "dependsOn": [
      132,
      133,
      140,
      159,
      160
    ],
    "acceptance": [
      "Group owner preferences separately from advanced provider/model, connection, capability, security, resource, and diagnostic settings.",
      "Use existing authorized APIs, preserve permission checks, and show current values, source, and actionable validation/errors.",
      "Keep routine chat and first-run readiness accessible without requiring users to understand operator controls."
    ],
    "outOfScope": [
      "Do not create new runtime configuration capabilities or weaken backend authorization.",
      "Do not expose credentials in ordinary settings summaries or logs."
    ],
    "decisions": [],
    "area": "P26",
    "checkpoint": "task-171-unified-settings-operator-controls",
    "validation": [
      "Focused Electron onboarding/settings tests: 17 passed.",
      "Next.js static production build and TypeScript checks passed; /settings was exported.",
      "Existing owner access, preference, provider connection, capability grant, and system-monitor regressions: 33 passed.",
      "Public documentation tests: 16 passed."
    ],
    "limitations": [
      "The settings hub reads only existing permission-checked endpoints and links to existing pages for changes; it adds no runtime settings or authority.",
      "The Electron installer was not rebuilt. The installed package must be rebuilt to include the new static settings route; hardware feasibility remains unknown."
    ]
  },
  {
    "number": 172,
    "title": "Interactive 3D corporation and execution map",
    "description": "Extend the reviewed visualization foundation into an interactive, evidence-backed 3D map of the organization and its live work relationships.",
    "category": "Phase K - Interactive Maps and Visualization",
    "status": "completed",
    "dependsOn": [
      114,
      115,
      116,
      159,
      160,
      162
    ],
    "acceptance": [
      "Show authorized Core, Agent/Employee, department/position, Project, Task/execution-flow, Provider/model, capability, resource, and memory/knowledge relationships only when backed by current source records.",
      "Support selecting nodes for details, zoom/orbit/pan, and filters/layers that make large maps understandable.",
      "Provide a labeled 2D/list fallback with equivalent access to key information, keyboard operation, reduced motion, and measured performance limits."
    ],
    "outOfScope": [
      "Do not invent nodes, relationships, activity, completion, or causal links.",
      "Do not choose or add a rendering dependency before Task 162 review and do not imply the map itself grants permissions."
    ],
    "decisions": [
      "Retain the existing vendored Three.js renderer based on Task 162 evidence; no dependency or framework migration is needed.",
      "Carry forward Task 162 reference gates (p95 <=16.7 ms, p99 <=33.3 ms across 300 frames on a published minimum desktop profile; <=128 geometries, <=4 textures, <=240 render calls) as validation targets. The profile is not defined, and a single on-device measurement is diagnostic rather than release qualification."
    ],
    "area": "P27",
    "checkpoint": "task-172-interactive-3d-corporation-execution-map",
    "validation": [
      "Deterministic scene and interaction tests: 14 passed, including source-backed links, layer/search filters, 60-node/119-link caps, 300-frame percentile reporting, cancellation, keyboard access, reduced motion, and WebGL fallback.",
      "Python visualization route tests: 2 passed; protected API behavior is exercised through the existing read endpoints.",
      "Desktop package tests: 17 passed; Next.js static production build and TypeScript checks passed; public documentation tests: 16 passed.",
      "Full Python run: collection is blocked by a pre-existing SyntaxError in tests/test_automation_traces.py; excluding it yielded 1,253 passed, 6 skipped, and two unrelated known model-assignment failures (test_model_set_command and test_model_replacement_uses_existing_assignment_service)."
    ],
    "limitations": [
      "Department records are not exposed by current APIs, so department nodes are omitted. Task and workflow records have no direct linkage field; no Task-to-workflow relationship is inferred.",
      "Each protected source is read independently on demand. The map does not represent an atomic multi-source snapshot, and timestamps are shown only where the source API provides them.",
      "The 60-node and 119-link render caps can omit records or relationships; layer filters and search select records for the current view. The list fallback exposes the same selected graph and omissions.",
      "Agent capability nodes represent registry declarations, not grants. Retained knowledge content is excluded; only authorized metadata and exact source references appear. Resource nodes describe software slots, not hardware fit.",
      "The 300-frame measurement is opt-in and device-local. Automated tests use deterministic timestamps; no physical-device, local-inference concurrency, minimum-hardware, screen-reader, or WCAG audit was performed."
    ]
  },
  {
    "number": 173,
    "title": "Memory and knowledge relationship explorer",
    "description": "Make retained memory and RAG activity understandable through authorized source, scope, provenance, retrieval, and status views.",
    "category": "Phase K - Interactive Maps and Visualization",
    "status": "completed",
    "dependsOn": [
      130,
      135,
      136,
      137,
      138,
      139,
      161
    ],
    "acceptance": [
      "Show retained knowledge sources, Project/owner scope, provenance, freshness, retrieval matches, and evidence-backed relationships with clear inferred-versus-recorded labels.",
      "Support useful cluster/relationship exploration and direct inspection without exposing content outside the owner's current permissions.",
      "Provide searchable labeled list/2D alternatives, accessible selection, and clear empty, stale, unavailable, and denied states."
    ],
    "outOfScope": [
      "Do not broaden Task 130 indexing, retention, or automatic chat-injection behavior.",
      "Do not reveal private memory through aggregate labels, graph edges, or search suggestions."
    ],
    "decisions": [
      "Use the existing permission-checked memory list/detail and semantic search APIs. The owner explicitly selects one exact Conversation, Project, or Corporation scope; never aggregate across scopes or owners.",
      "Show provenance only from returned records and label it as recorded. Similarity results are semantic retrieval candidates, not verified facts; freshness is confirmed only by re-reading the exact source revision.",
      "Keep the explorer read-only. Do not add indexing, retention changes, lexical/hybrid retrieval, automatic injection, or provider generation."
    ],
    "area": "P27",
    "checkpoint": "task-173-memory-knowledge-relationship-explorer",
    "validation": [
      "Focused memory, semantic retrieval, context, chat-context/knowledge, Project/Corporation knowledge regressions: 104 passed.",
      "Full browser module suite: 206 passed, including explicit scope reads, recorded provenance, semantic candidate display, exact-revision freshness recheck, denied/error states, safe text rendering, and stale-response rejection after scope changes.",
      "Memory API/page tests: 17 passed. The full Python suite was not rerun because the Python change is route markup only; focused checks above cover the changed page/API. Python compilation, JS syntax checks, and git diff --check passed; public docs tests: 16 passed. No live provider was called."
    ],
    "limitations": [
      "The explorer loads at most 50 records for one owner-authorized exact scope and does not claim complete history. The selected scope snapshot has no server-provided timestamp; expiry is shown and a semantic hit's revision is called current only after explicit recheck.",
      "Only existing semantic search matches are shown. The current APIs do not expose a durable RAG/index activity history or a lexical/hybrid result view; similarity is not proof.",
      "Conversation and Project source creation timestamps are not exposed by the detail API; the UI states that those timestamps are unavailable rather than substituting another time.",
      "Search excerpts are shown only after an explicit query within the selected, authorized scope. The graph itself hides record content, sends no query to a Provider, and does not inject retrieved context into chat."
    ]
  },
  {
    "number": 174,
    "title": "Unified multimodal capability controls and indicators",
    "description": "Integrate governed voice, vision, screen, camera, and automation status into a clear owner-facing control and activity surface.",
    "category": "Phase L - Multimodal Interface and Usability",
    "status": "completed",
    "dependsOn": [
      144,
      145,
      147,
      149,
      150,
      151,
      153,
      155,
      156,
      157,
      158,
      159,
      160
    ],
    "acceptance": [
      "Show supported/unavailable capability state, permission scope/expiry, and truthful active microphone, camera, screen-capture, speech-playback, and automation indicators.",
      "Provide explicit owner controls to start, stop, revoke, or inspect supported operations and clearly distinguish local processing from online transfer.",
      "Keep denied, unsupported, failed, uncertain-stop, and inactive states distinct and accessible."
    ],
    "outOfScope": [
      "Do not auto-enable, continuously capture, or silently transfer media or screen content.",
      "Do not claim a remote operation stopped without provider confirmation."
    ],
    "decisions": [],
    "area": "P28",
    "checkpoint": "task-174-unified-multimodal-capability-controls",
    "validation": [
      "Focused Task 174 Python regressions: 27 passed; full browser-module suite: 206 passed; focused capability UI suite: 23 passed; public docs tests: 16 passed; update-manifest tests: 6 passed; Python compilation, JavaScript syntax checks, and git diff --check passed.",
      "Full Python collection remains blocked by the existing SyntaxError in tests/test_automation_traces.py. Excluding that file yielded 1,256 passed, 3 skipped, and two previously recorded unrelated model-assignment failures."
    ],
    "limitations": [
      "Capability indicators reflect browser feature support and events reported by the current page only; they do not inspect OS-wide or cross-page activity or device permission state.",
      "The current-session permission API does not expose an expiry timestamp; session permissions end at sign-out or session expiry. Temporary grants expose scope, expiry, and revocation.",
      "Vision availability depends on the selected model; computer automation is unavailable in this UI. Remote cancellation remains unknown without provider confirmation.",
      "The full Python suite cannot currently pass collection because of tests/test_automation_traces.py syntax, and two unrelated known model-assignment tests still fail when that file is excluded."
    ]
  },
  {
    "number": 175,
    "title": "AI-run usability and accessibility regression evaluation",
    "description": "Evaluate supported user journeys through reproducible AI-run UI automation, accessibility checks and heuristic review; track representative-user research separately.",
    "category": "Phase L - Multimodal Interface and Usability",
    "status": "completed",
    "dependsOn": [
      132,
      133,
      159,
      160,
      171,
      172,
      173,
      174,
      176,
      177,
      178
    ],
    "acceptance": [
      "Run after the automated development acceptance of Tasks 176, 177 and 178; link evidence for the exact source or artifact tested.",
      "Exercise first-run readiness, basic chat, provider/model configuration, permission review, troubleshooting and navigation through scripted beginner and experienced-owner scenarios, without claiming actual representative-user participation.",
      "Evaluate keyboard-only use, screen-reader semantics, responsive layouts, contrast, reduced motion, and understandable loading/empty/error/denied states.",
      "Clearly communicate that app-managed capability packs are unavailable; do not present pack installation or management as a supported user journey.",
      "Record reproducible findings, severity, limitations, and verified follow-up fixes; do not claim usability or accessibility conformance without evidence."
    ],
    "outOfScope": [
      "Do not treat automated checks alone as proof of usability or accessibility conformance.",
      "Do not change runtime behavior or grant capabilities as part of the evaluation.",
      "Do not evaluate or claim the deferred Task 134 capability-pack lifecycle."
    ],
    "decisions": [
      "Task 134 is deferred and excluded from the supported user journeys; the UI must describe packs as unavailable until their trust and loading boundaries are implemented.",
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "area": "P28",
    "checkpoint": "task-175-ai-usability-accessibility-regression-evaluation",
    "validation": [
      "Expert heuristic walkthrough on 2026-10-15 covered first-run readiness, owner sign-in, chat, provider/model setup, permission review, troubleshooting links, navigation, organization and knowledge maps. It is not a representative owner study.",
      "Reproducible findings and verified fixes: (medium) open desktop first-run Setup checks: unsupported app-managed capability packs appeared Unknown; now Unavailable, with browser speech packs identified separately. (medium) #647488 small text measured 3.56:1 against #121d2b, below 4.5:1; shared #77889c now measures at least 4.68:1 on reviewed dark surfaces. (low) open /ui or /ui/chat and inspect Capability controls: four media indicators plus the aggregate status all announced changes; per-indicator live roles were removed while the aggregate remains announced. (low) Chat voice controls now label optional language downloads browser-managed.",
      "AI-run scripted UI evaluation on source checkpoint efad6ad: `node --test tests/test_chat_ui.mjs tests/test_employee_chat_ui.mjs desktop/test/onboarding.test.cjs desktop/test/navigation.test.cjs` passed 31/31. Coverage includes first-run/settings guidance, capability-pack unavailable state, accessible shared navigation, CSRF and permission-denied paths, chat plan cancellation, per-turn cloud consent, provider errors without replay, and retained-history opt-in/deletion.",
      "Existing review evidence: focused voice/safety browser checks 15 passed; full browser-module suite 220 passed; Electron tests 24 passed; Next.js production build and TypeScript checks passed; public docs 17 passed. The current-source packaged Windows Task 176 smoke exercised first-run setup, local chat, restart, uninstall retention, and reinstall recovery under the existing Windows account.",
      "Heuristic findings and fixes retained from 2026-10-15: unsupported app-managed packs now say Unavailable; reviewed small-text contrast is at least 4.68:1 on inspected dark surfaces; only aggregate capability status announces changes; optional speech-language downloads are identified as browser-managed. These are scoped checks, not accessibility certification."
    ],
    "limitations": [
      "No representative new or experienced owner participated; user research remains follow-up.",
      "Keyboard navigation and screen-reader semantics were reviewed in source and automated checks, but no real assistive-technology session or independent accessibility audit was performed. Responsive breakpoints and reduced motion were inspected and covered by code-level/browser tests, not exercised across physical devices or every viewport. No usability or accessibility conformance claim is made.",
      "Full Python suite baseline at Task 176 acceptance: 1,319 passed / 5 skipped / 0 failed (2 warnings); it was not rerun for this documentation/evaluation-only checkpoint."
    ],
    "followUpValidation": [
      "Representative-owner studies, real assistive-technology sessions and physical-device coverage remain unverified; automated completion makes no usability or accessibility conformance claim."
    ]
  },
  {
    "number": 176,
    "title": "Zero-config first run and project cleanup",
    "description": "Add an owner-controlled Windows first-run path from password setup to Coordinator Chat using either local Ollama or Google Gemini, while preserving existing authentication, consent, and provider boundaries.",
    "category": "Phase M - First-run Setup and Project Cleanup",
    "status": "completed",
    "dependsOn": [
      104,
      105,
      127,
      129,
      132,
      133,
      171
    ],
    "acceptance": [
      "On the supported Windows 11 x64 desktop target, a first-run owner can choose local Ollama or online Gemini and reach an open Coordinator conversation after explicit setup actions; startup and ordinary later launches remain available without repeating non-secret configuration.",
      "Ollama setup detects the supported standard install locations and loopback service; any Ollama installer download is previewed, retrieved only from an official fixed source, integrity-checked, launched without elevation, and run only after explicit owner confirmation.",
      "Before a model pull begins, show the verified model identity and registry-manifest byte estimate, available-size evidence when known, destination limitations, and exact owner confirmation. Stream bounded progress, allow cancellation, recheck `/api/tags`, and report real installed-model state.",
      "Gemini setup accepts only the existing supported key format, explicitly previews and confirms the model-catalog request, keeps credentials in memory by default, and persists a key only through an explicit current-Windows-user DPAPI opt-in. Per-turn cloud consent and spend limits remain unchanged.",
      "After setup, restore only explicitly persisted provider/model configuration, the existing Coordinator assignment, and configured 1/1/1 global/provider/model ResourceManager slots. Controlled Task dispatch remains subject to its existing confirmation, Ollama-only, and Task 170 release-review limits; slot configuration does not grant dispatch authority or imply Gemini dispatch.",
      "Provide distinct and recoverable offline, Ollama-not-installed, service-not-running, insufficient-space/space-unknown, pull-canceled/failed, unsupported-model, bad-key, and catalog-unavailable states with retry/skip paths. Hardware and GPU feasibility remain UNKNOWN unless directly observed.",
      "Keep the default API authentication rejecting, preserve loopback-only binding, HttpOnly sessions, Origin/CSRF checks and existing permissions; any startup-to-browser authentication handoff must use the existing owner login contract and create no new principal or permission.",
      "Shorten the root README to at most 150 lines, preserve removed detail in documentation, remove the duplicated Task 71 passage, reconcile roadmap status claims against `docs/tasks-data.mjs`, and add a concise project/license reference without publishing an unapproved license."
    ],
    "outOfScope": [
      "Do not add elevation, silent software/model downloads, automatic Gemini calls, silent cloud fallback, or automatic Task execution/replay.",
      "Do not claim hardware/GPU compatibility from model names or machine inventory; report UNKNOWN when no verified capability signal exists.",
      "Do not broaden Task dispatch beyond its current loopback Ollama path, bypass owner confirmation, or mark deferred Task 170 stable-release review complete.",
      "Do not store Gemini credentials in SQLite, logs, task records, backups, or ordinary configuration files; DPAPI persistence must be explicitly opt-in and owner-resettable.",
      "Do not alter the default standalone API's fail-closed authentication or make Task 53 documentation portal writeable."
    ],
    "decisions": [
      "The ordinary Gemini-key policy is memory-only. Restart persistence is available only if the owner explicitly opts in to current-Windows-user DPAPI protection; without that opt-in, the key must be re-entered after process restart.",
      "Configured slots enable only the pre-existing controlled-dispatch behavior for eligible pending Tasks routed to loopback Ollama. Gemini remains chat-only for controlled dispatch under the existing contract.",
      "Task 175 AI-run evaluation is recorded in checkpoint task-175-ai-usability-accessibility-regression-evaluation; representative-user and assistive-technology research remain optional follow-up.",
      "MIT licensing is not authorized until the owner explicitly confirms the license choice.",
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "area": "P29",
    "checkpoint": "task-176-zero-config-first-run-ai-acceptance",
    "validation": [
      "Implementation work in the worktree has automated validation: full Python suite 1,293 passed / 3 skipped / 0 failed (2 deprecation warnings); browser modules, public docs, and Electron suites: 257 passed / 0 failed (216 + 17 + 24).",
      "Additional checks passed: static Next.js production build and TypeScript checks, Python compilation, frozen-backend build, installed-package smoke against a separately built Windows installer, JSON/JavaScript syntax checks, and git diff --check. The live official Ollama release and model-manifest preview returned bounded metadata with an exact digest; no installer/model download or paid Gemini request was made.",
      "Partial installed-package acceptance (2026-10-17): built and installed the current Windows x64 package into temporary install and LOCALAPPDATA directories under the current Windows account. Set the owner password, chose Ollama, explicitly selected the already-installed llama3.2:3b model, and received a real local chat reply. Restart required the owner password but did not repeat provider setup; a new Coordinator conversation produced another local reply. Uninstall retained owner data and reinstall recovered it. This was not a separate clean Windows user profile and did not exercise app-managed Ollama installation/model download or Gemini.",
      "Current-source package acceptance (2026-10-18): Next.js static production build and TypeScript checks passed; PyInstaller and Windows x64 installer builds succeeded. The current installer was installed and exercised in temporary install/app-data directories: owner setup, selection of an already-installed Ollama model, a real local Coordinator reply, restart without repeating provider setup, uninstall retention, and reinstall recovery passed. This is still the current Windows account, not a separate clean Windows user profile.",
      "Re-run packaged Windows acceptance (2026-10-18): the preserved installer `ERSELMETZ-AI-Setup-0.1.0-win-x64.exe` (162,986,424 bytes; SHA-256 `C550611C90C70DBEB58B888C0B88F027D8AEF4C459BC9A65486DD9EB376C732B`) passed `desktop/scripts/smoke-installer.py`: fresh owner setup, existing local llama3.2:3b reply, restart without repeating setup, second chat reply, uninstall data retention and reinstall recovery. The smoke used a temporary install and app-data profile under the current Windows account; source commit provenance for this preserved artifact is unavailable.",
      "Windows OS ACL inspection used PowerShell `Get-Acl` on `%LOCALAPPDATA%\\ERSELMETZ AI`, its `projects` directory, and `projects\\ai_corporation.db`: current user owns each and has FullControl; inherited CodexSandboxUsers access is ReadAndExecute/Synchronize; SYSTEM and Administrators have FullControl. Task 184 separately verifies isolated app-data across actual Python process restart. No clean secondary Windows account was used.",
      "Focused Task 176 tests: 18 passed, covering fake Ollama manifest/progress/cancel/recheck, explicit pull confirmation and Retry, Gemini catalog/error sanitization and assignment behavior, plus current-user DPAPI round-trip for explicitly retained credentials.",
      "Final automated validation (2026-10-18): full Python suite 1,319 passed / 5 skipped / 0 failed (2 deprecation warnings); browser modules 220 passed; public docs 17 passed; Electron 24 passed. Packaged Windows smoke, Python compilation, JavaScript syntax checks, and git diff --check passed."
    ],
    "limitations": [
      "Live paid Gemini calls, model inference, Ollama installation, and large model downloads are not required for deterministic tests and must remain owner-triggered integration actions.",
      "Broader clean-profile/live-provider integration coverage remains unverified follow-up; it does not require human QA sign-off. The current-source package smoke verified owner setup, an already-installed Ollama model, a real local reply, restart with provider setup retained, uninstall retention, and reinstall recovery, but used temporary app-data under the existing Windows account. Pending: a separate clean Windows user profile; packaged installer preview followed by explicitly confirmed Ollama installation and model download/progress/cancel/recheck; Gemini key/catalog confirmation, cloud-turn approval and reply, and DPAPI restart persistence; live stopped/offline Ollama recovery with Retry; malformed and rejected Gemini key errors with secret redaction. No Gemini key is configured here, and no paid request, installer download, or model download was made.",
      "Development completion requires truthful automated Windows packaging and isolated-state evidence; automated fakes alone do not establish that every Windows machine, Ollama runtime, GPU, or provider account will work.",
      "Task 170 remains deferred and incomplete. Real Gemini account/catalog/chat, real Ollama installer/model download, offline/stopped-provider retries, separate clean-account coverage, assistive technology and representative-user research remain unverified follow-up; no paid request, installer download or model download was made for this checkpoint."
    ],
    "automatedVerification": [
      "Run packaged Windows setup, restart, data-retention and recovery against isolated app-data, inspect installed paths and ACLs using OS APIs, and record artifact/source identity. A separate Windows account or VM is optional follow-up coverage.",
      "Exercise Ollama installation/pull progress/cancel/recheck and Gemini catalog/consent/DPAPI/error paths through controlled adapters and UI automation. Record real integrations separately; credentials, paid calls and downloads are not prerequisites for deterministic acceptance."
    ]
  },
  {
    "number": 177,
    "title": "Auto-RAG with citations and answer trace",
    "description": "Add owner-opt-in retrieval over explicitly selected retained knowledge, usable local note intake, and a factual per-turn How I answered panel.",
    "category": "Phase N - Auto-RAG and Answer Tracing",
    "status": "completed",
    "dependsOn": [
      62,
      63,
      66,
      73,
      103,
      110,
      130
    ],
    "acceptance": [
      "Coordinator Chat keeps a default-off per-conversation Use my knowledge switch and retrieves only from owner-selected exact scopes, rechecking current owner access, expiry, withdrawal, and revision for every turn.",
      "Retrieval combines the existing deterministic lexical path with optional configured semantic candidates; it ranks, deduplicates near-identical chunks, and caps the result to at most 3 selected scopes, 5 chunks, and 1,800 UTF-8 context bytes with truthful truncation evidence.",
      "Retrieved excerpts are delimited structured untrusted reference data with citations; the model is told not to follow embedded instructions and to say when selected evidence is insufficient. Every successful turn shows sources, scope, chunk reference, scores, and freshness in How I answered.",
      "An owner can add a private text note or bounded UTF-8 .md/.txt/text-based .pdf file, set expiry, explicitly consent to local retention, build or inspect the optional local semantic index on demand, and forget the source with derived-index invalidation.",
      "A structured server-side per-turn trace reports the actual coordinator/provider/model, route source, selected query and chunks, truncation, cloud consent/provider use, elapsed time, sanitized failures, and that tools/tasks were not used. It never stores raw exceptions or prompts by default.",
      "An exact assembled prompt is shown only for an explicitly opted-in local-model turn, in that one response only; prompt capture is unavailable for cloud/image turns and is not stored in the trace.",
      "Owner-only access, CSRF/Origin protections, explicit retention and per-turn cloud consent, expiry/revocation checks, no automatic downloads, and existing Task/Tool authority boundaries remain enforced."
    ],
    "outOfScope": [
      "Do not add automatic retrieval when the toggle is off, background indexing, model downloads, automatic retries, Task creation/execution, Tool use, or changes to Agent/model assignments.",
      "Do not add web-page ingestion; the optional Task 88 allowlisted HTTPS path is not required here.",
      "Do not include a 3D globe in Task 177; the former Part 4 is a separate planned Task 186 and is not a prerequisite for Task 175.",
      "Do not claim verified reasoning, citation correctness, semantic quality, or hardware/model suitability from generated text or deterministic fakes."
    ],
    "decisions": [
      "Owner notes use a dedicated owner scope in the existing SQLite-backed memory system and are included in encrypted backups only with the existing explicit private-data option.",
      "Semantic retrieval remains optional and uses the existing Task 130 provider when configured; lexical retrieval remains available without it.",
      "Traces are bounded and process-local. Exact prompts are returned only in the explicit local one-turn response and are never retained for later inspection.",
      "Task 177 was completed after an isolated real local-model acceptance demonstrated a retrieved source in the factual answer trace; deterministic fake-provider tests alone were not treated as that evidence. Task 176 clean-secondary-account and live-provider coverage remain unverified follow-up and do not block scoped development acceptance."
    ],
    "area": "P30",
    "checkpoint": "task-177-auto-rag-trace",
    "validation": [
      "Isolated real local-model acceptance (2026-10-17): with a temporary SQLite profile and a retained owner note stating that the Orion test server uses port 8123, Ollama llama3.2:3b returned the matching answer. The trace identified Ollama/model, the exact source and chunk reference, retrieval score and expiry, and recorded no Task or Tool side effect. The temporary profile was removed.",
      "Focused Task 177 and directly related knowledge/context regressions: 65 passed, 1 existing Starlette deprecation warning. Full Python suite: 1,287 passed, 3 skipped, 0 failed, 2 deprecation warnings. Browser-module tests: 216 passed; public documentation tests: 17 passed."
    ],
    "limitations": [
      "One real Ollama llama3.2:3b response was verified against one synthetic retained fact; this does not establish general answer faithfulness, citation correctness, semantic quality, speed, or hardware suitability. The live UI was not manually inspected in a browser. Gemini was not called; cloud behavior uses an explicit fake path.",
      "Semantic retrieval tests use deterministic embedding/vector fakes. They do not establish real embedding relevance or quality. Scanned PDFs are unsupported; PDF intake extracts text only.",
      "Traces and exact one-turn prompt views do not survive app restart. Persisted notes and SQLite memory do; derived semantic storage depends on the configured local index provider.",
      "Optional Task 88 web ingestion and the former Task 177 Part 4 3D globe are not implemented. The globe is now a separate planned Task 186. The current trace remains 2D and accessible.",
      "Task 176 is complete for its scoped contract; clean-secondary-account and live-provider coverage remain unverified follow-up. Task 177 is complete for its scoped contract; broader citation quality remains unverified."
    ]
  },
  {
    "number": 178,
    "title": "Fix left navigation disappearing",
    "description": "Keep navigation reachable across the Python UI and Next.js desktop routes, including narrow-window layouts and first-run transitions.",
    "category": "Phase O - Navigation Reliability",
    "status": "completed",
    "dependsOn": [
      126,
      159,
      176
    ],
    "acceptance": [
      "Reproduce the missing-navigation flow and record the root cause before changing code.",
      "Render navigation from the shared application shell on every applicable route; keep a visible sidebar on wide windows and an accessible menu toggle on narrow windows.",
      "Keep navigation reachable after route changes, responsive resizing, static-export routing, and first-run completion without duplicating page-specific sidebars.",
      "Add a regression test for the failing route/layout case and run the full relevant test suites."
    ],
    "outOfScope": [
      "Do not redesign navigation destinations or add product capabilities.",
      "Do not claim manual native-window acceptance unless performed."
    ],
    "decisions": [],
    "area": "P31",
    "checkpoint": "task-178-nav-fix",
    "validation": [
      "Full Python suite: 1,282 passed, 8 skipped, 0 failed. Browser modules: 216 passed; Electron tests: 23 passed; public documentation tests: 16 passed.",
      "Next.js static production export and TypeScript checks passed; Python compilation and git diff --check passed. Regression coverage includes shared Next layout, Python route injection, compact menu behavior, and existing browser layout checks.",
      "On 2026-10-18, the corrected packaged Windows Electron app was opened with a temporary profile and resized at the native window level. Wide and narrow layouts were checked on both Next.js and Python UI routes; route change and first-run skip transition were included. The narrow menu opened, navigation was reachable, and Escape closed it."
    ],
    "limitations": [
      "Native resize behavior was verified in the locally packaged Windows app using an automated Win32/Playwright flow; no human mouse-drag or representative-owner usability study was performed. The tested installer is a local review build and has not been published or distributed."
    ]
  },
  {
    "number": 179,
    "title": "Sync public docs and extend the roadmap",
    "description": "Make the public task pages, status summaries, README, and changelog agree with the authoritative task records, then publish the reviewed future roadmap without implementing future capabilities.",
    "category": "Phase P - Roadmap Maintenance",
    "status": "completed",
    "dependsOn": [],
    "acceptance": [
      "The task page, home, roadmap, and changelog render status from docs/tasks-data.mjs; a public-docs regression fails when any task is missing from any required view.",
      "Tasks 175-178 show their honest implementation and acceptance state; Task 175 is ordered after automated development acceptance of Tasks 176-178.",
      "Tasks 180-190 are published as planned or design-only contracts with goals, acceptance, exclusions, dependencies, risks, and AI-run verification.",
      "The recommended order and rationale are derived from the authoritative roadmap and no future runtime capability is implemented."
    ],
    "outOfScope": [
      "No runtime changes, Task 177 implementation, installer changes, provider calls, downloads, or permission changes."
    ],
    "decisions": [],
    "area": "P32",
    "checkpoint": "task-179-roadmap-sync",
    "validation": [
      "Public documentation tests: 17 passed, 0 failed. Browser UI modules: 180 passed, 0 failed. Electron tests: 23 passed, 0 failed. Full Python suite: 1,282 passed, 8 skipped, 0 failed (2 warnings). `git diff --check`, JavaScript syntax checks, and update-manifest JSON parse passed."
    ],
    "limitations": [
      "At the original Task 179 checkpoint, the docs commit had not yet been pushed. It is now present on origin/main (HEAD and origin/main match); live-site deployment was not independently checked in this follow-up, and this checkpoint does not prove any pending manual acceptance."
    ]
  },
  {
    "number": 180,
    "title": "Hardware profile and model recommendation",
    "description": "Report directly observed CPU, GPU, RAM, and disk facts with source and freshness, then recommend an Ollama model size with an explicit CPU-use warning where applicable.",
    "category": "Phase Q - Hardware-Aware Local Models",
    "status": "completed",
    "dependsOn": [
      176
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Show each detected CPU/GPU/RAM/disk value with its observation source and timestamp; unsupported or unavailable fields remain UNKNOWN.",
      "Provide a bounded Ollama model-size recommendation with stated assumptions and a clear warning when inference is expected to run on CPU.",
      "Do not claim a model will fit or run well without verified capacity evidence; provide a manual confirmation before any separate download flow."
    ],
    "outOfScope": [
      "No model download, install, pull, automatic selection, GPU benchmark, cloud routing, or hardware telemetry upload."
    ],
    "risks": [
      "OS inventory may be incomplete or stale; recommendation thresholds can mislead across quantization/runtime variants."
    ],
    "area": "P33",
    "checkpoint": "task-180-hardware-profile-ai-acceptance",
    "validation": [
      "Implementation source reviewed in commit 15f49fc044c41ae4d4f936a67fbda71f241640d8; no further provider, routing, persistence, download, or telemetry behavior was added for this checkpoint.",
      "Focused deterministic service/API tests: `python -m pytest -q tests/test_hardware_profile.py tests/test_hardware_profile_api.py` passed 5; coverage includes source/timestamps, UNKNOWN states, bounded guidance, low-disk note, path redaction, and existing system:read authentication.",
      "Desktop UI regressions: 7 tests passed, including 2 new actual settings-summary checks for per-field provenance, CPU-only warning, UNKNOWN fields, and no-download text. Full Electron suite: 26 passed; desktop UI TypeScript check passed.",
      "Read-only local Windows comparison: CPU/GPU model names and total physical RAM matched WMI/OS counters. Ollama destination total/free disk values matched the C: volume within normal sampling-time change. Available RAM is time-sensitive. The adapter does not claim GPU memory or actual Ollama accelerator use.",
      "Latest full-suite baseline at Task 176 acceptance: Python 1,319 passed / 5 skipped / 0 failed (2 warnings); browser modules 220 passed; public docs 17 passed. Current public-docs tests after this record: 17 passed. No live inference, download, routing change, or telemetry upload occurred."
    ],
    "limitations": [
      "Physical CPU-only host behavior and recommendation accuracy across systems, model quantizations, and workloads remain unverified follow-up. The local check covered one GPU-equipped Windows host only.",
      "Usable VRAM and whether Ollama actually uses a GPU remain UNKNOWN; WMI AdapterRAM is intentionally not trusted. A detected GPU is not evidence of accelerated inference or model fit.",
      "The RAM-based size suggestion is heuristic guidance, not compatibility, performance, or fit proof. Disk space is only a current local observation and no download is initiated."
    ],
    "automatedVerification": [
      "Compare host inventory with independent OS counters where available; use CPU-only, GPU, missing and stale inventory fixtures to verify UNKNOWN states and bounded guidance. Automate UI checks for uncertainty and CPU warnings; broader physical-host coverage remains unverified follow-up."
    ],
    "followUpValidation": [
      "Unavailable real hardware, provider-account, physical-device and representative-user coverage is recorded as unverified enhancement work; it does not require human QA sign-off for this development checkpoint."
    ]
  },
  {
    "number": 181,
    "title": "Consent-based routing suggestions for small models",
    "description": "Keep simple prompts on the configured default local model and suggest a larger local model or Gemini for harder prompts only after per-turn owner consent.",
    "category": "Phase R - Reviewed Model Routing",
    "status": "completed",
    "dependsOn": [
      177,
      180
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed.",
      "The optional classifier is a deterministic local heuristic, not a model-quality or hardware-fit assessment. The configured coordinator remains the default and alternate model use requires per-turn confirmation."
    ],
    "acceptance": [
      "Keep the configured local model as the default route for simple prompts. Only a clear deterministic complexity cue may produce an uncertain suggestion; simple or uncertain classification preserves the configured route.",
      "Require explicit per-turn owner consent before sending any prompt to another local model or Gemini; show provider/model and data destination before confirmation.",
      "Declining, unavailable checks, or uncertain classification preserve the original route without retries, fallback, or assignment mutation."
    ],
    "outOfScope": [
      "No automatic provider/model selection, ranking claims, silent cloud use, hidden prompt transfer, or Agent assignment changes."
    ],
    "risks": [
      "Prompt difficulty is uncertain; a routing suggestion can be wrong and cloud consent must remain distinct per turn."
    ],
    "area": "P34",
    "checkpoint": "task-181-consent-based-model-routing",
    "validation": [
      "Focused Python route-suggestion and owned-chat tests verify simple prompts retain the default, only explicit installed larger-size IDs are suggested, missing/unavailable routes do not fall back, alternate local execution requires per-turn route consent, Agent assignments remain unchanged, and the observed route is recorded in the real chat trace.",
      "Browser chat test verifies the route destination/model is displayed before confirmation, route choices are cleared when the prompt changes, route consent is sent only after confirmation, and cloud consent remains a separate checkbox.",
      "Full Python suite: 1,329 passed, 3 skipped, 0 failed; browser-module suite: 222 passed; Electron suite: 26 passed; public-docs suite: 17 passed. Focused Python route/chat tests: 30 passed. Focused chat UI tests: 23 passed. Python compilation, JavaScript syntax checks and git diff --check passed. No live Gemini request, paid call, model download or inference was performed."
    ],
    "limitations": [
      "Prompt difficulty is heuristic and may be wrong. Local-size suggestions require explicit comparable parameter-size tokens in both configured and currently observed installed-model identifiers; unknown sizes are never described as larger. Hardware feasibility, output quality and latency are not evaluated.",
      "Route suggestions are offered only when the conversation's configured Coordinator is local; selecting an online Coordinator does not silently switch it back to local or enable these suggestions.",
      "The route suggestion check reads bounded local Ollama inventory only when the owner asks for suggestions. Configured Gemini candidates come only from the current app-run provider connection/catalog. Provider accounts, live Gemini execution, physical hardware behavior and runtime latency remain unverified follow-up."
    ],
    "automatedVerification": [
      "AI-run verification: Deterministic fakes cover simple/complex/uncertain prompts, installed larger local IDs, route confirmation, separate Gemini consent, owner-scoped suggestion access, unavailable routes, no retry/fallback, unchanged Agent assignments, and trace provenance. Live-provider and hardware outcomes remain unverified follow-up."
    ],
    "followUpValidation": [
      "Unavailable real hardware, provider-account, physical-device and representative-user coverage is recorded as unverified enhancement work; it does not require human QA sign-off for this development checkpoint."
    ]
  },
  {
    "number": 182,
    "title": "Reviewed tools for small models",
    "description": "Expose explicit bounded calculator and owner-authorized lookup in one selected top-level corporation_docs file to chat with visible trace entries. Web search is excluded from this task.",
    "category": "Phase S - Reviewed Tool Use",
    "status": "completed",
    "dependsOn": [
      177
    ],
    "decisions": [
      "Owner-approved scope is local calculator and selected corporation_docs lookup only; web search is excluded.",
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Expose only a bounded arithmetic calculator and exact-file lookup selected from the existing top-level corporation_docs portal; require documentation:read for the file lookup and fail closed for every unsupported tool.",
      "Show each explicitly selected tool call, redacted safe parameters, source, outcome, and elapsed time in the real per-turn trace; label file results as untrusted context.",
      "The implemented calls are read-only. Any future side-effecting tool must require fresh owner confirmation bound to its exact action and deny by default when permission, scope, or result is unknown."
    ],
    "outOfScope": [
      "Web search, arbitrary shell, code execution, background crawling, silent downloads, general filesystem access, and unreviewed side effects."
    ],
    "risks": [
      "Selected local documentation is untrusted input and may contain prompt injection; sending it to an online provider requires the existing per-turn cloud consent."
    ],
    "area": "P35",
    "checkpoint": "task-182-reviewed-chat-tools",
    "validation": [
      "Completed scoped Task 182 after implementation/evidence review. The calculator accepts only bounded arithmetic; exact-file lookup reads one selected document through the existing read-only documentation service and requires documentation:read. Tool results are marked untrusted, traces include bounded/redacted parameters, source, outcome and elapsed time, unsupported tools fail closed, and the UI obtains owner confirmation before the selected tools run. No web search or side-effecting tool is exposed. Focused reviewed-tool/API/knowledge tests: 21 passed; focused chat UI tests: 24 passed. Full Python suite: 1,329 passed, 3 skipped, 0 failed; browser modules: 223 passed; Electron: 26 passed; public docs: 17 passed. No live Gemini call or external-provider transfer was performed."
    ],
    "limitations": [
      "Local documentation content is untrusted and may contain prompt injection. If selected results are sent to Gemini, the existing separate per-turn cloud consent is required. No live Gemini transfer was performed. No arbitrary local-file scope or side-effecting tool is exposed; there is no side-effect approval dialog because the approved tools are read-only."
    ],
    "automatedVerification": [
      "AI-run verification: `python -m pytest -q tests/test_reviewed_chat_tools.py tests/test_chat_knowledge.py` covers bounded arithmetic, exact selected-file reads, path-like and oversized document rejection, documentation:read denial, prompt-injection labeling, redacted parameters, unsupported web search, real per-turn trace sources/outcomes/timing, and no Task creation. `node --test tests/test_chat_ui.mjs` covers explicit tool selection, confirmation, trace rendering, and documentation listing only after opening the tool section with permission."
    ],
    "followUpValidation": [
      "No live Gemini transfer was performed; actual external-provider handling of selected private document excerpts remains unverified. This does not block the deterministic read-only tool contract, and no human QA sign-off is required under the revised development policy."
    ]
  },
  {
    "number": 183,
    "title": "Visible task scaffolding",
    "description": "Break complex chat requests into visible plan, retrieve, and answer steps, recording actual events in the per-turn trace.",
    "category": "Phase T - Transparent Task Scaffolding",
    "status": "completed",
    "dependsOn": [
      177,
      182
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Display a bounded plan before work and record each real plan, retrieval, tool, and answer step with source, status, and timing.",
      "Allow the owner to cancel before each separately authorized action; no step is represented as completed without an observed outcome.",
      "Failures and skipped steps remain visible, and retrieved/tool content is marked untrusted and cannot grant authority."
    ],
    "outOfScope": [
      "No hidden multi-agent work, automatic retries/replay, dependency enforcement, or autonomous approval."
    ],
    "risks": [
      "A plan may omit work or overstate progress unless trace states reflect actual operations."
    ],
    "area": "P36",
    "checkpoint": "task-183-visible-chat-workflow-scaffolding",
    "validation": [
      "Completed scoped Task 183 after implementation/evidence review. Coordinator Chat displays a bounded deterministic plan and requires owner confirmation before selected retrieval, tools, or provider work. Per-turn traces record observed plan, retrieval, tool and answer outcomes, source labels, and elapsed timing; skipped steps remain skipped, failures remain failed/unknown, and failed-turn trace summaries are visible without raw provider diagnostics. Focused Python trace/tool/chat tests: 37 passed; focused chat UI tests: 24 passed. Full Python suite: 1,329 passed, 3 skipped, 0 failed; browser modules: 223 passed; Electron: 26 passed; public docs: 17 passed. No live Gemini call, live model, or representative-owner study was run."
    ],
    "limitations": [
      "The plan and trace are deterministic workflow metadata, not model-generated reasoning or proof of answer quality. Traces remain process-local and disappear after restart. No hidden agent execution, automatic retry, replay, Task creation, or additional authority is introduced. Live-provider response behavior remains unverified follow-up and is not claimed by deterministic tests."
    ],
    "automatedVerification": [
      "AI-run verification: `python -m pytest -q tests/test_chat_knowledge.py tests/test_owned_chat.py tests/test_reviewed_chat_tools.py` verifies real retrieval+tool+answer trace order and timings plus failed provider step status, sanitized failure, and no retry. `node --test tests/test_chat_ui.mjs` verifies pre-work cancellation (including a selected calculator), failed-turn trace rendering, and no resubmission."
    ],
    "followUpValidation": [
      "No live Gemini, provider timeout on a real service, or representative-owner workflow study was performed. These remain explicitly unverified follow-up; deterministic tests do not establish live-provider behavior or answer quality and no human QA sign-off is required for scoped development completion."
    ]
  },
  {
    "number": 184,
    "title": "Complete persistence for operator state",
    "description": "Persist currently in-memory positions, resource limits, proposals, and conversations with explicit migrations and a documented local data location.",
    "category": "Phase U - Persistence and Migration",
    "status": "completed",
    "dependsOn": [
      176
    ],
    "decisions": [
      "Inventory and lifecycle: positions are corporation-scoped, retain revision history, and follow the existing deactivate/remove rules; resource limits are corporation-scoped configuration, while active allocations and allocation-ID history remain process-local; Task proposals are owner-scoped, retain only a bounded review summary and replay-prevention metadata, expire under the existing 15-minute TTL, and are invalidated at startup; Employee conversations are owner-scoped and persisted only after explicit per-conversation opt-in, remain until explicit deletion, and recover read-only with uncertain pending turns never replayed.",
      "Schema version 3 adds SQLite tables for positions, resource limits, proposals, and retained Employee conversations. DDL is additive in the existing SQLite transaction; failed migrations roll back without advancing the schema version. No unencrypted sidecar backup or automatic app-data cleanup is added.",
      "Packaged Windows data location is %LOCALAPPDATA%\\ERSELMETZ AI\\projects\\ai_corporation.db because Electron starts the backend with the app-data folder as its working directory. Retained Employee chat is unencrypted; credentials, provider objects, active allocations, and retrieved proposal context are excluded.",
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Inventory each named in-memory domain record and define schema, owner scope, lifecycle, retention, and restart behavior before migration.",
      "Use versioned additive migrations with backup/rollback behavior; preserve fail-closed ownership and authorization after restart.",
      "Document the exact per-user data location and offer a safe, confirmed way to inspect and remove retained data where supported."
    ],
    "outOfScope": [
      "No cloud sync, cross-user sharing, credential persistence beyond existing policy, or automatic destructive cleanup."
    ],
    "risks": [
      "Schema migrations can lose or expose private data; persistent proposals can become stale or replayable."
    ],
    "area": "P37",
    "checkpoint": "task-184-operator-state-ai-acceptance",
    "validation": [
      "Implementation source was reviewed in checkpoint commit efed521; no new persistence architecture or schema behavior was added for this evidence checkpoint.",
      "Focused Task 184 persistence/proposal regressions: `python -m pytest -q tests/test_operator_state_persistence.py tests/test_chat_task_proposals.py` passed 10, including real separate-interpreter restart, additive schema rollback, opt-in conversation storage, owner isolation, read-only recovery, slot reset, proposal invalidation, and consumed-fingerprint replay prevention.",
      "Employee history UI regressions: `node --test tests/test_employee_chat_ui.mjs` passed 3, including retention opt-in and explicit confirmed deletion. Full Python suite: 1,321 passed / 3 skipped / 0 failed (2 warnings); browser modules 220 passed; Electron tests 26 passed; public docs 17 passed.",
      "Windows app-data inspection confirmed `%LOCALAPPDATA%\ERSELMETZ AI\projects\ai_corporation.db` exists. `Get-Acl` showed the current Windows account owns the file with FullControl; inherited CodexSandboxUsers has ReadAndExecute/Synchronize, while SYSTEM and Administrators have FullControl. A separate user profile was not used.",
      "No live model call, credential persistence, cloud sync, download, or telemetry was used. Retained Employee messages are stored only after explicit per-conversation opt-in and are not encrypted by this local SQLite database."
    ],
    "limitations": [
      "No separate clean Windows account was used; filesystem ACL and installed data-path checks cover the current account only. Cross-account access behavior remains unverified follow-up.",
      "SQLite content is local but unencrypted. Retained Employee chat requires explicit opt-in, stays until explicit deletion, and is read-only after restart. The database must be protected by the Windows profile and owner-controlled backups.",
      "Migration rollback was tested with an injected schema failure and prior schema version fixture; an upgrade against an independently preserved production database was not performed."
    ],
    "automatedVerification": [
      "Use isolated Windows app-data and real process restarts to verify retained state and unusable stale proposals. Inspect installed data location and ACLs through OS APIs. Inject migration failures, verify rollback and schema version, then exercise recovery and record evidence. Separate clean-account coverage is optional follow-up."
    ],
    "followUpValidation": [
      "Unavailable real hardware, provider-account, physical-device and representative-user coverage is recorded as unverified enhancement work; it does not require human QA sign-off for this development checkpoint."
    ]
  },
  {
    "number": 185,
    "title": "Installer, opt-in updates, and clean uninstall",
    "description": "Plan signed installation, an opt-in update check, clean uninstall choices, local-only crash reports, and an explicit reset-app-data control.",
    "category": "Phase V - Installation and Recovery",
    "status": "completed",
    "dependsOn": [
      176
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Define publisher/signing and artifact verification; update checks are disabled until owner opt-in and never download or install silently.",
      "Offer uninstall choices that explain retained user data and a separate confirmed reset-app-data operation with a recovery warning.",
      "Crash reports stay local, bounded, redacted, and inspectable; no automatic upload or hidden telemetry is added."
    ],
    "outOfScope": [
      "No silent updates/downloads, telemetry upload, remote crash reporting, or data deletion without explicit confirmation."
    ],
    "risks": [
      "Signing key loss/compromise, incomplete data removal, and diagnostic leakage can harm trust."
    ],
    "area": "P38",
    "checkpoint": "task-185-local-recovery-and-update-controls",
    "validation": [
      "Full Python suite: 1,327 passed, 5 skipped, 0 failed (2 dependency deprecation warnings).",
      "Browser-module tests: 224 passed; Electron tests: 33 passed; public documentation tests: 17 passed.",
      "Desktop UI TypeScript no-emit check, Electron and report/reset-helper syntax checks, deterministic crash-report and exact-path reset tests, and git diff --check passed.",
      "An isolated Next.js production-build attempt was not completed: the temporary dependency junction was rejected by Turbopack and webpack path resolution. Existing desktop-ui/.next and desktop-ui/out artifacts were left untouched.",
      "The full Python suite also ran three existing localhost Ollama integration tests because the local service was reachable; they were not needed for Task 185 and are not used as its feature evidence. No paid or external network call was made. Future full-suite runs will set OLLAMA_BASE_URL to an unavailable loopback port so those tests skip by default."
    ],
    "limitations": [
      "The Windows package remains Authenticode-unsigned. The publisher identity, certificate procurement, custody and public release are owner-controlled decisions; no certificate was selected or purchased.",
      "The release signature and artifact verification contracts are tested with deterministic keys, but no published signed Windows installer was available for verification.",
      "Native NSIS choice rendering, full data reset/relaunch on a clean Windows profile, and real installer/uninstaller behavior remain unverified follow-up.",
      "The Next.js production static build was not verified because the isolated build clone could not resolve the external node_modules junction; TypeScript compilation and Electron settings contract tests passed.",
      "The Python suite skips two image-processing tests because Pillow is not installed and three symlink-security tests because Windows reports WinError 1314; their behavior is not established by this run."
    ],
    "automatedVerification": [
      "AI-run verification: Confirm no release request occurs on page load and one check requires an explicit click; verify release signature before preview and separate explicit prepare confirmation.",
      "Verify the NSIS uninstall prompt defaults to keeping data and its separate delete choice targets only the fixed per-user ERSELMETZ AI data folder.",
      "Verify bounded local diagnostics whitelist only event metadata, omit raw errors/secrets/paths, and are readable only through trusted app UI with system:read.",
      "Verify full reset requires backup:restore, defaults native confirmation to Cancel, stops the backend, removes only the fixed app-data directory after parent exit, then relaunches into first-run."
    ],
    "followUpValidation": [
      "Real Authenticode signing and publisher identity, public signed artifact verification, NSIS UI behavior, and destructive reset/restart on a clean Windows profile remain unverified; their impact is release readiness and actual Windows shell behavior, not the deterministic contracts tested here.",
      "Unavailable real hardware, provider-account, physical-device and representative-user coverage is recorded as unverified enhancement work; it does not require human QA sign-off for this development checkpoint."
    ]
  },
  {
    "number": 186,
    "title": "3D globe visual map",
    "description": "Render permission-filtered recorded entities and source-backed relationships in a bounded, accessible 3D organizational globe.",
    "category": "Phase W - Interactive 3D Map",
    "status": "completed",
    "dependsOn": [
      177
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Render only permission-filtered recorded nodes, edges, status, and timestamps; unknown/missing telemetry is shown as unknown and never animated as activity.",
      "Cap nodes, frame rate, pixel ratio, and rendering work; expose measured resource cost and fall back to the existing usable 2D view on WebGL failure or reduced motion.",
      "Provide a keyboard-accessible labeled list with equivalent records and relationships; the visualization is read-only and has no execution authority."
    ],
    "outOfScope": [
      "No fabricated nodes/relationships, fake activity pulses, hidden polling, task execution controls, or removal of the 2D/list fallback."
    ],
    "risks": [
      "3D rendering can burden local inference and can make provenance or accessibility harder to inspect."
    ],
    "area": "P39",
    "checkpoint": "task-186-globe-visual-map",
    "validation": [
      "Visualization model/scene regressions: 18 passed; protected page tests: 2 passed (1 Starlette deprecation warning).",
      "Full Python suite: 1,324 passed, 8 skipped, 0 failed (2 dependency deprecation warnings); OLLAMA_BASE_URL was pointed at an unavailable loopback port so no live model inference ran.",
      "Browser-module tests: 227 passed; Electron tests: 33 passed; public documentation tests: 17 passed.",
      "git diff --check and Python/JavaScript syntax and import checks passed."
    ],
    "limitations": [
      "Globe positions are a stable visual layout, not geographic coordinates or measured organizational distances. Relationships alone come from recorded source links.",
      "No actual WebGL device render or minimum-hardware/inference-load benchmark was performed; deterministic tests use the vendored Three.js geometry with a fake WebGL renderer.",
      "The accessible fallback is the labeled record-and-relationship list; no separate 2D graph renderer was added. Source snapshots remain independent on-demand reads, not a live event stream."
    ],
    "automatedVerification": [
      "Verify deterministic ID-stable spherical placement, recorded-only links, the 60-node/119-edge caps, pixel ratio 1, 30 FPS maximum rendering, no continuous frame loop, and no activity pulse into or out of unknown telemetry.",
      "Verify WebGL failure and reduced motion use the keyboard-accessible labeled list with equivalent current records and recorded relationships."
    ],
    "followUpValidation": [
      "Actual GPU/browser WebGL rendering under concurrent local inference, minimum-device performance, physical assistive-technology coverage, and representative-user evaluation remain unverified follow-up; no rendered-device performance or accessibility conformance claim is made."
    ]
  },
  {
    "number": 187,
    "title": "Opt-in local voice input",
    "description": "Add optional local speech-to-text input with a visible microphone indicator and explicit capture controls.",
    "category": "Phase X - Voice Interaction",
    "status": "completed",
    "dependsOn": [
      184
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Voice input is disabled by default and uses only an explicitly configured local speech recognition provider unless a later consent contract permits otherwise.",
      "Show an always-visible microphone/capture state, duration limit, permission state, and stop/cancel control while recording or transcribing.",
      "Do not submit recognized text until the owner reviews and explicitly sends it; failures remain bounded and visible."
    ],
    "outOfScope": [
      "No always-on listening, background capture, default cloud transcription, or silent model download."
    ],
    "risks": [
      "Speech can include sensitive bystander information and local recognition may be inaccurate."
    ],
    "area": "P40",
    "checkpoint": "task-187-opt-in-local-voice-input",
    "validation": [
      "The shared owner safety panel now exposes voice phase, permission state, a live capture duration capped at 10 seconds, and a direct stop/cancel control even while the detailed voice settings are collapsed. Browser microphone permission is reported as pending until recognition starts; denied and failed states remain distinct.",
      "Existing local recognition requires processLocally=true, local model use requires explicit selection, and neither falls back to cloud. Transcript content remains an editable chat draft until the owner explicitly sends it. Existing Gemini transcription still requires separate per-recording consent and an app-run budget; no provider request was made for this checkpoint.",
      "Full validation: Python 1,324 passed / 8 skipped / 0 failed (2 deprecation warnings); browser modules 229 passed / 0 failed; Electron 33 passed / 0 failed; public docs 17 passed / 0 failed. Focused voice/emergency-stop browser tests: 17 passed; Python route/page tests: 3 passed. Python compilation, JavaScript syntax, and git diff --check passed."
    ],
    "limitations": [
      "Physical microphone/OS permission prompts, local recognition while offline, device audio quality and language accuracy remain unverified on target Windows/browser hardware."
    ],
    "automatedVerification": [
      "AI-run verification: deterministic browser fakes cover permission pending/granted/denied, capture elapsed time and 10-second bound, stop/cancel, transcript review before send, and local-mode absence of transcription network calls."
    ],
    "followUpValidation": [
      "Physical Windows/browser microphone prompt and permission-reset behavior, local-recognition quality while actually offline, device-specific hardware/audio compatibility, and representative-owner workflow remain unverified follow-up. Fakes validate the UI contract only and do not prove real OS/provider integration."
    ]
  },
  {
    "number": 188,
    "title": "Opt-in voice output",
    "description": "Add optional text-to-speech playback for assistant responses with a clear stop control.",
    "category": "Phase X - Voice Interaction",
    "status": "completed",
    "dependsOn": [
      187
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Voice output is disabled by default and uses an explicitly selected device-local voice/provider.",
      "Show playback state and provide a stop button that halts local playback promptly and clears queued speech.",
      "Do not transmit response text to an online voice service without separate explicit per-use consent."
    ],
    "outOfScope": [
      "No always-on playback, silent downloads, cloud TTS by default, or claims of universal voice quality."
    ],
    "risks": [
      "Spoken responses can expose private content to nearby people; queued speech may outlive view changes."
    ],
    "area": "P40",
    "checkpoint": "task-188-opt-in-local-voice-output",
    "validation": [
      "Speech remains silent until the owner explicitly selects a local device voice and requests playback for a reply. Only voices marked localService are accepted; the adapter has no online provider or fallback. A saved voice selection is restored only when the same local voice is currently available, and restoration does not start speech.",
      "The shared capability panel reports local playback and exposes Stop/clear-queue while the detailed controls are collapsed. Stop cancels the current utterance and clears queued text; bounded queue limits remain in force. Full validation: Python 1,324 passed / 8 skipped / 0 failed (2 deprecation warnings); browser modules 230 passed / 0 failed; Electron 33 passed / 0 failed; public docs 17 passed / 0 failed. Focused voice/output/capability tests: 23 passed; Python route/page tests: 3 passed. Python compilation, JavaScript syntax, and git diff --check passed."
    ],
    "limitations": [
      "Physical speakers/headphones, system voice installation, offline playback on representative Windows/browser configurations, voice-language quality, and acoustic privacy in the owner's environment were not tested."
    ],
    "automatedVerification": [
      "AI-run verification: deterministic fakes verify no playback by default, local-only voice filtering, explicit voice selection, saved local voice restoration only when present, active/inactive status, shared Stop/clear-queue behavior, and no network or online fallback."
    ],
    "followUpValidation": [
      "Real device voice availability, restart on a separately installed profile, offline operation on target devices, speaker/headphone leakage risk, language quality, and representative-owner usability remain unverified follow-up. Fakes do not prove physical audio behavior."
    ]
  },
  {
    "number": 189,
    "title": "Opt-in local vision input",
    "description": "Support image input through a local multimodal model with a clear preview showing what is sent and to which provider.",
    "category": "Phase Y - Local Vision",
    "status": "completed",
    "dependsOn": [
      180,
      181
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed.",
      "Use the conversation's explicitly configured provider/model for image turns. Ollama vision support is checked from its bounded /api/show capabilities metadata; unsupported or unknown capability fails closed without fallback. A configured cloud provider needs the existing image-specific consent and separate per-turn cloud consent. Task 181 alternate routes remain text-only; Task 180 hardware/profile evidence does not establish image capability or performance."
    ],
    "acceptance": [
      "Require explicit per-image selection and per-turn consent; preview image, selected local provider/model, size, and any preprocessing before send.",
      "Use the hardware/profile and consent-based routing contracts; local transfer is the default and any cloud transfer requires distinct explicit confirmation.",
      "Keep image retention bounded and visible, expose the actual provider/model and outcome in the trace, and report unsupported vision models without fallback."
    ],
    "outOfScope": [
      "No continuous camera/screen capture, automatic image upload, silent preprocessing, or inference of model capability from its name."
    ],
    "risks": [
      "Images can contain sensitive data; provider choice, retention, and model capability may be unclear."
    ],
    "area": "P41",
    "checkpoint": "task-189-opt-in-local-vision-input",
    "validation": [
      "Added an owner-scoped no-store image preview and transfer summary showing the exact configured provider/model, local or online destination, MIME type, dimensions, original byte size, expiry, and whether local OCR is selected. The original image is sent unchanged; no crop, resize, redaction, or other preprocessing is performed.",
      "Each image remains unselected until explicitly selected and requires per-turn image consent. Cloud image transfer also requires the separate existing Gemini cloud-consent checkbox. Ollama capability is read on demand from model-reported /api/show capabilities; unsupported or unknown vision support is blocked before image transfer, with no model-name inference or fallback.",
      "Successful and failed image turns record actual provider/model, local/online destination, outcome, image count, and retention in the existing How I answered trace. Selected attachments remain bounded in process memory and are discarded after one provider attempt; previews are owner-scoped and sent with no-store headers.",
      "Focused Task 189 and affected regressions: Python 57 passed; browser image/chat/vision modules: 26 passed. Full validation: Python 1,328 passed / 8 skipped / 0 failed (2 deprecation warnings); browser modules 231 passed / 0 failed; Electron 33 passed / 0 failed; public docs 17 passed / 0 failed. Python compilation, JavaScript syntax, and git diff --check passed."
    ],
    "limitations": [
      "No live Ollama model, Gemini account/model, or provider transfer was exercised. Deterministic fakes validate API contracts only and do not prove real model vision quality, compatibility, speed, hardware fit, or provider retention. Gemini capability is declared by its existing adapter; a per-model vision capability catalog is unavailable, so unsupported-model rejection is reported without fallback when the provider responds.",
      "Image turns use the configured conversation provider/model only; Task 181 alternate routing remains text-only. There is no automatic local-model discovery/selection, model download, or image transformation. Hardware profile guidance is not evidence of model-specific vision support.",
      "Reproducible follow-up issue: select an alternate route under Task 181, attach/select an image, then send; the API rejects the combination with HTTP 422 because image turns use only the configured coordinator. This is explicit current behavior, not a fallback. A future image-route task should reuse route consent and per-model vision evidence before enabling alternate image destinations.",
      "No real Windows/browser image preview, screen-reader review, clean-account session, or representative-user evaluation was performed."
    ],
    "automatedVerification": [
      "AI-run verification: deterministic API/provider and browser UI tests cover owner-scoped no-store previews, local/online destination disclosure, exact MIME/dimensions/size, local OCR disclosure, explicit selection and consent, separate cloud consent, expiry/one-attempt retention, successful and failed vision traces, unsupported and unknown model capability, and no-transfer/no-fallback behavior."
    ],
    "followUpValidation": [
      "Live loopback Ollama /api/show and actual multimodal inference, cloud Gemini account behavior and retention, representative GPU/CPU hardware cost, real browser preview/accessibility, clean-profile owner permissions, and representative-user comprehension remain unverified enhancement work; fake checks establish contracts only."
    ]
  },
  {
    "number": 190,
    "title": "Code-execution agent threat model and design",
    "description": "Design an Open Interpreter-style code-execution capability under a reviewed threat model before any implementation is considered.",
    "category": "Phase Z - Code Execution Design Gate",
    "status": "design_only",
    "dependsOn": [
      182
    ],
    "decisions": [
      "Owner-directed workflow revision (2026-10-18): use the roadmap AI-run development acceptance policy; routine testing, debugging and review require no human QA sign-off. Historical validation below is evidence only for the checks actually performed."
    ],
    "acceptance": [
      "Publish a threat model and design covering OS sandboxing, per-action owner confirmation bound to exact inputs, explicit filesystem scope, network policy, secret isolation, audit evidence, and a reliable kill switch.",
      "Run an AI security design review covering sandbox escape, prompt injection, resource exhaustion, exfiltration, cancellation, crash recovery and safe failure; record unresolved risks and proposed mitigations.",
      "Complete only the design deliverable after recorded AI review; Task 190 stays design-only and any runtime implementation requires a separately authorized task."
    ],
    "outOfScope": [
      "No code execution, shell/tool adapter, package installation, filesystem write, process spawn, autonomous approval, or runtime permission."
    ],
    "risks": [
      "Execution can compromise all data and processes available to the host if isolation or confirmation fails."
    ],
    "area": "P42",
    "checkpoint": "task-190-code-execution-threat-model",
    "validation": [
      "Inspected app/integrations/sandbox_executor.py, docker_sandbox.py, sandbox.py, app/application/services/maintenance_sandbox.py, and app/api/maintenance_experiments.py. The generic executor blocks; the optional Docker path is Linux maintenance-test-only and does not establish a Windows general-purpose code-execution boundary.",
      "Published docs/design/task-190-code-execution-threat-model.md with exact-action consent, Windows isolation prerequisites, filesystem/network/secret boundaries, resource limits, audit, kill/cancellation, crash recovery, and safe-result handling.",
      "Recorded adversarial self-review by Codex GPT-6 on 2026-10-18; it is not independent review, penetration testing, or implementation evidence. Public docs tests: 18 passed; git diff --check passed."
    ],
    "limitations": [
      "Design only. This checkpoint grants no execution authority; runtime implementation needs a separate owner-authorized roadmap task.",
      "Security review was an author self-review only; no independent model, Windows native implementation, penetration test, or red-team validation was performed.",
      "Supported Windows editions, virtualization availability, sandbox policy enforcement, kill behavior under host/app crashes, and resource quotas remain unverified implementation risks."
    ],
    "automatedVerification": [
      "Review the proposed target-OS isolation, kill switch and filesystem/network boundaries against explicit adversarial scenarios. Record design evidence and unknowns; no execution capability is implemented or approved by this review."
    ],
    "followUpValidation": [
      "Before implementation, obtain an independent security review and verify the isolation backend, policy, kill behavior, path handling, crash recovery, Windows edition support, and quotas on supported Windows builds."
    ]
  },
  {
    "number": 191,
    "title": "Direct-to-chat local quick start",
    "description": "Start the protected Electron backend and open Coordinator Chat directly, automatically configuring only installed local Ollama resources without a first-run wizard or silent download.",
    "category": "Phase AA - Direct-to-chat Quick Start",
    "status": "completed",
    "dependsOn": [176, 68, 72],
    "decisions": [
      "Task 191 supersedes Task 176's wizard-first provider setup where they conflict. Existing owner-password credentials remain required at launch; new installations use a random per-launch Electron session token and can enable a DPAPI-protected password lock in Settings.",
      "Prefer installed llama3.2:3b; otherwise inspect bounded Ollama tags/show metadata and choose the smallest installed completion-capable model. Keep a saved model choice stable across restarts; never download or install automatically. Persist one-slot Ollama resource limits and defer manager construction until controlled execution needs it."
    ],
    "acceptance": [
      "Electron starts the backend on loopback and opens Coordinator Chat directly; a new installation creates or resumes a coordinator conversation automatically.",
      "Passwordless startup is limited to a random per-launch Electron session token held by Electron and the backend; loopback, Origin, CSRF and default-deny authentication remain enforced. Existing DPAPI password lock is still checked at launch and can be enabled or disabled explicitly in Settings.",
      "Startup discovers only installed local Ollama models, chooses the preferred/default chat model truthfully, persists selection and software slot limits idempotently, and never changes provider/model assignments for optional Gemini use or performs silent downloads.",
      "Chat surfaces stopped/not-installed/no-model states with one guarded action, routes installation through the existing verified installer and model download through the existing size/digest confirmation and progress flow, and labels CPU performance/hardware fit as unmeasured.",
      "Plain local Coordinator chat can be sent without setup or a redundant planning dialog. Cloud turns, reviewed tools, knowledge retrieval, task proposals/dispatch, and other sensitive actions keep their existing consent and confirmation controls."
    ],
    "outOfScope": [
      "No silent Ollama install/model download, Gemini key prompt or cloud fallback, provider auto-routing, hardware readiness claim, background task dispatch, secret logging, remote access, or authorization bypass.",
      "Task 176's legacy first-run component remains available as historical code but is no longer the Electron launch flow."
    ],
    "risks": [
      "Windows Ollama install paths vary; the installation presence check recognizes standard per-user and Program Files locations and may report an alternate custom location as not installed.",
      "The per-launch token is held in Electron main process memory and passed to its child backend over the private parent pipe. Local malware running as the same Windows user remains outside this app's isolation boundary."
    ],
    "area": "P43",
    "checkpoint": "task-191-direct-to-chat",
    "validation": ["Full Python suite: 1,334 passed / 8 skipped / 0 failed (2 warnings; Ollama pointed to a closed loopback test port). Focused Task 191 Python regressions: 53 passed; targeted chat/quick-start browser tests: 28 passed; full browser-module suite: 235 passed; Electron tests: 34 passed; public-docs tests: 18 passed. Next.js static build and TypeScript checks passed; Python compilation/import checks and git diff --check passed."],
    "realWorldVerification": {
      "status": "partial",
      "evidence": ["A real local llama3.2:3b request through Ollama returned the requested reply in 5.417 s; Ollama reported the model at 100% GPU on the RX 570."],
      "unverified": ["The installed packaged Electron artifact predates Task 191. The current Electron launch, packaged app navigation to chat, and first reply in the packaged app were not verified.", "Clean-profile installation, restart persistence, password-lock behavior, and recovery remain unverified in this run."]
    },
    "limitations": [
      "Manual clean-Windows-profile acceptance remains pending: real Ollama absent/stopped/install/model download and chat, Gemini key/cloud-consent chat, restart persistence with and without DPAPI lock, recovery after offline/bad credentials, and physical CPU/GPU inference speed were not performed.",
      "Deterministic fakes validate routing, session and UI contracts only; they do not prove Ollama installation/service behavior, model quality, or live provider availability."
    ],
    "automatedVerification": [
      "Use deterministic local-provider fakes to verify preferred-model selection, smallest chat-capable fallback, missing service/model states, idempotent persisted assignments and slots, token rejection/injection, password-lock transitions, direct chat creation and a successful fake local turn.",
      "Verify the existing verified installer and exact manifest/digest-confirmed download are invoked only by explicit owner action, with bounded visible progress and no automatic retry or cloud routing."
    ],
    "followUpValidation": [
      "Manual clean-profile Windows install/start/chat/restart, real Ollama service and model metadata/download/recovery, DPAPI lock restart, Gemini account consent behavior, alternate Ollama install locations, hardware latency and representative-user comprehension remain unverified follow-up."
    ]
  },
  {
    "number": 192,
    "title": "Real-world verification and enhancement pass",
    "description": "Measure the real local Ollama, RAG, reviewed-tool, vision, voice, globe, and hardware journeys on the current Windows host, then make narrowly scoped, evidence-led enhancements.",
    "category": "Phase AB - Real-world Verification",
    "status": "completed",
    "dependsOn": [191, 177, 180, 182, 186, 187, 188, 189],
    "acceptance": [
      "Record actual outcomes, model/provider identity, latency, errors, and provenance for Task 191 packaged direct-to-chat; three explicitly selected knowledge notes and five RAG questions; read-only arithmetic and documentation lookup with a real local model; and a local vision turn using an already installed vision-capable Ollama model. Do not make paid/cloud calls or download a model without explicit owner confirmation.",
      "Record voice checks that are possible without a physical microphone and mark unavailable physical-device checks UNVERIFIED. Measure the existing capped 3D map on the installed RX 570 while a local model generates, verify the accessible list fallback, and compare reported hardware with OS inventory and Ollama's actual processor report.",
      "Add an optional loopback-only Ollama embedding adapter that never pulls models itself; an embedding model pull requires explicit owner confirmation, no new heavy Python dependency, and lexical fallback remains available. Evaluate the Task 135 fixture with real embeddings and report Recall@5/MRR separately from deterministic fake-embedding results.",
      "Evaluate concise prompts and retrieved-context formatting for the installed 3B model with a fixed 10-question with/without-retrieval set. Report each outcome honestly and do not claim quality improvement without measured evidence.",
      "Fix only reproducible defects discovered during this pass, each as a narrow change with focused regression coverage. Preserve explicit consent, loopback-only access, no silent downloads, no secret logging, and truthful telemetry.",
      "Keep automated deterministic/fake evidence separate from real hardware and live local-provider evidence in each task badge, changelog, and Task 192 record. Do not raise existing task statuses based solely on these checks."
    ],
    "outOfScope": [
      "No paid/cloud calls, account changes, deployment, push, silent model/software downloads, GPU/hardware compatibility claims, fake telemetry, permission bypass, or automatic fallback.",
      "Do not mark physical microphone, clean-profile, live-provider, or representative-user checks verified unless those exact checks were performed on this host."
    ],
    "risks": [
      "The installed vision model is large relative to host RAM and may be too slow or fail under current memory/accelerator limits; stop safely on resource exhaustion and report the outcome.",
      "Single-host measurements do not establish general hardware support, model quality, or performance on other systems."
    ],
    "area": "P44",
    "checkpoint": "task-192-small-model-answer-quality",
    "decisions": [],
    "validation": ["Task 192 answer-quality checkpoint: full Python suite 1,344 passed / 3 skipped / 0 failed (2 dependency deprecation warnings); browser-module suite 235 passed / 0 failed; Electron suite 34 passed / 0 failed; public-docs suite 21 passed / 0 failed. Focused Ollama/chat/RAG regressions: 50 passed. Deterministic tests cover separate system prompt routing and unchanged raw prompts. Real local model evaluations and limitations are recorded in realWorldVerification. git diff --check and Python compilation passed."],
    "realWorldVerification": {
      "status": "partial",
      "evidence": ["Real local Ollama llama3.2:3b chat: requested 'hello' response returned in 5.417 s; model load 5.115 s; Ollama reported 100% GPU.", "Real local RAG over three temporary notes: Q1 Atlas port 8123 correct, 3.838 s, trace listed all three notes; Q2 Atlas maintenance Tuesday 14:30 correct, 3.887 s, trace listed all three; Q3 Cedar path D:\\Work\\Cedar was formatted incorrectly in the answer, 3.237 s, trace listed only Cedar; Q4 Cedar QA lead correct, 4.207 s, trace listed all three; Q5 rollback command 'revert deploy 42' correct, 4.526 s, trace listed all three. The intended source was present in all five traces; strict factual answers were 4/5 and four traces were overinclusive.", "Real local reviewed tools completed in 13.834 s: calculator returned 731 for (43 * 17), and exact read-only documentation lookup returned source corporation_docs:api-and-web-ui-boundaries. No Tasks were created and no cloud route was used. The answer was verbose and described the selected document structure rather than giving a concise response. An initial test-harness lookup used a nonexistent .md-suffixed ID and got the expected safe unavailable result; retry with the exact ID succeeded.", "Ollama inventory: gemma4:26b (18 GB reported, local, vision capability); llama3.2:3b (2.0 GB, local, no vision capability); cloud references gemma4:31b-cloud and glm-5.3-flash:cloud are not local models and were not called. Hardware: AMD Ryzen 5 PRO 4650G (6 cores/12 logical), Radeon RX 570 Series (reported 4 GB), 15.8 GB total RAM and 5.4 GiB available at inspection; C: has 42.6 GiB free. Ollama reported 100% GPU for llama3.2:3b.", "After explicit owner approval, pulled nomic-embed-text locally with Ollama: 274 MB, 768-dimensional nomic-bert, model ID 0a109f422b47; no Python package or cloud service was added. Real embedding endpoint returned four vectors in 3.399 s on first measured batch. On Task 135's three semantic fixture queries, real-model query latency was 60.8 to 65.5 ms (mean 63.4 ms); Recall@5 1.00, MRR 1.00, Precision@5 0.50, with no excluded-record leakage and stale candidates rejected. The fixture's deterministic fake baseline reports Recall@5 1.00, MRR 1.00, Precision@5 1.00. These small synthetic-fixture results do not establish general retrieval quality.", "Real local llama3.2:3b ten-question comparison sent the concise Coordinator instruction through Ollama separate system field. Without retrieval, it returned 0/10 fixture values and abstained on all 10; mean latency 929 ms. With one selected note per question, it returned all 10 expected facts exactly and included [1] in all 10 answers; mean latency 1,187 ms. The Windows path used one backslash in this run. This is a single default-sampling run, not a general model-quality guarantee."],
      "unverified": ["Packaged Task 191 direct-to-chat flow: existing installed package predates Task 191, and native/browser UI automation was unavailable.", "Vision end-to-end: gemma4:26b is the only installed local model reporting vision, but at 18.6 GB it is larger than system RAM; no load/image request was attempted. No vision model was downloaded.", "Voice input/output without a physical microphone/audio session; live 3D globe FPS/frame-time under inference and interactive list fallback; CPU-only hardware behavior."]
    },
    "automatedVerification": [
      "Use the full Python, browser-module, Electron, and public-docs suites before each implementation checkpoint. Use deterministic fixtures/fakes for contract tests and report their counts separately from live local-model runs.",
      "Test that the public docs render latest completed and next planned task from docs/tasks-data.mjs, all tasks have separate automated and real-world evidence badges, UTF-8 metadata/headers are present, and no known mojibake sequences occur in public docs or the update manifest."
    ],
    "followUpValidation": [
      "Clean-profile Windows/Gemini/DPAPI, physical microphone and audio-device behavior, representative-user usability, cross-hardware performance, paid-provider behavior, and any model not already installed remain unverified unless directly tested; no such test is inferred from deterministic fixtures."
    ],
    "limitations": [
      "Task 192 is a scoped local development checkpoint. Real-model RAG, tools, and answer-quality checks are single-host observations, not general answer-quality or compatibility claims.",
      "Real Task 135 embedding metrics are from a three-query synthetic fixture and include false-positive candidates (Precision@5 0.50); they do not show production corpus quality. nomic-embed-text was pulled only after explicit owner approval. The runtime does not pull models, and Ollama embedding use remains optional and explicitly configured.",
      "Packaged Electron chat, vision image flow, physical voice, globe performance, and CPU-only hardware behavior remain unverified as listed in realWorldVerification.unverified."
    ]
  },
  {
    "number": 193,
    "title": "Structured chat prompts and focused desktop chat experience",
    "description": "Send native role-based chat messages to local and Gemini providers and make the served Coordinator Chat the focused, accessible desktop conversation surface.",
    "category": "Phase AC - Structured Chat and Desktop Experience",
    "status": "deferred",
    "dependsOn": [177, 178, 191, 192],
    "decisions": [],
    "acceptance": [
      "Build Ollama chat requests from a short system message, completed user/assistant history, optional untrusted retrieved/tool/OCR excerpts, and the current user text. Never place corporation identity, request envelopes, empty context/history, or presentation preference objects in provider prompts.",
      "Use the same structured roles through the Gemini adapter. Add short preference hints only for changed owner settings; exclude empty retrieved-context blocks.",
      "Use a centered readable conversation column, right-aligned user bubbles, plain assistant text, sticky multiline composer, Enter-to-send/Shift+Enter newline, Stop while waiting, Markdown with inert HTML, collapsed trace, and closed-by-default advanced controls.",
      "Keep the accessible responsive conversation sidebar, model picker, direct-to-chat first-run, explicit cloud/tool/image/voice consent, safe error states, and existing Task 178 narrow-window navigation behavior."
    ],
    "outOfScope": [
      "No new Next.js chat route where the desktop application currently serves the Python Coordinator Chat route; no provider/model auto-selection changes, authority changes, silent downloads, cloud fallback, or consent changes."
    ],
    "risks": [
      "Existing prompt-observer/debug display serializes only the structured messages for explicit local inspection; it must not become the provider request body or include private service envelopes.",
      "Markdown rendering must remain text-node based and must not execute provider-supplied HTML or scripts."
    ],
    "area": "P45",
    "checkpoint": null,
    "decisions": [],
    "validation": [
      "Full automated validation: Python 1,351 passed / 3 skipped / 0 failed (2 deprecation warnings); browser modules 239 passed / 0 failed; Electron 34 passed / 0 failed; public docs 21 passed / 0 failed; desktop-ui TypeScript no-emit passed. Python compilation and git diff --check passed. A Next.js production build and packaged Electron launch were not run; the desktop chat route is Python-served."
    ],
    "realWorldVerification": {
      "status": "partial",
      "evidence": [
        "Before the fix, a real loopback Ollama llama3.2:3b request for 'hello' returned: 'You want a concise answer unless more detail is requested. The conversation context and retrieved context are not trusted data. Is there something specific you'd like to know?'",
        "After the fix, real local llama3.2:3b Coordinator replies were: hello -> 'Hi!' (7.876 s); 'who are you?' -> 'I'm ERSELMETZ AI, your assistant. I'm here to help you with any questions or information you need.' (3.009 s); 'ano ang kaya mong gawin?' -> 'Mumagagawa ako ng mga tanong, magbigay ng impormasyon, at magpapakataon sa mga problema at mga kwestyon sa iyo.' (3.418 s). A two-turn remember/recall check answered 42 on the follow-up (2.401 s then 2.249 s). Final-code rerun through the real chat service: 'hello' -> 'Hi, how can I assist you today?' (2.450 s) using an isolated temporary database.",
        "In the local loopback app, 'hello' rendered as 'Hello! How can I assist you today?'; a code request rendered one fenced code block with its copy control. A generated 2,868-byte answer produced a 2,038-pixel document in a 600-pixel viewport; the Stop action aborted the app's wait without retrying the remote request."
      ],
      "unverified": [
        "The installed packaged Electron binary was not rebuilt/launched for this task; browser tests exercised the actual Python /ui/chat route that Electron currently opens. A separate Next.js chat page does not exist.",
        "Gemini used deterministic adapter tests only; no live account/provider call was made. Native accessibility/screen-reader use, other Windows display scaling, and broader model answer quality remain unverified."
      ]
    },
    "limitations": [
      "Filipino response quality is imperfect in the single captured capability question; this is a prompt-assembly and UI checkpoint, not a language-quality guarantee.",
      "The original checkpoint task-193-chat-prompt-and-ui was overstated: the installed app was an older package without a source stamp, and individual Employee chat still serialized a JSON request envelope into the legacy prompt path. Task 193 remains deferred until corrected by Task 194.",
      "Real local-model results are observations from this host and model. Deterministic provider, Python, browser, and Electron checks do not prove live Gemini or representative-user behavior."
    ],
    "automatedVerification": [
      "Use deterministic tests to verify providers receive structured role messages, internal envelope keys never enter messages, empty context adds no reference block, and selected retrieval is an explicitly delimited untrusted excerpt.",
      "Verify safe Markdown rendering, composer keyboard and Stop behavior, collapsed answer trace, closed-by-default options, responsive navigation, and direct-to-chat first send. Run full Python, browser-module, Electron, public-docs, and desktop-ui TypeScript checks."
    ],
    "followUpValidation": [
      "Task 194 corrects the incomplete provider-routing and package-identity acceptance. Exercise live Gemini only with separately authorized account use; evaluate screen reader/keyboard access and language quality with representative users."
    ]
  },
  {
    "number": 194,
    "title": "Correct chat prompt routing and prove the running desktop build",
    "description": "Remove request-envelope serialization from every chat entry point and identify the exact packaged backend commit before Electron accepts it.",
    "category": "Phase AD - Chat Prompt Correctness",
    "status": "deferred",
    "dependsOn": [193, 191],
    "acceptance": [
      "Coordinator, direct-to-chat, streaming, non-streaming, retrieval, image-capable structured chat, Gemini, and individual Employee chat send role-based messages only; provider adapters reject mappings before provider invocation.",
      "A local fake Ollama HTTP server captures the exact request body through authenticated real API routes and verifies system/user/assistant roles, no internal request-envelope fields, empty context omission, streaming parity, prior history, and only selected retrieval excerpts.",
      "The app health response reports version and source commit. Electron requires a matching packaged backend identity and opens Coordinator Chat with the existing loopback, per-launch session, Origin and CSRF controls intact.",
      "A locally rebuilt packaged Electron application must stay running from an isolated profile and port, report its version/commit stamp, and reach real local llama3.2:3b for the four requested prompt turns. No network provider, cloud call, push, or deployment is used."
    ],
    "outOfScope": [
      "No changes to authentication policy, provider/model selection, permissions, task authority, cloud consent, spending, automatic fallback, downloads, or deployment.",
      "No claim that deterministic fake-provider responses establish real provider quality or that this host establishes broader Windows/hardware compatibility."
    ],
    "risks": [
      "All new or legacy chat entry points must preserve conversation history, retrieval provenance, explicit cloud consent, and assigned provider/model identity while excluding service-only request fields.",
      "Version/commit identity must fail closed for a packaged backend with a missing or mismatched build stamp."
    ],
    "area": "P46",
    "checkpoint": null,
    "decisions": [],
    "validation": [
      "Authenticated route-to-fake-Ollama captures cover Coordinator non-streaming with prior history, Coordinator streaming, selected retrieval, and individual Employee non-streaming and streaming; all actual outbound bodies are checked for the forbidden envelope keys.",
      "Orchestrator rejects mapping envelopes before dispatch in regular, temporary-route, streaming, and image-chat paths; the app startup debug self-check also exercises this boundary.",
      "Full validation: Python 1,359 passed / 5 skipped / 0 failed; browser modules 239 passed / 0 failed; Electron 38 passed / 0 failed; public docs 21 passed / 0 failed; desktop UI TypeScript no-emit and Python compileall passed. Route-to-fake-Ollama capture for 'hello' was POST /api/chat with model llama3.2:3b, a four-line system message, one user message 'hello', and stream false; exact body contains no request-envelope fields. Version/commit health contract and packaged Electron build-stamp handshake are covered by deterministic tests. Isolated backend and Windows installer builds succeeded. The isolated packaged app launch exited with code 0 before opening a window or binding its backend port; the runtime reason is unresolved, so packaged identity and live local-model behavior were not verified. Existing release/build outputs were preserved."
    ],
    "realWorldVerification": {
      "status": "pending",
      "evidence": [
        "2026-10-20: A current-worktree unsigned Windows installer and unpacked package were produced in desktop/release-task194-review. The app process exited immediately with exit code 0; no app window, app-data directory, or backend listener on the isolated port appeared. No real local-model reply or running health stamp was captured. The embedded build-stamp.json identifies base HEAD 56b7d94, not the uncommitted Task 194 source tree, so it cannot prove which Task 194 source is running."
      ],
      "unverified": [
        "Launch the isolated packaged app successfully, verify the visible/running version and commit stamp, then capture actual llama3.2:3b replies and latencies for the requested four turns."
      ]
    },
    "limitations": [
      "Live Gemini is not called. Fake-server route captures validate only the outbound contract and do not prove third-party service behavior.",
      "The current packaged app exits before window/backend startup with exit code 0, so this checkpoint remains deferred despite the source-level route captures and successful build. The packaging script stamps Git HEAD and does not fingerprint dirty source changes; the built artifact's embedded 56b7d94 identity therefore does not identify the uncommitted Task 194 tree. No runtime failure cause is claimed. Other Windows profiles, GPU/CPU configurations, accessibility devices, and representative user behavior are not inferred."
    ],
    "automatedVerification": [
      "Use an ephemeral loopback HTTP capture server and the authenticated real chat route, not a direct service-only mock. Verify exact request body paths and payload fields for every applicable chat mode.",
      "Run full Python, browser-module, Electron and public-docs suites; Python compilation, desktop UI type check, build identity handshake, local isolated packaged launch, and git diff --check."
    ],
    "followUpValidation": [
      "Diagnose why the isolated packaged Windows app exits before Electron startup, then verify its build stamp and the four real local llama3.2:3b turns. Exercise Gemini only with an authorized test account; assess representative-user experience, native accessibility and additional Windows hardware separately."
    ]
  },
  {
    "number": 195,
    "title": "Minimal direct-to-chat experience",
    "description": "Make the actual Electron-served Python Coordinator Chat the focused conversation surface, keeping advanced operator controls grouped under Advanced and Settings.",
    "category": "Phase AE - Minimal Chat Experience",
    "status": "completed",
    "dependsOn": [178, 191, 193, 194],
    "acceptance": [
      "Electron's actual chat route is identified and redesigned: centered greeting, three prompt suggestions, one rounded multiline composer, compact model selector, one-use plus menu, accessible conversation sidebar, safe Markdown, and collapsed per-reply trace.",
      "Capability cards, permission lists, global navigation injection, and secondary sidebar controls do not clutter /ui/chat; the detailed capability and privacy panel stays reachable from Settings, and existing controls remain available through progressive disclosure.",
      "The composer supports Enter to send, Shift+Enter for newline, auto-grow, visible Stop while generating, narrow-window navigation, reduced motion, visible keyboard focus, and an emergency-stop control only during reported protected activity.",
      "Local Ollama, Gemini consent, selected knowledge, image/camera/screen capture, voice, install and download actions retain their existing permissions, per-use consent, no-secret, and no-silent-download boundaries."
    ],
    "outOfScope": [
      "No provider/model routing, permission grants, cloud consent policy, safety authority, download behavior, backend prompt construction, data retention policy, Next.js application rewrite, push, or deployment change.",
      "No inference that source-mode Electron screenshot or one live local reply establishes packaged-release, clean-profile, alternate-hardware, live Gemini, camera/microphone, accessibility-device, or representative-user behavior."
    ],
    "risks": [
      "The Python-rendered /ui/chat route is currently the Electron chat surface; leaving its global navigation middleware or invalid nested form structure active can break the layout or prevent chat modules from initializing.",
      "Narrow responsive navigation must remain reachable at the Electron window's minimum supported width while preserving Task 178 behavior."
    ],
    "area": "P47",
    "checkpoint": "task-195-simple-chat-ui",
    "decisions": [],
    "validation": [
      "The Electron source launcher opens /ui/chat?desktop=1; no Next.js /chat page exists. Task 195 changes app/webui/router.py, app/local.py middleware, Python-served chat modules/styles, and the Electron main-window minimum width.",
      "Reproduced the source Electron page failing before this fix: the browser parsed a nested chat form and removed voice-control markup, causing voice.mjs mountChat initialization to throw while the coordinator/chat controls stayed unavailable. Closed the outer form before its nested settings and moved advanced controls outside it.",
      "A source-mode Electron session opened Coordinator Chat on loopback without a password prompt, created an open Local Worker conversation, and a real local Ollama llama3.2:3b reply to 'hello' was 'Hello! How can I assist you today?' in 8.258 seconds. The health endpoint reported version 0.1.0 and base HEAD d4e33a5d08f2; the worktree changes were uncommitted, so this stamp is not an identity for this Task 195 source snapshot.",
      "Focused browser chat and safe-Markdown tests: 37 passed / 0 failed. Final full suites: Python 1,360 passed / 5 skipped / 0 failed (2 warnings), browser modules 247 passed, Electron 38 passed, public docs 21 passed. Python compileall and git diff --check passed."
    ],
    "realWorldVerification": {
      "status": "partial",
      "evidence": ["Windows source-mode Electron connected to the local Ollama service and returned one genuine llama3.2:3b greeting. Source Electron opened the Python /ui/chat route directly; the base revision health stamp was d4e33a5d08f2 while Task 195 changes were uncommitted."],
      "unverified": ["A Task 195 packaged installer/build, Gemini, physical microphone/camera/screen capture, screen reader and representative-owner usability were not exercised."]
    },
    "limitations": [
      "The Next.js static UI still contains the product home and Settings surfaces; it does not expose a duplicate chat route. Electron's configured chat experience is served by the Python /ui/chat page.",
      "One local model reply verifies the immediate source-mode path only; it does not prove model quality, cold-start performance on other hardware, or Task 191 clean-profile/password-lock/recovery acceptance.",
      "Capability information and emergency/session controls are centralized at Settings > Capabilities & privacy. The one-use image, camera, screen, knowledge and voice actions remain available from the chat composer so they can apply to the current conversation."
    ],
    "automatedVerification": [
      "Cover composer keyboard behavior, image/camera/screen/knowledge popover actions, conversation grouping/search/rename/pin/delete, default-collapsed trace, inline chat without capability/permission panels, responsive navigation, and emergency-stop visibility for voice, camera, screen, speech playback, and automation.",
      "Run full Python, browser-module, Electron, and public-docs suites, plus Python compilation and git diff --check; use no paid/cloud calls or automatic downloads."
    ],
    "followUpValidation": ["Build and launch a clean packaged Windows release after checkpointing; test Gemini consent and the actual capture devices separately, and gather representative-owner/accessibility feedback without treating this local automated pass as that evidence."]
  },
  {
    "number": 196,
    "title": "Brain memory and grounded retrieval",
    "description": "Provide one owner-controlled Brain for retained notes and supported files, with bounded extraction, durable source records, optional local semantic indexing, lexical fallback, and cited knowledge previews in chat.",
    "category": "Phase AF - Brain and Retrieval",
    "status": "completed",
    "dependsOn": [177, 192],
    "decisions": ["Optional FAISS capability uses exact official PyPI wheel pins and SHA-256 validation, installed only after explicit owner confirmation into an isolated app-local package directory. Ollama embedding models are listed, previewed, and pulled only after separate owner confirmation."],
    "acceptance": [
      "The Brain page accepts owner-selected UTF-8 text, Markdown, code, CSV, PDF, and DOCX files, folders, drag-and-drop, and pasted text. Each item reports queued, extracting, chunking, embedding, ready, or failed truthfully; unsupported or oversized content gets a clear bounded error.",
      "Retained owner notes require explicit retention consent and expiry. Text extraction and overlapping chunking are bounded; deleting/forgetting an item removes its derived chunks and vectors. Authoritative metadata/content stays in SQLite, with an optional persistent FAISS CPU index and lexical fallback when the pack/model is unavailable.",
      "The optional FAISS and NumPy wheels come only from exact official PyPI artifacts with SHA-256 pins and wheel-only isolated installation. The Ollama embedding adapter uses only an already installed explicitly selected model; any model pull has a separate size/digest confirmation and visible progress. Neither path downloads during startup or chat.",
      "When selected Brain items are used, chat previews the exact owner-authorized excerpts, retrieves at most five bounded chunks, marks retrieved text untrusted, and records citations in the real answer trace. Empty or irrelevant selection produces an honest no-answer notice. Gemini sends selected excerpts only after the existing exact-preview and per-turn cloud consent checks.",
      "Deterministic tests cover file bounds/extraction, auth, owner scope, expiry, deletion, persistence/rebuild, digest-confirmed wheel install, explicit model-pull consent, lexical fallback, preview revalidation, citations, and cloud-consent behavior. Real local acceptance adds five files and one pasted note, runs ten questions, and reports citation/factual outcomes, real embedding Recall@5/MRR, and ingestion timing separately from fakes."
    ],
    "outOfScope": ["No OCR/image intake, 3D Brain renderer, voice/camera/screen pack, task planning, code execution, automated source ingestion, silent installation/model pull, or arbitrary package source. ChromaDB and sentence-transformers remain optional integrations, not automatic base dependencies."],
    "risks": ["Semantic ranking and small-model answer quality vary by corpus, model, and host. A bounded offline evaluation is not a general quality guarantee.", "FAISS native wheels and DLL loading may differ in packaged/frozen Windows builds; exact hashes and fakes do not prove packaged binary compatibility.", "SQLite/vector deletion is logical application deletion, not secure erasure from disk or backups."],
    "area": "P48",
    "checkpoint": "task-196-brain-memory-grounded-retrieval",
    "validation": [
      "Automated validation: full Python suite 1,370 passed / 5 skipped / 0 failed (2 dependency deprecation warnings); browser modules 253 passed / 0 failed; Electron 38 passed / 0 failed; public docs 21 passed / 0 failed. Focused Python Brain/chat/retrieval tests 77 passed / 1 warning; focused Brain/chat UI modules 44 passed. Desktop UI production build and TypeScript checks passed; Python compileall and git diff --check passed.",
      "Real local acceptance on Windows with Ollama llama3.2:3b and nomic-embed-text: six source items (five uploaded files plus one pasted note), ten questions, 10/10 expected facts correct after semantic adjudication, 10/10 expected sources in traces, and real embedding ranking Recall@5 1.00 / MRR 1.00 on this small six-note fixture. Model-emitted inline citation markers appeared in 0/10; the UI renders trace-grounded citations beneath answers.",
      "Real chat latency averaged 3,181 ms across ten questions. Ingestion/storage averaged 21 ms/item (128 ms total); this measurement did not include semantic embeddings because the FAISS pack was not installed. Empty Brain returned an explicit no-answer in 29 ms without provider execution. A JSON snake_case lookup returned the expected 02:00 UTC backup window in 2,927 ms.",
      "Task 196 includes an explicit official-PyPI pinned SHA-256 wheel preview/confirmation flow and persisted FAISS store integration; no wheel was installed in this acceptance. All automated package tests use deterministic fake artifacts and do not download wheels."
    ],
    "realWorldVerification": {"status": "partial", "evidence": ["Windows source-mode local Ollama chat and Brain retrieval exercised with llama3.2:3b; installed nomic-embed-text queried for real Recall@5/MRR on six synthetic notes."], "unverified": ["FAISS wheel installation and native-library loading, packaged Electron integration, semantic-index persistence/rebuild with the installed pack, other Windows/Python versions, and broader corpus/model quality."]},
    "limitations": ["This small synthetic corpus and one local GPU-equipped Windows host do not establish general retrieval or response quality. The 10/10 fact score was manually adjudicated for one semantically equivalent date formatting; model inline citation markers were 0/10, so citations are rendered from the actual trace instead.", "FAISS was not installed because its PyPI wheels require a separate explicit owner action; the real embedding ranking metric measures the installed Ollama embedding model, while live chat used lexical retrieval."],
    "automatedVerification": ["Use deterministic fake embeddings/providers for normal tests. Assert all remote/model/package actions require explicit owner confirmation and loopback-only routes where applicable."],
    "followUpValidation": ["After owner-confirmed FAISS pack installation, verify actual wheel hashes, app-local isolation, native DLL load, persistent semantic index/rebuild and deletion in source and packaged Electron. Exercise supported file types with a broader corpus and a representative owner; report model quality separately."]
  },
  {
    "number": 197,
    "title": "Futuristic 3D Brain visualization",
    "description": "Add an optional Three.js Brain visualization based only on actual authorized document/chunk relationships, with a complete accessible list fallback.",
    "category": "Phase AG - Brain Visualization",
    "status": "completed",
    "dependsOn": [196, 172, 162],
    "decisions": [],
    "acceptance": [
      "Render real Brain documents/chunks as nodes positioned by actual embeddings/projection or recorded document clusters; edges represent measured similarity or a same-source relation only. No random or fabricated telemetry/data.",
      "Ingestion state and actual retrieval/citation events drive node highlighting. Selecting a node shows only owner-authorized source text; sensitive content is not exposed as graph labels or traces.",
      "Use bounded/instanced geometry, cap animation rate, pause work when the page is hidden, respect reduced-motion, and fall back automatically to an equivalent keyboard-accessible 2D list when WebGL or frame-time checks are poor.",
      "Automate real-data mapping, owner-scope, event highlighting, accessible fallback, reduced-motion, and pause/cap behavior. Measure frame time on available hardware during local model generation and label the hardware/configuration."
    ],
    "outOfScope": ["No inferred corporate hierarchy, generated graph nodes, cross-owner memory visibility, continuous model polling, or replacement of existing corporation maps."],
    "risks": ["Projection and similarity can mislead if presented as facts; labels must state their actual basis and preserve unknown states.", "WebGL/GPU timing varies widely; one host's result is not a general performance guarantee."],
    "area": "P49",
    "checkpoint": "task-197-brain-visualization",
    "validation": [
      "Full validation: Python 1,372 passed / 5 skipped / 0 failed (2 dependency deprecation warnings); browser modules 259 passed / 0 failed; Electron 38 passed / 0 failed; public docs 21 passed / 0 failed; desktop UI production build and TypeScript passed; Python compilation and git diff --check passed. Focused graph/API tests 2 passed; focused Brain/chat/knowledge browser tests 50 passed.",
      "Owner-only graph API returns metadata without source content; selected source/chunk text is fetched through the existing owner memory authorization boundary. Layout is deterministic by file-type/note grouping derived from authorized source metadata; edges are source-to-chunk only. No semantic similarity score is available from the existing API and none is shown.",
      "The 3D view uses vendored Three.js instanced geometry, caps continuous animation at 24 FPS and at 320 rendered nodes/480 edges, pauses while the document is hidden, honors reduced-motion preference and switches to the full keyboard-accessible list when WebGL is unavailable or frame-time thresholds are exceeded."
    ],
    "realWorldVerification": {"status": "partial", "evidence": ["On this Windows machine, a local llama3.2:3b generation completed in 11.9 seconds while the Brain implementation was under review. Host CPU/GPU process metrics were not sufficient to attribute inference to the RX 570 or measure Brain canvas FPS."], "unverified": ["RX 570 frame-time/FPS measurement while Ollama generates, packaged Electron WebGL rendering, representative-owner usability and GPU-driver-specific fallback behavior."]},
    "limitations": ["The existing Task 196 memory interface does not expose stored embedding coordinates or pairwise similarity values. The implemented 3D layout uses deterministic source groups and source-to-chunk links only; it does not claim semantic relationships."],
    "automatedVerification": ["Use deterministic embeddings and graph records, never random decorative nodes; test list parity, keyboard access, visibility pause, frame cap and fallback."],
    "followUpValidation": ["Measure actual Brain canvas frame time on the RX 570 while local Ollama generation is active, and verify renderer FPS/CPU/GPU via supported Windows telemetry. Test packaged Electron WebGL. Confirm the accessible list flow with a representative user."]
  },
  {
    "number": 198,
    "title": "Eyes, ears and voice capability packs",
    "description": "Offer owner-installed local image/OCR, microphone/transcription, and speech-output capabilities as separate optional packs with real self-tests and visible use indicators.",
    "category": "Phase AH - Multimodal Packs",
    "status": "completed",
    "dependsOn": [155, 145, 146, 148, 149, 196],
    "decisions": ["Owner approved official PyPI as the only wheel source, exact version and SHA-256 pins, owner confirmation, and isolated wheel-only installation; this does not authorize downloading or installing during development."],
    "acceptance": [
      "For every pack, show Not installed / Installed / Working from observed facts, exact pinned source/version/size/digest and compatibility before an owner-confirmed wheel-only isolated install. Base installer remains small; no unverified or silent downloads.",
      "Eyes: bounded image processing and one-shot screen capture/OCR using maintained local libraries; Tesseract installation/language data are guided separately, EasyOCR remains an optional heavy pack. Self-test captures a selected local screen/window only after permission, recognizes text, and reports the result. Provider transfer requires explicit per-turn consent.",
      "Ears: push-to-talk capture with a visible microphone indicator and local faster-whisper CPU-int8 self-test over an explicitly selected/download-confirmed model. Sounddevice is preferred; PyAudio is added only if required. No online speech recognizer or cloud fallback is implicit.",
      "Voice: local offline pyttsx3 self-test with an immediate Stop control; Kokoro may be separate. Include Coqui only if current maintenance and compatible Windows wheels are verified; any edge-tts option must clearly disclose online text transfer and require explicit consent.",
      "Vision chat lists only installed Ollama models that report vision capability. If none exists, offer choices with sizes and wait for owner confirmation before a pull. Image preview states exactly which provider receives the image and requires existing one-turn consent.",
      "Use deterministic adapter fakes for suites, and exercise real OCR, a five-second microphone recording/transcription, offline TTS/Stop, and one image turn on available Windows hardware where devices/models permit. Record unavailable physical devices as UNVERIFIED."
    ],
    "outOfScope": ["No cloud speech recognizer by default, remote audio/image storage, microphone always-on mode, automatic model/library installation, hidden capture, or claim that a package is working without its self-test."],
    "risks": ["Audio, OCR and vision wheel/model compatibility, licenses, language quality, device drivers and hardware use vary by Windows/Python version.", "Optional model downloads can consume substantial bandwidth/storage and may expose private content if transfer consent is misunderstood."],
    "area": "P50",
    "checkpoint": "task-198-multimodal-capability-packs",
    "validation": [
      "Full Python suite: 1,388 passed, 3 skipped, 0 failed (2 deprecation warnings).",
      "Full browser-module suite: 263 passed; Electron suite: 38 passed; public docs suite: 21 passed.",
      "Desktop UI production/type build, Python compileall, and git diff --check passed.",
      "Focused capability pack, speech model, local TTS, voice API, and emergency-stop tests: 25 passed (1 Starlette TestClient deprecation warning); focused browser capability/stop tests: 5 passed."
    ],
    "realWorldVerification": {"status": "pending", "evidence": [], "unverified": ["No optional pack or FasterWhisper model was downloaded or installed. Real OCR/Tesseract, microphone recording/transcription, physical TTS playback/Stop, screen/camera capture, vision-model chat, and packaged Windows loading were not exercised."]},
    "limitations": [
      "Optional wheels are currently offered only for official PyPI CPython 3.14 Windows x64 artifacts with exact version, size and SHA-256 preview, owner confirmation, and isolated wheel-only installation; this does not verify compatibility on other Python/Windows targets.",
      "Tesseract and its language data require a separately guided installation. EasyOCR is not offered as a heavy pack. Coqui TTS is excluded because compatible maintained Windows wheels were not established. Existing Task 189 vision behavior is reused; this task did not verify a real vision-capable model or image turn.",
      "The optional Ears runtime does not become Working until actual local transcription succeeds; the Eyes pack requires a real OCR self-test and Voice requires successful local speech output. Browser/device voice paths remain separate from these app-managed packs."
    ],
    "automatedVerification": [
      "Deterministic fake-wheel tests cover manifest confirmation, official-source and digest validation, compatibility gates, isolated extraction, atomic installation, startup activation, and failure states without network access or package installation.",
      "Fake OCR, local speech, TTS, API and UI tests cover actual self-test state transitions, permission checks, visible activity, Stop/emergency stop, bounded model pull confirmation, and safe error reporting.",
      "Security review confirmed no import-time downloads, implicit package/model installation, cloud speech fallback, or bypass of existing capture/provider consent."
    ],
    "followUpValidation": ["On a clean supported Windows profile, explicitly install each desired pack, test OCR on a known local image, record/transcribe five seconds of microphone input, exercise offline TTS and Stop, check screen/camera consent indicators, and run a real image turn only with an installed vision model and existing consent. Validate packaged wheel/DLL loading and unsupported-target messaging."]
  },
  {
    "number": 199,
    "title": "Owner-gated computer automation",
    "description": "Extend the existing allowlisted Playwright and Windows UI Automation boundaries with visible previews, per-action owner approval, bounded execution, and a reliable emergency stop.",
    "category": "Phase AI - Owner-Gated Automation",
    "status": "completed",
    "dependsOn": [142, 143, 144, 156, 157, 158],
    "decisions": [],
    "acceptance": [
      "Reuse existing Playwright/UI Automation providers, capability authorization, exact-action approvals, trace/audit services, and emergency-stop controls. Optional package installation is owner-confirmed, version-pinned, hash-checked and isolated.",
      "Playwright runs only in a visible browser against owner-allowlisted HTTPS origins. Preview each exact navigation/click/type/submit action and require fresh owner approval; display each step and record a bounded trace. Default allowlist is empty.",
      "PyAutoGUI, if retained, is disabled by default and requires an allowlisted app, dry-run preview and separate exact-action confirmation for every operation, rate limits, persistent active banner, global hotkey plus UI emergency stop, and stop checks before each action.",
      "Never interpret a timed-out/unconfirmed action as success or retry it automatically. Preserve origin/process/window scoping, fail-closed authorization, audit, owner consent and existing one-use high-risk approval.",
      "Test deterministic no-side-effect previews, denied/non-allowlisted targets, exact approval binding, expiry/replay, stop-before-action, action limits and unknown outcomes. Any real browser/native action test must use a disposable allowlisted target and explicit per-action confirmation."
    ],
    "outOfScope": ["Do not embed Open Interpreter or implement arbitrary code/shell execution. Task 190 remains design-only unless its threat model receives a separate owner review and authorization."],
    "risks": ["Browser/native UI actions may cause irreversible external changes; owner confirmation cannot guarantee the remote system's resulting state.", "A hotkey or process-level stop cannot cancel every native in-flight driver call; uncertain outcomes must remain unknown and never be replayed."],
    "area": "P51",
    "checkpoint": "task-199-owner-gated-computer-automation",
    "validation": [
      "Full Python suite: 1,391 passed, 5 skipped, 0 failed (2 dependency deprecation warnings).",
      "Full browser-module suite: 265 passed, 0 failed; Electron suite: 38 passed, 0 failed; public docs suite: 21 passed, 0 failed.",
      "Desktop UI production/type build, Python compileall, and git diff --check passed.",
      "Focused local automation, owner API, browser, desktop, and capability-pack tests: 32 passed (1 Starlette TestClient deprecation warning); approval-flow UI tests: 2 passed."
    ],
    "realWorldVerification": {"status": "pending", "evidence": [], "unverified": ["No live website action or native Windows UI Automation action was performed. The pywinauto pack was not installed; visible Chromium isolation, a disposable allowlisted site, real UIA target discovery/invocation, and emergency stop during a live action remain unverified."]},
    "limitations": [
      "Allowlists, action counters, and automation adapters are process-local. The browser uses a fresh visible temporary context; same-origin GET/HEAD inspection can still have site-side effects, so the exact URL is shown and the owner must confirm before inspection. No credentials, downloads, cross-origin requests, WebSockets, arbitrary scripts, keys, coordinates, shell commands, or PyAutoGUI are exposed.",
      "Native UI Automation is limited to invoking one exact enabled direct-child button. Emergency stop blocks new actions and is rechecked before dispatch, but an in-flight driver call cannot always be canceled; its outcome remains unknown and is never retried automatically.",
      "The isolated pywinauto pack was added to the reviewed optional-pack catalog but was not downloaded or installed. Real Chromium isolation and native Windows UI Automation were not exercised."
    ],
    "automatedVerification": [
      "Deterministic fake browser/desktop tests cover empty-by-default allowlists, HTTPS/origin and process scoping, read-only discovery, exact target digests, one-use approval, expiry/replay, stop-before-dispatch, rate limits, timeout/unknown outcomes, trace records, and no automatic retry.",
      "Local API/UI tests cover owner-session authorization, same-origin CSRF, process-local policy changes, visible route reachability, emergency stop, and cancellation before approve/execute. Browser action UI displays the exact request and approval digest before each one-use confirmation.",
      "Optional UI Automation support uses exact official PyPI wheels with pinned versions, sizes and SHA-256, CPython 3.14/Windows x64 compatibility gating, owner confirmation, isolated wheel-only installation, and a read-only native self-test. No package was downloaded or installed during validation.",
      "Security review confirmed that Task 190 remains design-only, the base runtime exposes no arbitrary shell/keyboard/coordinate automation, and default external-origin/process policies remain empty."
    ],
    "followUpValidation": ["On a disposable owner-controlled HTTPS site and a benign Windows test window, install the UI Automation pack only after reviewing its exact PyPI manifest, then verify visible browser behavior, one-action confirmation, native button invocation, emergency stop, and unknown-outcome handling. Keep Task 190's separate design gate closed."]
  },
  {
    "number": 200,
    "title": "Built-in Agent team",
    "description": "Provision six editable, role-scoped profiles in the existing Agent and Employee model, with safe default routes, tool/Brain allowlists, honest status, and shared one-at-a-time model capacity.",
    "category": "Phase AJ - Built-in Agent Team",
    "status": "completed",
    "dependsOn": [68, 71, 72, 130, 136, 191, 199],
    "decisions": [],
    "acceptance": [
      "First-run/runtime construction idempotently provisions Coordinator, Researcher, Developer, Librarian, Observer, and Operator through existing Agent and Employee registries. Existing owner-edited profile state is preserved; the Coordinator remains the default chat identity.",
      "Each profile has a bounded role prompt, default/manual or installed-coder route preference, owner Brain scope, reviewed tool allowlist, and bounded permissions. Developer prefers an already-installed coder model only; no model is downloaded. Operator starts paused and available action adapters still require their existing confirmations.",
      "Owners with agent:manage can edit profiles within supported Brain/tool/permission scope, pause/resume, duplicate to a custom Agent, reset a built-in profile, and cannot delete a built-in Employee. Persistent profile edits survive application reconstruction.",
      "Agent state reports only observed idle, working, paused, error, or unavailable (including a missing assigned local model/provider). The shared approvals inbox does not falsely attribute owner approval requests to an Agent; an Agent waiting state requires explicit Agent provenance.",
      "Coordinator and Employee chat receive the selected Agent's role prompt. Chat tool and Brain requests are checked against that Agent's allowlists. All chat turns use one shared configured ResourceManager slot; an assigned model route can be accounted without resetting allocation-ID history.",
      "Tests cover clean provisioning, repeat provisioning, coder preference without download, owner profile controls/persistence, fail-closed permission/CSRF checks, built-in protection, role prompt/tool scope, real status sources, and one-at-a-time slot reservation/release."
    ],
    "outOfScope": ["Do not add new Agent/Employee/Position domain models, UI pages, delegation, approval inbox behavior, background work, autonomous loops, live web search, provider fallback, hardware capability claims, or new dependencies. Exact-host web retrieval remains distinct from search."],
    "risks": ["All roles use the assigned provider/model and are profiles, not separate AI brains. A single shared slot serializes model turns locally; status and runtime metrics are process-local.", "Availability probes and installed model inventory can fail or be unsupported; report error/unavailable rather than fabricate readiness. Owner changes to profile permission metadata do not bypass existing service authorization or per-action approval."],
    "area": "P52",
    "checkpoint": "task-200-builtin-agent-team",
    "validation": [
      "Full Python suite: 1,398 passed, 5 skipped, 0 failed (2 dependency deprecation warnings).",
      "Full browser-module suite: 265 passed, 0 failed; Electron suite: 38 passed, 0 failed; public docs suite: 21 passed, 0 failed.",
      "Focused Agent team, profile API, resource slot, local model, migration, backup/restore, and browser regressions passed. git diff --check and Python compileall passed."
    ],
    "realWorldVerification": {"status": "unverified", "evidence": [], "unverified": ["No live local llama3.2:3b mixed-question delegation run is claimed for this phase; Task 202 will perform the requested Coordinator choice/latency/failure evaluation when its real delegation behavior exists."]},
    "limitations": ["Built-in profiles are role instructions and scoped metadata over shared providers/models, not isolated minds. The Researcher may retrieve only exact HTTPS URLs from the existing owner allowlist; it does not provide general web search. The six role positions are not auto-created because the existing Position templates are a separate owner-managed structure and do not include all six roles."],
    "automatedVerification": [
      "Deterministic tests cover idempotent provisioning, existing profile preservation, coder preference using only installed-model evidence, role prompt/tool/Brain boundaries, owner-only profile access and CSRF, edits/pause/duplicate/reset persistence, built-in protection, runtime status evidence, and one shared ResourceManager slot.",
      "Default and private encrypted backup paths preserve the Agent profile table under the existing owner-controlled Backup & Restore behavior; profile data is not exposed by the ordinary Agent read API.",
      "All required deterministic suites passed: Python 1,398/5 skipped, browser modules 265, Electron 38, public docs 21."
    ],
    "followUpValidation": ["Task 202 must evaluate five real Coordinator questions with local llama3.2:3b and report selected Agent, choice suitability, latency, and failures. Packaged Windows profile provisioning and real provider/status behavior remain separate follow-up evidence."]
  },
  {
    "number": 201,
    "title": "Agents page and profile management UI",
    "description": "Add a clean Agents workspace showing real role profiles, routes, states, activity, organization view, and owner-scoped editing.",
    "category": "Phase AK - Agents Workspace",
    "status": "completed",
    "dependsOn": [200],
    "decisions": [],
    "acceptance": ["Show All, Active, Paused, Error, and Built-in filters; List and existing organization Tree views; agent avatar/name/role/model/status/last activity and Chat action; and a New Agent form using existing records.", "Agent details expose role prompt, model, Brain scopes, tools, permissions and recent activity with advanced fields collapsed. Built-ins can be edited/reset/paused/duplicated through authorized APIs; status is sourced from runtime checks.", "Explain in plain language that profiles share model brains and local model work is serialized one at a time. Accessible responsive navigation and empty/loading/error states are covered by browser tests."],
    "outOfScope": ["No new Agent domain model, autonomous work, provider/model downloads, or permissions beyond existing owner APIs."],
    "risks": ["Provider checks may be slow or unavailable; the page must expose unknown/error states and avoid presenting a stale result as current."],
    "area": "P53",
    "checkpoint": "task-201-agents-page",
    "validation": [
      "Full validation: Python 1,396 passed / 8 skipped / 0 failed; browser modules 270 passed; Electron 38 passed; public docs 21 passed. Python compileall and git diff --check passed."
    ],
    "realWorldVerification": {"status": "unverified", "evidence": [], "unverified": ["Packaged Electron rendering, live provider/model status, and representative owner usability were not exercised; route and browser interaction checks used the local TestClient and deterministic fixtures."]},
    "limitations": ["Last-activity timestamps are process-local and disappear on restart. The organization tree shows actual recorded Positions and only their existing Employee/Agent links; it does not create a new Agent hierarchy. New Agents are created by duplicating an existing profile and Employee identity; no deletion control is added."],
    "automatedVerification": ["Full validation passed: Python 1,396/8 skipped, browser modules 270, Electron 38, public docs 21. Focused legacy chat regressions: 28 passed after aligning Ollama fakes with the native generate_chat adapter. Focused browser tests cover runtime-state filters, existing organization-map data, read-only permission denial, collapsed profile editing, CSRF-backed pause/reset, custom profile duplication, selected Employee chat routing, and single-slot wording. API tests verify built-in classification is exposed without role prompts, permissions, or other profile data."],
    "followUpValidation": ["Inspect the Agents page in the packaged Windows application and confirm real provider/model/status details match the current host."]
  },
  {
    "number": 202,
    "title": "Agent chat, bounded delegation, and approvals inbox",
    "description": "Let owners chat with a selected role profile and let the Coordinator propose at most one visible, bounded Agent handoff with a trace and an owner approvals inbox.",
    "category": "Phase AL - Agent Delegation and Approvals",
    "status": "completed",
    "dependsOn": [177, 182, 183, 191, 200, 201],
    "decisions": [],
    "acceptance": ["Default chat remains Coordinator; exact @Name selection or an Agent Chat action selects that existing Agent identity and conversation safely.", "Coordinator delegation is limited to one named Agent handoff, one active local model slot, a small fixed maximum number of steps, and no loops, retries, replay, or background work. The owner starts every run and every handoff plus actual evidence appears in the existing answer trace.", "A sidebar inbox surfaces actual pending, expiring exact-action approvals from existing approval services with preview, approve, deny, and expiry behavior. Side-effect actions, cloud calls, file changes and automation retain their existing explicit approval/consent and spend gates.", "Queue state is visible when the shared model slot is occupied. Five mixed real local llama3.2:3b Coordinator prompts report chosen Agent, suitability, latency and failures separately from deterministic tests."],
    "outOfScope": ["No autonomous/background Agent activity, multi-agent parallel execution, unlimited loops, silent cloud routing, new approval authority, or hidden execution."],
    "risks": ["Model-generated Agent selections and handoff summaries are untrusted proposals; coordinator limits and owner approval remain enforced by trusted code. Local model quality may produce unsuitable choices."],
    "area": "P54",
    "checkpoint": "task-202-agent-delegation-approvals",
    "validation": [
      "Full validation: Python 1,401 passed / 8 skipped / 0 failed (2 dependency deprecation warnings); browser modules 272 passed / 0 failed; Electron 38 passed / 0 failed; public docs 21 passed / 0 failed. Focused delegation/resource/approval regressions passed (including preserved cloud slot-exhaustion behavior); Python compileall, JavaScript syntax checks, and git diff --check passed.",
      "Focused delegation, approval, and resource regressions passed; Python compilation and JavaScript syntax checks passed."
    ],
    "realWorldVerification": {"status": "unverified", "evidence": [], "unverified": ["The live llama3.2:3b evaluation was not possible: http://127.0.0.1:11434/api/tags refused the local connection. The requested five mixed prompts, suitability, and real-model latency were not tested. Packaged Electron interaction was also not exercised."]},
    "limitations": ["Delegation is an owner-confirmed, synchronous local request: the Coordinator proposes one eligible installed-model Agent, trusted code validates it, and the selected Agent gets one plain-text answer turn. Tools, Brain context, cloud routes, retries, replay, and background execution are excluded. Shared-slot wait is process-local, bounded to 16 waiters and 30 seconds; a timed-out request is not admitted. It does not coordinate external processes or unsynchronized registry/resource changes.", "The inbox reads actual owner-scoped expiring approval records. Approve records the exact owner decision but never executes the action; the protected operation still needs its existing guarded execution path. Denial is audited and cannot execute. Existing approval records do not identify a requesting Agent, so no Agent is labeled as waiting for approval without that provenance."],
    "automatedVerification": ["Deterministic API/service tests cover one Coordinator selection plus one Agent answer, strict candidate validation, no second call on invalid selection, trace provenance, shared slot waiting/release, failed-answer cleanup, no secret diagnostics, owner-scoped approval listing, exact-digest approve/deny, CSRF, audit, expiry and no execution from approval alone.", "Browser tests cover explicit one-turn delegation confirmation, plain-text restrictions, visible pending/waiting state, permission-gated approval count, exact action preview, CSRF-backed denial, refresh, and safe DOM rendering."],
    "followUpValidation": ["When loopback Ollama is available, run five mixed prompts through the current local app and report actual replies, selected Agent, suitability, latency, and failures. Confirm packaged Electron status and owner approval inbox against actual runtime records."]
  },
  {
    "number": 203,
    "title": "Sage Core live-state visualization",
    "description": "Visualize the real Agent team as original amber concentric sigils with a 2D accessible fallback, using runtime state and real handoff/source links only.",
    "category": "Phase AM - Sage Core Visualization",
    "status": "completed",
    "dependsOn": [197, 200, 201, 202],
    "decisions": [],
    "acceptance": ["Create an original canvas/WebGL ring-and-glyph display on its own page and optional Agents-page compact view. Coordinator is centered; actual Agents occupy stable orbit positions, and selecting a sigil opens that Agent's real details.", "Brightness, pulse and rays are derived only from actual idle/working/waiting-approval/error/unavailable states; source and handoff links appear only while backed by real trace events. No random activity or copied anime artwork, glyph sheets, names, or assets.", "Provide a complete keyboard-accessible 2D list fallback, reduced-motion mode, hidden-page pause, capped frame rate and automatic fallback when WebGL is unavailable or measured frame time exceeds the threshold.", "Measure frame time on this RX 570 while a local model generates and report renderer/build identity, workload and results. Automated tests assert no fabricated nodes/edges, stable mappings, fallbacks and reduced-motion behavior."],
    "outOfScope": ["No copied third-party art, fake telemetry, idle animations that imply work, model-performance inference, or changes to Agent state/execution."],
    "risks": ["GPU/WebGL performance varies by driver and app packaging; a visual effect must never imply execution or approval that did not occur."],
    "area": "P55",
    "checkpoint": "task-203-sage-core-live-state-visualization",
    "validation": ["Full validation: Python 1,403 passed / 8 skipped / 0 failed; browser modules 281 passed / 0 failed; Electron 38 passed / 0 failed; public docs 21 passed / 0 failed. Python compilation, JavaScript syntax checks and git diff --check passed."],
    "realWorldVerification": {"status": "unverified", "evidence": [], "unverified": ["The loopback Ollama endpoint refused connection, so no live model generation was available. The requested RX 570 rendering/frame-time run while a local model generated was not performed. Packaged Electron rendering was not exercised."]},
    "limitations": ["The local map is read-only and renders at most 100 current Agent profiles, traces from the 20 most recent in-memory owner conversations, 60 handoffs, and 100 current Brain-source links. Trace links show recorded events, not a live transfer stream; no conversation text or Brain content is returned by the map API.", "Task 202 approval records do not identify a requesting Agent, and the current runtime status service does not produce an Agent-specific waiting-for-approval state. The visualization supports that state if a future authorized source reports it, but does not infer it from a generic pending approval.", "This implementation uses original Canvas 2D sigils rather than WebGL. Automatic fallback measures JavaScript draw duration; it does not establish GPU completion timing. RX 570 and packaged Electron measurements remain follow-up."],
    "automatedVerification": ["The protected snapshot requires both agent:read and chat:read, returns only bounded Agent metadata and current trace identifiers, strips conversation content, ignores stale Brain sources, and emits only validated handoff/source links.", "Browser tests verify actual-record-only nodes and links, ID-stable orbit placement, Coordinator center from the built-in profile key, state rendering, keyboard-selectable details, accessible list relationships, reduced-motion default, absent-canvas fallback, hidden-page pause, 24 FPS cap and draw-budget fallback."],
    "followUpValidation": ["Run the packaged Electron app on the RX 570 while a local model generates; record the exact build identity and observed frame timing. Confirm the accessible list and reduced-motion behavior in the packaged app. Live local inference remains unavailable in this acceptance environment."]
  },
  {
    "number": 207,
    "title": "Bounded Agent Runtime",
    "description": "Route every chat provider call through one synchronous Agent Runtime with bounded direct responses, a capped planner/tool interface, trace metadata, timeouts, token limits, and the existing emergency stop.",
    "category": "Phase AN - Agent Runtime",
    "status": "completed",
    "dependsOn": [177, 182, 200, 201, 202],
    "decisions": [],
    "acceptance": ["Coordinator, Employee, image, alternate-route, streaming and non-streaming chat calls share one runtime boundary; ordinary turns use one direct answer step.", "The synchronous planner contract is capped at five steps, bounded by total/per-step time and output-token budgets, validates exact answer/tool decision fields, marks tool output untrusted, and does not retry malformed tool calls.", "Registered tools declare a schema and risk class, provide a preview and dry-run, and may opt into undo. Unknown risk fails closed as control. Only explicitly authorized read tools can auto-run; every other risk is rejected with an approval-required preview.", "Runtime operations check the existing global emergency stop, emit a compact streaming status, and attach metadata-only runtime steps to the existing owner-scoped chat trace. No prompt, tool result, secret, or raw exception is stored in runtime metadata."],
    "outOfScope": ["No background/restarting loop, automatic tool selection, autonomy setting, model-quality policy, remote web search, task dispatch, or silent side effects; those remain later phase scope."],
    "risks": ["A synchronous local stop check cannot forcibly interrupt arbitrary blocking third-party code; provider adapters must honor runtime deadlines and check the stop between chunks."],
    "area": "P56",
    "checkpoint": "task-207-bounded-agent-runtime",
    "validation": ["Full validation passed: Python 1,414 passed / 5 skipped / 0 failed; browser modules 279 passed / 0 failed; Electron 38 passed / 0 failed; public docs 21 passed / 0 failed. Focused Agent Runtime/chat/tool tests passed (79 passed); Python compileall and git diff --check passed."],
    "realWorldVerification": {"status": "partial", "evidence": ["A real local TestClient chat route using the installed Ollama llama3.2:3b returned 'Hi!' to 'hello'; the attached metadata-only runtime trace recorded classify, plan and answer in 875 ms."], "unverified": ["Packaged Electron behavior and runtime interruption during a real provider generation were not exercised."]},
    "limitations": ["Agent Runtime direct chat is integrated with provider timeout/token bounds and emergency-stop checks. Its bounded planner interface is tested with deterministic fakes; automatic routing and production tool orchestration are later Tasks 208-210. The real local check used the Python-served API in an isolated temporary data directory, not a packaged Electron build."],
    "automatedVerification": ["Focused deterministic tests cover all chat routes through the runtime, structured provider messages, limits, stop checks, streaming cleanup, metadata-only traces, tool schemas, previews, read-only admission, approval denial, untrusted observations, and malformed structured output."],
    "followUpValidation": ["Run the local-model evaluation after the automatic tool-routing and quality-gating phases are implemented. Confirm stop and bounded generation in the packaged Windows application when a local model is available."]
  },
  {
    "number": 208,
    "title": "Deterministic direct-versus-agentic routing",
    "description": "Route ordinary chat directly and select bounded agentic handling only when a supported capability clearly matches; classification failures fall back to direct chat.",
    "category": "Phase AO - Auto-routing",
    "status": "completed",
    "dependsOn": [207, 182, 196],
    "decisions": [],
    "acceptance": ["Deterministic greetings and ordinary chat use one direct response; owner-selected Brain/reviewed read tools and the existing explicit one-step delegation select only their supported path and are recorded in the real trace.", "Unsupported web/screen/code cues, unknown tools, and classifier errors fall back to direct response without repeating tools or hiding failures.", "This implementation has no model-based classifier. Any future classifier fallback must use constrained structured output, exact field validation, and at most one repair retry; malformed tool calls cannot execute."],
    "outOfScope": ["No automatic cloud/provider/model switching, unsupported web/screen/code capabilities, background activity, or silent side effects."],
    "risks": ["Keyword heuristics may misclassify ambiguous language; fail-safe behavior is a direct answer and visible trace rather than a guessed tool call."],
    "area": "P57",
    "checkpoint": "task-208-deterministic-chat-routing",
    "validation": ["Full validation passed: Python 1,421 passed / 3 skipped / 0 failed (2 Starlette deprecation warnings); browser modules 281 passed / 0 failed; Electron 38 passed / 0 failed; public docs 21 passed / 0 failed; desktop UI production/type build passed; Python compileall and git diff --check passed."],
    "realWorldVerification": {"status": "ai-verified-only", "evidence": ["Routing is a deterministic local rule set and does not ask a model to classify tool requests. End-to-end route tests verify direct greetings, selected Brain/reviewed-tool paths, trace metadata, and direct fallback for unsupported web/screen/code cues and classifier failure."], "unverified": ["No representative-user or packaged-Electron route usability run was performed. Task 211 real-model evaluation remains pending."]},
    "limitations": ["Brain retrieval and reviewed read tools still require their existing owner-selected scopes/previews or exact tool parameters; delegation remains an explicit one-step owner action. Mentioning a capability never grants permission. Web search, screen access, code execution, unknown tools, and classifier failures use a direct answer path; this phase adds no model-based classifier or automatic repair."],
    "automatedVerification": ["Deterministic tests cover greeting/ordinary direct routing, owner-selected supported paths, unsupported capability fallback, unknown tools, classifier exceptions, route trace persistence and safe UI rendering."],
    "followUpValidation": ["Task 211 compares measured direct-versus-agentic outcomes on installed local models; representative-owner usability remains follow-up and is not substituted by tests."]
  },
  {
    "number": 209,
    "title": "Owner autonomy levels and action approvals",
    "description": "Add one persisted autonomy preference for chat-only, safe read actions, or approval before every action, while reusing current consent, approval and emergency-stop controls.",
    "category": "Phase AP - Autonomy controls",
    "status": "planned",
    "dependsOn": [207, 208, 142, 144, 182],
    "decisions": [],
    "acceptance": ["Settings and a compact chat control offer Chat only, Auto for safe actions (default), and Ask before every action; the selected value is persisted per owner and fail-closed on corrupt/missing data.", "Only declared read tools can execute automatically at the default level. Write, external, and control actions create an exact-preview inline approval card with owner approve/deny and expiry, before execution.", "Cloud calls retain per-turn consent and spend limits; Operator/automation remain disabled until separately enabled in Settings; the existing one-click emergency stop remains visible and effective."],
    "outOfScope": ["No change to fail-closed authentication, capability grants, existing permission requirements, cloud consent, spending limits, or approval execution contracts."],
    "risks": ["A persisted preference must never grant broader authority than current permissions or silently approve stale/changed action previews."],
    "area": "P58",
    "checkpoint": null,
    "validation": [],
    "limitations": [],
    "automatedVerification": ["Test owner isolation, migration/corruption fallback, each autonomy level, exact-preview digest, denial, expiry, CSRF, emergency stop and zero side effects without approval."],
    "followUpValidation": ["Review the three levels and approval clarity in the local UI; manual usability feedback remains follow-up and is not substituted by tests."]
  },
  {
    "number": 210,
    "title": "Small-model tool-calling quality",
    "description": "Prefer verified native tool calling when supported and otherwise use bounded structured output, then compare installed local models before suggesting any owner-confirmed model change.",
    "category": "Phase AQ - Tool-calling quality",
    "status": "planned",
    "dependsOn": [207, 208, 209, 182],
    "decisions": [],
    "acceptance": ["Provider capability evidence determines whether native tool calling is supported; unknown capability uses validated structured output, never model-name assumptions.", "Every proposed call is validated against the registered tool schema and risk before preview, approval or execution; malformed output gets at most one repair and never loops.", "Compare llama3.2:3b with any larger installed local model on the same deterministic tool cases. The UI may suggest a larger installed model with evidence, but switching requires owner confirmation; no download occurs."],
    "outOfScope": ["No silent model switching/downloads, cloud calls, paid services, fabricated capability evidence, or quality claims without measured results."],
    "risks": ["Native tool support and structured output vary by model/runtime; incorrect capability declarations can produce invalid or unsafe calls, which must fail closed."],
    "area": "P59",
    "checkpoint": null,
    "validation": [],
    "limitations": [],
    "automatedVerification": ["Use deterministic fake providers to test supported/unsupported/unknown capability paths, strict schemas, single repair, no invalid execution, bounded traces and explicit model-change confirmation."],
    "followUpValidation": ["Record model IDs, provider-reported capability, measured tool accuracy and latency for real local evaluations separately from fakes."]
  },
  {
    "number": 211,
    "title": "Real local Agent Runtime evaluation harness",
    "description": "Evaluate realistic plain-chat, Brain, read-tool, and approval-required requests against installed local models and keep agent mode experimental for models with poor measured results.",
    "category": "Phase AR - Runtime evaluation",
    "status": "planned",
    "dependsOn": [207, 208, 209, 210],
    "decisions": [],
    "acceptance": ["Provide 30 reproducible tasks: 10 plain chat, 10 Brain/retrieval, 5 web/read, and 5 approval-required. Run only installed local models with no cloud/paid calls or downloads.", "Report each model’s success rate, wrong-tool rate, average steps, latency and failures with model/runtime identity and retained evidence sufficient to reproduce the score.", "Models with poor measured results are labeled experimental and agent mode is not enabled by default for them; unknown/incomplete evaluations do not count as passing."],
    "outOfScope": ["No model downloads, paid/cloud evaluation, silent capability changes, or automatic promotion based on synthetic/fake-provider scores."],
    "risks": ["A small evaluation set may not predict general user quality; scores must remain bounded to the exact test set and hardware/runtime used."],
    "area": "P60",
    "checkpoint": null,
    "validation": [],
    "limitations": [],
    "automatedVerification": ["Test the harness with deterministic providers for task accounting, scoring math, wrong-tool detection, latency aggregation, failure reporting and gating of unmeasured models."],
    "followUpValidation": ["Run all 30 tasks with the real installed llama3.2:3b and any larger installed local model; publish actual replies, model identity and hardware/runtime limitations."]
  },
  {
    "number": 213,
    "title": "Shared UI foundation and polish",
    "description": "Make the existing Next.js and Python-served screens consistent, accessible, resilient, and reviewable through reproducible visual checks.",
    "category": "Phase AS - UI Foundation",
    "status": "completed",
    "dependsOn": [178, 191, 195, 201],
    "decisions": ["The owner approved the light/dark visual direction for continued development. Final before/after visuals were approved by the owner on 2026-10-23."],
    "acceptance": ["Use one shared set of color, spacing, type, radius and motion tokens and shared button, input, card, dialog, popover, banner and list primitives across both UI stacks.", "Audit each screen's empty, loading, error and offline states; remove stale technical copy, raw diagnostics, clipped text, dead links and overflow without changing runtime authority.", "Retain screenshot baselines for key screens in light/dark at 480/768/1280/1920 CSS pixels and simulated 100/125/150 percent device scales; report actual Windows scaling separately.", "Run axe with zero critical issues and check keyboard navigation, focus, contrast, reduced motion, labels and long Taglish/name/word resilience. Provide a before/after fix list for owner review."],
    "outOfScope": ["No multi-window behavior, workspace isolation, model-queue implementation, provider calls, downloads, or change to authentication and consent."],
    "risks": ["Dark-only page overrides can break light-theme contrast; viewport/device-scale simulation does not prove native Windows scaling or assistive-technology behavior."],
    "area": "P61", "checkpoint": "task-213-ui-foundation-polish", "validation": ["Python 1422 passed / 5 skipped / 0 failed; browser modules 289 passed; Electron 38 passed; public docs 21 passed. Next 16.4.2 production/type build, dependency audit (zero vulnerabilities), compilation and diff integrity passed. Latest 35-screen normal/error/offline/loading matrices passed 490 screenshots with keyboard focus, overflow, serious/critical axe, local-link and layout-shift checks. Twelve screenshot baselines retained; earlier key-screen matrix covered 480/768/1280/1920 widths and simulated 100/125/150 percent scales. Owner approved final visuals on 2026-10-23."],
    "realWorldVerification": {"status": "ai-verified-only", "evidence": ["Owner reviewed and approved the final screenshot direction; deterministic Chromium checks exercise isolated local pages."], "unverified": ["Packaged Electron theme persistence, actual Windows scaling, assistive technology and representative-user behavior are unverified."]},
    "limitations": ["The latest normal/error/offline/loading matrices passed 490 screenshots across 35 screens; earlier key-screen checks covered four widths and three simulated scales. Full Python: 1422 passed, 5 skipped; browser modules: 289 passed; Electron: 38 passed; public docs: 21 passed. Actual Windows scaling, packaged theme persistence and assistive technology remain unverified. Exhaustive dynamic-dialog keyboard flows, packaged theme persistence and native assistive technology are not established by automated Tab traversal. Tasks 214-217 remain separate planned scope."],
    "automatedVerification": ["Use an isolated local profile and fake provider, screenshot comparisons, axe, keyboard/focus checks, long-text stress cases and injected API failures. Run the full Python, browser-module, Electron and public-docs suites before the checkpoint."],
    "followUpValidation": ["Record packaged Electron, actual Windows scaling, assistive-technology and representative-user coverage honestly; no simulated check proves those integrations."]
  },
  {
    "number": 214,
    "title": "Shared-backend Electron windows",
    "description": "Open independent chat windows in one Electron process and one loopback Python backend, with a separate nonblocking Settings window and safe workspace restoration.",
    "category": "Phase AT - Window Architecture", "status": "completed",
    "dependsOn": [213, 191, 178], "decisions": [],
    "acceptance": ["Keep the single-instance lock; second launch and Ctrl+N create a new chat window using the existing backend. App launch stays direct-to-chat.", "Settings has one reusable window that can be focused without blocking chat windows.", "Restore window bounds, selected model/agent/project and conversation after close/reopen or restart, validating stored values and never replaying actions.", "Replace single-window trust assumptions with explicit trusted-window records while preserving owner authentication, loopback restrictions, Origin/CSRF checks and per-use native permission decisions."],
    "outOfScope": ["No second backend, hidden action replay, cross-owner sessions, silent provider/model loading, or public network binding."],
    "risks": ["Native IPC and media grants must not accept stale or untrusted windows; restored coordinates must remain reachable on changed monitors."],
    "area": "P62", "checkpoint": "task-214-shared-backend-windows", "validation": ["Full Python suite: 1422 passed / 5 skipped / 0 failed; browser modules 292 passed; Electron 43 passed; public docs 21 passed. JavaScript syntax and diff integrity passed. Real source-mode Electron 44.7.0 check passed direct chat, native Ctrl+N event handling, separate singleton Settings, second launch in the same main process with unchanged backend listener PID, and four-window restart restoration."],
    "realWorldVerification": {"status": "partial", "evidence": ["Isolated source-mode Windows Electron main PID 16432 and backend listener PID 21000: second launch reused both processes; four windows restored after restart. Electron was extracted from the existing local cache after matching its dependency SHA-256, without a download."], "unverified": ["Packaged installer, physical keyboard/media, multiple monitors, actual Windows scaling, retained production conversations and concurrent real model workloads are unverified."]},
    "limitations": ["Only geometry and bounded identifiers are restored; messages depend on existing owner-controlled retention. Missing/unretained conversations open a new empty chat with an explanation, never replaying actions or silently enabling retention. Descriptor fields include model/project, while independent selectors and server-enforced workspace/project/approval isolation remain Task 215. Native shortcut testing used Electron sendInputEvent, not a physical keyboard. The source-mode run used a dirty worktree based on Task 213, not a packaged Task 214 build stamp."],
    "automatedVerification": ["Test single-instance/second-launch behavior, Ctrl+N, singleton Settings, shared backend lifecycle, trusted-window IPC, safe bounds restoration and absence of replay. Run all four suites."],
    "followUpValidation": ["Record actual packaged Windows close/reopen/restart and monitor/scaling behavior separately from fakes."]
  },
  {
    "number": 215,
    "title": "Isolated per-window workspaces",
    "description": "Give each window its own conversation, model, agent and project while sharing owner auth, providers, Brain index and settings safely.",
    "category": "Phase AU - Workspace Sessions", "status": "planned",
    "dependsOn": [214, 184, 200, 202], "decisions": [],
    "acceptance": ["Expose compact model/agent/project selectors and a matching window title; support different models, agents or projects per window without silently changing global Agent assignments.", "Isolate conversation, approvals, selected route and trace by workspace; show requesting window/agent/project on approval previews and enforce the same provenance server-side.", "Use the existing project Brain scope and instructions with durable workspace/conversation association. Shared settings and providers remain owner-scoped.", "Enable and verify SQLite WAL and serialized writers where required; concurrent writes and restart recovery must not mix or corrupt workspaces."],
    "outOfScope": ["No new Agent/Employee model, new authority, cross-project retrieval, action replay, background autonomous work or silent provider transfer."],
    "risks": ["Client-only workspace labels cannot establish authorization; selection changes must preserve immutable existing conversation scopes and approval digests."],
    "area": "P63", "checkpoint": null, "validation": [], "limitations": [],
    "automatedVerification": ["Test two-window model/agent/project combinations, conversation and trace isolation, approval provenance, cross-project denials, concurrent writes, migrations and restart restoration. Run all four suites."],
    "followUpValidation": ["Exercise packaged Windows sessions and real model conversations separately; report unavailable clean-profile coverage."]
  },
  {
    "number": 216,
    "title": "Visible shared resources and capture ownership",
    "description": "Coordinate model capacity and protected local devices across workspaces with visible bounded waiting and reliable stop controls.",
    "category": "Phase AV - Concurrency and Resources", "status": "planned",
    "dependsOn": [215, 68, 70, 144, 200], "decisions": [],
    "acceptance": ["Route all chat model calls through the existing ResourceManager and show queue position, waiting-for-model state and cancellation without replay.", "Report actual Ollama loaded-model/parallel-capability observations or unknown; warn about likely reload cost and suggest one model without changing Ollama settings or loading/downloading models.", "Provide a configurable soft window cap with a warning, defaulting to three.", "Grant microphone, camera and screen capture to one workspace at a time with real ownership indicators and a clear denial in other windows. Provide global and per-window emergency stop, preserving per-turn cloud consent and global spend limits."],
    "outOfScope": ["No distributed coordination, automatic model download/load, changed Ollama configuration, silent cloud fallback or weakened native/owner consent."],
    "risks": ["A cancelled wait must release no unowned capacity; runtime failure and window close must release acquired slots/devices while reporting uncertain remote outcomes truthfully."],
    "area": "P64", "checkpoint": null, "validation": [], "limitations": [],
    "automatedVerification": ["Test queue ordering/position/cancel, capacity cleanup on failure/stop/close, unknown capability states, soft cap, capture exclusivity, global/per-window stop and spending/consent boundaries. Run all four suites."],
    "followUpValidation": ["Measure installed Ollama behavior and real device handoff/stop on Windows; fake concurrency does not establish RAM/VRAM feasibility."]
  },
  {
    "number": 217,
    "title": "Real multi-window workspace QA",
    "description": "Evaluate three-window isolation, resource waiting and rendering using the actual local app and installed Ollama models.",
    "category": "Phase AW - Multi-window QA", "status": "planned",
    "dependsOn": [213, 214, 215, 216], "decisions": [],
    "acceptance": ["Run parallel prompts in three windows for different installed local models, the same model with different agents, and the same model/agent with different projects.", "Record actual replies, isolation, queue/cancel behavior, project citations, crashes, latency and available RAM/VRAM observations with their provenance. Mark unavailable combinations unverified without downloading models.", "Repeat the visual matrix for workspace headers and the separate Settings window; report actual Windows scaling separately from device-scale simulation."],
    "outOfScope": ["No paid/cloud calls, model downloads, fabricated GPU telemetry, public release, push or deployment."],
    "risks": ["Results are limited to installed models and this machine; a passing deterministic test is not proof of live-provider performance or physical-device behavior."],
    "area": "P65", "checkpoint": null, "validation": [], "limitations": [],
    "automatedVerification": ["Run reproducible isolated multi-window scenarios and all Python, browser-module, Electron and public-docs suites; preserve logs and screenshots without owner content or credentials."],
    "followUpValidation": ["List untested hardware, clean-account, microphone/camera/screen and representative-user combinations explicitly."]
  }
];

export const roadmapRules = {
  "scope": "Publishing task contracts does not implement planned capabilities or grant runtime authority. Implement only the current authorized task after resolving its owner decision gates; credentials, installations, model calls and deployment actions require their own authorized scope.",
  "source": "Read docs/tasks-data.mjs and the relevant existing code before implementing a task; it is the single source for task scope and status across public pages. Completed, deferred, planned, and design-only states are distinct. Tasks 134, 170, 193 and 194 are deferred and incomplete; Tasks 135-169, 171-189, 191-192, 195-203 and 207-208 are completed scoped checkpoints; Tasks 213-214 are completed scoped checkpoints; Task 213 has owner-approved visuals and Task 214 has source-mode window evidence; Tasks 209-211 and 215-217 are planned; Task 190 is design-only. Tasks 204-206 and 212 have no published contract and are not inferred. Task 176's separate-account and live-provider checks remain unverified follow-up; Task 178 native resize was checked in a local packaged Windows build; Task 191 supersedes the wizard-first launch flow but its clean-profile Windows/Gemini/DPAPI acceptance remains pending; Task 193's prompt completion claim was corrected by Task 194 after package identity and Employee-chat coverage exposed the defect; P00-P16 remains supplementary product context.",
  "sequence": "Resume preserved work; inspect git status and current checkpoint first. Use one reviewed task checkpoint at a time; do not start later behavior early or overwrite another AI's work.",
  "decisions": "Planned means proposed work. Record owner approval for unresolved product/architecture/authority decisions before dependent code. Do not infer approval from a status change or generated text.",
  "developmentAcceptance": "For Tasks 175-211, AI agents perform testing, debugging, UI checks and evidence review without required human QA sign-off. Complete the scoped development contract only after reproducible checks pass; deterministic/fake evidence is distinct from real hardware/live-provider evidence and does not establish it. Record unavailable provider, clean-account, hardware and user-study coverage as unverified with impact. Such coverage does not block development completion unless an essential security or functional invariant remains unproven. Do not mark tasks complete by policy change alone. Dependencies use this scoped development acceptance. Preserve runtime owner consent, credentials, spending, signing, publishing and authority decisions. Task 190 remains design-only.",
  "enhancementLoop": "After scoped development acceptance, continue to the next dependency-ready task without waiting for human QA. Record reproducible defects and regression cases for later review by different AI models; identify model/reviewer when available and never claim independent review that did not occur.",
  "verification": "Run focused and directly affected regressions, then the full Python suite for runtime changes as appropriate. Run browser/docs tests for those changes; use deterministic fakes and separate optional live integration checks. Run compilation/type checks where available and diff/security/scope review.",
  "completion": "Completed requires actual acceptance evidence, truthful limitations/skips, required documentation/update records, and a reviewed task checkpoint. A local checkpoint is sufficient for development acceptance; push or deployment is separate and must be authorized and verified when performed. Never mark complete solely because code exists or an AI says it worked.",
  "failures": "Diagnose and fix implementation failures autonomously, rerun affected checks, and continue. Escalate only unavailable essential evidence, unclear security invariants or unresolved material product/authority decisions; preserve work and record the exact blocker. Correct obsolete/incorrect test expectations only when the approved contract proves why; never bypass immutable domain state to get green tests.",
  "boundaries": "Keep public docs separate from runtime and the Task 53 portal file-based/read-only. Preserve default-deny auth, explicit permissions, ownership, provenance, expiry and legacy domain/execution contracts. Avoid unnecessary dependencies, silent replay/cloud fallback and self-granted authority.",
  "handoff": "Record task number, base/current checkpoint, exact reviewed scope, touched files, commands/results/skips, remaining limitations/decisions, uncommitted work and next task. Different implementations must satisfy the same contract; identical generated code is not guaranteed."
};

const futureRoadmapGroups = [
  { name: "Phase A - Install and Onboarding", range: "131-134", tasks: post100Tasks.filter(task => task.category === "Phase A - Install and Onboarding").map(({ title, description }) => [title, description]) },
  { name: "Phase B - Knowledge and RAG", range: "135-139", tasks: post100Tasks.filter(task => task.category === "Phase B - Knowledge and RAG").map(({ title, description }) => [title, description]) },
  { name: "Phase C - Capability Governance", range: "140-144", tasks: post100Tasks.filter(task => task.category === "Phase C - Capability Governance").map(({ title, description }) => [title, description]) },
  { name: "Phase D - Voice and Speech", range: "145-149", tasks: post100Tasks.filter(task => task.category === "Phase D - Voice and Speech").map(({ title, description }) => [title, description]) },
  { name: "Phase E - Vision", range: "150-155", tasks: post100Tasks.filter(task => task.category === "Phase E - Vision").map(({ title, description }) => [title, description]) },
  { name: "Phase F - Controlled Automation", range: "156-158", tasks: post100Tasks.filter(task => task.category === "Phase F - Controlled Automation").map(({ title, description }) => [title, description]) },
  { name: "Phase G - Command Center UI and Visualization", range: "159-162", tasks: post100Tasks.filter(task => task.category === "Phase G - Command Center UI and Visualization").map(({ title, description }) => [title, description]) },
  { name: "Phase H - ERSELMETZ AI Persona", range: "163-166", tasks: post100Tasks.filter(task => task.category === "Phase H - ERSELMETZ AI Persona").map(({ title, description }) => [title, description]) },
  { name: "Phase I - Productization and Stable Release", range: "167-170", tasks: post100Tasks.filter(task => task.category === "Phase I - Productization and Stable Release").map(({ title, description }) => [title, description]) },
  { name: "Phase J - Settings and Operator Controls", range: "171-171", tasks: post100Tasks.filter(task => task.category === "Phase J - Settings and Operator Controls").map(({ title, description }) => [title, description]) },
  { name: "Phase K - Interactive Maps and Visualization", range: "172-173", tasks: post100Tasks.filter(task => task.category === "Phase K - Interactive Maps and Visualization").map(({ title, description }) => [title, description]) },
  { name: "Phase L - Multimodal Interface and Usability", range: "174-175", tasks: post100Tasks.filter(task => task.category === "Phase L - Multimodal Interface and Usability").map(({ title, description }) => [title, description]) },
  { name: "Phase M - First-run Setup and Project Cleanup", range: "176-176", tasks: post100Tasks.filter(task => task.category === "Phase M - First-run Setup and Project Cleanup").map(({ title, description }) => [title, description]) },
  { name: "Phase N - Auto-RAG and Answer Tracing", range: "177-177", tasks: post100Tasks.filter(task => task.category === "Phase N - Auto-RAG and Answer Tracing").map(({ title, description }) => [title, description]) },
  { name: "Phase O - Navigation Reliability", range: "178-178", tasks: post100Tasks.filter(task => task.category === "Phase O - Navigation Reliability").map(({ title, description }) => [title, description]) },
  { name: "Phase P - Roadmap Maintenance", range: "179-179", tasks: post100Tasks.filter(task => task.category === "Phase P - Roadmap Maintenance").map(({ title, description }) => [title, description]) },
  { name: "Phase Q - Hardware-Aware Local Models", range: "180-180", tasks: post100Tasks.filter(task => task.category === "Phase Q - Hardware-Aware Local Models").map(({ title, description }) => [title, description]) },
  { name: "Phase R - Reviewed Model Routing", range: "181-181", tasks: post100Tasks.filter(task => task.category === "Phase R - Reviewed Model Routing").map(({ title, description }) => [title, description]) },
  { name: "Phase S - Reviewed Tool Use", range: "182-182", tasks: post100Tasks.filter(task => task.category === "Phase S - Reviewed Tool Use").map(({ title, description }) => [title, description]) },
  { name: "Phase T - Transparent Task Scaffolding", range: "183-183", tasks: post100Tasks.filter(task => task.category === "Phase T - Transparent Task Scaffolding").map(({ title, description }) => [title, description]) },
  { name: "Phase U - Persistence and Migration", range: "184-184", tasks: post100Tasks.filter(task => task.category === "Phase U - Persistence and Migration").map(({ title, description }) => [title, description]) },
  { name: "Phase V - Installation and Recovery", range: "185-185", tasks: post100Tasks.filter(task => task.category === "Phase V - Installation and Recovery").map(({ title, description }) => [title, description]) },
  { name: "Phase W - Interactive 3D Map", range: "186-186", tasks: post100Tasks.filter(task => task.category === "Phase W - Interactive 3D Map").map(({ title, description }) => [title, description]) },
  { name: "Phase X - Voice Interaction", range: "187-188", tasks: post100Tasks.filter(task => task.category === "Phase X - Voice Interaction").map(({ title, description }) => [title, description]) },
  { name: "Phase Y - Local Vision", range: "189-189", tasks: post100Tasks.filter(task => task.category === "Phase Y - Local Vision").map(({ title, description }) => [title, description]) },
  { name: "Phase Z - Code Execution Design Gate", range: "190-190", tasks: post100Tasks.filter(task => task.category === "Phase Z - Code Execution Design Gate").map(({ title, description }) => [title, description]) },
  { name: "Phase AA - Direct-to-chat Quick Start", range: "191-191", tasks: post100Tasks.filter(task => task.category === "Phase AA - Direct-to-chat Quick Start").map(({ title, description }) => [title, description]) },
  { name: "Phase AB - Real-world Verification", range: "192-192", tasks: post100Tasks.filter(task => task.category === "Phase AB - Real-world Verification").map(({ title, description }) => [title, description]) },
  { name: "Phase AC - Structured Chat and Desktop Experience", range: "193-193", tasks: post100Tasks.filter(task => task.category === "Phase AC - Structured Chat and Desktop Experience").map(({ title, description }) => [title, description]) },
  { name: "Phase AD - Chat Prompt Correctness", range: "194-194", tasks: post100Tasks.filter(task => task.category === "Phase AD - Chat Prompt Correctness").map(({ title, description }) => [title, description]) },
  { name: "Phase AE - Minimal Chat Experience", range: "195-195", tasks: post100Tasks.filter(task => task.category === "Phase AE - Minimal Chat Experience").map(({ title, description }) => [title, description]) },
  { name: "Phase AF - Brain and Retrieval", range: "196-196", tasks: post100Tasks.filter(task => task.category === "Phase AF - Brain and Retrieval").map(({ title, description }) => [title, description]) },
  { name: "Phase AG - Brain Visualization", range: "197-197", tasks: post100Tasks.filter(task => task.category === "Phase AG - Brain Visualization").map(({ title, description }) => [title, description]) },
  { name: "Phase AH - Multimodal Packs", range: "198-198", tasks: post100Tasks.filter(task => task.category === "Phase AH - Multimodal Packs").map(({ title, description }) => [title, description]) },
  { name: "Phase AI - Owner-Gated Automation", range: "199-199", tasks: post100Tasks.filter(task => task.category === "Phase AI - Owner-Gated Automation").map(({ title, description }) => [title, description]) },
  { name: "Phase AJ - Built-in Agent Team", range: "200-200", tasks: post100Tasks.filter(task => task.category === "Phase AJ - Built-in Agent Team").map(({ title, description }) => [title, description]) },
  { name: "Phase AK - Agents Workspace", range: "201-201", tasks: post100Tasks.filter(task => task.category === "Phase AK - Agents Workspace").map(({ title, description }) => [title, description]) },
  { name: "Phase AL - Agent Delegation and Approvals", range: "202-202", tasks: post100Tasks.filter(task => task.category === "Phase AL - Agent Delegation and Approvals").map(({ title, description }) => [title, description]) },
  { name: "Phase AM - Sage Core Visualization", range: "203-203", tasks: post100Tasks.filter(task => task.category === "Phase AM - Sage Core Visualization").map(({ title, description }) => [title, description]) },
  { name: "Phase AN - Agent Runtime", range: "207-207", tasks: post100Tasks.filter(task => task.category === "Phase AN - Agent Runtime").map(({ title, description }) => [title, description]) },
  { name: "Phase AO - Auto-routing", range: "208-208", tasks: post100Tasks.filter(task => task.category === "Phase AO - Auto-routing").map(({ title, description }) => [title, description]) },
  { name: "Phase AP - Autonomy controls", range: "209-209", tasks: post100Tasks.filter(task => task.category === "Phase AP - Autonomy controls").map(({ title, description }) => [title, description]) },
  { name: "Phase AQ - Tool-calling quality", range: "210-210", tasks: post100Tasks.filter(task => task.category === "Phase AQ - Tool-calling quality").map(({ title, description }) => [title, description]) },
  { name: "Phase AR - Runtime evaluation", range: "211-211", tasks: post100Tasks.filter(task => task.category === "Phase AR - Runtime evaluation").map(({ title, description }) => [title, description]) },
  ...[
    [213, "Phase AS - UI Foundation"], [214, "Phase AT - Window Architecture"],
    [215, "Phase AU - Workspace Sessions"], [216, "Phase AV - Concurrency and Resources"],
    [217, "Phase AW - Multi-window QA"],
  ].map(([number, name]) => ({ name, range: `${number}-${number}`,
    tasks: post100Tasks.filter(task => task.category === name).map(({ title, description }) => [title, description]) }))
];

export const taskGroups = [...foundationTaskGroups, {
  name: "Post-100 Usable Command Center",
  range: "101-130",
  tasks: post100Tasks.filter(task => task.number <= 130).map(({ title, description }) => [title, description]),
}, ...futureRoadmapGroups];
export const tasks = [...foundationTasks, ...post100Tasks];
export const recommendedOrder = [
  { number: 178, reason: "Complete the navigation acceptance gate before asking owners to test the setup journey." },
  { number: 176, reason: "Verify fresh-profile install, provider setup, restart, and recovery before building on onboarding." },
  { number: 177, reason: "Accept RAG and factual traces before routing, tools, and visible multi-step work depend on them." },
  { number: 175, reason: "Evaluate complete user journeys after the setup, navigation, and chat foundations have automated acceptance evidence." },
  { number: 180, reason: "Establish truthful hardware observations before recommending local model sizes." },
  { number: 184, reason: "Define durable state and migrations before adding more operator preferences and long-lived workflows." },
  { number: 181, reason: "Use accepted RAG traces and hardware facts to make consent-based route suggestions." },
  { number: 182, reason: "Add only reviewed, bounded tools with visible trace evidence and explicit side-effect approval." },
  { number: 183, reason: "Compose retrieval and reviewed tools into visible steps backed by real events." },
  { number: 185, reason: "Finalize distribution, opt-in updates, uninstall, and local recovery controls after data behavior is defined." },
  { number: 186, reason: "Build the optional 3D map only after factual traces and performance/accessibility limits are established." },
  { number: 187, reason: "Add opt-in local speech input after settings and persistence can retain its controls safely." },
  { number: 188, reason: "Add speech output after input controls and their consent/privacy pattern are verified." },
  { number: 189, reason: "Gate image transfer on hardware evidence and reviewed provider-routing consent." },
  { number: 190, reason: "Keep code execution at a design-only security gate until its sandbox and owner controls are reviewed." },
  { number: 192, reason: "Measure real local behavior and report evidence separately from automated fixtures before considering product enhancements." },
  { number: 193, reason: "Deliver structured provider messages and an accessible chat surface; its prompt-routing closure is tracked by Task 194." },
  { number: 194, reason: "Prove every chat route excludes request envelopes and the opened desktop build matches the tested source." },
  { number: 195, reason: "Simplify the actual Electron chat surface after its route, initialization failure, and direct-to-chat behavior are understood." },
  { number: 196, reason: "Establish durable, owner-controlled Brain ingestion and cited retrieval before visualizing or expanding multimodal capabilities." },
  { number: 197, reason: "Visualize only real Brain data after the underlying documents, chunks and retrieval events exist." },
  { number: 198, reason: "Add independently tested, opt-in local Eyes/Ears/Voice packs after the Brain and consent surfaces are established." },
  { number: 199, reason: "Extend reviewed browser/desktop actions only after their exact approvals, audit traces and stop controls are in place." },
  { number: 200, reason: "Create the role profiles and shared local capacity boundary before adding Agent UI or delegation." },
  { number: 201, reason: "Expose existing Agent identities and owner controls before connecting them through chat." },
  { number: 202, reason: "Add bounded, traced handoffs and approvals before any live team visualization implies work." },
  { number: 203, reason: "Render only the real profiles, approvals, states and traces delivered by the earlier phases." },
  { number: 207, reason: "Establish one bounded, traced execution boundary before automatic routing or autonomy controls." },
  { number: 208, reason: "Route only supported requests to tools and keep all uncertain classification on direct chat." },
  { number: 209, reason: "Make safe-read defaults explicit while reusing owner approvals, cloud consent and the emergency stop." },
  { number: 210, reason: "Measure provider-supported tool calling and constrain small-model output before enabling broader use." },
  { number: 211, reason: "Use real local task results to gate agent mode instead of assuming model quality." },
  { number: 213, reason: "Establish consistent accessible screens and visual evidence before adding window complexity." },
  { number: 214, reason: "Secure one-process/one-backend window lifecycle before introducing workspace identity." },
  { number: 215, reason: "Isolate conversations, selections, approvals and project knowledge before concurrent operation." },
  { number: 216, reason: "Coordinate shared model/device capacity and stop controls before real parallel-window evaluation." },
  { number: 217, reason: "Measure actual multi-window behavior after isolation and resource coordination are implemented." }
];
export const nextTask = recommendedOrder.map(({ number }) => post100Tasks.find(task => task.number === number)).find(task => task?.status === "planned")
  ?? post100Tasks.find(task => task.status === "planned");

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
      ["ERSELMETZ AI CORPORATION Platform", "Develop a coherent, governed platform for operating a virtual/simulated AI organization."]
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
    "status": "planned",
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
    "decisions": [
      "Choose snapshot/event freshness and retention contracts before introducing live event infrastructure."
    ],
    "area": "P07b",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 116,
    "title": "Accessible Jarvis-style visualization",
    "description": "Add a Three.js 3D-first corporation/workflow presentation over the validated maps.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 117,
    "title": "Owned knowledge and chat context controls",
    "description": "Expose supported knowledge retention/retrieval controls and source traces in owner-scoped conversations.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 118,
    "title": "Durable conversation history and recovery",
    "description": "Add explicitly consented durable conversation history with truthful restart and interrupted-turn behavior.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Approve storage, retention/expiry, encryption needs, migrations and uncertain-outcome recovery contract."
    ],
    "area": "P02c / P08",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 119,
    "title": "Local model resource and loading controls",
    "description": "Expose configured budgets and supported model loading controls with actual hardware/runtime evidence.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Approve telemetry access, load/unload semantics and any runtime/resource contract extension."
    ],
    "area": "P09",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 120,
    "title": "Supported streaming and truthful Stop controls",
    "description": "Extend provider/chat contracts only where validated streaming or cancellation is supported.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
    "dependsOn": [
      103,
      119
    ],
    "acceptance": [
      "Show token/chunk progress only from actual streamed output and handle partial/final failure.",
      "Distinguish stopping UI display from confirmed provider/tool cancellation.",
      "Preserve history/lifecycle, ownership and bounded buffers on disconnect or timeout.",
      "Test partial streams, unsupported providers and cancellation races with deterministic fakes."
    ],
    "outOfScope": [
      "Calling a timeout or closed browser tab proof that external execution stopped."
    ],
    "decisions": [
      "Approve provider streaming/cancellation interfaces and partial-turn persistence before coding."
    ],
    "area": "P02d",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 121,
    "title": "Chat-driven GitHub study and research",
    "description": "Accept a scoped repository request and produce a source-linked adoption assessment through existing discovery/research services.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
    "dependsOn": [
      103,
      113
    ],
    "acceptance": [
      "Pin inspected revision and explicit repository/host scope; bound retrieval and research.",
      "Report license, dependencies, fit, risks and unknowns with traceable evidence.",
      "External code/docs are untrusted and cannot expand permissions or override policy.",
      "Return proposal, separate-tool option, rejection or information request without installation."
    ],
    "outOfScope": [
      "Automatic downloads/execution, source instructions authorizing actions or model retraining claims."
    ],
    "decisions": [
      "Approve any new external retrieval/search adapters and their allowed scope before use."
    ],
    "area": "P10",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 122,
    "title": "Isolated adaptation workspace and validation",
    "description": "Develop a selected authorized adaptation in a disposable isolated work area using existing maintenance stages.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Approve experiment tools, sandbox policy and source/patch authorization contract."
    ],
    "area": "P11a",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 123,
    "title": "Approved integration and verified recovery",
    "description": "Apply an exact owner-approved adaptation through bounded change control and verify the active result.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
    "dependsOn": [
      122
    ],
    "acceptance": [
      "Revalidate source/patch/test/review/approval links before applying the change.",
      "Show affected code/configuration/dependencies/data and create supported checkpoints.",
      "Verify actual activation; show failure/uncertainty and tested recovery scope.",
      "Test stale approvals, partial failures and inability to reverse external actions.",
      "Activate only the exact owner-approved artifact after passing scoped tests and independent review; verify restart/health and offer only recovery steps that were actually tested.",
      "Self-maintenance may improve software, workflows or explicitly approved memory; it never automatically trains or changes model weights."
    ],
    "outOfScope": [
      "Self-expanding authority, unrestricted self-modification or universal rollback guarantees."
    ],
    "decisions": [
      "Approve activation/deployment scope, per-artifact gates and recovery ownership; website deployment is a separate explicit action."
    ],
    "area": "P11b",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 124,
    "title": "Software and integration inventory panel",
    "description": "Show supported installed applications, repository checkouts, integrations and service versions as separate records.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Approve initial inventory adapters and local inspection scopes."
    ],
    "area": "P12a",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 125,
    "title": "Managed install update version and remove",
    "description": "Manage one explicitly supported software adapter with preview, permission checks and data-preserving recovery.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Select the first supported application/package manager; Git and VS Code are candidates. Approve install/update/removal and privilege boundaries."
    ],
    "area": "P12b",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 126,
    "title": "One-click local application lifecycle",
    "description": "Provide a supported startup/health/stop/restart flow for the existing Python backend and Web UI.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Approve OS process ownership and startup credential-entry behavior."
    ],
    "area": "P01b / P13a",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 127,
    "title": "Windows executable and installer",
    "description": "Package the shared Web UI and Python backend into an owner-approved desktop distribution.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Owner selected Electron as the Windows shell and Next.js static export for the JavaScript/TypeScript UI; Python remains the backend and AI orchestration layer. Define licensing, signing/update trust, credential storage and installer/data lifecycle before release."
    ],
    "area": "P13b",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 128,
    "title": "Optional voice interaction",
    "description": "Add explicitly enabled speech input/output while preserving typed chat and the same action gates.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
    "dependsOn": [
      127
    ],
    "acceptance": [
      "Visible microphone/recording controls and clear start/stop behavior.",
      "Offer explicit local or cloud speech processing choices with per-use consent, an enforced cloud spend ceiling and configured retention; local processing is the default where supported.",
      "Spoken requests use identical authorization/approval checks; typed chat remains fully usable.",
      "Test microphone denial, disabled voice, errors and sensitive-content handling.",
      "Let the owner interrupt capture, playback and speech requests; distinguish stopping local recording/audio from confirmed provider cancellation, and never report unconfirmed remote cancellation as successful.",
      "Test interruption at capture, transcription, model generation and playback stages, including providers without cancellation support and quota/budget exhaustion."
    ],
    "outOfScope": [
      "Always-on recording or voice bypassing action approval."
    ],
    "decisions": [
      "Resolve supported speech adapters and interruption/cancellation semantics per provider; never enable always-on recording or cloud speech without explicit consent and a configured ceiling."
    ],
    "area": "P14",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 129,
    "title": "Command center usability and release acceptance",
    "description": "Verify the supported owner workflows on a clean local installation and publish actual readiness evidence.",
    "category": "Post-100 Usable Command Center",
    "status": "planned",
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
      "Owner agrees the release acceptance environment, supported capabilities and remaining deferred areas."
    ],
    "area": "Release acceptance",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  }
];

export const roadmapRules = {
  "scope": "Publishing task contracts does not implement planned capabilities or grant runtime authority. Implement only the current authorized task after resolving its owner decision gates; credentials, installations, model calls and deployment actions require their own authorized scope.",
  "source": "Read docs/tasks-data.mjs, docs/tasks.html and the relevant existing code before implementing a task. Post-100 scope/status comes from post100Tasks; broader P00-P15 material is supplementary.",
  "sequence": "Resume preserved work; inspect git status and current checkpoint first. Use one reviewed task checkpoint at a time; do not start later behavior early or overwrite another AI's work.",
  "decisions": "Planned means proposed work. Record owner approval for unresolved product/architecture/authority decisions before dependent code. Do not infer approval from a status change or generated text.",
  "verification": "Run focused and directly affected regressions, then the full Python suite for runtime changes as appropriate. Run browser/docs tests for those changes; use deterministic fakes and separate optional live integration checks. Run compilation/type checks where available and diff/security/scope review.",
  "completion": "Completed requires actual acceptance evidence, truthful limitations/skips, required documentation/update records, and a reviewed task checkpoint. Verify pushed HEAD matches origin/main and the working tree is clean. Never mark complete solely because code exists or an AI says it worked.",
  "failures": "Preserve work and stop on genuine implementation failures, unclear security invariants, roadmap ambiguity or material architectural decisions. Correct obsolete/incorrect test expectations only when the approved contract proves why; never bypass immutable domain state to get green tests.",
  "boundaries": "Keep public docs separate from runtime and the Task 53 portal file-based/read-only. Preserve default-deny auth, explicit permissions, ownership, provenance, expiry and legacy domain/execution contracts. Avoid unnecessary dependencies, silent replay/cloud fallback and self-granted authority.",
  "handoff": "Record task number, base/current checkpoint, exact reviewed scope, touched files, commands/results/skips, remaining limitations/decisions, uncommitted work and next task. Different implementations must satisfy the same contract; identical generated code is not guaranteed."
};

export const taskGroups = [...foundationTaskGroups, {
  name: "Post-100 Usable Command Center",
  range: "101–129",
  tasks: post100Tasks.map(({ title, description }) => [title, description]),
}];
export const tasks = [...foundationTasks, ...post100Tasks];
export const nextTask = post100Tasks.find((task) => task.status !== "completed");

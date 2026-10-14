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
      "Dashboard, visualization, and camera browser-module regressions: 20 passed; public documentation tests: 13 passed. Full Python suite excluding the baseline-invalid tests/test_automation_traces.py: 1214 passed, 5 skipped, with the two previously recorded unrelated model-assignment failures. The unfiltered full-suite run stops at collection on that file?s existing `rom __future__` syntax error. Changed Python tests compile; git diff --check passed."
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
    "status": "planned",
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
    "decisions": [],
    "area": "P27",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 174,
    "title": "Unified multimodal capability controls and indicators",
    "description": "Integrate governed voice, vision, screen, camera, and automation status into a clear owner-facing control and activity surface.",
    "category": "Phase L - Multimodal Interface and Usability",
    "status": "planned",
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
    "checkpoint": null,
    "validation": [],
    "limitations": []
  },
  {
    "number": 175,
    "title": "End-user usability and accessibility evaluation",
    "description": "Evaluate the finished user journeys with evidence from beginner setup, everyday chat, operator controls, and organization/knowledge views.",
    "category": "Phase L - Multimodal Interface and Usability",
    "status": "planned",
    "dependsOn": [
      132,
      133,
      159,
      160,
      171,
      172,
      173,
      174
    ],
    "acceptance": [
      "Test first-run readiness, basic chat, provider/model configuration, permission review, troubleshooting, and navigation with representative new and experienced owners.",
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
      "Task 134 is deferred and excluded from the supported user journeys; the UI must describe packs as unavailable until their trust and loading boundaries are implemented."
    ],
    "area": "P28",
    "checkpoint": null,
    "validation": [],
    "limitations": []
  }
];

export const roadmapRules = {
  "scope": "Publishing task contracts does not implement planned capabilities or grant runtime authority. Implement only the current authorized task after resolving its owner decision gates; credentials, installations, model calls and deployment actions require their own authorized scope.",
  "source": "Read docs/tasks-data.mjs, docs/tasks.html and the relevant existing code before implementing a task. Post-100 scope/status comes from post100Tasks; completed, deferred, and planned states are distinct. Tasks 134 and 170 are deferred and incomplete; Tasks 135-169 are verified; Task 172 is complete and Task 173 is next; Tasks 173-175 remain planned expansion contracts grouped by capability phase; P00-P16 remains supplementary product context.",
  "sequence": "Resume preserved work; inspect git status and current checkpoint first. Use one reviewed task checkpoint at a time; do not start later behavior early or overwrite another AI's work.",
  "decisions": "Planned means proposed work. Record owner approval for unresolved product/architecture/authority decisions before dependent code. Do not infer approval from a status change or generated text.",
  "verification": "Run focused and directly affected regressions, then the full Python suite for runtime changes as appropriate. Run browser/docs tests for those changes; use deterministic fakes and separate optional live integration checks. Run compilation/type checks where available and diff/security/scope review.",
  "completion": "Completed requires actual acceptance evidence, truthful limitations/skips, required documentation/update records, and a reviewed task checkpoint. Verify pushed HEAD matches origin/main and the working tree is clean. Never mark complete solely because code exists or an AI says it worked.",
  "failures": "Preserve work and stop on genuine implementation failures, unclear security invariants, roadmap ambiguity or material architectural decisions. Correct obsolete/incorrect test expectations only when the approved contract proves why; never bypass immutable domain state to get green tests.",
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
  { name: "Phase L - Multimodal Interface and Usability", range: "174-175", tasks: post100Tasks.filter(task => task.category === "Phase L - Multimodal Interface and Usability").map(({ title, description }) => [title, description]) }
];

export const taskGroups = [...foundationTaskGroups, {
  name: "Post-100 Usable Command Center",
  range: "101-130",
  tasks: post100Tasks.filter(task => task.number <= 130).map(({ title, description }) => [title, description]),
}, ...futureRoadmapGroups];
export const tasks = [...foundationTasks, ...post100Tasks];
export const nextTask = post100Tasks.find((task) => task.status === "planned");

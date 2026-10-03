export const taskGroups = [
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
export const tasks = taskGroups.flatMap((group) =>
  group.tasks.map(([title, description]) => {
    const number = nextNumber++;
    return {
      number,
      title,
      description,
      category: group.name,
      status: number <= 88 ? "completed" : "planned",
    };
  })
);

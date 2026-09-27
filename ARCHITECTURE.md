# ERSELMETZ AI CORPORATION — Current Architecture and Roadmap

## Product definition

**ERSELMETZ AI CORPORATION is an actual software system implementing a virtual/simulated AI organization.** “Virtual/simulated organization” describes the domain being modeled; it does not mean that the software system itself is imaginary.

This document separates the implemented Tasks 1–27 foundation from future architecture. Source code is authoritative if implementation and documentation disagree.

## Implemented system at a glance

```text
Command interface
      │
      ▼
Orchestrator ─────────── task logs
      │
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

The intended future progression remains Discovery → Analysis/Learning → Evaluation → Integration Design → Sandbox → Implementation → Testing → Review → Approval → Integration → Monitoring. Task 27 implements only public GitHub information discovery. Proposals remain a separate domain rather than being represented as Tasks or passed through the Task Router.

## Tasks 1–27 completion scope

Tasks 1–27 are complete as the current foundation. Their implemented areas include:

1. Task and Project domain/registry foundations.
2. Task lifecycle, orchestration, logging, and SQLite persistence.
3. Agent, Employee, Provider, and Model domain boundaries.
4. Agent capability lookup and Employee-role lookup.
5. Ollama execution integration and Provider interface.
6. Employee and Provider management foundations.
7. Model assignment/replacement management for the in-memory Agent.
8. Tool abstraction and registry foundation.
9. Human approval request/status foundation.
10. Client request validation and business-layer Task translation.
11. Corporation and Node identity models and registries.
12. Runtime identity configuration, context validation, and startup wiring.
13. Interactive Corporation command interface and management/listing commands.
14. Deterministic explicit-Agent, role, and capability routing.
15. Dry-run execution and CLI routing options.
16. Persistent role/capability requirements with additive SQLite migration and reload.
17. Integration source/proposal models, controlled lifecycle, proposal registry, and approval-gated execution record foundation.
18. Public GitHub repository metadata discovery through a source-adapter abstraction.

This is a grouped capability summary, not a claim that every long-term capability is production-complete. See limitations above; particularly, project ID persistence is incomplete, registry/configuration persistence is limited, tools and approvals are not wired to task execution, integration proposals are not persisted, there is no integration executor, and only Ollama is implemented as a provider.

## Future / planned roadmap

None of the following should be represented as implemented until code provides it:

- Richer workflow orchestration, dependency scheduling, and multi-Agent collaboration.
- AI-based, semantic, or policy-aware task routing; dynamic selection and advanced Provider/Model selection.
- Agent-to-Agent communication.
- Additional Provider integrations beyond Ollama.
- Durable organization, Agent, Employee, Provider, and model configuration management.
- A Software Reliability Engineer / QA guardian and richer evaluation.
- Authentication, authorization, encryption, and permission enforcement.
- Offline Mode, durable queues, synchronization, and conflict resolution.
- Node discovery and networking among independent Corporation installations.
- Richer Tool and MCP integration, concrete tools, and controlled tool execution.
- Open-source coding/editing, repository mapping, terminal, browser/computer-control, voice, and Git/GitHub workflow integrations.
- Git/GitHub automation.
- Controlled self-improvement and a sandbox/evaluation pipeline.
- External integration stages beyond Task 27 discovery: analyze/learn, evaluate, design, sandbox, implement, test, review, approval orchestration, integrate, and monitor.

### Open-source ecosystem direction

ERSELMETZ AI CORPORATION should not unnecessarily recreate mature open-source agent and coding infrastructure. Its intended role is the **governance + organization + orchestration + identity + task management + routing + approval + coordination layer**. Suitable existing projects, protocols, and tools may be integrated for specialized coding/editing, repository mapping, terminal execution, browser/computer interaction, MCP/tool integration, voice/computer control, and Git/GitHub workflows. Such examples describe a direction only; no such integration is implied to exist today.

### Controlled self-improvement

The intended future improvement path is:

**Discovery → Analysis/Learning → Evaluation → Integration Design → Sandbox → Implementation → Testing → Review → Approval → Integration → Monitoring**

Unrestricted autonomous self-modification is **not** the current design. Future changes must be controlled, testable, auditable, and subject to appropriate approval boundaries.

The `IntegrationCapability` enum defines possible request scopes: `READ_SOURCE`, `ANALYZE_SOURCE`, `RUN_SANDBOX`, `WRITE_PROJECT`, `RUN_TESTS`, `REQUEST_APPROVAL`, and `INTEGRATE`. Execution records can describe requested scopes, but Task 26 grants or enforces none of them; delete, commit, and push authority are not provided by the integration foundation. Human/orchestrator approval must remain explicit before any future integration execution.

## Development rule

Before implementing a future milestone, inspect the actual implementation and tests for the affected area. Treat this architecture as a description of current behavior plus clearly labeled direction—not as evidence that planned behavior already exists.

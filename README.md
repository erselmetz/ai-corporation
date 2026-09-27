# ERSELMETZ AI CORPORATION

**ERSELMETZ AI CORPORATION is an actual software system implementing a virtual/simulated AI organization.** The organization is the system's domain model and operating concept; the software implements its current capabilities.

The current application is a local Python command-line system. It models a Corporation and installation Node, an Orchestrator, Employees, technical Agents, a Provider/Model execution boundary, persisted Tasks, deterministic routing, and dry-run inspection.

> **Implementation status:** Tasks 1–27 are complete as foundations. Task 27 adds public GitHub metadata discovery, not the long-term integration/adaptation pipeline. Future work is explicitly identified below and in [ARCHITECTURE.md](./ARCHITECTURE.md).

## Current architecture

```text
Corporation identity
└── Node / installation identity
    └── Runtime Context (validated Corporation + Node IDs)

CLI / client request
└── Orchestrator
    ├── Task lifecycle and logs
    └── Task Router
        └── Employee role or Agent capability / explicit Agent
            └── Agent
                └── Provider (currently Ollama)
                    └── Model (configured on the Agent)

SQLite: tasks, projects, task logs, agent memory, project memory
```

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

Important current limits:

- Startup configures one local Corporation, one Node, one Employee/Agent, and an Ollama Provider in code. Corporation, Node, Employee, Agent, Provider, and model-management state is not generally persisted as an administration/configuration system.
- The CLI task execution path can invoke the configured Ollama model. Dry-run does not invoke it.
- Tool definitions are not connected to Agents, permissions are not enforced by a tool-execution policy, and there are no concrete built-in tools.
- Approval requests are in-memory only and are not connected to task actions or execution gates.
- Integration proposals and execution records are in-memory only. GitHub discovery collects metadata and a bounded README excerpt only; it does not clone repositories, analyze code semantically, sandbox execution, write project files, or execute integrations.
- The client/business layer is a small API-level adapter, not an HTTP server or a fully integrated external intake workflow.
- `TaskRegistry` currently does not persist or reload `Task.project_id`. This known persistence gap remains.
- Networking, discovery, authentication, authorization, encryption, synchronization, and offline queueing are not implemented.

## Completed and planned work

**Completed:** Tasks 1–27 established the software/domain foundation: task and project management, Agents, Employees, Provider/Model boundaries and management, orchestration and lifecycle logging, tool and approval foundations, client/business request translation, Corporation/Node identity and runtime validation, the command interface, deterministic routing, dry-run, persisted role/capability requirements, the Integration Proposal lifecycle/approval boundary foundation, and public GitHub source discovery.

**Future / planned:** semantic analysis/learning; project evaluation; integration design; sandboxing; implementation; testing; review; approval workflow; controlled integration; monitoring; richer orchestration; AI-based or semantic routing; advanced Provider/Model selection; multi-Agent collaboration and Agent-to-Agent communication; independent-installation networking and Node Discovery; Authentication, Authorization, and Encryption; Offline Mode, Synchronization, and Conflict Resolution; a Software Reliability Engineer / QA guardian; controlled self-improvement with sandbox/evaluation; open-source ecosystem integrations; Git/GitHub workflow automation; and richer Tool/MCP integration.

Task 26 adds internal proposal/source/lifecycle models, an in-memory proposal registry, and a record-only execution object that requires an approved proposal. Task 27 adds public GitHub metadata discovery. Discovery validates HTTPS GitHub repository URLs and uses only fixed `api.github.com` REST endpoints; it does not clone, execute, install, analyze, or integrate repository contents. Proposals and execution records remain in memory, and discovery grants no permissions or approval.

### Open-source ecosystem direction

The Corporation should not unnecessarily reinvent mature open-source agent and coding infrastructure. Its intended role is the **governance, organization, orchestration, identity, task management, routing, approval, and coordination layer**. Where appropriate, existing projects and protocols may provide specialized coding/editing, repository mapping, terminal execution, browser/computer interaction, MCP/tool integration, voice/computer control, and Git/GitHub workflows. These are integration directions, not claims of current integration.

### Controlled self-improvement direction

Future improvement should follow a controlled path:

**Discovery → Analysis/Learning → Evaluation → Integration Design → Sandbox → Implementation → Testing → Review → Approval → Integration → Monitoring**

Unrestricted autonomous self-modification is not the current design. Any future improvement mechanism must be controlled, testable, auditable, and subject to appropriate approval boundaries.

## Documentation

- [Architecture and roadmap](./ARCHITECTURE.md)
- [Visual architecture overview](./docs/index.html)

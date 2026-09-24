# ERSELMETZ AI CORPORATION

An AI-assisted software engineering orchestration platform designed to coordinate multiple AI agents, providers, projects, tasks, memory, and future development workflows.

The goal is to evolve this system into an **AI Corporation** capable of managing software-development workflows through specialized AI agents while keeping the human as the final decision-maker and approval authority.

---

## Vision

The long-term vision is to build a multi-agent software engineering organization where different AI agents have specialized responsibilities.

```text
                         👨‍💻 YOU
                    CEO / PRODUCT OWNER
                           │
                           ▼
                  🏢 AI CORPORATION
                           │
                    ┌──────┴──────┐
                    │ ORCHESTRATOR│
                    │   / Manager │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   🧠 ARCHITECT        🔬 R&D             📋 PM
    AI Agent          AI Agent          AI Agent
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                  💻 ENGINEERING
                    Developer Agent
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
              🧪 QA              🛡️ SECURITY
             AI Agent             AI Agent
                 │                   │
                 └─────────┬─────────┘
                           ▼
                    👀 CODE REVIEW
                       AI Agent
                           │
                           ▼
                    🔀 Git / GitHub
                           │
                           ▼
                    👨‍💻 HUMAN APPROVAL
```

---

## Current Status

The project is currently in the **core orchestration foundation stage**.

### Implemented

* Agent abstraction
* Agent registry
* AI provider abstraction
* Provider registry
* Ollama provider
* Task creation
* Task execution
* Task status management
* Persistent SQLite database
* Task persistence
* Task execution audit logging
* Agent memory
* Project memory
* Project abstraction
* Project registry
* Persistent project storage
* Project → Task relationships
* Existing database migration support

### Current Architecture

```text
AI Corporation
       │
       ▼
Orchestrator
       │
 ┌─────┼─────┐
 ▼     ▼     ▼
Agents Providers Projects
 │       │       │
 ▼       ▼       ▼
Memory  Ollama  Tasks
                 │
                 ▼
               SQLite
```

---

## Project Structure

```text
ai-corporation/
│
├── app/
│   ├── orchestrator/
│   │   ├── orchestrator.py
│   │   ├── task.py
│   │   ├── task_registry.py
│   │   ├── project.py
│   │   └── project_registry.py
│   │
│   ├── agents/
│   │   ├── agent.py
│   │   └── registry.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── ollama.py
│   │   └── registry.py
│   │
│   ├── memory/
│   │   ├── store.py
│   │   └── project_store.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── init.py
│   │   └── logger.py
│   │
│   └── main.py
│
├── projects/
├── tasks/
├── knowledge/
├── logs/
├── tests/
├── config/
│
├── .env
├── .gitignore
├── README.md
└── requirements.txt
│
├── Dockerfile
├── compose.yaml
└── .dockerignore
```

---

## Agents

Agents represent specialized AI workers.

An agent currently contains:

* ID
* Name
* Role
* Provider
* Model
* Capabilities
* Permissions

Example:

```text
Local Worker
├── Provider: Ollama
├── Model: llama3.2:3b
├── Capabilities
│   ├── text_generation
│   ├── summarization
│   └── classification
└── Permissions
    └── read_files
```

Agents can also maintain persistent memory.

---

## AI Providers

AI providers are abstracted behind a common interface.

Current provider:

```text
Ollama
└── llama3.2:3b
```

The provider abstraction is designed so additional AI providers can be added later without changing the core orchestration architecture.

Potential future providers include cloud and local AI services.

---

## Tasks

Tasks represent units of work inside the corporation.

A task contains:

```text
Task
├── ID
├── Title
├── Description
├── Project
├── Assigned Agent
├── Status
├── Result
└── Error
```

Supported statuses:

```text
PENDING
RUNNING
COMPLETED
FAILED
```

Tasks are persisted in SQLite and survive application restarts.

---

## Projects

Projects provide a higher-level container for tasks.

Example:

```text
PROJECT-001
└── AI Corporation Internal
```

Tasks can belong to a project:

```text
PROJECT-001
│
├── TASK-001
├── TASK-002
├── TASK-003
└── TASK-004
```

Projects are persisted in SQLite.

Existing tasks created before project support may have:

```text
project_id = NULL
```

New tasks can be associated with a project.

---

## Memory

The system currently supports two memory scopes.

### Agent Memory

Agent-specific persistent memory:

```text
Agent
└── Memory
    ├── key
    ├── value
    └── timestamp
```

Supported operations:

* Remember
* Recall
* Forget
* List memories

### Project Memory

Project-specific persistent memory:

```text
Project
└── Memory
    ├── key
    ├── value
    └── timestamp
```

This allows future agents to share persistent project context without storing everything inside individual prompts.

---

## Audit Logging

Task execution is recorded in the database.

Current events include:

```text
TASK_CREATED
TASK_STARTED
TASK_COMPLETED
TASK_FAILED
```

Example:

```text
TASK_CREATED
      ↓
TASK_STARTED
      ↓
TASK_COMPLETED
```

This provides an execution history that can later be used for debugging, monitoring, reporting, and workflow analysis.

---

## Database

The current database implementation uses SQLite.

Database location:

```text
projects/ai_corporation.db
```

Current major tables:

```text
tasks
task_logs
projects
agent_memory
project_memory
```

Database initialization also contains migration logic so existing databases can receive newly introduced columns without requiring manual database recreation.

---

## Current Execution Flow

The current system can perform the following:

```text
Application
    │
    ▼
Initialize Database
    │
    ▼
Load Providers
    │
    ▼
Load Agents
    │
    ▼
Load Projects
    │
    ▼
Load Tasks
    │
    ▼
Create Task
    │
    ▼
Assign Project
    │
    ▼
Assign Agent
    │
    ▼
Execute Task
    │
    ▼
AI Provider
    │
    ▼
Ollama
    │
    ▼
Store Result
    │
    ▼
Audit Log
```

---

## Long-Term Roadmap

The following components are planned but are **not yet considered implemented**.

### 1. Project-aware Task Management

* Retrieve tasks by project
* Task filtering
* Task dependencies
* Project task dashboards

### 2. Advanced Orchestration

* Intelligent agent selection
* Task routing
* Agent delegation
* Execution policies
* Retry handling

### 3. Workflow Engine

The system will eventually support workflows such as:

```text
User Request
     ↓
Planning
     ↓
Research
     ↓
Implementation
     ↓
Testing
     ↓
Security Review
     ↓
Code Review
     ↓
Fix
     ↓
Re-test
     ↓
Human Approval
```

### 4. Multi-Agent Collaboration

Agents will eventually be able to communicate through controlled task handoffs.

```text
Architect
    ↓
Research
    ↓
Developer
    ↓
QA
    ↓
Security
    ↓
Reviewer
```

### 5. Tool System

Agents will eventually receive controlled access to tools such as:

```text
read_file
write_file
search_code
run_command
run_tests
git_diff
git_status
```

Tool permissions will determine which agents can perform which operations.

### 6. Developer Integration

The long-term development workflow will integrate the developer agent with the local development environment.

The intended model is:

```text
Orchestrator
      ↓
Developer Agent
      ↓
Development Environment
      ↓
Project Files
```

Only authorized development agents should receive write access to project files.

### 7. QA and Security Agents

Dedicated agents will inspect changes and produce structured results such as:

```text
PASS
FAIL
NEEDS_FIX
```

### 8. Review and Fix Loop

The system will eventually support automatic iteration:

```text
Developer
    ↓
QA
    ↓
FAIL
    ↓
Developer Fix
    ↓
QA
    ↓
PASS
    ↓
Reviewer
```

### 9. Git Integration

Git will become part of the controlled development lifecycle:

```text
Task
 ↓
Implementation
 ↓
Testing
 ↓
Review
 ↓
Git Diff
 ↓
Commit
 ↓
Human Approval
```

---

## Design Principles

### Human-in-the-loop

The AI Corporation is intended to assist with software development, not remove human authority.

The human remains the final approval authority for important actions.

### Single Write Authority

The architecture should avoid multiple AI agents modifying the same working tree simultaneously.

The intended design is to have one authorized developer agent perform code modifications while other agents provide planning, research, QA, security, and review.

### Provider Independence

Agents should not be tightly coupled to a specific AI provider.

The provider abstraction allows different models and services to be added independently.

### Persistent State

Projects, tasks, memory, and execution history should survive application restarts.

### Auditable Execution

Important actions should be recorded so the system can explain what happened during a workflow.

### Incremental Development

The corporation is being developed in stages, with each architectural milestone tested and committed before moving to the next layer.

---

## Development Environment

Current development environment:

```text
OS: Windows
Language: Python
Database: SQLite
Local AI Runtime: Ollama
Source Control: Git / GitHub
IDE: Antigravity
```

---

## Running the Application

### Native (default)

From the project root:

```powershell
python -m app.main
```

The project uses module execution intentionally:

```text
python -m app.main
```

rather than:

```text
python app\main.py
```

to preserve the Python package/module structure.

### Docker (optional)

Docker is an **optional** runtime. The application runs natively and does not require Docker.

Ollama continues to run on the host machine. The container reaches it through `host.docker.internal:11434`.

SQLite data is persisted through a bind mount of the `projects/` directory, so the database survives container recreation.

Build the image:

```powershell
docker compose build
```

Run the container:

```powershell
docker compose up
```

---

## Development Philosophy

ERSELMETZ AI CORPORATION is being developed as an actual software system rather than a simulated company.

The objective is to build the infrastructure first, validate each layer, and gradually evolve the system into a reliable multi-agent software engineering platform.

**Build the foundation.
Connect the agents.
Automate the workflow.
Keep humans in control.**

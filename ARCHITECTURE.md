# ERSELMETZ AI CORPORATION — Architecture

## Overview

**ERSELMETZ AI CORPORATION** is an actual software system implementing a virtual/simulated AI organization.

The system is designed to operate as an AI Corporation where multiple AI employees can work together under an Orchestrator.

The architecture is intentionally **AI-provider agnostic**.

The Corporation must not depend on a single AI vendor, a single model, or a single AI runtime.

AI employees can use:

* Local/offline LLMs
* Cloud-hosted LLMs
* AI providers accessed through APIs
* Different models from the same provider
* Different providers at the same time
* Additional AI systems added in the future

The system should allow AI employees to be **added, removed, replaced, reassigned, and expanded without redesigning the Corporation itself**.

---

# 1. High-Level Corporation Organization

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

This diagram represents the **organizational workflow**.

The actual number of employees is not fixed.

The Corporation may have:

```text
1 AI
5 AI employees
10 AI employees
50 AI employees
100+ AI employees
```

The architecture should not require a fixed number of AI employees.

---

# 2. AI Employee Architecture

An AI employee is not the same thing as an AI provider or an AI model.

These concepts must remain separate.

```text
                         AI EMPLOYEE
                              │
                ┌─────────────┴─────────────┐
                │                           │
              ROLE                     ASSIGNMENT
                │                           │
        Architect / Developer /        Provider
        Researcher / QA / etc.            │
                                          ▼
                                        Model
```

For example:

```text
Employee:
    Researcher

Provider:
    Ollama

Model:
    llama3.2:3b
```

Another employee may use:

```text
Employee:
    Architect

Provider:
    OpenAI

Model:
    configured OpenAI model
```

Another may use:

```text
Employee:
    Researcher

Provider:
    Google

Model:
    configured Gemini model
```

The employee's role should not determine which company or model provides the intelligence.

---

# 3. Provider and Model Separation

The Corporation uses the following conceptual separation:

```text
┌────────────────────┐
│      AI AGENT      │
│                    │
│ Role               │
│ Capabilities       │
│ Permissions        │
│ Provider assignment│
│ Model assignment   │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│      PROVIDER      │
│                    │
│ AI service/runtime │
│ Connection/config  │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│       MODEL        │
│                    │
│ Specific LLM       │
└────────────────────┘
```

### Provider

A provider represents the service or runtime used to access an AI model.

Examples include:

* Ollama
* OpenAI
* Google
* Anthropic
* DeepSeek
* Kimi
* Other compatible AI services
* Future providers

### Model

A model represents the specific AI model being used.

Examples include:

* Llama
* Gemma
* DeepSeek models
* Gemini models
* GPT models
* Claude models
* Future models

The provider and model must remain independently representable.

---

# 4. Local / Offline AI

The Corporation can use AI that runs locally on the computer.

Example:

```text
AI Corporation
      │
      ▼
AI Employee
      │
      ▼
Ollama Provider
      │
      ▼
Local LLM
      │
      ▼
Llama / Gemma / other local model
```

A local AI can operate without sending prompts to an external AI service, depending on the configured runtime and model.

Example configuration concept:

```text
Employee: Developer

Provider: Ollama

Model: llama3.2:3b
```

This allows the Corporation to continue using locally available AI infrastructure.

---

# 5. Online / Cloud AI

The Corporation can also use online AI services.

Example:

```text
AI Employee
      │
      ▼
Cloud Provider
      │
      ▼
Online AI Model
```

Possible integrations include:

```text
Google / Gemini
OpenAI / ChatGPT
DeepSeek
Anthropic / Claude
Kimi
Other providers
```

Cloud providers may be accessed through:

* API keys
* Provider SDKs
* HTTP APIs
* Other supported authentication mechanisms
* Future native integrations

The Corporation architecture must not assume that all providers use the same connection method.

---

# 6. Multiple AI Providers at the Same Time

The Corporation is designed to support multiple AI systems simultaneously.

For example:

```text
                    AI CORPORATION
                           │
                    ORCHESTRATOR
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ARCHITECT           RESEARCHER          DEVELOPER
        │                  │                  │
        ▼                  ▼                  ▼
     OpenAI             Gemini             Ollama
        │                  │                  │
        ▼                  ▼                  ▼
      GPT              Gemini Model       Llama/Gemma
```

There is no architectural requirement that every employee use the same AI.

---

# 7. AI Can Be Added, Removed, or Replaced

AI integration must be treated as a configurable part of the Corporation.

An AI employee may be:

```text
ADD
 │
 ▼
Employee + Provider + Model
```

An existing employee may be:

```text
REMOVE
 │
 ▼
Employee no longer participates
```

An employee may also be reassigned:

```text
OLD

Developer
   │
   ▼
Ollama
   │
   ▼
Llama


NEW

Developer
   │
   ▼
OpenAI
   │
   ▼
Configured GPT model
```

The Corporation itself does not need to be rebuilt when an AI provider or model changes.

---

# 8. Replacement Principle

The system should eventually support commands conceptually similar to:

```text
"Replace the Researcher AI with Gemini."
```

or:

```text
"Use DeepSeek for the Developer."
```

or:

```text
"Move the Architect employee to a local Llama model."
```

The goal is that these changes can be handled through Corporation configuration and management systems rather than requiring developers to manually rewrite core Python code.

The exact command/interface is a future implementation detail.

---

# 9. Temporary Model Override

Permanent employee configuration and task-specific configuration are separate concepts.

An employee may have a permanent assignment:

```text
Developer
    Provider: Ollama
    Model: llama3.2:3b
```

But a specific task may temporarily request another model:

```text
Task
    ↓
Temporary Provider/Model Override
    ↓
Execute
    ↓
Return to Employee's normal assignment
```

This allows the Corporation to eventually use specialized models for individual tasks without permanently changing an employee.

---

# 10. Provider Registry

The Corporation uses a provider registry to prevent the Orchestrator from being tightly coupled to one provider.

Conceptually:

```text
ProviderRegistry
    │
    ├── OllamaProvider
    ├── OpenAIProvider
    ├── GoogleProvider
    ├── AnthropicProvider
    ├── DeepSeekProvider
    ├── KimiProvider
    └── FutureProvider...
```

The exact providers implemented at any given time may change.

The architecture should allow additional providers to be introduced without changing the fundamental Corporation design.

---

# 11. Unlimited AI Integration Concept

There is intentionally no hard architectural limit such as:

```text
Only 3 AI systems
Only 5 providers
Only 10 employees
```

Instead:

```text
                AI CORPORATION
                       │
                 ORCHESTRATOR
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
      Agent          Agent          Agent
        │              │              │
        ▼              ▼              ▼
    Provider       Provider       Provider
        │              │              │
        ▼              ▼              ▼
      Model          Model          Model

        ... additional employees ...
        ... additional providers ...
        ... additional models ...
```

The practical limit depends on available hardware, provider limits, API limits, resources, configuration, and system performance — not on an arbitrary fixed employee count in the Corporation architecture.

---

# 12. Orchestrator

The Orchestrator is the management and coordination layer.

Conceptually:

```text
USER
 │
 ▼
ORCHESTRATOR
 │
 ├── Select / coordinate employee
 ├── Manage task execution
 ├── Coordinate workflow
 ├── Track task state
 └── Communicate with Corporation systems
```

The Orchestrator should not need to know the internal implementation details of every AI provider.

Instead:

```text
Orchestrator
      │
      ▼
Agent
      │
      ▼
Provider
      │
      ▼
Model
```

This separation keeps the Corporation extensible.

---

# 13. Tools Are Separate From Intelligence

An AI model is not automatically allowed to control the computer.

The architecture separates intelligence from tools.

```text
AI MODEL
    │
    ▼
AI EMPLOYEE
    │
    ▼
TOOL SYSTEM
    │
    ├── File System
    ├── Terminal
    ├── Browser
    ├── Git
    ├── Applications
    └── Future Tools
```

Permissions determine which tools an employee may use.

Examples of permissions:

```text
read
write
execute
git
publish
delete
```

Sensitive operations may require human approval.

---

# 14. Human Approval

The human remains the final authority.

The Corporation can automate work while preserving human control over important actions.

```text
AI EMPLOYEES
      │
      ▼
WORK
      │
      ▼
REVIEW
      │
      ▼
GIT / PUBLISH / SENSITIVE ACTION
      │
      ▼
HUMAN APPROVAL
```

The exact approval mechanisms will evolve as the system grows.

---

# 15. Complete Technical Architecture

```text
                         👨‍💻 HUMAN / CEO
                               │
                               ▼
                    🏢 AI CORPORATION
                               │
                               ▼
                        ORCHESTRATOR
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
          PROJECTS           TASKS          AI EMPLOYEES
                                                 │
                                  ┌──────────────┼──────────────┐
                                  │              │              │
                                  ▼              ▼              ▼
                               ROLE        PROVIDER        MODEL
                                                │              │
                                                └──────┬───────┘
                                                       ▼
                                                AI RUNTIME / API
                                                       │
                              ┌────────────────────────┼────────────────────┐
                              │                        │                    │
                              ▼                        ▼                    ▼
                           OLLAMA                 CLOUD APIs          FUTURE AI
                              │                        │                    │
                              ▼                        ▼                    ▼
                         Local LLMs            Gemini / GPT /       Additional
                         Llama / Gemma         DeepSeek / etc.      providers
```

---

# 16. Corporation vs AI Provider

These are different layers.

```text
AI CORPORATION
    │
    ├── Employees
    ├── Projects
    ├── Tasks
    ├── Memory
    ├── Orchestrator
    ├── Tools
    ├── Permissions
    └── Provider configuration
             │
             ├── Ollama
             ├── OpenAI
             ├── Google
             ├── DeepSeek
             ├── Anthropic
             └── Other providers
```

The Corporation is the software organization.

The AI providers are resources that the Corporation can use.

---

# 17. One Computer = One AI Corporation

The long-term system is designed around the concept that each installation represents an independent AI Corporation.

```text
PC 1
└── AI Corporation A
    ├── Employees
    ├── Projects
    ├── Tasks
    └── AI Providers

PC 2
└── AI Corporation B
    ├── Employees
    ├── Projects
    ├── Tasks
    └── AI Providers

PC 3
└── AI Corporation C
    ├── Employees
    ├── Projects
    ├── Tasks
    └── AI Providers
```

Future versions may allow multiple Corporations to communicate and collaborate over a network.

Networking is not part of the current local-first architecture.

---

# 18. Core Architectural Principles

The following principles should be preserved when implementing future features.

1. **One PC = one independent AI Corporation.**

2. **Agent ≠ Provider ≠ Model.**

3. **An Agent represents an AI employee.**

4. **A Provider represents an AI service/runtime.**

5. **A Model represents a specific AI model.**

6. **Employees can use different providers and models.**

7. **Local and cloud AI can coexist.**

8. **The Corporation must not be permanently tied to one AI vendor.**

9. **AI employees can eventually be added, removed, replaced, or reassigned.**

10. **The number of AI employees is not fixed by the architecture.**

11. **Tools are separate from AI intelligence.**

12. **Permissions control tool access.**

13. **Sensitive operations can require human approval.**

14. **The Orchestrator coordinates work rather than embedding provider-specific logic everywhere.**

15. **New features should preserve existing architectural boundaries.**

16. **The Corporation should remain usable with local AI, cloud AI, or a combination of both.**

17. **Provider-specific implementation details belong inside provider integrations, not throughout the Corporation core.**

18. **The system should be extensible without requiring a redesign when new AI providers or models appear.**

---

# 19. Current Implementation vs Future Architecture

Not everything shown in this document is implemented yet.

The architecture describes both:

* the current software foundation
* the intended long-term direction

Current development should implement the architecture incrementally.

Future concepts such as:

* automatic model routing
* fallback providers
* task-specific model selection
* additional cloud providers
* dynamic employee management
* tool authorization
* human approval workflows
* Corporation-to-Corporation networking

should be introduced only when their corresponding development milestones are reached.

Do not implement future architecture prematurely unless the current roadmap explicitly calls for it.

---

# 20. Development Rule

Before making architectural changes, coding agents should read:

```text
README.md
ARCHITECTURE.md
```

and any relevant documentation under:

```text
docs/
```

The purpose is to ensure that implementation decisions remain consistent with the Corporation's architecture.

The AI Corporation is designed to evolve.

**The Corporation should not need to be rebuilt simply because the AI employees, providers, or models change.**

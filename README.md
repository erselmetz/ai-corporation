## 🏢 What Is ERSELMETZ AI CORPORATION?

**ERSELMETZ AI CORPORATION** is an actual software system implementing a virtual/simulated AI organization.

The system is designed to coordinate multiple AI employees that can perform different roles inside a virtual Corporation.

The architecture is **AI-provider agnostic**. The Corporation is not designed around a single AI vendor or model.

AI employees can use:

* 🖥️ Local/offline LLMs
* ☁️ Cloud AI services
* 🔑 API-based AI providers
* 🔄 Different models from different providers
* ➕ Additional AI systems added in the future

An AI employee can eventually be **added, removed, replaced, or reassigned** without rebuilding the Corporation itself.

For example:

```text
Developer
    │
    ├── Provider: Ollama
    └── Model: Llama

        ↓ Replace provider/model

Developer
    │
    ├── Provider: OpenAI
    └── Model: configured GPT model
```

Multiple AI systems can operate simultaneously:

```text
                    AI CORPORATION
                           │
                    ORCHESTRATOR
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    ARCHITECT           RESEARCHER         DEVELOPER
        │                  │                  │
      OpenAI             Gemini             Ollama
        │                  │                  │
       GPT              Gemini Model       Llama/Gemma
```

The Corporation does not require a fixed number of AI employees or providers.

### Architecture

The main architecture is documented in:

**[`ARCHITECTURE.md`](ARCHITECTURE.md)**

It contains:

* Corporation organization
* AI employee architecture
* Provider and Model separation
* Local/offline AI
* Cloud AI
* Multiple AI providers
* Employee replacement and reassignment
* Orchestrator architecture
* Tool and permission architecture
* Human approval
* Long-term Corporation networking concept

### Documentation

Visual documentation is available under:

```text
docs/
└── html/
    └── index.html
```

The documentation provides a visual overview of how the AI Corporation is organized and how AI employees, providers, models, and runtimes interact.

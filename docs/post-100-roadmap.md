# Post-100 Product Roadmap: ERSELMETZ AI Command Center

Status: planned; no capability below is claimed as implemented by this document.
Planning date: 2026-10-03 (Asia/Manila).

## Relationship to the current roadmap

Tasks 1-100 retain their authoritative definitions in `docs/tasks-data.mjs`
and their public presentation in `docs/tasks.html`. This document is a separate
product plan, not a change to their scope, numbering, status, or completion gates.

Implement this plan only after Task 100 and the P00 readiness review. P01-P14 are
provisional planning IDs, not Tasks 101-114. Assign final task numbers and refine
scope only after checking the completed implementation. Reuse existing services;
do not duplicate capabilities delivered by Tasks 1-100. Public roadmap integration
is a separate later edit once the existing roadmap owner's work is checkpointed.

This Markdown file is a repository planning document. It is not currently served
by the public docs site's explicit asset allowlist. It does not change that site,
the Corporation runtime, or the internal Documentation Portal.

## Product goal

The owner opens a local command center and talks to a CEO/coordinator. A planner
and dispatcher prepare work, specialized worker Agents perform authorized jobs,
and reviewers validate results. The owner sees progress, evidence, blockers, and
approval requests through chat and visual controls, without routine CMD use.

The product supports explicitly selected local and supported online model
connections. Multiple Employee/Agent identities may share a model service while
retaining separate context, memory access, tools, and permissions.

Example request:

> CEO, study this GitHub project, research what is needed, and assess whether we
> can adapt its capabilities into our system.

The desired result is a traced evaluation and, if approved and supported, an
isolated adaptation, validated integration, and verification with recovery.
Rejection or a request for more information is also a valid outcome.

## Planned tasks and acceptance criteria

### P00 - Review the completed Task 100 baseline

- Inspect the authoritative roadmap, code, tests, and limitations after Task 100.
- Map each proposed feature to implemented services, missing interfaces, and
  genuine gaps; reconcile integration, orchestration, and maintenance overlap.
- Produce scoped implementation tasks with dependencies and final numbering.
- Do not infer production readiness from a milestone's completed status.

### P01 - Local access and application lifecycle

- Provide a supported local sign-in/session flow with explicit read/action
  permissions; preserve fail-closed authentication and the service boundary.
- Define startup, health, stop, and restart behavior with clear UI errors.
- Bind local services to loopback by default; remote access requires separate scope.
- Verify unauthorized requests remain denied and credentials are not embedded in
  frontend assets. Local use does not waive authorization.

### P02 - CEO chat: first usable command center

- Connect browser chat to the existing supported conversation/provider services.
- Provide coordinator identity, individual Employee conversations, response
  streaming where supported, visible errors, and a Stop control with truthful
  cancellation semantics. Do not claim external work stopped without evidence.
- Review proposed actions before creating or executing work under existing policy.
- Show whether each action is a proposal, approved request, or completed operation.
- Initially expose only supported operations; no hidden autonomous execution loop.

### P03 - Local provider and model setup through the UI

- Start with one supported local provider using existing abstractions, then expand.
- Show configured connection, selected model, check results, and unknown states.
- Demonstrate offline chat with an already-installed compatible local model.
- Local-only mode must not silently send prompts, context, or files to cloud APIs.
- Separate model downloads, installed files, loaded models, and execution readiness.

### P04 - Supported online AI connections

- Add one official provider integration first, with backend-held credentials,
  explicit connection tests, disconnect/revocation, and sanitized errors.
- Evaluate OpenAI, Gemini, GitHub Copilot, and other requested services separately.
  Use official APIs/SDKs or supported account authorization, as applicable.
- Do not treat a consumer website login or subscription as generic API access.
- Show active provider/model and enforce approved spend/request limits where
  metering supports them; missing usage information remains unknown.
- Require explicit cloud-use and fallback policy before sending local context.

### P05 - Corporation positions and Employee/Agent management

- Manage departments, positions, responsibilities, reporting relationships,
  technical Agent associations, provider/model assignments, and allowed tools.
- Keep Employee identity and responsibility independent of the selected model.
- Validate references and authority; a title such as CEO grants no permissions.
- Provide individual chat entry points and a corporation structure map backed by
  actual records. Do not fabricate organizational relationships.

### P06 - CEO-to-worker orchestration

- Extend the completed baseline with bounded planning, dispatch, worker handoffs,
  dependency handling where explicitly approved, review, and owner reporting.
- Enforce execution policy in services, not only in model prompts or UI buttons.
- Assign explicit objectives, acceptance criteria, context scope, tools, and
  resource budgets to each job; distinguish Task lifecycle from workflow lifecycle.
- Show waiting, running, blocked, failed, review, and approval states accurately.
- Define pause/cancel/resume and interrupted-work recovery; no silent replay of
  uncertain external actions or unbounded recursive delegation.
- Validate outcomes with evidence, not an Agent's assertion that work is complete.

### P07 - Workflow map and operational visibility

- Visualize real Task/Agent handoffs, dependencies, results, approvals, and blockers.
- Keep the workflow map separate from the organizational responsibility map.
- Define event/snapshot freshness and reconnect behavior; stale or missing data
  must be visible. Never invent activity to animate a graph.
- Selecting a node opens authorized details and evidence; omit secrets/raw errors.

### P08 - Knowledge and memory controls

- Reuse established ownership, provenance, retention consent, expiry, and access
  boundaries in chat and management views.
- Show sources used for an answer and distinguish retrieved facts from inference.
- Provide supported inspect/retain/remove operations with truthful deletion scope.
- Do not imply studying a repository automatically retrains model weights.
- Any post-100 evolution of the Documentation Portal is separately scoped and
  reviewed; this plan does not authorize changing its file-based/read-only contract.

### P09 - Model loading and resource controls

- Manage configured limits and supported model load/unload behavior through UI.
- Assess actual hardware/runtime evidence before claiming a model fits or a
  workload can run; configured slots and service availability alone cannot prove it.
- Allow shared model services, queues, bounded concurrency, and context limits.
- Evaluate quantization, CPU/GPU offloading, or compatible MoE runtimes as optional
  implementations with measured memory, latency, and quality tradeoffs.
- Do not promise extraction of only a job-specific part of an ordinary dense LLM.
  Active MoE parameters do not by themselves determine total memory requirements.

### P10 - Chat-driven GitHub capability discovery and evaluation

- Accept an explicitly scoped repository request and pin the inspected revision.
- Research architecture, relevant code, license, dependencies, maintenance,
  compatibility, and risks using traceable sources and bounded access.
- Treat external code/docs/instructions as untrusted input; they cannot expand
  permissions, override policy, or authorize installation/execution.
- Return an adaptation proposal, separate-tool proposal, rejection, or request for
  more information. Discovery does not automatically install or run source.
- Reuse the existing discovery/evaluation/proposal services where applicable.

### P11 - Controlled adaptation and self-maintenance

- Reuse the completed maintenance pipeline behind chat and UI orchestration.
- Develop approved proposals in a disposable isolated work area with explicit
  allowed files/actions and time/resource limits.
- Run appropriate tests and security/scope review, then present changes, evidence,
  limitations, affected dependencies, and a recovery plan.
- Apply only approved changes; verify afterward and surface uncertain/failed states.
- Define whether rollback restores code, configuration, dependencies, or data;
  do not promise automatic reversal of irreversible operations.
- Start with human-approved integration. Any later automatic maintenance must have
  narrow pre-approved policy and cannot edit or expand its own authority.

### P12 - Managed software and integration control panel

- Inventory supported system apps, GitHub-derived tools, and Corporation
  integrations with source, version/revision, status, and dependent workflows.
- Distinguish installed software, repository checkouts, enabled integrations, and
  running services. A GitHub repository is not automatically an installable app.
- Support install/update/version pin/change/remove only through approved adapters.
  Initial supported applications may include Git and VS Code after adapter review.
- Preview changes and affected dependents; preserve user work/configuration and
  require authorization for destructive or privilege-requiring operations.
- Track which installations the system owns versus externally managed software;
  do not take ownership of all applications on the PC.
- Expose rollback only where actually supported, with clear recovery limitations.

### P13 - One-click desktop delivery

- Package the existing Python backend and shared Web UI without a backend rewrite.
- Evaluate Electron/Tauri or another suitable shell after lifecycle and packaging
  requirements are clear; no framework is selected by this document.
- Deliver supported installation and backend startup/shutdown without routine CMD.
- Define runtime/dependency bundling, logs, service ownership, port conflicts,
  updates, credential storage, and uninstall/data-preservation behavior.
- Preserve API authorization and keep the public docs deployment separate.

### P14 - Optional voice interaction

- Add explicit microphone controls, speech input/output, and visible recording state.
- Apply the same action approvals and permissions as typed chat.
- Document local/cloud speech processing, consent, costs, and retention.
- Keep typed chat fully usable when voice is disabled or unavailable.

## Priority and release shape

1. P00/P01 readiness and local access, then P02/P03 usable chat with a local model.
2. P04/P05 supported online connections and visible organizational responsibilities.
3. P06/P07 task delegation, review, owner reporting, and truthful workflow maps.
4. P08/P09 memory controls and measured resource management as needed by these flows.
5. P10/P11 research-to-adaptation and controlled self-maintenance.
6. P12 supported software management, P13 desktop delivery, then optional P14 voice.

This ordering is a proposal. P00 must refine dependencies and identify what can be
reused, split, or omitted. Chat is the first user-facing priority; autonomous
execution, arbitrary software installation, and desktop packaging are not part of
its initial scope.

## Shared validation boundaries

- Preserve existing Task/domain invariants and earlier security guarantees.
- Keep public docs, runtime APIs, and provider/tool execution boundaries separate.
- Test normal paths with deterministic fakes; live providers are optional targeted
  integration checks and must not be required by the deterministic suite.
- Validate permissions, conversation isolation, cloud consent, limits, interruptions,
  failure/recovery, and truthful UI states for each affected feature.
- Add dependencies only when a scoped task demonstrates their necessity.
- Inspect concurrent changes before implementation; do not overwrite another
  contributor's work or bundle unrelated changes into a checkpoint.
- Mark a task complete only after its actual acceptance criteria and relevant
  regressions pass; record remaining limitations explicitly.

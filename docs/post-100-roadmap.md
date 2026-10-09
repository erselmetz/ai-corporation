# Post-100 Product Roadmap: ERSELMETZ AI Command Center

Status: Tasks 101–121 are verified foundations. Task 105 adds explicitly consented Gemini coordinator chat with an in-memory restricted API key and bounded generation. Task 106 adds best-effort Gemini key-paste blocking before chat persistence/submission. Task 107 adds ephemeral editable position records with independent read/manage permissions and provenance-preserving removal guards. Task 108 adds manual connection previews, fixed Task/conversation assignment snapshots, and bounded principal-owned individual Employee chat. Task 109 adds disabled-by-default review-only model assignment recommendations under fresh tested evidence, explicit access, capacity and budget constraints. Task 110 adds short-lived, principal-scoped coordinator proposals and exact-digest confirmation for pending Tasks; it does not execute work. Task 111 adds explicitly confirmed, budget-gated local worker dispatch through the existing queue; it does not provide cloud/Tool execution, replay, or outcome verification. Task 112 adds owner-configured local Ollama/Gemini connections, truthful catalogs/status and explicit Agent assignment under software request-slot limits. Task 120 adds bounded Ollama chat streaming with display-only Stop behavior; interrupted turns remain pending/uncertain without persisted partial assistant text or automatic replay. Task 121 adds chat-driven, allowlist-gated, commit-pinned GitHub study and an evidence-backed unapproved proposal; incomplete evidence requests more information, with no provider synthesis, installation, or execution. Task 122 is next. Broader product readiness, remaining P01/P02/P03 work and P04-P15 remain planned.
See [Task 101 readiness review](post-100-readiness.md) for evidence, gaps, and the
first proposed implementation checkpoints. The readiness record distinguishes validated checkpoints from remaining planned capabilities.
Planning date: 2026-10-03 (Asia/Manila).

## Relationship to the current roadmap

Tasks 1-100 retain their original definitions and completed foundation scope.
The numbered Tasks 101-129, their explicit statuses, dependencies, acceptance
checks, exclusions, decision gates and verified checkpoint records now live in
`docs/tasks-data.mjs` (`post100Tasks`) and appear on the public `docs/tasks.html`.
Those records are the authoritative implementation contracts; this P00-P15 file
is supplementary product context, not a competing status/numbering source.

Tasks 101-121 are complete; Task 122 is next and Tasks 122-129 remain planned.
Publishing this list does not implement those tasks or approve their unresolved
architecture/product/authority decisions. Read the shared `roadmapRules` before
coding, preserve uncommitted work, and record exact validation and handoff evidence.
Use one scoped checkpoint at a time and recheck for other contributors' changes.

This Markdown context remains repository-only and outside the public asset
allowlist. Public contracts are served as existing static task data; public docs
remain separate from runtime and the Task 53 portal remains file-based/read-only.

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

The initial source-review slice completed as Task 101 on 2026-10-04; see
[the readiness record](post-100-readiness.md). Task 101 mapped the baseline and scoped the first local checkpoints; it did not certify every future feature or complete operational acceptance. The numbered contracts subsequently published Tasks 104-128. The broader goals below remain context, not additional Task 101 completion claims. No fresh runtime validation claimed.

- Inspect the authoritative roadmap, code, tests, and limitations after Task 100.
- Map each proposed feature to implemented services, missing interfaces, and
  genuine gaps; reconcile integration, orchestration, and maintenance overlap.
- Produce scoped implementation tasks with dependencies and final numbering.
- Do not infer production readiness from a milestone's completed status.

### P01 - Local access and application lifecycle

P01a completed as Task 102: explicit local password sign-in, expiring sessions,
read permissions, logout and CSRF/Origin/Host protections. One-click lifecycle,
installer and remote identity work remain planned. See the readiness record.

- Provide a supported local sign-in/session flow with explicit read/action
  permissions; preserve fail-closed authentication and the service boundary.
- Define startup, health, stop, and restart behavior with clear UI errors.
- Bind local services to loopback by default; remote access requires separate scope.
- Verify unauthorized requests remain denied and credentials are not embedded in
  frontend assets. Local use does not waive authorization.

### P02 - CEO chat: first usable command center

P02a completed as Task 103: principal-owned selected-Agent chat API/UI, explicit
Send, actual model identity, safe replies/errors and bounded ephemeral history.
Streaming, true cancellation, individual Employee entry points, action reviews
and autonomous CEO delegation remain planned. See the readiness record.

- Connect browser chat to the existing supported conversation/provider services.
- Provide coordinator identity, individual Employee conversations, response
  streaming where supported, visible errors, and a Stop control with truthful
  cancellation semantics. Do not claim external work stopped without evidence.
- Review proposed actions before creating or executing work under existing policy.
- Show whether each action is a proposal, approved request, or completed operation.
- Initially expose only supported operations; no hidden autonomous execution loop.

### P03 - Local provider and model setup through the UI

P03a completed as Task 104: explicit supported loopback inventory refresh and
separately authorized installed-model selection, freshly revalidated and guarded
against active owned-chat calls. Assignment is per-run; other providers, download,
automatic assignment and hardware/execution feasibility remain outside this slice.

- Start with one supported local provider using existing abstractions, then expand.
- Show configured connection, selected model, check results, and unknown states.
- Demonstrate offline chat with an already-installed compatible local model.
- Local-only mode must not silently send prompts, context, or files to cloud APIs.
- Separate model downloads, installed files, loaded models, and execution readiness.
- On approved onboarding and explicit refresh, automatically discover models from
  supported local provider inventory endpoints, starting with Ollama. Use bounded
  loopback checks; do not scan arbitrary files, networks, or credential stores.
- Show detected provider/model IDs, inventory source, and current evidence. Missing
  or unsupported discovery remains explicit; detection does not install, download,
  load, execute, or prove the suitability of a model.

### P04 - Supported online AI connections

- Add one official provider integration first, with backend-held credentials,
  explicit connection tests, disconnect/revocation, and sanitized errors.
- Evaluate OpenAI, Gemini, GitHub Copilot, and other requested services separately.
  Use official APIs/SDKs or supported account authorization, as applicable.
- Do not treat a consumer website login or subscription as generic API access.
- Show active provider/model and enforce approved spend/request limits where
  metering supports them; missing usage information remains unknown.
- Require explicit cloud-use and fallback policy before sending local context.
- Support chat-driven setup such as "Connect my Gemini API and assign suitable
  positions automatically." Open a secure credential entry control in the chat UI
  instead of requesting the API key in ordinary conversation text.
- Submit credentials directly to the backend credential store without sending them
  to the conversation LLM, transcript/history, analytics, logs, or model context.
  Never echo the key. Define access controls, rotation, disconnect, and deletion.
- If a key is pasted into ordinary chat, intercept/redact supported formats before
  persistence or model submission; detection is fallible, so this is not the normal
  credential-entry path. Surface accidental exposure with provider-specific recovery
  guidance instead of pretending that masking reverses earlier disclosure.
- After authorized entry, verify the connection, discover accessible models where
  supported, and apply P15 assignment policy. Validation/capability probes must have
  explicit request/spend limits and must not include private project context.
- A key alone does not authorize arbitrary paid work, tool access, or cloud transfer;
  onboarding must capture permitted use, budget, and automatic-assignment preference.

### P05 - Corporation positions and Employee/Agent management

- Manage departments, positions, responsibilities, reporting relationships,
  technical Agent associations, provider/model assignments, and allowed tools.
- Keep Employee identity and responsibility independent of the selected model.
- Validate references and authority; a title such as CEO grants no permissions.
- Provide individual chat entry points and a corporation structure map backed by
  actual records. Do not fabricate organizational relationships.

#### Editable default positions

Provide these initial role templates in the future UI; they are planned defaults,
not a claim that these Employees or Agents are already installed or configured.

| Position | Initial responsibility |
| --- | --- |
| Architect | System design, integration fit, and architecture proposals |
| Developer | Implement approved changes within assigned scope |
| Researcher | Source discovery, research, and evidence gathering |
| Reasoning Analyst | Analyze alternatives, assumptions, and tradeoffs |
| QA Engineer | Test planning, validation, and result evidence |
| Security | Review permissions, external inputs, and security boundaries |
| Code Reviewer | Inspect changes against scope, quality, and correctness |
| Project Manager | Track plans, assignments, dependencies, and blockers |
| Technical Writer | Maintain approved documentation and user guidance |
| UI/UX | Design usable interfaces and evaluate user flows |

- Allow authorized add, edit, rename, deactivate/remove, and role assignment.
- Before removal or reassignment, show affected active jobs and references; require
  explicit resolution instead of silently dropping work or erasing history.
- Editing responsibilities must not automatically grant tool permissions.
- Preserve the CEO/coordinator and planner/dispatcher workflows independently of
  these templates. Organizational titles do not override execution authority.

#### Configurable model connections and reassignment

- Support a sample installation with two offline/local models and three supported
  online connections, such as Gemini, OpenAI models, and GitHub Copilot where the
  provider's official integration and account access permit it.
- These are configurable connection/model entries, not five required providers,
  five model copies, or a guarantee that all models run concurrently.
- Offer automatic initial role-to-model assignment under an owner-approved policy,
  using supported capabilities, access, and capacity checks; allow manual overrides.
  Show the reason for each assignment and leave unsupported roles unassigned rather
  than inventing compatibility. Automatic setup must not enable cloud use without consent.
- Several Employees/Agents may share a connection; each retains separate context,
  access scope, and instructions. Connections do not own organizational positions.
- Let authorized users move a position/Agent to another connection/model through
  the UI. Check compatibility and permissions and define the effective boundary;
  do not silently switch providers mid-job or move private context to the cloud.
- Keep prior job provenance and model identity after reassignment. Connection
  removal must expose affected assignments and unresolved work.
- Make local-only, online, and explicit fallback policy visible; hardware capacity,
  provider availability, and execution eligibility remain separate checks.

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
- Preferred visual direction: an original Iron Man/Jarvis-inspired command center,
  using Three.js as a candidate for interactive 3D corporation/workflow maps,
  selectable Agent nodes, and restrained status/connection animations.
- Keep chat, management forms, approvals, and readable operational details in the
  standard UI. The 3D scene is a presentation layer over authorized real state.
- Provide equivalent 2D/list views, keyboard access, readable labels, reduced-motion
  controls, and graceful fallback when graphics support/performance is insufficient.
- Measure rendering cost alongside local inference; cap visual complexity and allow
  disabling effects. Decorative animation must not imply nonexistent AI activity.
- Three.js is a planning preference, not a dependency installation or final framework
  commitment. Choose the implementation after P00 compatibility/performance review.

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

### P15 - Automatic capability-based AI position assignment

- "Auto deployment" in this product plan means assigning suitable AI connections
  and models to organizational positions. It does not add automatic website/server
  release or hosting-target migration requirements.
- Combine P03 supported local discovery and P04 authorized online onboarding into
  a reviewable inventory, including the two-local/three-online example in P05.
- Assess role fit from traceable provider capability metadata, owner-supplied
  requirements, and optional bounded evaluations under explicit budget. Distinguish
  declared capabilities, tested performance, availability, and unknowns.
- An installed model, successful connection, model size/name, or API key alone
  cannot prove coding, reasoning, security-review, or other job competence.
- Under an enabled owner-approved automatic policy, fill eligible unassigned roles
  and show the model, supporting evidence, constraints, and reason for each choice.
  Otherwise present suggested assignments for review. Leave uncertain or unsupported
  roles unassigned; do not fabricate capability scores.
- Preserve established/manual assignments unless the configured policy explicitly
  permits reassignment. Provide edit, move, disable, and undo controls with defined
  effects on active work; do not silently change a running job's model.
- Respect permissions, cloud consent, budget, local capacity, and concurrency limits.
  Multiple positions may share a model service with isolated contexts; assignment
  does not require every model to be loaded or every Agent to run simultaneously.
- Revalidate at supported refresh/admission boundaries and show stale assessments.
  Provider failure does not silently reroute sensitive work to another connection.
- Test discovery, onboarding, unknown capabilities, failed credentials, assignment,
  manual overrides, isolation, and exhaustion with deterministic fake providers.
- This document authorizes no live credential use, connection, model execution,
  installation, or assignment change now; all functionality remains planned.

## Priority and release shape

1. P00/P01 readiness and local access, then P02/P03 usable chat with a local model.
2. P04/P05 supported online connections and organizational responsibilities, with
   P15 capability-based automatic assignment after its onboarding/policy dependencies.
3. P06/P07 task delegation, review, owner reporting, and truthful workflow maps.
4. P08/P09 memory controls and measured resource management as needed by these flows.
5. P10/P11 research-to-adaptation and controlled self-maintenance.
6. P12 supported software management.
7. P13 desktop delivery, then optional P14 voice.

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

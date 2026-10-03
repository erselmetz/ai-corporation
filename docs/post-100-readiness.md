# Task 101 / P00 - Post-100 readiness review

Review date: 2026-10-04 (Asia/Manila).
Baseline: Task 100 commit `2f5db63d7d471964949027365a2fa8b435b42ae6`.
Status: readiness review completed; implementation tasks below remain planned.
The reviewed baseline had a clean working tree and HEAD matching origin/main.
This review is source inspection, not a fresh execution or full-suite validation.

## Why the application still feels incomplete

Tasks 1-100 deliver bounded foundations. Their completed status does not imply
that the owner can operate an autonomous organization through the browser.
The current roadmap truthfully marks all 100 foundations complete, while the
runtime still lacks a supported browser authentication and conversation flow.

| Existing foundation | Reuse path | Gap for usable local operation |
| --- | --- | --- |
| AuthenticationBackend and permission dependencies | app/api/security.py | Default rejects all requests; no browser login/session flow |
| create_app with injected authentication backend | app/api/app.py | Need explicit local-owner mode without weakening default app |
| Dashboard and management pages | app/webui/router.py and static modules | Protected data requires authentication; update sign-in messaging |
| CorporationChatService | app/application/services/corporation_chat.py | Trusted-local only; no authenticated ownership or chat API/UI |
| Conversation records and Employee chat | app/conversations/employee_chat.py | Reuse domain bounds; add HTTP owner isolation at service boundary |
| Local runtime factory | app/runtime/factory.py | Registers local_worker with llama3.2:3b; model presence is not checked |
| OllamaProvider | app/providers/ollama.py | Synchronous non-streaming generation; timeout is not cancellation |
| Task planning, collaboration, coordination | existing Application Service methods | No general autonomous worker loop or browser orchestration flow |
| Capability/integration/maintenance workflows | existing Application Service methods | Mostly explicit/review-only stages; records do not execute a pipeline |
| Platform Overview | app/application/services/platform_overview.py | Reports facts/limitations; adds no UI or operational readiness proof |

The factory configures a Local Worker, not a separately modeled CEO hierarchy.
The first chat can select an existing registered coordinator Agent; using a CEO
label must not falsely claim automatic delegation or grant additional authority.
No live Ollama, credentials, model downloads, runtime startup, or database writes
were needed for this review.

## First implementation checkpoints

### Task 102 / P01a - Explicit local-owner browser access

Proposed contract, pending owner approval:

- One local owner on a loopback-only supported launch path; remote/multi-user
  deployment and external identity providers are separate work.
- Password sign-in, bounded login attempts, expiring opaque HttpOnly sessions,
  logout/revocation, and cross-origin/CSRF protections for state-changing requests.
- Explicit trusted configuration, no embedded/default password or auto-login;
  credentials/session tokens must not appear in logs, assets, or URLs.
- Separate local app factory/entry point; existing default app and injected test
  authentication contracts remain unchanged and rejecting by default.
- Grant explicit existing read permissions and later separate chat permissions;
  no implicit management, task execution, maintenance approval, or wildcard grant.
- Show actual sign-in state in browser navigation and protected-data errors.
- Deterministic tests for wrong/missing credentials, expiry/logout, Origin/Host
  checks, CSRF, brute-force bounds, authorization denial, and existing API behavior.
- Document local startup/stop and the remaining installer/one-click lifecycle work.

This is a material authentication decision. Existing global engineering rules
require stopping for owner approval before implementing it. The review does not
claim this contract is already implemented or fully designed.

### Task 103 / P02a - Owned coordinator chat API and usable browser chat

Depends on validated Task 102. Scope remains planned:

- Authenticated create/get/send/close for principal-owned conversations, through
  the Application Service; no direct API registry/provider access.
- Select a registered coordinator and display its actual provider/model identity.
- Server-owned conversation IDs, owner checks, and serialized per-conversation
  sends to preserve existing domain invariants and avoid duplicate concurrent turns.
- Render text safely; show pending, completed, failed, missing-provider/model,
  and authorization states accurately. Preserve input/history byte limits.
- First milestone uses the current non-streaming provider contract. Do not promise
  streaming or true provider cancellation without a separately validated extension.
- No tool execution, automatic task creation, workforce edits, or deployment from
  generated text; later reviewed action flows are separately scoped.
- Test owner isolation, permissions, concurrency, validation, provider failures,
  safe rendering, and service boundaries using deterministic fake providers.

### Task 104 / P03a - Local model discovery and explicit coordinator configuration

Depends on validated local access; planned scope:

- Bounded supported Ollama inventory through provider abstractions, explicit refresh,
  safe errors, and installed-versus-ready distinctions.
- Authorized selection of an installed model for the coordinator; no background
  downloads, automatic execution, cloud fallback, or capability-fit claims.
- Make missing service/model remediation visible without requiring normal users to
  understand CMD. Broader automatic assignment belongs to P15.

## Remaining roadmap relationship

Task numbering after 104 is deferred until these first checkpoints are validated.
P04/P05/P15 online onboarding and positions follow usable local chat; P06/P07
actual delegation and maps follow validated execution contracts. P08/P09 memory
and hardware/resource policy must preserve ownership and truthful unknowns.
P10-P12 adaptation/software management reuse existing stages rather than asserting
that a recorded approval proves execution. P13 desktop delivery and P14 voice remain
planned. Existing Tasks 1-100 are not reopened or renumbered by this review.

## Validation and handoff

The first runnable goal is: start explicitly configured local app, sign in, see
existing authorized records, and exchange a message with a selected local Agent.
That goal requires Task 102, Task 103, and an available compatible local model;
this review alone does not satisfy it.

Preserve the full regression requirements for runtime changes. Reuse still-valid
inspection findings, run focused tests before affected regressions/full suite,
and repeat only when edits, failures, or unresolved concerns justify it.
Do not modify public docs deployment or the Task 53 file-based/read-only portal
as part of local authentication/chat. Inspect concurrent changes before each
checkpoint and commit only the current task's reviewed files.

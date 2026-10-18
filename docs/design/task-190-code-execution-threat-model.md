# Task 190: Code-execution agent threat model and design

**Status: design only. No execution capability is implemented or approved.**

## Boundary and current system

This document evaluates a possible future, owner-directed code-execution capability. Model output, prompts, repositories, retrieved files, and tool results are untrusted input. None can grant permission or broaden an approved action. This design creates no runtime permission, code path, adapter, process, installation, filesystem write, or approval bypass. A separate owner-authorized task and security review are required before implementation.

The current generic `UnavailableSandboxExecutor` returns `BLOCKED`; the integration sandbox registry stores policy metadata but does not itself enforce isolation. `DockerSandboxBackend` is an optional Linux-container backend, requires an already available immutable-digest image, disables network and host mounts for its bounded workspace, and refuses automatic image pulls. `MaintenanceSandboxService` only executes explicitly selected Python tests for maintenance proposals. These are not a general-purpose agent executor or a supported Windows isolation boundary. Do not treat them as authority to run arbitrary model-generated code.

## Threat model

**Assets:** owner files and credentials, application state and local services, provider/API credentials, other processes and accounts, integrity of the active project, and truthful action/audit records.

**Adversaries and failure sources:** prompt injection in user or retrieved content; malicious or compromised model/provider output; hostile repository files, dependencies, and parsers; confused-deputy UI/API calls; compromised runner or image; path, archive, and reparse-point tricks; resource exhaustion; network exfiltration; sandbox/kernel escape; cancellation races; and crashes during execution or result review.

**Trust boundary:** the owner-facing app and approval service are outside the worker boundary. The worker receives only a canonical, one-use action grant and an isolated input snapshot. The worker and all output remain untrusted. A successful exit code does not prove semantic correctness or make output safe to apply.

## Proposed design if separately authorized

### Isolation prerequisite

Use a disposable OS-enforced isolation boundary, not a Python subprocess, restricted prompt, Job Object alone, or application-level path checks. On supported Windows editions, evaluate a disposable Windows Sandbox/VM boundary with networking disabled, no clipboard sharing, and only a read-only selected input snapshot mapped in. A hardened AppContainer may be considered only after its exact process, filesystem, device, registry, credential, and network capabilities are explicitly provisioned and security-reviewed. Job Objects can supervise a process tree and impose resource limits, but they are not the isolation boundary. If the approved isolation backend, required policy, or kill control is unavailable or cannot be verified at startup, deny execution; never fall back to host execution.

Windows Sandbox has edition/hardware availability constraints and documented defaults that enable networking and clipboard sharing; configuration must explicitly disable such channels. AppContainer provides capability-based resource isolation, but its presence alone does not prove this product's policy is correct. Microsoft documents Job Objects as process grouping, control, accounting, and termination facilities; use them only as an additional supervisory control.

Sources: [Microsoft AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation), [Microsoft Windows Sandbox configuration](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file), [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

### Exact-action approval

Before each run, present a canonical action card containing the immutable input/source hashes, selected files, fixed runner/image identity and digest, exact executable and argument vector, working directory, filesystem read/write scope, network policy, resource ceilings, output handling, and expiry. Bind a one-use owner approval to the hash of this entire action payload. Any changed input, command, runner, path, permission, limit, or network setting invalidates approval and requires a new confirmation. Do not accept shell command strings, command chaining, model-supplied approval, or remembered blanket approval. Any later application of generated changes is a separate exact-diff review and confirmation action.

### Filesystem, secrets, and network

Start with a read-only snapshot of owner-selected project inputs; do not mount the live repository, home directory, profile, app data, credential stores, SSH keys, browser data, or provider configuration. Reject absolute paths, traversal, alternate data streams, junctions/reparse points, symlink escapes, hard links, and archive entries that can redirect writes. If future output is authorized, confine it to a fresh per-run staging area with bounded file count, file size, total bytes, and disk usage. Never let the worker write directly into the project or active application state.

Use an explicit environment allowlist, with no inherited credentials, tokens, secrets, or host-specific paths. Default network access to disabled at the OS boundary, including loopback access to Ollama, local APIs, and other host services. Do not permit per-action arbitrary network exceptions in this initial design. Any later network feature needs a separately reviewed destination/egress contract, including redirects, DNS rebinding, IP changes, and private-network access.

### Resource and output bounds

Enforce wall-clock, CPU, memory, process/thread count, disk, file count/size, handle, and stdout/stderr limits outside the worker where possible. Set conservative product defaults only after a separate supported-host study. Stop the run on quota breach. Treat output, generated diffs, filenames, and exit status as untrusted; escape rendered content and never auto-apply it. Do not write raw secrets or unrestricted output into logs.

### Audit and retention

Record owner identity, action/grant identifier, action hash, source and input digests, runner identity/digest, requested and enforced scope, approval time/expiry, sandbox identity, start/end times, termination/result state, exit code where known, quota events, and bounded output/diff hashes. Avoid recording secret values or full private file contents. Keep per-run artifacts in owner-inspectable local staging with an explicit expiry/delete action. If audit persistence fails before launch, fail closed; if final audit write fails, report the run outcome as not fully auditable and block further runs until resolved.

### Kill switch, cancellation, and crash recovery

The owner stop control first revokes the one-use grant and prevents new starts, then terminates the disposable VM/container and its supervised process tree. Use a bounded stop deadline. Report `stopped` only after the OS boundary confirms termination; otherwise report `stop uncertain`, retain the run identity and evidence, and block new runs. Do not retry, restart, or replay automatically. On app crash or restart, reconcile recorded sandbox identities with OS state, terminate any orphaned run, and keep its result `unknown` if termination or effects cannot be confirmed. Never equate UI cancellation with confirmed process termination.

### Safe result handling

Never import or execute worker-produced files in the host app. Present bounded diffs and metadata as inert text for owner review. A separate, explicit action would be required to apply an exact reviewed diff, with precondition hashes, backup/rollback behavior, and its own audit. Network-disabled execution limits direct exfiltration but cannot prevent every covert channel through outputs that an owner later shares; owners must review before export or application.

## AI security design review

**Reviewer:** Codex (GPT-6), author self-review on 2026-10-18. This is not an independent-model review, external penetration test, Windows implementation review, or red-team result.

Adversarial scenarios were checked against the proposed boundary:

| Scenario | Required response | Remaining concern |
|---|---|---|
| Prompt injection asks to read secrets, widen paths, or approve itself | Treat content as data; fixed schema and exact owner grant only | Model/UI confusion remains a risk; test hostile instructions in every input channel |
| Path traversal, symlink/junction swap, malicious archive | Snapshot inputs; reject link/reparse entries; stage writes; revalidate hashes | TOCTOU and Windows reparse behavior require native implementation review and adversarial tests |
| Network exfiltration to internet, LAN, or loopback | OS-level networking disabled; no host mounts or credentials | Sandbox configuration errors, host escape, and covert output remain possible |
| CPU/memory/disk/process/output exhaustion | Enforced quotas and hard wall-clock stop | Exact limits and enforcement need supported Windows builds and stress testing |
| User presses Stop during child-process spawn or worker crash | Revoke grant, terminate VM/job, bounded confirmation; otherwise uncertain and block | OS API races and app/service crash windows require native fault-injection tests |
| Sandbox or kernel escape / compromised runner | No automatic recovery or trust of output; keep disposable boundary and pinned artifact | Escape vulnerabilities and supply-chain compromise cannot be ruled out by this design |
| Worker output contains executable content or deceptive diff | Render inertly; never import/apply automatically; require exact separate confirmation | Human review can still be mistaken; a constrained diff applier needs separate design |

The design fails closed for missing isolation, network-policy uncertainty, expired or mismatched approval, resource-control failure, audit failure before launch, and uncertain termination. No unresolved issue is being represented as solved. Before any implementation decision, a reviewer independent of this author must assess the Windows isolation choice, policy enforcement, process/VM termination, path handling, and the threat scenarios above. A later implementation must add reproducible negative tests for all cases, plus Windows-version/edition and crash/cancellation testing.

## Open decisions and implementation gate

The following are intentionally unresolved and block implementation until separately decided and reviewed: supported Windows editions and virtualization prerequisites; exact Windows Sandbox versus hardened AppContainer/other VM boundary; runner artifact build, signing, provenance and update policy; allowed languages and fixed entrypoints; whether any staged file write is needed; whether network should ever be supported; retention and audit storage; owner approval UX and permission names; and measured resource ceilings. No paid service, account, signing certificate, download, or installation is authorized by this document.

**Gate:** Task 190 is complete only as this design deliverable and self-review record, with status `design_only`. Runtime implementation requires a distinct owner-authorized roadmap task, independent security review, supported-platform evidence, and explicit approvals for any new authority. This design grants none.

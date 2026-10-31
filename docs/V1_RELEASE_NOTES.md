# ERSELMETZ AI 1.0.0-rc.2 release notes

## Changes since rc.1

- Refined the native Aurora workspace so the Brain canvas has more room, the
  observed-step area is compact, and the chat pane remains usable at supported
  widths and Windows scaling factors.
- Added voice-first controls with explicit capture state, offline speech output,
  Stop controls and truthful unavailable states.
- Added Brain zoom controls and bounded, owner-visible chat-learning candidates.
- Detects every Ollama entry while allowing only local chat-capable models in
  the local model picker. Embedding models and cloud stubs remain visibly
  classified instead of being routed as ordinary local chat.
- Added a simple provider setup window for Ollama discovery and optional Gemini
  configuration. Cloud turns still require exact outbound review and consent.
- Preserved default-deny permissions, in-process owner authentication, no silent
  downloads, no automatic cloud fallback, and no default TCP listener.

## Candidate scope

This candidate packages the PySide6 native desktop, authenticated in-process
backend, local chat and model selection, Projects and pending Tasks, scoped Brain
retrieval, provider connections, bounded Agent workflows, approvals, resource
queues, stop controls, backup/restore and native Settings/Advanced views. Node,
Electron and Next.js are not runtime or build dependencies.

The authenticated local owner can create Projects and pending Tasks. Creation is
not execution: dispatch and every provider/tool/automation side effect retain
their separate permission, preview, consent or approval boundary.

## Tasks 213-217 disposition

- 213: superseded; V1 UI tokens, native states, accessibility-oriented controls
  and screenshot evidence are carried by Tasks 223, 229 and 230.
- 214: superseded; native single-instance and shared in-process backend behavior
  replace the former Electron window contract.
- 215: superseded; current native workspace, conversation, Project/Brain,
  approval and trace isolation are covered by current deterministic regressions.
- 216: superseded; current ResourceManager queues, cancellation, device ownership
  and stop paths are covered. This is not distributed coordination.
- 217: superseded; the original three-Electron-window hardware exercise was not
  performed. Task 230 supplies narrower current-user packaged Windows and local
  Ollama evidence only.

## Known limitations

- The installer is unsigned; no Authenticode or SmartScreen reputation claim.
- Separate clean-Windows-account, other Windows versions, physical media devices,
  assistive technology and paid/cloud provider checks remain unverified.
- Local model quality, retrieval accuracy, latency and hardware use vary. Test
  results are bounded evidence, not a general quality guarantee.
- Optional capability packs are installed only after owner confirmation and are
  not all verified in the packaged application.
- The app has no supported remote public API and no automatic updater or deploy.
- Uninstall keeps user data by default; removal requires an explicit choice.

## Upgrade and recovery

Back up from Advanced before replacing an installation. Install per user, keep
the matching `_internal` directory and build stamp, and start Ollama separately.
The application never silently downloads a model. See `packaging/README.md` for
artifact integrity, data paths, recovery and update boundaries.

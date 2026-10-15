# ERSELMETZ AI product audit — 15 October 2026

## Product health and verification boundary

ERSELMETZ AI has a substantial, functioning local application foundation, but it is **not yet a coherent, release-ready beginner product**. The secure local sign-in and coordinator chat journey works against a deterministic provider in a real Chromium browser. Projects, memory, providers, workflows, and visualizations exist, but their setup, navigation, permissions, and persistence boundaries remain fragmented. Passing tests do not establish live AI quality, hardware support, or release readiness.

The audit found and repaired production browser startup failures across ten pages, invalid coordinates in several 3D map layers, initial 3D framing, a model-management regression, repeated dashboard authentication failures, sign-in return navigation, narrow-screen overflow, theme contrast, visible legacy branding, and inaccurate documentation. No new subsystem, provider, frontend framework, capability-pack lifecycle, or permission grant was introduced. No commit or push was performed.

Verification combined source tracing, the full Python and Node suites, a real loopback Uvicorn/Chromium flow, all 25 Python UI pages plus both built desktop pages at 1280/768/390 CSS pixels, local-link/asset requests, API authentication probing, production Next export, and isolated startup checks. UI tests used temporary SQLite databases. No personal workspace data, owner credential store, provider secrets, camera, microphone, or desktop application was used for the audit flows.

**Status meaning:** WORKING means the stated bounded behavior was exercised by the named test/flow; PARTIAL means a foundation exists but integration, environment, usability, or supported scope is incomplete. MISSING means no implementation was found in the audited paths. PLANNED means the authoritative roadmap explicitly leaves the work incomplete. NOT APPLICABLE means a named library or approach was deliberately not selected. These labels do not certify every possible input or deployment.

## Repository, roadmap, and distribution

- Initial branch: `main`; clean tracked and untracked status.
- HEAD and local `origin/main`: `eba16ce78af9f7337e6b586b288e6944ffc47705` (`feat: improve onboarding and accessibility clarity`). A read-only `git ls-remote origin refs/heads/main` also returned that exact hash.
- Recent capabilities: unified settings, interactive Three.js organization map, memory relationship explorer, unified multimodal controls, and onboarding/accessibility changes. Older maintenance, portability, updates, and performance foundations are also present.
- `docs/tasks-data.mjs` is authoritative. Tasks 134 and 170 are deferred and incomplete; Tasks 171–174 are scoped completed milestones; Task 175 remains planned because representative owner acceptance is incomplete. The premise that every historical task is complete is false.
- Python entry points: `app.main` (CLI), `app.api.app:app` (default rejecting API), `app.local` (explicit owner-authenticated loopback UI), `app.desktop_launcher`, `app.desktop_runtime`, and `launch_erselmetz_ai.pyw`.
- UI entry points: `app/webui/router.py` and `app/webui/static/`; Electron `desktop/main.cjs`, bootstrap and preload; Next static export in `desktop-ui/src/app/` with Home and Settings pages.
- Public docs: `docs/server.mjs`, `docs/index.html`, `docs/vercel.json`. Internal approved Markdown portal: `corporation_docs/`. These are separate applications/content boundaries.
- Dependencies: pinned base `requirements.txt`; optional semantic `requirements-knowledge.txt`, optional image `requirements-image-processing.txt`; desktop build/automation requirements; locked Electron and Next packages. No dependency changes were made.
- Docker runs the Python CLI, not the desktop/browser product. Compose configures host Ollama and a projects bind mount; it exposes no HTTP UI port. This is internally consistent for its CLI scope, not an install-to-chat distribution path.
- Next production export builds. The unsigned Windows installer is a local acceptance artifact, not evidence of a currently signed/public/stable distribution. No installer rebuild, install, upgrade, or public release was performed. Task 170's independent security/privacy review remains deferred.

## Feature matrix

Paths below are repository-relative. Test names identify actual validation included in the suite; optional real-service execution is called out separately.

| Area | Feature | Status | Evidence | Test | Issue | Recommended action |
|---|---|---|---|---|---|---|
| Core | Startup and runtime identity | WORKING | `app/main.py`, `app/runtime/factory.py` | runtime tests; isolated interactive startup/exit and noninteractive startup | ONLINE CLI labels describe initialized components, not healthy AI services | Distinguish initialization from readiness |
| Core | Corporation/Node organization | WORKING | runtime factory, registries | `test_corporation.py`, runtime tests | Local installation model; no distributed organization service | Preserve local scope |
| Core | Employees | PARTIAL | employee registry, management API and UI | employee core/API/Node tests; page sweep | Local owner lacks `employee:manage`; organizational state not a durable admin system | Design explicit owner management policy and persistence |
| Core | Agents | PARTIAL | `app/agents/`, `/api/agents`, chat selector | agent/API and chat browser tests | No dedicated Agents management page; Employees and technical Agents remain distinct | Add understandable team/Agent inspection in approved scope |
| Core | Positions/reporting | WORKING | positions service, `/ui/positions`, structure map | positions and structure tests; page sweep | Technical identifiers and revision contracts exposed | Improve labels and selectors |
| Core | Task persistence and routing | WORKING | task registry, router, SQLite | task/routing/persistence tests | Deterministic routing, not autonomous semantic assignment | Keep distinction explicit |
| Core | Task creation UI | PARTIAL | `/ui/tasks`, `POST /api/tasks` | API tests; local-owner probe returns 403 | Local principal lacks `task:create`; chat proposal path is separate | Hide unauthorized actions or approve an explicit owner policy |
| Core | Projects | PARTIAL | project registry, `/ui/projects` | project tests; local-owner create returns 403 | Normal owner cannot create from existing form; no project delete/lifecycle product flow | Resolve owner workflow before promoting Projects to beginners |
| Core | Orchestrator/controlled execution | WORKING | orchestrator, task dispatch service/API | controlled-execution and task-dispatch tests | Explicit dispatch; no general autonomous organization | Keep explicit execution/approval boundary |
| Core | Queue/concurrency | WORKING | `app/orchestrator/execution_queue.py` | queue, recovery, dispatch tests | Restarted claims can have unknown remote outcomes | Require human resolution, never implicit replay |
| Core | Resource management | PARTIAL | resource manager and monitoring snapshots | resource/runtime/monitoring tests | Default snapshot has no configured manager; slots are not hardware capacity | Provide guided capacity configuration without invented hardware claims |
| Core | Provider/model routing | WORKING | provider registry, assignment services | provider/model and assignment guard tests | Reassignment previously required chat identity even in non-chat runtimes; fixed | Retain execution guards |
| Core | Availability/model inventory | PARTIAL | local models, provider connections, availability services | local-model/provider-connection tests | Explicit on-demand checks; live Ollama unavailable in this environment | Verify against a separately approved installed service |
| Chat | Coordinator/global organization chat | WORKING | owned-chat service, chat API and `/ui/chat` | real browser sign-in/send/reply/close/logout with fake provider | This proves integration, not live model quality | Repeat supported-provider acceptance separately |
| Chat | Individual Employee/Agent chat | WORKING | employee-chat service/API/module | Employee chat Python/Node tests; page boot sweep | In-memory lifecycle and advanced controls; browser boot was broken and fixed | Add a representative owner journey |
| Chat | Conversation lifecycle/context | WORKING | conversation models, context and owned-chat services | lifecycle/context/ownership tests | Pending/closed/conflicting turns remain bounded | Preserve immutable scope and no automatic retries |
| Chat | Conversation history | PARTIAL | chat-history service and explicit archiving | history tests | Open conversation catalog is process-local; durable history is consented, not automatic | Explain restart/archiving in main chat |
| Chat | Task proposals from chat | WORKING | chat-task proposal/review/confirmation services | chat proposal and creation tests; Node proposal flow | Creates pending Tasks only after confirmation | Keep review separate from dispatch |
| Chat | Activity/status visualization | PARTIAL | task progress, workflow map, dashboard | progress/workflow/dashboard tests | Snapshot evidence, not live token/Agent telemetry | Label timestamps and unknown outcomes |
| Knowledge | Explicit conversation memory | WORKING | conversation store and chat knowledge service | conversation-memory/chat-knowledge tests | Consent/expiry; withdrawal cannot recall provider-held copies | Preserve explicit controls |
| Knowledge | Project isolation/provenance | WORKING | project knowledge, memory management, retrieval | project/context/security and semantic evaluation tests | Tests establish covered owner/scope boundaries, not a universal security proof | Retain negative cross-scope tests |
| Knowledge | Organization publications | WORKING | corporation knowledge service | corporation-knowledge tests | Publications are independent immutable snapshots with source expiry | Explain withdrawal vs private-source deletion |
| Knowledge | Memory management UI | PARTIAL | `/ui/memory`, `memory.mjs` | memory Python/Node tests; browser boot fixed | Requires raw scope IDs, ISO expiry; owner lacks generic `memory:manage` | Guided selectors and explicit management permission design |
| Knowledge | Semantic embeddings/vector store | PARTIAL | sentence-transformers adapter, Chroma adapter | semantic tests with deterministic adapters | Current runtime status is disabled; actual packages/model absent | Manually configure optional local model/store and test real adapters |
| Knowledge | RAG/context integration | PARTIAL | `app/knowledge/rag_context.py`, context retrieval, chat knowledge | context/retrieval/evaluation tests | Explicit per-turn retrieval exists; no automatic universal chat brain | Keep automatic injection off unless separately approved |
| Knowledge | Visual Memory explorer | PARTIAL | memory scope/provenance/retrieval relationship UI | memory relationship Node tests; browser page | Real selected-scope records; no inferred semantic clusters or universal graph | Improve scope selection before adding graph inference |
| Knowledge | AI-managed documentation | PARTIAL | documentation review and knowledge proposal services | documentation-review/knowledge-proposal tests | Bounded proposal/review; not autonomous documentation maintenance | Describe review-only contract |
| Tools | Tool registry/calling | PARTIAL | `app/tools/`, explicit adapters | tools/MCP/coding tests | No universal Agent-to-tool execution product loop | Integrate only through explicit capability approvals |
| Tools | MCP | PARTIAL | synchronous allowlisted MCP client | in-process/local MCP tests | Trusted host processes; not OS isolation or general browser UI | Preserve limits; publish supported integration recipe |
| Tools | GitHub/repository study | PARTIAL | discovery/inspection/study services and chat UI | GitHub/study tests | Allowlisted read-only evidence; no remote GitHub writes | Expose allowlist setup clearly |
| Tools | Browser research | PARTIAL | `web_research.py`, browser inspection | research/inspection tests | Explicit bounded allowlisted retrieval, not an unrestricted web search engine | Describe exact supported scope |
| Tools | Coding tools | PARTIAL | MCP coding adapter and patch proposal services | coding/patch tests | Returns bounded proposals; does not grant arbitrary execution | Retain review/approval stages |
| Tools | External services/capability registry | PARTIAL | capability inventory/discovery/evaluation/integration | capability suites | Metadata/evidence foundations do not activate arbitrary integrations | Distinguish declarations, authorization, availability |
| Vision | Screen capture/screenshots | PARTIAL | browser capture plus Electron selection/preload | screen capture Node/Electron tests | One-frame user action; physical chooser/capture not exercised here | Test actual Windows chooser with owner consent |
| Vision | Camera | PARTIAL | camera module, Electron permission gate | camera capture/stop/security tests | One frame, video only; hardware untested | Hardware acceptance separately |
| Vision | Image input/model vision | PARTIAL | temporary attachments, Ollama/Gemini vision adapters, chat API/UI | image/vision/consent tests | Live vision provider untested; per-turn consent required | Validate supported model capability with owner |
| Vision | Pillow processing | PARTIAL | optional `image_processing()` adapter | bounded worker tests; 2 real-Pillow tests skipped | Chain stops at application service: no API/UI attachment transformation | Keep optional; plan integration separately |
| Vision | OCR/Tesseract | PARTIAL | OCR service and explicit Tesseract executable adapter | OCR/Tesseract tests | Chat exposes explicit optional local OCR; installed engine/language data and real extraction unverified | Provide supported setup and preview contract |
| Vision | MSS/OpenCV | NOT APPLICABLE | browser/Electron capture and Pillow selected instead | dependency/source inventory | Not integrated dependencies; absence does not mean capture is missing | Do not install redundant libraries merely to match a list |
| Speech | Browser local recognition/microphone | PARTIAL | `voice.mjs`, local-only recognition and WAV capture | voice Node/Electron tests | Browser/device language support varies; physical input not tested | Test supported browser and installed language |
| Speech | Faster-Whisper | PARTIAL | optional explicit-directory local provider and voice API/UI | local-speech/API/voice tests | Package and local model absent; no silent download | Document manual optional runtime/model setup |
| Speech | Consented cloud transcription | PARTIAL | Gemini voice boundary and separate consent | Gemini voice/voice UI tests | No cloud request or account billing verification here | Repeat against owner-approved account only |
| Speech | Local TTS/playback | PARTIAL | device-local Web Speech voices and bounded reply queue | TTS/voice tests | Actual installed voice/audio output untested | Test local voice availability and stop behavior |
| Speech | pyttsx3/Coqui/Kokoro/Edge TTS | NOT APPLICABLE | selected device-local browser output path | source/dependency inventory | No implemented integrations found for these libraries | Do not claim or require them |
| Automation | Browser actions/Playwright | PARTIAL | scoped browser adapter with exact-origin policy | scoped-browser tests | Bounded adapter/approval/trace chain; no in-app execution control | Approved UI/API integration is separate work |
| Automation | Desktop actions | PARTIAL | scoped native UIA adapter; optional pywinauto | scoped-desktop tests | Exact button invocation only; optional native backend/hardware untested | Keep allowlist empty by default |
| Automation | Selenium/pyautogui/Open Interpreter | NOT APPLICABLE | selected Playwright and semantic UIA approach | source/roadmap inspection | No integrated implementation found; pyautogui explicitly excluded | Avoid broader control surface without approval |
| Automation | Action approvals/audit/traces | WORKING | capability approvals/audit and automation traces | approval/audit/trace suites | Trace test file had collection typo, fixed | Preserve target/digest/actor binding |
| Automation | Cancellation/timeouts/emergency stop | PARTIAL | emergency service, local middleware and media events | stop/timeout/voice/camera tests | Local waiting can stop; remote provider outcome may remain unknown | Never label uncertain remote work canceled |
| Maintenance | Monitoring/diagnostics | WORKING | monitoring, failure detection, diagnostic service | monitoring/failure/diagnostic tests | Readouts and supplied evidence are not an autonomous monitor | Preserve truthful unknown states |
| Maintenance | Patch proposals/development | WORKING | disposable-copy patch services | proposal/patch tests | No unrestricted source mutation | Retain exact selected-file boundaries |
| Maintenance | Automated testing/code review | PARTIAL | host testing, advisory Agent review, Docker path | testing/review/sandbox tests | Host tests use OS permissions; actual Docker backend absent here | Prefer explicitly configured Docker for untrusted code |
| Maintenance | Approval/checkpoint/activation | PARTIAL | maintenance approvals/checkpoints/experiments | maintenance suite | Controlled workflow; no autonomous merge/push; Docker live unverified | Maintain exact patch/source approval |
| Maintenance | Self-improvement pipeline | PARTIAL | workflow linking and bounded experiments | maintenance/workflow tests | No unattended general self-modifying product | Describe stages and manual handoffs |
| Search | Global search | MISSING | inspected APIs/UI modules | source/route inventory | No cross-product search contract | Design a scoped search task; do not fake one |
| Search | Project/Task/Agent/doc/conversation text search | MISSING | list/detail UI modules | Node/API inventory | Selectors and lists are not full-text search | Prioritize after beginner journeys |
| Search | Activity filtering | WORKING | bounded `limit` and exact `task_id` | activity API/Node tests | Not general log full-text search | Keep coverage explicit |
| Search | Map filtering | WORKING | 3D name/ID/type/state and layer filters | visualization Node tests | Bounded source snapshot only | Preserve record/render limits |
| Search | Semantic knowledge search | PARTIAL | scoped semantic API/UI | semantic tests | Disabled without optional model/store; no global document index | Enable only with explicit setup |
| Visualization | Real Three.js/WebGL map | WORKING | vendored Three.js, scene/model/view modules, protected snapshots | real Three scene tests; browser rendered screenshot | Invalid layer coordinates and initial framing fixed | Add richer real-world graph acceptance |
| Visualization | Orbit/rotate/zoom/pan/select/layers | WORKING | canvas pointer handling and labeled buttons/list alternative | visualization interaction tests | Keyboard/list path exists; not a complete globe simulation | Keep accessibility alongside 3D |
| Visualization | Project/task/Agent workflow relations | PARTIAL | structure/workflow map and source-backed edges | map/model tests | Independent snapshots, no atomic/live telemetry; department API absent | Show only supported relations and timestamp differences |
| Visualization | RAG clusters/semantic brain/globe | MISSING | map shows retained metadata/provenance, not embeddings topology | source and rendered review | No genuine cluster/globe implementation found | Separate roadmap proposal; extend 172/173 only after approval |
| UX | Shared product shell | PARTIAL | nine traditional pages use `_navigation`; later pages use local nav | 25-page browser/route sweep | Same tokens, inconsistent header/sidebar/active-state coverage | Incremental shared layout, no framework rewrite |
| UX | Unified Settings | PARTIAL | Next `/desktop/settings/` | desktop tests, production build, and rendered browser sweep | Available through exported desktop UI, not equivalent Python `/ui/settings` route | Make entry point consistent across supported modes |
| UX | Beginner setup/owner acceptance | PLANNED | Task 175 acceptance evidence | roadmap tests | No representative new/experienced owners participated | Complete Task 175 before release claims |
| Release | Capability-pack lifecycle | PLANNED | Task 134 explicitly deferred | roadmap/docs tests | Trust anchor/artifact/loading boundary incomplete | Keep unavailable |
| Release | Stable release/security review | PLANNED | Task 170 explicitly deferred | roadmap/docs tests | No independent reviewer or stable-release evidence | Complete explicit release gates |

## UI, navigation, accessibility, and visual design

All 25 Python UI routes load: Home, Documentation, Activity, Updates, Employees, Positions, Providers, Tasks, Projects, Memory, Chat, Inventory, Preferences, Backup, Readiness, Employee chat, Local models, Assignment policy, Online provider, Workflows, Structure, Workflow map, Visualization, Provider connections, and local Login. The route test also authenticated and successfully loaded 54 distinct local link/asset targets. Protected download links were tested as authenticated links, not mistaken for public pages.

All 25 Python pages plus built `/desktop/` and `/desktop/settings/` were opened in Chromium and checked for page errors, one H1, and document overflow at desktop/tablet/phone widths. This is a useful regression check, not a complete screen-reader, keyboard-trap, color-contrast, or all-form-state certification. Existing browser-module tests cover many loading/empty/authentication/error/stale-state behaviors. Real hardware and all management actions were not exercised by the page sweep.

The dark tokens, cards, contrast, focus styles, reduced-motion rules, readable labels, and useful 3D/list alternatives provide a credible visual foundation. The product still mixes a sidebar/header shell with standalone pages and inline pipe-separated navigation. Shared navigation has correct active states where `_navigation` is used; later pages do not share that consistent active-state system. Employee chat and provider setup are reachable through page links, not all from one sidebar. Settings exists in the Next export rather than the Python primary navigation. No broken local link was found in the tested local mode.

The chat screen places a very large capability/safety panel before the conversation. Screenshot review shows that the primary chat input sits far below the first viewport. Keep the stop control visible but compact the informational indicators into an expandable region in a future usability pass. The memory page exposes scope IDs and ISO timestamps; the provider pages expose connection IDs, model IDs, slot counts, and policy JSON. Those are operator experiences, not minimal beginner setup.

The 3D map is real and data-backed, not decorative marketing. It is bounded to 60 selected nodes and 119 recorded links. Inspection found that `addNode` omitted the vertical layer index for several source types, producing non-finite coordinates; assigning finite per-layer defaults repaired those layers. Initial renderer resize also occurred before scene creation, losing aspect information; the view now retains the aspect and fits the source-backed node bounds. A new regression verifies finite coordinates and projects nodes inside the wide/narrow camera frustum. Final screenshot review shows all eight default-runtime nodes visible. It still needs a stronger product hierarchy, node labels/discovery, and representative populated workflows. No department data, semantic clustering, or atomic live flow is invented.

## First run, authentication, and end-user answers

1. ERSELMETZ AI is a local simulated AI organization with controlled chat, Tasks, Projects, and integration foundations.
2. For an available trusted Windows build, install and open it; current local installer evidence does not establish a public stable release. Developers may use the documented explicit local launcher. The default API alone is intentionally not a signed-in product session.
3. Create the owner password at first desktop setup, enter it to start the backend on later launches, then sign in to the local browser session. The repeated password step remains friction. No auto-login was added.
4. Configure a supported local model through Local models/Provider connections, or explicitly connect Gemini and review its separate consent prompts. Home reports configuration, not a provider health guarantee.
5. Open Chat, select a team member, start a conversation, and send. Provider failure must be shown as a failure; tests prove the UI path using a deterministic provider, not that an unavailable local model will reply.
6. Projects are visible, but the normal owner currently receives 403 for creation. This is an unresolved product workflow gap, not an empty-state success.
7. Memory is `/ui/memory`; choose the exact authorized resource scope. Semantic retrieval is disabled in the audited environment until optional dependencies, a local embedding model, and a vector-store directory are explicitly configured.
8. Employees, Positions, chat selectors, and maps expose the team. There is no separate full Agent-management product page.
9. Automation adapters exist with policies and approvals; no normal in-app automation execution screen is exposed.
10. Vision/Voice controls are in Chat. Browser support labels are not proof of hardware permission, a local speech model, or provider vision readiness.
11. The 3D structure is `/ui/visualization`. Organization and workflow list views are separate routes. A semantic RAG globe is not implemented.
12. Minimum AI setup is a usable provider/model assignment plus local owner sign-in. Resource policies, software management, backup, maintenance, and capability evidence are advanced.
13. Permissions still govern every backend operation. The ordinary local principal is broad in some protected capabilities but does not include generic Project/Task/Employee/memory management permissions. Do not infer access from an enabled-looking form.
14. Stable release, capability packs, representative usability acceptance, global search, automatic general tool use, semantic clusters, and hardware/cloud acceptance remain incomplete or unavailable.

Authentication remains fail closed: default backend rejects, local access binds loopback and validates host/origin, mutation requests require same origin and session CSRF, cookies are HttpOnly/SameSite Strict, sessions expire, sign-in is rate limited, and logout revokes the session. A signed-out dashboard now stops its panel-request fan-out after a 401 and clears/hides protected panel data. Independent safety/suggestion modules still perform their own session checks; this is not a claim of exactly one total network request for the entire page. A 403 remains resource-specific and does not hide otherwise authorized panels. Python page sign-in links now carry an explicit `next` destination because the local no-referrer policy intentionally suppresses browser referrers. Sign-in returns to those same-origin application destinations and rejects external/login-loop destinations. Desktop sign-in links without `next` still fall back to Python Home.

## Multimodal integration chain and automation safety

| Capability | Dependency/adapter → service → API → UI → permissions → test boundary |
|---|---|
| Screen/camera | Browser media/Electron chooser → temporary image attachment service → chat image routes → Chat controls → owner/media consent and scoped checks → deterministic browser/Electron tests; no physical capture performed |
| Vision model input | Ollama/Gemini adapters → owned chat/image service → consented message routes → temporary selection UI → per-turn image transfer consent → provider-contract tests; no live model evaluated |
| Pillow | Optional package → child-worker processing adapter → application-service accessor → **no processing API/UI integration** → caller-selected bounded operations → real package absent, two legitimate skips |
| OCR | Explicit Tesseract binary/language data → local adapter → OCR application service → `include_local_ocr` in consented chat image requests → Chat OCR checkbox → explicit image selection/transfer consent and untrusted evidence → synthetic executable/result and chat vision tests; real engine unverified |
| Microphone/local speech | Browser local recognition or bounded WAV capture; optional Faster-Whisper/model → local voice service/routes → Chat voice controls → owner action, session and consent → deterministic tests, actual hardware/model absent |
| Cloud speech | Gemini adapter → voice service/routes → reviewable transcript draft → one-use cloud consent → stubbed provider tests, no account request |
| TTS | Browser-installed local voices → bounded queue → client-side playback (no Python TTS API needed) → Chat controls → explicit playback/stop → voice tests, audible output unverified |
| Browser automation | Playwright → scoped origin/action adapter → approval/digest/trace services → **not a general app execution API/UI** → explicit policy, actor/session approval and emergency-stop checks → deterministic scoped tests |
| Desktop automation | Optional pywinauto UIA → exact native button adapter → approval/trace services → **not a general app execution API/UI** → exact process/window/control allowlists → native backend not installed; deterministic safety tests |

No silent model download or unrestricted automation path was enabled. Host-process MCP servers and host test execution are not OS sandboxes. Remote operations may continue after local waiting stops; unknown remote outcomes remain unknown and are not automatically replayed.

## API, security, stale state, and performance review

The default API's OpenAPI inventory contained 111 `/api/` operations; every operation returned 401 without a principal, including substituted missing-resource path parameters and empty mutation bodies. The explicit local app inventory contained 143 API paths/173 operations. This probes the unauthenticated boundary; it is **not** exhaustive authenticated contract fuzzing of 173 operations. The Python suites separately exercise permissions, validation, missing/conflicting/expired resources, ownership, and safe response contracts.

Inspected boundaries include permission dependencies, local CSRF/origin middleware, documentation filename/symlink constraints, source staging paths, owner-scoped memory lookup, vector candidate revalidation, cloud image/audio consent, safe error translation, and bounded automation policies. No secrets were printed or copied into the report. No external penetration test, dependency vulnerability scan, independent privacy review, or exploit-completeness claim is made. Three Windows symlink tests remain unexecuted because the environment lacks symlink privileges; this does not count as proof that those paths are safe on this host.

Most list/detail modules distinguish empty results from failures and clear prior records after failed refresh. Workflow maps explicitly retain stale-marked snapshots when disconnected. Memory scope/revision and semantic search generation guards reject stale results. Tests cover network/malformed/401/403/404/conflict/provider failures at their stated boundaries; the browser sweep itself is primarily startup/layout coverage. Dashboard 401 fan-out and page initialization were real integration defects despite green module tests.

The map bounds nodes/edges, caps pixel ratio, renders on demand, has reduced-motion/list fallback, and offers an explicit 300-frame measurement. It does not prove GPU completion, model hardware fit, or a supported minimum-device performance envelope. Dashboard freshness timer updates labels, not provider polling. Some API lists are still read in full before presentation limits are applied; pagination and populated-workspace performance deserve follow-up. The optional embedding adapter caches a local model rather than loading it per request. No speculative optimization or model download was added.

## Branding and documentation reconciliation

The public Task 100 title `ERSELMETZ AI CORPORATION Platform` appeared in roadmap data, the visible updates manifest, and a test expectation. Those three occurrences now say `ERSELMETZ AI Platform`. Task numbers and acceptance scope are unchanged. Git history retains historical wording.

`Corporation Web UI` remains in architectural descriptions in `ARCHITECTURE.md`, `corporation_docs/api-and-web-ui-boundaries.md`, and Task 46's foundation description. It identifies the domain/presentation boundary rather than renaming the product. Corporation classes, API concepts, repository/package paths, database identifiers, and historical architecture remain intact. Exact searches found no additional uppercase `AI CORPORATION`/`Corporation dashboard` product labels beyond the corrected title and these architectural references.

README had stale claims that Task 174 was planned, Ollama was the only implemented provider, browser sign-in did not exist, and Task project associations were not persisted. These were corrected or scoped to default API mode. Older foundation/future summaries are now explicitly labeled historical and point to the authoritative roadmap. The opening guide now states the installer distribution boundary. The README remains long and operator-heavy; a short, dedicated guide with tested first-run screenshots should replace the giant historical narrative as the beginner entry point.

Claims that should **not** be made from this repository: every roadmap item complete; stable public release; app-managed capability packs; unrestricted autonomous tools/automation; always-ready vision/voice/semantic memory; a global full-text search; an inferred RAG cluster/globe; registry presence as provider health; software slots as hardware capacity; local cancellation as confirmed remote cancellation. These are absent, deferred, conditional, or outside implemented scope. Existing scoped roadmap acceptance language generally acknowledges these limitations; product summaries must retain them.

## Defects fixed and remaining priorities

Fixed in this audit:

1. Invalid `rom __future__` import blocked the entire Python test collection.
2. Activity, Documentation, Employees, Positions, Projects, Providers, Tasks, Updates, Employee chat, and Memory destructured missing startup options, breaking actual page initialization. Their injected-option module tests had missed the normal browser entry point.
3. Model replacement/CLI assignment constructed owned chat even without a Corporation identity. Non-chat runtimes now retain registry execution locking without requiring chat identity; all active-run guards remain tested.
4. Signed-out dashboard issued protected panel requests and repeated sign-in failures. Identity-first 401 handling now suppresses that fan-out and clears/hides protected cards.
5. Sign-in always returned Home. Safe originating app destinations are now preserved with external destinations rejected.
6. Safety panel used a nonexistent CSS surface variable and a white fallback in the dark theme.
7. Advanced JSON output and assignment-policy editing overflowed at 768/390px.
8. Several map layers had non-finite vertical coordinates. Per-layer finite defaults now render real records.
9. Initial 3D view lost the prior canvas aspect ratio and did not frame the source nodes. Aspect retention and node-bound framing are now covered by projection tests.
10. Malformed page punctuation, old visible product title, stale provider/auth/Task/roadmap documentation.

Remaining priority order:

1. **P1 — Finish Task 175 with representative owners.** Install/sign-in/provider setup/chat/create Project/retain/retrieve memory must be walked by new and experienced owners. Record failures rather than marking acceptance complete.
2. **P1 — Resolve permission/UI mismatch.** Define intended owner/admin grants for Project/Task/Employee/memory management, then hide or explain actions not permitted. Direct probes currently return 403 for normal-owner Project and Task creation. No broad grants were added during this audit.
3. **P1 — Persistence/setup continuity.** Explain process-local conversations, provider connections and preferences; preserve only explicitly approved configuration through an intentional persistence contract. Do not silently retain credentials/transcripts.
4. **P1 — Supported provider/hardware acceptance.** Validate an actual installed Ollama model, optional cloud flow with consent, local audio devices, camera/screen selection, optional semantic and native automation adapters. Test failures without retries or secret disclosure.
5. **P2 — Shared navigation/settings and compact chat.** Unify headers/sidebar/active states incrementally, expose one Settings entry in supported modes, replace raw-ID choices where contracts permit, keep a compact visible stop control, and put chat before advanced controls.
6. **P2 — 3D and memory product quality.** Improve discoverability/labels, resize behavior and real populated graph acceptance. Keep metadata relationships separate from unimplemented semantic clustering. Task 172 owns the implemented interactive map and Task 173 the implemented memory relationship explorer. Neither proves semantic cluster inference or a globe. A real RAG globe needs a separately approved successor task after the existing Task 175 queue, with a permission-scoped bounded graph API over existing authoritative memory records and precomputed embedding metadata, versioned snapshots, and the existing Three.js/list renderer. Do not add model downloads, a new vector architecture, or a second frontend framework merely for visualization.
7. **P2 — Search and scale.** Approve a separate permission-scoped search contract, then pagination and populated-workspace performance. No global search was fabricated.
8. **Release gate — Task 170.** Independent security/privacy review and actual signed distribution acceptance remain prerequisites for a stable-release claim. Task 134 remains explicitly deferred.

## Validation results and review inventory

Initial validation stopped on one Python collection error (the trace-file typo). After repair, the first full run returned 1,258 passed, 2 failed, 8 skipped; both failures exposed the model-assignment/chat-identity regression. The focused repair run passed all 76 selected tests. An intermediate complete run passed 1,262 with 8 skips. A later repeat caught the audit report itself expanding the approved internal document catalog: it returned 1,261 passed, 1 failed, 8 skipped. The report was moved to this repository-root file rather than changing the catalog test. The focused catalog run then passed 11 with 2 existing symlink skips. Final results below supersede these intermediate runs.

The final eight skips comprise three Windows symlink-privilege limitations, three Ollama-unavailable checks, and two optional-Pillow tests. No failure was converted to a skip. The two warnings are existing AnyIO BlockingPortal and Starlette 422-name deprecations. Actual Docker isolation, a live cloud provider, real embeddings/Chroma, audio hardware, camera and desktop UIA were not validated merely because their deterministic contract suites passed.


The final validation record and exact changed-file/status snapshots are appended below. All results are local to this checkout/environment. Live-service/hardware gaps remain limitations, not successful tests. No dependencies were installed or changed for the audit, and no commit/push/checkpoint was created.

### Exact validation commands and results

| Check | Command / method | Result |
|---|---|---|
| Full Python suite, final repeat | `.\.venv\Scripts\python.exe -m pytest -q -rs` | **1,262 passed, 8 skipped, 2 warnings; 0 failures (213.26 seconds)** |
| All Node/browser modules, public docs/roadmap, desktop controls | `node --test tests/*.mjs docs/test/*.mjs desktop/test/*.cjs` | **242 passed; 0 failed, skipped, canceled, or todo** |
| Public docs/roadmap/Vercel subset | Included `docs/test/*.mjs` above | 16 passed, included in 242 |
| Electron control/security subset | Included `desktop/test/*.cjs` above | 17 passed, included in 242 |
| Browser-module subset | Included `tests/*.mjs` above | 209 passed, included in 242 |
| Focused model/CLI/assignment/trace repair | Python provider-model, command-interface, assignment-guard, local-model, automation-trace files | 76 passed |
| Cross-page Chromium/link sweep | `pytest tests/test_product_audit.py -q -s` | 2 passed; 25 Python routes, 54 unique local targets; **27 browser pages** including both built desktop exports; no page errors or overflow at 1280/768/390px |
| Real local chat plus Web UI regressions | `pytest tests/test_product_audit.py tests/test_webui.py tests/test_local_chat_browser.py -q -s` | 15 passed before adding the two exported desktop pages to the sweep |
| Map/update/route focus | `pytest tests/test_product_audit.py tests/test_updates.py tests/test_visualization_page.py -q -s` | 10 passed; includes all 6 update-manifest/API tests |
| 3D renderer focus | `node --test tests/test_visualization_ui.mjs` | 15 passed, including real Three.js scene/model and wide/narrow projection checks |
| Desktop production build | `npm.cmd --prefix desktop-ui run build` | Passed token sync, optimized Next compilation, TypeScript, static export for Home/Settings; no production Next server required |
| Python compilation/import coverage | `.\.venv\Scripts\python.exe -m compileall -q app tests`; suite collection/imports | Passed |
| JavaScript syntax | `node --check` on each top-level `app/webui/static/*.mjs` | 37 modules passed |
| Installed dependency consistency | `.\.venv\Scripts\python.exe -m pip check` | `No broken requirements found.` |
| Interactive startup | Temporary SQLite; `main(interactive=True)` with explicit `exit` input | Passed initialization and shell exit |
| Noninteractive startup | Temporary SQLite; `main(interactive=False)` | Passed without provider generation |
| Default API authentication | TestClient; all OpenAPI `/api/` operations with no principal | 111/111 returned 401 |
| Local API inventory/login | Explicit loopback TestClient | 143 paths, 173 operations; session 401 before sign-in, login 200 |
| Local-owner management limitation | Valid signed-in session + Origin/CSRF; supported create payloads | Project creation 403; Task creation 403; recorded as unresolved permission/workflow mismatch |
| Optional semantic readiness | Authenticated `GET /api/memory/semantic/status` | 200 response with `state: disabled`, provider/model null; no setup or retrieval was fabricated |
| Patch whitespace | `git diff --check` | Passed; Git emitted ordinary LF/CRLF conversion notices for some Windows working copies |

Dependency files and lockfiles have no changes. The full relevant suite was repeated after meaningful repairs; the report placement regression was corrected without weakening its catalog test. Test logs are in the current user's temporary directory (`erselmetz-audit-verified-python.txt`, `erselmetz-audit-node-verified.txt`); Chromium screenshots are emitted under the pytest temporary run directories, not added as application assets.

### Exact files changed

There are 25 modified tracked files and 2 new untracked files; nothing is staged.

```text
README.md
app/application/services/corporation.py
app/webui/router.py
app/webui/static/activity.mjs
app/webui/static/dashboard.mjs
app/webui/static/documentation.mjs
app/webui/static/employee-chat.mjs
app/webui/static/employees.mjs
app/webui/static/local-login.mjs
app/webui/static/memory.mjs
app/webui/static/positions.mjs
app/webui/static/projects.mjs
app/webui/static/providers.mjs
app/webui/static/scene-model.mjs
app/webui/static/style.css
app/webui/static/tasks.mjs
app/webui/static/three-scene.mjs
app/webui/static/updates.mjs
corporation_updates.json
docs/tasks-data.mjs
docs/test/site.test.mjs
tests/test_automation_traces.py
tests/test_dashboard_data.mjs
tests/test_local_login_ui.mjs
tests/test_visualization_ui.mjs
PRODUCT_AUDIT_2026-10-15.md
tests/test_product_audit.py
```

### git diff --stat

The standard Git diff below covers tracked modifications. It excludes the two new untracked files listed above (this report and the cross-page regression test).

```text
README.md                               | 28 ++++++++------
 app/application/services/corporation.py |  8 +++-
 app/webui/router.py                     | 66 +++++++++++++++++----------------
 app/webui/static/activity.mjs           |  2 +-
 app/webui/static/dashboard.mjs          | 20 +++++++++-
 app/webui/static/documentation.mjs      |  2 +-
 app/webui/static/employee-chat.mjs      |  2 +-
 app/webui/static/employees.mjs          |  2 +-
 app/webui/static/local-login.mjs        | 19 +++++++++-
 app/webui/static/memory.mjs             |  2 +-
 app/webui/static/positions.mjs          |  2 +-
 app/webui/static/projects.mjs           |  2 +-
 app/webui/static/providers.mjs          |  2 +-
 app/webui/static/scene-model.mjs        |  4 +-
 app/webui/static/style.css              |  6 ++-
 app/webui/static/tasks.mjs              |  2 +-
 app/webui/static/three-scene.mjs        | 22 ++++++++++-
 app/webui/static/updates.mjs            |  2 +-
 corporation_updates.json                |  2 +-
 docs/tasks-data.mjs                     |  2 +-
 docs/test/site.test.mjs                 |  2 +-
 tests/test_automation_traces.py         |  2 +-
 tests/test_dashboard_data.mjs           | 23 +++++++++++-
 tests/test_local_login_ui.mjs           | 22 +++++++++--
 tests/test_visualization_ui.mjs         | 23 ++++++++++++
 25 files changed, 200 insertions(+), 69 deletions(-)
```

### Final git status

```text
## main...origin/main
 M README.md
 M app/application/services/corporation.py
 M app/webui/router.py
 M app/webui/static/activity.mjs
 M app/webui/static/dashboard.mjs
 M app/webui/static/documentation.mjs
 M app/webui/static/employee-chat.mjs
 M app/webui/static/employees.mjs
 M app/webui/static/local-login.mjs
 M app/webui/static/memory.mjs
 M app/webui/static/positions.mjs
 M app/webui/static/projects.mjs
 M app/webui/static/providers.mjs
 M app/webui/static/scene-model.mjs
 M app/webui/static/style.css
 M app/webui/static/tasks.mjs
 M app/webui/static/three-scene.mjs
 M app/webui/static/updates.mjs
 M corporation_updates.json
 M docs/tasks-data.mjs
 M docs/test/site.test.mjs
 M tests/test_automation_traces.py
 M tests/test_dashboard_data.mjs
 M tests/test_local_login_ui.mjs
 M tests/test_visualization_ui.mjs
?? PRODUCT_AUDIT_2026-10-15.md
?? tests/test_product_audit.py
```

HEAD remains `eba16ce78af9f7337e6b586b288e6944ffc47705`; the branch still tracks `origin/main` without a new commit. No commit, push, merge, release, dependency installation, or user-data migration was performed. The tree is intentionally dirty with the reviewed audit changes.

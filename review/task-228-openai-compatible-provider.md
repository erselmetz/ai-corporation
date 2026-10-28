# Task 228 — OpenAI-compatible text endpoints and optional Free pool

Local source work, 28 October 2026. Base commit:
`4c240fdefe93c25b020976c646d7a7f3f12ce523`. Intended checkpoint:
`task-228-openai-compatible-provider`. No push, deployment, router installation,
downloaded installer, paid generation call or new packaged release is authorized
or claimed. The existing Task 227 EXE does not acquire this source feature without
a new build.

## Audit and reused boundaries

The first audit and reuse decisions are in `task-228-provider-audit.md`: reuse
AIProvider, provider connections/assignment checks, owner permissions and CSRF,
owned conversations/workspaces, ResourceManager, Brain/project preview digests,
local tool validation and the existing How I answered trace store. Gemini-specific
URLs/key rules are separate. There is no general text invoice cap to reuse;
voice/workflow ceilings retain their existing meaning and are not bypassed.

## Resulting owner journey

Provider connections offers OpenAI-compatible endpoint and Free pool types.
The preset defaults to `http://127.0.0.1:3001/v1`, requested model `auto`, and an
experimental label. Add validates and registers configuration **without a network
call**, with cloud turns and Brain context off by default. Credentials stay in
memory, never appear in connection responses, and are released/disabled on removal.
Python does not promise physical RAM zeroing of immutable strings.

The three-step guide links the official separate release and explains verification,
router setup, terms/billing limits and an explicit Test. Test requires management
permission, CSRF and explicit consent for fixed text `Hi` with `max_tokens: 1`.
It lists models, then makes that one test generation if models exist. Generic
endpoints can test an owner-selected model; there is no automatic alternate-model
retry. Test reserves both the connection gate and the shared ResourceManager
allocation. Exhausted global capacity or emergency Stop admits no generation and
spends no generation allowance. States distinguish Not tested, Not reachable,
Reachable, Key rejected and No models; reachable is not a quality or SLA claim.

Native “Ask the free pool?” prepares a read-only exact outbound preview against
one explicitly enabled/tested compatible destination. Multiple enabled targets
require resolving that choice in Settings; none is silently selected. The current
tab's draft or last local question is used; another tab's question is not reused.
The private preview shows all actual message text in a read-only scrollable view,
the exact destination, requested model and the warning:

> Your prompt may be sent to any provider enabled in that router.

Cancel performs no cloud generation. Approve authorizes only that digest/model/
connection incarnation, revalidating the owner/workspace/window generation and
selected Brain/project context. Stop, generation changes and changed prompts
invalidate the approval. The native local model and workspace selection remain
unchanged. The web Coordinator supports the same preview negotiation and explicit
one-turn route selection; it never preselects or executes a suggested cloud route.

## Data, tools and accounting

The adapter is cloud-classified regardless of URL. Only literal loopback or the
reserved localhost name is accepted without remote confirmation; non-loopback
requires explicit confirmation **and HTTPS**. URL credentials, query/fragment
data, ambiguous separators and redirects are rejected. httpx ignores environment
proxy settings and verifies TLS normally. Keys travel only in the configured
endpoint's Authorization header, not in a model prompt or API status response.

The provider's Brain switch defaults off; selecting Brain still requires its
existing authorized scope and digest plus the final outbound approval. Image,
screen/camera frame and audio inputs are unsupported. There is no embeddings
method or Brain embedding provider change. Selected reference/file/history/project
text must appear in the exact preview before transfer. The outbound redactor
handles the configured key, common API/Bearer/JWT/provider tokens, named secret
fields and private-key blocks, including split streamed output. It is a bounded
heuristic, not detection of every possible private fact. Local existing history/
notes are not erased by outbound sanitization.

Prompts are capped at 32 KB, replies request at most 1,024 tokens, response envelopes
at 512 KB and displayed answer text at 8 KB. A connection gets five generation
attempts per process, including Tests and failed attempts. There are **zero
automatic app retries or cloud/local fallbacks**. Those are software allowances,
not a monetary ceiling or certification of upstream free tiers. The external
router's internal retries, billing and enabled providers remain outside this app's
control. Stop can terminate app work; it cannot undo an already-sent remote request.

HTTP SSE is parsed incrementally with byte/time bounds, but answer text is buffered
until completion so split secrets and late tool proposals cannot escape early.
Sanitized chunks are then exposed through sync/async interfaces. This is not
unbuffered token-by-token display. Tool/function-call proposals are rejected and
execute nothing. No cloud Native Agent loop, Employee/workflow generation or new
tool authority is introduced; paths without the additional preview fail closed.
Existing owner-reviewed local tools retain their separate validation and approval.

## Provenance

How I answered distinguishes the requested model/alias from router-reported
`X-Routed-Via: platform/model`. It records that header's sanitized provider/model,
HTTP elapsed time and app retries (zero). Missing or unsafe headers produce unknown
served identity. Router-internal retries remain unknown. A header is attributed to
the router, not independent proof that a named upstream actually performed inference.
Adapter telemetry adds no connection credential or outbound preview. Existing
protected local content/history traces remain separate; outbound sanitization does
not erase the owner's original local data.

## Verification record

The full canonical suite passed **2,051 tests, 3 skipped, 4 warnings in 634.48 s**.
The final affected provider/Qt/actual-browser/startup/browser-contract/docs run
passed **381 tests, 1 warning in 68.98 s**, including the last one-token probe
regression and UI wording/layout corrections. These overlapping counts must not
be added together. Exact commands, chronology, environment and skip reasons are
recorded in `task-228-evidence.json`. All new upstream tests use an explicitly fake local HTTP
server or httpx transport; no result is labelled a live FreeLLMAPI measurement.

Checks cover disabled-by-default/no Add contact, URL validation, catalog/no-model
states, bad key, rate limiting, server failure, timeout, no redirects, call limits,
secret/private-key redaction, split streamed secrets, tool proposals, sync/async,
header identity/unknown handling, owner permission and CSRF, read-only previews,
stale approval, native-style workspace isolation and global resource/Stop gates.
Qt exercises actual preview/Cancel/Approve buttons, stale generations, friendly
errors and descriptor exclusion. The real Chromium journey signs in, adds the
preset, tests its fixed one-token payload, enables it, explicitly selects a cloud
route, approves the preview, inspects provenance and verifies the local assignment
is unchanged. Screenshots are local QA artifacts; no real cloud key appears in them.

Two full-suite infrastructure findings were repaired rather than skipped:

- Root discovery was collecting preserved historical test copies in ignored QA
  output folders. `pytest.ini` points discovery at the canonical `tests/` tree;
  no canonical tests were excluded or removed, and the backups were preserved.
- A full run exposed a transient Windows sharing lock on Chromium's freshly created
  DevToolsActivePort file. The shared readiness helper retries locked/incomplete
  startup data only within the original caller deadline, fails closed on timeout/
  process exit, and changes no ACL, network rule, target guard or browser profile.
  Unit regressions reproduce the lock/partial write and deadline; the actual
  scoped-browser network tripwire remains required.

The deliberate HTTP 409 used for read-only preview negotiation is explicitly
expected in the real-browser test; all other browser errors still fail it.
Earlier failed command/fixture/collection/full-run logs remain under
`task228-review/`, including the actual startup-race failure. No essential failure
was converted into a skip or an increased network/startup deadline.

## Readiness and remaining limits

| Capability | Evidence level |
| --- | --- |
| Provider, consent/data/trace/limits and owner API contracts | Source-verified with deterministic fakes; final check counts in evidence JSON |
| Native/Advanced UI journeys with fake upstream | AI-verified source UI; no real upstream quality claim |
| Existing local Brain embeddings and local-only Agent tools | Existing boundaries preserved; compatible endpoint has neither capability |
| Real FreeLLMAPI/router/upstream | **UNVERIFIED**: no TCP listener at `127.0.0.1:3001` during the probe; no install or credentialed real generation attempted |
| Signed installer/new packaged endpoint integration | **UNVERIFIED**, not built or published in this task |
| Upstream pricing, data retention, terms, reliability and answer quality | **UNVERIFIED**; optional experimental personal-use integration, no SLA |

Public setup/verification/limit guide: `docs/free-pool.html`, linked from the static
integrations page. It cites the official project/release pages; no live-site change
is claimed. Application licensing and third-party distribution choices are unchanged.

# Task 225 — shipped guidance, exact replies/math and Nomic prefixes

2026-10-25. Local only, parent `a6ac9b0` / `task-224-qt-brain`.
No push, deployment, premature Node retirement or paid provider call.

The native shell enables a bounded shipped `knowledge_pack.json`. Its persona
and rules enter the system message; the three retrieved entries enter a clearly
untrusted general-guidance block. Private user Brain rows stay in their existing
owner store. Derived shipped vectors use a separate
`shipped-pack-cache/<pack-sha256>/embeddings.sqlite3`, additionally keyed by
embedding identity and task-prefixed text. Removing this cache rebuilds it;
updating the shipped pack selects a different hash directory on next launch.
Nothing imports or overwrites user Brain content.
The pack contains eleven real guidance/school/coding entries. Its actual entries
form the inner Core cluster; private notes remain in the outer source clusters.
Core cards are read-only and never expose Forget. Only the three entries actually
retrieved for a model response light up, using response metadata rather than
guessed activity. No placeholder dots fill an empty private Brain. Semantic failure has an
explicit lexical mode; no model is downloaded or sent cloud data.

Exact-match greetings, thanks and identity replies avoid both provider calls and
model-slot reservations. Matching tolerates case, outer whitespace and terminal
punctuation, but never interprets an additional instruction as a greeting.
The response still passes through authentication, CSRF, owner/workspace lookup,
assignment consistency, the conversation lock, open state, message limits and
the existing history writer. Both message and streaming endpoints record truthful
`provider_called: false` provenance. Raw history keeps the owner's original text.
Other clients retain their previous behavior unless they enable the shipped pack.

The sidebar's **Exact math** opens a review dialog. The owner selects the operation
and exact inputs, then chooses Run locally. Requests pass through the existing
reviewed-tool endpoint, chat-only policy and Agent tool allowlist. Exact-only
turns cannot combine with private retrieval, media, delegation or alternate
routes. The server records the confirmed result directly in owned history and
records the actual tool trace without a model call. Failure is a failure message,
not a fabricated result. Ordinary reviewed-tool chat remains supported.

Arithmetic uses a fixed Python AST interpreter and rational numbers. Decimal
source spelling remains exact; terminating results print as exact decimals and
recurring results as fractions. No `eval`, `exec`, symbolic string parser,
imports, attributes, arbitrary names or function calls are accepted. Input is
bounded to 256 characters/40 AST nodes, precision and decimal exponent to 48,
intermediate magnitude to 10^12, rational sizes to 160 bits, and integer powers
to -12…12. These are deliberate supported limits, not general Python execution.

Equation solving supports **one variable x, real linear/quadratic polynomials**,
division by nonzero constants and exact rational or radical answers. Complex
roots, higher degrees and transcendental functions are explicitly unsupported.
Conversion uses an enumerated rational SI table for length, time, mass, speed
and affine temperatures; incompatible dimensions and below-absolute-zero
temperatures fail. Arbitrary unit expressions are unsupported. These limits
are visible rather than delegated to a model or an unsafe expression parser.

## Actual local evidence

`tools/qt_pack_check.py` ran the visible Qt shell with isolated data, installed
`qwen3.5:4b` and `nomic-embed-text:latest`; it stops if Ollama is unavailable and
downloads nothing. The actual review dialogs produced **0.3**, **x = 2, 3** and
**100 cm** through authenticated APIs, all with no-provider traces. A real Qwen
response followed a normal coding question with shipped guidance.

End-to-end source timing was **3,926.62 ms** for the first greeting (including
new workspace/conversation), **1,482.95 / 1,551.60 / 1,539.08 ms** for the three
math reviews (including the 150-ms scripted review pause), and **26,829.48 ms**
for the model-backed coding response. Avoiding inference does not establish
instant perceived latency; that remains a performance limitation. No packaged
timing or general speed claim follows from these numbers.

`tools/native_prefix_check.py` reused Task 224's exact five real file hashes plus
the two folder files frozen from `f074a8a`, **36 chunks**, ten identical questions,
one installed Nomic digest and top-five scoring. Both branches used actual
semantic embeddings, never lexical fallback. The isolated profile is discarded
after restoring its previous working directory; initial Windows cleanup failed
while the process was still inside that directory, and the script was repaired.

| Prefix mode | Thresholds 0 / .25 / .35 / .45 | .55 | .65 |
| --- | --- | --- | --- |
| None | Recall@5 .80; MRR .75 | .70 / .70 | .50 / .50 |
| `search_document:` / `search_query:` | Recall@5 .70; MRR .70 | .70 / .70 | .60 / .60 |

Prefixes are enabled as requested. The conservative existing **.35 threshold**
is retained: raising it did not improve the measured expected-source recall.
This is a **regression on this small corpus**, not an improvement or a held-out
quality evaluation. No answer/citation score is inferred from retrieval ranks.
End-to-end native private-Brain answer/citation verification belongs with the
226 context/agent loop and final 227 verification. Cache keys distinguish
prefixed and old unprefixed documents; changing the prefix cannot reuse old
vectors silently.

Exact model digests, hashes, ranked scores, timings and tool traces:
[evidence](task-225-knowledge-evidence.json). Screenshots:
[shell](task-225-qt-assets/shell-pack-math.png),
[calculate](task-225-qt-assets/math-review-0.png),
[solve](task-225-qt-assets/math-review-1.png),
[convert](task-225-qt-assets/math-review-2.png),
[read-only Core card](task-225-qt-assets/core-read-only-card.png).

## Verification and remaining scope

Focused existing/new chat, workspace, history, prompt and math/pack checks:
**104 passed**, 35.68 seconds; final Core/prompt/chat checks **61 passed**,
35.19 seconds. Browser modules **295 passed**; Electron source **44 passed**.
The initial full gate passed **1,539 / 3 skipped**, 337.89 seconds. After Core
highlight wiring, a full run had one legacy bridge assertion expecting the old
completion event (1,540 passed / 3 skipped). The bridge contract now explicitly
verifies the three returned Core IDs and uses fake embeddings as well as fake
chat, removing accidental live model access from that deterministic test. Final
bridge/Core gate: **22 passed**, 19.91 seconds. Final full Python: **1,541 passed,
3 skipped, 0 failed**, 323.44 seconds; four existing dependency/Qt deprecation
warnings. Public docs: **23 passed**; documentation integrity and diff checks
passed. The three Windows symlink privilege skips remain Unverified. No coverage is retired here.
New checks cover cache rebuild/prefix separation, no-provider owned history and
traces, closed conversations, CSRF, global stop, invalid action combinations,
streamed instant replies and all three actual Qt math review mappings.

Source behavior and visible local model/math journeys are verified. Packaged
resource inclusion, final screenshot baselines/control sweep, safe restore and
Node retirement remain **227**. ResourceManager coordination for embeddings and
chat, native private-Brain context, hardened action tools, model reload warnings,
device ownership, cancellation/stops and rename/delete remain **226**. Shipped
cache identity currently names the embedding model; rebuilding is required if
that same installed model tag is replaced with different weights.

Local checkpoint: `task-225-knowledge-pack`. No push or deployment.

# Task 228 provider framework audit

Base: `4c240fdefe93c25b020976c646d7a7f3f12ce523`, clean main at start,
28 October 2026. User authorizes one local commit/tag, no push/deploy, no router
installation or bundling. Canonical task data is JSON; generate its browser module.

| Existing boundary | Reuse and gap |
| --- | --- |
| `providers/base.py`, registry | Reuse AIProvider text/chat/stream contract and cloud flags. Existing generic ProviderManagement factory creates Ollama, not a general online endpoint. |
| Gemini adapter/connection manager | Reuse bounded httpx conventions, operator-safe errors, opt-in credentials, one-request gate, explicit cloud classification and no retries. Do not reuse Google's key format, fixed URL or model catalog for other endpoints. |
| Provider connections service/API/page | Reuse authenticated owner management, CSRF, immutable Agent assignment checks, in-memory credentials, bounded catalog freshness and request slots. Add an explicit compatible connection type and disabled preset; no startup contact. |
| Owned chat and workspaces | Reuse owner/window/generation access, history lifecycle, immutable assignments, ResourceManager and stop controls. Existing prompt observer runs before any message insertion/provider call, permitting a read-only exact preview. Native escalation must explicitly permit one reviewed cloud route over a local workspace without altering its saved selection. |
| Consent/context | Existing APIs gate cloud and images, revalidate knowledge digests and project briefs, and restrict Brain scopes/Agent tools. Some labels and alternate-route checks are Gemini-specific. Add a second digest-bound outbound approval, redaction and default-off per-provider Brain gate; do not infer consent from loopback or retrieval. |
| Spend/limits | Gemini text has a five-call allowance; voice has a cents budget; workflows have their own ceilings. There is no generic text-provider invoice cap to reuse. Preserve those gates and use explicit bounded calls/tokens, no retries, and unknown-cost wording. External router billing and internal retries cannot be certified. |
| Secret storage | Reuse in-memory connection credentials and secret-free response/error conventions. Existing owner DPAPI setup is Gemini-specific; no new key persistence is implied. Do not log request headers, keys or outbound previews. |
| Trace/How I answered | Reuse chat_knowledge turn traces and both web/native display paths. Configured model is not actual serving identity behind a router; retain requested model separately and report header attribution or unknown, elapsed time and zero app retries. |
| Smart routing | Existing local-first complexity hints and explicit alternate route consent never execute suggestions. Add optional endpoint candidates and an explicit native action; no failed-local auto-resend. |
| Tools | Native bounded Agent loop is verified-local-Ollama-only. Gemini's text adapter has no executable tool path. Reject compatible tool proposals instead of adding a cloud loop or bypassing tool/profile/approval validation. Existing reviewed local tools remain separate. |
| Brain embeddings | `knowledge/native_brain.py` and the separate internal local-embedding resource bucket remain unchanged. Compatible endpoints have no embedding or media method. |

Official external source checked: [project](https://github.com/tashfeenahmed/freellmapi)
and [releases](https://github.com/tashfeenahmed/freellmapi/releases). These support
separate installation and personal-experimentation guidance; no advertised model
count, token allowance, perpetual availability or upstream SLA is promised here.
No asset or install script was downloaded or executed.

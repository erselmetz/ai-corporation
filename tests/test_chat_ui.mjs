import assert from "node:assert/strict";
import test from "node:test";
import { mountChat, voiceTranscriptSourceLabel } from "../app/webui/static/chat.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.children = []; this.value = ""; this.text = ""; this.listeners = {}; this.disabled = false; this.hidden = false; }
  get textContent() { return this.text + this.children.map(item => item.textContent).join(""); }
  set textContent(value) { this.text = value; this.children = []; }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(...items) { this.children.push(...items); if (this.tag === "select" && this.children.length === 1) this.value = items[0].value; }
  replaceChildren() { this.children = []; this.text = ""; if (this.tag === "select") this.value = ""; }
  addEventListener(event, handler) { this.listeners[event] = handler; }
}
const agent = { id: "worker", name: "Actual Worker", role: "Worker", provider: "fake", model: "configured-model" };
const snapshot = (messages = [], status = "open", coordinator = agent) => ({ coordinator, conversation: { id: "conversation", status, messages } });
const message = (role, status, content) => ({ id: role, role, status, content });
const response = (payload, status = 200) => ({ ok: status === 200, status, json: async () => payload });
const streamEvent = event => `${JSON.stringify(event)}\n`;
function streamResponse(events) {
  const bytes = new TextEncoder().encode(events.map(streamEvent).join(""));
  return {
    ok: true,
    status: 200,
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(bytes);
        controller.close();
      },
    }),
  };
}
const completedStreamEvent = {
  type: "complete",
  streaming_supported: true,
  coordinator: agent,
  conversation: {
    id: "conversation",
    status: "open",
    messages: [
      message("user", "completed", "Hello"),
      message("assistant", "completed", "first reply"),
    ],
  },
};
function setup(handler = null, windowRef = globalThis.window) {
  const ids = [
    "chat-state", "chat-history", "chat-agent", "chat-conversation", "chat-input", "chat-input-provenance",
    "chat-start", "chat-send", "chat-close", "chat-refresh", "chat-identity",
    "chat-form", "cloud-consent-panel", "cloud-consent", "chat-task-source",
    "chat-task-agent", "chat-task-prepare", "chat-task-confirm", "chat-task-review",
    "chat-task-state", "chat-task-objective", "chat-task-project",
    "chat-task-context-query", "chat-task-context-scope", "chat-task-context-id",
    "chat-task-outcome", "chat-task-verification", "chat-task-evidence",
    "chat-stop-display", "repository-study-form", "repository-study-objective",
    "chat-knowledge-enabled", "chat-knowledge-scopes", "chat-knowledge-owner",
    "chat-knowledge-conversation", "chat-knowledge-extra-enabled", "chat-knowledge-extra-scope",
    "chat-knowledge-extra-id", "chat-knowledge-preview", "chat-knowledge-state",
    "chat-knowledge-preview-result", "chat-capture-local-prompt",
    "repository-study-owner", "repository-study-name", "repository-study-submit",
    "repository-study-state", "repository-study-result",
    "chat-stop-request", "voice-mode", "voice-language", "voice-start", "voice-stop",
    "response-preferences-label",
    "voice-transcribe", "voice-install-local", "voice-cloud-consent", "voice-budget-form",
    "voice-budget-cents", "voice-budget-save", "voice-budget-state", "voice-state",
    "voice-stop-playback",
  ];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(
    ["chat-agent", "chat-conversation", "chat-task-source", "chat-task-agent",
      "chat-task-context-scope", "chat-knowledge-extra-scope"].includes(id) ? "select" : "",
  )]));
  elements["chat-history"].dataset = {};
  for (const id of ["chat-knowledge-enabled", "chat-knowledge-owner", "chat-knowledge-conversation", "chat-knowledge-extra-enabled"]) elements[id].checked = false;
  const calls = [];
  elements["voice-mode"].value = "local";
  elements["voice-language"].value = "en-US";
  elements["voice-budget-cents"].value = "5";
  const fetchImpl = async (path, options) => {
    calls.push({ path, options });
    const custom = handler && await handler(path, options);
    if (custom) return custom;
    if (path === "/api/agents") return response({ items: [agent] });
    if (path === "/api/local/session") return response({
      csrf: "test-csrf",
      permissions: ["chat-task:create", "github:read"],
    });
    if (path === "/api/local/preferences") return response({ preferences: {
      response_mode: "balanced", locale: "en-US", detail_level: "standard",
      voice_mode: "off", voice_language: "en-US", voice_id: "",
    }, retention: "Local presentation choices only." });
    if (path === "/api/local/voice") return response({
      cloud_budget: { configured: false, ceiling_cents: null, reserved_cents: 0,
        remaining_cents: null, reservation_per_request_cents: 1, reset: "app_restart" },
    });
    if (path === "/api/chat/conversations" && !options.method) return response({ items: [] });
    if (path.endsWith("/close")) return response(snapshot([], "closed"));
    return response(snapshot());
  };
  const documentRef = { getElementById: id => elements[id], documentElement: {}, createElement: tag => new Element(tag) };
  const controller = mountChat({ documentRef, fetchImpl, confirmImpl: () => true, windowRef });
  return { controller, elements, calls };
}

test("local transcript is added after an unsent typed draft and never submits the chat", async () => {
  let recognition;
  class Recognition {
    static async available() { return "available"; }
    static async install() { return true; }
    processLocally = false;
    start() {}
    abort() { this.onend?.(); }
    constructor() { recognition = this; }
  }
  const ui = setup(null, { SpeechRecognition: Recognition });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "typed context";
  await ui.elements["voice-start"].listeners.click();
  recognition.onresult({ results: [[{ transcript: "spoken addition" }]] });
  assert.equal(ui.elements["chat-input"].value, "typed context\nspoken addition");
  assert.equal(ui.elements["chat-input-provenance"].hidden, false);
  assert.match(ui.elements["chat-input-provenance"].textContent, /Browser on-device speech recognition \(local\)/);
  assert.match(ui.elements["chat-input-provenance"].textContent, /source applies only to the inserted transcript/);
  assert.equal(ui.calls.some(call => call.path.endsWith("/messages") || call.path.endsWith("/messages/stream")), false);
});

test("speech source labels distinguish local, local-model, and consented online transcripts", () => {
  assert.match(voiceTranscriptSourceLabel("local"), /Browser on-device.*local/);
  assert.match(voiceTranscriptSourceLabel("local-model"), /Selected local speech model/);
  assert.match(voiceTranscriptSourceLabel("gemini"), /online, explicitly consented/);
  assert.match(voiceTranscriptSourceLabel("unexpected"), /Unverified/);
});

test("start and send use same-origin, session CSRF and actual coordinator identity; text stays inert", async () => {
  const untrusted = "<script>alert('x')</script>";
  const ui = setup((path) => path.endsWith("/messages") ? response(snapshot([
    message("user", "completed", "Hello"), message("assistant", "completed", untrusted)])) : null);
  assert.equal(await ui.controller.initialLoad, true);
  assert.equal(await ui.controller.start(), true);
  assert.match(ui.elements["chat-identity"].textContent, /Coordinator: Actual Worker.*fake.*configured-model/);
  ui.elements["chat-input"].value = "Hello";
  assert.equal(await ui.controller.send({ preventDefault() {} }), true);
  assert.ok(ui.elements["chat-history"].textContent.includes(untrusted));
  assert.equal(ui.elements["chat-input"].value, "");
  assert.equal(ui.elements["chat-input-provenance"].hidden, true);
  const post = ui.calls.find(call => call.path.endsWith("/messages"));
  assert.equal(post.options.credentials, "same-origin");
  assert.equal(post.options.headers["X-Local-CSRF"], "test-csrf");
  assert.deepEqual(JSON.parse(post.options.body), { text: "Hello" });
});

test("streaming chat renders provider chunks and verifies the completed response", async () => {
  const ui = setup((path, options) => {
    if (path === "/api/chat/conversations" && options.method === "POST") {
      return response({ ...snapshot(), streaming_supported: true });
    }
    if (path.endsWith("/messages/stream")) {
      return streamResponse([
        { type: "chunk", text: "first " },
        { type: "chunk", text: "reply" },
        completedStreamEvent,
      ]);
    }
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  assert.equal(ui.elements["chat-stop-display"].hidden, true);
  ui.elements["chat-input"].value = "Hello";
  assert.equal(await ui.controller.send(), true);
  const post = ui.calls.find(call => call.path.endsWith("/messages/stream"));
  assert.equal(post.options.credentials, "same-origin");
  assert.equal(post.options.headers["X-Local-CSRF"], "test-csrf");
  assert.deepEqual(JSON.parse(post.options.body), { text: "Hello" });
  assert.match(ui.elements["chat-history"].textContent, /assistant - completedfirst reply/);
  assert.match(ui.elements["chat-state"].textContent, /Stream completed/);
  assert.equal(ui.elements["chat-stop-display"].hidden, true);
});

test("knowledge requires an exact preview and displays returned citations in How I answered", async () => {
  const trace = {
    route: { agent_id: "worker", agent: "Actual Worker", provider: "ollama", model: "local-model", source: "owner selected" },
    retrieval: { enabled: true, mode: "lexical-only", query: "Which port?", returned_chunks: [{ source: "private.md" }] },
    sources: [{ source: "private.md", scope: "owner", chunk_reference: "note-1#1", score: 0.5 }],
    truncation: {}, cloud: { provider_used: null, consent_given: false, private_knowledge_sent: false },
    timing: { turn_elapsed_ms: 3 }, outcome: "completed", actions: { tools_run: false, tasks_created: false },
  };
  const preview = { digest: "a".repeat(64), trace: { context_bytes: 12 }, items: [{
    source: "private.md", scope: "owner", chunk_reference: "note-1#1", content: "Port 8123",
  }] };
  const ui = setup((path, options) => {
    if (path.endsWith("/knowledge-preview")) return response(preview);
    if (path.endsWith("/messages")) return response({
      ...snapshot([message("user", "completed", "Which port?"), message("assistant", "completed", "8123")]),
      context_trace: trace,
    });
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Which port?";
  ui.elements["chat-knowledge-enabled"].checked = true;
  ui.elements["chat-knowledge-enabled"].listeners.change();
  ui.elements["chat-knowledge-owner"].checked = true;
  ui.elements["chat-knowledge-owner"].listeners.change();
  assert.equal(await ui.controller.send(), false);
  assert.match(ui.elements["chat-state"].textContent, /Preview the exact selected knowledge/);
  await ui.elements["chat-knowledge-preview"].listeners.click();
  assert.match(ui.elements["chat-knowledge-preview-result"].textContent, /Port 8123/);
  assert.equal(await ui.controller.send(), true);
  const body = JSON.parse(ui.calls.find(call => call.path.endsWith("/messages")).options.body);
  assert.equal(body.knowledge_enabled, true);
  assert.equal(body.knowledge_preview_digest, "a".repeat(64));
  assert.match(ui.elements["chat-history"].textContent, /How I answered/);
  assert.match(ui.elements["chat-history"].textContent, /private.md.*note-1#1/);
});

test("Stop display hides chunks but continues consuming the provider response", async () => {
  let finishStream;
  let cancelled = false;
  const ui = setup((path, options) => {
    if (path === "/api/chat/conversations" && options.method === "POST") {
      return response({ ...snapshot(), streaming_supported: true });
    }
    if (path.endsWith("/messages/stream")) {
      return {
        ok: true,
        status: 200,
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(streamEvent({ type: "chunk", text: "partial " })));
            finishStream = () => {
              controller.enqueue(new TextEncoder().encode(streamEvent({ ...completedStreamEvent })));
              controller.close();
            };
          },
          cancel() { cancelled = true; },
        }),
      };
    }
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Hello";
  const pending = ui.controller.send();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.elements["chat-stop-display"].hidden, false);
  ui.elements["chat-stop-display"].listeners.click();
  finishStream();
  assert.equal(await pending, true);
  assert.equal(cancelled, false);
  assert.match(ui.elements["chat-history"].textContent, /assistant - completedfirst reply/);
  assert.match(ui.elements["chat-state"].textContent, /generation continued and completed/);
});

test("repository study sends explicit scope with CSRF and renders untrusted report as text", async () => {
  const report = {
    decision: "proposal_for_human_review",
    repository: { revision_sha: "a".repeat(40) },
    proposal: { requested_purpose: "<script>untrusted</script>" },
  };
  const ui = setup(path => (
    path.endsWith("/repository-studies") ? response(report) : null
  ));
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["repository-study-objective"].value = "Assess local integration";
  ui.elements["repository-study-owner"].value = "example";
  ui.elements["repository-study-name"].value = "project";
  assert.equal(
    await ui.elements["repository-study-form"].listeners.submit({ preventDefault() {} }),
    true,
  );
  const post = ui.calls.find(call => call.path.endsWith("/repository-studies"));
  assert.equal(post.options.credentials, "same-origin");
  assert.equal(post.options.headers["X-Local-CSRF"], "test-csrf");
  assert.deepEqual(JSON.parse(post.options.body), {
    objective: "Assess local integration",
    owner: "example",
    repository: "project",
  });
  assert.match(ui.elements["repository-study-result"].textContent, /<script>untrusted<\/script>/);
  assert.match(ui.elements["repository-study-state"].textContent, /human review/);
});

test("repository study is unavailable without the separate GitHub read permission", async () => {
  const ui = setup(path => (
    path === "/api/local/session"
      ? response({ csrf: "test-csrf", permissions: [] })
      : null
  ));
  await ui.controller.initialLoad;
  await ui.controller.start();
  assert.equal(ui.elements["repository-study-submit"].disabled, true);
  ui.elements["repository-study-objective"].value = "Assess";
  ui.elements["repository-study-owner"].value = "example";
  ui.elements["repository-study-name"].value = "project";
  assert.equal(
    await ui.elements["repository-study-form"].listeners.submit({ preventDefault() {} }),
    false,
  );
  assert.equal(ui.calls.some(call => call.path.endsWith("/repository-studies")), false);
});

test("Gemini requires per-turn cloud consent and sends only an explicit consent flag", async () => {
  const gemini = { ...agent, provider: "gemini", model: "gemini-test-flash" };
  const ui = setup((path, options) => {
    if (path === "/api/agents") return response({ items: [gemini] });
    if (path === "/api/chat/conversations" && options.method === "POST") return response(snapshot([], "open", gemini));
    if (path.endsWith("/messages")) return response(snapshot([message("assistant", "completed", "reply")], "open", gemini));
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  assert.equal(ui.elements["cloud-consent-panel"].hidden, false);
  ui.elements["chat-input"].value = "hello";
  assert.equal(await ui.controller.send(), false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 0);
  ui.elements["cloud-consent"].checked = true;
  assert.equal(await ui.controller.send(), true);
  const post = ui.calls.find(call => call.path.endsWith("/messages"));
  assert.deepEqual(JSON.parse(post.options.body), { text: "hello", cloud_consent: true });
  assert.equal(ui.elements["cloud-consent"].checked, false);
  assert.equal(ui.elements["cloud-consent-panel"].hidden, false);
});

test("pending send prevents duplicate turns and selection changes; provider failure is inspected without replay", async () => {
  let finish;
  const ui = setup((path) => {
    if (path.endsWith("/messages")) return new Promise(resolve => { finish = resolve; });
    if (path.endsWith("/conversation")) return response(snapshot([message("user", "failed", "Hello")]));
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Hello";
  const pending = ui.controller.send();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(ui.elements["chat-state"].textContent, /Pending/);
  assert.equal(ui.elements["chat-input"].disabled, true);
  assert.equal(ui.elements["chat-conversation"].disabled, true);
  assert.equal(await ui.controller.send(), false);
  assert.equal(await ui.controller.refresh(), false);
  finish(response({ detail: "raw failure" }, 502));
  assert.equal(await pending, false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 1);
  assert.match(ui.elements["chat-history"].textContent, /user - failed/);
  assert.match(ui.elements["chat-state"].textContent, /No automatic retry/);
  assert.equal(ui.elements["chat-input"].value, "Hello");
  assert.equal(ui.elements["chat-input"].disabled, false);
});

test("blank and UTF-8 oversized messages never submit", async () => {
  const ui = setup();
  await ui.controller.initialLoad;
  await ui.controller.start();
  for (const value of [" ", "界".repeat(3000)]) {
    ui.elements["chat-input"].value = value;
    assert.equal(await ui.controller.send(), false);
  }
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 0);
});

test("recognized Gemini key paste is blocked with setup guidance before submission", async () => {
  const ui = setup();
  await ui.controller.initialLoad;
  await ui.controller.start();
  const key = `AIza${"A".repeat(35)}`;
  ui.elements["chat-input"].value = `GEMINI_API_KEY=${key}`;
  assert.equal(await ui.controller.send(), false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 0);
  assert.equal(ui.elements["chat-input"].value, "");
  assert.match(ui.elements["chat-state"].textContent, /not saved or sent.*Gemini online setup/);
});

test("authorization and empty data are distinct and failed refresh removes stale data", async () => {
  let denied = false;
  const ui = setup(path => path === "/api/agents" && denied ? response({}, 401) : null);
  await ui.controller.initialLoad;
  await ui.controller.start();
  denied = true;
  assert.equal(await ui.controller.refresh(), false);
  assert.match(ui.elements["chat-state"].textContent, /Sign in/);
  assert.equal(ui.elements["chat-history"].textContent, "");
  assert.equal(ui.elements["chat-agent"].children.length, 0);
  const empty = setup(path => path === "/api/agents" ? response({ items: [] }) : null);
  assert.equal(await empty.controller.initialLoad, true);
  assert.match(empty.elements["chat-state"].textContent, /No registered AI team member/);
});

test("existing owner conversation can be selected after refresh and closed explicitly", async () => {
  const ui = setup((path, options) => path === "/api/chat/conversations" && !options.method
    ? response({ items: [{ id: "conversation", coordinator: agent }] }) : null);
  await ui.controller.initialLoad;
  ui.elements["chat-conversation"].value = "conversation";
  assert.equal(await ui.controller.load(), true);
  assert.equal(await ui.controller.close(), true);
  assert.match(ui.elements["chat-state"].textContent, /closed/);
  assert.equal(ui.elements["chat-input"].disabled, true);
});

test("coordinator proposal is shown before an explicit pending-Task confirmation", async () => {
  const proposal = {
    proposal_id: "proposal-1",
    proposal_digest: "a".repeat(64),
    objective: "Reviewed objective",
    responsible_agent: { id: "worker", name: "Actual Worker" },
    authorized_context: null,
    outcome: { expected_outcome: "Expected result" },
    task: { title: "Reviewed objective", description: "Canonical task fields" },
  };
  const ui = setup((path, options) => {
    if (path.endsWith("/messages")) {
      return response(snapshot([message("assistant", "completed", "Coordinator proposal")]));
    }
    if (path.endsWith("/confirm")) {
      return response({ proposal_id: "proposal-1", task_id: "task-1", status: "pending" });
    }
    if (path.endsWith("/task-proposals")) return response(proposal);
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Please propose work";
  await ui.controller.send();
  ui.elements["chat-task-source"].value = "assistant";
  ui.elements["chat-task-objective"].value = "Reviewed objective";
  ui.elements["chat-task-agent"].value = "worker";
  ui.elements["chat-task-project"].value = "project-1";
  ui.elements["chat-task-outcome"].value = "Expected result";
  ui.elements["chat-task-verification"].value = "Owner checks result";
  ui.elements["chat-task-evidence"].value = "Review record";

  assert.equal(await ui.controller.prepareTaskProposal(), true);
  assert.match(ui.elements["chat-task-review"].textContent, /Canonical task fields/);
  assert.equal(ui.calls.some(call => call.path.endsWith("/task-proposals/confirm")), false);
  assert.equal(await ui.controller.confirmTaskProposal(), true);
  assert.match(ui.elements["chat-task-review"].textContent, /pending/);
  const confirmation = ui.calls.find(call => call.path.endsWith("/confirm"));
  assert.equal(confirmation.options.headers["X-Local-CSRF"], "test-csrf");
  assert.deepEqual(JSON.parse(confirmation.options.body), {
    proposal_digest: "a".repeat(64),
    confirmed: true,
  });
});

test("a failed send that discovers closure keeps input disabled and never replays", async () => {
  const ui = setup(path => {
    if (path.endsWith("/messages")) return response({}, 502);
    if (path.endsWith("/conversation")) return response(snapshot([], "closed"));
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Hello";
  assert.equal(await ui.controller.send(), false);
  assert.equal(ui.elements["chat-input"].disabled, true);
  assert.equal(await ui.controller.send(), false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 1);
});

test("stopping a model wait aborts local waiting but records an unknown remote outcome without replay", async () => {
  let messageCalls = 0;
  const ui = setup((path, options) => {
    if (!path.endsWith("/messages")) return null;
    messageCalls += 1;
    return new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
    });
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Hello";
  const send = ui.controller.send();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.elements["chat-stop-request"].hidden, false);
  ui.elements["chat-stop-request"].listeners.click();
  assert.equal(await send, true);
  assert.equal(messageCalls, 1);
  assert.equal(ui.elements["chat-input"].disabled, true);
  assert.match(ui.elements["chat-state"].textContent, /remote outcome is unknown.*No resend/);
});

test("exact assembled prompt is visible only after explicit local-model opt-in and is inert text", async () => {
  const exactPrompt = '{"request":"<script>private prompt</script>"}';
  const ui = setup((path, options) => {
    if (path === "/api/chat/conversations" && options.method === "POST") {
      return response({ ...snapshot(), local_model: true });
    }
    if (path.endsWith("/messages")) {
      return response({ ...snapshot([message("user", "completed", "hello"),
        message("assistant", "completed", "reply")]), local_model: true,
      advanced_prompt: exactPrompt });
    }
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  const consent = ui.elements["chat-capture-local-prompt"];
  assert.equal(consent.disabled, false);
  consent.checked = true;
  ui.elements["chat-input"].value = "hello";
  assert.equal(await ui.controller.send(), true);
  const post = ui.calls.find(call => call.path.endsWith("/messages"));
  assert.equal(JSON.parse(post.options.body).capture_local_prompt, true);
  assert.ok(ui.elements["chat-history"].textContent.includes(exactPrompt));
  assert.equal(ui.elements["chat-history"].children.some(item => item.innerHTML), false);
});

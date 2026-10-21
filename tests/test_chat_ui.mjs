import assert from "node:assert/strict";
import test from "node:test";
import { mountChat, voiceTranscriptSourceLabel } from "../app/webui/static/chat.mjs";

class Element {
  constructor(tag = "") { this.tag = tag; this.tagName = tag.toUpperCase(); this.children = []; this.value = ""; this.text = ""; this.listeners = {}; this.disabled = false; this.hidden = false; this.open = false; this.style = {}; this.attributes = {}; }
  get textContent() { return this.text + this.children.map(item => item.textContent).join(""); }
  set textContent(value) { this.text = value; this.children = []; }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(...items) { this.children.push(...items); if (this.tag === "select" && this.children.length === 1) this.value = items[0].value; }
  replaceChildren() { this.children = []; this.text = ""; if (this.tag === "select") this.value = ""; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  dispatchEvent() {}
  click() { this.listeners.click?.({ preventDefault() {}, target: this, currentTarget: this }); }
  requestSubmit() { this.listeners.submit?.({ preventDefault() {} }); }
  focus() { this.focused = true; }
  addEventListener(event, handler) {
    const existing = this.listeners[event];
    this.listeners[event] = existing
      ? (...args) => { existing(...args); handler(...args); }
      : handler;
  }
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
function setup(handler = null, windowRef = globalThis.window, confirmImpl = () => true) {
  const ids = [
    "chat-state", "chat-history", "chat-agent", "chat-conversation", "chat-input", "chat-input-provenance",
    "chat-delegate-once", "chat-approval-inbox", "chat-approval-count", "chat-approval-state",
    "chat-approval-items", "chat-approval-refresh",
    "chat-start", "chat-send", "chat-close", "chat-refresh", "chat-identity",
    "chat-route-check", "chat-route-select", "chat-route-state",
    "chat-form", "cloud-consent-panel", "cloud-consent", "chat-task-source",
    "chat-task-agent", "chat-task-prepare", "chat-task-confirm", "chat-task-review",
    "chat-task-state", "chat-task-objective", "chat-task-project",
    "chat-task-context-query", "chat-task-context-scope", "chat-task-context-id",
    "chat-task-outcome", "chat-task-verification", "chat-task-evidence",
    "chat-stop-display", "repository-study-form", "repository-study-objective",
    "chat-knowledge-enabled", "chat-knowledge-panel", "chat-knowledge-scopes", "chat-knowledge-owner",
    "chat-knowledge-conversation", "chat-knowledge-extra-enabled", "chat-knowledge-extra-scope",
    "chat-knowledge-extra-id", "chat-knowledge-preview", "chat-knowledge-state",
    "chat-knowledge-preview-result", "chat-capture-local-prompt",
    "chat-reviewed-tools", "chat-tool-calculator-enabled", "chat-tool-calculator-expression",
    "chat-tool-document-enabled", "chat-tool-document-id", "chat-tool-document-query", "chat-tools-state",
    "repository-study-owner", "repository-study-name", "repository-study-submit",
    "repository-study-state", "repository-study-result",
    "chat-stop-request", "voice-mode", "voice-language", "voice-start", "voice-stop",
    "chat-empty-state", "chat-conversation-list", "chat-earlier-list", "chat-earlier-label",
    "chat-search", "chat-nav-toggle", "chat-menu-button", "chat-sidebar", "chat-emergency-stop",
    "chat-add-image-action", "chat-camera-action", "chat-screen-action", "chat-knowledge-menu-toggle",
    "chat-image-file", "chat-capture-camera", "chat-capture-screen",
    "chat-mic", "chat-theme-toggle", "chat-settings", "chat-header-model",
    "response-preferences-label",
    "voice-transcribe", "voice-install-local", "voice-cloud-consent", "voice-budget-form",
    "voice-budget-cents", "voice-budget-save", "voice-budget-state", "voice-state",
    "voice-stop-playback",
  ];
  const elements = Object.fromEntries(ids.map(id => [id, new Element(
    ["chat-agent", "chat-conversation", "chat-task-source", "chat-task-agent",
      "chat-task-context-scope", "chat-knowledge-extra-scope", "chat-tool-document-id",
      "chat-route-select"].includes(id) ? "select" : "",
  )]));
  windowRef ||= {};
  const sessionValues = new Map();
  windowRef.sessionStorage ||= { setItem: (key, value) => sessionValues.set(key, value),
    getItem: key => sessionValues.get(key), removeItem: key => sessionValues.delete(key) };
  elements["chat-history"].dataset = {};
  elements["chat-emergency-stop"].hidden = true;
  for (const id of ["chat-knowledge-enabled", "chat-knowledge-owner", "chat-knowledge-conversation", "chat-knowledge-extra-enabled"]) elements[id].checked = false;
  const calls = [];
  const planConfirmations = [];
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
      permissions: ["chat-task:create", "github:read", "documentation:read", "chat-history:manage", "capability-approval:manage"],
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
    if (path === "/api/capabilities/approvals") return response({ items: [] });
    if (path.endsWith("/close")) return response(snapshot([], "closed"));
    return response(snapshot());
  };
  const bodyClasses = new Set();
  const documentListeners = new Map();
  const documentRef = { getElementById: id => elements[id], documentElement: {}, body: { classList: { toggle: (name, value = !bodyClasses.has(name)) => { if (value) bodyClasses.add(name); else bodyClasses.delete(name); return value; }, contains: name => bodyClasses.has(name), remove: name => bodyClasses.delete(name) } }, createElement: tag => new Element(tag), createTextNode: value => ({ textContent: String(value) }), querySelectorAll: () => [], addEventListener: (name, callback) => documentListeners.set(name, [...(documentListeners.get(name) || []), callback]) };
  for (const [id, item] of Object.entries(elements)) item.id = id;
  const controller = mountChat({ documentRef, fetchImpl, confirmImpl: message => {
    planConfirmations.push(message);
    return confirmImpl(message);
  }, windowRef });
  return { controller, elements, calls, planConfirmations, bodyClasses, documentListeners, documentRef, windowRef };
}

test("local transcript is added after an unsent typed draft and never submits the chat", async () => {
  let recognition;
  class Recognition {
    static async available() { return "available"; }
    static async install() { return true; }
    processLocally = false;
    start() { this.onstart?.(); }
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

test("composer sends on Enter, keeps Shift+Enter for a newline, and stays keyboard operable", () => {
  const ui = setup();
  let submissions = 0;
  ui.elements["chat-form"].requestSubmit = () => { submissions += 1; };
  let prevented = 0;
  ui.elements["chat-input"].listeners.keydown({ key: "Enter", shiftKey: false, isComposing: false, preventDefault: () => { prevented += 1; } });
  assert.equal(submissions, 1);
  assert.equal(prevented, 1);
  ui.elements["chat-input"].listeners.keydown({ key: "Enter", shiftKey: true, isComposing: false, preventDefault: () => { prevented += 1; } });
  assert.equal(submissions, 1);
  assert.equal(prevented, 1);
});

test("plus actions stay explicit and start only the chosen capture or knowledge control", async () => {
  const ui = setup();
  await ui.controller.initialLoad;
  assert.equal(ui.elements["chat-settings"].open, false);
  let imageClicks = 0; let cameraClicks = 0; let screenClicks = 0;
  ui.elements["chat-image-file"].addEventListener("click", () => imageClicks++);
  ui.elements["chat-capture-camera"].addEventListener("click", () => cameraClicks++);
  ui.elements["chat-capture-screen"].addEventListener("click", () => screenClicks++);
  ui.elements["chat-add-image-action"].click();
  ui.elements["chat-camera-action"].click();
  ui.elements["chat-screen-action"].click();
  assert.deepEqual([imageClicks, cameraClicks, screenClicks], [1, 1, 1]);
  ui.elements["chat-knowledge-menu-toggle"].listeners.change({ target: { checked: true } });
  assert.equal(ui.elements["chat-knowledge-enabled"].checked, true);
  assert.equal(ui.elements["chat-knowledge-panel"].open, true);
});

test("Brain defaults on when owner knowledge exists and previews selected chunks automatically before a turn", async () => {
  let sentBody = null;
  const ui = setup(async (path, options = {}) => {
    if (path === "/api/memory/owner") return response({ items: [{ id: "brain-note" }] });
    if (path === "/api/chat/conversations/" + encodeURIComponent("conversation") + "/knowledge-preview") {
      return response({ digest: "d".repeat(64), items: [{ source: "note.md", scope: "owner", chunk_reference: "1/1", content: "Project uses Ollama locally." }], trace: { context_bytes: 32 } });
    }
    if (path === "/api/chat/conversations" && options.method === "POST") {
      const body = JSON.parse(options.body);
      return response(snapshot());
    }
    if (path.endsWith("/messages")) {
      sentBody = JSON.parse(options.body);
      return response(snapshot([message("user", "completed", sentBody.text), message("assistant", "completed", "Reply") ]));
    }
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  assert.equal(ui.elements["chat-knowledge-enabled"].checked, true);
  assert.equal(ui.elements["chat-knowledge-owner"].checked, true);
  ui.elements["chat-input"].value = "What is my local setup?";
  const sendResult = await ui.controller.send({ preventDefault() {} });
  const previewCall = ui.calls.find(call => call.path.endsWith("/knowledge-preview"));
  assert.ok(previewCall, "exact chunks are previewed without a manual panel action; send=" + sendResult + "; state=" + ui.elements["chat-state"].textContent + "; calls=" + ui.calls.map(call => call.path).join(","));
  assert.equal(JSON.parse(previewCall.options.body).query, "What is my local setup?");
  assert.equal(sentBody.knowledge_enabled, true);
  assert.equal(sentBody.knowledge_preview_digest, "d".repeat(64));
  assert.match(ui.elements["chat-knowledge-preview-result"].textContent, /Project uses Ollama locally/);
});

test("narrow sidebar uses the menu toggle and Escape closes it", async () => {
  const callbacks = new Map();
  const windowRef = {
    location: { search: "" },
    matchMedia: () => ({ matches: true, addEventListener() {} }),
    addEventListener: (name, callback) => callbacks.set(name, [...(callbacks.get(name) || []), callback]),
  };
  const ui = setup(null, windowRef); await ui.controller.initialLoad;
  ui.elements["chat-menu-button"].click();
  assert.equal(ui.bodyClasses.has("navigation-open"), true);
  assert.equal(ui.elements["chat-menu-button"].attributes["aria-expanded"], "true");
  ui.documentListeners.get("keydown")[0]({ key: "Escape" });
  assert.equal(ui.bodyClasses.has("navigation-open"), false);
});

test("dark theme is the default and the explicit toggle persists light and dark", async () => {
  const storage = new Map();
  const windowRef = {
    location: { search: "" },
    localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    addEventListener() {},
  };
  const ui = setup(null, windowRef);
  await ui.controller.initialLoad;
  assert.equal(ui.documentRef.body.dataset.theme, "dark");
  ui.elements["chat-theme-toggle"].click();
  assert.equal(ui.documentRef.body.dataset.theme, "light");
  assert.equal(storage.get("ersel-chat-theme-v1"), "light");
  ui.elements["chat-theme-toggle"].click();
  assert.equal(ui.documentRef.body.dataset.theme, "dark");
});

test("conversation sidebar groups by date, supports search, rename, and pin", async () => {
  const storage = new Map();
  const callbacks = new Map();
  const windowRef = {
    location: { search: "" },
    localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
    prompt: () => "Renamed chat",
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    addEventListener: (name, callback) => callbacks.set(name, [...(callbacks.get(name) || []), callback]),
    dispatchEvent() {}, CustomEvent: class {},
  };
  const oldDate = new Date(Date.now() - 2 * 86400000).toISOString();
  const ui = setup(path => path === "/api/chat/conversations" ? response({ items: [
    { id: "today-id", coordinator: agent, created_at: new Date().toISOString() },
    { id: "earlier-id", coordinator: agent, created_at: oldDate },
  ] }) : null, windowRef);
  await ui.controller.initialLoad;
  assert.equal(ui.elements["chat-conversation-list"].children.length, 1);
  assert.equal(ui.elements["chat-earlier-list"].children.length, 1);
  assert.equal(ui.elements["chat-earlier-label"].hidden, false);
  const actions = ui.elements["chat-conversation-list"].children[0].children[1];
  actions.children[1].click();
  assert.match(ui.elements["chat-conversation-list"].textContent, /Renamed chat/);
  const refreshedActions = ui.elements["chat-conversation-list"].children[0].children[1];
  refreshedActions.children[2].click();
  assert.match(ui.elements["chat-conversation-list"].textContent, /Pinned/);
  ui.elements["chat-search"].value = "not found";
  ui.elements["chat-search"].listeners.input();
  assert.equal(ui.elements["chat-conversation-list"].children.length, 0);
});

test("answer trace is collapsed by default and remains available after a reply", async () => {
  const trace = { route: { agent: "Local Worker", provider: "ollama", model: "llama3.2:3b" }, steps: [],
    retrieval: { enabled: true, returned_chunks: [{ source: "notes.json" }] },
    sources: [{ source: "notes.json", chunk_reference: "memory-1#1" }] };
  const ui = setup(path => path.endsWith("/messages")
    ? response({ ...snapshot([message("assistant", "completed", "Answer")]), context_traces: { assistant: trace } })
    : null);
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Question";
  await ui.controller.send({ preventDefault() {} });
  const answer = ui.elements["chat-history"].children.find(item => item.className === "chat-message chat-message-assistant");
  const details = answer.children.find(item => item.className === "chat-answer-trace");
  assert.ok(details);
  const citations = answer.children.find(item => item.className === "chat-visible-citations");
  assert.ok(citations);
  assert.match(citations.textContent, /\[1\] notes\.json · memory-1#1/);
  assert.equal(details.open, false);
  assert.equal(details.children[0].textContent, "How I answered");
  assert.match(JSON.parse(ui.windowRef.sessionStorage.getItem("ersel-brain-retrieval-v1")).retrieved[0], /memory-1#1/);
  assert.equal(ui.elements["chat-empty-state"].hidden, true);
});

test("approval inbox is permission-gated, previews exact scope, and deny uses CSRF without execution", async () => {
  const digest = "a".repeat(64);
  let current = [{ approval_id: "approval-1", approval_digest: digest,
    payload_digest: "b".repeat(64), target_digest: "c".repeat(64),
    action_summary: "Remove the selected test package", target_ref: "package:test",
    scope_type: "principal", scope_id: "owner",
    capability_id: "software:manage", action_id: "software.remove", risk: "high",
    irreversible: true, expires_at: "2035-01-01T00:00:00+00:00", status: "pending" }];
  const ui = setup(async (path, options = {}) => {
    if (path.endsWith("/approval-1/deny") && options.method === "POST") {
      assert.equal(options.headers["X-Local-CSRF"], "test-csrf");
      assert.deepEqual(JSON.parse(options.body), { confirmed_digest: digest });
      current = [];
      return response({ status: "denied", denied_by: "owner" });
    }
    if (path === "/api/capabilities/approvals") return response({ items: current });
    return null;
  });
  await ui.controller.initialLoad;
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.elements["chat-approval-inbox"].hidden, false);
  assert.equal(ui.elements["chat-approval-count"].textContent, "1");
  const card = ui.elements["chat-approval-items"].children[0];
  assert.match(card.textContent, /Remove the selected test package/);
  assert.match(card.textContent, /package:test/);
  assert.match(card.textContent, /principal:owner/);
  assert.match(card.textContent, new RegExp(digest));
  const deny = card.children.at(-1).children.find(button => button.textContent === "Deny");
  await deny.listeners.click();
  assert.match(ui.planConfirmations.at(-1), /No protected action will run/);
  assert.equal(ui.calls.some(call => call.path.endsWith("/deny") && call.options.method === "POST"), true);
  assert.equal(ui.elements["chat-approval-count"].textContent, "0");
  assert.match(ui.elements["chat-approval-state"].textContent, /No current approval requests/);

  const denied = setup(async path => path === "/api/local/session"
    ? response({ csrf: "test-csrf", permissions: ["chat:read"] }) : null);
  await denied.controller.initialLoad;
  assert.equal(denied.elements["chat-approval-inbox"].hidden, true);
  assert.equal(denied.calls.some(call => call.path === "/api/capabilities/approvals"), false);
});

test("Coordinator delegation is explicit, plain-text only, and shows the bounded plan before sending", async () => {
  let sent = null;
  const ui = setup(async (path, options = {}) => {
    if (path === "/api/chat/conversations" && options.method === "POST") return response(snapshot());
    if (path.endsWith("/messages")) {
      sent = JSON.parse(options.body);
      return response({ ...snapshot([message("user", "completed", sent.text), message("assistant", "completed", "Delegated answer")]),
        handoff: { status: "completed", agent: { id: "researcher", name: "Researcher" } } });
    }
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-delegate-once"].checked = true;
  ui.elements["chat-input"].value = "Summarize the repository guidance";
  assert.equal(await ui.controller.send({ preventDefault() {} }), true);
  assert.deepEqual(sent, { text: "Summarize the repository guidance", delegate_once: true });
  assert.match(ui.planConfirmations.at(-1), /exactly one eligible Agent/);
  assert.match(ui.planConfirmations.at(-1), /shared single model slot/);
  assert.equal(ui.elements["chat-delegate-once"].checked, false);
  assert.match(ui.elements["chat-state"].textContent, /Coordinator selected Researcher/);
});

test("delete is visible only to an authorized owner and sends an explicit confirmed delete", async () => {
  const ui = setup((path, options) => {
    if (path === "/api/chat/conversations") return response({ items: [{
      id: "conversation-to-delete", coordinator: agent, created_at: new Date().toISOString(),
    }] });
    if (path === "/api/chat/conversations/conversation-to-delete" && options?.method === "DELETE") return response({ deleted: "conversation-to-delete" });
    return null;
  });
  await ui.controller.initialLoad;
  const row = ui.elements["chat-conversation-list"].children[0];
  const actions = row.children[1];
  const remove = actions.children.find(child => child.textContent === "Delete");
  assert.ok(remove);
  await remove.listeners.click();
  assert.ok(ui.calls.some(call => call.path === "/api/chat/conversations/conversation-to-delete"
    && call.options?.method === "DELETE" && call.options.headers["X-Local-CSRF"] === "test-csrf"));
  assert.equal(ui.elements["chat-conversation-list"].children.length, 0);
});

test("emergency stop is hidden until protected activity is reported", async () => {
  const callbacks = new Map();
  const windowRef = {
    location: { search: "" }, matchMedia: () => ({ matches: false, addEventListener() {} }),
    addEventListener: (name, callback) => callbacks.set(name, [...(callbacks.get(name) || []), callback]),
    dispatchEvent() {}, CustomEvent: class {},
  };
  const ui = setup(null, windowRef);
  await ui.controller.initialLoad;
  const button = ui.elements["chat-emergency-stop"];
  assert.equal(button.hidden, true);
  for (const callback of callbacks.get("ersel:voice-activity") || []) callback({ detail: { microphone: "active", local_playback: "off" } });
  assert.equal(button.hidden, false);
  for (const callback of callbacks.get("ersel:voice-activity") || []) callback({ detail: { microphone: "inactive", local_playback: "off" } });
  assert.equal(button.hidden, true);
});

test("emergency stop appears for each protected activity source and hides when it ends", async () => {
  const callbacks = new Map();
  const windowRef = {
    location: { search: "" }, matchMedia: () => ({ matches: false, addEventListener() {} }),
    addEventListener: (name, callback) => callbacks.set(name, [...(callbacks.get(name) || []), callback]),
    dispatchEvent() {}, CustomEvent: class {},
  };
  const ui = setup(null, windowRef); await ui.controller.initialLoad;
  const button = ui.elements["chat-emergency-stop"];
  const events = [
    ["ersel:voice-activity", { microphone: "active", local_playback: "off" }, { microphone: "inactive", local_playback: "off" }],
    ["ersel:voice-activity", { microphone: "inactive", local_playback: "active" }, { microphone: "inactive", local_playback: "off" }],
    ["ersel:camera-activity", { state: "active" }, { state: "inactive" }],
    ["ersel:screen-capture-activity", { state: "active" }, { state: "inactive" }],
    ["ersel:automation-activity", { state: "active" }, { state: "inactive" }],
  ];
  for (const [name, active, inactive] of events) {
    callbacks.get(name)[0]({ detail: active }); assert.equal(button.hidden, false, name);
    callbacks.get(name)[0]({ detail: inactive }); assert.equal(button.hidden, true, name);
  }
});

test("Send becomes Stop while a turn is pending and aborts local waiting without replay", async () => {
  const ui = setup((path, options) => {
    if (path.endsWith("/messages")) return new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "hello";
  const pending = ui.controller.send();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.elements["chat-send"].textContent, "Stop");
  assert.match(ui.elements["chat-state"].textContent, /Pending: waiting for the configured model/);
  assert.equal(ui.elements["chat-send"].disabled, false);
  let prevented = false;
  ui.elements["chat-send"].listeners.click({ preventDefault: () => { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(await pending, true);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 1);
  assert.match(ui.elements["chat-state"].textContent, /Stopped waiting.*No resend/);
  assert.equal(ui.elements["chat-send"].textContent, "Send");
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
  assert.match(ui.planConfirmations[0], /Review this chat plan before work begins/);
  assert.match(ui.planConfirmations[0], /Cancel prevents retrieval, tool calls, and provider work/);
  const post = ui.calls.find(call => call.path.endsWith("/messages"));
  assert.equal(post.options.credentials, "same-origin");
  assert.equal(post.options.headers["X-Local-CSRF"], "test-csrf");
  assert.deepEqual(JSON.parse(post.options.body), { text: "Hello" });
});

test("Electron direct launch opens a coordinator conversation and sends local chat without a setup confirmation", async () => {
  const ui = setup((path, options) => {
    if (path === "/api/chat/conversations" && options?.method === "POST") return response(snapshot());
    if (path.endsWith("/messages")) return response(snapshot([
      message("user", "completed", "hello"), message("assistant", "completed", "hi from local fake"),
    ]));
    return null;
  }, { location: { search: "?desktop=1", pathname: "/ui/chat" } }, () => false);
  assert.equal(await ui.controller.initialLoad, true);
  assert.equal(ui.calls.some(call => call.path === "/api/chat/conversations" && call.options?.method === "POST"), true);
  assert.equal(ui.elements["chat-state"].textContent, "");
  assert.equal(ui.elements["chat-agent"].children[0].textContent, "Actual Worker / configured-model");
  assert.equal(ui.elements["chat-header-model"].textContent, "configured-model");
  ui.elements["chat-input"].value = "hello";
  assert.equal(await ui.controller.send({ preventDefault() {} }), true);
  assert.equal(ui.planConfirmations.length, 0);
  assert.match(ui.elements["chat-history"].textContent, /hi from local fake/);
});

test("canceling the reviewed chat plan starts no retrieval, tools, or provider request", async () => {
  const ui = setup(null, globalThis.window, () => false);
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Do not send this";
  assert.equal(await ui.controller.send(), true);
  assert.match(ui.planConfirmations[0], /Send this message and selected context/);
  assert.equal(ui.calls.some(call => call.path.endsWith("/messages") || call.path.endsWith("/messages/stream")), false);
  assert.match(ui.elements["chat-state"].textContent, /Cancelled.*Nothing was sent/);
});

test("canceling a plan with a selected calculator does not submit the tool or chat turn", async () => {
  const ui = setup(null, globalThis.window, () => false);
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Calculate this";
  ui.elements["chat-tool-calculator-enabled"].checked = true;
  ui.elements["chat-tool-calculator-expression"].value = "6 * 7";
  assert.equal(await ui.controller.send(), true);
  assert.match(ui.planConfirmations[0], /calculator/);
  assert.equal(ui.calls.some(call => call.path.endsWith("/messages") || call.path.endsWith("/messages/stream")), false);
  assert.match(ui.elements["chat-state"].textContent, /Cancelled.*Nothing was sent/);
});

test("alternate route is opt-in per turn and displayed before confirmation", async () => {
  const ui = setup((path) => {
    if (path.endsWith("/route-suggestions")) return response({
      complexity: "complex",
      reason: "Complexity heuristic matched; difficulty is uncertain.",
      suggested: { provider_id: "ollama", model_id: "qwen2.5:7b" },
      candidates: [{ provider_id: "ollama", model_id: "qwen2.5:7b",
        destination: "local Ollama service", kind: "local" }],
    });
    if (path.endsWith("/messages")) return response(snapshot([
      message("user", "completed", "Compare these options"),
      message("assistant", "completed", "A grounded comparison"),
    ]));
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Compare these options";
  assert.equal(await ui.elements["chat-route-check"].listeners.click(), true);
  assert.match(ui.elements["chat-route-state"].textContent, /uncertain/i);
  ui.elements["chat-input"].value = "A different prompt";
  ui.elements["chat-input"].listeners.input();
  assert.equal(ui.elements["chat-route-select"].disabled, true);
  ui.elements["chat-input"].value = "Compare these options";
  assert.equal(await ui.elements["chat-route-check"].listeners.click(), true);
  ui.elements["chat-route-select"].value = "ollama\nqwen2.5:7b";
  assert.equal(await ui.controller.send(), true);
  const confirmation = ui.planConfirmations.at(-1);
  assert.match(confirmation, /ollama \/ qwen2\.5:7b/);
  assert.match(confirmation, /local Ollama service/);
  const sent = JSON.parse(ui.calls.find(call => call.path.endsWith("/messages")).options.body);
  assert.equal(sent.route_provider_id, "ollama");
  assert.equal(sent.route_model_id, "qwen2.5:7b");
  assert.equal(sent.route_consent, true);
  assert.equal(sent.cloud_consent, undefined);
});

test("declining an alternate route confirmation performs no provider request", async () => {
  const ui = setup((path) => path.endsWith("/route-suggestions") ? response({
    complexity: "complex", reason: "Uncertain heuristic", suggested: null,
    candidates: [{ provider_id: "ollama", model_id: "qwen2.5:7b",
      destination: "local Ollama service", kind: "local" }],
  }) : null, globalThis.window, () => false);
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Compare these options";
  await ui.elements["chat-route-check"].listeners.click();
  ui.elements["chat-route-select"].value = "ollama\nqwen2.5:7b";
  assert.equal(await ui.controller.send(), true);
  assert.match(ui.planConfirmations.at(-1), /ollama \/ qwen2\.5:7b/);
  assert.equal(ui.calls.some(call => call.path.endsWith("/messages") || call.path.endsWith("/messages/stream")), false);
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
  assert.equal(ui.elements["chat-state"].textContent, "");
  assert.equal(ui.elements["chat-stop-display"].hidden, true);
});

test("knowledge requires an exact preview and displays returned citations in How I answered", async () => {
  const trace = {
    route: { agent_id: "worker", agent: "Actual Worker", provider: "ollama", model: "local-model", source: "owner selected" },
    retrieval: { enabled: true, mode: "lexical-only", query: "Which port?", returned_chunks: [{ source: "private.md" }] },
    sources: [{ source: "private.md", scope: "owner", chunk_reference: "note-1#1", score: 0.5 }],
    truncation: {}, cloud: { provider_used: null, consent_given: false, private_knowledge_sent: false },
    vision: { used: true, provider: "ollama", model: "vision-model", destination: "local", outcome: "completed", image_count: 1, retention: "discarded_after_one_use" },
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
  assert.equal(await ui.controller.send(), true);
  assert.ok(ui.calls.some(call => call.path.endsWith("/knowledge-preview")));
  assert.match(ui.elements["chat-knowledge-preview-result"].textContent, /Port 8123/);
  const body = JSON.parse(ui.calls.find(call => call.path.endsWith("/messages")).options.body);
  assert.equal(body.knowledge_enabled, true);
  assert.equal(body.knowledge_preview_digest, "a".repeat(64));
  assert.match(ui.elements["chat-history"].textContent, /How I answered/);
  assert.match(ui.elements["chat-history"].textContent, /private.md.*note-1#1/);
  assert.match(ui.elements["chat-history"].textContent, /Image input: ollama \/ vision-model \(local\) · completed · 1 image\(s\) · discarded_after_one_use/);
});

test("reviewed tool calls are explicit, one-turn, and routed through non-streaming chat", async () => {
  const ui = setup((path, options) => {
    if (path === "/api/chat/conversations" && options.method === "POST") return response({ ...snapshot(), streaming_supported: true });
    if (path.endsWith("/messages")) return response({
      ...snapshot([message("user", "completed", "Calculate it"), message("assistant", "completed", "The result is 36.")]),
      context_trace: {
        steps: [{ step: "plan", status: "completed", source: "bounded configured chat workflow", duration_ms: 0 },
          { step: "retrieve", status: "skipped", reason: "No selected retrieval", duration_ms: 0 },
          { step: "calculator", status: "completed", source: "local calculator", duration_ms: 0 },
          { step: "answer", status: "completed", source: "ollama / configured-model", duration_ms: 1 }],
        tools: [{ tool: "calculator", parameters: { expression: "(12 + 6) * 2" }, source: "local calculator", outcome: "completed", duration_ms: 0, result_characters: 2 }],
        actions: { tools_run: true, tasks_created: false },
      },
    });
    return null;
  });
  await ui.controller.initialLoad;
  await ui.controller.start();
  ui.elements["chat-input"].value = "Calculate it";
  ui.elements["chat-tool-calculator-enabled"].checked = true;
  ui.elements["chat-tool-calculator-expression"].value = "(12 + 6) * 2";
  assert.equal(await ui.controller.send(), true);
  const post = ui.calls.find(call => call.path.endsWith("/messages"));
  assert.deepEqual(JSON.parse(post.options.body).reviewed_tools, [{ kind: "calculator", expression: "(12 + 6) * 2" }]);
  assert.match(ui.planConfirmations[0], /calculator/);
  assert.match(ui.elements["chat-history"].textContent, /Reviewed tool calls.*calculator.*completed/);
  assert.match(ui.elements["chat-history"].textContent, /Workflow steps.*plan.*retrieve.*calculator.*answer/);
});

test("local document choices load only after opening reviewed tools with documentation permission", async () => {
  let calls = 0;
  const ui = setup(path => {
    if (path === "/api/documentation") {
      calls += 1;
      return response({ items: [{ id: "guide", title: "Local guide" }] });
    }
    return null;
  });
  await ui.controller.initialLoad;
  assert.equal(calls, 0);
  ui.elements["chat-reviewed-tools"].open = true;
  await ui.elements["chat-reviewed-tools"].listeners.toggle();
  assert.equal(calls, 1);
  assert.equal(ui.elements["chat-tool-document-id"].children[1].value, "guide");
  await ui.elements["chat-reviewed-tools"].listeners.toggle();
  assert.equal(calls, 1);
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
    if (path.endsWith("/conversation")) return response({
      ...snapshot([message("user", "failed", "Hello")]),
      context_traces: { user: {
        outcome: "failed", failure: "Provider or chat runtime did not produce a verified reply; raw diagnostics are omitted.",
        steps: [
          { step: "plan", status: "completed", source: "bounded configured chat workflow", duration_ms: 0 },
          { step: "retrieve", status: "skipped", reason: "No separate knowledge retrieval was selected.", duration_ms: 0 },
          { step: "tools", status: "skipped", reason: "No reviewed tools were selected.", duration_ms: 0 },
          { step: "answer", status: "failed", source: "configured coordinator", duration_ms: 2 },
        ], timing: { turn_elapsed_ms: 2 }, actions: { tools_run: false, tasks_created: false },
      } },
    });
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
  assert.equal(ui.elements["chat-send"].textContent, "Stop");
  assert.equal(ui.elements["chat-send"].disabled, false);
  assert.equal(await ui.controller.refresh(), false);
  finish(response({ detail: "raw failure" }, 502));
  assert.equal(await pending, false);
  assert.equal(ui.calls.filter(call => call.path.endsWith("/messages")).length, 1);
  assert.match(ui.elements["chat-history"].textContent, /user - failed/);
  assert.match(ui.elements["chat-history"].textContent, /How I answered.*answer.*failed/);
  assert.match(ui.elements["chat-history"].textContent, /Failure: Provider or chat runtime did not produce a verified reply/);
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

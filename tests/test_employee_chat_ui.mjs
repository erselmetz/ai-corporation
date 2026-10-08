import assert from "node:assert/strict";
import test from "node:test";
import { mountEmployeeChat } from "../app/webui/static/employee-chat.mjs";

class Element {
  constructor(tag = "") {
    this.tag = tag;
    this.children = [];
    this.value = "";
    this.text = "";
    this.listeners = {};
    this.disabled = false;
    this.hidden = false;
    this.checked = false;
  }
  set textContent(value) { this.text = value; this.children = []; }
  get textContent() { return this.text + this.children.map((node) => node.textContent).join(""); }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(node) {
    this.children.push(node);
    if (this.tag === "select" && this.children.length === 1) this.value = node.value;
  }
  replaceChildren() { this.children = []; this.text = ""; this.value = ""; }
  addEventListener(event, fn) { this.listeners[event] = fn; }
}

function setup({ supportsStreaming = false } = {}) {
  const ids = [
    "individual-employee", "individual-conversation", "individual-chat-state",
    "individual-chat-identity", "individual-chat-history", "individual-chat-form",
    "individual-chat-input", "individual-chat-send", "individual-cloud-consent-panel",
    "individual-cloud-consent", "individual-chat-new", "individual-chat-refresh",
    "individual-chat-close",
    "individual-chat-stop-display",
  ];
  const elements = Object.fromEntries(ids.map((id) => [
    id,
    new Element(["individual-employee", "individual-conversation"].includes(id) ? "select" : ""),
  ]));
  const calls = [];
  const conversation = {
    id: "conversation-1",
    employee_id: "employee-1",
    agent_id: "agent-1",
    status: "open",
    messages: [],
  };
  const agent = {
    id: "agent-1", name: "<script>Agent</script>", role: "Worker",
    provider_id: "gemini", model_id: "gemini-test",
    supports_streaming: supportsStreaming,
  };
  const employee = { id: "employee-1", name: "<script>Employee</script>", role: "Worker" };
  let created = false;
  const snapshot = () => ({
    conversation: structuredClone(conversation),
    employee,
    agent,
  });
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    let body = {};
    let status = 200;
    if (path === "/api/employees") {
      body = { items: [{ ...employee, agent_id: agent.id }] };
    } else if (path === "/api/local/session") {
      body = { csrf: "csrf-token" };
    } else if (path === "/api/employee-chat/conversations" && options.method === "POST") {
      created = true;
      status = 201;
      body = snapshot();
    } else if (path === "/api/employee-chat/conversations") {
      body = { items: created ? [{
        conversation_id: conversation.id, employee, agent, status: conversation.status,
      }] : [] };
    } else if (path === "/api/employee-chat/conversations/conversation-1/messages") {
      const request = JSON.parse(options.body);
      conversation.messages.push(
        { id: "user-1", role: "user", content: request.text, status: "completed" },
        { id: "assistant-1", role: "assistant", content: "<script>reply</script>", status: "completed" },
      );
      body = snapshot();
    } else if (path === "/api/employee-chat/conversations/conversation-1/messages/stream") {
      const request = JSON.parse(options.body);
      conversation.messages.push(
        { id: "user-1", role: "user", content: request.text, status: "completed" },
        { id: "assistant-1", role: "assistant", content: "actual reply", status: "completed" },
      );
      const event = {
        type: "complete",
        snapshot: snapshot(),
      };
      const encoder = new TextEncoder();
      const bodyBytes = encoder.encode([
        JSON.stringify({ type: "chunk", text: "actual " }),
        JSON.stringify({ type: "chunk", text: "reply" }),
        JSON.stringify(event),
      ].join("\n") + "\n");
      return {
        ok: true,
        status: 200,
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(bodyBytes);
            controller.close();
          },
        }),
      };
    } else {
      throw new Error(`Unexpected request ${path} ${options.method}`);
    }
    return { ok: true, status, json: async () => body };
  };
  const controller = mountEmployeeChat({
    documentRef: { getElementById: (id) => elements[id], createElement: (tag) => new Element(tag) },
    fetchImpl,
    confirmImpl: () => true,
  });
  return { elements, calls, controller };
}

test("Employee chat uses CSRF, inert rendering and explicit per-turn Gemini consent", async () => {
  const ui = setup();
  await ui.controller.initialLoad;
  assert.equal(ui.elements["individual-chat-new"].disabled, false);
  assert.equal(ui.elements["individual-cloud-consent-panel"].hidden, true);
  assert.equal(await ui.controller.startConversation(), true);
  assert.equal(ui.elements["individual-cloud-consent-panel"].hidden, false);
  assert.equal(ui.elements["individual-chat-send"].disabled, true);
  assert.match(ui.elements["individual-chat-identity"].textContent, /<script>Employee<\/script>/);
  assert.equal(ui.elements["individual-chat-history"].children.length, 0);

  ui.elements["individual-cloud-consent"].checked = true;
  ui.elements["individual-cloud-consent"].listeners.change();
  assert.equal(ui.elements["individual-chat-send"].disabled, false);
  ui.elements["individual-chat-input"].value = "Hello";
  assert.equal(await ui.controller.send(), true);
  const send = ui.calls.find((call) => call.path.endsWith("/messages"));
  assert.equal(send.options.credentials, "same-origin");
  assert.equal(send.options.headers["X-Local-CSRF"], "csrf-token");
  assert.deepEqual(JSON.parse(send.options.body), { text: "Hello", cloud_consent: true });
  assert.deepEqual(
    ui.elements["individual-chat-history"].children.map((element) => element.textContent),
    [
      "user (completed): Hello",
      "assistant (completed): <script>reply</script>",
    ],
  );
  assert.match(ui.elements["individual-chat-identity"].textContent, /gemini\/gemini-test/);
  assert.equal(ui.elements["individual-cloud-consent"].checked, false);
  assert.equal(ui.elements["individual-chat-send"].disabled, true);
});

test("Employee chat streams only from an advertised provider and handles the final snapshot", async () => {
  const ui = setup({ supportsStreaming: true });
  await ui.controller.initialLoad;
  assert.equal(await ui.controller.startConversation(), true);
  ui.elements["individual-cloud-consent"].checked = true;
  ui.elements["individual-cloud-consent"].listeners.change();
  ui.elements["individual-chat-input"].value = "Hello";
  assert.equal(await ui.controller.send(), true);
  const post = ui.calls.find((call) => call.path.endsWith("/messages/stream"));
  assert.equal(post.options.credentials, "same-origin");
  assert.equal(post.options.headers["X-Local-CSRF"], "csrf-token");
  assert.deepEqual(JSON.parse(post.options.body), {
    text: "Hello",
    cloud_consent: true,
  });
  assert.deepEqual(
    ui.elements["individual-chat-history"].children.map((element) => element.textContent),
    ["user (completed): Hello", "assistant (completed): actual reply"],
  );
  assert.match(ui.elements["individual-chat-state"].textContent, /Stream completed/);
  assert.equal(ui.elements["individual-chat-stop-display"].hidden, true);
});

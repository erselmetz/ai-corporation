import test from "node:test";
import assert from "node:assert/strict";
import { createChatWorkspace } from "../app/webui/static/chat-workspace.mjs";

class Element {
  constructor() { this.value = ""; this.children = []; }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; this.value = ""; }
}
function fixture(id, model = "small", project = "p1") {
  const elements = Object.fromEntries(["workspace-model", "workspace-project", "chat-agent"].map(id => [id, new Element()]));
  const calls = []; const changes = []; const saved = [];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url, options });
    const result = url === "/api/local/session" ? { csrf: "test-only" }
      : url === "/api/chat/workspaces/models" ? { items: [{ provider_id: "ollama", model_id: "small" }, { provider_id: "ollama", model_id: "large" }] }
      : url === "/api/projects" ? { items: [{ id: "p1", name: "Project one" }, { id: "p2", name: "Project two" }] }
      : url === "/api/chat/workspaces" ? { ...JSON.parse(options.body), owner: "owner" } : {};
    return { ok: true, json: async () => result };
  };
  const controller = createChatWorkspace({ documentRef: { getElementById: id => elements[id], createElement: () => new Element() },
    windowRef: { desktopBridge: { getWorkspaceState: async () => ({ id, agent: "coordinator", provider: "ollama", model, project }),
      saveWorkspaceState: async value => saved.push(value) } }, fetchImpl, onChange: async value => changes.push(value) });
  return { controller, calls, changes, saved, elements };
}
const agents = [{ id: "coordinator", name: "Coordinator", provider: "ollama", model: "small" }];

test("two window controllers keep model, project and request scope independent", async () => {
  const one = fixture("one", "small", "p1"); const two = fixture("two", "large", "p2");
  await Promise.all([one.controller.initialize(agents), two.controller.initialize(agents)]);
  assert.equal(one.controller.selection().model, "small");
  assert.equal(two.controller.selection().model, "large");
  assert.equal(one.controller.selection().project, "p1");
  assert.equal(two.controller.selection().project, "p2");
  await one.controller.fetch("/api/chat/conversations");
  await two.controller.fetch("/api/capabilities/approvals");
  assert.equal(one.calls.at(-1).options.headers["X-Chat-Workspace"], "one");
  assert.equal(two.calls.at(-1).options.headers["X-Chat-Workspace"], "two");
});

test("selection change opens a new context without sending a model turn or changing another window", async () => {
  const one = fixture("one"); await one.controller.initialize(agents);
  one.elements["workspace-model"].value = JSON.stringify(["ollama", "large"]);
  one.elements["workspace-project"].value = "p2";
  await one.controller.change();
  assert.equal(one.changes[0].model, "large"); assert.equal(one.changes[0].project, "p2");
  assert.equal(one.changes[0].conversation, "");
  assert.equal(one.saved[0].conversation, "");
  assert.equal(one.calls.some(call => call.url.endsWith("/messages")), false);
  assert.equal(one.calls.some(call => call.url.includes("assignment")), false);
  one.controller.setDisabled(true); assert.equal(one.elements["workspace-project"].disabled, true);
});

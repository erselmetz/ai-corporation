import assert from "node:assert/strict";
import test from "node:test";
import { mountTaskProgress } from "../app/webui/static/task-progress.mjs";

class Element {
  constructor() { this.children = []; this.text = ""; this.value = ""; this.listeners = {}; }
  get textContent() { return this.text + this.children.map(x => x.textContent).join(""); }
  set textContent(value) { this.text = value; this.children = []; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children = []; this.text = ""; }
  addEventListener(event, handler) { this.listeners[event] = handler; }
}
function setup(fetchImpl, taskId = "task") {
  const elements = Object.fromEntries(["task-progress", "task-progress-state", "activity-task-id", "activity-refresh"].map(id => [id, new Element()]));
  elements["activity-task-id"].value = taskId;
  const documentRef = { getElementById: id => elements[id], createElement: () => new Element() };
  const controller = mountTaskProgress({ documentRef, fetchImpl });
  return { controller, elements };
}
const response = (status, task) => ({ ok: status === 200, status, json: async () => task });
for (const status of ["pending", "running", "completed", "failed"]) {
  test(`shows actual ${status} lifecycle and only allowed fields`, async () => {
    let options;
    const { controller, elements } = setup(async (path, supplied) => {
      assert.equal(path, "/api/tasks/task");
      options = supplied;
      return response(200, { id: "task", status, assigned_agent: "agent", result: "private result", error: "private error" });
    });
    assert.equal(await controller.initialLoad, true);
    assert.equal(options.credentials, "same-origin");
    const text = elements["task-progress"].textContent;
    assert.match(text.toLowerCase(), new RegExp(status));
    assert.ok(text.includes("agent"));
    assert.ok(!text.includes("private"));
  });
}
for (const [status, message] of [[401, "Sign-in"], [403, "task:read"], [404, "not found"], [500, "could not"]]) {
  test(`clears previously rendered progress on ${status}`, async () => {
    let current = 200;
    const { controller, elements } = setup(async () => response(current, { id: "task", status: "running", assigned_agent: null }));
    await controller.initialLoad;
    current = status;
    assert.equal(await controller.loadProgress(), false);
    assert.equal(elements["task-progress"].textContent, "");
    assert.ok(elements["task-progress-state"].textContent.includes(message));
  });
}
test("does not fetch without a selected Task", async () => {
  const { controller } = setup(() => { throw new Error("No fetch expected"); }, "");
  assert.equal(await controller.initialLoad, false);
});
test("rejects mismatched Task identities and unsupported status", async () => {
  for (const task of [{ id: "other", status: "running", assigned_agent: null }, { id: "task", status: "unknown", assigned_agent: null }]) {
    const { controller, elements } = setup(async () => response(200, task));
    assert.equal(await controller.initialLoad, false);
    assert.equal(elements["task-progress"].textContent, "");
  }
});
test("a changed selection invalidates an in-flight response", async () => {
  let finish;
  const { controller, elements } = setup(() => new Promise(resolve => { finish = resolve; }));
  elements["activity-task-id"].value = "other";
  elements["activity-task-id"].listeners.input();
  finish(response(200, { id: "task", status: "running", assigned_agent: null }));
  assert.equal(await controller.initialLoad, false);
  assert.equal(elements["task-progress"].textContent, "");
});

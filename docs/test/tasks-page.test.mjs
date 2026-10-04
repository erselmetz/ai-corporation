import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import test from "node:test";
import { taskGroups, tasks, nextTask, roadmapRules } from "../tasks-data.mjs";

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ""; }
  set textContent(value) { this.text = value; this.children = []; }
  get textContent() { return this.text + this.children.map(node => node.textContent).join(""); }
  set innerHTML(_) { throw new Error("Task contracts must be rendered as text"); }
  append(...nodes) { this.children.push(...nodes); }
}
const source = (await readFile(new URL("../tasks-page.js", import.meta.url), "utf8")).replace(/^import[^\n]+\n/, "");
function render() {
  const elements = Object.fromEntries(["roadmap-groups", "roadmap-summary", "category-index", "next-task", "roadmap-rules"].map(id => [id, new Element("div")]));
  runInNewContext(source, { taskGroups, tasks, nextTask, roadmapRules,
    document: { querySelector: selector => elements[selector.slice(1)], createElement: tag => new Element(tag) } });
  return elements;
}

test("shows all tasks in descending order and highlights the actual next planned task", () => {
  const elements = render();
  const groups = elements["roadmap-groups"].children;
  assert.equal(groups[0].id, "tasks-101-128");
  const items = groups.flatMap(group => group.children[1].children);
  assert.deepEqual(items.map(item => Number(item.children[0].textContent)), Array.from({ length: 128 }, (_, index) => 128 - index));
  assert.match(elements["roadmap-summary"].textContent, /128 roadmap tasks.*110 completed.*18 planned/);
  assert.equal(elements["next-task"].children[0].href, "#task-111");
  assert.match(elements["next-task"].textContent, /Next: Task 111/);
  assert.match(elements["next-task"].textContent, /Controlled worker dispatch/);
});

test("renders completion evidence separately from planned decision gates and exposes handoff rules", () => {
  const elements = render();
  const items = elements["roadmap-groups"].children[0].children[1].children;
  const completed = items.find(item => item.id === "task-103");
  const planned = items.find(item => item.id === "task-111");
  assert.equal(completed.children[2].textContent, "Completed");
  assert.match(completed.textContent, /Verified checkpoint: d1ca364/);
  assert.match(completed.textContent, /876 Python passed/);
  const localSetup = items.find(item => item.id === "task-104");
  assert.match(localSetup.textContent, /Verified checkpoint: task-104-local-model-setup/);
  assert.ok(localSetup.children[4].children.some(node => node.href === "https://github.com/erselmetz/ai-corporation/tree/task-104-local-model-setup"));
  const onlineProvider = items.find(item => item.id === "task-105");
  assert.equal(onlineProvider.children[2].textContent, "Completed");
  assert.match(onlineProvider.textContent, /task-105-gemini-online-chat/);
  const secureChatOnboarding = items.find(item => item.id === "task-106");
  assert.equal(secureChatOnboarding.children[2].textContent, "Completed");
  assert.match(secureChatOnboarding.textContent, /task-106-secure-chat-onboarding/);
  assert.match(secureChatOnboarding.textContent, /best-effort/);
  assert.equal(planned.children[2].textContent, "Planned");
  assert.match(planned.textContent, /Acceptance checks/);
  assert.match(planned.textContent, /Out of scope/);
  assert.match(planned.textContent, /Owner decisions/);
  assert.ok(!planned.textContent.includes("Verified checkpoint"));
  const individualChat = items.find(item => item.id === "task-108");
  assert.equal(individualChat.children[2].textContent, "Completed");
  assert.match(individualChat.textContent, /manual and require an explicit preview\/confirmation/);
  assert.match(individualChat.textContent, /one-Gemini-Agent connection flow/);
  assert.match(individualChat.textContent, /62 passed/);
  const assignmentPolicy = items.find(item => item.id === "task-109");
  assert.equal(assignmentPolicy.children[2].textContent, "Completed");
  assert.match(assignmentPolicy.textContent, /fresh positive tested capability references/);
  assert.match(assignmentPolicy.textContent, /task-109-capability-based-assignment-policy/);
  const chatProposal = items.find(item => item.id === "task-110");
  assert.equal(chatProposal.children[2].textContent, "Completed");
  assert.match(chatProposal.textContent, /exact server-generated proposal digest/);
  assert.match(chatProposal.textContent, /chat-task:create/);
  assert.match(chatProposal.textContent, /task-110-chat-proposals-pending-task-review/);
  assert.match(elements["roadmap-rules"].textContent, /Do not infer approval/);
  assert.match(elements["roadmap-rules"].textContent, /identical generated code is not guaranteed/);
});

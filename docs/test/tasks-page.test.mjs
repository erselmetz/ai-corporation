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

test("shows all tasks in descending order and reports the next planned task", () => {
  const elements = render();
  const groups = elements["roadmap-groups"].children;
  assert.equal(groups[0].id, "tasks-167-170");
  const items = groups.flatMap(group => group.children[1].children);
  assert.deepEqual(items.map(item => Number(item.children[0].textContent)), Array.from({ length: 170 }, (_, index) => 170 - index));
  assert.match(elements["roadmap-summary"].textContent, /170 roadmap tasks.*130 completed.*40 planned/);
  assert.match(elements["next-task"].textContent, /Next: Task 131/);
});

test("renders completion evidence separately from planned decision gates and exposes handoff rules", () => {
  const elements = render();
  const items = elements["roadmap-groups"].children.flatMap(group => group.children[1].children);
  const completed = items.find(item => item.id === "task-103");
  const dispatch = items.find(item => item.id === "task-111");
  const multiProvider = items.find(item => item.id === "task-112");
  const release = items.find(item => item.id === "task-129");
  const semanticMemory = items.find(item => item.id === "task-130");
  const firstPlanned = items.find(item => item.id === "task-131");
  assert.equal(release.children[2].textContent, "Completed");
  assert.match(release.textContent, /task-129-command-center-release-acceptance/);
  assert.match(release.textContent, /206A36D5C94FD76B2696C01F95CD842C24E3A79FD05FEB7FDB45F3DA101DC091/);
  assert.match(release.textContent, /capacity remain UNKNOWN/);
  assert.equal(semanticMemory.children[2].textContent, "Completed");
  assert.match(semanticMemory.textContent, /task-130-semantic-memory-rag-foundation/);
  assert.match(semanticMemory.textContent, /104 passed/);
  assert.equal(firstPlanned.children[2].textContent, "Planned");
  assert.match(firstPlanned.textContent, /Task 131|Supported packaging/);
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
  assert.equal(dispatch.children[2].textContent, "Completed");
  assert.match(dispatch.textContent, /task-111-controlled-worker-dispatch/);
  assert.match(dispatch.textContent, /Focused dispatch API.*38 passed/);
  assert.match(dispatch.textContent, /fails closed until an embedding host/);
  assert.match(dispatch.textContent, /Acceptance checks/);
  assert.match(dispatch.textContent, /Out of scope/);
  assert.equal(multiProvider.children[2].textContent, "Completed");
  assert.match(multiProvider.textContent, /task-112-multiple-provider-connections/);
  assert.match(multiProvider.textContent, /88 passed/);
  assert.match(multiProvider.textContent, /16 passed/);
  assert.match(multiProvider.textContent, /not a monetary guarantee/);
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
  const streaming = items.find(item => item.id === "task-120");
  assert.equal(streaming.children[2].textContent, "Completed");
  assert.match(streaming.textContent, /task-120-supported-streaming-truthful-stop/);
  assert.match(streaming.textContent, /79 passed/);
  assert.match(streaming.textContent, /Stop only hides later chunks/);
  assert.match(streaming.textContent, /known unrelated pre-existing failures/);
  const repositoryStudy = items.find(item => item.id === "task-121");
  assert.equal(repositoryStudy.children[2].textContent, "Completed");
  assert.match(repositoryStudy.textContent, /task-121-chat-driven-github-study/);
  assert.match(repositoryStudy.textContent, /exact-repository allowlist/);
  assert.match(repositoryStudy.textContent, /unapproved/);
  assert.match(repositoryStudy.textContent, /empty GitHub repository allowlist/);
  assert.match(elements["roadmap-rules"].textContent, /Do not infer approval/);
  assert.match(elements["roadmap-rules"].textContent, /identical generated code is not guaranteed/);
});

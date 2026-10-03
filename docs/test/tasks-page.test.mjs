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
  assert.match(elements["roadmap-summary"].textContent, /128 roadmap tasks.*103 completed.*25 planned/);
  assert.equal(elements["next-task"].children[0].href, "#task-104");
  assert.match(elements["next-task"].textContent, /Next: Task 104/);
  assert.match(elements["next-task"].textContent, /model-selection permission/);
});

test("renders completion evidence separately from planned decision gates and exposes handoff rules", () => {
  const elements = render();
  const items = elements["roadmap-groups"].children[0].children[1].children;
  const completed = items.find(item => item.id === "task-103");
  const planned = items.find(item => item.id === "task-104");
  assert.equal(completed.children[2].textContent, "Completed");
  assert.match(completed.textContent, /Verified checkpoint: d1ca364/);
  assert.match(completed.textContent, /876 Python passed/);
  assert.equal(planned.children[2].textContent, "Planned");
  assert.match(planned.textContent, /Acceptance checks/);
  assert.match(planned.textContent, /Out of scope/);
  assert.match(planned.textContent, /Owner decisions/);
  assert.ok(!planned.textContent.includes("Verified checkpoint"));
  assert.match(elements["roadmap-rules"].textContent, /Do not infer approval/);
  assert.match(elements["roadmap-rules"].textContent, /identical generated code is not guaranteed/);
});

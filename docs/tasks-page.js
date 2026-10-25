import { taskGroups, tasks, nextTask, roadmapRules, recommendedOrder } from "./tasks-data.mjs";
import { verificationLabels } from "./roadmap-status.js";

const container = document.querySelector("#roadmap-groups");
const summary = document.querySelector("#roadmap-summary");
const categoryIndex = document.querySelector("#category-index");
function textNode(tag, content, parent) {
  const node = document.createElement(tag);
  node.textContent = String(content);
  parent.append(node);
  return node;
}
function contractList(parent, title, values) {
  if (!values?.length) return;
  textNode("h3", title, parent);
  const list = document.createElement("ul");
  values.forEach(value => textNode("li", value, list));
  parent.append(list);
}
const nextPanel = document.querySelector("#next-task");
if (nextTask) {
  const link = textNode("a", `Next: Task ${nextTask.number} — ${nextTask.title}`, nextPanel);
  link.href = `#task-${nextTask.number}`;
  textNode("p", nextTask.description, nextPanel);
  contractList(nextPanel, "Resolve before implementation", nextTask.decisions);
} else textNode("p", "No remaining planned task in this published list.", nextPanel);
const rulesPanel = document.querySelector("#roadmap-rules");
for (const [name, rule] of Object.entries(roadmapRules)) {
  const paragraph = document.createElement("p");
  textNode("strong", `${name[0].toUpperCase() + name.slice(1)}: `, paragraph);
  textNode("span", rule, paragraph);
  rulesPanel.append(paragraph);
}

for (const group of [...taskGroups].sort((a, b) => Math.max(...b.range.match(/\d+/g).map(Number)) - Math.max(...a.range.match(/\d+/g).map(Number)))) {
  const sectionId = `tasks-${group.range.replace("–", "-")}`;
  const categoryLink = document.createElement("a");
  categoryLink.href = `#${sectionId}`;
  const categoryName = group.name === "Web/API Corporation Interface"
    ? "Web / API Corporation Interface"
    : group.name;
  categoryLink.textContent = `${categoryName} — Tasks ${group.range}`;
  categoryIndex.append(categoryLink);

  const section = document.createElement("section");
  section.className = "task-category";
  section.id = sectionId;
  const heading = document.createElement("h2");
  heading.textContent = `Tasks ${group.range} — ${group.name}`;
  const list = document.createElement("ol");
  list.className = "task-list";

  for (const task of tasks.filter((item) => item.category === group.name).sort((a, b) => b.number - a.number)) {
    const item = document.createElement("li");
    item.className = "task-item";
    item.id = `task-${task.number}`;
    const number = document.createElement("span");
    number.className = "task-number";
    number.textContent = String(task.number).padStart(2, "0");
    const title = document.createElement("span");
    title.className = "task-title";
    title.textContent = task.title;
    const status = document.createElement("span");
    status.className = `status status-${task.status === "completed" ? "complete" : task.status === "deferred" ? "deferred" : "planned"}`;
    status.textContent = task.status === "completed" ? "Completed" : task.status === "deferred" ? "Deferred — incomplete" : task.status === "design_only" ? "Design only" : task.status === "superseded" ? "Superseded by 223-227" : task.status === "not_done" ? "Not done — scope undefined" : "Planned";
    const description = document.createElement("span");
    description.className = "task-description";
    description.textContent = task.description;
    const verification = verificationLabels(task);
    const automatedBadge = document.createElement("span");
    automatedBadge.className = "verification-badge verification-automated";
    automatedBadge.textContent = verification.automated;
    const realWorldBadge = document.createElement("span");
    realWorldBadge.className = "verification-badge verification-real-world";
    realWorldBadge.textContent = verification.realWorld;
    item.append(number, title, status, description, automatedBadge, realWorldBadge);
    if (task.acceptance) {
      const details = document.createElement("details");
      details.className = "task-contract";
      textNode("summary", "Scope, completion checks and evidence", details);
      textNode("p", `Planning area: ${task.area} · Depends on Tasks ${task.dependsOn.join(", ")}`, details);
      contractList(details, "Acceptance checks", task.acceptance);
      contractList(details, "Out of scope", task.outOfScope);
      contractList(details, "Risks", task.risks);
      contractList(details, "AI-run verification", task.automatedVerification);
      contractList(details, "Follow-up validation (unverified coverage)", task.followUpValidation);
      contractList(details, "Owner decisions before dependent code", task.decisions);
      if (task.checkpoint) {
        const link = textNode("a", `${task.status === "superseded" ? "Historical" : "Recorded"} checkpoint: ${task.checkpoint}`, details);
        link.href = `https://github.com/erselmetz/ai-corporation/${task.checkpoint.startsWith("task-") ? "tree" : "commit"}/${encodeURIComponent(task.checkpoint)}`;
      }
      contractList(details, "Recorded validation", task.validation);
      contractList(details, "Known limitations", task.limitations);
      contractList(details, "History", task.history?.map(entry => `${entry.date}: ${entry.summary}`));
      contractList(details, "Release readiness (source / packaged / real device)", task.releaseReadiness?.map(entry => `${entry.capability}: ${entry.source} / ${entry.packaged} / ${entry.realDevice}. ${entry.evidence}`));
      item.append(details);
    }
    list.append(item);
  }

  section.append(heading, list);
  container.append(section);
}

const completeCount = tasks.filter((task) => task.status === "completed").length;
const deferredCount = tasks.filter((task) => task.status === "deferred").length;
const plannedCount = tasks.filter((task) => task.status === "planned").length;
const designOnlyCount = tasks.filter((task) => task.status === "design_only").length;
summary.textContent = `${tasks.length} roadmap tasks · ${completeCount} completed scoped checkpoints · ${deferredCount} deferred and incomplete · ${plannedCount} planned · ${designOnlyCount} design only · ${tasks.filter(task => task.status === "superseded").length} superseded · ${tasks.filter(task => task.status === "not_done").length} not done`;
const introTitle = document.querySelector("#task-page-title");
if (introTitle) introTitle.textContent = `Tasks 1-${Math.max(...tasks.map(task => task.number))}`;
const introStatus = document.querySelector("#task-page-status");
if (introStatus) introStatus.textContent = summary.textContent;
const nextTaskReason = recommendedOrder.find(item => item.number === nextTask?.number)?.reason;
if (nextTaskReason) textNode("p", nextTaskReason, nextPanel);

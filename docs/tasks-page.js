import { taskGroups, tasks } from "./tasks-data.mjs";

const container = document.querySelector("#roadmap-groups");
const summary = document.querySelector("#roadmap-summary");
const categoryIndex = document.querySelector("#category-index");

for (const group of [...taskGroups].reverse()) {
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
    const number = document.createElement("span");
    number.className = "task-number";
    number.textContent = String(task.number).padStart(2, "0");
    const title = document.createElement("span");
    title.className = "task-title";
    title.textContent = task.title;
    const status = document.createElement("span");
    status.className = `status status-${task.status === "completed" ? "complete" : "planned"}`;
    status.textContent = task.status === "completed" ? "Completed" : "Planned";
    const description = document.createElement("span");
    description.className = "task-description";
    description.textContent = task.description;
    item.append(number, title, status, description);
    list.append(item);
  }

  section.append(heading, list);
  container.append(section);
}

const completeCount = tasks.filter((task) => task.status === "completed").length;
summary.textContent = `${tasks.length} roadmap tasks · ${completeCount} completed milestones · ${tasks.length - completeCount} planned`;

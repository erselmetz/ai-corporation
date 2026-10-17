import { tasks, nextTask, recommendedOrder } from "./tasks-data.mjs";

export function renderTaskDirectory(list, taskRecords = tasks) {
  const document = list.ownerDocument;
  for (const task of [...taskRecords].sort((a, b) => b.number - a.number)) {
    const item = document.createElement("li");
    item.id = `task-${task.number}`;
    const link = document.createElement("a");
    link.href = `tasks.html#task-${task.number}`;
    link.textContent = `Task ${task.number}: ${task.title} — ${statusLabel(task.status)}`;
    item.append(link);
    list.append(item);
  }
}

export function statusLabel(status) {
  return status === "completed" ? "Completed"
    : status === "deferred" ? "Deferred — incomplete"
      : status === "design_only" ? "Design only"
        : "Planned";
}

export function renderStatusSummary(element, taskRecords = tasks) {
  const counts = Object.groupBy
    ? Object.groupBy(taskRecords, task => task.status)
    : taskRecords.reduce((groups, task) => ((groups[task.status] ??= []).push(task), groups), {});
  const complete = counts.completed?.length ?? 0;
  const deferred = counts.deferred?.length ?? 0;
  const planned = counts.planned?.length ?? 0;
  const designOnly = counts.design_only?.length ?? 0;
  element.textContent = `${taskRecords.length} tasks · ${complete} completed · ${deferred} deferred and incomplete · ${planned} planned · ${designOnly} design only`;
}

export function renderRecommendedOrder(list, taskRecords = tasks, order = recommendedOrder) {
  const document = list.ownerDocument;
  for (const entry of order) {
    const task = taskRecords.find(item => item.number === entry.number);
    if (!task) continue;
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = `tasks.html#task-${task.number}`;
    link.textContent = `Task ${task.number}: ${task.title}`;
    const reason = document.createElement("span");
    reason.textContent = ` — ${entry.reason}`;
    item.append(link, reason);
    list.append(item);
  }
}

if (typeof document !== "undefined") {
  const list = document.querySelector("#task-status-index");
  if (list) renderTaskDirectory(list);
  const summary = document.querySelector("#task-status-summary");
  if (summary) renderStatusSummary(summary);
  const order = document.querySelector("#recommended-order");
  if (order) renderRecommendedOrder(order);
  const latestTask = [...tasks].filter(task => task.status === "completed").sort((a, b) => b.number - a.number)[0];
  const latestNumber = document.querySelector("#latest-task-number");
  const latestTitle = document.querySelector("#latest-task-title");
  if (latestTask && latestNumber && latestTitle) {
    latestNumber.textContent = `Task ${latestTask.number}`;
    latestTitle.textContent = latestTask.title;
  }
  const next = nextTask;
  const nextNumber = document.querySelector("#next-task-number");
  const nextTitle = document.querySelector("#next-task-title");
  const nextDescription = document.querySelector("#next-task-description");
  if (next && nextNumber && nextTitle && nextDescription) {
    nextNumber.textContent = `Task ${next.number}`;
    nextTitle.textContent = next.title;
    nextDescription.textContent = next.description;
  }
}

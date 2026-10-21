import { tasks, nextTask, recommendedOrder } from "./tasks-data.mjs";

export function verificationLabels(task) {
  const automated = task.validation?.length
    ? "AI-verified (deterministic/fake evidence recorded)"
    : "AI verification: not recorded";
  const realWorld = task.realWorldVerification?.status === "verified"
    ? "Real hardware/live provider: verified"
    : task.realWorldVerification?.status === "partial"
      ? "Real hardware/live provider: partially verified"
      : "Real hardware/live provider: unverified";
  return { automated, realWorld };
}

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

export function renderLatestRoadmapRecords(container, taskRecords = tasks, limit = 2) {
  const document = container.ownerDocument;
  const recent = [...taskRecords].sort((a, b) => b.number - a.number).slice(0, limit);
  for (const task of recent) {
    const article = document.createElement("article");
    article.className = "roadmap-record";
    const link = document.createElement("a");
    link.href = `tasks.html#task-${task.number}`;
    link.textContent = `Task ${task.number}: ${task.title}`;
    const status = document.createElement("span");
    status.className = `status status-${task.status === "completed" ? "complete" : task.status === "deferred" ? "deferred" : "planned"}`;
    status.textContent = statusLabel(task.status);
    const description = document.createElement("p");
    description.textContent = task.description;
    const evidence = document.createElement("p");
    evidence.className = "verification-summary";
    const labels = verificationLabels(task);
    evidence.textContent = `${labels.automated} · ${labels.realWorld}`;
    article.append(link, status, description, evidence);
    container.append(article);
  }
}

export function renderLatestStatusCards(documentObject, taskRecords = tasks, upcomingTask = nextTask) {
  const latestTask = [...taskRecords].filter(task => task.status === "completed").sort((a, b) => b.number - a.number)[0];
  const latestNumber = documentObject.querySelector("#latest-task-number");
  const latestTitle = documentObject.querySelector("#latest-task-title");
  if (latestTask && latestNumber && latestTitle) {
    latestNumber.textContent = `Task ${latestTask.number}`;
    latestTitle.textContent = latestTask.title;
    const latestLink = documentObject.querySelector("#latest-task-link");
    if (latestLink) latestLink.href = `tasks.html#task-${latestTask.number}`;
  }
  const nextNumber = documentObject.querySelector("#next-task-number");
  const nextTitle = documentObject.querySelector("#next-task-title");
  const nextDescription = documentObject.querySelector("#next-task-description");
  if (upcomingTask && nextNumber && nextTitle && nextDescription) {
    nextNumber.textContent = `Task ${upcomingTask.number}`;
    nextTitle.textContent = upcomingTask.title;
    nextDescription.textContent = upcomingTask.description;
    const nextLink = documentObject.querySelector("#next-task-link");
    if (nextLink) nextLink.href = `tasks.html#task-${upcomingTask.number}`;
  } else if (nextNumber && nextTitle && nextDescription) {
    nextNumber.textContent = "No planned gate";
    nextTitle.textContent = "No planned task";
    nextDescription.textContent = "No task is currently marked planned in the authoritative roadmap.";
    const nextLink = documentObject.querySelector("#next-task-link");
    if (nextLink) {
      nextLink.href = "tasks.html";
      nextLink.textContent = "Browse task history";
    }
  }
  const taskCount = documentObject.querySelector("#all-task-count");
  if (taskCount) taskCount.textContent = `Tasks 1-${Math.max(...taskRecords.map(task => task.number))}`;
}

if (typeof document !== "undefined") {
  const list = document.querySelector("#task-status-index");
  if (list) renderTaskDirectory(list);
  const summary = document.querySelector("#task-status-summary");
  if (summary) renderStatusSummary(summary);
  const order = document.querySelector("#recommended-order");
  if (order) renderRecommendedOrder(order);
  const recentRecords = document.querySelector("#latest-roadmap-records");
  if (recentRecords) renderLatestRoadmapRecords(recentRecords);
  renderLatestStatusCards(document);
}

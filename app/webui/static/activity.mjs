import { mountTaskProgress } from "./task-progress.mjs";

const allowedLimits = new Set(["10", "25", "50", "100"]);

function validActivity(entry) {
  return Boolean(
    entry &&
    Number.isInteger(entry.id) &&
    typeof entry.task_id === "string" &&
    typeof entry.event === "string" &&
    typeof entry.created_at === "string",
  );
}

function validActivityList(payload) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    Array.isArray(payload.items) &&
    payload.items.every(validActivity),
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function errorMessage(status) {
  if (status === 401) return "Sign-in required. This browser session is not authenticated.";
  if (status === 403) return "Access denied. This account lacks the activity:read permission.";
  if (status === 400 || status === 422) {
    return "The Activity API rejected the limit or Task ID filter. Check the query and retry.";
  }
  return "Activity could not be loaded. Please retry.";
}

function renderActivity(documentRef, list, entries) {
  list.replaceChildren();
  for (const entry of entries) {
    const item = documentRef.createElement("li");
    item.className = "activity-item";
    const article = documentRef.createElement("article");
    article.className = "activity-entry";

    const heading = documentRef.createElement("h3");
    heading.textContent = entry.event;
    const metadata = documentRef.createElement("dl");
    metadata.className = "activity-metadata";
    for (const [label, value] of [
      ["Activity ID", String(entry.id)],
      ["Task ID", entry.task_id],
      ["Timestamp", entry.created_at],
    ]) {
      const row = documentRef.createElement("div");
      row.className = "activity-data-row";
      const term = documentRef.createElement("dt");
      term.textContent = label;
      const description = documentRef.createElement("dd");
      description.textContent = value;
      row.append(term, description);
      metadata.append(row);
    }
    article.append(heading, metadata);
    item.append(article);
    list.append(item);
  }
}

export function mountActivityPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
}) {
  const list = documentRef.getElementById("activity-list");
  const listState = documentRef.getElementById("activity-list-state");
  const refreshButton = documentRef.getElementById("activity-refresh");
  const limitInput = documentRef.getElementById("activity-limit");
  const taskIdInput = documentRef.getElementById("activity-task-id");
  let isLoading = false;
  mountTaskProgress({ documentRef, fetchImpl });

  async function loadActivity() {
    if (isLoading) return false;
    const limit = limitInput.value;
    if (!allowedLimits.has(limit)) {
      list.replaceChildren();
      setState(listState, "Choose a supported maximum from 10 to 100.", "error-state");
      return false;
    }
    const taskId = taskIdInput.value.trim();
    const query = new URLSearchParams({ limit });
    if (taskId) query.set("task_id", taskId);

    isLoading = true;
    refreshButton.disabled = true;
    refreshButton.textContent = "Loading…";
    list.replaceChildren();
    setState(listState, "Loading activity…");
    try {
      const response = await fetchImpl(`/api/activity?${query.toString()}`, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        setState(listState, errorMessage(response.status), "error-state");
        return false;
      }
      const payload = await response.json();
      if (!validActivityList(payload)) {
        setState(listState, "Activity response was invalid.", "error-state");
        return false;
      }
      if (payload.items.length === 0) {
        setState(listState, "No activity records were returned by the API.", "empty-state");
        return true;
      }
      renderActivity(documentRef, list, payload.items);
      const count = payload.items.length;
      setState(
        listState,
        `Loaded ${count} activity record${count === 1 ? "" : "s"} returned by the API (maximum requested: ${limit}).`,
        "success-state",
      );
      return true;
    } catch {
      setState(listState, "Activity could not be loaded. Please retry.", "error-state");
      return false;
    } finally {
      isLoading = false;
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh";
    }
  }

  refreshButton.addEventListener("click", () => void loadActivity());
  const initialLoad = loadActivity();
  return { initialLoad, loadActivity };
}

if (typeof document !== "undefined") {
  mountActivityPage();
}

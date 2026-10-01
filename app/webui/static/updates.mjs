function validUpdate(entry) {
  if (
    !entry ||
    typeof entry.date !== "string" ||
    typeof entry.type !== "string" ||
    typeof entry.title !== "string" ||
    typeof entry.summary !== "string" ||
    !entry.title.trim() ||
    !entry.summary.trim() ||
    !["development", "release"].includes(entry.type) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(entry.date)
  ) {
    return false;
  }
  const parsedDate = new Date(`${entry.date}T00:00:00Z`);
  return !Number.isNaN(parsedDate.valueOf()) &&
    parsedDate.toISOString().slice(0, 10) === entry.date;
}

function validUpdatesList(payload) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    Array.isArray(payload.items) &&
    payload.items.every(validUpdate),
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function errorMessage(status) {
  if (status === 401) return "Sign-in required. This browser session is not authenticated.";
  if (status === 403) return "Access denied. This account lacks the updates:read permission.";
  return "Updates could not be loaded. Please retry.";
}

function renderUpdates(documentRef, list, entries) {
  list.replaceChildren();
  for (const entry of entries) {
    const item = documentRef.createElement("li");
    item.className = "update-item";
    const article = documentRef.createElement("article");
    article.className = "update-entry";

    const heading = documentRef.createElement("h3");
    heading.textContent = entry.title;
    const metadata = documentRef.createElement("p");
    metadata.className = "update-metadata";
    const date = documentRef.createElement("time");
    date.dateTime = entry.date;
    date.textContent = entry.date;
    const kind = documentRef.createElement("span");
    kind.className = `update-kind update-kind-${entry.type}`;
    kind.textContent = entry.type === "release" ? "Release" : "Development update";
    metadata.append(date, kind);

    const summary = documentRef.createElement("p");
    summary.className = "update-summary";
    summary.textContent = entry.summary;
    article.append(metadata, heading, summary);
    item.append(article);
    list.append(item);
  }
}

export function mountUpdatesPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
}) {
  const list = documentRef.getElementById("updates-list");
  const listState = documentRef.getElementById("updates-list-state");
  const refreshButton = documentRef.getElementById("updates-refresh");
  let isLoading = false;

  async function loadUpdates() {
    if (isLoading) return false;
    isLoading = true;
    refreshButton.disabled = true;
    refreshButton.textContent = "Loading…";
    list.replaceChildren();
    setState(listState, "Loading updates…");
    try {
      const response = await fetchImpl("/api/updates", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        setState(listState, errorMessage(response.status), "error-state");
        return false;
      }
      const payload = await response.json();
      if (!validUpdatesList(payload)) {
        setState(listState, "Updates response was invalid.", "error-state");
        return false;
      }
      if (payload.items.length === 0) {
        setState(listState, "No updates have been recorded yet.", "empty-state");
        return true;
      }
      renderUpdates(documentRef, list, payload.items);
      const count = payload.items.length;
      setState(
        listState,
        `Loaded ${count} curated update${count === 1 ? "" : "s"}.`,
        "success-state",
      );
      return true;
    } catch {
      setState(listState, "Updates could not be loaded. Please retry.", "error-state");
      return false;
    } finally {
      isLoading = false;
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh";
    }
  }

  refreshButton.addEventListener("click", () => void loadUpdates());
  const initialLoad = loadUpdates();
  return { initialLoad, loadUpdates };
}

if (typeof document !== "undefined") {
  mountUpdatesPage();
}

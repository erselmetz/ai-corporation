function validDocumentSummary(document) {
  return Boolean(
    document &&
    typeof document.id === "string" &&
    document.id.length > 0 &&
    typeof document.title === "string" &&
    document.title.length > 0,
  );
}

function validDocumentList(payload) {
  if (
    !payload ||
    typeof payload !== "object" ||
    !Array.isArray(payload.items) ||
    !payload.items.every(validDocumentSummary)
  ) {
    return false;
  }
  return new Set(payload.items.map((item) => item.id)).size === payload.items.length;
}

function validDocument(payload, expectedId) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    payload.id === expectedId &&
    typeof payload.title === "string" &&
    payload.title.length > 0 &&
    typeof payload.content === "string",
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function errorMessage(status, detailRequest) {
  if (status === 401) {
    return "Sign-in required. This browser session is not authenticated.";
  }
  if (status === 403) {
    return "Access denied. This account lacks the documentation:read permission.";
  }
  if (status === 404 && detailRequest) {
    return "This document was not found. Refresh the list and try again.";
  }
  if (status === 400 || status === 422) {
    return "The Documentation API rejected the request.";
  }
  return detailRequest
    ? "The document could not be loaded. Please retry."
    : "The document list could not be loaded. Please retry.";
}

function renderDocumentList(documentRef, list, items, onSelect) {
  list.replaceChildren();
  for (const item of items) {
    const listItem = documentRef.createElement("li");
    const button = documentRef.createElement("button");
    button.type = "button";
    button.className = "record-select";
    button.textContent = item.title;
    button.addEventListener("click", () => void onSelect(item.id));
    listItem.append(button);
    list.append(listItem);
  }
}

export function mountDocumentationPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
}) {
  const list = documentRef.getElementById("documentation-list");
  const listState = documentRef.getElementById("documentation-list-state");
  const refreshButton = documentRef.getElementById("documentation-refresh");
  const detailState = documentRef.getElementById("documentation-detail-state");
  const contentTitle = documentRef.getElementById("documentation-content-title");
  const content = documentRef.getElementById("documentation-content");
  let isLoadingList = false;
  let detailRequestNumber = 0;

  function clearDocument() {
    contentTitle.textContent = "";
    contentTitle.hidden = true;
    content.textContent = "";
    content.hidden = true;
  }

  async function loadDocument(documentId) {
    const requestNumber = ++detailRequestNumber;
    clearDocument();
    setState(detailState, "Loading document…");
    try {
      const response = await fetchImpl(
        `/api/documentation/${encodeURIComponent(documentId)}`,
        {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        },
      );
      if (requestNumber !== detailRequestNumber) return false;
      if (!response.ok) {
        setState(detailState, errorMessage(response.status, true), "error-state");
        return false;
      }
      const payload = await response.json();
      if (requestNumber !== detailRequestNumber) return false;
      if (!validDocument(payload, documentId)) {
        setState(detailState, "The Documentation API returned an invalid document.", "error-state");
        return false;
      }
      contentTitle.textContent = payload.title;
      contentTitle.hidden = false;
      content.textContent = payload.content;
      content.hidden = false;
      setState(detailState, "Document loaded.", "success-state");
      return true;
    } catch {
      if (requestNumber === detailRequestNumber) {
        setState(
          detailState,
          "The document could not be loaded. Please retry.",
          "error-state",
        );
      }
      return false;
    }
  }

  async function loadDocuments() {
    if (isLoadingList) return false;
    isLoadingList = true;
    detailRequestNumber += 1;
    list.replaceChildren();
    clearDocument();
    setState(detailState, "Select a document to read it.");
    setState(listState, "Loading documents…");
    refreshButton.disabled = true;
    refreshButton.textContent = "Loading…";

    try {
      const response = await fetchImpl("/api/documentation", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        setState(listState, errorMessage(response.status, false), "error-state");
        return false;
      }
      const payload = await response.json();
      if (!validDocumentList(payload)) {
        setState(listState, "The Documentation API returned an invalid document list.", "error-state");
        return false;
      }
      if (payload.items.length === 0) {
        setState(listState, "No documentation documents were returned by the API.", "empty-state");
        return true;
      }
      renderDocumentList(documentRef, list, payload.items, loadDocument);
      setState(
        listState,
        `Loaded ${payload.items.length} document${payload.items.length === 1 ? "" : "s"} returned by the API.`,
        "success-state",
      );
      return true;
    } catch {
      setState(listState, errorMessage(0, false), "error-state");
      return false;
    } finally {
      isLoadingList = false;
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh";
    }
  }

  refreshButton.addEventListener("click", () => void loadDocuments());
  const initialLoad = loadDocuments();
  return { initialLoad, loadDocuments, loadDocument };
}

if (typeof document !== "undefined") {
  mountDocumentationPage();
}

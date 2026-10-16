export function mountOwnerKnowledge({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
                                     confirmImpl = message => globalThis.confirm(message),
                                     now = () => new Date() } = {}) {
  const el = id => documentRef.getElementById(id);
  const state = el("knowledge-state"), indexState = el("knowledge-index-status");
  const list = el("knowledge-list"), detail = el("knowledge-detail");
  let ownerId = null, selected = null, semanticAvailable = false, busy = false;
  async function session() {
    const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error(response.status === 401 ? "Sign in to manage private notes." : "Owner session is unavailable.");
    return response.json();
  }
  async function request(path, { method = "GET", body, formData } = {}) {
    const options = { method, credentials: "same-origin", cache: "no-store" };
    if (method !== "GET") {
      const auth = await session();
      options.headers = { "X-Local-CSRF": auth.csrf };
      if (formData) options.body = formData;
      else {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body ?? {});
      }
    }
    const response = await fetchImpl(path, options);
    if (response.status === 204) return null;
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Knowledge request failed.");
    return result;
  }
  function setBusy(value) {
    busy = value;
    for (const id of ["knowledge-save", "knowledge-upload", "knowledge-refresh", "knowledge-index", "knowledge-inspect", "knowledge-delete"]) {
      const button = el(id);
      if (button) button.disabled = value || (["knowledge-index", "knowledge-inspect"].includes(id) && (!selected || !semanticAvailable)) || (id === "knowledge-delete" && !selected);
    }
  }
  function clearSelection() {
    selected = null;
    el("knowledge-index").disabled = true;
    el("knowledge-inspect").disabled = true;
    el("knowledge-delete").disabled = true;
    detail.textContent = "Select a note to inspect its index or remove it.";
  }
  function renderItems(items) {
    list.replaceChildren();
    for (const item of items) {
      const row = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.textContent = `${item.source_reference || "Owner note"} · expires ${item.expires_at}`;
      button.addEventListener("click", () => {
        selected = item;
        el("knowledge-index").disabled = busy || !semanticAvailable;
        el("knowledge-inspect").disabled = busy || !semanticAvailable;
        el("knowledge-delete").disabled = busy;
        detail.textContent = `Selected ${item.source_reference || "owner note"}. Expiry is enforced on every retrieval.`;
      });
      row.append(button);
      list.append(row);
    }
    if (!items.length) {
      const empty = documentRef.createElement("li");
      empty.textContent = "No saved notes yet.";
      list.append(empty);
    }
  }
  async function refresh() {
    if (busy) return;
    setBusy(true);
    try {
      const data = await request("/api/memory/owner");
      ownerId = data.scope_id;
      if (data.scope !== "owner" || !Array.isArray(data.items)) throw new Error("Invalid private knowledge response.");
      semanticAvailable = data.semantic?.state === "configured";
      indexState.textContent = semanticAvailable
        ? `Local semantic index available (${data.semantic.model || "local model"}). Indexing runs only when you request it; notes remain searchable lexically.`
        : `Local semantic index ${data.semantic?.state || "unknown"}: ${data.semantic?.detail || "status unavailable"} Lexical retrieval remains available.`;
      renderItems(data.items.filter(item => item.scope === "owner" && item.scope_id === ownerId));
      if (selected && !data.items.some(item => item.id === selected.id)) clearSelection();
      else if (selected) {
        selected = data.items.find(item => item.id === selected.id);
        el("knowledge-index").disabled = busy || !semanticAvailable;
        el("knowledge-inspect").disabled = busy || !semanticAvailable;
        el("knowledge-delete").disabled = busy;
      }
      state.textContent = `Loaded ${data.items.length} private note${data.items.length === 1 ? "" : "s"}.`;
    } catch (error) {
      state.textContent = error.message;
    } finally { setBusy(false); }
  }
  async function saveNote(event) {
    event?.preventDefault();
    if (busy) return;
    const content = el("knowledge-content").value;
    if (!content.trim()) { state.textContent = "Enter note text first."; return; }
    if (!el("knowledge-consent").checked) { state.textContent = "Confirm local retention consent first."; return; }
    setBusy(true);
    try {
      const expiresAt = new Date(now().getTime() + Number(el("knowledge-expiry").value) * 86400000).toISOString();
      const result = await request("/api/memory/owner", { method: "POST", body: {
        content, source_name: el("knowledge-source").value || "Owner note",
        expires_at: expiresAt, retention_opt_in: true,
      } });
      el("knowledge-content").value = "";
      el("knowledge-consent").checked = false;
      detail.textContent = `Saved ${result.source_reference}. It expires ${result.expires_at}.`;
      state.textContent = "Private note saved locally.";
      selected = { id: result.id };
      await refreshAfterAction();
    } catch (error) { state.textContent = error.message; }
    finally { setBusy(false); }
  }
  async function upload(event) {
    event?.preventDefault();
    if (busy) return;
    const file = el("knowledge-file").files?.[0];
    if (!file) { state.textContent = "Choose a .md, .txt, or .pdf file."; return; }
    if (file.size > 1_048_576) { state.textContent = "File exceeds the 1 MiB limit."; return; }
    if (!el("knowledge-consent").checked) { state.textContent = "Confirm local retention consent first."; return; }
    setBusy(true);
    try {
      const auth = await session(); ownerId = auth.identity;
      const formData = new FormData(); formData.append("file", file, file.name);
      const expiry = new Date(now().getTime() + Number(el("knowledge-expiry").value) * 86400000).toISOString();
      const query = new URLSearchParams({ expires_at: expiry, retention_opt_in: "true" });
      const result = await request(`/api/memory/owner/upload?${query}`, { method: "POST", formData });
      el("knowledge-file").value = ""; el("knowledge-consent").checked = false;
      selected = { id: result.id };
      state.textContent = `Added ${result.source_reference} as private local knowledge.`;
      await refreshAfterAction();
    } catch (error) { state.textContent = error.message; }
    finally { setBusy(false); }
  }
  async function refreshAfterAction() {
    const data = await request("/api/memory/owner");
    ownerId = data.scope_id; semanticAvailable = data.semantic?.state === "configured";
    indexState.textContent = semanticAvailable
      ? `Local semantic index available (${data.semantic.model || "local model"}); lexical retrieval is always available.`
      : `Local semantic index ${data.semantic?.state || "unknown"}: ${data.semantic?.detail || "status unavailable"} Lexical retrieval remains available.`;
    renderItems(data.items);
    if (selected) {
      selected = data.items.find(item => item.id === selected.id) || null;
      el("knowledge-index").disabled = !selected || !semanticAvailable;
      el("knowledge-inspect").disabled = !selected || !semanticAvailable;
      el("knowledge-delete").disabled = !selected;
    }
  }
  async function indexSelected() {
    if (busy || !selected || !semanticAvailable) return;
    setBusy(true); detail.textContent = "Building local index… this bounded operation runs synchronously. No model is downloaded.";
    try {
      const result = await request("/api/memory/semantic/index", { method: "POST", body: {
        scope: "owner", scope_id: ownerId, memory_id: selected.id,
      } });
      detail.textContent = `Index built at ${result.indexed_at || "time not reported"}: ${result.chunk_count} chunks. Local embedding model: ${result.model || "unknown"}.`;
      state.textContent = "Local semantic index updated.";
    } catch (error) { detail.textContent = error.message; }
    finally { setBusy(false); }
  }
  async function inspectIndex() {
    if (busy || !selected || !semanticAvailable) return;
    setBusy(true); detail.textContent = "Checking current index status…";
    try {
      const result = await request("/api/memory/semantic/inspect", { method: "POST", body: {
        scope: "owner", scope_id: ownerId, memory_ids: [selected.id],
      } });
      const source = result.sources?.[0];
      detail.textContent = source
        ? `Index ${source.state}; ${source.indexed_chunks} chunks; last built ${source.indexed_at || "unknown"}. ${source.detail}`
        : "Index status is unknown; refresh and retry.";
    } catch (error) { detail.textContent = error.message; }
    finally { setBusy(false); }
  }
  async function removeSelected() {
    if (busy || !selected || !confirmImpl("Forget this private note and invalidate its derived index?")) return;
    setBusy(true);
    try {
      const query = new URLSearchParams({ scope: "owner", scope_id: ownerId, memory_id: selected.id });
      await request(`/api/memory/record?${query}`, { method: "DELETE" });
      selected = null; await refreshAfterAction(); clearSelection();
      detail.textContent = "Note removed. Its derived local index was invalidated.";
      state.textContent = "Private note forgotten.";
    } catch (error) { detail.textContent = error.message; }
    finally { setBusy(false); }
  }
  el("knowledge-note-form").addEventListener("submit", event => void saveNote(event));
  el("knowledge-upload-form").addEventListener("submit", event => void upload(event));
  el("knowledge-refresh").addEventListener("click", () => void refresh());
  el("knowledge-index").addEventListener("click", () => void indexSelected());
  el("knowledge-inspect").addEventListener("click", () => void inspectIndex());
  el("knowledge-delete").addEventListener("click", () => void removeSelected());
  void refresh();
  return { refresh };
}

if (globalThis.document?.getElementById("knowledge-note-form")) mountOwnerKnowledge();

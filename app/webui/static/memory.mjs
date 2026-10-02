const scopes = new Set(["conversation", "project", "corporation"]);
function validSummary(item) {
  return item && typeof item.id === "string" && scopes.has(item.scope)
    && typeof item.scope_id === "string" && typeof item.type === "string"
    && typeof item.expires_at === "string" && Number.isFinite(Date.parse(item.expires_at))
    && typeof item.expired === "boolean" && typeof item.can_manage === "boolean";
}
function failure(status) {
  return status === 401 ? "Sign-in required."
    : status === 403 ? "Access denied: memory permission or owner authority required."
    : status === 404 ? "Memory unavailable in this identity and scope."
    : status === 409 ? "Memory changed or publication is immutable. Reload before retrying."
    : status === 410 ? "Memory has expired. Its content is unavailable."
    : status === 422 ? "Memory validation failed. Check content, consent, and expiry."
    : "Memory service failed. Please retry.";
}
export function mountMemoryPage({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
                                  confirmImpl = message => globalThis.confirm(message) }) {
  const el = id => documentRef.getElementById(id);
  const list = el("memory-list"), state = el("memory-state"), detail = el("memory-detail-state");
  let selected = null, revision = 0, busy = false;
  function clearDetail() {
    selected = null;
    el("memory-content").value = "";
    el("memory-expiry").value = "";
    el("memory-consent").checked = false;
    for (const id of ["memory-content", "memory-expiry", "memory-consent"]) el(id).disabled = true;
    el("memory-save").disabled = true;
    el("memory-remove").disabled = true;
    detail.textContent = "Select a memory record.";
  }
  function query(item, withId = true) {
    const params = new URLSearchParams({ scope: item.scope, scope_id: item.scope_id });
    if (withId) params.set("memory_id", item.id);
    return params.toString();
  }
  async function select(item) {
    if (busy) return false;
    const token = ++revision;
    clearDetail();
    if (!validSummary(item)) return false;
    if (item.expired) {
      selected = item;
      detail.textContent = "Expired: content is unavailable. The owner can remove this record.";
      el("memory-remove").disabled = !item.can_manage;
      return true;
    }
    detail.textContent = "Loading memory…";
    try {
      const response = await fetchImpl(`/api/memory/record?${query(item)}`, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (token !== revision) return false;
      if (!response.ok) { detail.textContent = failure(response.status); return false; }
      const data = await response.json();
      if (token !== revision) return false;
      if (!validSummary(data) || data.id !== item.id || data.scope !== item.scope || data.scope_id !== item.scope_id
          || typeof data.content !== "string" || typeof data.revision !== "string" || data.revision.length !== 64
          || typeof data.source_id !== "string" || typeof data.source_scope_id !== "string" || typeof data.source_reference !== "string") {
        detail.textContent = "Memory response was invalid."; return false;
      }
      selected = data;
      el("memory-content").value = data.content;
      el("memory-expiry").value = data.expires_at;
      const editable = data.can_manage && data.scope !== "corporation";
      el("memory-content").disabled = !editable;
      el("memory-expiry").disabled = !editable;
      el("memory-consent").disabled = !editable;
      el("memory-save").disabled = !editable;
      el("memory-remove").disabled = !data.can_manage;
      detail.textContent = `Source memory/reference: ${data.source_id}; scope resource: ${data.source_scope_id}; original reference: ${data.source_reference}. `
        + (data.scope === "corporation" ? "Published snapshot: correction or new retention requires withdrawal and explicit republication through the application service." : "Owner correction preserves source IDs; explicit consent and expiry are required.");
      return true;
    } catch { if (token === revision) detail.textContent = "Memory service failed. Please retry."; return false; }
  }
  async function load() {
    if (busy) return false;
    const token = ++revision;
    clearDetail(); list.replaceChildren();
    const scope = el("memory-scope").value, scopeId = el("memory-scope-id").value.trim();
    if (!scopes.has(scope) || !scopeId) { state.textContent = "Choose a scope and enter its resource ID."; return false; }
    state.textContent = "Loading memory…";
    try {
      const response = await fetchImpl(`/api/memory?${query({ scope, scope_id: scopeId }, false)}&limit=50`, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (token !== revision) return false;
      if (!response.ok) { state.textContent = failure(response.status); return false; }
      const data = await response.json();
      if (token !== revision) return false;
      if (!data || !Array.isArray(data.items) || !data.items.every(item => validSummary(item) && item.scope === scope && item.scope_id === scopeId)) {
        state.textContent = "Memory response was invalid."; return false;
      }
      for (const item of data.items) {
        const row = documentRef.createElement("li"), button = documentRef.createElement("button");
        button.type = "button";
        button.textContent = `${item.id} · ${item.type} · ${item.expired ? "expired" : item.expires_at}`;
        button.addEventListener("click", () => void select(item));
        row.append(button); list.append(row);
      }
      state.textContent = data.items.length ? `Loaded ${data.items.length} records (maximum 50; this is not a complete history).` : "No accessible memory records returned for this scope.";
      return true;
    } catch { if (token === revision) state.textContent = "Memory service failed. Please retry."; return false; }
  }
  async function save() {
    if (busy || !selected?.can_manage || selected.expired || selected.scope === "corporation") return false;
    const item = selected;
    busy = true; el("memory-save").disabled = true; el("memory-remove").disabled = true;
    let error = null;
    try {
      const response = await fetchImpl(`/api/memory/record?${query(item)}`, {
        method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ content: el("memory-content").value, expires_at: el("memory-expiry").value,
                               retention_opt_in: el("memory-consent").checked === true, revision: item.revision }),
      });
      if (!response.ok) error = failure(response.status);
    } catch { error = "Memory service failed. Please retry."; }
    finally { busy = false; }
    await load();
    detail.textContent = error ?? "Memory correction/retention saved. Select the record to inspect current data.";
    return !error;
  }
  async function remove() {
    if (busy || !selected?.can_manage || !confirmImpl("Remove this memory? For published knowledge, this withdraws all reader access.")) return false;
    const item = selected;
    busy = true; el("memory-save").disabled = true; el("memory-remove").disabled = true;
    let error = null;
    try {
      const response = await fetchImpl(`/api/memory/record?${query(item)}`, { method: "DELETE", credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) error = failure(response.status);
    } catch { error = "Memory service failed. Please retry."; }
    finally { busy = false; }
    await load();
    detail.textContent = error ?? "Memory removed.";
    return !error;
  }
  el("memory-refresh").addEventListener("click", () => void load());
  el("memory-save").addEventListener("click", () => void save());
  el("memory-remove").addEventListener("click", () => void remove());
  for (const id of ["memory-scope", "memory-scope-id"]) el(id).addEventListener("input", () => {
    if (busy) return;
    ++revision; list.replaceChildren(); clearDetail(); state.textContent = "Scope changed. Refresh to load current records.";
  });
  clearDetail();
  return { load, select, save, remove };
}
if (typeof document !== "undefined") mountMemoryPage();

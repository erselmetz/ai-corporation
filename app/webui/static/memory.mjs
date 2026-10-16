const scopes = new Set(["owner", "conversation", "project", "corporation"]);
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
    : status === 503 ? "The optional local semantic capability is unavailable or could not complete the request."
    : "Memory service failed. Please retry.";
}
export function mountMemoryPage({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
                                  confirmImpl = message => globalThis.confirm(message),
                                  now = () => new Date() } = {}) {
  const el = id => documentRef.getElementById(id);
  const list = el("memory-list"), state = el("memory-state"), detail = el("memory-detail-state");
  let selected = null, revision = 0, busy = false;
  let semanticConfigured = false;
  let loadedScope = null;
  let listedItems = [];
  let retrievalHits = [];
  let searchRevision = 0;
  let freshness = new Map();
  function clearDetail() {
    selected = null;
    el("memory-content").value = "";
    el("memory-expiry").value = "";
    el("memory-consent").checked = false;
    for (const id of ["memory-content", "memory-expiry", "memory-consent"]) el(id).disabled = true;
    el("memory-save").disabled = true;
    el("memory-remove").disabled = true;
    if (el("semantic-index")) el("semantic-index").disabled = true;
    detail.textContent = "Select a memory record.";
  }
  function query(item, withId = true) {
    const params = new URLSearchParams({ scope: item.scope, scope_id: item.scope_id });
    if (withId) params.set("memory_id", item.id);
    return params.toString();
  }
  function renderRelationships() {
    const root = el("memory-map-root"), list = el("memory-relationship-list"), mapState = el("memory-map-state");
    root.replaceChildren(); list.replaceChildren();
    if (!loadedScope) {
      mapState.textContent = "Choose a scope and refresh to load its authorized records.";
      return;
    }
    const { scope, scope_id: scopeId } = loadedScope;
    const rootNode = documentRef.createElement("p");
    rootNode.className = "memory-map-root-node";
    rootNode.textContent = `Selected ${scope} scope: ${scopeId} · ${listedItems.length} records in this authorized response`;
    root.append(rootNode);
    mapState.textContent = `Showing only the ${scope} scope ${scopeId}. The API does not provide a source snapshot timestamp; refresh to recheck current records.`;
    const hitsById = new Map(retrievalHits.map(hit => [hit.memory_id, hit]));
    const shown = new Set();
    for (const item of listedItems) {
      if (!validSummary(item) || item.scope !== scope || item.scope_id !== scopeId) continue;
      shown.add(item.id);
      const row = documentRef.createElement("li");
      row.className = "memory-map-node";
      const inspect = documentRef.createElement("button");
      inspect.type = "button";
      inspect.textContent = `Inspect ${item.type} ${item.id}`;
      inspect.addEventListener("click", () => void select(item));
      row.append(inspect);
      const relation = documentRef.createElement("p");
      relation.textContent = `Recorded in selected ${scope} scope · ${item.expired ? "expired metadata; content unavailable" : `expires ${item.expires_at}`}.`;
      row.append(relation);
      if (item.provenance) {
        const provenance = documentRef.createElement("p");
        const source = item.provenance;
        provenance.textContent = `Recorded provenance: ${source.source_scope}:${source.source_scope_id} / ${source.source_reference}; ${source.source_created_at ? `source created ${source.source_created_at}.` : "source creation time is unavailable."}`;
        row.append(provenance);
      }
      const hit = hitsById.get(item.id);
      if (hit) appendRetrievalMatch(row, hit);
      list.append(row);
    }
    for (const hit of retrievalHits) {
      if (!shown.has(hit.memory_id)) {
        const row = documentRef.createElement("li");
        row.className = "memory-map-node";
        row.append(makeInspectButton(hit));
        appendRetrievalMatch(row, hit);
        list.append(row);
      }
    }
    if (!listedItems.length && !retrievalHits.length) {
      const empty = documentRef.createElement("li");
      empty.textContent = "No authorized records were returned for this exact scope.";
      list.append(empty);
    }
  }
  function makeInspectButton(hit) {
    const button = documentRef.createElement("button");
    button.type = "button";
    button.textContent = `Inspect retrieved record ${hit.memory_id}`;
    button.addEventListener("click", () => void select({ id: hit.memory_id, scope: hit.scope, scope_id: hit.scope_id,
      type: "retrieved record", expires_at: hit.expires_at, expired: false, can_manage: false }));
    return button;
  }
  function appendRetrievalMatch(row, hit) {
    const match = documentRef.createElement("p");
    match.textContent = `Semantic retrieval match · chunk ${hit.chunk_position + 1} · relevance ${hit.relevance.toFixed(3)} (ranking hint, not confidence or proof) · source ${hit.source_reference}.`;
    row.append(match);
    const verify = documentRef.createElement("button");
    verify.type = "button";
    verify.textContent = "Recheck source freshness";
    verify.addEventListener("click", () => verifyHit(hit));
    row.append(verify);
    const state = documentRef.createElement("p");
    const key = `${hit.scope}\u0000${hit.scope_id}\u0000${hit.memory_id}`;
    state.textContent = freshness.get(key) ?? `Retrieved source revision ${hit.revision.slice(0, 12)}… · not rechecked since search.`;
    state.dataset.testid = "memory-hit-freshness";
    row.append(state);
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
      renderRelationships();
      return true;
    }
    detail.textContent = "Loading memory…";
    try {
      const response = await fetchImpl(`/api/memory/record?${query(item)}`, { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
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
      if (el("semantic-index")) el("semantic-index").disabled = !semanticConfigured || !data.can_manage || data.expired;
      detail.textContent = `Source memory/reference: ${data.source_id}; scope resource: ${data.source_scope_id}; original reference: ${data.source_reference}. `
        + (data.scope === "corporation" ? "Published snapshot: correction or new retention requires withdrawal and explicit republication through the application service." : "Owner correction preserves source IDs; explicit consent and expiry are required.");
      if (loadedScope?.scope === data.scope && loadedScope.scope_id === data.scope_id) {
        const entry = listedItems.find(value => value.id === data.id);
        if (entry) entry.provenance = { source_scope: data.source_scope, source_scope_id: data.source_scope_id,
          source_reference: data.source_reference, source_created_at: null };
      }
      renderRelationships();
      return true;
    } catch { if (token === revision) detail.textContent = "Memory service failed. Please retry."; return false; }
  }
  async function load() {
    if (busy) return false;
    const token = ++revision;
    clearDetail(); list.replaceChildren();
    ++searchRevision; loadedScope = null; listedItems = []; retrievalHits = []; freshness.clear(); renderRelationships();
    const scope = el("memory-scope").value, scopeId = el("memory-scope-id").value.trim();
    if (!scopes.has(scope) || !scopeId) { loadedScope = null; listedItems = []; retrievalHits = []; renderRelationships(); state.textContent = "Choose a scope and enter its resource ID."; return false; }
    state.textContent = "Loading memory…";
    try {
      const response = await fetchImpl(`/api/memory?${query({ scope, scope_id: scopeId }, false)}&limit=50`, { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
      if (token !== revision) return false;
      if (!response.ok) { state.textContent = failure(response.status); return false; }
      const data = await response.json();
      if (token !== revision) return false;
      if (!data || !Array.isArray(data.items) || !data.items.every(item => validSummary(item) && item.scope === scope && item.scope_id === scopeId)) {
        state.textContent = "Memory response was invalid."; return false;
      }
      loadedScope = { scope, scope_id: scopeId };
      listedItems = data.items;
      retrievalHits = [];
      freshness.clear();
      for (const item of data.items) {
        const row = documentRef.createElement("li"), button = documentRef.createElement("button");
        button.type = "button";
        button.textContent = `${item.id} · ${item.type} · ${item.expired ? "expired" : item.expires_at}`;
        button.addEventListener("click", () => void select(item));
        row.append(button); list.append(row);
      }
      state.textContent = data.items.length ? `Loaded ${data.items.length} records (maximum 50; this is not a complete history).` : "No accessible memory records returned for this scope.";
      renderRelationships();
      return true;
    } catch { if (token === revision) { loadedScope = null; listedItems = []; retrievalHits = []; renderRelationships(); state.textContent = "Memory service failed. Please retry."; } return false; }
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
  async function localCsrf() {
    const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error("Owner session is unavailable");
    const session = await response.json();
    if (!session || typeof session.csrf !== "string" || !session.csrf) throw new Error("Owner session is unavailable");
    return session.csrf;
  }
  async function refreshSemantic() {
    const status = el("semantic-memory-status");
    if (!status) return false;
    status.textContent = "Checking local semantic capability…";
    try {
      const response = await fetchImpl("/api/memory/semantic/status", { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) { status.textContent = failure(response.status); semanticConfigured = false; return false; }
      const data = await response.json();
      if (!data || !["disabled", "unavailable", "configured"].includes(data.state) || typeof data.detail !== "string") {
        status.textContent = "Semantic capability response was invalid."; semanticConfigured = false; return false;
      }
      semanticConfigured = data.state === "configured";
      status.textContent = `${data.state === "configured" ? `Configured locally${data.model ? ` (${data.model})` : ""}.` : `${data.state}.`} ${data.detail}`;
      if (el("semantic-index")) el("semantic-index").disabled = !semanticConfigured || !selected?.can_manage || selected.expired;
      if (el("semantic-search")) el("semantic-search").disabled = !semanticConfigured;
      return true;
    } catch { status.textContent = "Could not check the local semantic capability."; semanticConfigured = false; return false; }
  }
  async function indexSelected() {
    if (!semanticConfigured || !selected?.can_manage || selected.expired || busy) return false;
    const item = selected, state = el("semantic-search-state");
    state.textContent = "Indexing this selected record locally…";
    try {
      const csrf = await localCsrf();
      const response = await fetchImpl("/api/memory/semantic/index", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf, Accept: "application/json" },
        body: JSON.stringify({ scope: item.scope, scope_id: item.scope_id, memory_id: item.id }),
      });
      if (!response.ok) { state.textContent = failure(response.status); return false; }
      const data = await response.json();
      if (selected?.id !== item.id || data?.indexed !== true || !Number.isInteger(data.chunk_count)) return false;
      state.textContent = `Indexed ${data.chunk_count} chunk${data.chunk_count === 1 ? "" : "s"} locally. No generation or Task execution occurred.`;
      return true;
    } catch { state.textContent = "Local indexing failed. Check the optional model setup and retry."; return false; }
  }
  async function searchSemantic() {
    if (!semanticConfigured || busy) return false;
    const scope = el("memory-scope").value, scopeId = el("memory-scope-id").value.trim();
    const queryText = el("semantic-query").value.trim(), state = el("semantic-search-state"), results = el("semantic-results");
    const token = ++searchRevision;
    const scopeToken = revision;
    retrievalHits = [];
    results.replaceChildren();
    renderRelationships();
    if (!scopes.has(scope) || !scopeId || !queryText || loadedScope?.scope !== scope || loadedScope?.scope_id !== scopeId) { state.textContent = "Load this exact scope before searching; enter a query and refresh the selected scope."; renderRelationships(); return false; }
    state.textContent = "Searching the selected scope…";
    try {
      const csrf = await localCsrf();
      const response = await fetchImpl("/api/memory/semantic/search", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf, Accept: "application/json" },
        body: JSON.stringify({ query: queryText, scope, scope_id: scopeId, limit: 5 }),
      });
      if (token !== searchRevision || scopeToken !== revision || el("memory-scope").value !== scope || el("memory-scope-id").value.trim() !== scopeId) return false;
      if (!response.ok) { state.textContent = failure(response.status); return false; }
      const data = await response.json();
      if (!data || !Array.isArray(data.items) || !data.items.every(hit => hit && typeof hit.memory_id === "string"
          && hit.scope === scope && hit.scope_id === scopeId && typeof hit.revision === "string" && /^[a-f0-9]{64}$/i.test(hit.revision)
          && typeof hit.expires_at === "string" && Number.isFinite(Date.parse(hit.expires_at))
          && typeof hit.excerpt === "string" && typeof hit.source_reference === "string"
          && Number.isInteger(hit.chunk_position) && hit.chunk_position >= 0 && Number.isFinite(hit.relevance))) {
        state.textContent = "Semantic search response was invalid."; return false;
      }
      retrievalHits = data.items;
      for (const hit of data.items) {
        const row = documentRef.createElement("li");
        row.textContent = `${hit.memory_id} · ${hit.source_reference} · chunk ${hit.chunk_position + 1} · relevance ${hit.relevance.toFixed(3)} — ${hit.excerpt}`;
        results.append(row);
      }
      state.textContent = data.items.length
        ? `${data.items.length} authorized results${data.candidate_limit_reached ? " (candidate limit reached; more results may exist)" : ""}. Similarity is a relevance hint, not a confidence guarantee.`
        : `No current result in the bounded candidate set${data.candidate_limit_reached ? " (candidate limit reached; more results may exist)" : ""}.`;
      renderRelationships();
      return true;
    } catch { if (token === searchRevision && scopeToken === revision) state.textContent = "Local semantic search failed."; return false; }
  }
  async function verifyHit(hit) {
    const scopeToken = revision;
    const key = `${hit.scope}\u0000${hit.scope_id}\u0000${hit.memory_id}`;
    freshness.set(key, "Checking current source revision…");
    renderRelationships();
    try {
      const response = await fetchImpl(`/api/memory/record?${query({ scope: hit.scope, scope_id: hit.scope_id, id: hit.memory_id })}`,
        { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
      if (scopeToken !== revision || loadedScope?.scope !== hit.scope || loadedScope?.scope_id !== hit.scope_id) return false;
      if (!response.ok) {
        freshness.set(key, response.status === 410 ? "Expired since search; content is unavailable." : failure(response.status));
      } else {
        const data = await response.json();
        if (scopeToken !== revision || loadedScope?.scope !== hit.scope || loadedScope?.scope_id !== hit.scope_id) return false;
        if (!validSummary(data) || data.id !== hit.memory_id || data.scope !== hit.scope || data.scope_id !== hit.scope_id
            || typeof data.revision !== "string" || !/^[a-f0-9]{64}$/i.test(data.revision)) {
          freshness.set(key, "Source recheck returned invalid metadata; current revision is unknown.");
        } else if (data.expired) {
          freshness.set(key, "Source is expired; content is unavailable.");
        } else {
          freshness.set(key, data.revision === hit.revision
            ? `Source revision is current at recheck (${now().toISOString()}).`
            : `Source changed since retrieval (${now().toISOString()}); search result may be stale.`);
        }
      }
      renderRelationships();
      return true;
    } catch {
      if (scopeToken === revision) { freshness.set(key, "Source recheck failed; freshness is unknown."); renderRelationships(); }
      return false;
    }
  }
  el("memory-refresh").addEventListener("click", () => void load());
  el("memory-save").addEventListener("click", () => void save());
  el("memory-remove").addEventListener("click", () => void remove());
  for (const id of ["memory-scope", "memory-scope-id"]) el(id).addEventListener("input", () => {
    if (busy) return;
    ++revision; ++searchRevision; loadedScope = null; listedItems = []; retrievalHits = []; freshness.clear();
    list.replaceChildren(); clearDetail(); state.textContent = "Scope changed. Refresh to load current records."; renderRelationships();
    if (el("semantic-results")) el("semantic-results").replaceChildren();
    if (el("semantic-search-state")) el("semantic-search-state").textContent = "Scope changed. Search results cleared.";
  });
  if (el("semantic-index")) el("semantic-index").addEventListener("click", () => void indexSelected());
  if (el("semantic-search")) el("semantic-search").addEventListener("click", () => void searchSemantic());
  if (el("semantic-query")) el("semantic-query").addEventListener("input", () => {
    ++searchRevision; retrievalHits = []; freshness.clear();
    if (el("semantic-results")) el("semantic-results").replaceChildren();
    if (el("semantic-search-state")) el("semantic-search-state").textContent = "Query changed. Search this exact scope again.";
    renderRelationships();
  });
  if (el("semantic-memory-status")) void refreshSemantic();
  clearDetail();
  return { load, select, save, remove, refreshSemantic, indexSelected, searchSemantic, verifyHit, renderRelationships };
}
if (typeof document !== "undefined") mountMemoryPage();

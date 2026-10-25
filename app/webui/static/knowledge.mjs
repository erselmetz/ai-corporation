import { mountBrainView } from "./brain-view.mjs";

export function mountOwnerKnowledge({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
                                     confirmImpl = message => globalThis.confirm(message),
                                     now = () => new Date(), windowRef = globalThis.window, brainView: brainViewOverride = null } = {}) {
  const el = id => documentRef.getElementById(id);
  const brainView = brainViewOverride || mountBrainView({ documentRef, fetchImpl, sessionStorage: windowRef?.sessionStorage });
  const state = el("knowledge-state"), indexState = el("knowledge-index-status");
  const list = el("knowledge-list"), detail = el("knowledge-detail");
  let ownerId = null, selected = null, semanticAvailable = false, busy = false;
  let legacyBrainFile = null, legacyBrainPlan = null;
  const MAX_FILES_PER_BATCH = 25;
  const ALLOWED_EXTENSIONS = new Set(".txt .md .pdf .docx .csv .py .js .mjs .cjs .ts .tsx .jsx .json .html .htm .css .scss .yaml .yml .toml .ini .xml .sql .sh .ps1 .bat .java .c .h .cpp .hpp .go .rs .rb .php .cs .kt .swift .vue .svelte .mdx .rst .log".split(" "));
  const statusList = el("brain-ingestion-list");
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
    const preview = el("v3code-brain-preview"), commit = el("v3code-brain-import");
    if (preview) preview.disabled = value || !legacyBrainFile;
    if (commit) commit.disabled = value || !legacyBrainFile || !legacyBrainPlan;
  }
  function stagedRow(file) {
    const row = documentRef.createElement("li");
    const title = documentRef.createElement("strong");
    title.textContent = file.webkitRelativePath || file.name || "Selected file";
    const stage = documentRef.createElement("span");
    stage.textContent = "Queued";
    row.append(title, documentRef.createTextNode(" — "), stage);
    statusList?.append(row);
    const nodeId = `ingest:${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`}`;
    const label = file.webkitRelativePath || file.name || "Selected file";
    return next => {
      stage.textContent = next;
      const state = next.startsWith("Ready") ? "ready" : next.startsWith("Failed") ? "failed"
        : next.toLowerCase().includes("embedding") ? "embedding" : next.toLowerCase().includes("chunk") ? null
          : next.toLowerCase().includes("extract") ? "extracting" : "queued";
      // Chunking runs inside the upload/index request; the backend exposes no
      // chunking progress event, so do not report it as a live graph stage.
      if (state === null) return;
      const CustomEventType = windowRef?.CustomEvent || globalThis.CustomEvent;
      try {
        if (CustomEventType && typeof documentRef.dispatchEvent === "function") {
          documentRef.dispatchEvent(new CustomEventType("brain:ingestion", { detail: { id: nodeId, label, state } }));
        }
      } catch { /* File ingestion stays available when the host lacks DOM event support. */ }
      brainView.setIngestion();
    };
  }
  function setSelectedFiles(files) {
    const selected = [...(files || [])];
    if (el("brain-selection-status")) el("brain-selection-status").textContent = selected.length
      ? `${selected.length} file${selected.length === 1 ? "" : "s"} selected; ${selected.reduce((sum, file) => sum + (file.size || 0), 0)} bytes total.`
      : "No files selected.";
  }
  const nextPaint = () => new Promise(resolve => setTimeout(resolve, 0));
  async function uploadOne(file, setStage, expiry) {
    const suffix = (file.name.match(/\.[^.]+$/)?.[0] || "").toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(suffix)) { setStage("failed — unsupported file type"); return false; }
    if (!file.size || file.size > 1_048_576) { setStage("failed — empty or larger than 1 MiB"); return false; }
    setStage("Extracting text…"); await nextPaint();
    try {
      const formData = new FormData(); formData.append("file", file, file.name);
      const query = new URLSearchParams({ expires_at: expiry, retention_opt_in: "true" });
      const result = await request(`/api/memory/owner/upload?${query}`, { method: "POST", formData });
      selected = { id: result.id };
      setStage("Chunking text…"); await nextPaint();
      if (!semanticAvailable) {
        setStage("Ready — searchable with local lexical retrieval; semantic pack unavailable");
        return true;
      }
      setStage("Embedding locally…"); await nextPaint();
      try {
        const index = await request("/api/memory/semantic/index", { method: "POST", body: {
          scope: "owner", scope_id: ownerId, memory_id: result.id,
        } });
        setStage(`Ready — ${index.chunk_count} chunks embedded on this device`);
      } catch {
        setStage("Ready — lexical retrieval available; local embedding failed");
      }
      return true;
    } catch (error) {
      setStage(`Failed — ${error.message}`);
      return false;
    }
  }
  async function processStoredNote(memoryId, setStage) {
    setStage("Chunking text…"); await nextPaint();
    if (!semanticAvailable) {
      setStage("Ready — searchable with local lexical retrieval; semantic pack unavailable");
      return;
    }
    setStage("Embedding locally…"); await nextPaint();
    try {
      const index = await request("/api/memory/semantic/index", { method: "POST", body: {
        scope: "owner", scope_id: ownerId, memory_id: memoryId,
      } });
      setStage(`Ready — ${index.chunk_count} chunks embedded on this device`);
    } catch {
      setStage("Ready — lexical retrieval available; local embedding failed");
    }
  }
  function notifyGraphRefresh() {
    Promise.resolve().then(() => brainView.refresh()).catch(() => {});
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
      const setStage = stagedRow({ name: el("knowledge-source").value || "Pasted note" });
      setStage("Extracting pasted text…"); await nextPaint();
      notifyGraphRefresh();
      await processStoredNote(result.id, setStage);
      state.textContent = "Private note saved to your Brain.";
      selected = { id: result.id };
      await refreshAfterAction();
    } catch (error) { state.textContent = error.message; }
    finally { setBusy(false); }
  }
  async function upload(event) {
    event?.preventDefault();
    if (busy) return;
    const files = [...(el("knowledge-file").files || []), ...(el("knowledge-folder").files || [])];
    if (!files.length) { state.textContent = "Choose one or more supported files or a folder."; return; }
    if (files.length > MAX_FILES_PER_BATCH) { state.textContent = `Choose no more than ${MAX_FILES_PER_BATCH} files per batch.`; return; }
    if (!el("knowledge-consent").checked) { state.textContent = "Confirm local retention consent first."; return; }
    setBusy(true);
    try {
      const auth = await session(); ownerId = auth.identity;
      const expiry = new Date(now().getTime() + Number(el("knowledge-expiry").value) * 86400000).toISOString();
      const rows = files.map(file => ({ file, setStage: stagedRow(file) }));
      if (el("knowledge-file")) el("knowledge-file").value = "";
      if (el("knowledge-folder")) el("knowledge-folder").value = "";
      el("knowledge-consent").checked = false;
      let complete = 0, failed = 0;
      for (const item of rows) {
        if (await uploadOne(item.file, item.setStage, expiry)) complete++; else failed++;
      }
      state.textContent = `${complete} file${complete === 1 ? "" : "s"} added to your Brain; ${failed} failed.`;
      await refreshAfterAction();
    } catch (error) { state.textContent = error.message; }
    finally { setBusy(false); }
  }
  function selectLegacyBrainFile(event) {
    legacyBrainFile = event?.target?.files?.[0] || null;
    legacyBrainPlan = null;
    el("v3code-brain-state").textContent = legacyBrainFile
      ? `${legacyBrainFile.name || "Selected JSON"} selected (${legacyBrainFile.size || 0} bytes). Preview before import.`
      : "Choose a v3code brain.json export to begin.";
    setBusy(busy);
  }
  async function previewLegacyBrain() {
    if (busy) return;
    const file = legacyBrainFile;
    if (!file || !(file.name || "").toLowerCase().endsWith(".json")) {
      el("v3code-brain-state").textContent = "Choose a v3code Brain .json export.";
      return;
    }
    if (!file.size || file.size > 12 * 1024 * 1024) {
      el("v3code-brain-state").textContent = "Choose a non-empty Brain export no larger than 12 MiB.";
      return;
    }
    setBusy(true);
    el("v3code-brain-state").textContent = "Validating the selected Brain export locally…";
    try {
      const formData = new FormData(); formData.append("file", file, file.name);
      const result = await request("/api/memory/owner/v3code/preview", { method: "POST", formData });
      if (!/^[a-f0-9]{64}$/i.test(result.digest || "")
          || ![result.chunk_count, result.source_count, result.note_count].every(value => Number.isSafeInteger(value) && value > 0)
          || result.ignored_embeddings !== true) throw new Error("Brain preview response was invalid.");
      legacyBrainPlan = { digest: result.digest, summary: result, file };
      el("v3code-brain-state").textContent = `Preview: ${result.chunk_count} chunks from ${result.source_count} sources become ${result.note_count} private notes. Legacy vectors are discarded; no model runs or downloads.`;
    } catch (error) {
      legacyBrainPlan = null;
      el("v3code-brain-state").textContent = error.message;
    } finally { setBusy(false); }
  }
  async function importLegacyBrain() {
    if (busy) return;
    if (!legacyBrainPlan || legacyBrainPlan.file !== legacyBrainFile) {
      el("v3code-brain-state").textContent = "Preview the currently selected Brain export first.";
      return;
    }
    if (!el("knowledge-consent").checked) {
      el("v3code-brain-state").textContent = "Confirm local retention consent before importing private notes.";
      return;
    }
    const expiry = new Date(now().getTime() + Number(el("knowledge-expiry").value) * 86400000).toISOString();
    const { digest, summary } = legacyBrainPlan;
    const confirmation = `Import ${summary.chunk_count} legacy chunks from ${summary.source_count} sources as ${summary.note_count} owner-only local notes? They will expire ${expiry}. The old vectors are discarded; no model is run or downloaded. Existing matching import records are skipped. SHA-256: ${digest}`;
    if (!confirmImpl(confirmation)) {
      el("v3code-brain-state").textContent = "Import cancelled. No notes were added.";
      return;
    }
    setBusy(true);
    el("v3code-brain-state").textContent = "Importing into your private Brain…";
    try {
      const formData = new FormData(); formData.append("file", legacyBrainFile, legacyBrainFile.name);
      const query = new URLSearchParams({ expected_digest: digest, expires_at: expiry, retention_opt_in: "true" });
      const result = await request(`/api/memory/owner/v3code/import?${query}`, { method: "POST", formData });
      legacyBrainFile = null; legacyBrainPlan = null;
      if (el("v3code-brain-file")) el("v3code-brain-file").value = "";
      el("knowledge-consent").checked = false;
      el("v3code-brain-state").textContent = `${result.created_count} notes imported; ${result.skipped_count} matching notes already existed. ${result.chunk_count} source chunks retained in owner-only storage. Semantic indexing remains optional and local.`;
      try { await refreshAfterAction(); }
      catch { el("v3code-brain-state").textContent += " The Brain list did not refresh; the import result was saved."; }
    } catch (error) {
      el("v3code-brain-state").textContent = error.message;
    } finally { setBusy(false); }
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
    await brainView.refresh();
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
  async function refreshFaissStatus() {
    const status = el("brain-faiss-state"), detail = el("brain-faiss-detail");
    if (!status || !detail) return;
    try {
      const preview = await request("/api/memory/brain/faiss/preview");
      status.textContent = preview.state === "installed" ? "FAISS pack: Installed" : "FAISS pack: Not installed";
      detail.textContent = preview.supported
        ? preview.source + ". " + preview.install_action + " No model is downloaded."
        : "This pinned pack is unavailable for the current Python runtime or Windows architecture; lexical retrieval remains available.";
      el("brain-faiss-install").disabled = !preview.supported || preview.state === "installed" || busy;
      el("brain-faiss-test").disabled = preview.state !== "installed" || busy;
    } catch (error) {
      status.textContent = "FAISS pack: status unavailable";
      detail.textContent = error.message;
    }
  }
  async function installFaissPack() {
    if (busy) return;
    setBusy(true);
    try {
      const preview = await request("/api/memory/brain/faiss/preview");
      el("brain-faiss-detail").textContent = "Pinned wheels: " + preview.files.join(", ") + "; " + preview.download_bytes + " bytes. SHA-256 manifest: " + preview.manifest_digest + ".";
      if (!preview.supported || preview.state === "installed") {
        await refreshFaissStatus();
        return;
      }
      const mib = (preview.download_bytes / (1024 * 1024)).toFixed(1);
      const question = "Install the optional FAISS Brain pack (" + mib + " MiB) from official PyPI wheels? Exact versions: " + preview.files.join(", ") + ". SHA-256 manifest: " + preview.manifest_digest + ". This downloads and installs code into the app-local isolated pack directory. No embedding model is downloaded.";
      if (!confirmImpl(question)) {
        el("brain-faiss-detail").textContent = "Installation cancelled. No files were downloaded.";
        return;
      }
      await request("/api/memory/brain/faiss/install", { method: "POST", body: {
        confirmed: true, manifest_digest: preview.manifest_digest,
      } });
      el("brain-faiss-detail").textContent = "FAISS pack installed and loaded. No embedding model was downloaded; semantic indexing works only if the local Ollama embedding model is already installed.";
      await refreshFaissStatus();
      await refresh();
    } catch (error) {
      el("brain-faiss-detail").textContent = error.message + " Lexical retrieval remains available.";
    } finally { setBusy(false); }
  }
  async function testFaissPack() {
    if (busy) return;
    setBusy(true); el("brain-faiss-detail").textContent = "Running a temporary local index/search/delete self-test…";
    try {
      const result = await request("/api/memory/brain/faiss/self-test", { method: "POST", body: {} });
      el("brain-faiss-state").textContent = "FAISS pack: " + (result.state === "working" ? "Working" : result.state === "not-installed" ? "Not installed" : "Failed");
      el("brain-faiss-detail").textContent = result.detail;
    } catch (error) { el("brain-faiss-detail").textContent = error.message; }
    finally { setBusy(false); }
  }
  async function refreshEmbeddingStatus() {
    const status = el("brain-embedding-state"), detail = el("brain-embedding-detail");
    if (!status || !detail) return;
    try {
      const result = await request("/api/memory/brain/embedding/status");
      if (result.model_installed === true) {
        status.textContent = "nomic-embed-text:latest — Installed";
        el("brain-embedding-download").disabled = true;
        el("brain-embedding-test").disabled = false;
        detail.textContent = "Installed locally. Use Test local embeddings to verify a real loopback Ollama embedding call.";
      } else if (result.service_running === true) {
        status.textContent = "nomic-embed-text:latest — Not installed";
        el("brain-embedding-download").disabled = false;
        el("brain-embedding-test").disabled = true;
        detail.textContent = "The local Ollama service is running. Review the registry size and digest before choosing Download.";
      } else {
        status.textContent = "nomic-embed-text:latest — Unknown";
        el("brain-embedding-download").disabled = true;
        el("brain-embedding-test").disabled = true;
        detail.textContent = result.reason || "Start Ollama, then retry. No download was started.";
      }
    } catch (error) {
      status.textContent = "nomic-embed-text:latest — Status unavailable";
      detail.textContent = error.message;
      el("brain-embedding-download").disabled = true;
      el("brain-embedding-test").disabled = true;
    }
  }
  async function downloadEmbeddingModel() {
    if (busy) return;
    setBusy(true);
    try {
      const preview = await request("/api/memory/brain/embedding/preview");
      const size = (preview.manifest_bytes / 1_000_000_000).toFixed(2);
      el("brain-embedding-detail").textContent = "Official Ollama registry estimate: " + preview.manifest_bytes + " bytes (" + size + " GB); digest " + preview.manifest_digest + ".";
      if (preview.model_installed === true) { await refreshEmbeddingStatus(); return; }
      const question = "Download nomic-embed-text:latest (about " + size + " GB) from Ollama? Manifest digest: " + preview.manifest_digest + ". This only installs the local embedding model; it does not change the chat model assignment.";
      if (!confirmImpl(question)) {
        el("brain-embedding-detail").textContent = "Model download cancelled. No model data was requested.";
        return;
      }
      const auth = await session();
      const response = await fetchImpl("/api/memory/brain/embedding/pull", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": auth.csrf },
        body: JSON.stringify({ confirmed: true, manifest_digest: preview.manifest_digest,
          manifest_bytes: preview.manifest_bytes }),
      });
      if (!response.ok || !response.body) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : "Confirmed Ollama model download could not start.");
      }
      el("brain-embedding-download").disabled = true;
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let pending = ""; let completed = false;
      while (true) {
        const chunk = await reader.read();
        pending += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
        const lines = pending.split("\n"); pending = lines.pop() || "";
        for (const line of lines) if (line) {
          const event = JSON.parse(line);
          if (event.event === "error") throw new Error(event.message || "Ollama model download failed.");
          if (event.event === "complete") completed = true;
          if (event.event === "progress") el("brain-embedding-detail").textContent = event.total > 0
            ? "Downloading nomic-embed-text:latest — " + Math.floor(100 * event.completed / event.total) + "%"
            : "Downloading nomic-embed-text:latest — " + String(event.status || "working");
        }
        if (chunk.done) break;
      }
      if (!completed) throw new Error("Ollama ended before confirming the embedding model. Retry after checking Ollama.");
      el("brain-embedding-detail").textContent = "Ollama confirmed the local embedding model. No chat model assignment was changed.";
      await refreshEmbeddingStatus();
      await refresh();
    } catch (error) {
      el("brain-embedding-detail").textContent = error.message + " Lexical retrieval remains available.";
      await refreshEmbeddingStatus();
    } finally { setBusy(false); }
  }
  async function testEmbeddingModel() {
    if (busy) return;
    setBusy(true); el("brain-embedding-detail").textContent = "Sending a fixed self-test string to local Ollama only…";
    try {
      const result = await request("/api/memory/brain/embedding/self-test", { method: "POST", body: {} });
      el("brain-embedding-state").textContent = "nomic-embed-text:latest — " + (result.state === "working" ? "Working" : "Failed");
      el("brain-embedding-detail").textContent = result.detail;
    } catch (error) { el("brain-embedding-detail").textContent = error.message; }
    finally { setBusy(false); }
  }
  el("knowledge-note-form").addEventListener("submit", event => void saveNote(event));
  el("knowledge-upload-form").addEventListener("submit", event => void upload(event));
  el("knowledge-file").addEventListener("change", event => setSelectedFiles(event.target.files));
  el("knowledge-folder").addEventListener("change", event => setSelectedFiles(event.target.files));
  el("v3code-brain-file")?.addEventListener("change", selectLegacyBrainFile);
  el("v3code-brain-preview")?.addEventListener("click", () => void previewLegacyBrain());
  el("v3code-brain-import")?.addEventListener("click", () => void importLegacyBrain());
  const dropZone = el("brain-drop-zone");
  dropZone?.addEventListener("click", () => el("knowledge-file")?.click());
  dropZone?.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); el("knowledge-file")?.click(); }
  });
  dropZone?.addEventListener("dragover", event => { event.preventDefault(); dropZone.classList.add("drag-over"); });
  dropZone?.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone?.addEventListener("drop", event => {
    event.preventDefault(); dropZone.classList.remove("drag-over");
    const files = [...(event.dataTransfer?.files || [])];
    if (!files.length) return;
    const transfer = new DataTransfer(); files.forEach(file => transfer.items.add(file));
    el("knowledge-file").files = transfer.files; setSelectedFiles(transfer.files);
  });
  el("knowledge-refresh").addEventListener("click", () => void refresh());
  el("knowledge-index").addEventListener("click", () => void indexSelected());
  el("knowledge-inspect").addEventListener("click", () => void inspectIndex());
  el("knowledge-delete").addEventListener("click", () => void removeSelected());
  el("brain-faiss-install")?.addEventListener("click", () => void installFaissPack());
  el("brain-faiss-test")?.addEventListener("click", () => void testFaissPack());
  el("brain-embedding-download")?.addEventListener("click", () => void downloadEmbeddingModel());
  el("brain-embedding-test")?.addEventListener("click", () => void testEmbeddingModel());
  void refresh();
  void refreshFaissStatus();
  void refreshEmbeddingStatus();
  return { refresh, refreshBrain: () => brainView.refresh() };
}

if (globalThis.document?.getElementById("knowledge-note-form")) mountOwnerKnowledge();

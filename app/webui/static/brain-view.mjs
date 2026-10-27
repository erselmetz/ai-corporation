import { layoutBrainGraph, readLastBrainRetrieval } from "./brain-graph.mjs";

export function mountBrainView({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
  sessionStorage = globalThis.sessionStorage,
  createRenderer = null,
  reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true,
 } = {}) {
  const byId = id => documentRef.getElementById(id);
  const status = byId("brain-map-status"), list = byId("brain-map-list"), canvasWrap = byId("brain-map-canvas-wrap");
  if (!status || !list) return { refresh: async () => {}, dispose() {} };
  if (!createRenderer) {
    if (canvasWrap) canvasWrap.hidden = true;
    list.hidden = false;
    byId('brain-map-view-toggle').textContent = 'Desktop 3D help';
  }
  let graph = { nodes: [], edges: [] }, layout = layoutBrainGraph(graph), renderer = null;
  let selectedNode = null, active3d = false, resizeObserver = null;
  const retrieval = readLastBrainRetrieval(sessionStorage);
  const ingestion = new Map();
  let retrieved = [], cited = [];
  const applyRetrieval = value => {
    const ids = new Set(layout.allNodes.filter(node => node.kind === "chunk").map(node => node.id));
    retrieved = (value.retrieved || []).map(reference => `chunk:${reference}`).filter(id => ids.has(id));
    cited = (value.cited || []).map(reference => `chunk:${reference}`).filter(id => ids.has(id));
  };
  const safeLabel = node => node.kind === "document" ? `${node.label} (source)`
    : node.kind === "ingestion" ? `${node.label} (upload ${node.state})`
      : `${node.label}, chunk ${node.chunk_position ?? node.position ?? "unknown"}`;
  const authorizedFetch = async (url, options = {}) => {
    const response = await fetchImpl(url, { credentials: "same-origin", cache: "no-store", ...options });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Brain map request failed.");
    return body;
  };
  function setStatus(message) { status.textContent = message; }
  function updateHighlights() {
    if (!renderer || typeof renderer.setHighlights !== "function") return;
    renderer.setHighlights(retrieved, cited, [...ingestion.values()].filter(item => !["ready", "failed"].includes(item.state)));
  }
  const onIngestionEvent = event => {
    const item = event.detail;
    if (typeof item?.id === "string" && typeof item.label === "string"
        && ["queued", "extracting", "chunking", "embedding", "ready", "failed"].includes(item.state)) {
      ingestion.set(item.id, item);
      renderIngestion();
      if (active3d && renderer) renderer.setGraph(renderGraph());
    }
    updateHighlights();
  };
  documentRef.addEventListener("brain:ingestion", onIngestionEvent);
  function renderIngestion() {
    const target = byId("brain-map-ingestion");
    if (!target) return;
    target.replaceChildren();
    for (const item of ingestion.values()) {
      const row = documentRef.createElement("li"); row.textContent = `${item.label} — ${item.state}`; target.append(row);
    }
  }
  function renderGraph() {
    const additions = [...ingestion.values()].map((item, index) => ({
      id: item.id, kind: "ingestion", label: item.label, cluster: "ingestion",
      state: item.state, position: index + 1,
    }));
    return layoutBrainGraph({ nodes: [...layout.allNodes, ...additions], edges: layout.edges, basis: layout.basis });
  }
  function selectNode(node) {
    selectedNode = node;
    byId("brain-map-detail-title").textContent = node ? safeLabel(node) : "Select a source or chunk";
    byId("brain-map-detail-text").textContent = node ? "Loading authorized source text…" : "";
    renderer?.select?.(node?.id || null);
    if (!node) return;
    const params = new URLSearchParams({ node_id: node.id });
    void authorizedFetch(`/api/memory/brain/node?${params}`).then(result => {
      if (selectedNode?.id === node.id) byId("brain-map-detail-text").textContent = result.content;
    }).catch(error => {
      if (selectedNode?.id === node.id) byId("brain-map-detail-text").textContent = error.message;
    });
  }
  function renderList() {
    list.replaceChildren();
    for (const node of layout.allNodes) {
      const item = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button"; button.textContent = safeLabel(node);
      button.setAttribute("aria-current", selectedNode?.id === node.id ? "true" : "false");
      button.addEventListener("click", () => selectNode(node));
      const state = documentRef.createElement("span"); state.textContent = ` — ${node.state}`;
      item.append(button, state); list.append(item);
    }
  }
  function resize() {
    if (!renderer || !canvasWrap) return;
    const rect = byId("brain-map-canvas").getBoundingClientRect();
    renderer.resize(Math.max(1, rect.width), Math.max(1, Math.min(rect.height || rect.width * 0.62, 520)));
  }
  function fallback(reason) {
    active3d = false; canvasWrap.hidden = true;
    list.hidden = false;
    byId("brain-map-view-toggle").setAttribute("aria-pressed", "false");
    byId("brain-map-view-toggle").textContent = createRenderer ? "Show 3D map" : "Desktop 3D help";
    setStatus(`${reason} The complete keyboard-accessible list remains available.`);
  }
  async function enable3d() {
    if (reducedMotion) { fallback("Reduced motion is enabled; showing the list view."); return; }
    active3d = true;
    try {
      if (!renderer) {
        const callbacks = { canvas: byId("brain-map-canvas"),
          onSelect: id => {
            const node = layout.allNodes.find(candidate => candidate.id === id);
            if (node) selectNode(node);
          },
          documentRef, onStats: stats => {
            byId("brain-map-frame-stats").textContent = `3D capped at 24 FPS; observed ${stats.fps.toFixed(1)} FPS, p95 interval ${stats.interval_p95_ms.toFixed(1)} ms. Render CPU ${stats.render_cpu_ms.toFixed(2)} ms.`;
          }, onFallback: fallback };
        if (createRenderer) renderer = createRenderer({ ...callbacks, documentRef });
        else { fallback('Open Brain in the desktop app for the native 3D view.'); return; }
        renderer.setGraph(renderGraph());
        renderer.setHighlights(retrieved, cited, [...ingestion.values()].filter(item => !["ready", "failed"].includes(item.state)));
        renderer.setReducedMotion(false);
        resizeObserver = globalThis.ResizeObserver ? new ResizeObserver(resize) : null;
        resizeObserver?.observe(canvasWrap);
      }
      canvasWrap.hidden = false; list.hidden = false;
      byId("brain-map-view-toggle").setAttribute("aria-pressed", "true");
      byId("brain-map-view-toggle").textContent = "Show list";
      resize(); setStatus(layout.omitted ? `3D displays ${layout.nodes.length} nodes; ${layout.omitted} additional nodes remain in the complete list.` : "3D map shows the available source and chunk nodes.");
    } catch (error) { fallback(`3D map unavailable: ${error.message}`); }
  }
  async function refresh() {
    setStatus("Loading owner-only Brain map…");
    try {
      const next = await authorizedFetch("/api/memory/brain/graph");
      graph = next; layout = layoutBrainGraph(graph); applyRetrieval(retrieval); renderList();
      if (renderer) renderer.setGraph(renderGraph());
      updateHighlights();
      setStatus(`${layout.allNodes.filter(node => node.kind === "document").length} saved sources and ${layout.allNodes.filter(node => node.kind === "chunk").length} text chunks. Layout uses derived file-type/note groups; similarity is not measured.`);
    } catch (error) { setStatus(error.message); }
  }
  byId("brain-map-view-toggle")?.addEventListener("click", () => active3d ? (active3d = false, canvasWrap.hidden = true,
    list.hidden = false, byId("brain-map-view-toggle").setAttribute("aria-pressed", "false"),
    byId("brain-map-view-toggle").textContent = "Show 3D map", setStatus("Showing the complete keyboard-accessible list.")) : void enable3d());
  byId("brain-map-reduced-motion")?.addEventListener("change", event => {
    reducedMotion = event.target.checked;
    if (renderer) renderer.setReducedMotion(reducedMotion);
    if (reducedMotion && active3d) fallback("Reduced motion is enabled; showing the list view.");
  });
  byId("brain-map-reduced-motion").checked = reducedMotion;
  byId("brain-map-refresh")?.addEventListener("click", () => void refresh());
  void refresh();
  return { refresh, setIngestion: updateHighlights, dispose() {
    resizeObserver?.disconnect(); renderer?.dispose(); renderer = null;
    documentRef.removeEventListener("brain:ingestion", onIngestionEvent);
  } };
}

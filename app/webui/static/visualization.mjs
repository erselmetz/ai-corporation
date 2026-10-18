import { buildCorporationMapModel, changedNodeIds } from "./scene-model.mjs";

const THREE_URL = "/ui/static/vendor/three/three.module.js";
const SECTION_LABEL = { 401: "sign-in required", 403: "forbidden (permission not granted)" };

export async function mountVisualization({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  loadThree = () => import(THREE_URL),
  createView = null,
  matchMedia = globalThis.matchMedia?.bind(globalThis),
  requestFrame = globalThis.requestAnimationFrame?.bind(globalThis),
  cancelFrame = globalThis.cancelAnimationFrame?.bind(globalThis),
} = {}) {
  const el = id => documentRef.getElementById(id);
  const status = el("viz-status");
  const canvas = el("viz-canvas");
  const list = el("viz-list");
  const detail = el("viz-detail");
  const evidence = el("viz-evidence-data");
  const costLine = el("viz-cost");
  const frameMetric = el("viz-frame-metric");
  const frameMeasureButton = el("viz-frame-measure");
  const effectsBox = el("viz-effects");
  const motionBox = el("viz-reduce-motion");
  const searchInput = el("viz-search");
  const layerBoxes = Object.fromEntries(["organization", "projects", "tasks", "workflows", "providers", "capabilities", "resources", "knowledge"]
    .map(layer => [layer, el(`viz-layer-${layer}`)]));
  let reduced = Boolean(matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
  motionBox.checked = reduced;
  let mode = reduced ? "list" : "3d";
  let model = null;
  let selectedId = null;
  let view = null;
  let notice = "";
  let sectionNotes = [];
  let modelAssignments = [];
  let resourceCapacities = null;
  let knowledgeItems = [];
  let modelReadState = "unknown";
  let resourceReadState = "unknown";
  let knowledgeReadState = "unknown";
  let resourceObservedAt = null;
  let structureSnapshotAt = null;
  let workflowSnapshotAt = null;
  let sources = { states: {} };
  let frameMeasureId = null;
  let frameMeasureRun = 0;

  const text = (tag, value) => {
    const node = documentRef.createElement(tag);
    node.textContent = value;
    return node;
  };

  async function fetchSection(url) {
    const controller = new AbortController();
    const timeout = globalThis.setTimeout(() => controller.abort(), 2500);
    try {
      const response = await fetchImpl(url, { credentials: "same-origin", cache: "no-store",
        headers: { Accept: "application/json" }, signal: controller.signal });
      if (response.ok) return { data: await response.json() };
      return { note: SECTION_LABEL[response.status] ?? "could not be loaded" };
    } catch {
      return { note: "disconnected" };
    } finally {
      globalThis.clearTimeout(timeout);
    }
  }

  async function fetchKnowledge(corporationId) {
    const query = new URLSearchParams({ scope: "corporation", scope_id: corporationId, limit: "10" });
    return fetchSection(`/api/memory?${query}`);
  }

  function renderEvidence() {
    evidence.replaceChildren();
    const stateText = note => ({
      signin: "Sign in to read this source.",
      forbidden: "Access denied for this source.",
      disconnected: "Source disconnected.",
      failed: "Source could not be loaded.",
      unavailable: "Source unavailable.",
    }[note] ?? "Source state unknown.");

    const resources = documentRef.createElement("section");
    resources.append(text("h3", "Software resource snapshot"));
    if (resourceReadState !== "available") {
      resources.append(text("p", stateText(resourceReadState)));
    } else if (resourceObservedAt) {
      resources.append(text("p", `Server snapshot observed at ${resourceObservedAt}.`));
    }
    if (resourceReadState === "available" && !resourceCapacities) {
      resources.append(text("p", "No resource manager is configured; hardware availability is unknown."));
    } else if (resourceReadState === "available" && !resourceCapacities.length) {
      resources.append(text("p", "No configured resource slots are reported."));
    } else if (resourceReadState === "available") {
      const list = documentRef.createElement("ul");
      for (const capacity of resourceCapacities) {
        const target = [capacity.scope, capacity.provider_id, capacity.model_id].filter(Boolean).join(" / ");
        list.append(text("li", `${target}: ${capacity.allocated}/${capacity.limit} slots allocated; ${capacity.remaining} remaining`));
      }
      resources.append(list);
    }
    evidence.append(resources);

    const knowledge = documentRef.createElement("section");
    knowledge.append(text("h3", "Corporation knowledge provenance"));
    if (knowledgeReadState !== "available") {
      knowledge.append(text("p", stateText(knowledgeReadState)));
    } else if (!knowledgeItems.length) {
      knowledge.append(text("p", "No owner-readable retained Corporation knowledge."));
    } else {
      const list = documentRef.createElement("ul");
      for (const item of knowledgeItems) {
        const provenance = item.provenance;
        const source = provenance
          ? `${provenance.source_scope} ${provenance.source_scope_id} / ${provenance.source_reference} (source created ${provenance.source_created_at})`
          : "Source provenance unavailable";
        list.append(text("li", `${item.type} ${item.id}: published ${item.created_at}; ${source}; expires ${item.expires_at}`));
      }
      knowledge.append(list);
    }
    evidence.append(knowledge);
  }

  function appendAgentModelDetail(container, node) {
    if (node.agent_visibility === "forbidden") {
      container.append(text("p", "Provider/model association unavailable because Agent access is forbidden."));
      return;
    }
    if (!node.agent_id) {
      container.append(text("p", "No recorded Agent association for this map item."));
      return;
    }
    if (modelReadState !== "available") {
      container.append(text("p", `Model assignment for Agent ${node.agent_id}: ${modelReadState}.`));
      return;
    }
    const assignment = modelAssignments.find(item => item.agent_id === node.agent_id);
    if (!assignment) {
      container.append(text("p", `No recorded provider/model assignment for Agent ${node.agent_id}.`));
      return;
    }
    container.append(text("p", `Recorded assignment for Agent ${node.agent_id}: provider ${assignment.provider_id}, model ${assignment.model_id}.`));
    const matching = resourceCapacities?.filter(item => item.scope === "model"
      && item.provider_id === assignment.provider_id && item.model_id === assignment.model_id) ?? [];
    if (resourceReadState === "available" && matching.length) {
      for (const capacity of matching) {
        container.append(text("p", `Associated software slot budget: ${capacity.allocated}/${capacity.limit} allocated; ${capacity.remaining} remaining. This is not hardware capacity.`));
      }
    } else if (resourceReadState !== "available") {
      container.append(text("p", `Resource snapshot: ${resourceReadState}.`));
    } else {
      container.append(text("p", "No exact configured model slot limit is recorded; hardware fit is unknown."));
    }
  }

  async function ensureView() {
    if (view) return view;
    try {
      const THREE = await loadThree();
      const factory = createView ?? (await import("./three-scene.mjs")).createThreeView;
      view = factory({ THREE, canvas });
      return view;
    } catch {
      notice = "3D graphics are unavailable on this device; showing the list view.";
      mode = "list";
      return null;
    }
  }

  function renderList() {
    list.replaceChildren();
    if (!model || !model.nodes.length) {
      list.append(text("p", "No authorized records in the selected map layers."));
      return;
    }
    list.append(text("p", `${model.nodes.length} visible nodes; ${model.omitted} matching records omitted by the 60-node cap; ${model.omittedEdges} additional recorded links omitted by the 119-link render cap.`));
    const items = documentRef.createElement("ul");
    for (const node of model.nodes) {
      const row = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.textContent = `${node.label} (${node.id}): ${node.state}`;
      button.addEventListener("click", () => select(node.id));
      row.append(button);
      items.append(row);
    }
    list.append(items);
    const links = documentRef.createElement("ul");
    for (const edge of model.edges) links.append(text("li", `${edge.kind}: ${edge.from} -> ${edge.to}`));
    list.append(text("h3", "Recorded links"));
    list.append(links);
  }

  function renderCost() {
    frameMeasureButton.disabled = !view || mode !== "3d";
    if (!view || mode !== "3d") { costLine.textContent = "Render cost: not measured (3D view inactive)."; return; }
    const { average, samples, resources } = view.cost();
    const resourceText = resources
      ? ` Scene resources: ${resources.geometries} geometries, ${resources.textures} textures, ${resources.calls} calls.` : " Scene resource counters unavailable.";
    costLine.textContent = `Render cost: ${average.toFixed(2)} ms average over ${samples} synchronous renders on this device; this is not frame pacing or GPU completion.${resourceText} The 300-frame performance and resource gates remain unverified on a published minimum device profile.`;
  }

  function cancelFrameMeasurement(message = "Frame pacing measurement canceled.") {
    frameMeasureRun += 1;
    if (frameMeasureId !== null) cancelFrame?.(frameMeasureId);
    frameMeasureId = null;
    frameMeasureButton.textContent = "Measure 300 frames";
    frameMeasureButton.disabled = !view || mode !== "3d";
    frameMetric.textContent = message;
  }

  function measureFrames() {
    if (frameMeasureId !== null) { cancelFrameMeasurement(); return; }
    if (mode !== "3d" || !view) {
      frameMetric.textContent = "Frame pacing requires an active 3D scene.";
      return;
    }
    if (typeof requestFrame !== "function") {
      frameMetric.textContent = "Frame pacing measurement is unavailable in this browser.";
      return;
    }
    const run = ++frameMeasureRun;
    const intervals = [];
    let previous = null;
    frameMetric.textContent = "Measuring 300 frame intervals on this device. This does not check model-inference load.";
    frameMeasureButton.textContent = "Cancel measurement";
    frameMeasureButton.disabled = false;
    const sample = timestamp => {
      if (run !== frameMeasureRun) return;
      frameMeasureId = null;
      if (previous !== null) intervals.push(timestamp - previous);
      previous = timestamp;
      try { view?.renderFrame?.(); } catch {
        cancelFrameMeasurement("Frame pacing measurement failed; the rendering result is unknown.");
        return;
      }
      if (intervals.length < 300) {
        frameMeasureId = requestFrame(sample);
        return;
      }
      const ordered = intervals.slice().sort((a, b) => a - b);
      const p95 = ordered[Math.ceil(ordered.length * 0.95) - 1];
      const p99 = ordered[Math.ceil(ordered.length * 0.99) - 1];
      frameMeasureButton.textContent = "Measure 300 frames";
      frameMeasureButton.disabled = false;
      frameMetric.textContent = `Observed p95 ${p95.toFixed(2)} ms and p99 ${p99.toFixed(2)} ms over 300 frame intervals. Task 162 reference targets are 16.7 ms and 33.3 ms; this single device-local run is diagnostic only. Minimum hardware profile and inference-load condition are unknown.`;
      frameMeasureId = null;
    };
    frameMeasureId = requestFrame(sample);
  }

  function showDetail(note = "") {
    detail.replaceChildren();
    if (note) detail.append(text("p", note));
    const node = model?.nodes.find(n => n.id === selectedId);
    if (!selectedId) { detail.append(text("p", "Select a node.")); return; }
    detail.append(text("p", node ? `${node.detail} Source: ${node.source}${node.snapshot_at ? `; source snapshot ${node.snapshot_at}` : "; this API does not expose a source timestamp"}.` : "Stale: this item is no longer recorded."));
    if (node) {
      const related = model.edges.filter(edge => edge.from === node.id || edge.to === node.id);
      detail.append(text("p", related.length ? `Recorded relationships: ${related.map(edge => `${edge.kind} ${edge.from === node.id ? `to ${edge.to}` : `from ${edge.from}`}`).join("; ")}.` : "No related node is present in the selected, authorized layers."));
    }
    if (node) appendAgentModelDetail(detail, node);
  }

  function select(id) {
    selectedId = id;
    view?.select(selectedId);
    showDetail();
  }

  function applyMode() {
    const threeD = mode === "3d";
    canvas.hidden = !threeD;
    list.hidden = threeD;
    el("viz-mode-3d").setAttribute?.("aria-pressed", String(threeD));
    el("viz-mode-list").setAttribute?.("aria-pressed", String(!threeD));
    canvas.setAttribute?.("aria-label", `3D organizational globe with ${model?.nodes.length ?? 0} recorded nodes; placement is not geographic. Use left and right arrow keys to move between nodes. Drag to orbit, hold Shift and drag to pan, or use the labeled controls. Switch to the accessible list for equivalent records and relationships.`);
    renderCost();
  }

  function renderStatus() {
    const parts = [];
    if (model) parts.push(`${model.nodes.length} of at most 60 selected nodes and ${model.edges.length} of at most 119 recorded links shown${model.omitted ? `; ${model.omitted} matching records omitted` : ""}${model.omittedEdges ? `; ${model.omittedEdges} links omitted` : ""}.`);
    if (structureSnapshotAt) parts.push(`Structure snapshot: ${structureSnapshotAt}.`);
    if (workflowSnapshotAt) parts.push(`Workflow snapshot: ${workflowSnapshotAt}.`);
    if (resourceObservedAt) parts.push(`Resource snapshot: ${resourceObservedAt}.`);
    if (sectionNotes.length) parts.push(`Unavailable: ${sectionNotes.join("; ")}.`);
    parts.push("Department records are not exposed by current APIs. Sources are independent on-demand snapshots, not one atomic view.");
    if (notice) parts.push(notice);
    status.textContent = parts.join(" ");
  }

  function activeLayers() {
    return Object.entries(layerBoxes).filter(([, input]) => input.checked).map(([layer]) => layer);
  }

  async function renderModel() {
    if (frameMeasureId !== null) cancelFrameMeasurement("Frame pacing measurement canceled because map filters changed.");
    const previous = model;
    model = buildCorporationMapModel(sources, { layers: activeLayers(), query: searchInput.value });
    if (selectedId && !model.nodes.some(node => node.id === selectedId)) selectedId = null;
    renderList();
    if (mode === "3d") {
      const active = await ensureView();
      if (active) {
        active.resize(canvas.clientWidth || 800, canvas.clientHeight || 448);
        active.setModel(model, { effects: effectsBox.checked });
        active.select(selectedId);
        const changed = changedNodeIds(previous, model);
        if (effectsBox.checked && !reduced && changed.length) active.pulse(changed);
      }
    }
    applyMode();
    renderStatus();
    showDetail();
    renderEvidence();
  }

  async function refresh() {
    if (frameMeasureId !== null) cancelFrameMeasurement("Frame pacing measurement canceled because source snapshots refreshed.");
    const [structure, workflows, employeesRead, projectsRead, tasksRead, agentsRead, providersRead, modelsRead, resourcesRead, statusRead] = await Promise.all([
      fetchSection("/api/structure-map"), fetchSection("/api/local/workflows/map"),
      fetchSection("/api/employees"), fetchSection("/api/projects"), fetchSection("/api/tasks"), fetchSection("/api/agents"),
      fetchSection("/api/providers"), fetchSection("/api/models"), fetchSection("/api/system/monitor"), fetchSection("/api/status"),
    ]);
    sectionNotes = [];
    const reads = { structure, workflows, employees: employeesRead, projects: projectsRead, tasks: tasksRead,
      agents: agentsRead, providers: providersRead, models: modelsRead, resources: resourcesRead, corporation: statusRead };
    for (const [name, result] of Object.entries(reads)) if (result.note) sectionNotes.push(`${name} ${result.note}`);
    structureSnapshotAt = structure.data?.generated_at ?? null;
    workflowSnapshotAt = workflows.data?.generated_at ?? null;
    modelReadState = modelsRead.data && Array.isArray(modelsRead.data.items)
      && modelsRead.data.items.every(item => item && typeof item.agent_id === "string"
        && typeof item.provider_id === "string" && typeof item.model_id === "string")
      ? "available" : modelsRead.note ?? "failed";
    modelAssignments = modelReadState === "available" ? modelsRead.data.items : [];
    resourceReadState = resourcesRead.data && typeof resourcesRead.data.observed_at === "string"
      && (resourcesRead.data.resource_capacities === null || Array.isArray(resourcesRead.data.resource_capacities))
      ? "available" : resourcesRead.note ?? "failed";
    resourceCapacities = resourceReadState === "available" ? resourcesRead.data.resource_capacities : null;
    resourceObservedAt = resourceReadState === "available" ? resourcesRead.data.observed_at : null;
    knowledgeItems = [];
    let memory = null;
    if (statusRead.data?.corporation?.id) {
      const knowledgeRead = await fetchKnowledge(statusRead.data.corporation.id);
      knowledgeReadState = knowledgeRead.data && Array.isArray(knowledgeRead.data.items)
        && knowledgeRead.data.items.every(item => item && typeof item.id === "string"
          && typeof item.type === "string" && typeof item.created_at === "string"
          && typeof item.expires_at === "string" && item.scope === "corporation")
        ? "available" : knowledgeRead.note ?? "failed";
      knowledgeItems = knowledgeReadState === "available" ? knowledgeRead.data.items : [];
      memory = knowledgeRead.data ?? null;
      if (knowledgeRead.note) sectionNotes.push(`knowledge ${knowledgeRead.note}`);
    } else knowledgeReadState = statusRead.note ?? "unavailable";
    sources = {
      corporation: statusRead.data ?? null, corporationSource: "/api/status",
      structure: structure.data ?? null, workflows: workflows.data ?? null,
      employees: employeesRead.data ?? null, projects: projectsRead.data ?? null, tasks: tasksRead.data ?? null, agents: agentsRead.data ?? null,
      providers: providersRead.data ?? null, models: modelsRead.data ?? null,
      monitoring: resourcesRead.data ?? null, memory,
      states: { organization: structure.data ? "available" : structure.note ?? "unknown",
        workflows: workflows.data ? "available" : workflows.note ?? "unknown",
        employees: employeesRead.data ? "available" : employeesRead.note ?? "unknown",
        projects: projectsRead.data ? "available" : projectsRead.note ?? "unknown",
        tasks: tasksRead.data ? "available" : tasksRead.note ?? "unknown",
        agents: agentsRead.data ? "available" : agentsRead.note ?? "unknown",
        providers: providersRead.data ? "available" : providersRead.note ?? "unknown",
        models: modelsRead.data ? "available" : modelsRead.note ?? "unknown",
        resources: resourcesRead.data ? "available" : resourcesRead.note ?? "unknown",
        capabilities: agentsRead.data ? "available" : agentsRead.note ?? "unknown",
        knowledge: knowledgeReadState,
        corporation: statusRead.data ? "available" : statusRead.note ?? "unknown" },
    };
    await renderModel();
  }

  async function setMode(next) {
    if (next !== "3d" && frameMeasureId !== null) cancelFrameMeasurement("Frame pacing measurement canceled because 3D view closed.");
    mode = next;
    notice = "";
    if (mode === "3d") await refresh(); else { applyMode(); renderStatus(); }
  }

  function step(delta) {
    if (!model?.nodes.length) return;
    const index = model.nodes.findIndex(n => n.id === selectedId);
    select(model.nodes[(index + delta + model.nodes.length) % model.nodes.length].id);
  }

  canvas.addEventListener("keydown", event => {
    if (event.key === "ArrowRight") { event.preventDefault?.(); step(1); }
    if (event.key === "ArrowLeft") { event.preventDefault?.(); step(-1); }
  });
  canvas.addEventListener("click", event => {
    const rect = canvas.getBoundingClientRect?.() ?? { left: 0, top: 0, width: 1, height: 1 };
    const id = view?.pick(((event.clientX - rect.left) / rect.width) * 2 - 1, -(((event.clientY - rect.top) / rect.height) * 2 - 1));
    if (id) select(id);
  });
  let drag = null;
  canvas.addEventListener("pointerdown", event => {
    drag = { x: event.clientX, y: event.clientY, pan: event.shiftKey || event.button === 2 };
    canvas.setPointerCapture?.(event.pointerId);
  });
  canvas.addEventListener("pointermove", event => {
    if (!drag) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    drag.x = event.clientX; drag.y = event.clientY;
    if (drag.pan) view?.pan?.(dx * 0.04, -dy * 0.04);
    else { view?.rotate(dx * 0.01); view?.tilt?.(dy * 0.01); }
  });
  for (const eventName of ["pointerup", "pointercancel", "lostpointercapture"]) canvas.addEventListener(eventName, () => { drag = null; });
  canvas.addEventListener("wheel", event => { event.preventDefault?.(); view?.zoom?.(event.deltaY < 0 ? -1 : 1); }, { passive: false });
  canvas.addEventListener("contextmenu", event => event.preventDefault?.());
  el("viz-mode-3d").addEventListener("click", () => setMode("3d"));
  el("viz-mode-list").addEventListener("click", () => setMode("list"));
  el("viz-refresh").addEventListener("click", refresh);
  frameMeasureButton.addEventListener("click", measureFrames);
  el("viz-rotate-left").addEventListener("click", () => view?.rotate(-0.3));
  el("viz-rotate-right").addEventListener("click", () => view?.rotate(0.3));
  el("viz-zoom-in").addEventListener("click", () => view?.zoom?.(-1));
  el("viz-zoom-out").addEventListener("click", () => view?.zoom?.(1));
  el("viz-pan-left").addEventListener("click", () => view?.pan?.(-1, 0));
  el("viz-pan-right").addEventListener("click", () => view?.pan?.(1, 0));
  el("viz-pan-up").addEventListener("click", () => view?.pan?.(0, 1));
  el("viz-pan-down").addEventListener("click", () => view?.pan?.(0, -1));
  for (const input of Object.values(layerBoxes)) input.addEventListener("change", renderModel);
  searchInput.addEventListener("input", renderModel);
  effectsBox.addEventListener("change", () => { if (model && view) { view.setModel(model, { effects: effectsBox.checked }); renderCost(); } });
  motionBox.addEventListener("change", () => {
    reduced = motionBox.checked;
    if (reduced && mode === "3d") setMode("list");
  });

  await refresh();
  return { refresh, select, setMode, mode: () => mode };
}

if (globalThis.document) await mountVisualization();

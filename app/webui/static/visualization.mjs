import { buildSceneModel, changedNodeIds } from "./scene-model.mjs";

const THREE_URL = "/ui/static/vendor/three/three.module.js";
const SECTION_LABEL = { 401: "sign-in required", 403: "forbidden (permission not granted)" };

export async function mountVisualization({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  loadThree = () => import(THREE_URL),
  createView = null,
  matchMedia = globalThis.matchMedia?.bind(globalThis),
} = {}) {
  const el = id => documentRef.getElementById(id);
  const status = el("viz-status");
  const canvas = el("viz-canvas");
  const list = el("viz-list");
  const detail = el("viz-detail");
  const evidence = el("viz-evidence-data");
  const costLine = el("viz-cost");
  const effectsBox = el("viz-effects");
  const motionBox = el("viz-reduce-motion");
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

  const text = (tag, value) => {
    const node = documentRef.createElement(tag);
    node.textContent = value;
    return node;
  };

  async function fetchSection(url) {
    try {
      const response = await fetchImpl(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (response.ok) return { data: await response.json() };
      return { note: SECTION_LABEL[response.status] ?? "could not be loaded" };
    } catch {
      return { note: "disconnected" };
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
      list.append(text("p", "No recorded positions or workflow items to show."));
      return;
    }
    const items = documentRef.createElement("ul");
    for (const node of model.nodes) {
      const row = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.textContent = `${node.label}: ${node.state}`;
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
    if (!view || mode !== "3d") { costLine.textContent = "Render cost: not measured (3D view inactive)."; return; }
    const { average, samples } = view.cost();
    costLine.textContent = `Render cost: ${average.toFixed(2)} ms average over ${samples} renders, measured on this device while local inference may also be running.`;
  }

  function showDetail(note = "") {
    detail.replaceChildren();
    if (note) detail.append(text("p", note));
    const node = model?.nodes.find(n => n.id === selectedId);
    if (!selectedId) { detail.append(text("p", "Select a node.")); return; }
    detail.append(text("p", node ? node.detail : "Stale: this item is no longer recorded."));
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
    canvas.setAttribute?.("aria-label", `3D map with ${model?.nodes.length ?? 0} recorded nodes. Use left and right arrow keys to move between nodes, or switch to the list view.`);
    renderCost();
  }

  function renderStatus() {
    const parts = [];
    if (model) parts.push(`${model.nodes.length} recorded nodes${model.omitted ? ` (${model.omitted} more omitted by the scene cap)` : ""}.`);
    if (structureSnapshotAt) parts.push(`Structure snapshot: ${structureSnapshotAt}.`);
    if (workflowSnapshotAt) parts.push(`Workflow snapshot: ${workflowSnapshotAt}.`);
    if (sectionNotes.length) parts.push(`Unavailable: ${sectionNotes.join("; ")}.`);
    if (notice) parts.push(notice);
    status.textContent = parts.join(" ");
  }

  async function refresh() {
    const [structure, workflows, modelsRead, resourcesRead, statusRead] = await Promise.all([
      fetchSection("/api/structure-map"), fetchSection("/api/local/workflows/map"),
      fetchSection("/api/models"), fetchSection("/api/system/monitor"), fetchSection("/api/status"),
    ]);
    sectionNotes = [];
    if (structure.note) sectionNotes.push(`structure ${structure.note}`);
    if (workflows.note) sectionNotes.push(`workflows ${workflows.note}`);
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
    if (statusRead.data?.corporation?.id) {
      const knowledgeRead = await fetchKnowledge(statusRead.data.corporation.id);
      knowledgeReadState = knowledgeRead.data && Array.isArray(knowledgeRead.data.items)
        && knowledgeRead.data.items.every(item => item && typeof item.id === "string"
          && typeof item.type === "string" && typeof item.created_at === "string"
          && typeof item.expires_at === "string" && item.scope === "corporation")
        ? "available" : knowledgeRead.note ?? "failed";
      knowledgeItems = knowledgeReadState === "available" ? knowledgeRead.data.items : [];
    } else knowledgeReadState = statusRead.note ?? "unavailable";
    const previous = model;
    model = buildSceneModel(structure.data, workflows.data);
    renderList();
    if (mode === "3d") {
      const active = await ensureView();
      if (active) {
        const effects = effectsBox.checked;
        active.resize(canvas.clientWidth || 800, canvas.clientHeight || 448);
        active.setModel(model, { effects });
        active.select(selectedId);
        const changed = changedNodeIds(previous, model);
        if (effects && !reduced && changed.length) active.pulse(changed);
      }
    }
    applyMode();
    renderStatus();
    showDetail();
    renderEvidence();
  }

  async function setMode(next) {
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
  el("viz-mode-3d").addEventListener("click", () => setMode("3d"));
  el("viz-mode-list").addEventListener("click", () => setMode("list"));
  el("viz-refresh").addEventListener("click", refresh);
  el("viz-rotate-left").addEventListener("click", () => view?.rotate(-0.3));
  el("viz-rotate-right").addEventListener("click", () => view?.rotate(0.3));
  effectsBox.addEventListener("change", () => { if (model && view) { view.setModel(model, { effects: effectsBox.checked }); renderCost(); } });
  motionBox.addEventListener("change", () => {
    reduced = motionBox.checked;
    if (reduced && mode === "3d") setMode("list");
  });

  await refresh();
  return { refresh, select, setMode, mode: () => mode };
}

if (globalThis.document) await mountVisualization();

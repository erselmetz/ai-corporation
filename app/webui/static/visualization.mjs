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
    if (sectionNotes.length) parts.push(`Unavailable: ${sectionNotes.join("; ")}.`);
    if (notice) parts.push(notice);
    status.textContent = parts.join(" ");
  }

  async function refresh() {
    const [structure, workflows] = await Promise.all([
      fetchSection("/api/structure-map"), fetchSection("/api/local/workflows/map"),
    ]);
    sectionNotes = [];
    if (structure.note) sectionNotes.push(`structure ${structure.note}`);
    if (workflows.note) sectionNotes.push(`workflows ${workflows.note}`);
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
  motionBox.addEventListener("change", () => { reduced = motionBox.checked; });

  await refresh();
  return { refresh, select, setMode, mode: () => mode };
}

if (globalThis.document) await mountVisualization();
import assert from "node:assert/strict";
import test from "node:test";
import { buildCorporationMapModel, buildSceneModel, changedNodeIds, MAX_SCENE_EDGES, MAX_SCENE_NODES } from "../app/webui/static/scene-model.mjs";
import { buildThreeScene, createThreeView } from "../app/webui/static/three-scene.mjs";
import { mountVisualization } from "../app/webui/static/visualization.mjs";
import * as THREE from "../app/webui/static/vendor/three/three.module.js";

const pos = (id, extra = {}) => ({
  id, title: id, active: true, revision: 1, reports_to_position_id: null, reporting_state: "root",
  employee: { state: "assigned" }, agent: { state: "assigned" }, ...extra,
});
const structure = { positions: [pos("boss"), pos("dev", { reports_to_position_id: "boss", reporting_state: "linked" })] };
const wi = (id, state) => ({ id, role: "worker", state, reason: "", agent_id: "w1", agent_visibility: "available" });
const workflows = state => ({ workflows: [{ id: "w", title: "Plan", nodes: [wi("a", state), wi("b", "waiting")],
  operational_edges: [{ kind: "handoff", from: "a", to: "b" }] }] });

test("scene model contains only recorded nodes and edges, with a hard cap", () => {
  const model = buildSceneModel(structure, workflows("review"));
  assert.deepEqual(model.nodes.map(n => n.id), ["pos:boss", "pos:dev", "wi:a", "wi:b"]);
  assert.deepEqual(model.edges.map(e => e.kind).sort(), ["handoff", "reporting"]);
  assert.equal(model.nodes.find(n => n.id === "pos:dev").y < model.nodes.find(n => n.id === "pos:boss").y, true);
  const many = { positions: Array.from({ length: 100 }, (_, i) => pos(`p${i}`)) };
  const capped = buildSceneModel(many, null);
  assert.equal(capped.nodes.length, MAX_SCENE_NODES);
  assert.equal(capped.omitted, 100 - MAX_SCENE_NODES);
  assert.deepEqual(buildSceneModel(null, null).nodes, []);
});

test("only recorded state changes count as changes", () => {
  const before = buildSceneModel(structure, workflows("running"));
  const after = buildSceneModel(structure, workflows("review"));
  assert.deepEqual(changedNodeIds(before, after), ["wi:a"]);
  assert.deepEqual(changedNodeIds(after, after), []);
  assert.deepEqual(changedNodeIds(null, after), []);
});

test("corporation map includes only exact source-backed relationships and caps each selected layer view", () => {
  const sources = {
    corporation: { corporation: { id: "corp", name: "Core" } },
    structure: { generated_at: "org-time", positions: [{ id: "position-1", title: "Builder", active: true,
      reporting_state: "root", employee: { state: "assigned", id: "employee-1", name: "Dev", role: "Developer" },
      agent: { state: "assigned", id: "agent-1", name: "Builder Agent" } }] },
    employees: { items: [{ id: "employee-1", name: "Dev", role: "Developer", agent_id: "agent-1" }] },
    agents: { items: [{ id: "agent-1", name: "Builder Agent", role: "Developer", capabilities: ["code-review"] }] },
    projects: { items: [{ id: "project-1", name: "Website", status: "active" }] },
    tasks: { items: [{ id: "task-1", title: "Build page", status: "pending", project_id: "project-1", assigned_agent: "agent-1" }] },
    providers: { items: [{ id: "local", type: "ollama" }] },
    models: { items: [{ agent_id: "agent-1", provider_id: "local", model_id: "small-model" }] },
    workflows: { generated_at: "workflow-time", workflows: [{ id: "flow-1", title: "Review", state: "active", nodes: [
      { id: "work-1", role: "reviewer", state: "running", response_state: "not recorded" },
    ], operational_edges: [] }] },
    monitoring: { observed_at: "resource-time", resource_capacities: [
      { scope: "model", provider_id: "local", model_id: "small-model", allocated: 1, limit: 2, remaining: 1 },
    ] },
    memory: { items: [{ id: "memory-1", type: "summary", scope: "corporation", expires_at: "future",
      provenance: { source_scope: "project", source_scope_id: "project-1", source_reference: "project-1" } }] },
  };
  const model = buildCorporationMapModel(sources);
  assert.ok(model.nodes.some(node => node.id === "core:corp"));
  assert.ok(model.nodes.some(node => node.id === "emp:employee-1"));
  assert.ok(model.nodes.some(node => node.id === "agent:agent-1"));
  assert.ok(model.nodes.some(node => node.id === "task:task-1"));
  assert.ok(model.nodes.some(node => node.id === "workflow:flow-1"));
  assert.ok(model.nodes.some(node => node.id === "capability:agent-1:code-review"));
  assert.ok(model.nodes.some(node => node.id === "resource:model:local:small-model"));
  assert.ok(model.nodes.some(node => node.id === "knowledge:memory-1"));
  assert.ok(model.edges.some(edge => edge.kind === "belongs to project" && edge.from === "task:task-1" && edge.to === "project:project-1"));
  assert.ok(model.edges.some(edge => edge.kind === "source Project" && edge.from === "knowledge:memory-1" && edge.to === "project:project-1"));
  assert.ok(model.edges.some(edge => edge.kind === "assigned model" && edge.from === "agent:agent-1"));
  assert.ok(model.nodes.every(node => !node.detail.includes("private content")));
  assert.equal(model.sections.departments, "unsupported");
  const tasksOnly = buildCorporationMapModel(sources, { layers: ["tasks"] });
  assert.deepEqual(tasksOnly.nodes.map(node => node.id), ["task:task-1"]);
  const many = buildCorporationMapModel({ tasks: { items: Array.from({ length: 90 }, (_, i) => ({
    id: `task-${i}`, title: `Task ${i}`, status: "pending",
  })) } }, { layers: ["tasks"] });
  assert.equal(many.nodes.length, MAX_SCENE_NODES);
  assert.equal(many.omitted, 30);
  const ids = Array.from({ length: 59 }, (_, i) => `work-${i}`);
  const dense = buildCorporationMapModel({ workflows: { workflows: [{ id: "dense", title: "Dense", state: "active",
    nodes: ids.map(id => ({ id, role: "worker", state: "pending" })),
    operational_edges: ids.flatMap(from => ids.filter(to => to !== from).map(to => ({ kind: "handoff", from, to }))) }] } }, { layers: ["workflows"] });
  assert.equal(dense.edges.length, MAX_SCENE_EDGES);
  assert.ok(dense.omittedEdges > 0);
});

test("real Three.js scene builds one mesh per node and effects can be disabled", () => {
  const model = buildSceneModel(structure, workflows("review"));
  const full = buildThreeScene(THREE, model, { effects: true });
  const plain = buildThreeScene(THREE, model, { effects: false });
  assert.equal(full.meshes.size, 4);
  assert.ok(full.group.children.length > plain.group.children.length);
  assert.equal(plain.group.children.length, 4 + 2);
  full.dispose(); plain.dispose();
});

test("view records render cost and pulses only requested nodes", () => {
  const rendered = [];
  const FakeThree = { ...THREE, WebGLRenderer: class { constructor() { this.info = { memory: { geometries: 3, textures: 1 }, render: { calls: 5 } }; }
    setPixelRatio() {} setSize() {} render() { rendered.push(1); } dispose() {} } };
  const frames = [];
  let clock = 0;
  const view = createThreeView({ THREE: FakeThree, canvas: {}, requestFrame: f => frames.push(f), now: () => (clock += 2) });
  view.setModel(buildSceneModel(structure, workflows("review")));
  assert.equal(view.cost().samples, 1);
  assert.deepEqual(view.cost().resources, { geometries: 3, textures: 1, calls: 5 });
  view.pulse(["wi:a"]);
  assert.equal(frames.length, 1);
  view.pulse([]);
  assert.equal(frames.length, 1);
  view.dispose();
});

class El {
  constructor(tag = "div") { this.tag = tag; this.children = []; this.text = ""; this.handlers = {}; this.hidden = false; this.checked = false; this.value = ""; this.attrs = {}; }
  set textContent(v) { this.text = v; this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join("|"); }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(n) { this.children.push(n); }
  replaceChildren() { this.children = []; }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  setAttribute(k, v) { this.attrs[k] = v; }
  all(tag) { return this.children.flatMap(c => [...(c.tag === tag ? [c] : []), ...c.all(tag)]); }
}
const IDS = ["viz-status", "viz-canvas", "viz-list", "viz-detail", "viz-cost", "viz-effects", "viz-reduce-motion",
  "viz-mode-3d", "viz-mode-list", "viz-refresh", "viz-rotate-left", "viz-rotate-right", "viz-zoom-in", "viz-zoom-out",
  "viz-pan-left", "viz-pan-right", "viz-pan-up", "viz-pan-down", "viz-evidence-data",
  "viz-search", "viz-frame-measure", "viz-frame-metric",
  ...["organization", "projects", "tasks", "workflows", "providers", "capabilities", "resources", "knowledge"].map(layer => `viz-layer-${layer}`)];
const setup = () => {
  const els = Object.fromEntries(IDS.map(id => [id, new El()]));
  els["viz-effects"].checked = true;
  for (const id of IDS.filter(id => id.startsWith("viz-layer-"))) els[id].checked = true;
  return { els, doc: { getElementById: id => els[id], createElement: tag => new El(tag) } };
};
const ok = body => ({ ok: true, status: 200, json: async () => body });
const route = (state = "review") => async url => {
  if (url.includes("structure")) return ok(structure);
  if (url.includes("workflows")) return ok(workflows(state));
  if (url === "/api/models") return ok({ items: [{ agent_id: "w1", provider_id: "local", model_id: "qwen" }] });
  if (url === "/api/system/monitor") return ok({ observed_at: "T", resource_capacities: [
    { scope: "model", provider_id: "local", model_id: "qwen", allocated: 1, limit: 2, remaining: 1 },
  ] });
  if (url === "/api/status") return ok({ corporation: { id: "corp" } });
  if (url.startsWith("/api/memory?")) return ok({ items: [{ id: "knowledge", scope: "corporation", type: "summary",
    created_at: "published-time", expires_at: "expiry",
    provenance: { source_scope: "project", source_scope_id: "p1", source_reference: "task-1", source_created_at: "source-time" } }] });
  return { ok: false, status: 404 };
};
const fakeView = log => () => ({
  setModel: (m, o) => log.push(["model", m.nodes.length, o.effects]), select: id => log.push(["select", id]),
  pulse: ids => log.push(["pulse", ...ids]), rotate: d => log.push(["rotate", d]), resize() {}, pick: () => "wi:a",
  tilt: d => log.push(["tilt", d]), zoom: d => log.push(["zoom", d]), pan: (x, y) => log.push(["pan", x, y]),
  renderFrame: () => log.push(["frame"]),
  cost: () => ({ average: 1.5, samples: 3 }),
});

const corporationMapRoute = async url => {
  const data = {
    "/api/structure-map": { generated_at: "org-time", positions: [{ id: "position-1", title: "Builder", active: true,
      reporting_state: "root", employee: { state: "assigned", id: "employee-1", name: "Dev", role: "Developer" },
      agent: { state: "assigned", id: "agent-1", name: "Builder Agent" } }] },
    "/api/employees": { items: [{ id: "employee-1", name: "Dev", role: "Developer", agent_id: "agent-1" }] },
    "/api/projects": { items: [{ id: "project-1", name: "Website", status: "active" }] },
    "/api/tasks": { items: [{ id: "task-1", title: "Build page", status: "pending", project_id: "project-1", assigned_agent: "agent-1" }] },
    "/api/agents": { items: [{ id: "agent-1", name: "Builder Agent", role: "Developer", capabilities: ["code-review"] }] },
    "/api/providers": { items: [{ id: "local", type: "ollama" }] },
    "/api/models": { items: [{ agent_id: "agent-1", provider_id: "local", model_id: "small-model" }] },
    "/api/local/workflows/map": { generated_at: "flow-time", workflows: [{ id: "flow-1", title: "Review", state: "active", nodes: [
      { id: "work-1", role: "reviewer", state: "running", response_state: "not recorded", agent_id: "agent-1", agent_visibility: "available" },
    ], operational_edges: [] }] },
    "/api/system/monitor": { observed_at: "resource-time", resource_capacities: [
      { scope: "model", provider_id: "local", model_id: "small-model", allocated: 1, limit: 2, remaining: 1 },
    ] },
    "/api/status": { corporation: { id: "corp", name: "Core" } },
  };
  if (url.startsWith("/api/memory?")) return ok({ items: [{ id: "memory-1", scope: "corporation", type: "summary", expires_at: "future",
    provenance: { source_scope: "project", source_scope_id: "project-1", source_reference: "project-1" } }] });
  return url in data ? ok(data[url]) : { ok: false, status: 404 };
};

test("interactive map uses separate authorized snapshots, source-backed layers and actionable selection", async () => {
  const { els, doc } = setup();
  const requests = [];
  const log = [];
  const fetchImpl = async (url, options) => { requests.push([url, options]); return corporationMapRoute(url); };
  const api = await mountVisualization({ documentRef: doc, fetchImpl, loadThree: async () => ({}),
    createView: fakeView(log), matchMedia: () => ({ matches: false }) });
  assert.ok(requests.some(([url]) => url === "/api/projects"));
  assert.ok(requests.some(([url]) => url === "/api/tasks"));
  assert.ok(requests.some(([url]) => url === "/api/agents"));
  assert.ok(requests.every(([, options]) => options.credentials === "same-origin" && options.cache === "no-store"));
  assert.match(els["viz-status"].textContent, /independent on-demand snapshots/);
  assert.match(els["viz-status"].textContent, /Department records are not exposed/);
  assert.match(els["viz-list"].textContent, /belongs to project: task:task-1 -> project:project-1/);
  assert.match(els["viz-list"].textContent, /source Project: knowledge:memory-1 -> project:project-1/);
  await api.select("task:task-1");
  assert.match(els["viz-detail"].textContent, /Source: \/api\/tasks/);
  assert.match(els["viz-detail"].textContent, /Recorded relationships: belongs to project/);
  els["viz-layer-projects"].checked = false;
  await els["viz-layer-projects"].handlers.change();
  assert.doesNotMatch(els["viz-list"].textContent, /project:project-1/);
  assert.doesNotMatch(els["viz-detail"].textContent, /project:project-1/);
  els["viz-search"].value = "task-1";
  await els["viz-search"].handlers.input();
  assert.match(els["viz-list"].textContent, /task:task-1/);
  assert.doesNotMatch(els["viz-list"].textContent, /project:project-1/);
  els["viz-zoom-in"].handlers.click();
  els["viz-pan-up"].handlers.click();
  assert.ok(log.some(item => item[0] === "zoom" && item[1] === -1));
  assert.ok(log.some(item => item[0] === "pan" && item[1] === 0 && item[2] === 1));
  els["viz-canvas"].handlers.pointerdown({ clientX: 0, clientY: 0, pointerId: 1, button: 0, shiftKey: false });
  els["viz-canvas"].handlers.pointermove({ clientX: 10, clientY: 4 });
  els["viz-canvas"].handlers.pointerup();
  assert.ok(log.some(item => item[0] === "rotate" && item[1] === 0.1));
  assert.ok(log.some(item => item[0] === "tilt" && item[1] === 0.04));
  els["viz-canvas"].handlers.pointerdown({ clientX: 0, clientY: 0, pointerId: 2, button: 0, shiftKey: true });
  els["viz-canvas"].handlers.pointermove({ clientX: 5, clientY: 5 });
  els["viz-canvas"].handlers.pointerup();
  assert.ok(log.some(item => item[0] === "pan" && item[1] === 0.2 && item[2] === -0.2));
});

test("frame pacing benchmark is opt-in, bounded to 300 intervals, and reports inference limits", async () => {
  const { els, doc } = setup();
  const callbacks = new Map();
  let nextId = 0;
  const api = await mountVisualization({ documentRef: doc, fetchImpl: corporationMapRoute, loadThree: async () => ({}),
    createView: fakeView([]), matchMedia: () => ({ matches: false }),
    requestFrame: callback => { const id = ++nextId; callbacks.set(id, callback); return id; },
    cancelFrame: id => callbacks.delete(id) });
  els["viz-frame-measure"].handlers.click();
  assert.equal(callbacks.size, 1);
  els["viz-frame-measure"].handlers.click();
  assert.equal(callbacks.size, 0);
  assert.match(els["viz-frame-metric"].textContent, /canceled/);
  els["viz-frame-measure"].handlers.click();
  let timestamp = 0;
  for (let index = 0; index < 301; index += 1) {
    const [id, callback] = callbacks.entries().next().value;
    callbacks.delete(id);
    callback(timestamp);
    timestamp += 16;
  }
  assert.equal(callbacks.size, 0);
  assert.match(els["viz-frame-metric"].textContent, /p95 16\.00 ms and p99 16\.00 ms over 300 frame intervals/);
  assert.match(els["viz-frame-metric"].textContent, /inference-load condition are unknown/);
  assert.equal(api.mode(), "3d");
});

test("3D is the default view with list as a selectable alternative", async () => {
  const { els, doc } = setup();
  const log = [];
  const api = await mountVisualization({ documentRef: doc, fetchImpl: route(), loadThree: async () => ({}), createView: fakeView(log), matchMedia: () => ({ matches: false }) });
  assert.equal(api.mode(), "3d");
  assert.equal(els["viz-canvas"].hidden, false);
  assert.equal(els["viz-list"].hidden, true);
  assert.match(els["viz-cost"].textContent, /1\.50 ms average over 3 synchronous renders/);
  await api.setMode("list");
  assert.equal(els["viz-list"].hidden, false);
  assert.equal(els["viz-list"].all("button").length, 9);
});

test("pulse only follows a verified state change and never under reduced motion", async () => {
  for (const [reduce, expected] of [[false, true], [true, false]]) {
    const { els, doc } = setup();
    const log = [];
    let state = "running";
    const api = await mountVisualization({ documentRef: doc, fetchImpl: async u => route(state)(u), loadThree: async () => ({}),
      createView: fakeView(log), matchMedia: () => ({ matches: false }) });
    els["viz-reduce-motion"].checked = reduce;
    els["viz-reduce-motion"].handlers.change();
    await api.refresh();
    assert.equal(log.some(e => e[0] === "pulse"), false, "no pulse without a change");
    state = "review";
    await api.refresh();
    assert.equal(log.some(e => e[0] === "pulse" && e[1] === "wi:w:a"), expected);
  }
});

test("reduced-motion preference starts in list mode without loading graphics", async () => {
  const { els, doc } = setup();
  let loaded = false;
  const api = await mountVisualization({ documentRef: doc, fetchImpl: route(), loadThree: async () => { loaded = true; return {}; },
    createView: fakeView([]), matchMedia: () => ({ matches: true }) });
  assert.equal(api.mode(), "list");
  assert.equal(loaded, false);
  assert.equal(els["viz-reduce-motion"].checked, true);
});

test("turning on reduced motion while viewing 3D switches to the equivalent list view", async () => {
  const { els, doc } = setup();
  const api = await mountVisualization({ documentRef: doc, fetchImpl: route(), loadThree: async () => ({}),
    createView: fakeView([]), matchMedia: () => ({ matches: false }) });
  assert.equal(api.mode(), "3d");
  els["viz-reduce-motion"].checked = true;
  els["viz-reduce-motion"].handlers.change();
  assert.equal(api.mode(), "list");
  assert.equal(els["viz-canvas"].hidden, true);
  assert.equal(els["viz-list"].hidden, false);
});

test("WebGL failure falls back to the list with a notice", async () => {
  const { els, doc } = setup();
  const api = await mountVisualization({ documentRef: doc, fetchImpl: route(), loadThree: async () => ({}),
    createView: () => { throw new Error("no webgl"); }, matchMedia: () => ({ matches: false }) });
  assert.equal(api.mode(), "list");
  assert.equal(els["viz-list"].hidden, false);
  assert.match(els["viz-status"].textContent, /3D graphics are unavailable/);
});

test("keyboard selection, effects toggle, forbidden and failed sections", async () => {
  const { els, doc } = setup();
  const log = [];
  const fetchImpl = async url => url.includes("structure") ? { ok: false, status: 403 } : ok(workflows("review"));
  const api = await mountVisualization({ documentRef: doc, fetchImpl, loadThree: async () => ({}), createView: fakeView(log), matchMedia: () => ({ matches: false }) });
  assert.match(els["viz-status"].textContent, /structure forbidden \(permission not granted\)/);
  api.select("wi:w:a");
  assert.match(els["viz-detail"].textContent, /Work item a/);
  els["viz-canvas"].handlers.keydown({ key: "ArrowRight", preventDefault() {} });
  assert.deepEqual(log.at(-1), ["select", "wi:w:b"]);
  els["viz-effects"].checked = false;
  els["viz-effects"].handlers.change();
  assert.deepEqual(log.at(-1), ["model", 3, false]);
  const down = setup();
  await mountVisualization({ documentRef: down.doc, fetchImpl: async () => { throw new Error("x"); }, loadThree: async () => ({}),
    createView: fakeView([]), matchMedia: () => ({ matches: false }) });
  assert.match(down.els["viz-status"].textContent, /disconnected/);
  assert.match(down.els["viz-list"].textContent, /No authorized records/);
});

test("shows only recorded Agent associations, provenance metadata, and software slot budgets", async () => {
  const { els, doc } = setup();
  const api = await mountVisualization({ documentRef: doc, fetchImpl: route(), loadThree: async () => ({}),
    createView: fakeView([]), matchMedia: () => ({ matches: false }) });
  await api.select("wi:w:a");
  assert.match(els["viz-detail"].textContent, /Recorded assignment for Agent w1: provider local, model qwen/);
  assert.match(els["viz-detail"].textContent, /1\/2 allocated/);
  assert.match(els["viz-evidence-data"].textContent, /project p1 \/ task-1/);
  assert.doesNotMatch(els["viz-evidence-data"].textContent, /content of knowledge/);
});

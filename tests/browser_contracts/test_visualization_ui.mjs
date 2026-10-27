// Browser fixtures collected and run by Python/CDP.
import { assert,test } from "/__contracts/harness.mjs";
import { buildCorporationMapModel, buildSceneModel, changedNodeIds, MAX_SCENE_EDGES, MAX_SCENE_NODES } from "../app/webui/static/scene-model.mjs";
import { mountVisualization } from "../app/webui/static/visualization.mjs";

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
  assert.deepEqual(changedNodeIds({ nodes: [{ id: "uncertain", state: "unknown" }] },
    { nodes: [{ id: "uncertain", state: "running" }] }), [], "unknown telemetry does not create an activity pulse");
  assert.deepEqual(changedNodeIds({ nodes: [{ id: "recorded", state: "running" }] },
    { nodes: [{ id: "recorded", state: "unknown" }] }), [], "missing telemetry does not create an activity pulse");
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
  assert.ok(model.nodes.every(node => [node.x, node.y, node.z].every(Number.isFinite)),
    "Every layer must provide finite coordinates to the real renderer");
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

test("reduced-motion preference starts in list mode without loading graphics", async () => {
  const { els, doc } = setup();
  let loaded = false;
  const api = await mountVisualization({ documentRef: doc, fetchImpl: route(), loadThree: async () => { loaded = true; return {}; },
    createView: fakeView([]), matchMedia: () => ({ matches: true }) });
  assert.equal(api.mode(), "list");
  assert.equal(loaded, false);
  assert.equal(els["viz-reduce-motion"].checked, true);
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

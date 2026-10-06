import assert from "node:assert/strict";
import test from "node:test";
import { buildSceneModel, changedNodeIds, MAX_SCENE_NODES } from "../app/webui/static/scene-model.mjs";
import { buildThreeScene, createThreeView } from "../app/webui/static/three-scene.mjs";
import { mountVisualization } from "../app/webui/static/visualization.mjs";
import * as THREE from "../app/webui/static/vendor/three/three.module.js";

const pos = (id, extra = {}) => ({
  id, title: id, active: true, revision: 1, reports_to_position_id: null, reporting_state: "root",
  employee: { state: "assigned" }, agent: { state: "assigned" }, ...extra,
});
const structure = { positions: [pos("boss"), pos("dev", { reports_to_position_id: "boss", reporting_state: "linked" })] };
const wi = (id, state) => ({ id, role: "worker", state, reason: "" });
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
  const FakeThree = { ...THREE, WebGLRenderer: class { setPixelRatio() {} setSize() {} render() { rendered.push(1); } dispose() {} } };
  const frames = [];
  let clock = 0;
  const view = createThreeView({ THREE: FakeThree, canvas: {}, requestFrame: f => frames.push(f), now: () => (clock += 2) });
  view.setModel(buildSceneModel(structure, workflows("review")));
  assert.equal(view.cost().samples, 1);
  view.pulse(["wi:a"]);
  assert.equal(frames.length, 1);
  view.pulse([]);
  assert.equal(frames.length, 1);
  view.dispose();
});

class El {
  constructor(tag = "div") { this.tag = tag; this.children = []; this.text = ""; this.handlers = {}; this.hidden = false; this.checked = false; this.attrs = {}; }
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
  "viz-mode-3d", "viz-mode-list", "viz-refresh", "viz-rotate-left", "viz-rotate-right"];
const setup = () => {
  const els = Object.fromEntries(IDS.map(id => [id, new El()]));
  els["viz-effects"].checked = true;
  return { els, doc: { getElementById: id => els[id], createElement: tag => new El(tag) } };
};
const ok = body => ({ ok: true, status: 200, json: async () => body });
const route = (state = "review") => async url => ok(url.includes("structure") ? structure : workflows(state));
const fakeView = log => () => ({
  setModel: (m, o) => log.push(["model", m.nodes.length, o.effects]), select: id => log.push(["select", id]),
  pulse: ids => log.push(["pulse", ...ids]), rotate: d => log.push(["rotate", d]), resize() {}, pick: () => "wi:a",
  cost: () => ({ average: 1.5, samples: 3 }),
});

test("3D is the default view with list as a selectable alternative", async () => {
  const { els, doc } = setup();
  const log = [];
  const api = await mountVisualization({ documentRef: doc, fetchImpl: route(), loadThree: async () => ({}), createView: fakeView(log), matchMedia: () => ({ matches: false }) });
  assert.equal(api.mode(), "3d");
  assert.equal(els["viz-canvas"].hidden, false);
  assert.equal(els["viz-list"].hidden, true);
  assert.match(els["viz-cost"].textContent, /1\.50 ms average over 3 renders/);
  await api.setMode("list");
  assert.equal(els["viz-list"].hidden, false);
  assert.equal(els["viz-list"].all("button").length, 4);
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
    assert.equal(log.some(e => e[0] === "pulse" && e[1] === "wi:a"), expected);
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
  await mountVisualization({ documentRef: doc, fetchImpl, loadThree: async () => ({}), createView: fakeView(log), matchMedia: () => ({ matches: false }) });
  assert.match(els["viz-status"].textContent, /structure forbidden \(permission not granted\)/);
  els["viz-canvas"].handlers.keydown({ key: "ArrowRight" });
  assert.deepEqual(log.at(-1), ["select", "wi:a"]);
  assert.match(els["viz-detail"].textContent, /Work item a/);
  els["viz-effects"].checked = false;
  els["viz-effects"].handlers.change();
  assert.deepEqual(log.at(-1), ["model", 2, false]);
  const down = setup();
  await mountVisualization({ documentRef: down.doc, fetchImpl: async () => { throw new Error("x"); }, loadThree: async () => ({}),
    createView: fakeView([]), matchMedia: () => ({ matches: false }) });
  assert.match(down.els["viz-status"].textContent, /disconnected/);
  assert.match(down.els["viz-list"].textContent, /No recorded positions/);
});
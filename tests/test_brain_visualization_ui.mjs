import assert from "node:assert/strict";
import test from "node:test";
import { layoutBrainGraph, recordLastBrainRetrieval, readLastBrainRetrieval } from "../app/webui/static/brain-graph.mjs";
import { mountBrainView } from "../app/webui/static/brain-view.mjs";
import { BRAIN_RENDER_FPS_CAP, BRAIN_RENDER_NODE_LIMIT, createBrainThreeView } from "../app/webui/static/brain-three.mjs";

test("Brain graph layout uses real groups and source edges, caps only the renderer", () => {
  const nodes = Array.from({ length: 400 }, (_, index) => ({ id: `n${index}`, kind: index ? "chunk" : "document", cluster: index % 2 ? "md" : "py" }));
  const graph = { nodes, edges: [{ from: "n0", to: "n1", kind: "same-source" }, { from: "n1", to: "n2", kind: "similarity" }] };
  const laidOut = layoutBrainGraph(graph);
  assert.equal(laidOut.nodes.length, BRAIN_RENDER_NODE_LIMIT);
  assert.equal(laidOut.allNodes.length, 400);
  assert.equal(laidOut.omitted, 80);
  assert.equal(laidOut.edges.length, 1);
  assert.equal(laidOut.basis, "Derived file-type/note groups");
  assert.ok(laidOut.allNodes.every(node => Number.isFinite(node.x) && Number.isFinite(node.y) && Number.isFinite(node.z)));
  assert.equal(BRAIN_RENDER_FPS_CAP, 24);
});

test("retrieval highlight persistence stores bounded chunk identifiers without content", () => {
  const entries = new Map();
  const storage = { setItem: (key, value) => entries.set(key, value), getItem: key => entries.get(key), removeItem: key => entries.delete(key) };
  assert.equal(recordLastBrainRetrieval(storage, { sources: [
    { chunk_reference: "m1#1", content: "private note text" }, { chunk_reference: "m2#2" },
  ] }), true);
  const raw = entries.get("ersel-brain-retrieval-v1");
  assert.doesNotMatch(raw, /private note text/);
  assert.deepEqual(readLastBrainRetrieval(storage), { retrieved: ["m1#1", "m2#2"], cited: ["m1#1", "m2#2"] });
  assert.equal(entries.has("ersel-brain-retrieval-v1"), false);
});

class Element {
  constructor(id = "") { this.id = id; this.children = []; this.listeners = {}; this.attributes = {}; this.text = ""; this.hidden = false; this.checked = false; this.value = ""; this.style = {}; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(item => item.textContent).join(""); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; this.text = ""; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getBoundingClientRect() { return { width: 720, height: 400 }; }
}
function fakeDocument() {
  const names = ["brain-map-status", "brain-map-list", "brain-map-ingestion", "brain-map-canvas-wrap", "brain-map-view-toggle", "brain-map-reduced-motion",
    "brain-map-refresh", "brain-map-detail-title", "brain-map-detail-text", "brain-map-canvas", "brain-map-frame-stats"];
  const elements = Object.fromEntries(names.map(name => [name, new Element(name)]));
  const listeners = {};
  return { elements, ref: { visibilityState: "visible", getElementById: id => elements[id], createElement: tag => new Element(tag),
    addEventListener: (name, cb) => { listeners[name] = cb; }, removeEventListener: name => { delete listeners[name]; }, dispatchEvent(event) { listeners[event.type]?.(event); } } };
}

test("Brain page exposes a complete keyboard list and loads selected text only on selection", async () => {
  const { elements, ref } = fakeDocument();
  elements["brain-map-canvas-wrap"].hidden = true;
  const calls = [];
  const fetchImpl = async path => {
    calls.push(path);
    return { ok: true, json: async () => path.includes("/graph") ? { nodes: [
      { id: "document:m1", kind: "document", label: "notes.md", state: "ready", cluster: "md" },
      { id: "chunk:m1#1", kind: "chunk", label: "Chunk 1", position: 1, state: "ready", cluster: "md" },
    ], edges: [{ from: "document:m1", to: "chunk:m1#1", kind: "same-source" }], basis: "Derived file-type/note groups" }
      : { content: "authorized text", source_reference: "notes.md" } };
  };
  const view = mountBrainView({ documentRef: ref, fetchImpl, sessionStorage: null, reducedMotion: true });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(elements["brain-map-list"].children.length, 2);
  assert.equal(elements["brain-map-canvas-wrap"].hidden, true);
  assert.equal(elements["brain-map-list"].hidden, false);
  assert.equal(calls.some(path => path.includes("/node?")), false);
  const select = elements["brain-map-list"].children[1].children[0];
  select.listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(elements["brain-map-detail-text"].textContent, "authorized text");
  assert.ok(calls.at(-1).includes("node_id=chunk%3Am1%231"));
  view.dispose();
});

test("reduced motion and renderer failures preserve the complete list fallback", async () => {
  const { elements, ref } = fakeDocument();
  const view = mountBrainView({ documentRef: ref, fetchImpl: async () => ({ ok: true, json: async () => ({ nodes: [], edges: [] }) }),
    sessionStorage: null, reducedMotion: true, importThree: async () => { throw new Error("WebGL unavailable"); } });
  await new Promise(resolve => setTimeout(resolve, 0));
  elements["brain-map-view-toggle"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(elements["brain-map-status"].textContent, /Reduced motion/);
  assert.equal(elements["brain-map-list"].hidden, false);
  view.dispose();
});

test("ingestion events create actual temporary graph nodes while the keyboard list stays visible", async () => {
  const { elements, ref } = fakeDocument();
  let renderedGraph = null;
  const renderer = { setGraph: graph => { renderedGraph = graph; }, setHighlights() {}, setReducedMotion() {}, resize() {}, select() {}, dispose() {} };
  const view = mountBrainView({ documentRef: ref, fetchImpl: async () => ({ ok: true, json: async () => ({ nodes: [], edges: [] }) }),
    sessionStorage: null, reducedMotion: false, createRenderer: () => renderer });
  await new Promise(resolve => setTimeout(resolve, 0));
  elements["brain-map-view-toggle"].listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(elements["brain-map-list"].hidden, false);
  ref.dispatchEvent({ type: "brain:ingestion", detail: { id: "upload:one", label: "real.md", state: "extracting" } });
  assert.ok(renderedGraph.allNodes.some(node => node.id === "upload:one" && node.kind === "ingestion"));
  assert.match(elements["brain-map-ingestion"].textContent, /real\.md.*extracting/);
  ref.dispatchEvent({ type: "brain:ingestion", detail: { id: "upload:one", label: "real.md", state: "ready" } });
  assert.match(elements["brain-map-ingestion"].textContent, /ready/);
  view.dispose();
});

function fakeThree() {
  class Vector { set() {} setScalar() {} }
  class Group { constructor() { this.rotation = { y: 0 }; } add() {} remove() {} }
  class Renderer { constructor() { this.frames = 0; } setPixelRatio() {} setSize() {} render() { this.frames++; } getContext() { return { isContextLost: () => false }; } dispose() {} }
  class Scene { add() {} }
  class Camera { constructor() { this.position = { set() {} }; } updateProjectionMatrix() {} }
  class Geometry { dispose() {} }
  class Material { dispose() {} }
  class Object { constructor() { this.position = new Vector(); this.scale = new Vector(); this.matrix = {}; } updateMatrix() {} }
  class Color { setHex() {} }
  class Instances { constructor() { this.instanceMatrix = { setUsage() {} }; } setMatrixAt() {} setColorAt() {} }
  class Raycaster { setFromCamera() {} intersectObject() { return []; } }
  class Buffer { setAttribute() {} dispose() {} }
  class Lines { constructor() { this.geometry = new Buffer(); this.material = new Material(); } }
  return { WebGLRenderer: Renderer, Scene, Color, PerspectiveCamera: Camera, Group, IcosahedronGeometry: Geometry,
    MeshBasicMaterial: Material, InstancedMesh: Instances, Object3D: Object, Raycaster, BufferGeometry: Buffer,
    Float32BufferAttribute: class {}, LineBasicMaterial: Material, LineSegments: Lines, DynamicDrawUsage: 1 };
}
function rafHarness() {
  let id = 0; const queued = new Map();
  return { request: callback => { queued.set(++id, callback); return id; }, cancel: key => queued.delete(key),
    step(timestamp) { const first = queued.entries().next().value; if (!first) return false; queued.delete(first[0]); first[1](timestamp); return true; },
    get size() { return queued.size; } };
}

test("Three.js renderer caps frames, pauses while hidden, and falls back under slow frame timing", () => {
  const raf = rafHarness(); let time = 0; let fallbackReason = "";
  const listeners = {};
  const doc = { visibilityState: "visible", addEventListener: (name, cb) => { listeners[name] = cb; },
    removeEventListener: name => { delete listeners[name]; } };
  const canvas = { addEventListener() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 600, height: 400 }) };
  const view = createBrainThreeView({ THREE: fakeThree(), canvas, documentRef: doc, requestFrame: raf.request,
    cancelFrame: raf.cancel, now: () => time, onFallback: reason => { fallbackReason = reason; } });
  view.setGraph({ nodes: [{ id: "document:m", kind: "document", x: 0, y: 0, z: 0 }], edges: [] });
  for (let frame = 1; frame <= 60; frame++) { time = frame * (1000 / 60); assert.equal(raf.step(time), true); }
  const rendered = view.cost();
  assert.ok(rendered.samples <= BRAIN_RENDER_FPS_CAP);
  assert.ok(rendered.samples > 10);
  doc.visibilityState = "hidden"; listeners.visibilitychange();
  assert.equal(raf.size, 0);
  doc.visibilityState = "visible"; listeners.visibilitychange();
  assert.equal(raf.size, 1);
  view.dispose();

  const slowRaf = rafHarness(); time = 0; fallbackReason = "";
  const slow = createBrainThreeView({ THREE: fakeThree(), canvas, documentRef: doc, requestFrame: slowRaf.request,
    cancelFrame: slowRaf.cancel, now: () => time, onFallback: reason => { fallbackReason = reason; } });
  slow.setGraph({ nodes: [], edges: [] });
  for (let frame = 1; frame <= 60 && !fallbackReason; frame++) { time = frame * 100; slowRaf.step(time); }
  assert.match(fallbackReason, /frame interval p95/);
  assert.equal(slowRaf.size, 0);
  slow.dispose();
});

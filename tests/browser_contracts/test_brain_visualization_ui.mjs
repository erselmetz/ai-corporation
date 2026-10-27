// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { layoutBrainGraph, recordLastBrainRetrieval, readLastBrainRetrieval } from "../app/webui/static/brain-graph.mjs";
import { mountBrainView } from "../app/webui/static/brain-view.mjs";
// Historical bounds are kept explicit here; renderer implementation is retired in 227.
const BRAIN_RENDER_NODE_LIMIT = 320;
const BRAIN_RENDER_FPS_CAP = 24;

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

// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { buildSageCoreModel, drawSageCore, layoutSageCore, mountSageCore,
  SAGE_CORE_FRAME_BUDGET_MS, SAGE_CORE_MAX_FPS } from "../app/webui/static/sage-core.mjs";

const fixture = () => ({
  observed_at: "2026-10-21T00:00:00+00:00",
  nodes: [
    { id: "researcher", name: "Researcher", role: "Find sources", provider: "ollama", model: "small", state: "idle" },
    { id: "local_worker", name: "Coordinator", role: "Routes requests", provider: "ollama", model: "small", state: "working", built_in_key: "coordinator" },
  ],
  handoffs: [{ id: "trace-1", from: "local_worker", to: "researcher", state: "completed", recorded_at: "now" },
    { id: "invented", from: "local_worker", to: "missing-agent", state: "completed" }],
  source_links: [{ id: "trace-source", agent_id: "researcher", source_id: "memory-1", label: "notes.md" }],
});

function makeContext() {
  const gradient = { addColorStop() {} };
  const target = { calls: new Map() };
  return new Proxy(target, { get(object, key) { if (key in object) return object[key]; return key === "createRadialGradient" ? () => gradient : () => object.calls.set(key, (object.calls.get(key) ?? 0) + 1); },
    set(target, key, value) { target[key] = value; return true; } });
}

class FakeNode {
  constructor(id = "", context = null) {
    this.id = id; this.context = context; this.children = []; this.listeners = new Map();
    this.attributes = {}; this.hidden = false; this.disabled = false; this.checked = false;
    this.clientWidth = 800; this.clientHeight = 560; this.width = 0; this.height = 0;
    this.textContent = ""; this.value = ""; this.href = "";
  }
  getContext(type) { return type === "2d" ? this.context : null; }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = [...items]; }
  getBoundingClientRect() { return { left: 0, top: 0, width: this.clientWidth, height: this.clientHeight }; }
  click(event = {}) { this.listeners.get("click")?.({ preventDefault() {}, ...event }); }
}

function setup({ snapshot = fixture(), context = makeContext(), slowDraw = false,
  reducedMotion = false, status = 200, responseSequence = [] } = {}) {
  const ids = ["sage-core-canvas", "sage-core-state", "sage-core-accessible-list", "sage-core-map-mode",
    "sage-core-list-mode", "sage-core-reduced-motion", "sage-core-detail-title", "sage-core-detail-content",
    "sage-core-refresh"];
  const elements = Object.fromEntries(ids.map(id => [id, new FakeNode(id, id === "sage-core-canvas" ? context : null)]));
  const documentListeners = new Map(); const frames = new Map(); let frameSequence = 0; let wall = 0;
  const documentRef = { visibilityState: "visible", getElementById: id => elements[id],
    createElement: tag => new FakeNode(tag), addEventListener: (name, callback) => documentListeners.set(name, callback) };
  const windowRef = { devicePixelRatio: 1, matchMedia: () => ({ matches: reducedMotion, addEventListener() {} }),
    requestAnimationFrame: callback => { const id = ++frameSequence; frames.set(id, callback); return id; },
    cancelAnimationFrame: id => frames.delete(id), setTimeout: () => ++frameSequence, clearTimeout() {} };
  const fetchImpl = async () => {
    const current = responseSequence.shift() ?? { status, snapshot };
    return { ok: current.status === 200, status: current.status, json: async () => current.status === 200 ? current.snapshot : {} };
  };
  let timeCalls = 0;
  const controller = mountSageCore({ documentRef, windowRef, fetchImpl,
    now: () => { timeCalls++; wall += slowDraw ? 40 : 1; return wall; } });
  return { controller, elements, documentRef, documentListeners, frames, windowRef,
    get timeCalls() { return timeCalls; },
    runFrame(timestamp) { const next = [...frames.entries()][0]; if (!next) return false; frames.delete(next[0]); next[1](timestamp); return true; } };
}

test("Sage Core only maps recorded Agents and current trace edges with stable positions", () => {
  const model = buildSageCoreModel(fixture());
  assert.deepEqual(model.nodes.map(node => node.id), ["researcher", "local_worker"]);
  assert.deepEqual(model.handoffs.map(edge => edge.id), ["trace-1"]);
  assert.deepEqual(model.sourceLinks.map(edge => edge.sourceId), ["memory-1"]);
  const first = layoutSageCore(model.nodes, 800, 560);
  const reordered = layoutSageCore([...model.nodes].reverse(), 800, 560);
  assert.deepEqual(first.get("researcher"), reordered.get("researcher"));
  assert.deepEqual(first.get("local_worker"), { x: 400, y: 280, radius: 25 });
  assert.equal(buildSageCoreModel({ nodes: [{ id: "x", name: "X", state: "telemetry-invented" }] }).nodes[0].state, "unknown");
});

test("original canvas rendering draws only existing nodes and links without random decorations", () => {
  const model = buildSageCoreModel(fixture()); const positions = drawSageCore(makeContext(), model, 800, 560, 120, "researcher");
  assert.deepEqual([...positions.keys()].sort(), ["local_worker", "researcher"]);
  assert.equal(SAGE_CORE_MAX_FPS, 24);
  assert.ok(SAGE_CORE_FRAME_BUDGET_MS > 0 && SAGE_CORE_FRAME_BUDGET_MS < 50);
});

test("Agent details and equivalent keyboard-accessible list are available", async () => {
  const ui = setup(); await ui.controller.initialLoad;
  assert.equal(ui.controller.mode, "map");
  ui.elements["sage-core-list-mode"].click();
  assert.equal(ui.elements["sage-core-accessible-list"].hidden, false);
  assert.equal(ui.elements["sage-core-accessible-list"].children.length, 4, "two Agents, one handoff and one Brain link");
  ui.elements["sage-core-accessible-list"].children[0].children[0].click();
  assert.equal(ui.elements["sage-core-detail-title"].textContent, "Researcher");
  assert.match(ui.elements["sage-core-detail-content"].children.map(child => child.textContent).join(" "), /ollama \/ small/);
  assert.equal(ui.elements["sage-core-detail-content"].children.at(-1).href, "/ui/agents");
});

test("reduced motion and missing canvas select the accessible list", async () => {
  const reduced = setup({ reducedMotion: true }); await reduced.controller.initialLoad;
  assert.equal(reduced.elements["sage-core-reduced-motion"].checked, true);
  assert.equal(reduced.controller.mode, "list");
  const unsupported = setup({ context: null }); await unsupported.controller.initialLoad;
  assert.equal(unsupported.controller.mode, "list");
  assert.equal(unsupported.elements["sage-core-map-mode"].disabled, true);
});

test("hidden page stops animation and poll timer; visibility restores a fresh snapshot", async () => {
  const ui = setup(); await ui.controller.initialLoad;
  assert.equal(ui.controller.animationActive, true);
  ui.documentRef.visibilityState = "hidden";
  ui.documentListeners.get("visibilitychange")();
  assert.equal(ui.controller.animationActive, false);
  ui.documentRef.visibilityState = "visible";
  ui.documentListeners.get("visibilitychange")();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.controller.animationActive, true);
});

test("repeated over-budget draws automatically switch to the accessible list", async () => {
  const ui = setup({ slowDraw: true }); await ui.controller.initialLoad;
  ui.runFrame(100); ui.runFrame(150); ui.runFrame(200);
  assert.equal(ui.controller.mode, "list");
  assert.match(ui.elements["sage-core-state"].textContent, /frame budget/);
});

test("working-state animation respects the 24 FPS frame interval", async () => {
  const ui = setup(); await ui.controller.initialLoad;
  ui.runFrame(100);
  const callsAfterFrame = ui.timeCalls;
  ui.runFrame(110);
  assert.equal(ui.timeCalls, callsAfterFrame, "a frame inside the 24 FPS interval skips canvas drawing");
});

test("failed and unauthorized snapshots clear stale Agent nodes", async () => {
  const ui = setup({ status: 403 }); await ui.controller.initialLoad;
  assert.equal(ui.controller.model.nodes.length, 0);
  assert.match(ui.elements["sage-core-state"].textContent, /Agent read and chat read permission/);
});

test("failed refresh clears the prior canvas snapshot instead of leaving stale Agent signals visible", async () => {
  const context = makeContext();
  const ui = setup({ context, responseSequence: [{ status: 200, snapshot: fixture() }, { status: 403 }] });
  await ui.controller.initialLoad;
  const before = context.calls.get("clearRect");
  await ui.controller.refresh();
  assert.equal(ui.controller.model.nodes.length, 0);
  assert.ok(context.calls.get("clearRect") > before);
});

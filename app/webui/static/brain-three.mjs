export const BRAIN_RENDER_FPS_CAP = 24;
export const BRAIN_RENDER_NODE_LIMIT = 320;
const FRAME_BUDGET_MS = 1000 / BRAIN_RENDER_FPS_CAP;
const FALLBACK_INTERVAL_P95_MS = 84;

export function createBrainThreeView({ THREE, canvas, onStats = () => {}, onFallback = () => {},
  onSelect = () => {},
  requestFrame = globalThis.requestAnimationFrame?.bind(globalThis),
  cancelFrame = globalThis.cancelAnimationFrame?.bind(globalThis),
  now = () => globalThis.performance.now(), documentRef = globalThis.document } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "low-power" });
  renderer.setPixelRatio(1);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070d18);
  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  const root = new THREE.Group(); scene.add(root);
  const geometry = new THREE.IcosahedronGeometry(1, 1);
  const material = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const instances = new THREE.InstancedMesh(geometry, material, BRAIN_RENDER_NODE_LIMIT);
  instances.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  root.add(instances);
  let lines = null;
  let graph = { nodes: [], edges: [] };
  let nodeIndexes = new Map();
  let selectedId = null;
  let retrieved = new Set();
  let cited = new Set();
  let ingesting = new Map();
  let reducedMotion = false;
  let visible = documentRef?.visibilityState !== "hidden";
  let rafId = null;
  let lastFrameAt = -Infinity;
  let previousFrameAt = null;
  let intervals = [];
  let renderTimes = [];
  let dragState = null;
  let fallbackSent = false;
  const scratch = new THREE.Object3D();
  const color = new THREE.Color();
  const raycaster = new THREE.Raycaster();

  const stateColor = node => {
    if (cited.has(node.id)) return 0xf5c451;
    if (retrieved.has(node.id)) return 0x40d7f3;
    if (ingesting.has(node.id)) return 0x61e6a6;
    return node.kind === "document" ? 0x9b8afb : 0x6c8cf3;
  };
  function syncInstances(time = 0) {
    nodeIndexes = new Map();
    graph.nodes.slice(0, BRAIN_RENDER_NODE_LIMIT).forEach((node, index) => {
      const base = node.kind === "document" ? 0.12 : 0.075;
      const active = ingesting.has(node.id) ? Math.sin(time / 170) * 0.22
        : retrieved.has(node.id) && !reducedMotion ? Math.sin(time / 230) * 0.12 : 0;
      const selected = node.id === selectedId ? 1.28 : 1;
      const scale = (base + active * base) * selected;
      scratch.position.set(node.x, node.y, node.z);
      scratch.scale.setScalar(scale);
      scratch.updateMatrix(); instances.setMatrixAt(index, scratch.matrix);
      color.setHex(stateColor(node)); instances.setColorAt(index, color);
      nodeIndexes.set(node.id, index);
    });
    instances.count = Math.min(graph.nodes.length, BRAIN_RENDER_NODE_LIMIT);
    instances.instanceMatrix.needsUpdate = true;
    if (instances.instanceColor) instances.instanceColor.needsUpdate = true;
  }
  function renderOnce(time = now()) {
    const started = now();
    syncInstances(time);
    renderer.render(scene, camera);
    const duration = Math.max(0, now() - started);
    renderTimes.push(duration); if (renderTimes.length > 60) renderTimes.shift();
    return duration;
  }
  const percentile = (values, p) => values.length
    ? [...values].sort((a, b) => a - b)[Math.min(values.length - 1, Math.floor((values.length - 1) * p))] : 0;
  function checkPerformance() {
    if (intervals.length < 48 || fallbackSent) return;
    const p95 = percentile(intervals, 0.95);
    const renderP95 = percentile(renderTimes, 0.95);
    if (p95 > FALLBACK_INTERVAL_P95_MS || renderP95 > FRAME_BUDGET_MS) {
      fallbackSent = true;
      stop();
      onFallback(`3D frame interval p95 ${p95.toFixed(0)} ms; render p95 ${renderP95.toFixed(1)} ms. Switched to the complete list view.`);
    }
  }
  function frame(timestamp) {
    rafId = null;
    if (!visible || reducedMotion || !requestFrame) return;
    if (previousFrameAt !== null) {
      const interval = timestamp - previousFrameAt;
      if (interval < 500) { intervals.push(interval); if (intervals.length > 90) intervals.shift(); }
    }
    previousFrameAt = timestamp;
    if (timestamp - lastFrameAt >= FRAME_BUDGET_MS) {
      lastFrameAt = timestamp;
      renderOnce(timestamp);
      if (intervals.length && intervals.length % 30 === 0) {
        onStats({ fps: Math.min(BRAIN_RENDER_FPS_CAP, 1000 / percentile(intervals.slice(-30), 0.5)),
          interval_p95_ms: percentile(intervals.slice(-30), 0.95),
          render_cpu_ms: renderTimes.at(-1) ?? 0, samples: intervals.length });
      }
      checkPerformance();
    }
    if (visible && !reducedMotion && !fallbackSent) rafId = requestFrame(frame);
  }
  function start() {
    if (rafId === null && visible && !reducedMotion && requestFrame && !fallbackSent) {
      previousFrameAt = null;
      rafId = requestFrame(frame);
    }
  }
  function stop() {
    if (rafId !== null) cancelFrame?.(rafId);
    rafId = null; previousFrameAt = null;
  }
  function rebuildEdges() {
    if (lines) { root.remove(lines); lines.geometry.dispose(); lines.material.dispose(); lines = null; }
    const positions = [];
    const indices = new Map(graph.nodes.slice(0, BRAIN_RENDER_NODE_LIMIT).map(node => [node.id, node]));
    for (const edge of graph.edges.slice(0, 480)) {
      if (edge.kind !== "same-source") continue;
      const from = indices.get(edge.from), to = indices.get(edge.to);
      if (from && to) positions.push(from.x, from.y, from.z, to.x, to.y, to.z);
    }
    if (!positions.length) return;
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x314b73, transparent: true, opacity: 0.72 });
    lines = new THREE.LineSegments(edgeGeometry, edgeMaterial); root.add(lines);
  }
  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1;
    const y = -((event.clientY - rect.top) / Math.max(1, rect.height)) * 2 + 1;
    raycaster.setFromCamera({ x, y }, camera);
    const hit = raycaster.intersectObject(instances, false)[0];
    if (hit?.instanceId !== undefined) return graph.nodes[hit.instanceId]?.id || null;
    return null;
  }
  canvas.addEventListener("pointerdown", event => {
    dragState = { x: event.clientX, rotation: root.rotation.y };
    canvas.setPointerCapture?.(event.pointerId);
  });
  canvas.addEventListener("pointermove", event => {
    if (!dragState || reducedMotion) return;
    root.rotation.y = dragState.rotation + (event.clientX - dragState.x) * 0.006;
    renderOnce();
  });
  const selectNode = id => { if (id) { selectedId = id; onSelect(id); renderOnce(); } };
  canvas.addEventListener("pointerup", event => {
    if (dragState && Math.abs(event.clientX - dragState.x) < 4) {
      selectNode(pick(event));
    }
    dragState = null; renderOnce();
  });
  canvas.addEventListener("pointercancel", () => { dragState = null; });
  canvas.addEventListener("wheel", event => {
    event.preventDefault();
    camera.position.z = Math.max(5, Math.min(16, camera.position.z + Math.sign(event.deltaY) * 0.5));
    renderOnce();
  }, { passive: false });
  const onVisibility = () => { visible = documentRef?.visibilityState !== "hidden"; if (visible) start(); else stop(); };
  documentRef?.addEventListener("visibilitychange", onVisibility);
  try {
    const gl = renderer.getContext();
    if (!gl || gl.isContextLost?.()) throw new Error("WebGL context unavailable");
  } catch {
    renderer.dispose(); throw new Error("WebGL is unavailable on this device");
  }
  function setGraph(next) {
    graph = { nodes: Array.isArray(next?.nodes) ? next.nodes.slice(0, BRAIN_RENDER_NODE_LIMIT) : [],
      edges: Array.isArray(next?.edges) ? next.edges.slice(0, 480) : [] };
    rebuildEdges(); renderOnce(); start();
  }
  function setHighlights(nextRetrieved = [], nextCited = [], nextIngesting = []) {
    retrieved = new Set(nextRetrieved); cited = new Set(nextCited);
    ingesting = new Map(nextIngesting.map(node => [node.id, node]));
    renderOnce(); start();
  }
  function setReducedMotion(value) { reducedMotion = value === true; if (reducedMotion) stop(); else start(); renderOnce(); }
  function resize(width, height) {
    const w = Math.max(1, width), h = Math.max(1, height);
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); renderOnce();
  }
  function select(id) { selectedId = id; renderOnce(); }
  function dispose() {
    stop(); documentRef?.removeEventListener("visibilitychange", onVisibility);
    if (lines) { root.remove(lines); lines.geometry.dispose(); lines.material.dispose(); }
    geometry.dispose(); material.dispose(); renderer.dispose();
  }
  return { setGraph, setHighlights, setReducedMotion, resize, select, renderOnce, dispose,
    cost: () => ({ samples: renderTimes.length, render_cpu_ms: renderTimes.at(-1) ?? 0,
      interval_p95_ms: percentile(intervals, 0.95), fps: intervals.length ? Math.min(BRAIN_RENDER_FPS_CAP, 1000 / percentile(intervals, 0.5)) : null }) };
}

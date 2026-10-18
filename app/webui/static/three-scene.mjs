import { colorFor, MAX_SCENE_EDGES, MAX_SCENE_NODES } from "./scene-model.mjs";

const EDGE_COLORS = { reporting: 0x818cf8, handoff: 0x22d3ee, delegation: 0xfbbf24 };
export const GLOBE_NODE_RADIUS = 6;
export const MAX_RENDER_FPS = 30;
const GLOBE_SURFACE_RADIUS = 5.7;
const MIN_RENDER_INTERVAL_MS = 1000 / MAX_RENDER_FPS;

/** Assign stable, evenly distributed positions to the actual records in the supplied model. */
export function projectGlobeNodes(nodes, radius = GLOBE_NODE_RADIUS) {
  const ordered = [...nodes].sort((left, right) => {
    const a = String(left.id ?? ""), b = String(right.id ?? "");
    return a < b ? -1 : a > b ? 1 : 0;
  });
  const locations = new Map();
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  ordered.forEach((node, index) => {
    const y = ordered.length ? 1 - 2 * (index + 0.5) / ordered.length : 0;
    const horizontal = Math.sqrt(Math.max(0, 1 - y * y));
    const angle = goldenAngle * index;
    locations.set(node.id, {
      x: radius * Math.cos(angle) * horizontal,
      y: radius * y,
      z: radius * Math.sin(angle) * horizontal,
    });
  });
  return locations;
}

export function buildThreeScene(THREE, model, { effects = true } = {}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050a14);
  const group = new THREE.Group();
  scene.add(group);
  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
  camera.position.set(2, 3, 14);
  camera.lookAt(2, -2, 0);
  scene.add(new THREE.AmbientLight(0xffffff, 1.2));
  const sphere = new THREE.SphereGeometry(0.5, 16, 12);
  const halo = new THREE.RingGeometry(0.7, 0.78, 32);
  const meshes = new Map();
  const disposables = [sphere, halo];
  const globe = new THREE.Mesh(new THREE.SphereGeometry(GLOBE_SURFACE_RADIUS, 24, 16),
    new THREE.MeshBasicMaterial({ color: 0x1e3a5f, wireframe: true, transparent: true, opacity: 0.24 }));
  group.add(globe);
  disposables.push(globe.geometry, globe.material);
  const boundedNodes = model.nodes.slice(0, MAX_SCENE_NODES);
  const nodeIds = new Set(boundedNodes.map(node => node.id));
  const boundedEdges = model.edges.filter(edge => nodeIds.has(edge.from) && nodeIds.has(edge.to)).slice(0, MAX_SCENE_EDGES);
  const locations = projectGlobeNodes(boundedNodes);
  const positionedNodes = boundedNodes.map(node => ({ ...node, ...locations.get(node.id) }));
  for (const node of positionedNodes) {
    const material = new THREE.MeshBasicMaterial({ color: colorFor(node.state) });
    disposables.push(material);
    const mesh = new THREE.Mesh(sphere, material);
    mesh.position.set(node.x, node.y, node.z);
    mesh.userData = { id: node.id, baseScale: 1 };
    group.add(mesh);
    meshes.set(node.id, mesh);
    if (effects) {
      const ringMaterial = new THREE.MeshBasicMaterial({ color: colorFor(node.state), side: THREE.DoubleSide });
      disposables.push(ringMaterial);
      const ring = new THREE.Mesh(halo, ringMaterial);
      ring.position.copy(mesh.position);
      group.add(ring);
    }
  }
  for (const edge of boundedEdges) {
    const a = meshes.get(edge.from);
    const b = meshes.get(edge.to);
    if (!a || !b) continue;
    const geometry = new THREE.BufferGeometry().setFromPoints([a.position, b.position]);
    const material = new THREE.LineBasicMaterial({ color: EDGE_COLORS[edge.kind] ?? 0x64748b });
    disposables.push(geometry, material);
    group.add(new THREE.Line(geometry, material));
  }
  if (effects) {
    const grid = new THREE.GridHelper(40, 40, 0x1e3a5f, 0x0f2038);
    grid.position.y = -9;
    group.add(grid);
    disposables.push(grid.geometry, grid.material);
  }
  return { scene, camera, group, meshes, nodes: positionedNodes, edges: boundedEdges, dispose: () => disposables.forEach(d => d.dispose?.()) };
}

export function createThreeView({
  THREE, canvas, requestFrame = globalThis.requestAnimationFrame?.bind(globalThis),
  now = () => globalThis.performance.now(),
  scheduleTimeout = globalThis.setTimeout?.bind(globalThis),
  cancelTimeout = globalThis.clearTimeout?.bind(globalThis),
}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "low-power" });
  renderer.setPixelRatio(1);
  let built = null;
  let selected = null;
  let model = null;
  let effects = true;
  let aspect = 1;
  const costs = [];
  let lastRenderAt = -Infinity;
  let renderTimeout = null;

  function frameModel() {
    if (!built) return;
    built.camera.aspect = aspect;
    const points = model.nodes;
    if (points.length) {
      const bounds = axis => [Math.min(...points.map(p => p[axis])) - 1,
        Math.max(...points.map(p => p[axis])) + 1];
      const [left, right] = bounds("x"), [bottom, top] = bounds("y"), [back, front] = bounds("z");
      const x = (left + right) / 2, y = (bottom + top) / 2;
      const tangent = Math.tan(built.camera.fov * Math.PI / 360);
      const distance = Math.max((right - left) / (2 * aspect * tangent), (top - bottom) / (2 * tangent));
      built.camera.position.set(x, y, front + distance * 1.15);
      built.camera.lookAt(x, y, (back + front) / 2);
    }
    built.camera.updateProjectionMatrix();
  }

  function renderOnce() {
    if (!built) return;
    const current = now();
    const remaining = MIN_RENDER_INTERVAL_MS - (current - lastRenderAt);
    if (remaining > 0) {
      if (renderTimeout === null && scheduleTimeout) {
        renderTimeout = scheduleTimeout(() => { renderTimeout = null; renderOnce(); }, remaining);
      }
      return;
    }
    const start = current;
    renderer.render(built.scene, built.camera);
    lastRenderAt = start;
    costs.push(now() - start);
    if (costs.length > 30) costs.shift();
  }

  function applySelection() {
    if (!built) return;
    for (const [id, mesh] of built.meshes) {
      const scale = id === selected ? 1.6 : 1;
      mesh.userData.baseScale = scale;
      mesh.scale.setScalar(scale);
    }
  }

  function setModel(next, options = {}) {
    effects = options.effects ?? effects;
    built?.dispose();
    built = buildThreeScene(THREE, next, { effects });
    model = { ...next, nodes: built.nodes, edges: built.edges };
    frameModel();
    if (selected && !built.meshes.has(selected)) selected = null;
    applySelection();
    renderOnce();
  }

  function pulse(ids) {
    if (!built || !ids.length) return;
    const start = now();
    const step = () => {
      const t = Math.min(1, (now() - start) / 800);
      const bump = 1 + 0.5 * Math.sin(Math.PI * t);
      for (const id of ids) {
        const mesh = built?.meshes.get(id);
        if (mesh) mesh.scale.setScalar(mesh.userData.baseScale * bump);
      }
      renderOnce();
      if (t < 1) requestFrame(step);
    };
    requestFrame(step);
  }

  return {
    setModel,
    pulse,
    renderFrame: renderOnce,
    select(id) { selected = id; applySelection(); renderOnce(); },
    rotate(radians) { if (built) { built.group.rotation.y += radians; renderOnce(); } },
    tilt(radians) { if (built) { built.group.rotation.x = Math.max(-1, Math.min(1, built.group.rotation.x + radians)); renderOnce(); } },
    zoom(steps) {
      if (!built) return;
      built.camera.position.z = Math.max(5, Math.min(36, built.camera.position.z + steps * 1.5));
      renderOnce();
    },
    pan(x, y) {
      if (!built) return;
      built.group.position.x = Math.max(-12, Math.min(12, built.group.position.x + x));
      built.group.position.y = Math.max(-12, Math.min(12, built.group.position.y + y));
      renderOnce();
    },
    resize(width, height) {
      aspect = Math.max(1, width) / Math.max(1, height);
      renderer.setSize(width, height, false);
      frameModel();
      renderOnce();
    },
    pick(ndcX, ndcY) {
      if (!built) return null;
      const caster = new THREE.Raycaster();
      caster.setFromCamera({ x: ndcX, y: ndcY }, built.camera);
      const hit = caster.intersectObjects([...built.meshes.values()], false)[0];
      return hit ? hit.object.userData.id : null;
    },
    cost() {
      const info = renderer.info;
      const resources = info ? { geometries: info.memory?.geometries ?? 0, textures: info.memory?.textures ?? 0,
        calls: info.render?.calls ?? 0 } : null;
      if (!costs.length) return { last: 0, average: 0, samples: 0, resources };
      return { last: costs.at(-1), average: costs.reduce((a, b) => a + b, 0) / costs.length, samples: costs.length, resources };
    },
    dispose() {
      if (renderTimeout !== null) cancelTimeout?.(renderTimeout);
      renderTimeout = null;
      built?.dispose(); built = null; renderer.dispose();
    },
  };
}

import { colorFor } from "./scene-model.mjs";

const EDGE_COLORS = { reporting: 0x818cf8, handoff: 0x22d3ee, delegation: 0xfbbf24 };

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
  for (const node of model.nodes) {
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
  for (const edge of model.edges) {
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
  return { scene, camera, group, meshes, dispose: () => disposables.forEach(d => d.dispose?.()) };
}

export function createThreeView({
  THREE, canvas, requestFrame = globalThis.requestAnimationFrame?.bind(globalThis),
  now = () => globalThis.performance.now(),
}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "low-power" });
  renderer.setPixelRatio(1);
  let built = null;
  let selected = null;
  let model = null;
  let effects = true;
  const costs = [];

  function renderOnce() {
    if (!built) return;
    const start = now();
    renderer.render(built.scene, built.camera);
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
    model = next;
    built = buildThreeScene(THREE, model, { effects });
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
    select(id) { selected = id; applySelection(); renderOnce(); },
    rotate(radians) { if (built) { built.group.rotation.y += radians; renderOnce(); } },
    resize(width, height) {
      renderer.setSize(width, height, false);
      if (built) { built.camera.aspect = width / Math.max(1, height); built.camera.updateProjectionMatrix(); }
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
      if (!costs.length) return { last: 0, average: 0, samples: 0 };
      return { last: costs.at(-1), average: costs.reduce((a, b) => a + b, 0) / costs.length, samples: costs.length };
    },
    dispose() { built?.dispose(); built = null; renderer.dispose(); },
  };
}
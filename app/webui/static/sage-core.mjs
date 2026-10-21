export const SAGE_CORE_MAX_FPS = 24;
export const SAGE_CORE_FRAME_BUDGET_MS = 28;
const FRAME_INTERVAL = 1000 / SAGE_CORE_MAX_FPS;
const VALID_STATES = new Set(["idle", "working", "waiting_for_approval", "paused", "error", "unavailable"]);
const STATE_COLOR = {
  idle: "#d6ad59", working: "#ffe39a", waiting_for_approval: "#f5bd52",
  paused: "#8c8065", error: "#ff766f", unavailable: "#718092", unknown: "#8793a2",
};

function safeId(value) { return typeof value === "string" && value.length > 0 && value.length <= 128; }
function isCoordinator(node) { return node.id === "coordinator" || node.builtInKey === "coordinator"; }

/** Keep only API-backed Agent records and trace relationships; never invent activity. */
export function buildSageCoreModel(snapshot) {
  const seen = new Set();
  const nodes = (Array.isArray(snapshot?.nodes) ? snapshot.nodes : []).filter(item => {
    if (!item || !safeId(item.id) || typeof item.name !== "string" || seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  }).map(item => ({
    id: item.id, name: item.name.slice(0, 128), role: typeof item.role === "string" ? item.role.slice(0, 256) : "",
    provider: typeof item.provider === "string" ? item.provider.slice(0, 128) : "unknown",
    model: typeof item.model === "string" ? item.model.slice(0, 128) : "unknown",
    state: VALID_STATES.has(item.state) ? item.state : "unknown",
    reason: typeof item.reason === "string" ? item.reason.slice(0, 256) : "",
    lastActive: typeof item.last_active === "string" ? item.last_active : null,
    builtIn: item.built_in === true,
    builtInKey: typeof item.built_in_key === "string" ? item.built_in_key : null,
  }));
  const ids = new Set(nodes.map(node => node.id));
  const handoffs = (Array.isArray(snapshot?.handoffs) ? snapshot.handoffs : []).filter(edge =>
    edge && safeId(edge.id) && ids.has(edge.from) && ids.has(edge.to)
      && ["completed", "failed"].includes(edge.state))
    .slice(0, 60).map(edge => ({ id: edge.id, from: edge.from, to: edge.to,
      state: edge.state, recordedAt: typeof edge.recorded_at === "string" ? edge.recorded_at : null }));
  const sourceLinks = (Array.isArray(snapshot?.source_links) ? snapshot.source_links : []).filter(edge =>
    edge && safeId(edge.id) && ids.has(edge.agent_id) && safeId(edge.source_id))
    .slice(0, 100).map(edge => ({ id: edge.id, agentId: edge.agent_id,
      sourceId: edge.source_id, label: typeof edge.label === "string" ? edge.label.slice(0, 128) : "Brain source",
      recordedAt: typeof edge.recorded_at === "string" ? edge.recorded_at : null }));
  return { nodes, handoffs, sourceLinks, observedAt: typeof snapshot?.observed_at === "string" ? snapshot.observed_at : null };
}

function hashId(value) {
  let hash = 2166136261;
  for (const char of value) { hash ^= char.charCodeAt(0); hash = Math.imul(hash, 16777619); }
  return hash >>> 0;
}

/** Coordinator is fixed at the core; other Agents keep an ID-derived orbit position. */
export function layoutSageCore(nodes, width, height) {
  const cx = width / 2, cy = height / 2, scale = Math.min(width, height);
  const radius = Math.max(48, scale * 0.34);
  const result = new Map();
  const ordered = [...nodes].sort((a, b) => a.id.localeCompare(b.id));
  const coordinator = ordered.find(isCoordinator);
  if (coordinator) result.set(coordinator.id, { x: cx, y: cy, radius: 25 });
  ordered.filter(node => !isCoordinator(node)).forEach(node => {
    const angle = (hashId(node.id) / 0x100000000) * Math.PI * 2 - Math.PI / 2;
    result.set(node.id, { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius, radius: 17 });
  });
  return result;
}

const GLYPH_SEGMENTS = [
  [[0,-1],[0,1],[-0.65,-0.45],[0.65,0.45]],
  [[-0.7,0.7],[0,-0.8],[0.7,0.7],[0,0.15],[-0.5,0.15]],
  [[-0.7,-0.5],[0.6,-0.5],[-0.35,0],[0.65,0.5],[-0.7,0.5]],
  [[-0.7,0],[0.7,0],[-0.45,-0.65],[-0.45,0.65],[0.45,-0.65],[0.45,0.65]],
  [[-0.65,-0.6],[0.65,0.6],[0.65,-0.6],[-0.65,0.6],[0,-0.9],[0,0.9]],
  [[-0.7,-0.4],[0.7,-0.4],[-0.3,0],[0.7,0.4],[-0.7,0.4]],
  [[0,-0.9],[0.7,-0.3],[0,0.3],[-0.7,-0.3],[0,0.9]],
  [[-0.7,0.65],[-0.7,-0.55],[0,-0.85],[0.7,-0.55],[0.7,0.65],[0,0.1],[-0.7,0.65]],
];

function drawGlyph(ctx, x, y, size, index) {
  const segments = GLYPH_SEGMENTS[index % GLYPH_SEGMENTS.length];
  ctx.beginPath();
  for (let i = 0; i < segments.length; i++) {
    const [px, py] = segments[i], xx = x + px * size, yy = y + py * size;
    if (i === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
  }
  ctx.stroke();
}

/** Draw original amber geometry. Only working/approval states pulse or emit rays. */
export function drawSageCore(ctx, model, width, height, time = 0, selectedId = null, reducedMotion = false) {
  ctx.clearRect(0, 0, width, height);
  const cx = width / 2, cy = height / 2, radius = Math.min(width, height) * 0.34;
  const points = layoutSageCore(model.nodes, width, height);
  const activity = model.nodes.some(node => ["working", "waiting_for_approval"].includes(node.state));
  const pulse = !reducedMotion && activity ? 1 + 0.035 * (0.5 + 0.5 * Math.sin(time / 270)) : 1;
  const bg = ctx.createRadialGradient(cx, cy, 5, cx, cy, Math.max(width, height) * 0.7);
  bg.addColorStop(0, "#18202b"); bg.addColorStop(1, "#080b10");
  ctx.fillStyle = bg; ctx.fillRect(0, 0, width, height);

  ctx.save(); ctx.translate(cx, cy);
  for (let i = 0; i < 5; i++) {
    const r = 42 + i * Math.min(width, height) * 0.085;
    const rotate = activity && !reducedMotion ? time * (i % 2 ? -0.00008 : 0.00008) : 0;
    ctx.save(); ctx.rotate(rotate); ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.strokeStyle = i === 2 ? "rgba(226,177,82,.62)" : "rgba(215,169,78,.24)";
    ctx.lineWidth = i === 2 ? 1.6 : 1; ctx.stroke();
    for (let tick = 0; tick < 24; tick++) {
      const a = tick * Math.PI / 12, inner = r - (tick % 3 === 0 ? 7 : 3);
      ctx.beginPath(); ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
      ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r); ctx.strokeStyle = "rgba(237,195,112,.45)"; ctx.stroke();
    }
    ctx.restore();
  }
  ctx.restore();

  for (const edge of model.handoffs) {
    const from = points.get(edge.from), to = points.get(edge.to);
    if (!from || !to) continue;
    ctx.beginPath(); ctx.moveTo(from.x, from.y); ctx.lineTo(to.x, to.y);
    ctx.strokeStyle = edge.state === "completed" ? "rgba(240,194,99,.78)" : "rgba(255,118,111,.78)";
    ctx.lineWidth = 1.5; ctx.stroke();
  }
  for (const link of model.sourceLinks) {
    const point = points.get(link.agentId); if (!point) continue;
    const x = point.x + (point.x < cx ? -26 : 26), y = point.y + (point.y < cy ? -17 : 17);
    ctx.beginPath(); ctx.moveTo(point.x, point.y); ctx.lineTo(x, y);
    ctx.strokeStyle = "rgba(238,196,113,.7)"; ctx.lineWidth = 1; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fillStyle = "#f4d28b"; ctx.fill();
  }

  for (const [index, node] of model.nodes.entries()) {
    const point = points.get(node.id); if (!point) continue;
    const color = STATE_COLOR[node.state] ?? STATE_COLOR.unknown;
    const coordinator = isCoordinator(node);
    const r = (point.radius ?? 16) * (coordinator ? pulse : 1);
    if (["working", "waiting_for_approval"].includes(node.state)) {
      ctx.save(); ctx.globalAlpha = reducedMotion ? 0.3 : 0.12 + 0.11 * (0.5 + 0.5 * Math.sin(time / 230));
      ctx.strokeStyle = color; ctx.lineWidth = 1.3;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(point.x, point.y); ctx.stroke(); ctx.restore();
    }
    ctx.beginPath(); ctx.arc(point.x, point.y, r, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(10,14,19,.94)"; ctx.fill();
    ctx.strokeStyle = color; ctx.lineWidth = node.id === selectedId ? 2.7 : 1.5; ctx.stroke();
    ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 1.4; ctx.lineCap = "round";
    drawGlyph(ctx, point.x, point.y, coordinator ? 11 : 7, hashId(node.id) % GLYPH_SEGMENTS.length);
    ctx.restore();
    ctx.font = coordinator ? "600 13px system-ui" : "12px system-ui";
    ctx.textAlign = "center"; ctx.fillStyle = "#e8e3d8";
    ctx.fillText(node.name.slice(0, 22), point.x, point.y + r + 17);
  }
  return points;
}

export function mountSageCore({ documentRef = globalThis.document, windowRef = globalThis.window,
  fetchImpl = globalThis.fetch, now = () => globalThis.performance.now(),
  requestFrame = windowRef?.requestAnimationFrame?.bind(windowRef),
  cancelFrame = windowRef?.cancelAnimationFrame?.bind(windowRef),
  scheduleTimeout = windowRef?.setTimeout?.bind(windowRef), cancelTimeout = windowRef?.clearTimeout?.bind(windowRef),
} = {}) {
  const el = id => documentRef.getElementById(id);
  const canvas = el("sage-core-canvas"), status = el("sage-core-state"), list = el("sage-core-accessible-list");
  const mapMode = el("sage-core-map-mode"), listMode = el("sage-core-list-mode");
  const reducedBox = el("sage-core-reduced-motion"), detailTitle = el("sage-core-detail-title");
  const detailContent = el("sage-core-detail-content"), refreshButton = el("sage-core-refresh");
  const context = canvas?.getContext?.("2d") ?? null;
  const mediaQuery = windowRef?.matchMedia?.("(prefers-reduced-motion: reduce)");
  let reducedMotion = mediaQuery?.matches === true;
  let mode = reducedMotion || !context ? "list" : "map";
  let model = buildSageCoreModel({}); let selectedId = null; let points = new Map();
  let loading = false, frameId = null, pollId = null, lastFrame = -Infinity, slowFrames = 0;
  const make = (tag, value, className) => {
    const item = documentRef.createElement(tag); item.textContent = value;
    if (className) item.className = className;
    return item;
  };
  function select(id) {
    const node = model.nodes.find(item => item.id === id); if (!node) return;
    selectedId = id; detailTitle.textContent = node.name; detailContent.replaceChildren();
    detailContent.append(make("p", node.role), make("p", `${node.provider} / ${node.model}`),
      make("p", `Status: ${node.state}${node.reason ? ` — ${node.reason}` : ""}`),
      make("p", node.lastActive ? `Last active ${new Date(node.lastActive).toLocaleString()}` : "No activity recorded this run."));
    const link = make("a", "Open Agent details"); link.href = "/ui/agents"; detailContent.append(link);
    draw(); renderList();
  }
  function renderList() {
    list.replaceChildren();
    for (const node of model.nodes) {
      const row = documentRef.createElement("li");
      const button = make("button", `${node.name} — ${node.role || "Agent"} · ${node.state}`);
      button.type = "button"; button.setAttribute("aria-pressed", String(node.id === selectedId));
      button.addEventListener("click", () => select(node.id)); row.append(button);
      if (node.reason) row.append(make("p", node.reason));
      list.append(row);
    }
    for (const edge of model.handoffs) {
      const from = model.nodes.find(node => node.id === edge.from)?.name ?? edge.from;
      const to = model.nodes.find(node => node.id === edge.to)?.name ?? edge.to;
      list.append(make("li", `Recorded handoff: ${from} to ${to} (${edge.state})${edge.recordedAt ? ` at ${edge.recordedAt}` : ""}.`));
    }
    for (const source of model.sourceLinks) {
      const agent = model.nodes.find(node => node.id === source.agentId)?.name ?? source.agentId;
      list.append(make("li", `Recorded Brain source for ${agent}: ${source.label}.`));
    }
  }
  function renderControls() {
    const mapAvailable = Boolean(context);
    if (!mapAvailable) mode = "list";
    canvas.hidden = mode !== "map" || !mapAvailable;
    list.hidden = mode !== "list";
    mapMode.disabled = !mapAvailable;
    mapMode.setAttribute("aria-pressed", String(mode === "map"));
    listMode.setAttribute("aria-pressed", String(mode === "list"));
  }
  function draw() {
    if (!context || mode !== "map") return;
    const width = Math.max(320, canvas.clientWidth || 800), height = Math.max(320, canvas.clientHeight || 560);
    const ratio = Math.min(2, windowRef?.devicePixelRatio || 1);
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    points = drawSageCore(context, model, width, height, now(), selectedId, reducedMotion);
  }
  function stopAnimation() { if (frameId !== null) cancelFrame?.(frameId); frameId = null; }
  function animate(timestamp) {
    frameId = null;
    if (documentRef.visibilityState === "hidden" || mode !== "map" || reducedMotion
      || !model.nodes.some(node => ["working", "waiting_for_approval"].includes(node.state))) return;
    if (timestamp - lastFrame >= FRAME_INTERVAL) {
      const started = now(); draw(); const renderMs = now() - started;
      lastFrame = timestamp;
      slowFrames = renderMs > SAGE_CORE_FRAME_BUDGET_MS ? slowFrames + 1 : 0;
      if (slowFrames >= 3) {
        mode = "list"; stopAnimation(); renderControls();
        status.textContent = "Animated map switched to the accessible list because recent draw times exceeded its frame budget.";
        return;
      }
    }
    frameId = requestFrame?.(animate) ?? null;
  }
  function updateAnimation() {
    stopAnimation(); slowFrames = 0; lastFrame = -Infinity;
    if (mode === "map" && !reducedMotion && model.nodes.some(node => ["working", "waiting_for_approval"].includes(node.state))) {
      frameId = requestFrame?.(animate) ?? null;
    }
  }
  function applyMode(next) {
    mode = next === "map" && context ? "map" : "list";
    renderControls(); draw(); updateAnimation();
  }
  async function refresh() {
    if (loading) return false;
    loading = true; refreshButton.disabled = true; status.textContent = "Reading current Agent states and recorded traces...";
    try {
      const response = await fetchImpl("/api/local/agents/sage-core", { credentials: "same-origin", headers: { Accept: "application/json" } });
      let payload = {}; try { payload = await response.json(); } catch { /* handled as unavailable */ }
      if (!response.ok) throw Object.assign(new Error(), { status: response.status });
      if (!Array.isArray(payload.nodes) || !payload.nodes.every(item => item && safeId(item.id) && typeof item.name === "string")) throw new Error("Invalid Agent map response");
      model = buildSageCoreModel(payload);
      if (selectedId && !model.nodes.some(node => node.id === selectedId)) selectedId = null;
      renderList(); renderControls(); draw(); updateAnimation();
      status.textContent = `${model.nodes.length} recorded Agents; ${model.handoffs.length} recorded handoffs and ${model.sourceLinks.length} current Brain-source links. Snapshot ${payload.observed_at || "time unavailable"}.`;
      if (selectedId) select(selectedId);
      else if (model.nodes.length === 0) { detailTitle.textContent = "Agent details"; detailContent.textContent = "No Agent records are available."; }
      return true;
    } catch (error) {
      model = buildSageCoreModel({}); renderList(); renderControls(); draw(); updateAnimation();
      status.textContent = error.status === 401 ? "Sign in through local owner access to view Agent states and chat traces."
        : error.status === 403 ? "This session needs Agent read and chat read permission to view this map."
          : "Current Agent states could not be loaded. Refresh and try again.";
      detailTitle.textContent = "Agent details"; detailContent.textContent = "No current snapshot is available.";
      return false;
    } finally { loading = false; refreshButton.disabled = false; }
  }
  function schedulePoll() {
    if (pollId !== null) cancelTimeout?.(pollId);
    pollId = null;
    if (documentRef.visibilityState !== "hidden") pollId = scheduleTimeout?.(async () => { pollId = null; await refresh(); schedulePoll(); }, 5000) ?? null;
  }
  refreshButton.addEventListener("click", refresh);
  mapMode.addEventListener("click", () => applyMode("map"));
  listMode.addEventListener("click", () => applyMode("list"));
  reducedBox.checked = reducedMotion;
  reducedBox.addEventListener("change", () => {
    reducedMotion = reducedBox.checked;
    if (reducedMotion) applyMode("list"); else applyMode("map");
  });
  canvas.addEventListener("click", event => {
    const rect = canvas.getBoundingClientRect?.() ?? { left: 0, top: 0, width: 1, height: 1 };
    const x = event.clientX - rect.left, y = event.clientY - rect.top;
    const hit = [...points.entries()].find(([, point]) => Math.hypot(point.x - x, point.y - y) <= (point.radius ?? 18) + 8);
    if (hit) select(hit[0]);
  });
  canvas.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key) || !model.nodes.length) return;
    event.preventDefault?.();
    const index = model.nodes.findIndex(node => node.id === selectedId);
    const direction = ["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 1;
    select(model.nodes[(index + direction + model.nodes.length) % model.nodes.length].id);
  });
  documentRef.addEventListener("visibilitychange", () => {
    if (documentRef.visibilityState === "hidden") {
      stopAnimation(); if (pollId !== null) cancelTimeout?.(pollId); pollId = null;
    } else { draw(); updateAnimation(); refresh().finally(schedulePoll); }
  });
  mediaQuery?.addEventListener?.("change", event => {
    if (event.matches && !reducedBox.checked) { reducedBox.checked = true; reducedMotion = true; applyMode("list"); }
  });
  renderControls();
  const initialLoad = refresh().finally(schedulePoll);
  return { initialLoad, refresh, select, get model() { return model; }, get mode() { return mode; },
    get animationActive() { return frameId !== null; }, dispose() {
      stopAnimation(); if (pollId !== null) cancelTimeout?.(pollId); pollId = null;
    } };
}

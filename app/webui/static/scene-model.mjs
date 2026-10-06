export const MAX_SCENE_NODES = 60;

const STATE_COLORS = {
  waiting: 0x8892a6, running: 0x22d3ee, review: 0xfbbf24, reviewed: 0x60a5fa, approved: 0x34d399,
  failed: 0xf87171, interrupted: 0xf87171, blocked: 0xfb923c, paused: 0xa78bfa,
  staffed: 0xa78bfa, unassigned: 0x64748b, missing: 0xf87171, forbidden: 0x475569, inactive: 0x475569,
};

export const colorFor = state => STATE_COLORS[state] ?? 0x64748b;

function positionState(node) {
  if (!node.active) return "inactive";
  const state = node.employee.state;
  return state === "assigned" ? "staffed" : state;
}

function depths(positions) {
  const byId = new Map(positions.map(p => [p.id, p]));
  const memo = new Map();
  const depth = (node, seen = new Set()) => {
    if (memo.has(node.id)) return memo.get(node.id);
    if (node.reporting_state !== "linked" || seen.has(node.id)) return 0;
    seen.add(node.id);
    const parent = byId.get(node.reports_to_position_id);
    const value = parent ? depth(parent, seen) + 1 : 0;
    memo.set(node.id, value);
    return value;
  };
  return new Map(positions.map(p => [p.id, depth(p)]));
}

export function buildSceneModel(structure, workflows, { maxNodes = MAX_SCENE_NODES } = {}) {
  const nodes = [];
  const edges = [];
  const sections = {
    structure: structure ? "available" : "unavailable",
    workflows: workflows ? "available" : "unavailable",
  };
  const positions = structure?.positions ?? [];
  const tiers = new Map();
  const depthOf = depths(positions);
  for (const p of positions) {
    const tier = depthOf.get(p.id);
    const index = tiers.get(tier) ?? 0;
    tiers.set(tier, index + 1);
    nodes.push({
      id: `pos:${p.id}`, kind: "position", label: p.title, state: positionState(p), revision: p.revision,
      detail: `Position ${p.title}; ${p.active ? "active" : "inactive"}; employee ${p.employee.state}; agent ${p.agent.state}`,
      x: index * 2.4 - 1.2, y: -tier * 2.2, z: 0, slot: index,
    });
    if (p.reporting_state === "linked") {
      edges.push({ kind: "reporting", from: `pos:${p.id}`, to: `pos:${p.reports_to_position_id}` });
    }
  }
  let row = 0;
  for (const workflow of workflows?.workflows ?? []) {
    workflow.nodes.forEach((n, index) => {
      nodes.push({
        id: `wi:${n.id}`, kind: "work_item", label: `${workflow.title}: ${n.role}`, state: n.state,
        detail: `Work item ${n.id} (${n.role}) is ${n.state}${n.reason ? ` - ${n.reason}` : ""}`,
        x: index * 2.4 - 1.2, y: -row * 1.8, z: -6, slot: index,
      });
    });
    for (const edge of workflow.operational_edges) {
      edges.push({ kind: edge.kind, from: `wi:${edge.from}`, to: `wi:${edge.to}` });
    }
    row += 1;
  }
  const kept = nodes.slice(0, maxNodes);
  const ids = new Set(kept.map(n => n.id));
  return {
    nodes: kept,
    edges: edges.filter(e => ids.has(e.from) && ids.has(e.to)),
    omitted: nodes.length - kept.length,
    sections,
  };
}

export function changedNodeIds(previous, next) {
  if (!previous) return [];
  const before = new Map(previous.nodes.map(n => [n.id, n.state]));
  return next.nodes.filter(n => before.has(n.id) && before.get(n.id) !== n.state).map(n => n.id);
}
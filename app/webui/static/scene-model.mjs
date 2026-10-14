export const MAX_SCENE_NODES = 60;
export const MAX_SCENE_EDGES = 119;

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
      agent_id: p.agent.state === "assigned" ? p.agent.id : null,
      agent_visibility: p.agent.state === "forbidden" ? "forbidden" : "available",
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
        agent_id: n.agent_visibility === "available" ? n.agent_id : null,
        agent_visibility: n.agent_visibility ?? "unknown",
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

const LAYERS = new Set(["organization", "projects", "tasks", "workflows", "providers", "capabilities", "resources", "knowledge"]);

function boundedText(value, fallback = "not recorded", limit = 160) {
  return typeof value === "string" && value.trim() ? value.trim().slice(0, limit) : fallback;
}

function addNode(nodes, layer, id, kind, label, state, detail, source, xIndex, yIndex, snapshotAt = null) {
  nodes.push({ id, layer, kind, label: boundedText(label, kind), state: boundedText(state, "unknown", 40),
    detail: boundedText(detail, "No additional details recorded."), source, snapshot_at: snapshotAt,
    x: (xIndex % 6) * 2.4 - 6, y: -yIndex * 1.8, z: -Math.floor(xIndex / 6) * 2.4, slot: xIndex });
}

/** Build a capped graph only from records supplied by the permission-checked API reads. */
export function buildCorporationMapModel(sources, { layers = LAYERS, maxNodes = MAX_SCENE_NODES, query = "" } = {}) {
  const enabled = new Set(layers);
  const nodes = [];
  const edges = [];
  const sections = { ...(sources.states ?? {}), departments: "unsupported" };
  const records = section => Array.isArray(section?.items) ? section.items : [];
  const positions = new Map();
  const employees = new Map();
  for (const employee of records(sources.employees)) {
    if (employee && typeof employee.id === "string") employees.set(employee.id, employee);
  }
  const agents = new Map(records(sources.agents).filter(item => item && typeof item.id === "string").map(item => [item.id, item]));
  const projects = new Map(records(sources.projects).filter(item => item && typeof item.id === "string").map(item => [item.id, item]));
  const providers = new Map(records(sources.providers).filter(item => item && typeof item.id === "string").map(item => [item.id, item]));
  const models = new Map();
  const ordinals = new Map();
  const indexFor = layer => { const i = ordinals.get(layer) ?? 0; ordinals.set(layer, i + 1); return i; };
  const include = (layer, ...items) => enabled.has(layer) && items.every(Boolean);

  const corporation = sources.corporation?.corporation;
  if (include("organization", corporation) && typeof corporation.id === "string") {
    addNode(nodes, "organization", `core:${corporation.id}`, "core", corporation.name, "recorded",
      `Corporation ${corporation.id}; source ${sources.corporationSource ?? "/api/status"}.`, sources.corporationSource ?? "/api/status", indexFor("organization"), 0);
  }

  for (const p of Array.isArray(sources.structure?.positions) ? sources.structure.positions : []) {
    if (!p || typeof p.id !== "string") continue;
    positions.set(p.id, p);
    if (include("organization", sources.structure)) {
      addNode(nodes, "organization", `pos:${p.id}`, "position", p.title, p.active ? "active" : "inactive",
        `Position ${p.title}; reporting ${p.reporting_state}; employee ${p.employee?.state ?? "unknown"}; Agent ${p.agent?.state ?? "unknown"}.`,
        "/api/structure-map", indexFor("organization"), 1, sources.structure.generated_at);
      nodes.at(-1).agent_id = p.agent?.state === "assigned" ? p.agent.id : null;
      nodes.at(-1).agent_visibility = p.agent?.state === "forbidden" ? "forbidden" : "available";
    }
    const employee = p.employee;
    if (employee?.state === "assigned" && typeof employee.id === "string") {
      if (!employees.has(employee.id)) employees.set(employee.id, employee);
      if (include("organization", sources.structure)) {
        addNode(nodes, "organization", `emp:${employee.id}`, "employee", employee.name, "assigned",
          `Employee ${employee.id}; role ${boundedText(employee.role)}.`, "/api/structure-map", indexFor("organization"), 2, sources.structure.generated_at);
        edges.push({ kind: "assigned employee", from: `pos:${p.id}`, to: `emp:${employee.id}` });
      }
    }
    const agent = p.agent;
    if (agent?.state === "assigned" && typeof agent.id === "string") {
      if (!agents.has(agent.id)) agents.set(agent.id, { id: agent.id, name: agent.name, role: null, capabilities: [] });
      if (include("organization", sources.structure)) {
        addNode(nodes, "organization", `agent:${agent.id}`, "agent", agent.name, "assigned",
          `Agent ${agent.id}; identity linked from the position assignment.`, "/api/structure-map", indexFor("organization"), 3, sources.structure.generated_at);
        if (employee?.state === "assigned") edges.push({ kind: "assigned Agent", from: `emp:${employee.id}`, to: `agent:${agent.id}` });
      }
    }
  }

  for (const p of positions.values()) {
    if (corporation?.id && positions.has(p.id)) edges.push({ kind: "recorded organization position", from: `core:${corporation.id}`, to: `pos:${p.id}` });
    if (p.reporting_state === "linked" && positions.has(p.reports_to_position_id)) {
      edges.push({ kind: "reports to", from: `pos:${p.id}`, to: `pos:${p.reports_to_position_id}` });
    }
  }

  for (const employee of employees.values()) {
    if (!employee || typeof employee.id !== "string") continue;
    if (!nodes.some(node => node.id === `emp:${employee.id}`) && include("organization", sources.employees)) addNode(nodes, "organization", `emp:${employee.id}`, "employee", employee.name,
      "registered", `Employee ${employee.id}; role ${boundedText(employee.role)}.`, "/api/employees", indexFor("organization"), 2);
    if (typeof employee.agent_id === "string" && agents.has(employee.agent_id)) {
      edges.push({ kind: "assigned Agent", from: `emp:${employee.id}`, to: `agent:${employee.agent_id}` });
    }
  }

  const tasks = new Map();
  for (const project of records(sources.projects)) {
    if (!project || typeof project.id !== "string") continue;
    if (include("projects", sources.projects)) addNode(nodes, "projects", `project:${project.id}`, "project", project.name,
      project.status, `Project ${project.id}; status ${project.status}.`, "/api/projects", indexFor("projects"));
  }
  for (const task of records(sources.tasks)) {
    if (!task || typeof task.id !== "string") continue;
    tasks.set(task.id, task);
    if (include("tasks", sources.tasks)) addNode(nodes, "tasks", `task:${task.id}`, "task", task.title, task.status,
      `Task ${task.id}; project ${task.project_id ?? "not assigned"}; Agent ${task.assigned_agent ?? "not assigned"}.`, "/api/tasks", indexFor("tasks"));
    if (task.project_id && projects.has(task.project_id)) edges.push({ kind: "belongs to project", from: `task:${task.id}`, to: `project:${task.project_id}` });
    if (task.assigned_agent && agents.has(task.assigned_agent)) edges.push({ kind: "assigned Agent", from: `task:${task.id}`, to: `agent:${task.assigned_agent}` });
  }

  for (const agent of agents.values()) {
    if (!agent || typeof agent.id !== "string") continue;
    if (!nodes.some(node => node.id === `agent:${agent.id}`) && (enabled.has("organization") || enabled.has("capabilities")) && sources.agents) {
      const agentLayer = enabled.has("organization") ? "organization" : "capabilities";
      addNode(nodes, agentLayer, `agent:${agent.id}`, "agent", agent.name, "registered",
        `Agent ${agent.id}; role ${boundedText(agent.role)}.`, "/api/agents", indexFor("organization"), 3);
    }
    for (const capability of Array.isArray(agent.capabilities) ? agent.capabilities : []) {
      if (typeof capability !== "string" || !capability.trim()) continue;
      const capabilityId = `capability:${agent.id}:${capability}`;
      if (!nodes.some(node => node.id === capabilityId) && include("capabilities", sources.agents)) {
        addNode(nodes, "capabilities", capabilityId, "capability", capability, "declared",
          `Capability declaration on Agent ${agent.id}. This does not grant execution authority.`, "/api/agents", indexFor("capabilities"));
      }
      edges.push({ kind: "declares capability", from: `agent:${agent.id}`, to: capabilityId });
    }
  }

  for (const provider of providers.values()) {
    if (include("providers", sources.providers)) addNode(nodes, "providers", `provider:${provider.id}`, "provider", provider.id,
      "registered", `Provider ${provider.id}; type ${boundedText(provider.type)}. Registration does not establish availability.`, "/api/providers", indexFor("providers"));
  }
  for (const assignment of records(sources.models)) {
    if (!assignment || typeof assignment.agent_id !== "string" || typeof assignment.provider_id !== "string" || typeof assignment.model_id !== "string") continue;
    const key = `${assignment.provider_id}\u0000${assignment.model_id}`;
    const modelId = `model:${encodeURIComponent(assignment.provider_id)}:${encodeURIComponent(assignment.model_id)}`;
    if (!models.has(key)) models.set(key, { id: modelId, provider_id: assignment.provider_id, model_id: assignment.model_id });
    if (!nodes.some(node => node.id === `agent:${assignment.agent_id}`) && (enabled.has("organization") || enabled.has("providers")) && sources.agents) {
      const agent = agents.get(assignment.agent_id);
      const agentLayer = enabled.has("organization") ? "organization" : "providers";
      if (agent) addNode(nodes, agentLayer, `agent:${agent.id}`, "agent", agent.name, "registered",
        `Agent ${agent.id}; role ${boundedText(agent.role)}.`, "/api/agents", indexFor("organization"), 3);
    }
    edges.push({ kind: "assigned model", from: `agent:${assignment.agent_id}`, to: modelId });
    edges.push({ kind: "provider assignment", from: `provider:${assignment.provider_id}`, to: modelId });
  }
  for (const model of models.values()) {
    if (include("providers", sources.models)) addNode(nodes, "providers", model.id, "model", model.model_id, "assigned",
      `Recorded assignment model ${model.model_id} at provider ${model.provider_id}. This is not an installed-model inventory.`, "/api/models", indexFor("providers"));
  }

  for (const workflow of Array.isArray(sources.workflows?.workflows) ? sources.workflows.workflows : []) {
    if (!workflow || typeof workflow.id !== "string") continue;
    const workflowId = `workflow:${workflow.id}`;
    if (include("workflows", sources.workflows)) addNode(nodes, "workflows", workflowId, "workflow", workflow.title,
      workflow.state, `Workflow ${workflow.id}; state ${workflow.state}${workflow.paused ? "; paused" : ""}.`,
      "/api/local/workflows/map", indexFor("workflows"), 0, sources.workflows.generated_at);
    for (const item of workflow.nodes ?? []) {
      if (!item || typeof item.id !== "string") continue;
      const itemId = `wi:${workflow.id}:${item.id}`;
      if (include("workflows", sources.workflows)) {
        addNode(nodes, "workflows", itemId, "work item", `${item.role} ${item.id}`,
          item.state, `Work item ${item.id}; role ${item.role}; state ${item.state}; outcome ${item.uncertain ? "unknown" : item.response_state ?? "not recorded"}.`,
          "/api/local/workflows/map", indexFor("workflows"), 1, sources.workflows.generated_at);
        nodes.at(-1).agent_id = item.agent_visibility === "forbidden" ? null : item.agent_id ?? null;
        nodes.at(-1).agent_visibility = item.agent_visibility ?? "unknown";
      }
      edges.push({ kind: "contains work item", from: workflowId, to: itemId });
      if (item.agent_id && item.agent_visibility !== "forbidden") edges.push({ kind: "assigned Agent", from: itemId, to: `agent:${item.agent_id}` });
    }
    for (const edge of workflow.operational_edges ?? []) {
      const from = `wi:${workflow.id}:${edge.from}`;
      const to = `wi:${workflow.id}:${edge.to}`;
      if ((workflow.nodes ?? []).some(item => item.id === edge.from) && (workflow.nodes ?? []).some(item => item.id === edge.to)) {
        edges.push({ kind: edge.kind, from, to });
      }
    }
  }

  const capacities = sources.monitoring?.resource_capacities;
  if (Array.isArray(capacities)) for (const capacity of capacities) {
    if (!capacity || typeof capacity.scope !== "string") continue;
    const suffix = [capacity.scope, capacity.provider_id, capacity.model_id].filter(Boolean).map(encodeURIComponent).join(":");
    const id = `resource:${suffix}`;
    if (include("resources", sources.monitoring)) {
      const history = capacity.scope === "allocation_history";
      addNode(nodes, "resources", id, history ? "allocation ID history" : "resource budget",
        history ? "allocation ID history" : `${capacity.scope} slots`, "configured",
        history ? `${capacity.allocated}/${capacity.limit} historical IDs used; this is not active slot capacity.`
          : `${capacity.allocated}/${capacity.limit} allocated; ${capacity.remaining} remaining. Software capacity only.`,
        "/api/system/monitor", indexFor("resources"), 0, sources.monitoring.observed_at);
    }
    if (capacity.scope === "global" && corporation?.id) edges.push({ kind: "software capacity", from: `core:${corporation.id}`, to: id });
    if (capacity.scope === "provider" && capacity.provider_id) edges.push({ kind: "provider capacity", from: `provider:${capacity.provider_id}`, to: id });
    if (capacity.scope === "model" && capacity.provider_id && capacity.model_id) {
      const modelId = `model:${encodeURIComponent(capacity.provider_id)}:${encodeURIComponent(capacity.model_id)}`;
      edges.push({ kind: "model capacity", from: modelId, to: id });
    }
  }

  for (const item of records(sources.memory)) {
    if (!item || typeof item.id !== "string") continue;
    const provenance = item.provenance;
    if (include("knowledge", sources.memory)) addNode(nodes, "knowledge", `knowledge:${item.id}`, "knowledge record", item.type,
      "retained", `Record ${item.id}; scope ${item.scope}; source ${boundedText(provenance?.source_reference)}; expires ${boundedText(item.expires_at)}. Content is not shown.`,
      "/api/memory", indexFor("knowledge"), 0);
    if (item.scope === "corporation" && corporation?.id) {
      edges.push({ kind: "published within Corporation", from: `knowledge:${item.id}`, to: `core:${corporation.id}` });
    }
    if (provenance?.source_scope === "project" && projects.has(provenance.source_scope_id)) {
      edges.push({ kind: "source Project", from: `knowledge:${item.id}`, to: `project:${provenance.source_scope_id}` });
    }
    if (provenance?.source_scope === "task" && tasks.has(provenance.source_scope_id)) {
      edges.push({ kind: "source Task", from: `knowledge:${item.id}`, to: `task:${provenance.source_scope_id}` });
    }
  }

  const term = typeof query === "string" ? query.trim().toLowerCase().slice(0, 120) : "";
  const filtered = nodes.filter(node => enabled.has(node.layer)
    && (!term || `${node.id} ${node.kind} ${node.label} ${node.state}`.toLowerCase().includes(term)));
  const kept = filtered.slice(0, Math.max(0, Math.min(MAX_SCENE_NODES, maxNodes)));
  const ids = new Set(kept.map(node => node.id));
  const uniqueEdges = [...new Map(edges.filter(edge => ids.has(edge.from) && ids.has(edge.to))
    .map(edge => [`${edge.kind}\u0000${edge.from}\u0000${edge.to}`, edge])).values()];
  const connected = uniqueEdges;
  const visibleEdges = connected.slice(0, MAX_SCENE_EDGES);
  return { nodes: kept, edges: visibleEdges, omitted: filtered.length - kept.length,
    omittedEdges: connected.length - visibleEdges.length, sections, layers: [...enabled].filter(layer => LAYERS.has(layer)) };
}

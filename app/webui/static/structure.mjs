const LABELS = {
  unassigned: "Unassigned", missing: "Missing record", forbidden: "Forbidden (permission not granted)",
  not_applicable: "Not applicable",
};

export async function mountStructure({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
} = {}) {
  const el = id => documentRef.getElementById(id);
  const status = el("structure-status");
  const tree = el("structure-tree");
  const detail = el("structure-detail");
  let current = null;
  let selectedId = null;
  let selectedRevision = null;

  async function load() {
    let response;
    try {
      response = await fetchImpl("/api/structure-map", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
    } catch {
      return { error: "The structure could not be loaded." };
    }
    if (response.status === 401) return { error: "Sign in through local owner access first." };
    if (response.status === 403) return { error: "This session lacks permission to read positions." };
    if (!response.ok) return { error: "The structure could not be loaded." };
    return { data: await response.json() };
  }

  const text = (tag, value) => {
    const node = documentRef.createElement(tag);
    node.textContent = value;
    return node;
  };

  function describe(part, ok) {
    if (part.state === "assigned") return ok(part);
    return LABELS[part.state] ?? "Unknown";
  }

  function renderNode(node, byParent, depth, seen) {
    const item = documentRef.createElement("li");
    const button = documentRef.createElement("button");
    button.type = "button";
    const flags = [];
    if (!node.active) flags.push("inactive");
    if (node.employee.state !== "assigned") flags.push(LABELS[node.employee.state].toLowerCase());
    button.textContent = `${node.title}${flags.length ? ` (${flags.join(", ")})` : ""}`;
    button.addEventListener("click", () => select(node.id));
    item.append(button);
    if (!seen.has(node.id) && depth < 32) {
      seen.add(node.id);
      const children = byParent.get(node.id) ?? [];
      if (children.length) {
        const sub = documentRef.createElement("ul");
        for (const child of children) sub.append(renderNode(child, byParent, depth + 1, seen));
        item.append(sub);
      }
    }
    return item;
  }

  function render(data) {
    current = data;
    const byParent = new Map();
    for (const node of data.positions) {
      if (node.reporting_state === "linked") {
        byParent.set(node.reports_to_position_id, [...(byParent.get(node.reports_to_position_id) ?? []), node]);
      }
    }
    tree.replaceChildren();
    const seen = new Set();
    for (const node of data.positions.filter(n => n.reporting_state !== "linked")) {
      tree.append(renderNode(node, byParent, 0, seen));
    }
    const forbidden = Object.entries(data.sections).filter(([, s]) => s === "forbidden").map(([n]) => n);
    status.textContent = `${data.positions.length} recorded positions as of ${data.generated_at}.` +
      (forbidden.length ? ` Not permitted: ${forbidden.join(", ")}.` : "");
  }

  function showDetail(node, staleNote) {
    detail.replaceChildren();
    if (staleNote) detail.append(text("p", staleNote));
    if (!node) return;
    detail.append(text("h3", node.title));
    detail.append(text("p", `Status: ${node.active ? "active" : "inactive"}; revision ${node.revision}`));
    const reporting = node.reporting_state === "linked" ? `reports to ${node.reports_to_position_id}`
      : node.reporting_state === "root" ? "top-level position" : `reports to missing position ${node.reports_to_position_id}`;
    detail.append(text("p", `Reporting: ${reporting}`));
    detail.append(text("p", `Responsibilities: ${node.responsibilities.join("; ") || "none recorded"}`));
    detail.append(text("p", `Employee: ${describe(node.employee, e => `${e.name} (${e.role})`)}`));
    detail.append(text("p", `Agent/model: ${describe(node.agent, a =>
      `${a.name}; provider ${a.provider_id} (${a.provider_state}); model ${a.model_id}`)}`));
  }

  async function select(id) {
    const previousRevision = id === selectedId ? selectedRevision : current?.positions.find(n => n.id === id)?.revision;
    const result = await load();
    if (result.error) { status.textContent = result.error; return; }
    render(result.data);
    const node = result.data.positions.find(n => n.id === id);
    selectedId = id;
    selectedRevision = node?.revision ?? null;
    let note = "";
    if (!node) note = "Stale: this position no longer exists.";
    else if (previousRevision !== undefined && previousRevision !== node.revision) {
      note = "Stale list: this position changed since it was listed; current details are shown.";
    }
    showDetail(node, note);
  }

  async function refresh() {
    const result = await load();
    if (result.error) { status.textContent = result.error; tree.replaceChildren(); return; }
    render(result.data);
  }

  el("structure-refresh").addEventListener("click", refresh);
  await refresh();
  return { select, refresh };
}

if (globalThis.document) await mountStructure();

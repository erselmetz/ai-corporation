const FORBIDDEN = "Forbidden (permission not granted)";

export async function mountWorkflowMap({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  nowImpl = () => Date.now(),
} = {}) {
  const el = id => documentRef.getElementById(id);
  const status = el("workflow-map-status");
  const list = el("workflow-map-list");
  const org = el("workflow-map-org");
  const detail = el("workflow-map-detail");
  let snapshot = null;
  let selected = null;

  const text = (tag, value) => {
    const node = documentRef.createElement(tag);
    node.textContent = value;
    return node;
  };

  async function load() {
    let response;
    try {
      response = await fetchImpl("/api/local/workflows/map", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
    } catch {
      return { error: "disconnected" };
    }
    if (response.status === 401) return { error: "signin" };
    if (response.status === 403) return { error: "forbidden" };
    if (!response.ok) return { error: "failed" };
    return { data: await response.json() };
  }

  function age(data) {
    return (nowImpl() - Date.parse(data.generated_at)) / 1000;
  }

  function freshness(data) {
    const seconds = age(data);
    return seconds > data.stale_after_seconds ? ` Stale: ${Math.round(seconds)}s old.` : "";
  }

  function render(data) {
    snapshot = data;
    list.replaceChildren();
    org.replaceChildren();
    const count = data.workflows.length;
    status.textContent = (count ? `${count} recorded workflows as of ${data.generated_at}.`
      : `No workflows in this app run (as of ${data.generated_at}).`) + freshness(data);
    for (const workflow of data.workflows) {
      const section = documentRef.createElement("section");
      section.append(text("h2", `${workflow.title}: ${workflow.state}${workflow.paused ? " (paused)" : ""}`));
      const items = documentRef.createElement("ul");
      for (const node of workflow.nodes) {
        const row = documentRef.createElement("li");
        const button = documentRef.createElement("button");
        button.type = "button";
        button.textContent = `${node.role} ${node.id}: ${node.state}`;
        button.addEventListener("click", () => select(workflow.id, node.id));
        row.append(button);
        items.append(row);
      }
      section.append(items);
      const edges = documentRef.createElement("ul");
      for (const edge of workflow.operational_edges) {
        edges.append(text("li", `Operational ${edge.kind}: ${edge.from} -> ${edge.to}`));
      }
      section.append(text("h3", "Operational links"));
      section.append(edges);
      list.append(section);
    }
    if (data.organization.state === "forbidden") {
      org.append(text("li", `Reporting links: ${FORBIDDEN}`));
    } else if (!data.organization.reporting_edges.length) {
      org.append(text("li", "No recorded reporting links."));
    } else {
      const titles = new Map(data.organization.positions.map(p => [p.id, p.title]));
      for (const edge of data.organization.reporting_edges) {
        org.append(text("li", `Reporting: ${titles.get(edge.from)} reports to ${titles.get(edge.to)}`));
      }
    }
  }

  function showDetail(workflowId, nodeId, note) {
    detail.replaceChildren();
    if (note) detail.append(text("p", note));
    const workflow = snapshot?.workflows.find(w => w.id === workflowId);
    const node = workflow?.nodes.find(n => n.id === nodeId);
    if (!node) {
      detail.append(text("p", "This work item is no longer recorded."));
      return;
    }
    detail.append(text("h3", `${node.role} ${node.id}`));
    detail.append(text("p", `State: ${node.state}${node.reason ? ` - ${node.reason}` : ""}`));
    detail.append(text("p", `Agent: ${node.agent_visibility === "forbidden" ? FORBIDDEN : node.agent_id}`));
    detail.append(text("p", `Destination: ${node.agent_visibility === "forbidden" ? FORBIDDEN : node.destination_id ?? "none"}`));
    detail.append(text("p", `Attempts: ${node.attempts}; output recorded: ${node.output_recorded ? "yes" : "no"}`));
    if (node.uncertain) detail.append(text("p", "Outcome UNKNOWN: inspect before retrying."));
    detail.append(text("p", node.review
      ? `Review ${node.review.passed ? "passed" : "rejected"} at ${node.review.at}: ${node.review.evidence}`
      : "Review: none recorded"));
    detail.append(text("p", node.approval
      ? `Owner approval at ${node.approval.at}: ${node.approval.evidence}`
      : "Owner approval: none recorded"));
  }

  function fail(error) {
    const stale = snapshot ? ` Showing the last snapshot from ${snapshot.generated_at} (stale).` : "";
    status.textContent = {
      signin: "Sign in through local owner access first.",
      forbidden: "This session lacks permission to read workflows.",
      disconnected: "Disconnected: the workflow map could not be reached.",
      failed: "The workflow map could not be loaded.",
    }[error] + stale;
    if (!snapshot) {
      list.replaceChildren();
      org.replaceChildren();
    }
  }

  async function refresh() {
    const result = await load();
    if (result.error) { fail(result.error); return false; }
    render(result.data);
    if (selected) showDetail(selected.workflowId, selected.nodeId, "");
    return true;
  }

  async function select(workflowId, nodeId) {
    selected = { workflowId, nodeId };
    const ok = await refresh();
    if (!ok) showDetail(workflowId, nodeId, "Showing the last snapshot; current details are unavailable.");
  }

  el("workflow-map-refresh").addEventListener("click", refresh);
  await refresh();
  return { select, refresh };
}

if (globalThis.document) await mountWorkflowMap();
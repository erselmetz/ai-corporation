export async function mountWorkflows({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
} = {}) {
  const status = documentRef.getElementById("workflow-status");
  const list = documentRef.getElementById("workflow-list");
  const line = (parent, text) => {
    const row = documentRef.createElement("p");
    row.textContent = text;
    parent.append(row);
  };
  let response;
  try {
    response = await fetchImpl("/api/local/workflows", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
  } catch {
    status.textContent = "Workflows could not be loaded.";
    return;
  }
  if (!response.ok) {
    status.textContent = "Sign in through local owner access to view workflows.";
    return;
  }
  const { workflows } = await response.json();
  list.replaceChildren();
  status.textContent = workflows.length ? "" : "No workflows in this app run.";
  for (const workflow of workflows) {
    const section = documentRef.createElement("section");
    const heading = documentRef.createElement("h2");
    heading.textContent = workflow.title;
    section.append(heading);
    line(section, `State: ${workflow.state}${workflow.paused ? " (paused)" : ""}`);
    line(section, `Owner approved: ${workflow.owner_approved ? "yes" : "no"}`);
    line(section, `Routing: ${workflow.preference}; fallback ${workflow.fallback_enabled ? "enabled" : "disabled"}`);
    const ceiling = workflow.spend_ceiling_cents === null ? "UNKNOWN" : `${workflow.spend_ceiling_cents} cents`;
    line(section, `Spend ceiling: ${ceiling}; declared spend: ${workflow.spent_cents} cents`);
    line(section, "Cancellation: unsupported");
    for (const item of workflow.items) {
      line(section, `${item.role} ${item.id} (${item.agent_id}): ${item.state}${item.reason ? ` - ${item.reason}` : ""}`);
    }
    for (const handoff of workflow.handoffs) {
      line(section, `Handoff ${handoff.from} -> ${handoff.to}`);
    }
    list.append(section);
  }
}

if (globalThis.document) await mountWorkflows();

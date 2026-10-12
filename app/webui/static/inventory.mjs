function addText(documentRef, parent, tag, value, className) {
  const element = documentRef.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function displayValue(value) {
  return typeof value === "string" && value.length ? value : "unknown";
}

export function mountInventoryPage(documentRef, fetchImpl) {
  const status = documentRef.querySelector("#inventory-status");
  const records = documentRef.querySelector("#inventory-records");
  const limitations = documentRef.querySelector("#inventory-limitations");
  const refreshButton = documentRef.querySelector("#inventory-refresh");

  function render(snapshot) {
    records.replaceChildren();
    limitations.replaceChildren();
    for (const item of snapshot.items ?? []) {
      const card = documentRef.createElement("section");
      card.className = "dashboard-card";
      addText(documentRef, card, "h2", item.name ?? item.id);
      addText(documentRef, card, "p", `${item.kind ?? "record"} - ${item.status ?? "unknown"}`, "section-state");
      const details = documentRef.createElement("dl");
      for (const [label, value] of [
        ["Version", item.version],
        ["Revision", item.revision],
        ["Source", item.source],
        ["Management", item.management],
        ["Observed", item.observed_at],
      ]) {
        addText(documentRef, details, "dt", label);
        addText(documentRef, details, "dd", displayValue(value));
      }
      if (Array.isArray(item.models) && item.models.length) {
        addText(documentRef, details, "dt", "Available models");
        addText(documentRef, details, "dd", item.models.join(", "));
      }
      addText(documentRef, details, "dt", "Dependent workflows");
      addText(documentRef, details, "dd", item.dependent_workflows?.length ? item.dependent_workflows.join(", ") : "none recorded");
      card.append(details);
      records.append(card);
    }
    for (const note of snapshot.limitations ?? []) addText(documentRef, limitations, "li", note);
    status.textContent = `Showing ${snapshot.items?.length ?? 0} read-only records; generated ${snapshot.generated_at ?? "unknown"}.`;
  }

  async function refresh() {
    status.textContent = "Checking local session...";
    try {
      const session = await fetchImpl("/api/local/session", { credentials: "same-origin" });
      if (!session.ok) throw new Error("Sign in to inspect the local inventory.");
      const sessionData = await session.json();
      if (!sessionData.permissions?.includes("inventory:read")) throw new Error("This session cannot inspect inventory.");
      const response = await fetchImpl("/api/local/inventory", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error(response.status === 401 ? "Sign in to inspect the local inventory." : "Inventory is unavailable.");
      render(await response.json());
    } catch (error) {
      records.replaceChildren();
      status.textContent = error instanceof Error ? error.message : "Inventory is unavailable.";
    }
  }
  refreshButton?.addEventListener("click", refresh);
  return { refresh };
}

if (typeof document !== "undefined") mountInventoryPage(document, fetch);

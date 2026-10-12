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
  const softwareState = documentRef.querySelector("#software-manager-state");
  const softwareDetails = documentRef.querySelector("#software-manager-details");
  const softwareControls = documentRef.querySelector("#software-manager-controls");
  const softwareLimitations = documentRef.querySelector("#software-manager-limitations");
  const softwareAction = documentRef.querySelector("#software-action");
  const softwareVersion = documentRef.querySelector("#software-version");
  const softwarePreviewButton = documentRef.querySelector("#software-preview");
  const softwarePreviewPanel = documentRef.querySelector("#software-preview-panel");
  const softwarePreviewDetails = documentRef.querySelector("#software-preview-details");
  const softwareConfirmButton = documentRef.querySelector("#software-confirm");
  const softwareResult = documentRef.querySelector("#software-operation-result");
  let csrfToken = null;
  let pendingPreview = null;

  function renderDetails(parent, entries) {
    parent.replaceChildren();
    for (const [label, value] of entries) {
      addText(documentRef, parent, "dt", label);
      addText(documentRef, parent, "dd", displayValue(value));
    }
  }

  function renderSoftware(record, permissions) {
    csrfToken = permissions.csrf;
    renderDetails(softwareDetails, [
      ["Package", record.name], ["Package ID", record.package_id],
      ["Source", record.source], ["Scope", record.scope],
      ["Status", record.status], ["Installed version", record.installed_version],
      ["Managed version", record.managed_version], ["Pinned version", record.pinned_version],
      ["Dependent workflows", record.dependent_workflows?.join(", ") || "none recorded"],
    ]);
    softwareLimitations.replaceChildren();
    for (const note of record.limitations ?? []) addText(documentRef, softwareLimitations, "li", note);
    const canManage = permissions.permissions?.includes("software:manage");
    const managed = record.status === "managed";
    const uncertainRecovery = record.status === "ownership_uncertain"
      && !record.installed_version && Boolean(record.managed_version);
    softwareControls.hidden = !canManage || (!managed && record.status !== "not_installed" && !uncertainRecovery);
    if (softwareAction) {
      if (managed && softwareAction.value === "install") softwareAction.value = "update";
      if (uncertainRecovery) {
        softwareAction.value = "install";
        softwareVersion.value = record.managed_version;
      }
      for (const option of softwareAction.children ?? []) {
        if (option.value === "install") option.disabled = record.status !== "not_installed" && !uncertainRecovery;
        else option.disabled = !managed || uncertainRecovery;
      }
      const unpinOption = [...(softwareAction.children ?? [])].find((option) => option.value === "unpin");
      if (unpinOption) unpinOption.disabled = !managed || !record.pinned_version;
      if (record.pinned_version === false && softwareAction.value === "unpin") softwareAction.value = "update";
    }
    softwareState.textContent = record.status === "externally_managed"
      ? "This installation is external to ERSELMETZ AI and is read-only."
      : `Supported package status: ${record.status}.`;
  }

  function renderPreview(preview) {
    pendingPreview = preview;
    renderDetails(softwarePreviewDetails, [
      ["Operation", preview.action], ["Package", `${preview.name} (${preview.package_id})`],
      ["Source / scope", `${preview.source} / ${preview.scope}`],
      ["Version change", `${preview.from_version ?? "not installed"} → ${preview.to_version ?? "removed"}`],
      ["Installer SHA-256", preview.installer_sha256],
      ["Affected dependents", preview.affected_dependents.join(", ") || preview.dependency_note],
      ["Data preserved", preview.preserved_data.join(", ")],
      ["Installation directory removed", preview.removed_install_directory],
      ["Warnings", preview.warnings.join(" ")],
      ["Expires", `${preview.expires_in_seconds} seconds`],
    ]);
    softwarePreviewPanel.hidden = false;
    softwareResult.textContent = "Review the exact package, version, source, scope and data effects before confirming.";
  }

  async function requestPreview() {
    pendingPreview = null;
    softwarePreviewPanel.hidden = true;
    softwareResult.textContent = "Refreshing package metadata and preparing a bounded preview…";
    try {
      const body = { action: softwareAction.value };
      if (["install", "update", "version", "pin"].includes(body.action)) body.version = softwareVersion.value.trim();
      const response = await fetchImpl("/api/local/software/preview", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": csrfToken },
        body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "The software preview is unavailable.");
      renderPreview(result);
    } catch (error) {
      softwareResult.textContent = error instanceof Error ? error.message : "The software preview is unavailable.";
    }
  }

  async function confirmPreview() {
    const approved = pendingPreview;
    if (!approved) return;
    pendingPreview = null;
    softwareConfirmButton.disabled = true;
    softwarePreviewPanel.hidden = true;
    softwareResult.textContent = "Running the owner-confirmed operation once; do not retry until status is refreshed.";
    try {
      const response = await fetchImpl("/api/local/software/confirm", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": csrfToken },
        body: JSON.stringify({ confirmation_id: approved.confirmation_id, preview_sha256: approved.preview_sha256 }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "The package operation could not be completed.");
      softwareResult.textContent = `Actual result: ${result.status}. ${result.message ?? ""}${result.version ? ` Verified version: ${result.version}.` : ""}${result.recovery ? ` Verified recovery is available for version ${result.recovery.version}; it requires a new preview and confirmation.` : ""}`;
      await refreshSoftware();
    } catch (error) {
      softwareResult.textContent = error instanceof Error ? error.message : "The result is unknown; refresh status before taking another action.";
    } finally {
      softwareConfirmButton.disabled = false;
    }
  }

  async function refreshSoftware() {
    try {
      const session = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      if (!session.ok) throw new Error("Sign in to inspect supported software.");
      const sessionData = await session.json();
      if (!sessionData.permissions?.includes("software:read")) throw new Error("This session cannot inspect supported software.");
      const response = await fetchImpl("/api/local/software", { credentials: "same-origin", cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Software status is unavailable.");
      renderSoftware(result, sessionData);
    } catch (error) {
      softwareState.textContent = error instanceof Error ? error.message : "Software status is unavailable.";
      softwareControls.hidden = true;
    }
  }

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
      csrfToken = sessionData.csrf;
      const response = await fetchImpl("/api/local/inventory", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error(response.status === 401 ? "Sign in to inspect the local inventory." : "Inventory is unavailable.");
      render(await response.json());
      const softwareResponse = await fetchImpl("/api/local/software", { credentials: "same-origin", cache: "no-store" });
      if (softwareResponse.ok) renderSoftware(await softwareResponse.json(), sessionData);
      else softwareState.textContent = "Supported software status is unavailable.";
    } catch (error) {
      records.replaceChildren();
      status.textContent = error instanceof Error ? error.message : "Inventory is unavailable.";
      pendingPreview = null;
      if (softwarePreviewPanel) softwarePreviewPanel.hidden = true;
      if (softwareControls) softwareControls.hidden = true;
    }
  }
  refreshButton?.addEventListener("click", refresh);
  softwarePreviewButton?.addEventListener("click", requestPreview);
  softwareConfirmButton?.addEventListener("click", confirmPreview);
  return { refresh, requestPreview, confirmPreview };
}

if (typeof document !== "undefined") mountInventoryPage(document, fetch);

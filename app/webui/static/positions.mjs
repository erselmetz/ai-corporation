function validPosition(position) {
  return Boolean(
    position &&
      typeof position.id === "string" &&
      typeof position.title === "string" &&
      Array.isArray(position.responsibilities) &&
      position.responsibilities.every((item) => typeof item === "string") &&
      (position.reports_to_position_id === null ||
        typeof position.reports_to_position_id === "string") &&
      (position.employee_id === null || typeof position.employee_id === "string") &&
      typeof position.active === "boolean" &&
      Number.isInteger(position.revision) &&
      Array.isArray(position.history) &&
      position.history.every((item) => Number.isInteger(item.revision)),
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function messageFor(status) {
  if (status === 401) return "Sign in through local owner access first.";
  if (status === 403) return "This session lacks the separate position read or management permission.";
  if (status === 404) return "The position or referenced record no longer exists. Refresh and review it.";
  if (status === 409) return "The position changed or still has references. Refresh and resolve them before retrying.";
  if (status === 422) return "The position fields or references are invalid. Check the template, responsibilities, and selections.";
  return "Position management failed. Refresh and try again.";
}

export function mountPositionManagementPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  confirmImpl = globalThis.confirm,
}) {
  const byId = (id) => documentRef.getElementById(id);
  const pageState = byId("position-state");
  const list = byId("position-list");
  const detailState = byId("position-detail-state");
  const detail = byId("position-detail");
  const history = byId("position-history");
  const form = byId("position-form");
  const formState = byId("position-form-state");
  const save = byId("position-save");
  const deactivate = byId("position-deactivate");
  const remove = byId("position-remove");
  const title = byId("position-title");
  const responsibilities = byId("position-responsibilities");
  const reportsTo = byId("position-reports-to");
  const employee = byId("position-employee");
  let positions = [];
  let templates = [];
  let employees = [];
  let employeeAccess = true;
  let selected = null;
  let busy = false;

  function readOptions() {
    return { credentials: "same-origin", headers: { Accept: "application/json" } };
  }

  async function request(path, method = "GET", body = undefined) {
    const options = { ...readOptions(), method };
    if (body !== undefined || method !== "GET") {
      const sessionResponse = await fetchImpl("/api/local/session", readOptions());
      if (!sessionResponse.ok) throw Object.assign(new Error(), { status: sessionResponse.status });
      const session = await sessionResponse.json();
      options.headers = {
        ...options.headers,
        "Content-Type": "application/json",
        "X-Local-CSRF": session.csrf,
      };
      if (body !== undefined) options.body = JSON.stringify(body);
    }
    const response = await fetchImpl(path, options);
    if (!response.ok) throw Object.assign(new Error(), { status: response.status });
    if (response.status === 204) return null;
    return response.json();
  }

  function option(select, value, label) {
    const item = documentRef.createElement("option");
    item.value = value;
    item.textContent = label;
    select.append(item);
  }

  function fillReferences(excludeId = "", currentEmployeeId = null) {
    reportsTo.replaceChildren();
    option(reportsTo, "", "No reporting position");
    for (const position of positions) {
      if (position.active && position.id !== excludeId) {
        option(reportsTo, position.id, `${position.title} · ${position.id}`);
      }
    }
    employee.replaceChildren();
    option(employee, "", "Unassigned");
    for (const item of employees) {
      option(employee, item.id, `${item.name} · ${item.id}`);
    }
    if (
      currentEmployeeId &&
      !employees.some((item) => item.id === currentEmployeeId)
    ) {
      option(employee, currentEmployeeId, `Existing employee reference · ${currentEmployeeId}`);
    }
  }

  function clearEditor() {
    selected = null;
    fillReferences();
    title.value = templates[0] ?? "";
    responsibilities.value = "";
    reportsTo.value = "";
    employee.value = "";
    save.textContent = "Create position";
    deactivate.hidden = true;
    remove.hidden = true;
    detail.replaceChildren();
    history.replaceChildren();
    setState(detailState, "Add a position or select an existing record.");
    setState(
      formState,
      employeeAccess
        ? ""
        : "Employee choices are hidden because this session lacks employee:read; existing references are preserved.",
    );
  }

  function renderDetails(position) {
    detail.replaceChildren();
    const entries = [
      ["Position ID", position.id],
      ["Template", position.title],
      ["Status", position.active ? "Active" : "Inactive"],
      ["Reports to", position.reports_to_position_id ?? "None"],
      ["Employee ID", position.employee_id ?? "Unassigned"],
      ["Revision", String(position.revision)],
      ["Responsibilities", position.responsibilities.join("; ")],
    ];
    for (const [label, value] of entries) {
      const row = documentRef.createElement("p");
      row.textContent = `${label}: ${value}`;
      detail.append(row);
    }
    history.replaceChildren();
    for (const revision of position.history) {
      const item = documentRef.createElement("li");
      item.textContent = `Revision ${revision.revision}: ${revision.title}; employee ${
        revision.employee_id ?? "unassigned"
      }; ${revision.active ? "active" : "inactive"} at ${revision.recorded_at}`;
      history.append(item);
    }
  }

  function renderList() {
    list.replaceChildren();
    for (const position of positions) {
      const row = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.setAttribute("aria-pressed", String(selected?.id === position.id));
      button.textContent = `${position.title} · ${position.active ? "Active" : "Inactive"} · ${position.id}`;
      button.addEventListener("click", () => selectPosition(position.id));
      row.append(button);
      list.append(row);
    }
    setState(
      pageState,
      positions.length
        ? `${positions.length} position record${positions.length === 1 ? "" : "s"} loaded.`
        : "No positions are configured.",
      positions.length ? "success-state" : "empty-state",
    );
  }

  function selectPosition(positionId) {
    const position = positions.find((item) => item.id === positionId);
    if (!position) return;
    selected = position;
    fillReferences(position.id, position.employee_id);
    title.value = position.title;
    responsibilities.value = position.responsibilities.join("\n");
    reportsTo.value = position.reports_to_position_id ?? "";
    employee.value = position.employee_id ?? "";
    save.textContent = "Save changes";
    deactivate.hidden = !position.active;
    remove.hidden = false;
    renderDetails(position);
    setState(detailState, "Position details loaded.");
    setState(
      formState,
      employeeAccess
        ? ""
        : "Employee choices are hidden because this session lacks employee:read; existing references are preserved.",
    );
    renderList();
  }

  async function refresh(selectId = null) {
    try {
      const [positionResult, templateResult] = await Promise.all([
        request("/api/positions"),
        request("/api/positions/templates"),
      ]);
      employeeAccess = true;
      let employeeResult;
      try {
        employeeResult = await request("/api/employees");
      } catch (error) {
        if (error.status !== 403) throw error;
        employeeAccess = false;
        employeeResult = { items: [] };
      }
      if (
        !positionResult || !Array.isArray(positionResult.items) ||
        !templateResult || !Array.isArray(templateResult.items) ||
        !employeeResult || !Array.isArray(employeeResult.items) ||
        !positionResult.items.every(validPosition) ||
        !templateResult.items.every((item) => typeof item === "string") ||
        !employeeResult.items.every((item) => typeof item.id === "string" && typeof item.name === "string")
      ) {
        throw Object.assign(new Error(), { status: 502 });
      }
      positions = positionResult.items;
      templates = templateResult.items;
      employees = employeeResult.items;
      title.replaceChildren();
      templates.forEach((item) => option(title, item, item));
      fillReferences(selectId ?? "");
      renderList();
      if (selectId && positions.some((item) => item.id === selectId)) {
        selectPosition(selectId);
      } else {
        clearEditor();
      }
      if (!employeeAccess) {
        setState(
          formState,
          "Employee choices are hidden because this session lacks employee:read; existing references are preserved.",
        );
      }
      return true;
    } catch (error) {
      positions = [];
      list.replaceChildren();
      clearEditor();
      setState(pageState, messageFor(error.status), "error-state");
      return false;
    }
  }

  async function submit(event) {
    event?.preventDefault();
    if (busy) return false;
    busy = true;
    save.disabled = true;
    const lines = responsibilities.value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
    const body = {
      title: title.value,
      responsibilities: lines,
      reports_to_position_id: reportsTo.value || null,
      employee_id: employee.value || null,
    };
    const path = selected
      ? `/api/positions/${encodeURIComponent(selected.id)}`
      : "/api/positions";
    if (selected) body.expected_revision = selected.revision;
    try {
      const position = await request(path, selected ? "PUT" : "POST", body);
      setState(formState, selected ? "Position changes saved." : "Position created.", "success-state");
      await refresh(position.id);
      return true;
    } catch (error) {
      setState(formState, messageFor(error.status), "error-state");
      return false;
    } finally {
      busy = false;
      save.disabled = false;
    }
  }

  async function deactivatePosition() {
    if (!selected || busy || !confirmImpl?.("Deactivate this position and preserve its history?")) return false;
    busy = true;
    deactivate.disabled = true;
    try {
      const position = await request(
        `/api/positions/${encodeURIComponent(selected.id)}/deactivate`,
        "POST",
        { expected_revision: selected.revision },
      );
      setState(formState, "Position deactivated; its history remains available.", "success-state");
      await refresh(position.id);
      return true;
    } catch (error) {
      setState(formState, messageFor(error.status), "error-state");
      return false;
    } finally {
      busy = false;
      deactivate.disabled = false;
    }
  }

  async function removePosition() {
    if (!selected || busy || !confirmImpl?.("Remove this unreferenced position permanently?")) return false;
    busy = true;
    remove.disabled = true;
    try {
      await request(`/api/positions/${encodeURIComponent(selected.id)}`, "DELETE");
      setState(formState, "Position removed.", "success-state");
      await refresh();
      return true;
    } catch (error) {
      setState(formState, messageFor(error.status), "error-state");
      return false;
    } finally {
      busy = false;
      remove.disabled = false;
    }
  }

  byId("position-new").addEventListener("click", clearEditor);
  form.addEventListener("submit", submit);
  deactivate.addEventListener("click", deactivatePosition);
  remove.addEventListener("click", removePosition);
  const initialLoad = refresh();
  return {
    initialLoad,
    refresh,
    selectPosition,
    submit,
    deactivatePosition,
    removePosition,
  };
}

if (typeof document !== "undefined" && document.getElementById("position-form")) {
  mountPositionManagementPage();
}

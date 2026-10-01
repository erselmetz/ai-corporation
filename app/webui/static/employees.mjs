const readOptions = {
  credentials: "same-origin",
  headers: { Accept: "application/json" },
};

const writeOptions = {
  credentials: "same-origin",
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
};

function validEmployee(employee) {
  return Boolean(
    employee &&
    typeof employee.id === "string" &&
    typeof employee.name === "string" &&
    typeof employee.role === "string" &&
    Array.isArray(employee.responsibilities) &&
    employee.responsibilities.every((item) => typeof item === "string") &&
    (employee.agent_id === null || typeof employee.agent_id === "string"),
  );
}

function validEmployeeList(payload) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    Array.isArray(payload.items) &&
    payload.items.every(validEmployee),
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function errorMessage(status, operation) {
  if (status === 401) return "Sign-in required. This browser session is not authenticated.";
  if (status === 403) return "Access denied. This account lacks the required employee permission.";
  if (status === 404) return operation === "detail"
    ? "This employee no longer exists. The employee list was refreshed."
    : "This employee no longer exists.";
  if (status === 409) return "An employee with this ID already exists.";
  if (status === 422) return "The Employee API rejected these fields. Check that ID, name, and role are valid.";
  return "The request could not be completed. Please retry.";
}

function displayValue(documentRef, label, value) {
  const row = documentRef.createElement("div");
  row.className = "data-row";
  const term = documentRef.createElement("dt");
  term.textContent = label;
  const description = documentRef.createElement("dd");
  description.textContent = value;
  row.append(term, description);
  return row;
}

function parseResponsibilities(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function mountEmployeeManagementPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  confirmImpl = globalThis.confirm,
}) {
  const listElement = documentRef.getElementById("employee-list");
  const listState = documentRef.getElementById("employee-list-state");
  const detailElement = documentRef.getElementById("employee-detail");
  const detailState = documentRef.getElementById("employee-detail-state");
  const refreshButton = documentRef.getElementById("employee-refresh");
  const form = documentRef.getElementById("employee-create-form");
  const createButton = documentRef.getElementById("employee-create-submit");
  const createState = documentRef.getElementById("employee-create-state");
  let employees = [];
  let selectedEmployeeId = null;
  let detailRequest = 0;
  let isCreating = false;
  let isRemoving = false;

  function clearDetails(message = "Select an employee to view details.") {
    selectedEmployeeId = null;
    detailRequest += 1;
    detailElement.replaceChildren();
    detailElement.hidden = true;
    setState(detailState, message);
  }

  function renderEmployeeList() {
    listElement.replaceChildren();
    if (employees.length === 0) {
      setState(listState, "No employees found.", "empty-state");
      return;
    }

    setState(listState, `${employees.length} employee record${employees.length === 1 ? "" : "s"} loaded.`, "success-state");
    for (const employee of employees) {
      const item = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.className = "employee-select";
      button.setAttribute("aria-pressed", String(employee.id === selectedEmployeeId));
      button.textContent = `${employee.name} · ${employee.role} · ${employee.id}`;
      button.addEventListener("click", () => loadEmployeeDetails(employee.id));
      item.append(button);
      listElement.append(item);
    }
  }

  function renderEmployeeDetails(employee) {
    detailElement.replaceChildren();
    const details = documentRef.createElement("dl");
    details.className = "identity-list";
    details.append(
      displayValue(documentRef, "Employee ID", employee.id),
      displayValue(documentRef, "Name", employee.name),
      displayValue(documentRef, "Role", employee.role),
      displayValue(
        documentRef,
        "Agent ID",
        employee.agent_id ?? "Not associated",
      ),
    );

    const responsibilitiesTitle = documentRef.createElement("h3");
    responsibilitiesTitle.textContent = "Responsibilities";
    const responsibilities = documentRef.createElement("ul");
    responsibilities.className = "compact-list";
    if (employee.responsibilities.length === 0) {
      const empty = documentRef.createElement("li");
      empty.className = "empty-state";
      empty.textContent = "No responsibilities listed.";
      responsibilities.append(empty);
    } else {
      for (const responsibility of employee.responsibilities) {
        const item = documentRef.createElement("li");
        item.textContent = responsibility;
        responsibilities.append(item);
      }
    }

    const removeButton = documentRef.createElement("button");
    removeButton.type = "button";
    removeButton.className = "danger-button";
    removeButton.textContent = "Remove employee";
    removeButton.addEventListener("click", () => removeEmployee(employee));
    detailElement.append(details, responsibilitiesTitle, responsibilities, removeButton);
    detailElement.hidden = false;
  }

  async function loadEmployeeDetails(employeeId) {
    const requestId = ++detailRequest;
    selectedEmployeeId = employeeId;
    renderEmployeeList();
    detailElement.replaceChildren();
    detailElement.hidden = true;
    setState(detailState, "Loading employee details…");

    try {
      const response = await fetchImpl(
        `/api/employees/${encodeURIComponent(employeeId)}`,
        { ...readOptions },
      );
      if (requestId !== detailRequest) return;
      if (!response.ok) {
        setState(detailState, errorMessage(response.status, "detail"), "error-state");
        if (response.status === 404) {
          clearDetails(errorMessage(404, "detail"));
          await loadEmployees();
        }
        return;
      }

      const employee = await response.json();
      if (requestId !== detailRequest) return;
      if (!validEmployee(employee)) {
        setState(detailState, "Employee details could not be loaded because the response was invalid.", "error-state");
        return;
      }
      renderEmployeeDetails(employee);
      setState(detailState, "Employee details loaded.", "success-state");
    } catch {
      if (requestId === detailRequest) {
        setState(detailState, "Employee details could not be loaded. Please retry.", "error-state");
      }
    }
  }

  async function loadEmployees() {
    setState(listState, "Loading employees…");
    try {
      const response = await fetchImpl("/api/employees", { ...readOptions });
      if (!response.ok) {
        employees = [];
        listElement.replaceChildren();
        clearDetails("Employee details are unavailable until the list can be loaded.");
        setState(listState, errorMessage(response.status, "list"), "error-state");
        return false;
      }

      const payload = await response.json();
      if (!validEmployeeList(payload)) {
        employees = [];
        listElement.replaceChildren();
        clearDetails("Employee details are unavailable because the list response was invalid.");
        setState(listState, "Employee records could not be loaded because the response was invalid.", "error-state");
        return false;
      }

      employees = payload.items;
      if (
        selectedEmployeeId &&
        !employees.some((employee) => employee.id === selectedEmployeeId)
      ) {
        clearDetails("The selected employee is no longer in the list.");
      }
      renderEmployeeList();
      return true;
    } catch {
      employees = [];
      listElement.replaceChildren();
      clearDetails("Employee details are unavailable until the list can be loaded.");
      setState(listState, "Employee records could not be loaded. Please retry.", "error-state");
      return false;
    }
  }

  async function submitNewEmployee(event) {
    event.preventDefault();
    if (isCreating) return;

    const employee = {
      id: documentRef.getElementById("employee-id").value.trim(),
      name: documentRef.getElementById("employee-name").value.trim(),
      role: documentRef.getElementById("employee-role").value.trim(),
      responsibilities: parseResponsibilities(
        documentRef.getElementById("employee-responsibilities").value,
      ),
    };
    if (!employee.id || !employee.name || !employee.role) {
      setState(createState, "Employee ID, name, and role are required.", "error-state");
      return;
    }

    isCreating = true;
    createButton.disabled = true;
    setState(createState, "Creating employee…");
    try {
      const response = await fetchImpl("/api/employees", {
        ...writeOptions,
        method: "POST",
        body: JSON.stringify(employee),
      });
      if (!response.ok) {
        setState(createState, errorMessage(response.status, "create"), "error-state");
        return;
      }

      const created = await response.json();
      if (!validEmployee(created)) {
        setState(createState, "The API response was invalid; employee creation could not be confirmed.", "error-state");
        return;
      }

      form.reset();
      setState(createState, `Employee ${created.id} created.`, "success-state");
      const refreshed = await loadEmployees();
      if (refreshed) {
        if (employees.some((employee) => employee.id === created.id)) {
          await loadEmployeeDetails(created.id);
        } else {
          setState(
            createState,
            `Employee ${created.id} was created, but is not present in the refreshed list.`,
            "error-state",
          );
        }
      } else {
        setState(
          createState,
          `Employee ${created.id} was created, but the list could not be refreshed.`,
          "error-state",
        );
      }
    } catch {
      setState(createState, "Employee creation could not be confirmed. Please refresh before retrying.", "error-state");
    } finally {
      isCreating = false;
      createButton.disabled = false;
    }
  }

  async function removeEmployee(employee) {
    if (isRemoving) return;
    const confirmed = confirmImpl(
      `Remove ${employee.name} (${employee.id})? This action cannot be undone.`,
    );
    if (!confirmed) return;

    isRemoving = true;
    const removeButton = detailElement.querySelector(".danger-button");
    if (removeButton) removeButton.disabled = true;
    setState(detailState, "Removing employee…");
    try {
      const response = await fetchImpl(
        `/api/employees/${encodeURIComponent(employee.id)}`,
        { method: "DELETE", credentials: "same-origin", headers: { Accept: "application/json" } },
      );
      if (response.status === 404) {
        clearDetails(errorMessage(404, "delete"));
        setState(listState, errorMessage(404, "delete"), "error-state");
        await loadEmployees();
        return;
      }
      if (!response.ok) {
        setState(detailState, errorMessage(response.status, "delete"), "error-state");
        return;
      }

      employees = employees.filter((item) => item.id !== employee.id);
      clearDetails(`Employee ${employee.id} was removed.`);
      renderEmployeeList();
      setState(detailState, `Employee ${employee.id} was removed.`, "success-state");
    } catch {
      setState(detailState, "Employee removal could not be confirmed. Refresh the list before retrying.", "error-state");
    } finally {
      if (removeButton) removeButton.disabled = false;
      isRemoving = false;
    }
  }

  refreshButton.addEventListener("click", loadEmployees);
  form.addEventListener("submit", submitNewEmployee);
  const initialLoad = loadEmployees();

  return {
    initialLoad,
    loadEmployees,
    loadEmployeeDetails,
    submitNewEmployee,
  };
}

if (typeof document !== "undefined") {
  mountEmployeeManagementPage();
}

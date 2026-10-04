const readOptions = {
  credentials: "same-origin",
  headers: { Accept: "application/json" },
};

const writeHeaders = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

const taskFields = [
  "id",
  "title",
  "description",
  "project_id",
  "status",
  "assigned_agent",
  "required_role",
  "required_capability",
];

function validTask(task) {
  return Boolean(
    task &&
    typeof task.id === "string" &&
    typeof task.title === "string" &&
    typeof task.description === "string" &&
    typeof task.status === "string" &&
    (task.project_id === null || typeof task.project_id === "string") &&
    (task.assigned_agent === null || typeof task.assigned_agent === "string") &&
    (task.required_role === null || typeof task.required_role === "string") &&
    (task.required_capability === null || typeof task.required_capability === "string"),
  );
}

function validTaskList(payload) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    Array.isArray(payload.items) &&
    payload.items.every(validTask),
  );
}

function validDryRun(payload, taskId) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    payload.task_id === taskId &&
    typeof payload.task_title === "string" &&
    typeof payload.task_description === "string" &&
    typeof payload.selected_agent_id === "string" &&
    typeof payload.selected_agent_name === "string" &&
    typeof payload.selected_agent_role === "string" &&
    (payload.selected_employee_id === null || typeof payload.selected_employee_id === "string") &&
    (payload.selected_employee_name === null || typeof payload.selected_employee_name === "string") &&
    (payload.provider === null || typeof payload.provider === "string") &&
    (payload.model === null || typeof payload.model === "string") &&
    (payload.routing_method === null || typeof payload.routing_method === "string") &&
    typeof payload.status === "string",
  );
}

function validDispatchEntry(entry) {
  return Boolean(
    entry &&
    Number.isInteger(entry.sequence) &&
    typeof entry.id === "string" &&
    typeof entry.task_id === "string" &&
    ["queued", "claimed", "completed", "failed", "abandoned"].includes(entry.state) &&
    (entry.worker_id === null || typeof entry.worker_id === "string") &&
    (entry.claim_id === null || typeof entry.claim_id === "string") &&
    (entry.resolution === null || typeof entry.resolution === "string") &&
    typeof entry.created_at === "string" &&
    typeof entry.updated_at === "string" &&
    entry.task &&
    typeof entry.task.title === "string" &&
    typeof entry.task.status === "string" &&
    typeof entry.task.result_recorded === "boolean" &&
    typeof entry.task.error_recorded === "boolean"
  );
}

function validDispatchQueue(payload) {
  return Boolean(
    payload &&
    Array.isArray(payload.items) &&
    payload.items.every(validDispatchEntry) &&
    typeof payload.history_limit_reached === "boolean"
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function errorMessage(status, action) {
  if (status === 401) return "Sign-in required. This browser session is not authenticated.";
  if (status === 403) return "Access denied. This account lacks the required task permission.";
  if (status === 404) {
    return action === "task-create"
      ? "The referenced Project was not found. Check the Project ID and retry."
      : "This Task no longer exists.";
  }
  if (status === 409 && action === "task-dispatch") {
    return "Dispatch is blocked by the current Task or queue state. Inspect the queue; no automatic retry occurred.";
  }
  if (status === 503 && action === "task-dispatch") {
    return "Dispatch is unavailable until explicit provider and model slot budgets are configured.";
  }
  if (status === 502 && action === "task-dispatch") {
    return "The dispatch outcome may be uncertain. Inspect the queue before taking further action.";
  }
  if (status === 409) return "The Task request conflicts with current data.";
  if (status === 422) return "The API rejected the Task fields. Review the form and retry.";
  if (status === 400 && action === "task-create") {
    return "The Task could not be created with the supplied routing selection.";
  }
  if (status === 400 && action === "task-preview") {
    return "This Task cannot be routed with its current assignment.";
  }
  return "The request could not be completed. Please retry.";
}

async function validationMessage(response) {
  const allowed = new Set(["title", "description", "project_id", "agent_id", "role", "capability"]);
  try {
    const payload = await response.json();
    const issues = Array.isArray(payload?.detail)
      ? payload.detail
          .filter((issue) =>
            Array.isArray(issue?.loc) &&
            allowed.has(issue.loc.at(-1)) &&
            typeof issue.msg === "string",
          )
          .map((issue) => `${issue.loc.at(-1)}: ${issue.msg}`)
      : [];
    return issues.length ? `Validation failed: ${issues.join("; ")}.` : errorMessage(422, "task-create");
  } catch {
    return errorMessage(422, "task-create");
  }
}

function appendDefinition(documentRef, container, label, value) {
  const row = documentRef.createElement("div");
  row.className = "data-row";
  const term = documentRef.createElement("dt");
  term.textContent = label;
  const description = documentRef.createElement("dd");
  description.textContent = value;
  row.append(term, description);
  container.append(row);
}

export function mountTaskPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  confirmImpl = globalThis.confirm,
}) {
  const list = documentRef.getElementById("task-list");
  const listState = documentRef.getElementById("task-list-state");
  const refreshButton = documentRef.getElementById("task-refresh");
  const detail = documentRef.getElementById("task-detail");
  const detailState = documentRef.getElementById("task-detail-state");
  const preview = documentRef.getElementById("task-preview");
  const previewState = documentRef.getElementById("task-preview-state");
  const form = documentRef.getElementById("task-create-form");
  const createButton = documentRef.getElementById("task-create-submit");
  const createState = documentRef.getElementById("task-create-state");
  const dispatchState = documentRef.getElementById("task-dispatch-state");
  const dispatchQueue = documentRef.getElementById("task-dispatch-queue");
  const dispatchRefresh = documentRef.getElementById("task-dispatch-refresh");
  const dispatchResolution = documentRef.getElementById("task-dispatch-resolution");
  const dispatchResolve = documentRef.getElementById("task-dispatch-resolve");

  let tasks = [];
  let selectedTaskId = null;
  let listRequest = 0;
  let detailRequest = 0;
  let previewRequest = 0;
  let isCreating = false;
  let dispatchAllowed = false;
  let dispatchCsrf = null;
  let selectedQueueEntryId = null;
  let isDispatching = false;
  let isResolvingDispatch = false;

  const formFields = Object.fromEntries(
    taskFieldsForCreation.map((field) => [
      field,
      documentRef.getElementById(`task-${field.replace("_", "-")}`),
    ]),
  );

  function clearDetail(message = "Select a task to view its details.") {
    selectedTaskId = null;
    detailRequest += 1;
    detail.replaceChildren();
    detail.hidden = true;
    clearPreview("Select a task to preview routing.");
    setState(detailState, message);
  }

  function clearPreview(message = "Select a task to preview routing.") {
    previewRequest += 1;
    preview.replaceChildren();
    preview.hidden = true;
    setState(previewState, message);
  }

  function renderTaskList() {
    list.replaceChildren();
    if (tasks.length === 0) {
      setState(listState, "No tasks found.", "empty-state");
      return;
    }
    setState(listState, `${tasks.length} task record${tasks.length === 1 ? "" : "s"} loaded.`, "success-state");
    for (const task of tasks) {
      const item = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.className = "record-select";
      button.setAttribute("aria-pressed", String(task.id === selectedTaskId));
      button.textContent = `${task.id} · ${task.title} · ${task.status}`;
      button.addEventListener("click", () => void loadTaskDetail(task.id));
      item.append(button);
      list.append(item);
    }
  }

  function renderTaskDetail(task) {
    detail.replaceChildren();
    const fields = [
      ["Task ID", task.id],
      ["Title", task.title],
      ["Description", task.description],
      ["Status", task.status],
      ["Project ID", task.project_id],
      ["Assigned Agent", task.assigned_agent],
      ["Required role", task.required_role],
      ["Required capability", task.required_capability],
    ];
    const definitions = documentRef.createElement("dl");
    definitions.className = "identity-list";
    for (const [label, value] of fields) {
      if (value !== null) appendDefinition(documentRef, definitions, label, value);
    }
    const previewButton = documentRef.createElement("button");
    previewButton.type = "button";
    previewButton.textContent = "Preview routing (dry-run)";
    previewButton.addEventListener("click", () => void runDryRun(task.id));
    detail.append(definitions, previewButton);
    if (dispatchAllowed && task.status === "pending") {
      const dispatchButton = documentRef.createElement("button");
      dispatchButton.type = "button";
      dispatchButton.textContent = "Confirm and dispatch this Task";
      dispatchButton.disabled = isDispatching;
      dispatchButton.addEventListener("click", () => void dispatchTask(task));
      detail.append(dispatchButton);
    }
    detail.hidden = false;
  }

  function renderDispatchQueue(payload) {
    dispatchQueue.replaceChildren();
    selectedQueueEntryId = null;
    dispatchResolution.value = "";
    dispatchResolution.disabled = true;
    dispatchResolve.disabled = true;
    if (payload.items.length === 0) {
      setState(dispatchState, "No queued or historical dispatch entries.", "empty-state");
      return;
    }
    for (const entry of payload.items) {
      const item = documentRef.createElement("li");
      const label = documentRef.createElement("p");
      label.textContent = `${entry.state} · ${entry.task_id} · ${entry.task.title} · Task ${entry.task.status} · result ${entry.task.result_recorded ? "recorded" : "not recorded"} · error ${entry.task.error_recorded ? "recorded" : "not recorded"}${entry.resolution ? ` · resolution: ${entry.resolution}` : ""}`;
      item.append(label);
      if (entry.state === "queued" || entry.state === "claimed") {
        const select = documentRef.createElement("button");
        select.type = "button";
        select.textContent = "Select for explicit resolution";
        select.addEventListener("click", () => {
          selectedQueueEntryId = entry.id;
          dispatchResolution.disabled = false;
          dispatchResolve.disabled = false;
          setState(
            dispatchState,
            `Selected ${entry.state} entry ${entry.id}. Resolution abandons queue membership; it does not alter the Task or replay work.`,
          );
        });
        item.append(select);
      }
      dispatchQueue.append(item);
    }
    setState(
      dispatchState,
      payload.history_limit_reached
        ? "Showing the oldest 100 dispatch records. Queue state is actual; recorded results are not outcome verification."
        : "Queue state is actual; recorded results are not outcome verification.",
      "success-state",
    );
  }

  async function refreshDispatchQueue() {
    try {
      const sessionResponse = await fetchImpl("/api/local/session", {
        ...readOptions,
      });
      if (!sessionResponse.ok) {
        dispatchAllowed = false;
        dispatchCsrf = null;
        dispatchQueue.replaceChildren();
        selectedQueueEntryId = null;
        dispatchResolution.value = "";
        dispatchResolution.disabled = true;
        dispatchResolve.disabled = true;
        setState(
          dispatchState,
          "Controlled dispatch is unavailable without an authenticated local task:dispatch permission.",
          "error-state",
        );
        if (selectedTaskId) {
          const current = tasks.find(({ id }) => id === selectedTaskId);
          if (current) renderTaskDetail(current);
        }
        return false;
      }
      const session = await sessionResponse.json();
      dispatchAllowed = Array.isArray(session.permissions)
        && session.permissions.includes("task:dispatch")
        && typeof session.csrf === "string";
      dispatchCsrf = dispatchAllowed ? session.csrf : null;
      if (!dispatchAllowed) {
        dispatchQueue.replaceChildren();
        selectedQueueEntryId = null;
        dispatchResolution.value = "";
        dispatchResolution.disabled = true;
        dispatchResolve.disabled = true;
        setState(
          dispatchState,
          "Controlled dispatch is unavailable: this session lacks task:dispatch permission.",
          "error-state",
        );
        return false;
      }
      const response = await fetchImpl("/api/task-dispatch/queue", {
        ...readOptions,
      });
      if (!response.ok) {
        dispatchQueue.replaceChildren();
        setState(dispatchState, errorMessage(response.status, "task-dispatch"), "error-state");
        return false;
      }
      const payload = await response.json();
      if (!validDispatchQueue(payload)) {
        setState(dispatchState, "Dispatch queue response was invalid.", "error-state");
        return false;
      }
      renderDispatchQueue(payload);
      if (selectedTaskId) {
        const current = tasks.find(({ id }) => id === selectedTaskId);
        if (current) renderTaskDetail(current);
      }
      return true;
    } catch {
      setState(dispatchState, "Dispatch queue could not be inspected. No work was run.", "error-state");
      return false;
    }
  }

  async function dispatchTask(task) {
    if (isDispatching || !dispatchAllowed || !dispatchCsrf) return;
    if (typeof confirmImpl !== "function" || !confirmImpl(
      `Dispatch "${task.title}" through the configured loopback Ollama worker? Only this pending Task will be run; no Tools or cloud Providers are used. A completed run does not verify its expected outcomes.`,
    )) {
      setState(dispatchState, "Dispatch cancelled. No work was run.");
      return;
    }
    isDispatching = true;
    setState(dispatchState, "Queueing and running one explicitly confirmed Task…");
    try {
      const response = await fetchImpl(`/api/tasks/${encodeURIComponent(task.id)}/dispatch`, {
        credentials: "same-origin",
        method: "POST",
        headers: {
          ...writeHeaders,
          "X-Local-CSRF": dispatchCsrf,
        },
        body: JSON.stringify({ confirmed: true }),
      });
      if (!response.ok) {
        const message = errorMessage(response.status, "task-dispatch");
        await refreshDispatchQueue();
        setState(dispatchState, message, "error-state");
        return;
      }
      const entry = await response.json();
      if (!validDispatchEntry(entry)) {
        await refreshDispatchQueue();
        setState(dispatchState, "Dispatch response was invalid; inspect the queue before any further action.", "error-state");
        return;
      }
      setState(
        dispatchState,
        `Queue entry ${entry.id} is ${entry.state}; Task is ${entry.task.status}. Result recorded: ${entry.task.result_recorded}. Outcome remains unverified.`,
        "success-state",
      );
      await refreshDispatchQueue();
      const refreshed = await loadTasks();
      if (refreshed && tasks.some(({ id }) => id === task.id)) {
        await loadTaskDetail(task.id);
      }
    } catch {
      await refreshDispatchQueue();
      setState(dispatchState, "Dispatch outcome could be uncertain. Inspect the queue before any further action; do not retry automatically.", "error-state");
    } finally {
      isDispatching = false;
      if (selectedTaskId) {
        const current = tasks.find(({ id }) => id === selectedTaskId);
        if (current) renderTaskDetail(current);
      }
    }
  }

  async function resolveDispatchEntry() {
    if (isResolvingDispatch || !dispatchAllowed || !dispatchCsrf || !selectedQueueEntryId) return;
    const resolution = dispatchResolution.value.trim();
    if (!resolution) {
      setState(dispatchState, "Enter the human inspection and resolution before continuing.", "error-state");
      return;
    }
    if (typeof confirmImpl !== "function" || !confirmImpl(
      "Abandon this queue entry with the recorded resolution? This does not change the Task or replay work.",
    )) {
      setState(dispatchState, "Queue resolution cancelled.");
      return;
    }
    isResolvingDispatch = true;
    dispatchResolve.disabled = true;
    try {
      const response = await fetchImpl(
        `/api/task-dispatch/${encodeURIComponent(selectedQueueEntryId)}/resolve`,
        {
          credentials: "same-origin",
          method: "POST",
          headers: {
            ...writeHeaders,
            "X-Local-CSRF": dispatchCsrf,
          },
          body: JSON.stringify({ resolution, confirmed: true }),
        },
      );
      if (!response.ok) {
        setState(dispatchState, errorMessage(response.status, "task-dispatch"), "error-state");
        return;
      }
      setState(dispatchState, "Queue entry was explicitly abandoned. Task state was not changed.", "success-state");
      await refreshDispatchQueue();
    } catch {
      setState(dispatchState, "Resolution outcome could not be confirmed. Refresh the queue before another action.", "error-state");
    } finally {
      isResolvingDispatch = false;
      dispatchResolve.disabled = !selectedQueueEntryId;
    }
  }

  function renderDryRun(result) {
    preview.replaceChildren();
    const definitions = documentRef.createElement("dl");
    definitions.className = "identity-list";
    const fields = [
      ["Task ID", result.task_id],
      ["Task title", result.task_title],
      ["Selected Agent ID", result.selected_agent_id],
      ["Selected Agent name", result.selected_agent_name],
      ["Selected Agent role", result.selected_agent_role],
      ["Selected Employee ID", result.selected_employee_id],
      ["Selected Employee name", result.selected_employee_name],
      ["Provider ID", result.provider],
      ["Model ID", result.model],
      ["Routing method", result.routing_method],
      ["Preview status", result.status],
    ];
    for (const [label, value] of fields) {
      if (value !== null) appendDefinition(documentRef, definitions, label, value);
    }
    preview.append(definitions);
    preview.hidden = false;
  }

  async function loadTasks() {
    const requestId = ++listRequest;
    setState(listState, "Loading tasks…");
    try {
      const response = await fetchImpl("/api/tasks", { ...readOptions });
      if (requestId !== listRequest) return false;
      if (!response.ok) {
        tasks = [];
        list.replaceChildren();
        clearDetail("Task details are unavailable until the Task list can be loaded.");
        setState(listState, errorMessage(response.status, "task-list"), "error-state");
        return false;
      }
      const payload = await response.json();
      if (requestId !== listRequest) return false;
      if (!validTaskList(payload)) {
        tasks = [];
        list.replaceChildren();
        clearDetail("Task details are unavailable because the list response was invalid.");
        setState(listState, "Task list response was invalid.", "error-state");
        return false;
      }
      tasks = payload.items;
      if (selectedTaskId && !tasks.some(({ id }) => id === selectedTaskId)) {
        clearDetail("The selected Task is no longer in the list.");
      }
      renderTaskList();
      return true;
    } catch {
      if (requestId !== listRequest) return false;
      tasks = [];
      list.replaceChildren();
      clearDetail("Task details are unavailable until the Task list can be loaded.");
      setState(listState, "Task list could not be loaded. Please retry.", "error-state");
      return false;
    }
  }

  async function refreshAfterMissingTask(taskId) {
    const refreshed = await loadTasks();
    if (refreshed) {
      tasks = tasks.filter(({ id }) => id !== taskId);
      renderTaskList();
    }
  }

  async function loadTaskDetail(taskId) {
    const requestId = ++detailRequest;
    selectedTaskId = taskId;
    renderTaskList();
    detail.replaceChildren();
    detail.hidden = true;
    clearPreview("Select a task to preview routing.");
    setState(detailState, "Loading Task details…");
    try {
      const response = await fetchImpl(
        `/api/tasks/${encodeURIComponent(taskId)}`,
        { ...readOptions },
      );
      if (requestId !== detailRequest) return;
      if (!response.ok) {
        if (response.status === 404) {
          clearDetail(errorMessage(404, "task-detail"));
          setState(detailState, errorMessage(404, "task-detail"), "error-state");
          await refreshAfterMissingTask(taskId);
          return;
        }
        setState(detailState, errorMessage(response.status, "task-detail"), "error-state");
        return;
      }
      const task = await response.json();
      if (requestId !== detailRequest) return;
      if (!validTask(task) || task.id !== taskId) {
        setState(detailState, "Task detail response was invalid.", "error-state");
        return;
      }
      renderTaskDetail(task);
      setState(detailState, "Task details loaded.", "success-state");
    } catch {
      if (requestId === detailRequest) {
        setState(detailState, "Task details could not be loaded. Please retry.", "error-state");
      }
    }
  }

  async function runDryRun(taskId) {
    const requestId = ++previewRequest;
    preview.replaceChildren();
    preview.hidden = true;
    setState(previewState, "Loading routing preview…");
    try {
      const response = await fetchImpl(`/api/tasks/${encodeURIComponent(taskId)}/dry-run`, {
        credentials: "same-origin",
        method: "POST",
        headers: { Accept: "application/json" },
      });
      if (requestId !== previewRequest) return;
      if (!response.ok) {
        if (response.status === 404) {
          clearDetail(errorMessage(404, "task-detail"));
          setState(detailState, errorMessage(404, "task-detail"), "error-state");
          await refreshAfterMissingTask(taskId);
          return;
        }
        setState(previewState, errorMessage(response.status, "task-preview"), "error-state");
        return;
      }
      const result = await response.json();
      if (requestId !== previewRequest) return;
      if (!validDryRun(result, taskId)) {
        setState(previewState, "Routing preview response was invalid.", "error-state");
        return;
      }
      renderDryRun(result);
      setState(previewState, "Routing preview loaded. No Task state was changed.", "success-state");
    } catch {
      if (requestId === previewRequest) {
        setState(previewState, "Routing preview could not be loaded. Please retry.", "error-state");
      }
    }
  }

  function buildCreateRequest() {
    const request = {
      title: formFields.title.value.trim(),
      description: formFields.description.value.trim(),
    };
    for (const field of ["project_id", "agent_id", "role", "capability"]) {
      const value = formFields[field].value.trim();
      if (value) request[field] = value;
    }
    if (!request.title || !request.description) {
      return { error: "Title and description are required." };
    }
    const selectors = ["agent_id", "role", "capability"].filter((field) => request[field]);
    if (selectors.length > 1) {
      return { error: "Choose no more than one routing selector: Agent ID, Employee role, or Agent capability." };
    }
    return { request };
  }

  async function createTask(event) {
    event.preventDefault();
    if (isCreating) return;
    const built = buildCreateRequest();
    if (built.error) {
      setState(createState, built.error, "error-state");
      return;
    }
    isCreating = true;
    createButton.disabled = true;
    setState(createState, "Creating Task…");
    try {
      const response = await fetchImpl("/api/tasks", {
        credentials: "same-origin",
        method: "POST",
        headers: { ...writeHeaders },
        body: JSON.stringify(built.request),
      });
      if (!response.ok) {
        const message = response.status === 422
          ? await validationMessage(response)
          : errorMessage(response.status, "task-create");
        setState(createState, message, "error-state");
        return;
      }
      const created = await response.json();
      if (!validTask(created)) {
        setState(createState, "Task creation could not be confirmed because the response was invalid.", "error-state");
        return;
      }
      form.reset();
      setState(createState, `Task ${created.id} created.`, "success-state");
      const refreshed = await loadTasks();
      if (refreshed && tasks.some(({ id }) => id === created.id)) {
        await loadTaskDetail(created.id);
      } else if (refreshed) {
        setState(createState, `Task ${created.id} was created but is not in the refreshed list.`, "error-state");
      } else {
        setState(createState, `Task ${created.id} was created but the list could not be refreshed.`, "error-state");
      }
    } catch {
      setState(createState, "Task creation could not be confirmed. Refresh before retrying.", "error-state");
    } finally {
      isCreating = false;
      createButton.disabled = false;
    }
  }

  refreshButton.addEventListener("click", () => void loadTasks());
  dispatchRefresh.addEventListener("click", () => void refreshDispatchQueue());
  dispatchResolve.addEventListener("click", () => void resolveDispatchEntry());
  form.addEventListener("submit", (event) => void createTask(event));
  const initialLoad = Promise.all([loadTasks(), refreshDispatchQueue()]);
  return {
    initialLoad,
    loadTasks,
    loadTaskDetail,
    runDryRun,
    createTask,
    buildCreateRequest,
    refreshDispatchQueue,
    dispatchTask,
    resolveDispatchEntry,
  };
}

const taskFieldsForCreation = [
  "title",
  "description",
  "project_id",
  "agent_id",
  "role",
  "capability",
];

if (typeof document !== "undefined") {
  mountTaskPage();
}

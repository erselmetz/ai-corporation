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

function validProject(project) {
  return Boolean(
    project &&
    typeof project.id === "string" &&
    typeof project.name === "string" &&
    typeof project.description === "string" &&
    typeof project.status === "string",
  );
}

function validProjectList(payload) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    Array.isArray(payload.items) &&
    payload.items.every(validProject),
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function errorMessage(status, action) {
  if (status === 401) return "Sign-in required. This browser session is not authenticated.";
  if (status === 403) return "Access denied. This account lacks the required Project permission.";
  if (status === 404) {
    return action === "project-create"
      ? "The Project API returned not found. Check the requested resource and retry."
      : "This Project no longer exists.";
  }
  if (status === 409) return "The Project conflicts with an existing Project. Please retry.";
  if (status === 422) return "The Project API rejected these fields. Check the Project name and description.";
  return "The request could not be completed. Please retry.";
}

async function validationMessage(response) {
  const allowedFields = new Set(["name", "description"]);
  try {
    const payload = await response.json();
    const issues = Array.isArray(payload?.detail)
      ? payload.detail
          .filter((issue) =>
            Array.isArray(issue?.loc) &&
            allowedFields.has(issue.loc.at(-1)) &&
            typeof issue.msg === "string",
          )
          .map((issue) => `${issue.loc.at(-1)}: ${issue.msg}`)
      : [];
    return issues.length
      ? `Validation failed: ${issues.join("; ")}.`
      : errorMessage(422, "project-create");
  } catch {
    return errorMessage(422, "project-create");
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

export function mountProjectPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
}) {
  const list = documentRef.getElementById("project-list");
  const listState = documentRef.getElementById("project-list-state");
  const refreshButton = documentRef.getElementById("project-refresh");
  const detail = documentRef.getElementById("project-detail");
  const detailState = documentRef.getElementById("project-detail-state");
  const form = documentRef.getElementById("project-create-form");
  const nameInput = documentRef.getElementById("project-name");
  const descriptionInput = documentRef.getElementById("project-description");
  const createButton = documentRef.getElementById("project-create-submit");
  const createState = documentRef.getElementById("project-create-state");

  let projects = [];
  let selectedProjectId = null;
  let listRequest = 0;
  let detailRequest = 0;
  let isCreating = false;

  function clearDetails(message = "Select a project to view its details.") {
    selectedProjectId = null;
    detailRequest += 1;
    detail.replaceChildren();
    detail.hidden = true;
    setState(detailState, message);
  }

  function renderProjectList() {
    list.replaceChildren();
    if (projects.length === 0) {
      setState(listState, "No projects found.", "empty-state");
      return;
    }
    setState(
      listState,
      `${projects.length} project record${projects.length === 1 ? "" : "s"} loaded.`,
      "success-state",
    );
    for (const project of projects) {
      const item = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.className = "record-select";
      button.setAttribute("aria-pressed", String(project.id === selectedProjectId));
      button.textContent = `${project.name} · ${project.status} · ${project.id}`;
      button.addEventListener("click", () => void loadProjectDetail(project.id));
      item.append(button);
      list.append(item);
    }
  }

  function renderProjectDetail(project) {
    detail.replaceChildren();
    const definitions = documentRef.createElement("dl");
    definitions.className = "identity-list";
    appendDefinition(documentRef, definitions, "Project ID", project.id);
    appendDefinition(documentRef, definitions, "Name", project.name);
    appendDefinition(documentRef, definitions, "Description", project.description);
    appendDefinition(documentRef, definitions, "Status", project.status);
    detail.append(definitions);
    detail.hidden = false;
  }

  async function loadProjects() {
    const requestId = ++listRequest;
    setState(listState, "Loading projects…");
    try {
      const response = await fetchImpl("/api/projects", { ...readOptions });
      if (requestId !== listRequest) return false;
      if (!response.ok) {
        projects = [];
        list.replaceChildren();
        clearDetails("Project details are unavailable until the Project list can be loaded.");
        setState(listState, errorMessage(response.status, "project-list"), "error-state");
        return false;
      }
      const payload = await response.json();
      if (requestId !== listRequest) return false;
      if (!validProjectList(payload)) {
        projects = [];
        list.replaceChildren();
        clearDetails("Project details are unavailable because the list response was invalid.");
        setState(listState, "Project list response was invalid.", "error-state");
        return false;
      }
      projects = payload.items;
      if (selectedProjectId && !projects.some(({ id }) => id === selectedProjectId)) {
        clearDetails("The selected Project is no longer in the list.");
      }
      renderProjectList();
      return true;
    } catch {
      if (requestId !== listRequest) return false;
      projects = [];
      list.replaceChildren();
      clearDetails("Project details are unavailable until the Project list can be loaded.");
      setState(listState, "Project list could not be loaded. Please retry.", "error-state");
      return false;
    }
  }

  async function refreshAfterMissingProject(projectId) {
    const refreshed = await loadProjects();
    if (refreshed) {
      projects = projects.filter(({ id }) => id !== projectId);
      renderProjectList();
    }
  }

  async function loadProjectDetail(projectId) {
    const requestId = ++detailRequest;
    selectedProjectId = projectId;
    renderProjectList();
    detail.replaceChildren();
    detail.hidden = true;
    setState(detailState, "Loading Project details…");
    try {
      const response = await fetchImpl(
        `/api/projects/${encodeURIComponent(projectId)}`,
        { ...readOptions },
      );
      if (requestId !== detailRequest) return false;
      if (!response.ok) {
        if (response.status === 404) {
          clearDetails(errorMessage(404, "project-detail"));
          setState(detailState, errorMessage(404, "project-detail"), "error-state");
          await refreshAfterMissingProject(projectId);
          setState(detailState, errorMessage(404, "project-detail"), "error-state");
          return false;
        }
        setState(detailState, errorMessage(response.status, "project-detail"), "error-state");
        return false;
      }
      const project = await response.json();
      if (requestId !== detailRequest) return false;
      if (!validProject(project) || project.id !== projectId) {
        setState(detailState, "Project detail response was invalid.", "error-state");
        return false;
      }
      renderProjectDetail(project);
      setState(detailState, "Project details loaded.", "success-state");
      return true;
    } catch {
      if (requestId === detailRequest) {
        setState(detailState, "Project details could not be loaded. Please retry.", "error-state");
      }
      return false;
    }
  }

  async function createProject(event) {
    event.preventDefault();
    if (isCreating) return;
    const name = nameInput.value.trim();
    const description = descriptionInput.value.trim();
    if (!name) {
      setState(createState, "Project name is required.", "error-state");
      return;
    }

    isCreating = true;
    createButton.disabled = true;
    setState(createState, "Creating Project…");
    try {
      const response = await fetchImpl("/api/projects", {
        ...writeOptions,
        method: "POST",
        body: JSON.stringify({ name, description }),
      });
      if (!response.ok) {
        const message = response.status === 422
          ? await validationMessage(response)
          : errorMessage(response.status, "project-create");
        setState(createState, message, "error-state");
        return;
      }
      const created = await response.json();
      if (!validProject(created)) {
        setState(createState, "Project creation could not be confirmed because the response was invalid.", "error-state");
        return;
      }
      form.reset();
      setState(createState, `Project ${created.id} created.`, "success-state");
      const refreshed = await loadProjects();
      if (!refreshed) {
        setState(createState, `Project ${created.id} was created, but the list could not be refreshed.`, "error-state");
        return;
      }
      if (!projects.some(({ id }) => id === created.id)) {
        setState(createState, `Project ${created.id} was created but is not in the refreshed list.`, "error-state");
        return;
      }
      const detailsLoaded = await loadProjectDetail(created.id);
      if (detailsLoaded) {
        setState(createState, `Project ${created.id} created and loaded from the API.`, "success-state");
      } else {
        setState(createState, `Project ${created.id} was created, but its details could not be loaded.`, "error-state");
      }
    } catch {
      setState(createState, "Project creation could not be confirmed. Refresh before retrying.", "error-state");
    } finally {
      isCreating = false;
      createButton.disabled = false;
    }
  }

  refreshButton.addEventListener("click", () => void loadProjects());
  form.addEventListener("submit", (event) => void createProject(event));
  const initialLoad = loadProjects();
  return {
    initialLoad,
    loadProjects,
    loadProjectDetail,
    createProject,
  };
}

if (typeof document !== "undefined") {
  mountProjectPage();
}

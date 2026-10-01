const readOptions = {
  credentials: "same-origin",
  headers: { Accept: "application/json" },
};

const writeHeaders = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

function validProvider(provider) {
  return Boolean(
    provider &&
    typeof provider.id === "string" &&
    typeof provider.type === "string",
  );
}

function validProviderList(payload) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    Array.isArray(payload.items) &&
    payload.items.every(validProvider),
  );
}

function validAssignment(assignment) {
  return Boolean(
    assignment &&
    typeof assignment.agent_id === "string" &&
    typeof assignment.provider_id === "string" &&
    typeof assignment.model_id === "string",
  );
}

function validAssignmentList(payload) {
  return Boolean(
    payload &&
    typeof payload === "object" &&
    Array.isArray(payload.items) &&
    payload.items.every(validAssignment),
  );
}

function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function errorMessage(status, action) {
  if (status === 401) return "Sign-in required. This browser session is not authenticated.";
  if (status === 403) return "Access denied. This account lacks the required permission.";
  if (status === 404) {
    if (action === "provider-detail") return "This provider no longer exists.";
    if (action === "provider-delete") return "This provider no longer exists. The provider list was refreshed.";
    return "The Agent or Provider was not found. Check the IDs and refresh the data.";
  }
  if (status === 409) return "A provider with this ID already exists.";
  if (status === 422) return "The API rejected the submitted fields. Check the Provider ID/name or Provider ID/model ID.";
  return "The request could not be completed. Please retry.";
}

async function responseErrorMessage(response, action) {
  const fallback = errorMessage(response.status, action);
  if (response.status !== 422) return fallback;
  const allowedFields = action === "provider-create"
    ? new Set(["id", "name"])
    : new Set(["provider_id", "model_id"]);
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
    if (issues.length > 0) return `Validation failed: ${issues.join("; ")}.`;
  } catch {
    return fallback;
  }
  return fallback;
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

export function mountProviderModelPage({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  confirmImpl = globalThis.confirm,
}) {
  const providerList = documentRef.getElementById("provider-list");
  const providerListState = documentRef.getElementById("provider-list-state");
  const providerDetail = documentRef.getElementById("provider-detail");
  const providerDetailState = documentRef.getElementById("provider-detail-state");
  const providerRefresh = documentRef.getElementById("provider-refresh");
  const providerForm = documentRef.getElementById("provider-create-form");
  const providerIdInput = documentRef.getElementById("provider-id");
  const providerNameInput = documentRef.getElementById("provider-name");
  const providerCreateButton = documentRef.getElementById("provider-create-submit");
  const providerCreateState = documentRef.getElementById("provider-create-state");

  const modelList = documentRef.getElementById("model-list");
  const modelListState = documentRef.getElementById("model-list-state");
  const modelDetail = documentRef.getElementById("model-detail");
  const modelDetailState = documentRef.getElementById("model-detail-state");
  const modelRefresh = documentRef.getElementById("model-refresh");

  let providers = [];
  let assignments = [];
  let selectedProviderId = null;
  let selectedAgentId = null;
  let providerListRequest = 0;
  let modelListRequest = 0;
  let providerDetailRequest = 0;
  let modelDetailRequest = 0;
  let isCreatingProvider = false;
  let isDeletingProvider = false;
  let isReplacingModel = false;

  function clearProviderDetail(message = "Select a provider to view details.") {
    selectedProviderId = null;
    providerDetailRequest += 1;
    providerDetail.replaceChildren();
    providerDetail.hidden = true;
    setState(providerDetailState, message);
  }

  function clearModelDetail(message = "Select an assignment to inspect or replace it.") {
    selectedAgentId = null;
    modelDetailRequest += 1;
    modelDetail.replaceChildren();
    modelDetail.hidden = true;
    setState(modelDetailState, message);
  }

  function renderProviderList() {
    providerList.replaceChildren();
    if (providers.length === 0) {
      setState(providerListState, "No providers found.", "empty-state");
      return;
    }
    setState(
      providerListState,
      `${providers.length} configured provider${providers.length === 1 ? "" : "s"} loaded.`,
      "success-state",
    );
    for (const provider of providers) {
      const item = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.className = "record-select";
      button.setAttribute("aria-pressed", String(provider.id === selectedProviderId));
      button.textContent = `${provider.id} · ${provider.type}`;
      button.addEventListener("click", () => loadProviderDetail(provider.id));
      item.append(button);
      providerList.append(item);
    }
  }

  function renderAssignments() {
    modelList.replaceChildren();
    if (assignments.length === 0) {
      setState(modelListState, "No model assignments found.", "empty-state");
      return;
    }
    setState(
      modelListState,
      `${assignments.length} Agent model assignment${assignments.length === 1 ? "" : "s"} loaded.`,
      "success-state",
    );
    for (const assignment of assignments) {
      const item = documentRef.createElement("li");
      const button = documentRef.createElement("button");
      button.type = "button";
      button.className = "record-select";
      button.setAttribute("aria-pressed", String(assignment.agent_id === selectedAgentId));
      button.textContent = `${assignment.agent_id} · ${assignment.provider_id} · ${assignment.model_id}`;
      button.addEventListener("click", () => loadModelDetail(assignment.agent_id));
      item.append(button);
      modelList.append(item);
    }
  }

  function renderProviderDetail(provider) {
    providerDetail.replaceChildren();
    const details = documentRef.createElement("dl");
    details.className = "identity-list";
    appendDefinition(documentRef, details, "Provider ID", provider.id);
    appendDefinition(documentRef, details, "Configured type", provider.type);
    const removeButton = documentRef.createElement("button");
    removeButton.type = "button";
    removeButton.className = "danger-button";
    removeButton.textContent = "Remove provider";
    removeButton.addEventListener("click", () => removeProvider(provider));
    providerDetail.append(details, removeButton);
    providerDetail.hidden = false;
  }

  function renderModelDetail(assignment) {
    modelDetail.replaceChildren();
    const details = documentRef.createElement("dl");
    details.className = "identity-list";
    appendDefinition(documentRef, details, "Agent ID", assignment.agent_id);
    appendDefinition(documentRef, details, "Provider ID", assignment.provider_id);
    appendDefinition(documentRef, details, "Model ID", assignment.model_id);

    const form = documentRef.createElement("form");
    form.className = "model-replace-form";
    const providerLabel = documentRef.createElement("label");
    providerLabel.textContent = "Provider ID";
    const providerInput = documentRef.createElement("input");
    providerInput.name = "provider_id";
    providerInput.required = true;
    providerInput.value = assignment.provider_id;
    providerLabel.append(providerInput);

    const modelLabel = documentRef.createElement("label");
    modelLabel.textContent = "Model ID";
    const modelInput = documentRef.createElement("input");
    modelInput.name = "model_id";
    modelInput.required = true;
    modelInput.value = assignment.model_id;
    modelLabel.append(modelInput);

    const submit = documentRef.createElement("button");
    submit.type = "submit";
    submit.textContent = "Replace assignment";
    const status = documentRef.createElement("p");
    status.className = "section-state";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    form.addEventListener("submit", (event) => {
      void replaceModelAssignment(assignment.agent_id, providerInput, modelInput, submit, status, event);
    });
    form.append(providerLabel, modelLabel, submit, status);
    modelDetail.append(details, form);
    modelDetail.hidden = false;
  }

  async function loadProviders() {
    const requestId = ++providerListRequest;
    setState(providerListState, "Loading providers…");
    try {
      const response = await fetchImpl("/api/providers", { ...readOptions });
      if (requestId !== providerListRequest) return false;
      if (!response.ok) {
        providers = [];
        providerList.replaceChildren();
        clearProviderDetail("Provider details are unavailable until the list can be loaded.");
        setState(providerListState, errorMessage(response.status, "provider-list"), "error-state");
        return false;
      }
      const payload = await response.json();
      if (requestId !== providerListRequest) return false;
      if (!validProviderList(payload)) {
        providers = [];
        providerList.replaceChildren();
        clearProviderDetail("Provider details are unavailable because the list response was invalid.");
        setState(providerListState, "Provider list response was invalid.", "error-state");
        return false;
      }

      providers = payload.items;
      if (selectedProviderId && !providers.some(({ id }) => id === selectedProviderId)) {
        clearProviderDetail("The selected provider is no longer in the list.");
      }
      renderProviderList();
      return true;
    } catch {
      if (requestId !== providerListRequest) return false;
      providers = [];
      providerList.replaceChildren();
      clearProviderDetail("Provider details are unavailable until the list can be loaded.");
      setState(providerListState, "Provider list could not be loaded. Please retry.", "error-state");
      return false;
    }
  }

  async function loadProviderDetail(providerId) {
    const requestId = ++providerDetailRequest;
    selectedProviderId = providerId;
    renderProviderList();
    providerDetail.replaceChildren();
    providerDetail.hidden = true;
    setState(providerDetailState, "Loading provider details…");
    try {
      const response = await fetchImpl(
        `/api/providers/${encodeURIComponent(providerId)}`,
        { ...readOptions },
      );
      if (requestId !== providerDetailRequest) return;
      if (!response.ok) {
        if (response.status === 404) {
          clearProviderDetail(errorMessage(404, "provider-detail"));
          setState(providerDetailState, errorMessage(404, "provider-detail"), "error-state");
          await loadProviders();
          return;
        }
        setState(providerDetailState, errorMessage(response.status, "provider-detail"), "error-state");
        return;
      }
      const provider = await response.json();
      if (requestId !== providerDetailRequest) return;
      if (!validProvider(provider)) {
        setState(providerDetailState, "Provider detail response was invalid.", "error-state");
        return;
      }
      renderProviderDetail(provider);
      setState(providerDetailState, "Provider details loaded.", "success-state");
    } catch {
      if (requestId === providerDetailRequest) {
        setState(providerDetailState, "Provider details could not be loaded. Please retry.", "error-state");
      }
    }
  }

  async function createProvider(event) {
    event.preventDefault();
    if (isCreatingProvider) return;
    const provider = {
      id: providerIdInput.value.trim(),
      name: providerNameInput.value.trim(),
    };
    if (!provider.id || !provider.name) {
      setState(providerCreateState, "Provider ID and name are required.", "error-state");
      return;
    }

    isCreatingProvider = true;
    providerCreateButton.disabled = true;
    setState(providerCreateState, "Creating provider…");
    try {
      const response = await fetchImpl("/api/providers", {
        credentials: "same-origin",
        method: "POST",
        headers: { ...writeHeaders },
        body: JSON.stringify(provider),
      });
      if (!response.ok) {
        setState(providerCreateState, await responseErrorMessage(response, "provider-create"), "error-state");
        return;
      }
      const created = await response.json();
      if (!validProvider(created)) {
        setState(providerCreateState, "Provider creation could not be confirmed because the response was invalid.", "error-state");
        return;
      }
      providerForm.reset();
      setState(providerCreateState, `Provider ${created.id} created.`, "success-state");
      const refreshed = await loadProviders();
      if (refreshed && providers.some(({ id }) => id === created.id)) {
        await loadProviderDetail(created.id);
      } else if (refreshed) {
        setState(providerCreateState, `Provider ${created.id} was created but is not in the refreshed list.`, "error-state");
      } else {
        setState(providerCreateState, `Provider ${created.id} was created but the list could not be refreshed.`, "error-state");
      }
    } catch {
      setState(providerCreateState, "Provider creation could not be confirmed. Refresh before retrying.", "error-state");
    } finally {
      isCreatingProvider = false;
      providerCreateButton.disabled = false;
    }
  }

  async function removeProvider(provider) {
    if (isDeletingProvider) return;
    if (!confirmImpl(`Remove Provider ${provider.id} (${provider.type})? This action cannot be undone.`)) return;
    isDeletingProvider = true;
    const button = providerDetail.querySelector(".danger-button");
    if (button) button.disabled = true;
    setState(providerDetailState, "Removing provider…");
    try {
      const response = await fetchImpl(
        `/api/providers/${encodeURIComponent(provider.id)}`,
        {
          method: "DELETE",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        },
      );
      if (!response.ok) {
        if (response.status === 404) {
          clearProviderDetail(errorMessage(404, "provider-delete"));
          setState(providerDetailState, errorMessage(404, "provider-delete"), "error-state");
          await loadProviders();
          return;
        }
        setState(providerDetailState, errorMessage(response.status, "provider-delete"), "error-state");
        return;
      }
      clearProviderDetail(`Provider ${provider.id} was removed.`);
      const refreshed = await loadProviders();
      if (refreshed) {
        setState(providerDetailState, `Provider ${provider.id} was removed.`, "success-state");
      } else {
        setState(
          providerDetailState,
          `Provider ${provider.id} was removed, but the provider list could not be refreshed.`,
          "error-state",
        );
      }
    } catch {
      setState(providerDetailState, "Provider removal could not be confirmed. Refresh before retrying.", "error-state");
    } finally {
      if (button) button.disabled = false;
      isDeletingProvider = false;
    }
  }

  async function loadAssignments() {
    const requestId = ++modelListRequest;
    setState(modelListState, "Loading model assignments…");
    try {
      const response = await fetchImpl("/api/models", { ...readOptions });
      if (requestId !== modelListRequest) return false;
      if (!response.ok) {
        assignments = [];
        modelList.replaceChildren();
        clearModelDetail("Assignment details are unavailable until the list can be loaded.");
        setState(modelListState, errorMessage(response.status, "model-list"), "error-state");
        return false;
      }
      const payload = await response.json();
      if (requestId !== modelListRequest) return false;
      if (!validAssignmentList(payload)) {
        assignments = [];
        modelList.replaceChildren();
        clearModelDetail("Assignment details are unavailable because the list response was invalid.");
        setState(modelListState, "Model assignment list response was invalid.", "error-state");
        return false;
      }
      assignments = payload.items;
      if (!assignments.some(({ agent_id: id }) => id === selectedAgentId)) {
        clearModelDetail("The selected assignment is no longer in the list.");
      }
      renderAssignments();
      return true;
    } catch {
      if (requestId !== modelListRequest) return false;
      assignments = [];
      modelList.replaceChildren();
      clearModelDetail("Assignment details are unavailable until the list can be loaded.");
      setState(modelListState, "Model assignments could not be loaded. Please retry.", "error-state");
      return false;
    }
  }

  async function loadModelDetail(agentId) {
    const requestId = ++modelDetailRequest;
    selectedAgentId = agentId;
    renderAssignments();
    modelDetail.replaceChildren();
    modelDetail.hidden = true;
    setState(modelDetailState, "Loading assignment details…");
    try {
      const response = await fetchImpl(
        `/api/models/${encodeURIComponent(agentId)}`,
        { ...readOptions },
      );
      if (requestId !== modelDetailRequest) return;
      if (!response.ok) {
        if (response.status === 404) {
          clearModelDetail(errorMessage(404, "model-detail"));
          await loadAssignments();
          setState(modelDetailState, errorMessage(404, "model-detail"), "error-state");
          return;
        }
        setState(modelDetailState, errorMessage(response.status, "model-detail"), "error-state");
        return;
      }
      const assignment = await response.json();
      if (requestId !== modelDetailRequest) return;
      if (!validAssignment(assignment)) {
        setState(modelDetailState, "Model assignment response was invalid.", "error-state");
        return;
      }
      renderModelDetail(assignment);
      setState(modelDetailState, "Assignment details loaded.", "success-state");
    } catch {
      if (requestId === modelDetailRequest) {
        setState(modelDetailState, "Assignment details could not be loaded. Please retry.", "error-state");
      }
    }
  }

  async function replaceModelAssignment(agentId, providerInput, modelInput, submit, state, event) {
    event.preventDefault();
    if (isReplacingModel) return;
    const replacement = {
      provider_id: providerInput.value.trim(),
      model_id: modelInput.value.trim(),
    };
    if (!replacement.provider_id || !replacement.model_id) {
      setState(state, "Provider ID and model ID are required.", "error-state");
      return;
    }

    isReplacingModel = true;
    submit.disabled = true;
    setState(state, "Replacing model assignment…");
    try {
      const response = await fetchImpl(`/api/models/${encodeURIComponent(agentId)}`, {
        credentials: "same-origin",
        method: "PUT",
        headers: { ...writeHeaders },
        body: JSON.stringify(replacement),
      });
      if (!response.ok) {
        setState(state, await responseErrorMessage(response, "model-replace"), "error-state");
        return;
      }
      const result = await response.json();
      if (!validAssignment(result) || result.agent_id !== agentId) {
        setState(state, "Model replacement could not be confirmed because the response was invalid.", "error-state");
        return;
      }
      setState(state, "Model assignment replaced.", "success-state");
      const refreshed = await loadAssignments();
      if (refreshed && assignments.some(({ agent_id: id }) => id === agentId)) {
        await loadModelDetail(agentId);
      } else if (refreshed) {
        setState(state, "Model assignment was replaced, but is not in the refreshed list.", "error-state");
      } else {
        setState(
          modelDetailState,
          "Model assignment was replaced, but the assignment list could not be refreshed.",
          "error-state",
        );
      }
    } catch {
      setState(state, "Model replacement could not be confirmed. Refresh before retrying.", "error-state");
    } finally {
      isReplacingModel = false;
      submit.disabled = false;
    }
  }

  providerRefresh.addEventListener("click", loadProviders);
  modelRefresh.addEventListener("click", loadAssignments);
  providerForm.addEventListener("submit", (event) => void createProvider(event));
  const initialLoad = Promise.all([loadProviders(), loadAssignments()]);
  return {
    initialLoad,
    loadProviders,
    loadProviderDetail,
    loadAssignments,
    loadModelDetail,
    createProvider,
    replaceModelAssignment,
  };
}

if (typeof document !== "undefined") {
  mountProviderModelPage();
}

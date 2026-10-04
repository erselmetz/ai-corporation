function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function isGeminiProvider(providerId) {
  return typeof providerId === "string"
    && (providerId === "gemini" || providerId.startsWith("gemini-"));
}

function validEmployee(item) {
  return Boolean(
    item &&
      typeof item.id === "string" &&
      typeof item.name === "string" &&
      typeof item.role === "string" &&
      (item.agent_id === null || typeof item.agent_id === "string"),
  );
}

function validConversation(item) {
  return Boolean(
    item &&
      typeof item.conversation_id === "string" &&
      typeof item.status === "string" &&
      typeof item.employee?.id === "string" &&
      typeof item.agent?.id === "string" &&
      typeof item.agent?.provider_id === "string" &&
      typeof item.agent?.model_id === "string",
  );
}

function validSnapshot(item) {
  return Boolean(
    item &&
      item.conversation &&
      typeof item.conversation.id === "string" &&
      typeof item.conversation.employee_id === "string" &&
      typeof item.conversation.agent_id === "string" &&
      Array.isArray(item.conversation.messages) &&
      item.conversation.messages.every(
        (message) =>
          typeof message.id === "string" &&
          typeof message.role === "string" &&
          typeof message.content === "string" &&
          typeof message.status === "string",
      ) &&
      typeof item.employee?.id === "string" &&
      typeof item.agent?.id === "string" &&
      typeof item.agent?.provider_id === "string" &&
      typeof item.agent?.model_id === "string",
  );
}

function errorMessage(status) {
  if (status === 401) return "Sign in through local owner access first.";
  if (status === 403) return "This session lacks Employee chat permission or Gemini consent.";
  if (status === 404) return "This Employee or conversation is unavailable to this account.";
  if (status === 409) return "The Employee or Agent assignment changed, or work is active. Refresh and start a new conversation.";
  if (status === 413) return "The individual chat request exceeded its size limit.";
  if (status === 422) return "The message or selected Employee is invalid. Gemini keys must use the separate setup page.";
  if (status === 429) return "The conversation or configured provider/model request-slot limit was reached.";
  if (status === 502) return "The assigned provider is unavailable or the reply failed. No automatic retry occurred.";
  if (status === 503) return "Provider capacity is UNKNOWN or the assigned provider is unavailable; the request was not admitted.";
  return "Individual chat could not be completed. Refresh and try again.";
}

export function mountEmployeeChat({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  confirmImpl = globalThis.confirm,
}) {
  const byId = (id) => documentRef.getElementById(id);
  const employeeSelect = byId("individual-employee");
  const conversationSelect = byId("individual-conversation");
  const state = byId("individual-chat-state");
  const identity = byId("individual-chat-identity");
  const history = byId("individual-chat-history");
  const form = byId("individual-chat-form");
  const message = byId("individual-chat-input");
  const consentPanel = byId("individual-cloud-consent-panel");
  const consent = byId("individual-cloud-consent");
  const newButton = byId("individual-chat-new");
  const refreshButton = byId("individual-chat-refresh");
  const closeButton = byId("individual-chat-close");
  let employees = [];
  let conversations = [];
  let current = null;
  let busy = false;

  function controls() {
    const open = current?.conversation.status === "open";
    employeeSelect.disabled = busy;
    conversationSelect.disabled = busy || !conversations.length;
    newButton.disabled = busy || !employeeSelect.value;
    refreshButton.disabled = busy;
    closeButton.disabled = busy || !open;
    message.disabled = busy || !open;
    byId("individual-chat-send").disabled =
      busy || !open || (isGeminiProvider(current?.agent.provider_id) && !consent.checked);
  }

  async function request(path, { method = "GET", body } = {}) {
    const options = {
      method,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    };
    if (method !== "GET") {
      const sessionResponse = await fetchImpl("/api/local/session", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!sessionResponse.ok) {
        throw Object.assign(new Error(), { status: sessionResponse.status });
      }
      const session = await sessionResponse.json();
      options.headers = {
        ...options.headers,
        "Content-Type": "application/json",
        "X-Local-CSRF": session.csrf,
      };
      options.body = JSON.stringify(body ?? {});
    }
    const response = await fetchImpl(path, options);
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    if (!response.ok) {
      throw Object.assign(new Error(), {
        status: response.status,
        detail: typeof data.detail === "string" ? data.detail : "",
      });
    }
    return data;
  }

  function renderHistory(snapshot) {
    history.replaceChildren();
    for (const item of snapshot.conversation.messages) {
      const row = documentRef.createElement("p");
      row.textContent = `${item.role} (${item.status}): ${item.content}`;
      history.append(row);
    }
    identity.textContent =
      `${snapshot.employee.name} · ${snapshot.employee.role} · ` +
      `Agent ${snapshot.agent.name} (${snapshot.agent.id}) · ` +
      `${snapshot.agent.provider_id}/${snapshot.agent.model_id} · ` +
      `${snapshot.conversation.status}`;
    consentPanel.hidden = !isGeminiProvider(snapshot.agent.provider_id);
    consent.checked = false;
    controls();
  }

  function renderConversations() {
    conversationSelect.replaceChildren();
    for (const item of conversations) {
      const option = documentRef.createElement("option");
      option.value = item.conversation_id;
      option.textContent =
        `${item.employee.name} · ${item.agent.name} · ` +
        `${item.agent.provider_id}/${item.agent.model_id} · ${item.status}`;
      conversationSelect.append(option);
    }
    if (!conversations.length) {
      current = null;
      history.replaceChildren();
      identity.textContent = "";
      consentPanel.hidden = true;
      setState(state, "No individual conversations are available in this app run.");
    }
    controls();
  }

  async function refresh() {
    if (busy) return false;
    busy = true;
    controls();
    setState(state, "Refreshing Employees and your conversations…");
    try {
      const [employeeResult, conversationResult] = await Promise.all([
        request("/api/employees"),
        request("/api/employee-chat/conversations"),
      ]);
      if (
        !Array.isArray(employeeResult.items) ||
        !employeeResult.items.every(validEmployee) ||
        !Array.isArray(conversationResult.items) ||
        !conversationResult.items.every(validConversation)
      ) {
        throw new Error("The Employee or conversation response was invalid.");
      }
      employees = employeeResult.items;
      employeeSelect.replaceChildren();
      for (const employee of employees.filter((item) => item.agent_id)) {
        const option = documentRef.createElement("option");
        option.value = employee.id;
        option.textContent = `${employee.name} · ${employee.role} · Agent ${employee.agent_id}`;
        employeeSelect.append(option);
      }
      conversations = conversationResult.items;
      renderConversations();
      if (!employees.some((item) => item.agent_id)) {
        setState(state, "No Employee currently has an assigned registered Agent.");
      } else if (conversations.length) {
        setState(state, `${conversations.length} individual conversation(s) loaded.`);
      } else {
        setState(state, "Choose an assigned Employee to start an isolated conversation.");
      }
      return true;
    } catch (error) {
      setState(
        state,
        error.status ? errorMessage(error.status) : "Employee chat could not load. Refresh and retry.",
        "error-state",
      );
      return false;
    } finally {
      busy = false;
      controls();
    }
  }

  async function loadConversation(identifier) {
    if (!identifier || busy) return false;
    busy = true;
    controls();
    try {
      const snapshot = await request(
        `/api/employee-chat/conversations/${encodeURIComponent(identifier)}`,
      );
      if (!validSnapshot(snapshot)) throw new Error("Invalid conversation response.");
      current = snapshot;
      renderHistory(snapshot);
      setState(state, "Conversation loaded.");
      return true;
    } catch (error) {
      current = null;
      setState(
        state,
        error.status ? errorMessage(error.status) : "Conversation could not load. Refresh and retry.",
        "error-state",
      );
      return false;
    } finally {
      busy = false;
      controls();
    }
  }

  async function startConversation() {
    if (busy || !employeeSelect.value) return false;
    busy = true;
    controls();
    try {
      const snapshot = await request("/api/employee-chat/conversations", {
        method: "POST",
        body: { employee_id: employeeSelect.value },
      });
      if (!validSnapshot(snapshot)) throw new Error("Invalid conversation response.");
      current = snapshot;
      await refreshAfterMutation();
      renderHistory(snapshot);
      setState(state, "New isolated Employee conversation started.");
      return true;
    } catch (error) {
      setState(
        state,
        error.status ? errorMessage(error.status) : "Conversation could not start. Refresh and retry.",
        "error-state",
      );
      return false;
    } finally {
      busy = false;
      controls();
    }
  }

  async function refreshAfterMutation() {
    const result = await request("/api/employee-chat/conversations");
    if (!Array.isArray(result.items) || !result.items.every(validConversation)) {
      throw new Error("Invalid conversation list response.");
    }
    conversations = result.items;
    renderConversations();
    conversationSelect.value = current?.conversation.id ?? "";
  }

  async function send(event) {
    event?.preventDefault();
    if (busy || !current || current.conversation.status !== "open") return false;
    if (!message.value.trim()) {
      setState(state, "Enter a message before sending.", "error-state");
      return false;
    }
    if (new TextEncoder().encode(message.value).length > 8192) {
      setState(state, "Messages are limited to 8192 UTF-8 bytes.", "error-state");
      return false;
    }
    busy = true;
    controls();
    try {
      const snapshot = await request(
        `/api/employee-chat/conversations/${encodeURIComponent(current.conversation.id)}/messages`,
        {
          method: "POST",
          body: { text: message.value, cloud_consent: consent.checked },
        },
      );
      if (!validSnapshot(snapshot)) throw new Error("Invalid conversation response.");
      current = snapshot;
      message.value = "";
      renderHistory(snapshot);
      await refreshAfterMutation();
      renderHistory(snapshot);
      setState(state, "Reply received.");
      return true;
    } catch (error) {
      setState(
        state,
        error.status
          ? (error.detail || errorMessage(error.status))
          : "Message outcome is uncertain. Refresh the conversation; it was not automatically replayed.",
        "error-state",
      );
      return false;
    } finally {
      busy = false;
      controls();
    }
  }

  async function closeConversation() {
    if (
      busy ||
      !current ||
      current.conversation.status !== "open" ||
      !confirmImpl("Close this conversation? Its in-memory history will be retained for this app run.")
    ) {
      return false;
    }
    busy = true;
    controls();
    try {
      const snapshot = await request(
        `/api/employee-chat/conversations/${encodeURIComponent(current.conversation.id)}/close`,
        { method: "POST", body: {} },
      );
      if (!validSnapshot(snapshot)) throw new Error("Invalid conversation response.");
      current = snapshot;
      renderHistory(snapshot);
      await refreshAfterMutation();
      renderHistory(snapshot);
      setState(state, "Conversation closed; its history remains isolated.");
      return true;
    } catch (error) {
      setState(
        state,
        error.status ? errorMessage(error.status) : "Conversation could not close. Refresh and retry.",
        "error-state",
      );
      return false;
    } finally {
      busy = false;
      controls();
    }
  }

  conversationSelect.addEventListener("change", () => {
    loadConversation(conversationSelect.value);
  });
  newButton.addEventListener("click", startConversation);
  refreshButton.addEventListener("click", refresh);
  closeButton.addEventListener("click", closeConversation);
  form.addEventListener("submit", send);
  consent.addEventListener("change", controls);
  controls();
  const initialLoad = refresh();
  return {
    initialLoad,
    refresh,
    loadConversation,
    startConversation,
    send,
    closeConversation,
  };
}

if (typeof document !== "undefined" && document.getElementById("individual-employee")) {
  mountEmployeeChat();
}

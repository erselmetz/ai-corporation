export function mountChat({
  documentRef = document,
  fetchImpl = fetch,
  confirmImpl = globalThis.confirm ?? (() => false),
} = {}) {
  const element = (id) => documentRef.getElementById(id);
  const state = element("chat-state");
  const history = element("chat-history");
  const agents = element("chat-agent");
  const conversations = element("chat-conversation");
  const input = element("chat-input");
  const cloudPanel = element("cloud-consent-panel");
  const cloudConsent = element("cloud-consent");
  const taskSource = element("chat-task-source");
  const taskAgent = element("chat-task-agent");
  const taskPrepare = element("chat-task-prepare");
  const taskConfirm = element("chat-task-confirm");
  const taskReview = element("chat-task-review");
  const taskState = element("chat-task-state");
  const taskFields = [
    taskSource, taskAgent, element("chat-task-objective"), element("chat-task-project"),
    element("chat-task-context-query"), element("chat-task-context-scope"),
    element("chat-task-context-id"), element("chat-task-outcome"),
    element("chat-task-verification"), element("chat-task-evidence"),
  ];
  const geminiKeyPattern = /\bAIza[A-Za-z0-9_-]{20,}\b|\b(?:GEMINI|GOOGLE)_API_KEY\s*=\s*\S+/i;
  const buttons = ["chat-start", "chat-send", "chat-close", "chat-refresh"].map(element);
  let busy = false;
  let selected = null;
  let canSend = false;
  let requiresCloudConsent = false;
  let canCreateTask = false;
  let currentProposal = null;
  const base = "/api/chat/conversations";
  function clear() {
    history.replaceChildren();
    element("chat-identity").textContent = "";
    selected = null;
    canSend = false;
    requiresCloudConsent = false;
    cloudPanel.hidden = true;
    cloudConsent.checked = false;
    input.disabled = true;
    clearTaskProposal();
    taskControls();
  }
  function clearTaskProposal() {
    currentProposal = null;
    taskReview.textContent = "";
    taskConfirm.disabled = true;
  }
  function taskControls() {
    taskFields.forEach(field => { field.disabled = busy || !canCreateTask; });
    taskPrepare.disabled = busy || !canCreateTask || !selected || !canSend;
    taskConfirm.disabled = busy || !canCreateTask || !currentProposal;
  }
  async function request(path, body) {
    const options = { credentials: "same-origin" };
    if (body !== undefined) {
      const session = await request("/api/local/session");
      options.method = "POST";
      options.headers = { "Content-Type": "application/json", "X-Local-CSRF": session.csrf };
      options.body = JSON.stringify(body);
    }
    const response = await fetchImpl(path, options);
    const payload = await response.json();
    if (!response.ok) {
      if (response.status === 401) throw new Error("Sign in through Local sign-in to continue.");
      if (response.status === 403) throw new Error("This session does not have permission for that chat action.");
      if (response.status === 502) throw new Error("Reply failed. Check that the configured service and model are available. No automatic retry occurred.");
      throw new Error(typeof payload.detail === "string" ? payload.detail : "Chat request failed.");
    }
    return payload;
  }
  function option(select, value, label) {
    const item = documentRef.createElement("option");
    item.value = value;
    item.textContent = label;
    select.append(item);
  }
  function render(result) {
    const record = result.conversation;
    const agent = result.coordinator;
    if (!record || !agent || typeof record.id !== "string" || !Array.isArray(record.messages)
        || !["open", "closed"].includes(record.status)) throw new Error("Invalid conversation response.");
    selected = record.id;
    requiresCloudConsent = agent.provider === "gemini";
    cloudPanel.hidden = !requiresCloudConsent;
    cloudConsent.checked = false;
    conversations.value = record.id;
    element("chat-identity").textContent = `${agent.name} (${agent.role}) | ${agent.provider} / ${agent.model} | ${record.status}`;
    history.replaceChildren();
    taskSource.replaceChildren();
    option(taskSource, "", "Select a completed coordinator proposal");
    for (const message of record.messages) {
      if (typeof message.content !== "string" || !["user", "assistant", "system"].includes(message.role)
          || !["pending", "completed", "failed"].includes(message.status)) throw new Error("Invalid message response.");
      const item = documentRef.createElement("article");
      item.className = "chat-message";
      const label = documentRef.createElement("strong");
      label.textContent = `${message.role} - ${message.status}`;
      const content = documentRef.createElement("p");
      content.textContent = message.content;
      item.append(label, content);
      history.append(item);
      if (message.role === "assistant" && message.status === "completed" && typeof message.id === "string") {
        option(taskSource, message.id, `Coordinator proposal - ${message.content.slice(0, 100)}`);
      }
    }
    state.textContent = record.status === "closed" ? "Conversation closed. Start a new conversation to send." : "Ready. Responses are complete messages; streaming is not available.";
    canSend = record.status === "open";
    input.disabled = !canSend;
    clearTaskProposal();
    taskControls();
  }
  async function action(operation) {
    if (busy) return false;
    busy = true;
    buttons.forEach(button => { button.disabled = true; });
    agents.disabled = true; conversations.disabled = true;
    taskControls();
    try { await operation(); return true; }
    catch (error) { state.textContent = error.message; return false; }
    finally {
      busy = false;
      buttons.forEach(button => { button.disabled = false; });
      agents.disabled = false; conversations.disabled = false;
      taskControls();
    }
  }
  async function refresh() {
    return action(async () => {
      clear();
      clearTaskProposal();
      agents.replaceChildren(); conversations.replaceChildren();
      state.textContent = "Loading authorized chat records…";
      try {
        const session = await request("/api/local/session");
        canCreateTask = Array.isArray(session.permissions)
          && session.permissions.includes("chat-task:create");
      } catch {
        canCreateTask = false;
      }
      taskState.textContent = canCreateTask
        ? "Prepare and inspect a proposal before explicit confirmation."
        : "Task proposal review is unavailable: this session lacks chat-task:create permission.";
      const agentList = await request("/api/agents");
      const list = await request(base);
      if (!Array.isArray(agentList.items) || !Array.isArray(list.items)) throw new Error("Invalid chat list response.");
      agents.replaceChildren(); conversations.replaceChildren();
      taskAgent.replaceChildren();
      option(taskAgent, "", "Select the responsible Agent");
      option(conversations, "", "Select an existing conversation");
      for (const agent of agentList.items) {
        const label = `${agent.name} | ${agent.provider} / ${agent.model}`;
        option(agents, agent.id, label);
        option(taskAgent, agent.id, `${agent.name} | ${agent.role}`);
      }
      for (const item of list.items) option(conversations, item.id, `${item.coordinator.name} - ${item.id.slice(0, 8)}`);
      state.textContent = agentList.items.length ? "Choose a coordinator and start a conversation." : "No registered coordinator is available.";
    });
  }
  async function start() {
    return action(async () => {
      if (!agents.value) throw new Error("Choose a coordinator first.");
      state.textContent = "Starting conversation…";
      const result = await request(base, { agent_id: agents.value });
      option(conversations, result.conversation.id, `${result.coordinator.name} - ${result.conversation.id.slice(0, 8)}`);
      input.disabled = false;
      render(result);
    });
  }
  async function load() {
    return action(async () => {
      const identifier = conversations.value;
      clear();
      if (!identifier) { state.textContent = "Choose a conversation or start a new one."; return; }
      state.textContent = "Loading conversation…";
      render(await request(`${base}/${encodeURIComponent(identifier)}`));
    });
  }
  async function send(event) {
    event?.preventDefault();
    return action(async () => {
      const text = input.value;
      if (!selected || !canSend) throw new Error("Start or select an open conversation first.");
      if (!text.trim() || new TextEncoder().encode(text).length > 8192) throw new Error("Enter a message of at most 8192 UTF-8 bytes.");
      if (geminiKeyPattern.test(text)) {
        input.value = "";
        throw new Error("This message looks like it contains a Gemini API key. It was not saved or sent. Use the Gemini online setup page to connect a key.");
      }
      if (requiresCloudConsent && !cloudConsent.checked) throw new Error("Consent to send this message and chat context to Google Gemini before continuing.");
      const identifier = selected;
      input.disabled = true;
      state.textContent = "Pending: waiting for the configured model. Closing this page does not cancel its request.";
      try {
        const body = requiresCloudConsent ? { text, cloud_consent: true } : { text };
        const result = await request(`${base}/${encodeURIComponent(identifier)}/messages`, body);
        input.value = "";
        render(result);
      } catch (error) {
        // Inspect recorded failure; never replay a possibly executed turn.
        try { render(await request(`${base}/${encodeURIComponent(identifier)}`)); } catch { clear(); }
        throw error;
      } finally { input.disabled = !canSend; }
    });
  }
  async function close() {
    return action(async () => {
      if (!selected) throw new Error("Select a conversation first.");
      render(await request(`${base}/${encodeURIComponent(selected)}/close`, {}));
    });
  }
  async function prepareTaskProposal() {
    return action(async () => {
      if (!selected || !canSend || !canCreateTask) {
        throw new Error("An open conversation and chat-task:create permission are required.");
      }
      const scope = element("chat-task-context-scope").value;
      const body = {
        source_message_id: taskSource.value,
        objective: element("chat-task-objective").value,
        project_id: element("chat-task-project").value,
        agent_id: taskAgent.value,
        expected_outcome: element("chat-task-outcome").value,
        verification_method: element("chat-task-verification").value,
        expected_evidence: element("chat-task-evidence").value,
      };
      if (scope) {
        body.context_query = element("chat-task-context-query").value;
        body.context_scope = scope;
        body.context_scope_id = element("chat-task-context-id").value;
      }
      const proposal = await request(
        `${base}/${encodeURIComponent(selected)}/task-proposals`,
        body,
      );
      if (typeof proposal.proposal_id !== "string"
          || typeof proposal.proposal_digest !== "string"
          || !proposal.task || !proposal.responsible_agent || !proposal.outcome) {
        throw new Error("Invalid Task proposal response.");
      }
      currentProposal = proposal;
      taskReview.textContent = JSON.stringify(proposal, null, 2);
      taskState.textContent = "Review the objective, Agent, authorized context, outcome, evidence, and canonical Task fields above. No Task has been created.";
      taskControls();
    });
  }
  async function confirmTaskProposal() {
    return action(async () => {
      if (!currentProposal || !selected || !canCreateTask) {
        throw new Error("Prepare a proposal and sign in with the required permission first.");
      }
      if (!confirmImpl("Create this reviewed Task as pending? It will not execute.")) {
        taskState.textContent = "Confirmation cancelled. No Task was created.";
        return;
      }
      const result = await request(
        `${base}/${encodeURIComponent(selected)}/task-proposals/${encodeURIComponent(currentProposal.proposal_id)}/confirm`,
        { proposal_digest: currentProposal.proposal_digest, confirmed: true },
      );
      currentProposal = null;
      taskReview.textContent = JSON.stringify(result, null, 2);
      taskState.textContent = "Confirmed Task created as pending. No execution occurred.";
    });
  }
  element("chat-start").addEventListener("click", start);
  element("chat-form").addEventListener("submit", send);
  element("chat-close").addEventListener("click", close);
  element("chat-refresh").addEventListener("click", refresh);
  taskPrepare.addEventListener("click", prepareTaskProposal);
  taskConfirm.addEventListener("click", confirmTaskProposal);
  conversations.addEventListener("change", load);
  return {
    initialLoad: refresh(),
    refresh,
    start,
    load,
    send,
    close,
    prepareTaskProposal,
    confirmTaskProposal,
  };
}
if (typeof document !== "undefined") mountChat();

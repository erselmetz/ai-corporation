export function mountChat({ documentRef = document, fetchImpl = fetch } = {}) {
  const element = (id) => documentRef.getElementById(id);
  const state = element("chat-state");
  const history = element("chat-history");
  const agents = element("chat-agent");
  const conversations = element("chat-conversation");
  const input = element("chat-input");
  const cloudPanel = element("cloud-consent-panel");
  const cloudConsent = element("cloud-consent");
  const buttons = ["chat-start", "chat-send", "chat-close", "chat-refresh"].map(element);
  let busy = false;
  let selected = null;
  let canSend = false;
  let requiresCloudConsent = false;
  const base = "/api/chat/conversations";
  function clear() { history.replaceChildren(); element("chat-identity").textContent = ""; selected = null; canSend = false; requiresCloudConsent = false; cloudPanel.hidden = true; cloudConsent.checked = false; input.disabled = true; }
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
    }
    state.textContent = record.status === "closed" ? "Conversation closed. Start a new conversation to send." : "Ready. Responses are complete messages; streaming is not available.";
    canSend = record.status === "open";
    input.disabled = !canSend;
  }
  async function action(operation) {
    if (busy) return false;
    busy = true;
    buttons.forEach(button => { button.disabled = true; });
    agents.disabled = true; conversations.disabled = true;
    try { await operation(); return true; }
    catch (error) { state.textContent = error.message; return false; }
    finally {
      busy = false;
      buttons.forEach(button => { button.disabled = false; });
      agents.disabled = false; conversations.disabled = false;
    }
  }
  async function refresh() {
    return action(async () => {
      clear();
      agents.replaceChildren(); conversations.replaceChildren();
      state.textContent = "Loading authorized chat records…";
      const agentList = await request("/api/agents");
      const list = await request(base);
      if (!Array.isArray(agentList.items) || !Array.isArray(list.items)) throw new Error("Invalid chat list response.");
      agents.replaceChildren(); conversations.replaceChildren();
      option(conversations, "", "Select an existing conversation");
      for (const agent of agentList.items) option(agents, agent.id, `${agent.name} | ${agent.provider} / ${agent.model}`);
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
  element("chat-start").addEventListener("click", start);
  element("chat-form").addEventListener("submit", send);
  element("chat-close").addEventListener("click", close);
  element("chat-refresh").addEventListener("click", refresh);
  conversations.addEventListener("change", load);
  return { initialLoad: refresh(), refresh, start, load, send, close };
}
if (typeof document !== "undefined") mountChat();

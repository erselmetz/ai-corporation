import { mountVoiceControls } from "./voice.mjs";
import { mountScreenCapture } from "./screen-capture.mjs";
import { mountCameraCapture } from "./camera-capture.mjs";
import { mountChatImages } from "./chat-images.mjs";
import { renderSafeMarkdown } from "./chat-markdown.mjs";
import { formatDetails } from "./ui-details.mjs";
import { createChatWorkspace } from "./chat-workspace.mjs";
import { recordLastBrainRetrieval } from "./brain-graph.mjs";
import "./quick-start.mjs?v=195";

export function voiceTranscriptSourceLabel(source) {
  return ({
    local: "Browser on-device speech recognition (local)",
    "local-model": "Selected local speech model",
    gemini: "Google Gemini (online, explicitly consented for this recording)",
  })[source] || "Unverified speech source";
}

function isGeminiProvider(providerId) {
  return typeof providerId === "string"
    && (providerId === "gemini" || providerId.startsWith("gemini-"));
}

export function mountChat({
  documentRef = document,
  fetchImpl = fetch,
  confirmImpl = globalThis.confirm ?? (() => false),
  windowRef = globalThis.window,
} = {}) {
  const element = (id) => documentRef.getElementById(id);
  documentRef.body.dataset ||= {};
  const themeKey = "ersel-chat-theme-v1";
  const applyTheme = theme => {
    documentRef.body.dataset.theme = theme;
    if (documentRef.documentElement?.dataset) documentRef.documentElement.dataset.theme = theme;
    const button = element("chat-theme-toggle");
    if (button) button.textContent = theme === "light" ? "Switch to dark theme" : "Switch to light theme";
  };
  try { applyTheme(windowRef?.localStorage?.getItem(themeKey) === "light" ? "light" : "dark"); }
  catch { applyTheme("dark"); }
  const state = element("chat-state");
  const history = element("chat-history");
  const agents = element("chat-agent");
  const headerModel = element("chat-header-model");
  const autonomyLevel = element("chat-autonomy-level");
  let coordinatorAgentModels = new Map();
  const updateHeaderModel = () => { headerModel.textContent = coordinatorAgentModels.get(agents.value) || ""; };
  const conversations = element("chat-conversation");
  const workspaceController = createChatWorkspace({ documentRef, windowRef, fetchImpl,
    onChange: async descriptor => { restoredWorkspace = descriptor; clear(); await start(); } });
  fetchImpl = workspaceController.fetch;
  let restoredWorkspace = null;
  let projectBriefDigest = null;
  function saveWorkspace() {
    const bridge = windowRef?.desktopBridge;
    if (!bridge?.saveWorkspaceState) return;
    void Promise.resolve(bridge.saveWorkspaceState({
      conversation: selected || "", agent: agents.value || "",
      model: headerModel.textContent || "", provider: workspaceController.selection()?.provider || "",
      project: workspaceController.selection()?.project || "",
    })).catch(() => {}); // Restoration is optional; it never grants execution authority.
  }
  const input = element("chat-input");
  const delegateOnce = element("chat-delegate-once");
  const approvalInbox = element("chat-approval-inbox");
  const voiceProvenance = element("chat-input-provenance");
  voiceProvenance.hidden = true;
  const cloudPanel = element("cloud-consent-panel");
  const cloudConsent = element("cloud-consent");
  const knowledgeEnabled = element("chat-knowledge-enabled");
  const knowledgeScopesPanel = element("chat-knowledge-scopes");
  const knowledgePreviewButton = element("chat-knowledge-preview");
  const knowledgeState = element("chat-knowledge-state");
  const knowledgePreviewResult = element("chat-knowledge-preview-result");
  const calculatorEnabled = element("chat-tool-calculator-enabled");
  const calculatorExpression = element("chat-tool-calculator-expression");
  const documentToolEnabled = element("chat-tool-document-enabled");
  const documentToolId = element("chat-tool-document-id");
  const documentToolQuery = element("chat-tool-document-query");
  const toolsState = element("chat-tools-state");
  const reviewedToolsPanel = element("chat-reviewed-tools");
  const captureLocalPrompt = element("chat-capture-local-prompt");
  const routeSelect = element("chat-route-select");
  const routeState = element("chat-route-state");
  const routeAlternatives = new Map();
  let configuredCloudRoute = false;
  const taskSource = element("chat-task-source");
  const taskAgent = element("chat-task-agent");
  const taskPrepare = element("chat-task-prepare");
  const taskConfirm = element("chat-task-confirm");
  const taskReview = element("chat-task-review");
  const taskState = element("chat-task-state");
  const repositoryStudyForm = element("repository-study-form");
  const repositoryStudyButton = element("repository-study-submit");
  const repositoryStudyState = element("repository-study-state");
  const repositoryStudyResult = element("repository-study-result");
  const repositoryStudyFields = [
    element("repository-study-objective"),
    element("repository-study-owner"),
    element("repository-study-name"),
  ];
  const taskFields = [
    taskSource, taskAgent, element("chat-task-objective"), element("chat-task-project"),
    element("chat-task-context-query"), element("chat-task-context-scope"),
    element("chat-task-context-id"), element("chat-task-outcome"),
    element("chat-task-verification"), element("chat-task-evidence"),
  ];
  const geminiKeyPattern = /\bAIza[A-Za-z0-9_-]{20,}\b|\b(?:GEMINI|GOOGLE)_API_KEY\s*=\s*\S+/i;
  const stopDisplayButton = element("chat-stop-display");
  const stopRequestButton = element("chat-stop-request");
  const buttons = [
    "chat-start", "chat-send", "chat-close", "chat-refresh",
    "chat-stop-display", "repository-study-submit", "chat-knowledge-preview",
  ].map(element);
  let busy = false;
  let selected = null;
  let canSend = false;
  let streamingSupported = false;
  let localModelAvailable = false;
  let stopDisplay = null;
  let requiresCloudConsent = false;
  let canCreateTask = false;
  let canStudyRepositories = false;
  let canReadDocumentation = false;
  let canDeleteHistory = false;
  let canManageApprovals = false;
  let documentsLoaded = false;
  let currentProposal = null;
  let voiceController = null;
  const voiceSources = [];
  let emergencyStopped = false;
  let requestController = null;
  let imageRefreshPromise = Promise.resolve();
  let imageRefreshPending = false;
  let sendInProgress = false;
  let presentationPreferences = { response_mode: "balanced", locale: "en-US", detail_level: "standard" };
  const knowledgeSettings = new Map();
  let ownerBrainNonEmpty = false;
  let knowledgePreview = null;
  const base = "/api/chat/conversations";
  let conversationItems = [];
  const metadataKey = "ersel-chat-list-v1";
  function readConversationMetadata() {
    try { return JSON.parse(windowRef?.localStorage?.getItem(metadataKey) || "{}"); }
    catch { return {}; }
  }
  function writeConversationMetadata(value) {
    try { windowRef?.localStorage?.setItem(metadataKey, JSON.stringify(value)); } catch { /* Chat remains usable without list preferences. */ }
  }
  const imageManager = mountChatImages({ documentRef, windowRef, fetchImpl, getConversation: () => selected });
  function clearVoiceProvenance() {
    voiceSources.length = 0;
    voiceProvenance.hidden = true;
    voiceProvenance.textContent = "";
  }
  function clear() {
    voiceController?.clear();
    history.replaceChildren();
    updateEmptyState(false);
    element("chat-identity").textContent = "";
    selected = null;
    canSend = false;
    streamingSupported = false;
    localModelAvailable = false;
    stopDisplay = null;
    stopDisplayButton.disabled = true;
    stopDisplayButton.hidden = true;
    requiresCloudConsent = false;
    configuredCloudRoute = false;
    resetRouteAlternatives("No route check has run. No prompt has been sent to another provider.", true);
    cloudPanel.hidden = true;
    cloudConsent.checked = false;
    knowledgePreview = null;
    knowledgePreviewResult.replaceChildren();
    knowledgePreviewResult.hidden = true;
    captureLocalPrompt.checked = false;
    captureLocalPrompt.disabled = true;
    knowledgeEnabled.checked = false;
    knowledgeScopesPanel.disabled = true;
    knowledgePreviewButton.disabled = true;
    knowledgeState.textContent = "Knowledge retrieval is off. Choose each scope explicitly; no knowledge is added automatically.";
    input.disabled = true;
    repositoryStudyResult.textContent = "";
    repositoryStudyState.textContent = "";
    clearTaskProposal();
    taskControls();
    repositoryStudyControls();
  }
  function updateEmptyState(visible) {
    const empty = element("chat-empty-state");
    if (empty) empty.hidden = !visible;
  }
  function renderConversationList(items = conversationItems) {
    const list = element("chat-conversation-list");
    const earlier = element("chat-earlier-list");
    if (!list) return;
    conversationItems = items;
    list.replaceChildren(); earlier?.replaceChildren();
    const metadata = readConversationMetadata();
    const query = (element("chat-search")?.value || "").trim().toLocaleLowerCase();
    const sorted = [...items].sort((a, b) => Number(Boolean(metadata[b.id]?.pinned)) - Number(Boolean(metadata[a.id]?.pinned))
      || (Date.parse(b.created_at || 0) || 0) - (Date.parse(a.created_at || 0) || 0));
    for (const item of sorted) {
      const title = metadata[item.id]?.title || `${item.coordinator.name} - ${item.id.slice(0, 8)}`;
      if (query && !title.toLocaleLowerCase().includes(query)) continue;
      const created = Date.parse(item.created_at || "");
      const isToday = !Number.isFinite(created) || new Date(created).toDateString() === new Date().toDateString();
      const target = isToday || !earlier ? list : earlier;
      const row = documentRef.createElement("div"); row.className = "chat-conversation-row";
      const button = documentRef.createElement("button"); button.type = "button";
      button.className = "chat-conversation-item"; button.textContent = `${metadata[item.id]?.pinned ? "Pinned | " : ""}${title}`;
      button.setAttribute("aria-current", item.id === selected ? "true" : "false");
      button.addEventListener("click", () => { conversations.value = item.id; void load(); });
      const actions = documentRef.createElement("details"); actions.className = "chat-conversation-actions";
      const summary = documentRef.createElement("summary"); summary.textContent = "..."; summary.setAttribute("aria-label", `Actions for ${title}`);
      const rename = documentRef.createElement("button"); rename.type = "button"; rename.textContent = "Rename";
      rename.addEventListener("click", () => {
        const next = windowRef?.prompt?.("Conversation name", title);
        if (typeof next !== "string" || !next.trim()) return;
        const nextMetadata = readConversationMetadata();
        nextMetadata[item.id] = { ...nextMetadata[item.id], title: next.trim().slice(0, 80) };
        writeConversationMetadata(nextMetadata); renderConversationList();
      });
      const pin = documentRef.createElement("button"); pin.type = "button"; pin.textContent = metadata[item.id]?.pinned ? "Unpin" : "Pin";
      pin.addEventListener("click", () => {
        const nextMetadata = readConversationMetadata();
        nextMetadata[item.id] = { ...nextMetadata[item.id], pinned: !nextMetadata[item.id]?.pinned };
        writeConversationMetadata(nextMetadata); renderConversationList();
      });
      actions.append(summary, rename, pin);
      if (canDeleteHistory) {
        const remove = documentRef.createElement("button"); remove.type = "button"; remove.textContent = "Delete";
        remove.addEventListener("click", async () => {
          if (!confirmImpl("Permanently delete this conversation and any retained copy?")) return;
          try {
            const sessionResponse = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
            if (!sessionResponse.ok) throw new Error("Sign in to delete this conversation.");
            const session = await sessionResponse.json();
            const response = await fetchImpl(`/api/chat/conversations/${encodeURIComponent(item.id)}`, {
              method: "DELETE", credentials: "same-origin", headers: { "X-Local-CSRF": session.csrf },
            });
            const result = await response.json();
            if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Conversation could not be deleted.");
            conversationItems = conversationItems.filter(entry => entry.id !== item.id);
            const nextMetadata = readConversationMetadata(); delete nextMetadata[item.id]; writeConversationMetadata(nextMetadata);
            if (selected === item.id) { clear(); state.textContent = "Conversation deleted."; }
            renderConversationList();
          } catch (error) { state.textContent = error.message; }
        });
        actions.append(remove);
      }
      row.append(button, actions); target.append(row);
    }
    if (element("chat-earlier-label")) element("chat-earlier-label").hidden = !earlier?.children?.length;
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
  function repositoryStudyControls() {
    repositoryStudyFields.forEach(field => {
      field.disabled = busy || !canStudyRepositories || !selected || !canSend;
    });
    repositoryStudyButton.disabled =
      busy || !canStudyRepositories || !selected || !canSend;
  }
  async function request(path, body, signal) {
    const options = { credentials: "same-origin" };
    if (signal) options.signal = signal;
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
      if (response.status === 429 && String(payload.detail || "").includes("request-slot capacity")) {
        throw new Error("The shared model slot stayed busy and timed out before admission. No model request was sent; retry after the current Agent finishes.");
      }
      throw new Error(typeof payload.detail === "string" ? payload.detail : "Chat request failed.");
    }
    return payload;
  }
  autonomyLevel?.addEventListener("change", async () => {
    const previous = presentationPreferences.autonomy_level || "auto_safe";
    try {
      const session = await request("/api/local/session");
      const response = await fetchImpl("/api/local/preferences", {
        method: "PUT", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": session.csrf },
        body: JSON.stringify({ autonomy_level: autonomyLevel.value }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Autonomy setting could not be saved.");
      presentationPreferences = payload.preferences;
      state.textContent = `Autonomy saved: ${autonomyLevel.options?.[autonomyLevel.selectedIndex]?.textContent || autonomyLevel.value}. Permissions and cloud consent are unchanged.`;
    } catch (error) {
      autonomyLevel.value = previous;
      state.textContent = error.message || "Autonomy setting could not be saved.";
    }
  });
  function option(select, value, label) {
    const item = documentRef.createElement("option");
    item.value = value;
    item.textContent = label;
    select.append(item);
  }
  function renderApprovals(items) {
    const list = element("chat-approval-items");
    const pending = items.filter(item => item && item.status === "pending"
      && typeof item.approval_id === "string" && typeof item.approval_digest === "string"
      && typeof item.action_summary === "string" && typeof item.target_ref === "string"
      && typeof item.expires_at === "string");
    list.replaceChildren();
    element("chat-approval-count").textContent = String(pending.length);
    if (!pending.length) {
      element("chat-approval-state").textContent = "No current approval requests. Expired requests cannot be approved.";
      return;
    }
    element("chat-approval-state").textContent = `${pending.length} exact action${pending.length === 1 ? "" : "s"} awaiting your decision.`;
    for (const approval of pending.slice(0, 20)) {
      const card = documentRef.createElement("article"); card.className = "chat-approval-item";
      const heading = documentRef.createElement("strong"); heading.textContent = approval.action_summary;
      const target = documentRef.createElement("p"); target.textContent = `Target: ${approval.target_ref}`;
      const capability = documentRef.createElement("p"); capability.textContent = `${approval.capability_id} / ${approval.action_id} - ${approval.risk}${approval.irreversible ? " / irreversible" : ""}`;
      const scope = documentRef.createElement("p"); scope.textContent = `Scope: ${approval.scope_type}:${approval.scope_id}`;
      const provenance = approval.workspace_id
        ? `Window: ${approval.workspace_id}; Agent: ${approval.workspace_agent_id}; Project: ${approval.workspace_project_id || "Personal"}; Model: ${approval.workspace_model_id}`
        : "";
      if (provenance) scope.textContent += ` · ${provenance}`;
      const expiry = documentRef.createElement("p"); expiry.textContent = `Expires ${new Date(approval.expires_at).toLocaleString()}`;
      const fingerprints = documentRef.createElement("details");
      const fingerprintSummary = documentRef.createElement("summary"); fingerprintSummary.textContent = "Exact-action fingerprints";
      const fingerprintText = documentRef.createElement("p");
      fingerprintText.textContent = `Approval: ${approval.approval_digest}; payload: ${approval.payload_digest}; target: ${approval.target_digest}`;
      fingerprints.append(fingerprintSummary, fingerprintText);
      const actions = documentRef.createElement("div"); actions.className = "chat-approval-actions";
      const approve = documentRef.createElement("button"); approve.type = "button"; approve.textContent = "Approve exact action";
      approve.addEventListener("click", async () => {
        const preview = `${approval.action_summary}\nTarget: ${approval.target_ref}\nCapability/action: ${approval.capability_id} / ${approval.action_id}\nScope: ${approval.scope_type}:${approval.scope_id}\nRisk: ${approval.risk}${approval.irreversible ? " (irreversible)" : ""}\nExpires: ${approval.expires_at}\nApproval digest: ${approval.approval_digest}\n\nApprove this exact request? Approval alone does not execute it.`;
        if (!confirmImpl(provenance ? `${preview}\n${provenance}` : preview)) return;
        approve.disabled = true;
        try {
          await request(`/api/capabilities/approvals/${encodeURIComponent(approval.approval_id)}/approve`, { confirmed_digest: approval.approval_digest });
          element("chat-approval-state").textContent = "Approval recorded. The protected action still needs its separate exact execution request.";
          await refreshApprovals();
        } catch (error) { element("chat-approval-state").textContent = error.message || "Approval could not be recorded. Refresh and inspect the current request."; }
        finally { approve.disabled = false; }
      });
      const deny = documentRef.createElement("button"); deny.type = "button"; deny.textContent = "Deny";
      deny.addEventListener("click", async () => {
        if (!confirmImpl(`Deny this exact request?\n${approval.action_summary}\nTarget: ${approval.target_ref}\nScope: ${approval.scope_type}:${approval.scope_id}\nNo protected action will run.`)) return;
        deny.disabled = true;
        try {
          await request(`/api/capabilities/approvals/${encodeURIComponent(approval.approval_id)}/deny`, { confirmed_digest: approval.approval_digest });
          element("chat-approval-state").textContent = "Request denied. No protected action was run.";
          await refreshApprovals();
        } catch (error) { element("chat-approval-state").textContent = error.message || "Request could not be denied. Refresh and inspect it."; }
        finally { deny.disabled = false; }
      });
      actions.append(approve, deny);
      card.append(heading, target, capability, scope, expiry, fingerprints, actions); list.append(card);
    }
  }
  async function refreshApprovals() {
    if (!canManageApprovals || !approvalInbox) return false;
    element("chat-approval-state").textContent = "Checking current exact-action requests...";
    try {
      const result = await request("/api/capabilities/approvals");
      if (!Array.isArray(result.items)) throw new Error("Approval list response was invalid.");
      renderApprovals(result.items);
      return true;
    } catch (error) {
      element("chat-approval-items").replaceChildren();
      element("chat-approval-count").textContent = "?";
      element("chat-approval-state").textContent = error.message || "Approval requests could not be loaded. Refresh and retry.";
      return false;
    }
  }
  function render(result) {
    const record = result.conversation;
    const agent = result.coordinator;
    if (!record || !agent || typeof record.id !== "string" || !Array.isArray(record.messages)
        || !["open", "closed"].includes(record.status)) throw new Error("Invalid conversation response.");
    selected = record.id;
    if (typeof agent.id === "string" && coordinatorAgentModels.has(agent.id)) agents.value = agent.id;
    headerModel.textContent = typeof agent.model === "string" ? agent.model : "";
    workspaceController.remember({ conversation: record.id, agent: agent.id,
      provider: agent.provider, model: agent.model, project: result.workspace?.project_id || "" });
    projectBriefDigest = result.workspace?.project_brief_digest || null;
    const briefEditor = element("workspace-brief");
    if (briefEditor) briefEditor.value = result.workspace?.project_brief || "";
    const briefPanel = element("workspace-brief-panel");
    if (briefPanel) briefPanel.hidden = !result.workspace?.project_id;
    const cloudBrief = element("workspace-cloud-brief");
    if (cloudBrief) {
      cloudBrief.textContent = result.workspace?.project_brief ? `Project brief sent with this turn:\n${result.workspace.project_brief}` : "";
      cloudBrief.hidden = !result.workspace?.project_brief;
    }
    if (!conversationItems.some(item => item.id === record.id)) conversationItems = [{ id: record.id, coordinator: agent, created_at: new Date().toISOString() }, ...conversationItems];
    renderConversationList();
    if (!knowledgeSettings.has(record.id)) knowledgeSettings.set(record.id, {
      enabled: result.workspace?.project_id ? result.workspace.brain_non_empty === true : ownerBrainNonEmpty,
      owner: ownerBrainNonEmpty && !result.workspace?.project_id, conversation: false,
      extra: Boolean(result.workspace?.project_id), extraScope: "project", extraId: result.workspace?.project_id || "",
    });
    const savedKnowledge = knowledgeSettings.get(record.id);
    knowledgeEnabled.checked = savedKnowledge.enabled;
    element("chat-knowledge-owner").checked = savedKnowledge.owner;
    element("chat-knowledge-conversation").checked = savedKnowledge.conversation;
    element("chat-knowledge-extra-enabled").checked = savedKnowledge.extra;
    element("chat-knowledge-extra-scope").value = savedKnowledge.extraScope;
    element("chat-knowledge-extra-id").value = savedKnowledge.extraId;
    knowledgePreview = null;
    streamingSupported = result.streaming_supported === true;
    localModelAvailable = result.local_model === true;
    captureLocalPrompt.disabled = busy || !localModelAvailable;
    captureLocalPrompt.checked = false;
    requiresCloudConsent = isGeminiProvider(agent.provider);
    configuredCloudRoute = requiresCloudConsent;
    cloudPanel.hidden = !requiresCloudConsent;
    cloudConsent.checked = false;
    resetRouteAlternatives("Check this turn's prompt before selecting an optional route.", false);
    conversations.value = record.id;
    saveWorkspace();
    element("chat-identity").textContent = `Coordinator: ${agent.name} (${agent.role}) | ${agent.provider} / ${agent.model} | ${record.status}`;
    history.replaceChildren();
    updateEmptyState(record.messages.length === 0);
    const traces = { ...(result.context_traces || {}) };
    if (result.context_trace && record.messages.length) {
      const latestReply = [...record.messages].reverse().find(message => message.role === "assistant");
      if (latestReply?.id) traces[latestReply.id] = result.context_trace;
    }
    const latestAssistant = [...record.messages].reverse().find(message => message.role === "assistant");
    if (latestAssistant?.id) {
      const latestTrace = traces[latestAssistant.id];
      if (latestTrace?.retrieval?.enabled === true) recordLastBrainRetrieval(windowRef?.sessionStorage, latestTrace);
      else { try { windowRef?.sessionStorage?.removeItem("ersel-brain-retrieval-v1"); } catch { /* Highlight is best effort only. */ } }
    }
    taskSource.replaceChildren();
    option(taskSource, "", "Select a completed chat proposal");
    for (const message of record.messages) {
      if (typeof message.content !== "string" || !["user", "assistant", "system"].includes(message.role)
          || !["pending", "completed", "failed"].includes(message.status)) throw new Error("Invalid message response.");
      const item = documentRef.createElement("article");
      item.className = `chat-message chat-message-${message.role}`;
      const label = documentRef.createElement("strong");
      label.textContent = `${message.role} - ${message.status}`;
      const content = documentRef.createElement("div");
      content.className = "chat-message-content";
      content.append(renderSafeMarkdown(message.content, { documentRef }));
      item.append(label, content);
      const trace = typeof message.id === "string" ? traces[message.id] : null;
      if (trace && message.role === "assistant") appendVisibleBrainCitations(item, trace);
      if (trace && (message.role === "assistant" || message.status === "failed")) appendAnswerTrace(item, trace);
      if (message.role === "assistant" && message === [...record.messages].reverse().find(row => row.role === "assistant")
          && typeof result.advanced_prompt === "string") {
        const advanced = documentRef.createElement("details");
        const summary = documentRef.createElement("summary");
        summary.textContent = "Advanced: exact prompt sent to this local model";
        const warning = documentRef.createElement("p");
        warning.textContent = "This one-turn view includes recent chat history and selected knowledge. It is not saved in the trace; avoid sharing sensitive text.";
        const prompt = documentRef.createElement("pre");
        prompt.textContent = result.advanced_prompt;
        advanced.append(summary, warning, prompt);
        item.append(advanced);
      }
      if (message.role === "assistant" && message.status === "completed"
          && presentationPreferences.detail_level === "brief") content.classList.add("response-detail-brief");
      if (message.role === "assistant" && message.status === "completed" && voiceController) {
        const speak = documentRef.createElement("button");
        speak.type = "button";
        speak.textContent = "Speak reply locally";
        speak.addEventListener("click", () => voiceController.speak(message.content));
        item.append(speak);
      }
      history.append(item);
      if (message.role === "assistant" && message.status === "completed" && typeof message.id === "string") {
        option(taskSource, message.id, `Coordinator proposal - ${message.content.slice(0, 100)}`);
      }
    }
    const uncertain = record.messages.some(message => message.status === "pending");
    state.textContent = record.status === "closed"
      ? "Conversation closed. Start a new conversation to send."
      : uncertain
        ? "A turn is pending or uncertain. It is not replayed; inspect this conversation and start a new one before sending again."
        : "";
    canSend = record.status === "open" && !uncertain;
    input.disabled = !canSend;
    clearTaskProposal();
    taskControls();
    repositoryStudyControls();
    voiceController?.updateControls();
    updateKnowledgeControls();
    if (imageManager) {
      imageRefreshPending = true;
      input.disabled = true;
      imageRefreshPromise = Promise.resolve(imageManager.refresh()).catch(() => {}).finally(() => {
        imageRefreshPending = false;
        if (selected === record.id && !requestController) input.disabled = !canSend;
      });
    }
  }
  function currentKnowledgeScopes() {
    const scopes = [];
    if (element("chat-knowledge-owner").checked) scopes.push({ scope: "owner" });
    if (element("chat-knowledge-conversation").checked) scopes.push({ scope: "conversation" });
    if (element("chat-knowledge-extra-enabled").checked) scopes.push({
      scope: element("chat-knowledge-extra-scope").value,
      scope_id: element("chat-knowledge-extra-id").value.trim(),
    });
    return scopes;
  }
  function knowledgeSelectionKey(text = input.value) {
    return JSON.stringify({ text, scopes: currentKnowledgeScopes() });
  }
  function updateKnowledgeControls() {
    if (!knowledgeEnabled) return;
    const enabled = knowledgeEnabled.checked === true;
    knowledgeScopesPanel.disabled = busy || !canSend || !enabled;
    knowledgePreviewButton.disabled = busy || !canSend || !enabled;
    if (!enabled) {
      knowledgePreview = null;
      knowledgePreviewResult.hidden = true;
      knowledgeState.textContent = "Knowledge retrieval is off. No knowledge is added to this turn.";
    }
  }
  function appendVisibleBrainCitations(article, trace) {
    const retrieval = trace?.retrieval || {};
    if (retrieval.enabled !== true || !Array.isArray(trace.sources) || !trace.sources.length) return;
    const citations = documentRef.createElement("p");
    citations.className = "chat-visible-citations";
    citations.setAttribute("aria-label", "Sources used");
    const label = documentRef.createElement("strong");
    label.textContent = "Sources";
    citations.append(label);
    for (const [index, source] of trace.sources.entries()) {
      const item = documentRef.createElement("span");
      const name = source.source || source.origin_reference || source.memory_id || "Saved source";
      const reference = source.chunk_reference || source.memory_id || "reference unavailable";
      item.textContent = ` [${index + 1}] ${name} · ${reference}`;
      citations.append(item);
    }
    article.append(citations);
  }
  function appendAnswerTrace(article, trace) {
    const panel = documentRef.createElement("details");
    panel.className = "chat-answer-trace";
    const summary = documentRef.createElement("summary"); summary.textContent = "How I answered"; panel.append(summary);
    const route = trace.route || {};
    const routeText = documentRef.createElement("p");
    routeText.textContent = route.agent
      ? `Route: ${route.agent} (${route.agent_id}) · ${route.provider || "provider unknown"} / ${route.model || "model unknown"}. ${route.source || "Route reason not recorded."}`
      : "Route details were not recorded for this reply.";
    panel.append(routeText);
    const automaticRoute = trace.auto_route;
    if (automaticRoute && typeof automaticRoute.mode === "string") {
      const decision = documentRef.createElement("p");
      decision.textContent = `Auto-routing: ${automaticRoute.mode.replaceAll("_", " ")} · ${automaticRoute.capability || "no capability"} · ${automaticRoute.reason || "reason unavailable"}.`;
      panel.append(decision);
    }
    if (trace.handoff && typeof trace.handoff === "object") {
      const handoff = documentRef.createElement("p");
      const responder = trace.handoff.agent || {};
      handoff.textContent = trace.handoff.status === "completed"
        ? `One local handoff: Coordinator selected ${responder.name || "an Agent"} (${responder.id || "unknown ID"}); one answer step, ${trace.handoff.selection_ms ?? "unknown"} ms to select and ${trace.handoff.answer_ms ?? "unknown"} ms to answer.`
        : `One local handoff was attempted for ${responder.name || "an Agent"} (${responder.id || "unknown ID"}); no completed answer was verified.`;
      panel.append(handoff);
    }
    if (Array.isArray(trace.steps)) {
      const heading = documentRef.createElement("strong");
      heading.textContent = "Workflow steps";
      panel.append(heading);
      const steps = documentRef.createElement("ol");
      for (const step of trace.steps) {
        const item = documentRef.createElement("li");
        const timing = step.duration_ms === undefined ? "timing unavailable" : `${step.duration_ms} ms`;
        item.textContent = `${step.step || "unknown step"} · ${step.status || "status unknown"} · ${step.source || step.reason || "no source"} · ${timing}`;
        steps.append(item);
      }
      panel.append(steps);
    }
    const retrieval = trace.retrieval || {};
    const retrievalText = documentRef.createElement("p");
    retrievalText.textContent = retrieval.enabled === true
      ? `Knowledge: ${retrieval.returned_chunks?.length || 0} chunks · ${retrieval.mode || "mode unknown"} · query: ${retrieval.query || "not recorded"}`
      : retrieval.reason || "Knowledge retrieval was not used.";
    panel.append(retrievalText);
    if (Array.isArray(trace.sources) && trace.sources.length) {
      const heading = documentRef.createElement("strong"); heading.textContent = "Sources used"; panel.append(heading);
      const sources = documentRef.createElement("ol");
      for (const source of trace.sources) {
        const item = documentRef.createElement("li");
        const label = source.source || source.origin_reference || source.memory_id || "Saved source";
        const reference = source.chunk_reference || source.memory_id || "reference unavailable";
        item.textContent = `${label} · ${source.scope || "scope unknown"} · ${reference}${source.score === undefined ? "" : ` · score ${source.score}`}${source.freshness ? ` · ${source.freshness}` : ""}`;
        sources.append(item);
      }
      panel.append(sources);
    } else if (retrieval.enabled === true) {
      const empty = documentRef.createElement("p");
      empty.textContent = "No relevant selected knowledge was found; the model was instructed not to guess from outside the selected notes.";
      panel.append(empty);
    }
    const truncation = retrieval.truncation || {};
    const truncated = Object.entries(truncation)
      .filter(([key, value]) => value === true || (key === "duplicates_removed" && value > 0))
      .map(([key, value]) => `${key}: ${value === true ? "limit reached" : value}`).join("; ");
    const limitText = documentRef.createElement("p");
    limitText.textContent = truncated ? `Limits: ${truncated}` : "Retrieval limits did not truncate selected context.";
    panel.append(limitText);
    const cloud = trace.cloud || {};
    const cloudText = documentRef.createElement("p");
    cloudText.textContent = cloud.provider_used
      ? `Cloud provider: ${cloud.provider_used}; per-turn consent ${cloud.consent_given ? "given" : "not given"}; private knowledge sent ${cloud.private_knowledge_sent ? "yes" : "no"}.`
      : "Cloud provider: none reported for this turn.";
    panel.append(cloudText);
    const vision = trace.vision || {};
    if (vision.used === true) {
      const visionText = documentRef.createElement("p");
      visionText.textContent = `Image input: ${vision.provider || "provider unknown"} / ${vision.model || "model unknown"} (${vision.destination || "destination unknown"}) · ${vision.outcome || "outcome unknown"} · ${vision.image_count ?? "?"} image(s) · ${vision.retention || "retention unknown"}.`;
      panel.append(visionText);
    }
    const timing = documentRef.createElement("p");
    timing.textContent = `Turn duration: ${trace.timing?.turn_elapsed_ms ?? "unknown"} ms · outcome: ${trace.outcome || "unknown"}.`;
    panel.append(timing);
    if (typeof trace.failure === "string" && trace.failure.trim()) {
      const failure = documentRef.createElement("p");
      failure.textContent = `Failure: ${trace.failure}`;
      panel.append(failure);
    }
    const actions = documentRef.createElement("p");
    actions.textContent = `Tools run: ${trace.actions?.tools_run === false ? "no" : "unknown"} · Tasks created: ${trace.actions?.tasks_created === false ? "no" : "unknown"}.`;
    panel.append(actions);
    if (Array.isArray(trace.tools) && trace.tools.length) {
      const heading = documentRef.createElement("strong");
      heading.textContent = "Reviewed tool calls";
      panel.append(heading);
      const calls = documentRef.createElement("ol");
      for (const tool of trace.tools) {
        const item = documentRef.createElement("li");
        const parameters = Object.entries(tool.parameters || {}).map(([key, value]) => `${key}: ${value}`).join("; ");
        item.textContent = `${tool.tool || "unknown tool"} (${parameters || "no parameters"}) · ${tool.source || "source unknown"} · ${tool.outcome || "outcome unknown"} · ${tool.duration_ms ?? "?"} ms · ${tool.result_characters ?? "?"} result characters${tool.message ? ` · ${tool.message}` : ""}`;
        calls.append(item);
      }
      panel.append(calls);
    }
    const advanced = documentRef.createElement("p");
    advanced.textContent = trace.advanced_prompt_retained === false && route.provider === "ollama"
      ? "Exact prompt is available only when separately requested for a local turn; it is not retained in this trace."
      : "Exact prompts are not retained in this trace.";
    panel.append(advanced);
    article.append(panel);
  }
  function renderKnowledgePreview(result) {
    knowledgePreviewResult.replaceChildren();
    knowledgePreviewResult.hidden = false;
    const heading = documentRef.createElement("h3"); heading.textContent = "Exact knowledge preview"; knowledgePreviewResult.append(heading);
    const note = documentRef.createElement("p");
    note.textContent = result.items.length
      ? `${result.items.length} selected excerpt(s), ${result.trace.context_bytes} UTF-8 bytes. No model was called.`
      : "No relevant selected notes found. The model will be instructed not to guess from outside the selected knowledge.";
    knowledgePreviewResult.append(note);
    for (const source of result.items) {
      const card = documentRef.createElement("article"); card.className = "chat-knowledge-preview-item";
      const label = documentRef.createElement("strong"); label.textContent = `${source.source} · ${source.scope} · ${source.chunk_reference}`;
      const text = documentRef.createElement("p"); text.textContent = source.content;
      card.append(label, text); knowledgePreviewResult.append(card);
    }
    if (requiresCloudConsent && result.items.length) {
      const cloud = documentRef.createElement("p");
      cloud.textContent = "This exact excerpt will be sent to Google Gemini only if you also check the per-turn cloud consent and press Send.";
      knowledgePreviewResult.append(cloud);
    }
  }
  async function loadKnowledgePreview(conversationId, text, scopes) {
    knowledgePreview = null;
    knowledgeState.textContent = "Reviewing the selected Brain entries for this message; no model has been called.";
    const result = await request(`${base}/${encodeURIComponent(conversationId)}/knowledge-preview`, { query: text, scopes });
    if (typeof result.digest !== "string" || !Array.isArray(result.items) || !result.trace) throw new Error("Invalid knowledge preview response.");
    knowledgePreview = { digest: result.digest, key: knowledgeSelectionKey(text) };
    renderKnowledgePreview(result);
    knowledgeState.textContent = "The exact excerpts are shown above and will be rechecked before Send.";
    return result;
  }
  async function action(operation, { preserveSend = false } = {}) {
    if (busy) return false;
    busy = true;
    buttons.forEach(button => { button.disabled = preserveSend ? button.id !== "chat-send" : true; });
    agents.disabled = true; conversations.disabled = true;
    workspaceController.setDisabled(true);
    taskControls();
    try { await operation(); return true; }
    catch (error) { state.textContent = error.message; return false; }
    finally {
      busy = false;
      buttons.forEach(button => { button.disabled = false; });
      if (sendInProgress) finishSendButton();
      captureLocalPrompt.disabled = !localModelAvailable;
      agents.disabled = false; conversations.disabled = false;
      workspaceController.setDisabled(false);
      taskControls();
      repositoryStudyControls();
      updateKnowledgeControls();
      voiceController?.updateControls();
      if (!imageRefreshPending && !requestController) input.disabled = !canSend;
    }
  }
  async function refresh() {
    return action(async () => {
      clear();
      clearTaskProposal();
      try {
        const response = await fetchImpl("/api/local/preferences", { credentials: "same-origin", cache: "no-store" });
        const payload = response.ok ? await response.json() : null;
        const prefs = payload?.preferences;
        if (prefs) presentationPreferences = prefs;
        if (prefs?.autonomy_level && autonomyLevel) autonomyLevel.value = prefs.autonomy_level;
        const preferenceLabel = element("response-preferences-label");
        if (preferenceLabel) preferenceLabel.textContent = prefs
          ? `Display preference: ${prefs.response_mode}; locale ${prefs.locale}; ${prefs.detail_level} detail. It does not alter provider prompts or assignments.`
          : "Sign in to load your saved response preferences.";
        document.documentElement.lang = prefs?.locale || "en-US";
        history.dataset.responseMode = prefs?.response_mode || "balanced";
        history.dataset.detailLevel = prefs?.detail_level || "standard";
      } catch {
        element("response-preferences-label").textContent = "Saved response preferences are unavailable.";
      }
      agents.replaceChildren(); conversations.replaceChildren();
      state.textContent = "Loading authorized chat records…";
      try {
        const session = await request("/api/local/session");
        canCreateTask = Array.isArray(session.permissions)
          && session.permissions.includes("chat-task:create");
        canStudyRepositories = Array.isArray(session.permissions)
          && session.permissions.includes("github:read");
        canReadDocumentation = Array.isArray(session.permissions)
          && session.permissions.includes("documentation:read");
        canDeleteHistory = Array.isArray(session.permissions)
          && session.permissions.includes("chat-history:manage");
        canManageApprovals = Array.isArray(session.permissions)
          && session.permissions.includes("capability-approval:manage");
        approvalInbox.hidden = !canManageApprovals;
        try {
          const brain = await request("/api/memory/owner");
          ownerBrainNonEmpty = Array.isArray(brain.items) && brain.items.length > 0;
        } catch { ownerBrainNonEmpty = false; }
      } catch {
        canCreateTask = false;
        canStudyRepositories = false;
        canReadDocumentation = false;
        canManageApprovals = false;
        approvalInbox.hidden = true;
      }
      taskState.textContent = canCreateTask
        ? "Prepare and inspect a proposal before explicit confirmation."
        : "Task proposal review is unavailable: this session lacks chat-task:create permission.";
      repositoryStudyState.textContent = canStudyRepositories
        ? "Repository study is limited to repositories already in the configured allowlist."
        : "Repository study is unavailable: this session lacks github:read permission.";
      repositoryStudyControls();
      if (!canReadDocumentation) {
        documentToolEnabled.disabled = true;
        documentToolId.disabled = true;
        documentToolQuery.disabled = true;
        toolsState.textContent = "Calculator is available; local documentation lookup requires documentation:read permission.";
      }
      const agentList = await request("/api/agents");
      if (!Array.isArray(agentList.items)) throw new Error("Invalid chat list response.");
      coordinatorAgentModels = new Map(agentList.items.map(agent => [agent.id, agent.model]));
      agents.replaceChildren(); conversations.replaceChildren();
      taskAgent.replaceChildren();
      option(taskAgent, "", "Select the responsible Agent");
      option(conversations, "", "Select an existing conversation");
      for (const agent of agentList.items) {
        const label = element("workspace-model") ? agent.name : `${agent.name} / ${agent.model}`;
        option(agents, agent.id, label);
        option(taskAgent, agent.id, `${agent.name} | ${agent.role}`);
      }
      restoredWorkspace = await workspaceController.initialize(agentList.items);
      const list = await request(base);
      if (!Array.isArray(list.items)) throw new Error("Invalid chat list response.");
      const directDesktopLaunch = new URLSearchParams(windowRef?.location?.search || "").get("desktop") === "1";
      const defaultCoordinator = agentList.items.find(agent => agent.id === "local_worker")
        || agentList.items.find(agent => agent.builtin === true && agent.name === "Coordinator");
      if (defaultCoordinator) agents.value = defaultCoordinator.id;
      if (restoredWorkspace?.agent && coordinatorAgentModels.has(restoredWorkspace.agent)) agents.value = restoredWorkspace.agent;
      updateHeaderModel();
      for (const item of list.items) option(conversations, item.id, `${item.coordinator.name} - ${item.id.slice(0, 8)}`);
      renderConversationList(list.items);
      const requestedConversation = new URLSearchParams(windowRef?.location?.search || "").get("conversation") || restoredWorkspace?.conversation;
      if (typeof requestedConversation === "string" && /^[a-f0-9]{32}$/.test(requestedConversation)
          && list.items.some((item) => item.id === requestedConversation)) {
        conversations.value = requestedConversation;
        render(await request(`${base}/${encodeURIComponent(requestedConversation)}`));
        state.textContent = "";
      } else if (directDesktopLaunch && !restoredWorkspace && list.items.length > 0) {
        conversations.value = list.items[0].id;
        render(await request(`${base}/${encodeURIComponent(conversations.value)}`));
        state.textContent = "";
      } else if (directDesktopLaunch && (restoredWorkspace || list.items.length === 0) && agents.value) {
        const result = await request(base, { agent_id: agents.value });
        option(conversations, result.conversation.id, `${result.coordinator.name} - ${result.conversation.id.slice(0, 8)}`);
        render(result);
        state.textContent = restoredWorkspace?.conversation
          ? "The previous chat is not in retained history. A new empty chat is open."
          : "";
      } else {
        state.textContent = agentList.items.length ? "Choose an AI team member and start a conversation." : "No registered AI team member is available.";
        updateEmptyState(true);
      }
    });
  }
  async function start() {
    return action(async () => {
      if (emergencyStopped) throw new Error("Emergency stop is active. Resume protected actions before starting a conversation.");
      if (!agents.value) throw new Error("Choose an AI team member first.");
      state.textContent = "Starting conversation…";
      await workspaceController.commit();
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
    if (requestController) {
      requestController.abort();
      state.textContent = "Stopping this app's wait. The local model may continue; its final outcome will be checked before any resend.";
      return false;
    }
    sendInProgress = true;
    const submitButton = element("chat-send");
    submitButton.textContent = streamingSupported ? "Stop" : "Stop waiting";
    submitButton.setAttribute("aria-label", "Stop generating");
    return action(async () => {
      await imageRefreshPromise;
      if (emergencyStopped) throw new Error("Emergency stop is active. Resume protected actions before sending a message.");
      const text = input.value;
      if (!selected || !canSend) throw new Error("Start or select an open conversation first.");
      if (!text.trim() || new TextEncoder().encode(text).length > 8192) throw new Error("Enter a message of at most 8192 UTF-8 bytes.");
      if (geminiKeyPattern.test(text)) {
        input.value = "";
        throw new Error("This message looks like it contains a Gemini API key. It was not saved or sent. Use the Gemini online setup page to connect a key.");
      }
      const delegateForTurn = delegateOnce?.checked === true;
      const selectedRoute = routeAlternatives.get(routeSelect.value) || null;
      requiresCloudConsent = selectedRoute ? selectedRoute.kind === "cloud" : configuredCloudRoute;
      cloudPanel.hidden = !requiresCloudConsent;
      if (requiresCloudConsent) cloudPanel.hidden = false;
    if (requiresCloudConsent && !cloudConsent.checked) throw new Error("Check the separate per-turn Gemini cloud consent before continuing.");
      const imageIds = imageManager?.selectedIds() || [];
      const reviewedTools = [];
      if (calculatorEnabled.checked === true) {
        const expression = calculatorExpression.value.trim();
        if (!expression) throw new Error("Enter an arithmetic expression before selecting the calculator.");
        reviewedTools.push({ kind: "calculator", expression });
      }
      if (documentToolEnabled.checked === true) {
        const documentId = documentToolId.value;
        const query = documentToolQuery.value.trim();
        if (!canReadDocumentation) throw new Error("This session cannot read local documentation.");
        if (!documentId || !query) throw new Error("Select one local document and enter terms to find.");
        reviewedTools.push({ kind: "local-document-lookup", document_id: documentId, query });
      }
      if (reviewedTools.length && imageIds.length) throw new Error("Reviewed tools cannot be combined with image turns.");
      const useKnowledge = knowledgeEnabled.checked === true;
      const knowledgeScopes = useKnowledge ? currentKnowledgeScopes() : [];
      if (useKnowledge) {
        if (imageIds.length) throw new Error("Knowledge-assisted turns cannot combine with temporary images.");
        if (!knowledgeScopes.length) throw new Error("Select at least one exact knowledge scope before previewing.");
        if (!knowledgePreview || knowledgePreview.key !== knowledgeSelectionKey(text)) {
          await loadKnowledgePreview(selected, text, knowledgeScopes);
        }
      }
      if (imageIds.length && !imageManager.consented()) throw new Error("Select the per-turn image consent checkbox before sending selected images to the configured provider.");
      if (!imageIds.length && imageManager?.wantsLocalOcr()) throw new Error("Select an image before requesting local OCR.");
      if (delegateForTurn && (requiresCloudConsent || selectedRoute || imageIds.length || reviewedTools.length
          || useKnowledge || captureLocalPrompt.checked === true)) {
        throw new Error("One-step delegation is local plain text only. Turn off cloud routes, images, retrieval, tools, and exact prompt capture first.");
      }
      const identifier = selected;
      const plannedSteps = delegateForTurn ? [
        "1. Ask the configured local Coordinator to select exactly one eligible Agent; trusted code validates the choice.",
        "2. Send this plain-text request once to that Agent through the shared single model slot.",
        "3. Show the selected Agent and both measured steps in How I answered. No retry, tool, Brain data, cloud route, or second handoff.",
      ] : [
        "1. Plan: follow this bounded, single-coordinator chat flow.",
        useKnowledge
          ? `2. Retrieve only the selected scopes: ${knowledgeScopes.map(scope => `${scope.scope}:${scope.scope_id || "current owner"}`).join(", ")}; the server will recheck the preview.`
          : "2. Skip knowledge retrieval; no knowledge scope is selected.",
        reviewedTools.length
          ? `3. Run only these reviewed read-only tools: ${reviewedTools.map(tool => tool.kind === "local-document-lookup" ? `${tool.kind} (${tool.document_id})` : tool.kind).join(", ")}.`
          : "3. Skip tools; no reviewed tool is selected.",
      ];
      if (imageIds.length) plannedSteps.push("4. Send only the selected temporary image(s), with the consent you checked.");
      plannedSteps.push(`${plannedSteps.length + 1}. Send this message and selected context to ${selectedRoute ? `${selectedRoute.provider_id} / ${selectedRoute.model_id} (${selectedRoute.destination})` : "the configured coordinator"}, then show the answer and observed trace.`);
      plannedSteps.push("No Task execution, background work, automatic retry, or unselected tool use will occur.");
      const routeLabel = (element("chat-identity").textContent || "Configured coordinator").slice(0, 240);
      const chosenRouteLabel = selectedRoute
        ? `\nAlternate route for this turn: ${selectedRoute.provider_id} / ${selectedRoute.model_id}; destination: ${selectedRoute.destination}. Prompt, recent history, and selected context/tool results go there.`
        : "\nRoute: configured model remains the default.";
      const directLocalChat = new URLSearchParams(windowRef?.location?.search || "").get("desktop") === "1"
        && !requiresCloudConsent && !selectedRoute && !imageIds.length && !reviewedTools.length
        && !useKnowledge && captureLocalPrompt.checked !== true && !delegateForTurn;
      if (!directLocalChat && !confirmImpl(`Review this chat plan before work begins:\n${plannedSteps.join("\n")}\n\nCoordinator: ${routeLabel}${chosenRouteLabel}\n\nContinue? Cancel prevents retrieval, tool calls, and provider work.`)) {
        state.textContent = "Cancelled before retrieval, tool calls, or provider work. Nothing was sent.";
        return;
      }
      const controller = new AbortController();
      requestController = controller;
      submitButton.disabled = false;
      submitButton.textContent = "Stop";
      stopRequestButton.hidden = false;
      stopRequestButton.disabled = false;
      input.disabled = true;
      const typing = documentRef.createElement("div");
      typing.id = "chat-typing-indicator";
      typing.className = "chat-typing-indicator";
      typing.setAttribute("role", "status");
      typing.textContent = "ERSELMETZ AI is thinking…";
      history.append(typing);
      try {
        const body = { text };
        if (projectBriefDigest) body.project_brief_digest = projectBriefDigest;
        if (delegateForTurn) body.delegate_once = true;
        if (requiresCloudConsent) body.cloud_consent = true;
        if (selectedRoute) Object.assign(body, {
          route_provider_id: selectedRoute.provider_id,
          route_model_id: selectedRoute.model_id,
          route_consent: true,
        });
        if (useKnowledge) Object.assign(body, {
          knowledge_enabled: true, knowledge_scopes: knowledgeScopes,
          knowledge_preview_digest: knowledgePreview.digest,
        });
        if (reviewedTools.length) body.reviewed_tools = reviewedTools;
        const capturePrompt = captureLocalPrompt.checked && captureLocalPrompt.disabled !== true;
        if (capturePrompt) body.capture_local_prompt = true;
        if (imageIds.length) {
          body.image_ids = imageIds;
          body.image_consent = true;
          body.include_local_ocr = imageManager.wantsLocalOcr();
        }
        if (streamingSupported && !delegateForTurn && !selectedRoute && !imageIds.length && !capturePrompt && !reviewedTools.length) {
          const outcome = await receiveStream(identifier, body, controller.signal);
          if (outcome.complete) {
            input.value = "";
            clearVoiceProvenance();
            render(outcome.complete);
            state.textContent = outcome.displayStopped
              ? "Display was stopped, but generation continued and completed. This did not cancel the provider request; the verified final response is shown."
              : "";
          } else {
            try { render(await request(`${base}/${encodeURIComponent(identifier)}`)); }
            catch { clear(); }
            if (outcome.partial && !outcome.displayStopped) {
              const item = documentRef.createElement("article");
              item.className = "chat-message";
              const label = documentRef.createElement("strong");
              label.textContent = "Partial streamed output - not saved as a completed reply";
              const content = documentRef.createElement("p");
              content.textContent = outcome.partial;
              item.append(label, content);
              history.append(item);
            }
            state.textContent = outcome.error
              || "The stream ended before a verified final response. This turn may have reached the provider; do not resend it.";
            canSend = false;
            input.disabled = true;
          }
        } else {
          state.textContent = "Pending: waiting for the configured model. Closing this page does not cancel its request.";
          const result = await request(`${base}/${encodeURIComponent(identifier)}/messages`, body, controller.signal);
          input.value = "";
          if (delegateForTurn) delegateOnce.checked = false;
          clearVoiceProvenance();
          render(result);
          if (result.handoff?.status === "completed") {
            state.textContent = `The Coordinator selected ${result.handoff.agent.name} for one local handoff. Open How I answered to inspect the selection and response timing.`;
          }
          imageManager?.clearConsent();
          await imageManager?.refresh();
          if (result.image_transfer) {
            const statuses = result.image_transfer.ocr_statuses || [];
            state.textContent = statuses.length
              ? `Image turn completed; selected temporary images were discarded. Local OCR: ${statuses.map(item => item.status).join(", ")}. OCR text is untrusted.`
              : "Image turn completed; selected temporary images were discarded.";
          }
        }
      } catch (error) {
        void imageManager?.refresh();
        if (controller.signal.aborted) {
          try { render(await request(`${base}/${encodeURIComponent(identifier)}`)); } catch { clear(); }
          canSend = false;
          input.disabled = true;
          state.textContent = "Stopped waiting in this app. The model may still be processing and may have saved a reply; the remote outcome is unknown. No resend was attempted.";
          return;
        }
        // Inspect recorded failure; never replay a possibly executed turn.
        try { render(await request(`${base}/${encodeURIComponent(identifier)}`)); } catch { clear(); }
        throw error;
      } finally {
        requestController = null;
        const typing = element("chat-typing-indicator");
        typing?.remove?.();
        stopRequestButton.hidden = true;
        stopRequestButton.disabled = true;
        input.disabled = !canSend;
        captureLocalPrompt.disabled = busy || !localModelAvailable;
      }
    }, { preserveSend: true });
  }
  function finishSendButton() {
    sendInProgress = false;
    const button = element("chat-send");
    button.textContent = "Send";
    button.setAttribute("aria-label", "Send message");
  }
  async function receiveStream(identifier, body, signal) {
    let displayStopped = false;
    let partial = "";
    let complete = null;
    let streamError = null;
    let buffered = "";
    let receivedBytes = 0;
    const response = await fetchImpl(
      `${base}/${encodeURIComponent(identifier)}/messages/stream`,
      {
        method: "POST",
        credentials: "same-origin",
        signal,
        headers: {
          "Content-Type": "application/json",
          "X-Local-CSRF": (await request("/api/local/session")).csrf,
        },
        body: JSON.stringify(body),
      },
    );
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(typeof payload.detail === "string" ? payload.detail : "Chat stream request failed.");
    }
    if (!response.body || typeof response.body.getReader !== "function") {
      throw new Error("The browser does not support response streaming.");
    }
    const article = documentRef.createElement("article");
    article.className = "chat-message";
    const label = documentRef.createElement("strong");
    label.textContent = "assistant - streaming";
    const output = documentRef.createElement("p");
    article.append(label, output);
    history.append(article);
    stopDisplay = () => {
      displayStopped = true;
      stopDisplayButton.disabled = true;
      output.textContent = "";
      state.textContent =
        "Stopped displaying chunks. The provider request continues; this control does not cancel generation.";
    };
    stopDisplayButton.hidden = false;
    stopDisplayButton.disabled = false;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    function consumeLine(line) {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === "status" && typeof event.message === "string") {
        state.textContent = event.message.slice(0, 80);
      } else if (event.type === "chunk" && typeof event.text === "string") {
        partial += event.text;
        receivedBytes += new TextEncoder().encode(event.text).length;
        if (receivedBytes > 8192) throw new Error("Provider stream exceeded the response limit.");
        if (!displayStopped) {
          output.textContent = partial;
          state.textContent = `Receiving actual provider output (${receivedBytes} bytes).`;
        }
      } else if (event.type === "complete" && event.streaming_supported === true
          && event.conversation && event.coordinator) {
        complete = {
          conversation: event.conversation,
          coordinator: event.coordinator,
          streaming_supported: true,
          ...(event.context_trace ? { context_trace: event.context_trace } : {}),
        };
      } else if (event.type === "error" && typeof event.message === "string") {
        streamError = event.message;
      } else {
        throw new Error("The provider returned an invalid stream event.");
      }
    }
    try {
      while (true) {
        const { value, done } = await reader.read();
        buffered += decoder.decode(value || new Uint8Array(), { stream: !done });
        if (new TextEncoder().encode(buffered).length > 65536) {
          throw new Error("Provider stream event exceeded the response limit.");
        }
        let newline = buffered.indexOf("\n");
        while (newline !== -1) {
          consumeLine(buffered.slice(0, newline));
          buffered = buffered.slice(newline + 1);
          newline = buffered.indexOf("\n");
        }
        if (done) break;
      }
      if (buffered) consumeLine(buffered);
    } finally {
      stopDisplayButton.disabled = true;
      stopDisplayButton.hidden = true;
      stopDisplay = null;
      reader.releaseLock();
    }
    if (complete && !streamError) return { complete, displayStopped };
    return {
      complete: null,
      displayStopped,
      partial,
      error: streamError || "The stream ended before a verified final response. This turn may have reached the provider; do not resend it.",
    };
  }
  async function close() {
    return action(async () => {
      if (!selected) throw new Error("Select a conversation first.");
      render(await request(`${base}/${encodeURIComponent(selected)}/close`, {}));
    });
  }
  async function previewKnowledge() {
    return action(async () => {
      if (!selected || !canSend || !knowledgeEnabled.checked) throw new Error("Select an open conversation and turn on Use my knowledge first.");
      const text = input.value;
      if (!text.trim() || new TextEncoder().encode(text).length > 8192) throw new Error("Enter a message of at most 8192 UTF-8 bytes before previewing.");
      const scopes = currentKnowledgeScopes();
      if (!scopes.length) throw new Error("Select at least one exact knowledge scope.");
      knowledgePreview = null;
      knowledgeState.textContent = "Checking only the selected owner-authorized scopes…";
      const result = await request(`${base}/${encodeURIComponent(selected)}/knowledge-preview`, { query: text, scopes });
      if (typeof result.digest !== "string" || !Array.isArray(result.items) || !result.trace) throw new Error("Invalid knowledge preview response.");
      knowledgePreview = { digest: result.digest, key: knowledgeSelectionKey(text) };
      renderKnowledgePreview(result);
      knowledgeState.textContent = "Preview is ready. The server will recheck it before Send; any changed note requires a new preview.";
    });
  }
  async function checkRouteSuggestions() {
    return action(async () => {
      if (!selected || !canSend) throw new Error("Select an open conversation before checking route suggestions.");
      const text = input.value;
      if (!text.trim() || new TextEncoder().encode(text).length > 8192) throw new Error("Enter a message of at most 8192 UTF-8 bytes first.");
      resetRouteAlternatives("Checking the current prompt; old suggestions were cleared.", true);
      routeState.textContent = "Checking local installed-model evidence and configured Gemini catalog; no model will receive this prompt.";
      const result = await request(`${base}/${encodeURIComponent(selected)}/route-suggestions`, { text });
      if (!["simple", "complex", "unknown"].includes(result.complexity) || !Array.isArray(result.candidates)) throw new Error("Invalid route-suggestion response.");
      routeAlternatives.clear();
      routeSelect.replaceChildren();
      option(routeSelect, "", "Use configured model (default)");
      for (const item of result.candidates.slice(0, 20)) {
        if (typeof item.provider_id !== "string" || typeof item.model_id !== "string"
            || typeof item.destination !== "string" || !["local", "cloud"].includes(item.kind)) continue;
        const key = `${item.provider_id}\n${item.model_id}`;
        routeAlternatives.set(key, item);
        option(routeSelect, key, `${item.provider_id} / ${item.model_id} — ${item.destination}`);
      }
      routeSelect.disabled = result.complexity !== "complex" || routeAlternatives.size === 0;
      routeSelect.value = "";
      requiresCloudConsent = configuredCloudRoute;
      cloudPanel.hidden = !requiresCloudConsent;
      cloudConsent.checked = false;
      const suggestion = result.suggested
        ? ` Optional uncertain suggestion: ${result.suggested.provider_id} / ${result.suggested.model_id}.`
        : " No verified alternate is available; keep the configured route.";
      routeState.textContent = `${result.complexity === "simple" ? "Simple" : result.complexity === "unknown" ? "Uncertain" : "Potentially complex"} prompt. ${result.reason}${suggestion} No provider received the prompt.`;
    });
  }
  function resetRouteAlternatives(message, disabled) {
    routeAlternatives.clear();
    routeSelect.replaceChildren();
    option(routeSelect, "", "Use configured model (default)");
    routeSelect.disabled = disabled;
    routeState.textContent = message;
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
      taskReview.textContent = formatDetails(proposal);
      taskState.textContent = "Review the objective, Agent, authorized context, outcome, evidence, and canonical Task fields above. No Task has been created.";
      taskControls();
    });
  }
  async function studyRepository(event) {
    event?.preventDefault();
    return action(async () => {
      if (!selected || !canSend || !canStudyRepositories) {
        throw new Error("An open conversation and github:read permission are required.");
      }
      const [objective, owner, repository] = repositoryStudyFields.map(field => field.value.trim());
      if (!objective || !owner || !repository) {
        throw new Error("Enter a study goal and an explicit GitHub owner/repository.");
      }
      repositoryStudyState.textContent =
        "Studying the allowlisted repository with bounded read-only GitHub requests…";
      repositoryStudyResult.textContent = "";
      const report = await request(
        `${base}/${encodeURIComponent(selected)}/repository-studies`,
        { objective, owner, repository },
      );
      repositoryStudyResult.textContent = formatDetails(report);
      repositoryStudyState.textContent = report.decision === "proposal_for_human_review"
        ? "Evidence-backed proposal prepared for human review; nothing was installed or executed."
        : "More information is needed before this evidence can support a review proposal.";
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
      taskReview.textContent = formatDetails(result);
      taskState.textContent = "Confirmed Task created as pending. No execution occurred.";
    });
  }
  reviewedToolsPanel.addEventListener("toggle", async () => {
    if (!reviewedToolsPanel.open || !canReadDocumentation || documentsLoaded) return;
    toolsState.textContent = "Loading authorized local documentation titles…";
    try {
      const result = await request("/api/documentation");
      if (!Array.isArray(result.items)) throw new Error("Invalid documentation list.");
      documentToolId.replaceChildren();
      const empty = documentRef.createElement("option");
      empty.value = "";
      empty.textContent = "Choose one file";
      documentToolId.append(empty);
      for (const item of result.items) {
        if (typeof item.id !== "string" || typeof item.title !== "string") continue;
        const option = documentRef.createElement("option");
        option.value = item.id;
        option.textContent = item.title;
        documentToolId.append(option);
      }
      documentsLoaded = true;
      toolsState.textContent = `${result.items.length} top-level local documentation file(s) available. The exact selected file is read only when you send this turn.`;
    } catch {
      toolsState.textContent = "Local documentation titles could not be loaded. No file was read.";
    }
  });
  element("chat-start").addEventListener("click", start);
  element("chat-route-check").addEventListener("click", checkRouteSuggestions);
  input.addEventListener("input", () => {
    resetRouteAlternatives("Prompt changed. Check suggestions again before selecting an alternate route.", true);
    requiresCloudConsent = configuredCloudRoute;
    cloudPanel.hidden = !requiresCloudConsent;
    cloudConsent.checked = false;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight || 160, 240)}px`;
  });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      element("chat-form").requestSubmit?.();
    }
  });
  for (const example of documentRef.querySelectorAll?.("[data-chat-example]") || []) {
    example.addEventListener("click", () => {
      input.value = example.getAttribute("data-chat-example") || "";
      input.focus?.();
      input.dispatchEvent?.(new Event("input", { bubbles: true }));
    });
  }
  const resizeComposer = () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight || 160, 240)}px`;
  };
  input.addEventListener("input", resizeComposer);
  const search = element("chat-search");
  search?.addEventListener("input", () => renderConversationList());
  const compactSidebar = windowRef?.matchMedia?.("(max-width: 760px)");
  const menuButton = element("chat-menu-button");
  const collapseButton = element("chat-nav-toggle");
  const setSidebarOpen = open => {
    const compact = compactSidebar?.matches === true;
    documentRef.body.classList.toggle("navigation-open", compact && open);
    if (menuButton) menuButton.setAttribute("aria-expanded", String(compact && open));
    if (collapseButton) collapseButton.setAttribute("aria-expanded", String(!documentRef.body.classList.contains("sidebar-collapsed")));
  };
  menuButton?.addEventListener("click", () => setSidebarOpen(!documentRef.body.classList.contains("navigation-open")));
  collapseButton?.addEventListener("click", () => {
    if (compactSidebar?.matches) setSidebarOpen(false);
    else documentRef.body.classList.toggle("sidebar-collapsed");
  });
  compactSidebar?.addEventListener?.("change", () => setSidebarOpen(false));
  documentRef.addEventListener?.("keydown", event => { if (event.key === "Escape") setSidebarOpen(false); });
  element("chat-sidebar")?.addEventListener?.("click", event => {
    if (event.target?.closest?.("a, [data-close-navigation]")) setSidebarOpen(false);
  });
  element("chat-add-image-action")?.addEventListener("click", () => element("chat-image-file")?.click?.());
  element("chat-camera-action")?.addEventListener("click", () => element("chat-capture-camera")?.click?.());
  element("chat-screen-action")?.addEventListener("click", () => element("chat-capture-screen")?.click?.());
  element("chat-mic")?.addEventListener("click", () => element("voice-start")?.click?.());
  element("chat-knowledge-menu-toggle")?.addEventListener("change", event => {
    knowledgeEnabled.checked = event.target.checked;
    if (knowledgeEnabled.checked) {
      element("chat-knowledge-panel").open = true;
      element("chat-settings").open = true;
    }
    knowledgeEnabled.dispatchEvent?.(new Event("change", { bubbles: true }));
  });
  element("chat-theme-toggle")?.addEventListener("click", () => {
    const theme = documentRef.body.dataset.theme === "light" ? "dark" : "light";
    applyTheme(theme);
    try { windowRef?.localStorage?.setItem(themeKey, theme); } catch { /* Theme can be changed for this page only. */ }
  });
  const quickStop = element("chat-emergency-stop");
  const activity = { microphone: false, camera: false, screen: false, playback: false, automation: false };
  const updateQuickStop = () => { if (quickStop) quickStop.hidden = !Object.values(activity).some(Boolean); };
  windowRef?.addEventListener?.("ersel:voice-activity", event => {
    activity.microphone = event.detail?.microphone === "active";
    activity.playback = event.detail?.local_playback === "active";
    updateQuickStop();
  });
  windowRef?.addEventListener?.("ersel:camera-activity", event => { activity.camera = event.detail?.state === "active"; updateQuickStop(); });
  windowRef?.addEventListener?.("ersel:screen-capture-activity", event => { activity.screen = event.detail?.state === "active"; updateQuickStop(); });
  windowRef?.addEventListener?.("ersel:automation-activity", event => { activity.automation = event.detail?.state === "active"; updateQuickStop(); });
  quickStop?.addEventListener("click", async () => {
    quickStop.disabled = true;
    try {
      const session = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      if (!session.ok) throw new Error("Sign in to stop protected activity.");
      const credentials = await session.json();
      const stopped = await fetchImpl("/api/local/emergency-stop/stop", {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Local-CSRF": credentials.csrf }, body: "{}",
      });
      if (!stopped.ok) throw new Error("Emergency stop could not be confirmed. Open Settings to review safety status.");
      windowRef?.dispatchEvent?.(new windowRef.CustomEvent("ersel:emergency-stop"));
      for (const key of Object.keys(activity)) activity[key] = false;
      updateQuickStop();
    } catch (error) { state.textContent = error.message; }
    finally { quickStop.disabled = false; }
  });
  routeSelect.addEventListener("change", () => {
    const selectedRoute = routeAlternatives.get(routeSelect.value) || null;
    requiresCloudConsent = selectedRoute ? selectedRoute.kind === "cloud" : configuredCloudRoute;
    cloudPanel.hidden = !requiresCloudConsent;
    cloudConsent.checked = false;
  });
  element("chat-form").addEventListener("submit", send);
  const changeWorkspace = async () => {
    if (busy) return;
    if (!workspaceController.selection()) { updateHeaderModel(); saveWorkspace(); return; }
    const priorCanSend = canSend;
    canSend = false; input.disabled = true;
    try { await workspaceController.change(); }
    catch (error) { state.textContent = error.message; workspaceController.remember({}); canSend = priorCanSend; }
    finally { input.disabled = !canSend; }
  };
  agents.addEventListener("change", changeWorkspace);
  element("workspace-model")?.addEventListener("change", changeWorkspace);
  element("workspace-project")?.addEventListener("change", changeWorkspace);
  element("workspace-brief-save")?.addEventListener("click", () => action(async () => {
    await workspaceController.saveBrief(element("workspace-brief").value);
    if (selected) render(await request(`${base}/${encodeURIComponent(selected)}`));
    state.textContent = "Project brief saved locally. It applies to future turns in this project.";
  }));
  element("chat-send").addEventListener("click", event => {
    if (!requestController) return;
    event.preventDefault();
    requestController.abort();
    state.textContent = "Stopping this app's wait. The local model may continue; its final outcome will be checked before any resend.";
  });
  repositoryStudyForm.addEventListener("submit", studyRepository);
  element("chat-close").addEventListener("click", close);
  element("chat-refresh").addEventListener("click", refresh);
  element("chat-approval-refresh")?.addEventListener("click", refreshApprovals);
  windowRef?.addEventListener?.("ersel:emergency-stop", () => {
    emergencyStopped = true;
    if (requestController) requestController.abort();
    stopDisplay?.();
    state.textContent = "Emergency stop active. This app stopped waiting locally; provider-side cancellation is unknown.";
  });
  windowRef?.addEventListener?.("ersel:emergency-resumed", () => { emergencyStopped = false; });
  stopDisplayButton.addEventListener("click", () => stopDisplay?.());
  stopRequestButton.addEventListener("click", () => {
    requestController?.abort();
    stopRequestButton.disabled = true;
    state.textContent = "Stopping this app's wait. A remote model may continue; its outcome is unknown.";
  });
  taskPrepare.addEventListener("click", prepareTaskProposal);
  taskConfirm.addEventListener("click", confirmTaskProposal);
  knowledgePreviewButton.addEventListener("click", previewKnowledge);
  knowledgeEnabled.addEventListener("change", () => {
    if (selected) knowledgeSettings.set(selected, { ...knowledgeSettings.get(selected), enabled: knowledgeEnabled.checked });
    knowledgePreview = null; updateKnowledgeControls();
  });
  for (const id of ["chat-knowledge-owner", "chat-knowledge-conversation", "chat-knowledge-extra-enabled", "chat-knowledge-extra-scope", "chat-knowledge-extra-id"]) {
    element(id).addEventListener("change", () => {
      if (selected) knowledgeSettings.set(selected, {
        enabled: knowledgeEnabled.checked, owner: element("chat-knowledge-owner").checked,
        conversation: element("chat-knowledge-conversation").checked,
        extra: element("chat-knowledge-extra-enabled").checked,
        extraScope: element("chat-knowledge-extra-scope").value,
        extraId: element("chat-knowledge-extra-id").value,
      });
      knowledgePreview = null; knowledgePreviewResult.hidden = true;
      knowledgeState.textContent = "Scope selection changed. Preview again before sending.";
    });
    element(id).addEventListener("input", () => { knowledgePreview = null; knowledgePreviewResult.hidden = true; });
  }
  input.addEventListener("input", () => {
    if (knowledgePreview && knowledgePreview.key !== knowledgeSelectionKey(input.value)) {
      knowledgePreview = null; knowledgePreviewResult.hidden = true;
      knowledgeState.textContent = "Message changed. Preview again before sending.";
    }
  });
  conversations.addEventListener("change", load);
  voiceController = mountVoiceControls({
    documentRef,
    windowRef,
    fetchImpl,
    confirmImpl,
    canUseChat: () => Boolean(selected && canSend && !busy),
    onTranscript: (transcript, source) => {
      const draft = input.value.replace(/\s+$/, "");
      input.value = draft ? `${draft}\n${transcript}` : transcript;
      const label = voiceTranscriptSourceLabel(source);
      if (!voiceSources.includes(label)) voiceSources.push(label);
      voiceProvenance.hidden = false;
      voiceProvenance.textContent = `Voice transcript source: ${voiceSources.join("; ")}. The draft remains editable; this source applies only to the inserted transcript, not typed text or later edits. Review it and choose Send. Nothing was submitted automatically.`;
      input.focus?.();
    },
  });
  const initialLoad = refresh();
  void initialLoad.then(() => {
    if (canManageApprovals) void refreshApprovals();
    if (canSend) input.focus?.();
  });
  return {
    initialLoad,
    refresh,
    start,
    load,
    send,
    close,
    prepareTaskProposal,
    confirmTaskProposal,
    voice: voiceController,
  };
}
if (typeof document !== "undefined") {
  mountChat();
  mountScreenCapture();
  mountCameraCapture();
}

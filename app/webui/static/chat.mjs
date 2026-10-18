import { mountVoiceControls } from "./voice.mjs";
import { mountScreenCapture } from "./screen-capture.mjs";
import { mountCameraCapture } from "./camera-capture.mjs";
import { mountChatImages } from "./chat-images.mjs";

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
  const state = element("chat-state");
  const history = element("chat-history");
  const agents = element("chat-agent");
  const conversations = element("chat-conversation");
  const input = element("chat-input");
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
  let documentsLoaded = false;
  let currentProposal = null;
  let voiceController = null;
  const voiceSources = [];
  let emergencyStopped = false;
  let requestController = null;
  let presentationPreferences = { response_mode: "balanced", locale: "en-US", detail_level: "standard" };
  const knowledgeSettings = new Map();
  let knowledgePreview = null;
  const base = "/api/chat/conversations";
  const imageManager = mountChatImages({ documentRef, windowRef, fetchImpl, getConversation: () => selected });
  function clearVoiceProvenance() {
    voiceSources.length = 0;
    voiceProvenance.hidden = true;
    voiceProvenance.textContent = "";
  }
  function clear() {
    voiceController?.clear();
    history.replaceChildren();
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
    if (!knowledgeSettings.has(record.id)) knowledgeSettings.set(record.id, {
      enabled: false, owner: false, conversation: false, extra: false,
      extraScope: "project", extraId: "",
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
    element("chat-identity").textContent = `Coordinator: ${agent.name} (${agent.role}) | ${agent.provider} / ${agent.model} | ${record.status}`;
    history.replaceChildren();
    const traces = { ...(result.context_traces || {}) };
    if (result.context_trace && record.messages.length) {
      const latestReply = [...record.messages].reverse().find(message => message.role === "assistant");
      if (latestReply?.id) traces[latestReply.id] = result.context_trace;
    }
    taskSource.replaceChildren();
    option(taskSource, "", "Select a completed chat proposal");
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
      const trace = typeof message.id === "string" ? traces[message.id] : null;
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
        : streamingSupported
          ? "Ready. This provider supports bounded response streaming."
          : "Ready. This provider returns complete responses; streaming and Stop display are unavailable.";
    canSend = record.status === "open" && !uncertain;
    input.disabled = !canSend;
    clearTaskProposal();
    taskControls();
    repositoryStudyControls();
    voiceController?.updateControls();
    updateKnowledgeControls();
    void imageManager?.refresh();
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
      captureLocalPrompt.disabled = !localModelAvailable;
      agents.disabled = false; conversations.disabled = false;
      taskControls();
      repositoryStudyControls();
      updateKnowledgeControls();
      voiceController?.updateControls();
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
      } catch {
        canCreateTask = false;
        canStudyRepositories = false;
        canReadDocumentation = false;
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
      const requestedConversation = new URLSearchParams(windowRef?.location?.search || "").get("conversation");
      if (typeof requestedConversation === "string" && /^[a-f0-9]{32}$/.test(requestedConversation)
          && list.items.some((item) => item.id === requestedConversation)) {
        conversations.value = requestedConversation;
        render(await request(`${base}/${encodeURIComponent(requestedConversation)}`));
        state.textContent = "Coordinator conversation ready.";
      } else {
        state.textContent = agentList.items.length ? "Choose an AI team member and start a conversation." : "No registered AI team member is available.";
      }
    });
  }
  async function start() {
    return action(async () => {
      if (emergencyStopped) throw new Error("Emergency stop is active. Resume protected actions before starting a conversation.");
      if (!agents.value) throw new Error("Choose an AI team member first.");
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
      if (emergencyStopped) throw new Error("Emergency stop is active. Resume protected actions before sending a message.");
      const text = input.value;
      if (!selected || !canSend) throw new Error("Start or select an open conversation first.");
      if (!text.trim() || new TextEncoder().encode(text).length > 8192) throw new Error("Enter a message of at most 8192 UTF-8 bytes.");
      if (geminiKeyPattern.test(text)) {
        input.value = "";
        throw new Error("This message looks like it contains a Gemini API key. It was not saved or sent. Use the Gemini online setup page to connect a key.");
      }
      const selectedRoute = routeAlternatives.get(routeSelect.value) || null;
      requiresCloudConsent = selectedRoute ? selectedRoute.kind === "cloud" : configuredCloudRoute;
      cloudPanel.hidden = !requiresCloudConsent;
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
          throw new Error("Preview the exact selected knowledge for this message before Send.");
        }
      }
      if (imageIds.length && !imageManager.consented()) throw new Error("Select the per-turn image consent checkbox before sending selected images to the configured provider.");
      if (!imageIds.length && imageManager?.wantsLocalOcr()) throw new Error("Select an image before requesting local OCR.");
      const identifier = selected;
      const plannedSteps = [
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
      if (!confirmImpl(`Review this chat plan before work begins:\n${plannedSteps.join("\n")}\n\nCoordinator: ${routeLabel}${chosenRouteLabel}\n\nContinue? Cancel prevents retrieval, tool calls, and provider work.`)) {
        state.textContent = "Cancelled before retrieval, tool calls, or provider work. Nothing was sent.";
        return;
      }
      const controller = new AbortController();
      requestController = controller;
      stopRequestButton.hidden = false;
      stopRequestButton.disabled = false;
      input.disabled = true;
      try {
        const body = { text };
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
        if (streamingSupported && !selectedRoute && !imageIds.length && !capturePrompt && !reviewedTools.length) {
          const outcome = await receiveStream(identifier, body, controller.signal);
          if (outcome.complete) {
            input.value = "";
            clearVoiceProvenance();
            render(outcome.complete);
            state.textContent = outcome.displayStopped
              ? "Display was stopped, but generation continued and completed. This did not cancel the provider request; the verified final response is shown."
              : "Stream completed and the final response was saved.";
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
          clearVoiceProvenance();
          render(result);
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
        stopRequestButton.hidden = true;
        stopRequestButton.disabled = true;
        input.disabled = !canSend;
        captureLocalPrompt.disabled = busy || !localModelAvailable;
      }
    });
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
      if (event.type === "chunk" && typeof event.text === "string") {
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
      taskReview.textContent = JSON.stringify(proposal, null, 2);
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
      repositoryStudyResult.textContent = JSON.stringify(report, null, 2);
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
      taskReview.textContent = JSON.stringify(result, null, 2);
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
  });
  routeSelect.addEventListener("change", () => {
    const selectedRoute = routeAlternatives.get(routeSelect.value) || null;
    requiresCloudConsent = selectedRoute ? selectedRoute.kind === "cloud" : configuredCloudRoute;
    cloudPanel.hidden = !requiresCloudConsent;
    cloudConsent.checked = false;
  });
  element("chat-form").addEventListener("submit", send);
  repositoryStudyForm.addEventListener("submit", studyRepository);
  element("chat-close").addEventListener("click", close);
  element("chat-refresh").addEventListener("click", refresh);
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
  return {
    initialLoad: refresh(),
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

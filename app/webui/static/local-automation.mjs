export function createAutomationApprovalFlow({ request, confirmImpl = message => globalThis.confirm(message),
                                              onStatus = () => {} }) {
  return async function approveAndExecute(kind, actionBody) {
    const route = `/api/local/automation/${kind}`;
    const preview = await request(`${route}/preview`, { method: "POST", body: actionBody });
    onStatus(`Preview only: ${preview.action || actionBody.action}. Target: ${preview.target_label || preview.window_title || actionBody.name || actionBody.control_name}. No action has run.`);
    const approvalResult = await request(`${route}/request-approval`, { method: "POST", body: actionBody });
    const approval = approvalResult.approval;
    const summary = `${approval.action_summary}\nTarget: ${approval.target_ref}\nExact request: ${JSON.stringify(actionBody)}\nApproval digest: ${approval.approval_digest}\nPayload digest: ${approval.payload_digest}\nTarget digest: ${approval.target_digest}\nExpires: ${approval.expires_at}\n\nApprove this exact action once?`;
    if (confirmImpl(summary) !== true) {
      onStatus("Cancelled. The action was not approved or executed.");
      return { state: "cancelled" };
    }
    await request(`/api/capabilities/approvals/${encodeURIComponent(approval.approval_id)}/approve`, {
      method: "POST", body: { confirmed_digest: approval.approval_digest },
    });
    const result = await request(`${route}/execute`, {
      method: "POST", body: { ...actionBody, approval_id: approval.approval_id },
    });
    const known = result.remote_outcome === "known_success";
    onStatus(known ? "Action completed." : "Action was dispatched; the remote outcome is unknown. Do not retry automatically.");
    return result;
  };
}

export function mountLocalAutomation({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
                                       confirmImpl = message => globalThis.confirm(message),
                                       setIntervalImpl = globalThis.setInterval } = {}) {
  const root = documentRef?.getElementById?.("automation-state");
  if (!root || typeof fetchImpl !== "function") return { refresh: async () => {} };
  const byId = id => documentRef.getElementById(id);
  const state = byId("automation-state");
  const activity = byId("automation-activity");
  const status = message => { if (activity) activity.textContent = message; };
  async function session() {
    const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error(response.status === 401 ? "Sign in as the local owner to use computer automation." : "Owner session is unavailable.");
    return response.json();
  }
  async function request(path, { method = "GET", body } = {}) {
    const options = { method, credentials: "same-origin", cache: "no-store" };
    if (method !== "GET") {
      const auth = await session();
      options.headers = { "Content-Type": "application/json", "X-Local-CSRF": auth.csrf };
      options.body = JSON.stringify(body ?? {});
    }
    const response = await fetchImpl(path, options);
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Computer automation request failed.");
    return result;
  }
  const flow = createAutomationApprovalFlow({ request, confirmImpl, onStatus: status });
  async function run(button, operation) {
    if (!button) return;
    button.disabled = true;
    try { await operation(); await refresh(); }
    catch (error) { status(error.message); }
    finally { button.disabled = false; }
  }
  async function refresh() {
    try {
      const result = await request("/api/local/automation");
      state.textContent = `Local owner session active. Browser allowlist: ${result.browser.allowed_origins.join(", ") || "empty"}. Desktop allowlist: ${result.desktop.allowed_process_names.join(", ") || "empty"}. Policies last for this app process only.`;
      const isActive = result.browser.active || result.desktop.active;
      activity.textContent = isActive ? `Protected activity: browser ${result.browser.state}; desktop ${result.desktop.state}.` : "No protected computer action is currently running.";
      const stopButton = byId("automation-stop");
      if (stopButton) stopButton.hidden = false;
      const originList = byId("automation-origins");
      if (originList) originList.replaceChildren(...result.browser.allowed_origins.map(value => {
        const item = documentRef.createElement("li"); item.textContent = value;
        const remove = documentRef.createElement("button"); remove.type = "button"; remove.textContent = "Remove";
        remove.addEventListener("click", () => run(remove, async () => { await request("/api/local/automation/browser/origin", { method: "PUT", body: { origin: value, allowed: false } }); await refresh(); }));
        item.append(" ", remove); return item;
      }));
      const processList = byId("desktop-processes");
      if (processList) processList.replaceChildren(...result.desktop.allowed_process_names.map(value => {
        const item = documentRef.createElement("li"); item.textContent = value;
        const remove = documentRef.createElement("button"); remove.type = "button"; remove.textContent = "Remove";
        remove.addEventListener("click", () => run(remove, async () => { await request("/api/local/automation/desktop/process", { method: "PUT", body: { process_name: value, allowed: false } }); await refresh(); }));
        item.append(" ", remove); return item;
      }));
    } catch (error) { state.textContent = error.message; }
    try {
      const traces = await request("/api/local/automation/traces");
      const list = byId("automation-traces");
      if (list) list.replaceChildren(...traces.items.map(trace => {
        const item = documentRef.createElement("li");
        item.textContent = `${trace.capability_id}: ${trace.action_id}; ${trace.action_result}; outcome ${trace.remote_outcome}.`;
        return item;
      }));
    } catch (error) { status(error.message); }
  }
  byId("automation-refresh")?.addEventListener("click", () => void refresh());
  byId("automation-stop")?.addEventListener("click", event => run(event.currentTarget, () => request("/api/local/emergency-stop/stop", { method: "POST", body: {} })));
  byId("automation-origin-add")?.addEventListener("click", event => run(event.currentTarget, async () => {
    const value = byId("automation-origin")?.value?.trim();
    await request("/api/local/automation/browser/origin", { method: "PUT", body: { origin: value, allowed: true } });
    if (byId("automation-origin")) byId("automation-origin").value = "";
    await refresh();
  }));
  let browserBody = null;
  byId("browser-preview")?.addEventListener("click", event => run(event.currentTarget, async () => {
    browserBody = { action: byId("browser-action").value, url: byId("browser-url").value.trim(),
      role: byId("browser-role").value, name: byId("browser-name").value.trim(),
      value: byId("browser-action").value === "fill_text" ? byId("browser-value").value : null };
    if (confirmImpl(`Open this exact URL in the visible temporary browser to inspect the target?\n${browserBody.url}\n\nThis sends a page request to the allowlisted site, which may process even a GET request. No click or text entry will be sent.`) !== true) {
      status("Page inspection cancelled. No browser was opened."); return;
    }
    status("Opening the exact page in a visible temporary browser for read-only inspection. No click or text entry will be sent.");
    const result = await request("/api/local/automation/browser/preview", { method: "POST", body: browserBody });
    byId("browser-preview-result").textContent = JSON.stringify({ action: result.action, target: result.target_label,
      url: browserBody.url, target_digest: result.target_digest, payload_digest: result.payload_digest,
      confirmation_required: result.confirmation_required }, null, 2);
    byId("browser-run").hidden = false;
    status("Read-only preview complete. No browser action has been dispatched.");
  }));
  byId("browser-run")?.addEventListener("click", event => run(event.currentTarget, async () => {
    if (!browserBody) throw new Error("Preview the exact browser action before approval.");
    const result = await flow("browser", browserBody);
    if (result.state !== "cancelled") byId("browser-run").hidden = true;
  }));
  byId("desktop-process-add")?.addEventListener("click", event => run(event.currentTarget, async () => {
    const value = byId("desktop-process").value.trim().toLowerCase();
    await request("/api/local/automation/desktop/process", { method: "PUT", body: { process_name: value, allowed: true } });
    await refresh();
  }));
  byId("desktop-discover")?.addEventListener("click", event => run(event.currentTarget, async () => {
    const value = byId("desktop-process").value.trim().toLowerCase();
    const result = await request("/api/local/automation/desktop/windows", { method: "POST", body: { process_name: value } });
    const select = byId("desktop-window");
    select.replaceChildren(...[new Option("Select an allowlisted window", ""), ...result.items.map(item => {
      const option = new Option(`${item.window_title} (${item.process_name})`, JSON.stringify(item)); return option;
    })]);
    status(`Found ${result.items.length} visible window(s) for ${value}.`);
  }));
  byId("desktop-buttons")?.addEventListener("click", event => run(event.currentTarget, async () => {
    const selected = JSON.parse(byId("desktop-window").value || "null");
    if (!selected) throw new Error("Select a visible window first.");
    const result = await request("/api/local/automation/desktop/buttons", { method: "POST", body: selected });
    const select = byId("desktop-button");
    select.replaceChildren(...[new Option("Select an inspected button", ""), ...result.items.map(item =>
      new Option(`${item.control_name} (${item.automation_id})`, JSON.stringify(item))) ]);
    status(`Inspected ${result.items.length} enabled, visible direct-child buttons. No button was invoked.`);
  }));
  byId("desktop-run")?.addEventListener("click", event => run(event.currentTarget, async () => {
    const window = JSON.parse(byId("desktop-window").value || "null");
    const button = JSON.parse(byId("desktop-button").value || "null");
    if (!window || !button) throw new Error("Inspect and select one visible button first.");
    const body = { ...window, ...button };
    await flow("desktop", body);
    await refresh();
  }));
  byId("desktop-button")?.addEventListener("change", () => { byId("desktop-run").disabled = !byId("desktop-button").value; });
  void refresh();
  if (typeof setIntervalImpl === "function") setIntervalImpl(() => void refresh(), 1000);
  return { refresh, request };
}

if (typeof document !== "undefined") mountLocalAutomation();

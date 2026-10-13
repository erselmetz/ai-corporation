export function isQuietNow({ quiet_start: start, quiet_end: end }, date = new Date()) {
  if (!start || !end) return false;
  const current = `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  return start < end ? current >= start && current < end : current >= start || current < end;
}

export async function mountSuggestions({ documentRef = globalThis.document,
  fetchImpl = globalThis.fetch, nowImpl = () => new Date() } = {}) {
  const byId = id => documentRef.getElementById(id);
  const status = byId("suggestions-status");
  const list = byId("suggestions-list");
  const form = byId("suggestions-settings");
  const enabled = byId("suggestions-enabled");
  const quietStart = byId("suggestions-quiet-start");
  const quietEnd = byId("suggestions-quiet-end");
  let preferences = null;
  let csrf = "";
  let loading = false;
  const refreshButton = byId("suggestions-refresh");

  const request = async (path, options = {}) => {
    const response = await fetchImpl(path, { credentials: "same-origin", cache: "no-store", ...options });
    let body = {};
    try { body = await response.json(); } catch { /* handled as an empty error body */ }
    if (!response.ok) throw new Error(body.detail || (response.status === 401
      ? "Sign in to view and manage suggestions."
      : response.status === 403 ? "This session is not allowed to read workflow suggestions."
        : "Suggestions are unavailable."));
    return body;
  };

  const showPreferences = value => {
    preferences = value;
    enabled.checked = value.enabled === true;
    quietStart.value = value.quiet_start || "";
    quietEnd.value = value.quiet_end || "";
  };

  const quietMessage = () => {
    status.textContent = `Quiet period is active in this browser’s local time (${preferences.quiet_start}–${preferences.quiet_end}). Suggestions are hidden until it ends.`;
    list.replaceChildren();
  };

  async function loadSuggestions() {
    if (!preferences?.enabled) {
      list.replaceChildren();
      status.textContent = "Suggestions are off. Enable them above to inspect current workflow signals.";
      return;
    }
    if (isQuietNow(preferences, nowImpl())) { quietMessage(); return; }
    if (loading) return;
    loading = true;
    refreshButton.disabled = true;
    status.textContent = "Checking current local workflow records…";
    list.replaceChildren();
    try {
      const result = await request("/api/local/suggestions");
      const checked = new Date(result.generated_at).toLocaleString();
      status.textContent = result.suggestions.length
        ? `Source: local workflow records · checked ${checked}. Suggestions require your decision.`
        : `No current workflow suggestions. Source checked: ${checked}.`;
      for (const suggestion of result.suggestions) {
        const row = documentRef.createElement("li");
        const heading = documentRef.createElement("h3");
        heading.textContent = suggestion.title;
        const reason = documentRef.createElement("p");
        reason.textContent = suggestion.reason;
        const source = documentRef.createElement("p");
        source.className = "muted";
        const lastChanged = suggestion.source.last_changed_at
          ? new Date(suggestion.source.last_changed_at).toLocaleString() : "time unavailable";
        source.textContent = `Workflow ${suggestion.source.workflow_id}, item ${suggestion.source.work_item_id}; state ${suggestion.state}; last changed ${lastChanged}; checked ${new Date(suggestion.observed_at).toLocaleString()}.`;
        const actions = documentRef.createElement("div");
        actions.className = "suggestion-actions";
        const inspect = documentRef.createElement("a");
        inspect.href = suggestion.href;
        inspect.textContent = "Inspect workflow";
        const dismiss = documentRef.createElement("button");
        dismiss.type = "button";
        dismiss.textContent = "Dismiss";
        dismiss.addEventListener("click", async () => {
          dismiss.disabled = true;
          try {
            await request(`/api/local/suggestions/${encodeURIComponent(suggestion.id)}/dismiss`, {
              method: "POST", headers: { "X-Local-CSRF": csrf }, body: "{}",
            });
            await loadSuggestions();
          } catch (error) { status.textContent = error.message; dismiss.disabled = false; }
        });
        actions.append(inspect, dismiss);
        row.append(heading, reason, source, actions);
        list.append(row);
      }
    } catch (error) {
      status.textContent = error.message;
      list.replaceChildren();
    } finally {
      loading = false;
      refreshButton.disabled = false;
    }
  }

  async function loadPreferences() {
    try {
      const session = await request("/api/local/session");
      csrf = session.csrf;
      const result = await request("/api/local/suggestions/preferences");
      showPreferences(result.preferences);
      await loadSuggestions();
    } catch (error) {
      status.textContent = error.message;
      list.replaceChildren();
    }
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();
    const changes = { enabled: enabled.checked, quiet_start: quietStart.value, quiet_end: quietEnd.value };
    try {
      const result = await request("/api/local/suggestions/preferences", {
        method: "PUT", headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
        body: JSON.stringify(changes),
      });
      showPreferences(result.preferences);
      await loadSuggestions();
    } catch (error) { status.textContent = error.message; }
  });
  refreshButton.addEventListener("click", loadSuggestions);
  await loadPreferences();
  return { loadSuggestions };
}

if (globalThis.document?.getElementById("suggestions-settings")) await mountSuggestions();

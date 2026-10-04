export function mountAssignmentPolicy({
  documentRef = document,
  fetchImpl = fetch,
  confirmImpl = globalThis.confirm,
} = {}) {
  const config = documentRef.getElementById("assignment-policy-config");
  const state = documentRef.getElementById("assignment-policy-state");
  const results = documentRef.getElementById("assignment-policy-results");
  const save = documentRef.getElementById("assignment-policy-save");
  const disable = documentRef.getElementById("assignment-policy-disable");
  const preview = documentRef.getElementById("assignment-policy-preview");
  let canManage = false, busy = false, csrf = "";

  function controls() {
    config.disabled = busy || !canManage;
    save.disabled = busy || !canManage;
    disable.disabled = busy || !canManage;
    preview.disabled = busy;
  }

  async function request(path, options = {}) {
    const response = await fetchImpl(path, {
      ...options,
      credentials: "same-origin",
      headers: { Accept: "application/json", ...options.headers },
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error("Sign in through local owner access first.");
      if (response.status === 403) throw new Error("This session lacks assignment policy permission.");
      throw new Error("Assignment policy request failed; no Agent assignment was changed.");
    }
    return response.json();
  }

  async function run(action) {
    if (busy) return;
    busy = true;
    controls();
    try {
      await action();
    } catch (error) {
      state.textContent = error.message;
    } finally {
      busy = false;
      controls();
    }
  }

  function show(value) {
    results.textContent = JSON.stringify(value, null, 2);
  }

  save.addEventListener("click", () => run(async () => {
    let policy;
    try {
      policy = JSON.parse(config.value);
    } catch {
      throw new Error("Policy must be valid JSON.");
    }
    if (policy.enabled !== true) {
      throw new Error("Set enabled to true before saving an owner-approved policy.");
    }
    if (!confirmImpl("Enable review-only model recommendations? No Agent assignment or provider connection will change.")) {
      state.textContent = "Policy was not changed.";
      return;
    }
    const saved = await request("/api/local/assignment-policy", {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
      body: JSON.stringify(policy),
    });
    config.value = JSON.stringify(saved, null, 2);
    state.textContent = "Owner-approved policy saved and enabled. Assignments are unchanged.";
    show(await request("/api/local/assignment-policy/preview"));
  }));

  disable.addEventListener("click", () => run(async () => {
    if (!confirmImpl("Disable recommendations and clear the saved policy? Existing Agent assignments will remain unchanged.")) {
      state.textContent = "Policy was retained; no assignment was changed.";
      return;
    }
    const saved = await request("/api/local/assignment-policy", {
      method: "DELETE",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
    });
    config.value = JSON.stringify(saved, null, 2);
    state.textContent = "Recommendations disabled and policy data cleared. Existing Agent assignments are unchanged.";
    show(await request("/api/local/assignment-policy/preview"));
  }));

  preview.addEventListener("click", () => run(async () => {
    show(await request("/api/local/assignment-policy/preview"));
    state.textContent = "Preview refreshed. No assignment or provider state was changed.";
  }));

  controls();
  return run(async () => {
    const session = await request("/api/local/session");
    csrf = session.csrf;
    canManage = session.permissions.includes("assignment-policy:manage");
    config.value = JSON.stringify(
      await request("/api/local/assignment-policy"),
      null,
      2,
    );
    show(await request("/api/local/assignment-policy/preview"));
    state.textContent = canManage
      ? "Policy is disabled by default. Save an owner-approved policy to enable review-only recommendations."
      : "Read-only assignment policy access; this session cannot configure it.";
  });
}

if (typeof document !== "undefined" && document.getElementById("assignment-policy-config")) {
  mountAssignmentPolicy();
}

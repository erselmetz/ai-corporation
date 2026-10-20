export function mountCapabilityPacks({ documentRef = globalThis.document, fetchImpl = globalThis.fetch,
                                      confirmImpl = message => globalThis.confirm(message) } = {}) {
  const list = documentRef?.getElementById?.("media-capability-packs");
  const status = documentRef?.getElementById?.("media-capability-packs-status");
  if (!list || !status || typeof fetchImpl !== "function") return { refresh: async () => {} };

  async function session() {
    const response = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error(response.status === 401 ? "Sign in to manage optional local capability packs." : "Owner session is unavailable.");
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
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Capability pack request failed.");
    return result;
  }
  function card(preview) {
    const article = documentRef.createElement("article");
    article.className = "management-card capability-pack-card";
    const heading = documentRef.createElement("h3"); heading.textContent = preview.title;
    const state = documentRef.createElement("p"); state.setAttribute("role", "status");
    const stateName = preview.state === "working" ? "Working" : preview.state === "installed" ? "Installed" : "Not installed";
    state.textContent = `${stateName}${preview.supported ? " · CPython 3.14 / Windows x64 supported" : " · This Python / Windows runtime is unsupported"}`;
    const detail = documentRef.createElement("p"); detail.className = "muted";
    detail.textContent = `${preview.source}. ${preview.compatibility}. ${preview.detail}`;
    const files = documentRef.createElement("details");
    const summary = documentRef.createElement("summary"); summary.textContent = `Review ${preview.download_bytes.toLocaleString()} byte download and pinned wheels`;
    const manifest = documentRef.createElement("p");
    manifest.textContent = `${preview.files.join(", ")}. SHA-256 manifest: ${preview.manifest_digest}.`;
    files.append(summary, manifest);
    const actions = documentRef.createElement("div"); actions.className = "capability-pack-actions";
    const install = documentRef.createElement("button"); install.type = "button";
    install.textContent = "Review & install"; install.disabled = !preview.supported || preview.state !== "not-installed";
    install.addEventListener("click", async () => {
      const accepted = confirmImpl(`${preview.title}\n\nSource: ${preview.source}\nFiles: ${preview.files.join(", ")}\nTotal: ${preview.download_bytes.toLocaleString()} bytes\nSHA-256 manifest: ${preview.manifest_digest}\n\nInstall these exact wheels into the isolated local app directory?`);
      if (accepted !== true) { status.textContent = "Installation cancelled. No files were downloaded."; return; }
      install.disabled = true; status.textContent = `Installing ${preview.title}; verified wheel bytes are being checked.`;
      try {
        await request(`/api/capability-packs/${encodeURIComponent(preview.pack_id)}/install`, {
          method: "POST", body: { confirmed: true, manifest_digest: preview.manifest_digest },
        });
        status.textContent = "Pinned pack installed. Run its self-test before use."; await refresh();
      } catch (error) { status.textContent = error.message; install.disabled = false; }
    });
    const test = documentRef.createElement("button"); test.type = "button"; test.textContent = "Test it";
    test.disabled = preview.state === "not-installed";
    test.addEventListener("click", async () => {
      test.disabled = true; status.textContent = `Testing ${preview.title} locally.`;
      try {
        const result = await request(`/api/capability-packs/${encodeURIComponent(preview.pack_id)}/self-test`, { method: "POST" });
        status.textContent = result.detail || `Self-test state: ${result.state}.`; await refresh();
      } catch (error) { status.textContent = error.message; test.disabled = false; }
    });
    actions.append(install, test); article.append(heading, state, detail, files, actions);
    return article;
  }
  async function refresh() {
    status.textContent = "Checking optional local capability packs.";
    try {
      const result = await request("/api/capability-packs");
      list.replaceChildren(...(result.items || []).map(card));
      status.textContent = result.items?.length ? "Pack inventory reflects the local app directory and the last self-test in this process." : "No optional packs are configured.";
    } catch (error) { list.replaceChildren(); status.textContent = error.message; }
  }
  void refresh();
  return { refresh };
}

if (typeof document !== "undefined") mountCapabilityPacks();

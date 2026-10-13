const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

function base64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  return btoa(binary);
}

export function mountChatImages({ documentRef = document, windowRef = globalThis.window, fetchImpl = fetch, getConversation = () => null } = {}) {
  const list = documentRef.getElementById("chat-image-list");
  const file = documentRef.getElementById("chat-image-file");
  const upload = documentRef.getElementById("chat-image-upload");
  const consentPanel = documentRef.getElementById("chat-image-consent-panel");
  const consent = documentRef.getElementById("chat-image-consent");
  const ocr = documentRef.getElementById("chat-image-ocr");
  const state = documentRef.getElementById("chat-image-status");
  if (!list || !file || !upload || !consentPanel || !consent || !ocr || !state) return null;
  let images = [];
  let providerSupported = false;
  let busy = false;
  function selectedIds() { return [...list.querySelectorAll?.("input[type=checkbox]:checked") || []].map(input => input.value); }
  function render() {
    list.replaceChildren();
    for (const image of images) {
      const row = documentRef.createElement("div");
      const label = documentRef.createElement("label");
      const checkbox = documentRef.createElement("input");
      checkbox.type = "checkbox"; checkbox.value = image.id; checkbox.disabled = busy || !providerSupported;
      const description = documentRef.createElement("span");
      description.textContent = `${image.source}: ${image.media_type}, ${image.size_bytes} bytes, expires ${image.expires_at}. Include for one reply.`;
      label.append(checkbox, description);
      const remove = documentRef.createElement("button"); remove.type = "button"; remove.textContent = "Discard"; remove.disabled = busy;
      remove.addEventListener("click", () => void discard(image.id));
      row.append(label, remove); list.append(row);
    }
    consentPanel.hidden = images.length === 0;
    if (!images.length) { consent.checked = false; ocr.checked = false; }
    consent.disabled = busy || !providerSupported;
    ocr.disabled = busy || !providerSupported;
  }
  async function request(url, options = {}) {
    let headers = { ...(options.headers || {}) };
    if (options.method && options.method !== "GET") {
      const sessionResponse = await fetchImpl("/api/local/session", { credentials: "same-origin", cache: "no-store" });
      if (!sessionResponse.ok) throw new Error("Sign in again to manage temporary images.");
      headers["X-Local-CSRF"] = (await sessionResponse.json()).csrf;
    }
    const response = await fetchImpl(url, { credentials: "same-origin", cache: "no-store", ...options, headers });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Temporary image action failed.");
    return payload;
  }
  async function refresh() {
    const id = getConversation();
    if (!id) { images = []; providerSupported = false; render(); return; }
    try {
      const result = await request(`/api/chat/conversations/${encodeURIComponent(id)}/images`);
      images = Array.isArray(result.items) ? result.items : [];
      providerSupported = result.provider_transfer_supported === true;
      render();
      state.textContent = images.length ? (providerSupported
        ? "Selected images stay temporary and are discarded after their one-use chat turn. They are not sent until you select them and confirm consent below."
        : "This configured provider does not report image input support; attached images cannot be sent.") : "No temporary images attached.";
    } catch (error) { images = []; providerSupported = false; render(); state.textContent = error.message; }
  }
  async function attach() {
    if (busy) return;
    const id = getConversation(); const selected = file.files?.[0];
    if (!id) { state.textContent = "Start or select an open conversation first."; return; }
    if (!selected || !["image/jpeg", "image/png"].includes(selected.type) || selected.size > MAX_IMAGE_BYTES) {
      state.textContent = "Choose one JPEG or PNG up to 2 MiB."; return;
    }
    busy = true; render();
    try {
      const bytes = new Uint8Array(await selected.arrayBuffer());
      const result = await request(`/api/chat/conversations/${encodeURIComponent(id)}/images`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ media_type: selected.type, data_base64: base64(bytes) }) });
      file.value = ""; state.textContent = result.message; await refresh();
    } catch (error) { state.textContent = error.message; }
    finally { busy = false; render(); }
  }
  async function discard(imageId) {
    if (busy) return; const id = getConversation(); if (!id) return;
    busy = true; render();
    try { await request(`/api/chat/conversations/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}`, { method: "DELETE" }); await refresh(); }
    catch (error) { state.textContent = error.message; }
    finally { busy = false; render(); }
  }
  upload.addEventListener("click", () => void attach());
  consent.addEventListener("change", () => { if (!consent.checked) ocr.checked = false; });
  windowRef?.addEventListener?.("ersel:chat-images-changed", () => void refresh());
  return { refresh, selectedIds, consented: () => consent.checked === true, wantsLocalOcr: () => ocr.checked === true, clearConsent: () => { consent.checked = false; ocr.checked = false; render(); } };
}

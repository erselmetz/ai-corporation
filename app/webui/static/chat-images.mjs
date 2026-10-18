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
  const transferPreview = documentRef.getElementById("chat-image-transfer-preview");
  const consent = documentRef.getElementById("chat-image-consent");
  const ocr = documentRef.getElementById("chat-image-ocr");
  const state = documentRef.getElementById("chat-image-status");
  if (!list || !file || !upload || !consentPanel || !consent || !ocr || !state) return null;
  let images = [];
  let providerSupported = false;
  let destination = null;
  let busy = false;
  function selectedIds() { return [...list.querySelectorAll?.("input[type=checkbox]:checked") || []].map(input => input.value); }
  function renderPreview() {
    if (!transferPreview) return;
    transferPreview.replaceChildren();
    const selected = images.filter(image => selectedIds().includes(image.id));
    transferPreview.hidden = selected.length === 0;
    if (!selected.length) return;
    const heading = documentRef.createElement("h3");
    heading.textContent = "Image transfer preview";
    transferPreview.append(heading);
    const target = documentRef.createElement("p");
    const local = destination?.local === true;
    target.textContent = `Destination: ${destination?.provider_id || "unknown provider"} / ${destination?.model_id || "unknown model"} (${local ? "local" : "online"}; vision capability ${destination?.state || "unknown"}).`;
    transferPreview.append(target);
    const policy = documentRef.createElement("p");
    policy.textContent = local
      ? "Local transfer only after you consent for this reply."
      : "Online transfer needs this image consent and the separate cloud-consent checkbox.";
    transferPreview.append(policy);
    for (const image of selected) {
      const item = documentRef.createElement("div");
      const preview = documentRef.createElement("img");
      preview.src = `/api/chat/conversations/${encodeURIComponent(getConversation())}/images/${encodeURIComponent(image.id)}/preview`;
      preview.alt = `Preview of selected ${image.media_type} image, ${image.width} by ${image.height} pixels`;
      preview.loading = "lazy";
      item.append(preview);
      const details = documentRef.createElement("p");
      details.textContent = `${image.media_type} · ${image.width} × ${image.height} · ${image.size_bytes} bytes. Original image sent; no resize, crop, or redaction.`;
      item.append(details);
      transferPreview.append(item);
    }
    const ocrInfo = documentRef.createElement("p");
    ocrInfo.textContent = ocr.checked
      ? "Preprocessing: optional local OCR is enabled; extracted text will be included as untrusted evidence."
      : "Preprocessing: none selected.";
    transferPreview.append(ocrInfo);
  }
  function render() {
    list.replaceChildren();
    for (const image of images) {
      const row = documentRef.createElement("div");
      const label = documentRef.createElement("label");
      const checkbox = documentRef.createElement("input");
      checkbox.type = "checkbox"; checkbox.value = image.id; checkbox.disabled = busy || !providerSupported;
      checkbox.addEventListener("change", renderPreview);
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
    renderPreview();
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
      destination = result.destination || null;
      render();
      state.textContent = images.length ? (providerSupported
        ? "Images stay temporary and are discarded after one attempted turn. Select each image, review its preview and destination, then consent below."
        : `Vision is ${destination?.state || "unknown"} for ${destination?.provider_id || "the configured provider"} / ${destination?.model_id || "the selected model"}; no fallback is used.`) : "No temporary images attached.";
    } catch (error) { images = []; providerSupported = false; destination = null; render(); state.textContent = error.message; }
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
  consent.addEventListener("change", () => { if (!consent.checked) ocr.checked = false; renderPreview(); });
  ocr.addEventListener("change", renderPreview);
  windowRef?.addEventListener?.("ersel:chat-images-changed", () => void refresh());
  return { refresh, selectedIds, consented: () => consent.checked === true, wantsLocalOcr: () => ocr.checked === true, clearConsent: () => { consent.checked = false; ocr.checked = false; render(); } };
}

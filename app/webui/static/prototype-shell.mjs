// Task 223: compose existing, permission-checked surfaces without changing their services.
export function clampSplit(value, low = 25, high = 75) {
  return Math.max(low, Math.min(high, Number.isFinite(value) ? value : 50));
}

export async function mountPrototypeShell({ documentRef = document, windowRef = window,
  fetchImpl = fetch, loadKnowledge = () => import("./knowledge.mjs") } = {}) {
  const el = id => documentRef.getElementById(id);
  const app = documentRef.querySelector(".chat-app");
  if (!app || el("shell-brain")) return;
  documentRef.body.classList.add("prototype-shell");
  const sidebar = el("chat-sidebar"), workspace = documentRef.querySelector(".chat-workspace");
  const brain = documentRef.createElement("section");
  brain.id = "shell-brain"; brain.setAttribute("aria-label", "Brain and observed steps");
  brain.innerHTML = `<header><h1>Brain</h1><a href="/ui/knowledge">Brain settings</a></header>
    <div id="shell-map"><p id="shell-brain-state" role="status">Loading local Brain…</p></div>
    <section class="shell-log"><h2>Steps</h2><p>Observed retrieval, tool calls and results appear here. Model thinking support arrives in Phase 226.</p><div id="shell-step-log" aria-live="polite"></div></section>`;
  const separator = (name, adjust) => {
    const node = documentRef.createElement("div"); node.className = "shell-separator";
    node.tabIndex = 0; node.setAttribute("role", "separator");
    node.setAttribute("aria-label", name); node.setAttribute("aria-orientation", "vertical");
    node.setAttribute("aria-valuemin", "25"); node.setAttribute("aria-valuemax", "75");
    node.setAttribute("aria-valuenow", "50");
    node.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home"].includes(event.key)) return;
      event.preventDefault(); adjust(event.key === "Home" ? 50 : Number(node.getAttribute("aria-valuenow")) + (event.key === "ArrowLeft" ? -2 : 2), node);
    });
    node.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      node.setPointerCapture(event.pointerId);
      const move = next => {
        const rect = app.getBoundingClientRect();
        const left = name === "Resize sidebar" ? rect.left : sidebar.getBoundingClientRect().right;
        adjust(100 * (next.clientX - left) / Math.max(1, rect.right - left), node);
      };
      const end = () => { node.removeEventListener("pointermove", move); node.removeEventListener("pointerup", end); node.removeEventListener("pointercancel", end); };
      node.addEventListener("pointermove", move); node.addEventListener("pointerup", end); node.addEventListener("pointercancel", end);
    });
    return node;
  };
  const leftSplit = separator("Resize sidebar", (value, node) => {
    const bounded = clampSplit(value, 15, 30);
    app.style.setProperty("--shell-sidebar", `${bounded}vw`); node.setAttribute("aria-valuenow", String(bounded));
  });
  leftSplit.id = "shell-left-split"; leftSplit.setAttribute("aria-valuemin", "15"); leftSplit.setAttribute("aria-valuemax", "30"); leftSplit.setAttribute("aria-valuenow", "20");
  const rightSplit = separator("Resize Brain and chat", (value, node) => {
    const bounded = clampSplit(value); app.style.setProperty("--shell-brain", `${bounded}fr`);
    app.style.setProperty("--shell-chat", `${100 - bounded}fr`); node.setAttribute("aria-valuenow", String(bounded));
  });
  rightSplit.id = "shell-right-split";
  app.insertBefore(leftSplit, workspace); app.insertBefore(brain, workspace); app.insertBefore(rightSplit, workspace);

  const tabs = documentRef.createElement("nav"); tabs.id = "shell-tabs"; tabs.setAttribute("aria-label", "Chat tabs");
  for (const id of ["chat-start", "chat-conversation-list", "chat-earlier-list"]) tabs.append(el(id));
  workspace.prepend(tabs);
  for (const node of sidebar.querySelectorAll(".chat-sidebar-label")) node.hidden = true;
  const searchLabel = el("chat-search").closest("label");
  const controls = documentRef.createElement("section"); controls.className = "shell-actions";
  controls.innerHTML = `<h2>My Brain</h2><button id="shell-feed-file" type="button">Feed file</button><button id="shell-feed-folder" type="button">Feed folder</button><button id="shell-add-note" type="button">Add note</button><div id="shell-intake" hidden></div><h2>Agent settings</h2><p class="shell-planned">Multi-step and thinking controls: planned for Phase 226.</p><details><summary>Coming later</summary><p>Knowledge pack · Tool loop · Thinking stream</p></details>`;
  sidebar.insertBefore(controls, sidebar.children[1]);
  const selectors = documentRef.querySelector(".chat-workspace-selectors");
  const autonomy = documentRef.querySelector(".chat-autonomy-chip");
  controls.append(selectors, autonomy);
  const toggle = () => {
    documentRef.body.classList.toggle("sidebar-collapsed");
    documentRef.body.classList.remove("navigation-open");
    const open = !documentRef.body.classList.contains("sidebar-collapsed");
    for (const id of ["chat-menu-button", "chat-nav-toggle"]) el(id)?.setAttribute("aria-expanded", String(open));
  };
  // Capture to replace legacy mobile-overlay behavior with a persistent three-pane shell.
  for (const id of ["chat-menu-button", "chat-nav-toggle"]) el(id)?.addEventListener("click", event => {
    event.stopImmediatePropagation(); toggle();
  }, true);
  documentRef.addEventListener("keydown", event => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
    if (event.key.toLowerCase() === "b") { event.preventDefault(); toggle(); }
    if (event.key.toLowerCase() === "n") { event.preventDefault(); el("chat-start").click(); }
  });
  // Existing trace cards contain sanitized observed events; clone inert text, never prompts.
  const updateLog = () => {
    const cards = [...documentRef.querySelectorAll("#chat-history .chat-answer-trace")].slice(-4);
    el("shell-step-log").replaceChildren(...cards.map(card => {
      const row = documentRef.createElement("p"); row.textContent = card.textContent.slice(0, 6000); return row;
    }));
  };
  new windowRef.MutationObserver(updateLog).observe(el("chat-history"), { childList: true, subtree: true, characterData: true });
  const advanced = documentRef.querySelector(".chat-advanced-nav");
  advanced.append(searchLabel);
  for (const link of documentRef.querySelectorAll('a[href^="/ui/"], a[href^="/desktop/"]')) {
    if (link.getAttribute("href") === "/ui/chat") continue;
    link.target = "_blank"; link.rel = "noopener";
  }
  const settingsLink = advanced.querySelector('a[href="/ui/knowledge"]');
  if (settingsLink) settingsLink.textContent = "Brain settings";
  try {
    // Read only same-origin application markup; scripts from the fetched page are never inserted.
    const response = await fetchImpl("/ui/knowledge", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error("Brain controls unavailable. Open Advanced > Brain settings to retry.");
    const parsed = new windowRef.DOMParser().parseFromString(await response.text(), "text/html");
    const source = parsed.querySelector(".brain-page");
    if (!source) throw new Error("Brain controls unavailable.");
    for (const node of source.querySelectorAll("script, nav, #advanced-memory")) node.remove();
    const map = source.querySelector(".brain-map-card");
    if (!map) throw new Error("Brain map unavailable.");
    el("shell-map").replaceChildren(documentRef.adoptNode(map));
    const intake = el("shell-intake"); intake.append(documentRef.adoptNode(source));
    // Keep settings/library controls in their separate Advanced window.
    for (const child of source.children) child.hidden = true;
    const note = el("knowledge-note-form"), upload = el("knowledge-upload-form");
    note.parentElement.hidden = false;
    for (const child of note.parentElement.children) child.hidden = ![note, upload, el("knowledge-state"), el("brain-ingestion-list")].includes(child);
    note.hidden = true; upload.hidden = true;
    const show = form => { intake.hidden = false; note.hidden = form !== note; upload.hidden = form !== upload; };
    el("shell-add-note").addEventListener("click", () => { show(note); el("knowledge-content").focus(); });
    el("shell-feed-file").addEventListener("click", () => { show(upload); el("knowledge-file").click(); });
    el("shell-feed-folder").addEventListener("click", () => { show(upload); el("knowledge-folder").click(); });
    // Retention is shared by the existing intake controller and must remain visible for uploads.
    for (const id of ["knowledge-expiry", "knowledge-consent"]) {
      const field = el(id), label = field.closest("label");
      if (label) intake.prepend(label);
      else { intake.prepend(field); const text = source.querySelector(`label[for="${id}"]`); if (text) intake.prepend(text); }
    }
    await loadKnowledge(); // existing controller auto-mounts once, after its markup is present
  } catch (error) {
    const state = el("shell-brain-state") || el("shell-map"); state.textContent = error.message;
    for (const id of ["shell-feed-file", "shell-feed-folder", "shell-add-note"]) el(id).disabled = true;
  }
}

if (globalThis.document?.querySelector(".chat-app")) void mountPrototypeShell();

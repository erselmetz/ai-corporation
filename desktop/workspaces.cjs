"use strict";

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

// Only existing application pages may open as Advanced windows. No arbitrary URLs.
const ADVANCED_ROUTES = new Set(["/ui/knowledge", "/ui/employees", "/ui/positions", "/ui/structure",
  "/ui/providers", "/ui/visualization", "/ui/tasks", "/ui/workflows", "/ui/workflow-map",
  "/ui/activity", "/ui/inventory", "/ui/readiness", "/ui/backup", "/ui/documentation",
  "/ui/updates", "/ui/preferences", "/ui/settings/capabilities", "/ui/employee-chat", "/ui/login"]);

// Restore identifiers and geometry only. No prompts, credentials, approvals or actions.
function selection(value = {}) {
  if (!value || typeof value !== "object") value = {};
  return Object.fromEntries(["conversation", "agent", "provider", "model", "project"].map(key =>
    [key, typeof value[key] === "string" && /^[\w.:/@ -]{1,160}$/.test(value[key]) ? value[key] : ""]));
}

function reachableBounds(value, area) {
  const width = Math.min(area.width, Math.max(600, Number.isFinite(value?.width) ? value.width : 1440));
  const height = Math.min(area.height, Math.max(620, Number.isFinite(value?.height) ? value.height : 960));
  return { width: Math.floor(width), height: Math.floor(height),
    x: Math.floor(Math.max(area.x, Math.min(area.x + area.width - width, Number.isFinite(value?.x) ? value.x : area.x))),
    y: Math.floor(Math.max(area.y, Math.min(area.y + area.height - height, Number.isFinite(value?.y) ? value.y : area.y))) };
}

function readWorkspaces(file) {
  try {
    if (fs.statSync(file).size > 64 * 1024) return [];
    const data = JSON.parse(fs.readFileSync(file, "utf8"));
    if (data.version !== 1 || !Array.isArray(data.windows)) return [];
    return data.windows.slice(0, 10).filter(item => item?.kind === "chat" || item?.kind === "settings")
      .map(item => ({ id: typeof item.id === "string" && /^[0-9a-f-]{36}$/.test(item.id) ? item.id : undefined,
        kind: item.kind, bounds: item.bounds, selection: selection(item.selection) }));
  } catch { return []; }
}

function createWorkspaceWindows({ BrowserWindow, origin, preload, file, workArea, onCrash = () => {}, onClose = () => {} }) {
  const records = new Map();
  let lastClosed = null;
  let restoring = false;
  let closingAll = false;
  function persist() {
    if (restoring || closingAll) return;
    const windows = [...records.values()].filter(record => !record.window.isDestroyed()).map(record => ({
      id: record.id, kind: record.kind, bounds: record.window.getNormalBounds(), selection: record.selection,
    }));
    if (!windows.length && lastClosed) windows.push(lastClosed);
    try {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file + ".tmp", JSON.stringify({ version: 1, windows: windows.slice(0, 10) }), { mode: 0o600 });
      fs.renameSync(file + ".tmp", file);
    } catch { /* A read-only profile must not crash or loosen access. */ }
  }
  function recordFor(sender) {
    return [...records.values()].find(record => !record.window.isDestroyed() && record.window.webContents === sender);
  }
  function trusted(sender, route = null) {
    const record = recordFor(sender);
    if (!record) return null;
    try {
      const url = new URL(sender.getURL());
      if (url.origin !== origin || (route && !(route.endsWith("/") ? url.pathname.startsWith(route) : url.pathname === route))) return null;
      return record;
    } catch { return null; }
  }
  function create(kind = "chat", saved = {}) {
    if (!["chat", "settings", "advanced"].includes(kind)
      || (kind === "advanced" && !ADVANCED_ROUTES.has(saved.route)) || records.size >= 10) return null;
    if (kind === "settings") {
      const existing = [...records.values()].find(record => record.kind === "settings");
      if (existing) {
        if (existing.window.isMinimized()) existing.window.restore();
        if (existing.window.webContents.getURL() !== `${origin}/desktop/settings/`) existing.window.loadURL(`${origin}/desktop/settings/`);
        existing.window.focus(); return existing.window;
      }
    }
    const window = new BrowserWindow({ ...reachableBounds(saved.bounds, workArea()),
      minWidth: 600, minHeight: 620, show: false, title: "ERSELMETZ AI", autoHideMenuBar: true,
      webPreferences: { preload, nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true } });
    const duplicate = saved.id && [...records.values()].some(record => record.id === saved.id);
    const record = { id: duplicate ? crypto.randomUUID() : saved.id || crypto.randomUUID(),
      kind, window, selection: selection(duplicate ? { ...saved.selection, conversation: "" } : saved.selection) };
    const senderId = window.webContents.id;
    records.set(window.id, record);
    window.webContents.setWindowOpenHandler(({ url: target } = {}) => {
      try {
        const url = new URL(target);
        if (url.origin === origin && ADVANCED_ROUTES.has(url.pathname)) {
          create("advanced", { route: url.pathname });
        }
      } catch { /* Malformed and external destinations remain denied. */ }
      return { action: "deny" };
    });
    window.webContents.on("render-process-gone", (_event, details) => onCrash(details));
    window.webContents.on("will-navigate", (event, target) => {
      try {
        const url = new URL(target);
        if (url.origin !== origin) { event.preventDefault(); return; }
        if (kind === "chat" && ["/desktop/settings", "/ui/settings/capabilities"].includes(url.pathname.replace(/\/$/, ""))) { event.preventDefault(); create("settings"); }
        if (kind === "settings" && url.pathname === "/ui/chat") { event.preventDefault(); create("chat"); }
      } catch { event.preventDefault(); }
    });
    window.webContents.on("before-input-event", (event, input) => {
      if (kind !== "chat" && input.type === "keyDown" && (input.control || input.meta) && !input.alt && input.key.toLowerCase() === "n") {
        event.preventDefault(); create("chat");
      }
    });
    window.once("ready-to-show", () => { if (!window.isDestroyed()) window.show(); });
    for (const event of ["move", "resize"]) window.on(event, persist);
    window.on("close", () => {
      lastClosed = { id: record.id, kind: record.kind, bounds: window.getNormalBounds(), selection: record.selection };
      persist();
    });
    window.on("closed", () => { records.delete(window.id); onClose(senderId); persist(); });
    window.loadURL(`${origin}${kind === "advanced" ? saved.route : kind === "settings" ? "/desktop/settings/" : "/ui/chat?desktop=1"}`);
    persist();
    return window;
  }
  function restore() {
    const saved = readWorkspaces(file);
    restoring = true;
    try {
      // Start in chat even when Settings was the only last open window.
      if (!saved.some(item => item.kind === "chat")) create("chat");
      for (const item of saved) create(item.kind, item);
    } finally { restoring = false; persist(); }
  }
  function update(sender, value) {
    const record = trusted(sender, "/ui/chat");
    if (!record) return false;
    record.selection = selection(value);
    record.window.setTitle(`ERSELMETZ AI · ${record.selection.model || "Default model"} · ${record.selection.agent || "Coordinator"} · ${record.selection.project || "Personal"}`);
    persist();
    return true;
  }
  return { create, restore, trusted, recordFor, update, persist,
    prepareQuit: () => { persist(); closingAll = true; },
    all: () => [...records.values()],
    first: () => [...records.values()].find(record => !record.window.isDestroyed())?.window };
}

module.exports = { selection, reachableBounds, readWorkspaces, createWorkspaceWindows };

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

// Restore identifiers and geometry only. No prompts, credentials, approvals or actions.
function selection(value = {}) {
  if (!value || typeof value !== "object") value = {};
  return Object.fromEntries(["conversation", "agent", "model", "project"].map(key =>
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
      .map(item => ({ kind: item.kind, bounds: item.bounds, selection: selection(item.selection) }));
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
      kind: record.kind, bounds: record.window.getNormalBounds(), selection: record.selection,
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
    const record = { id: crypto.randomUUID(), kind, window, selection: selection(saved.selection) };
    const senderId = window.webContents.id;
    records.set(window.id, record);
    window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    window.webContents.on("render-process-gone", (_event, details) => onCrash(details));
    window.webContents.on("will-navigate", (event, target) => {
      try {
        const url = new URL(target);
        if (url.origin !== origin) { event.preventDefault(); return; }
        if (kind === "chat" && url.pathname.replace(/\/$/, "") === "/desktop/settings") { event.preventDefault(); create("settings"); }
        if (kind === "settings" && url.pathname === "/ui/chat") { event.preventDefault(); create("chat"); }
      } catch { event.preventDefault(); }
    });
    window.webContents.on("before-input-event", (event, input) => {
      if (input.type === "keyDown" && (input.control || input.meta) && !input.alt && input.key.toLowerCase() === "n") {
        event.preventDefault(); create("chat");
      }
    });
    window.once("ready-to-show", () => { if (!window.isDestroyed()) window.show(); });
    for (const event of ["move", "resize"]) window.on(event, persist);
    window.on("close", () => {
      lastClosed = { kind: record.kind, bounds: window.getNormalBounds(), selection: record.selection };
      persist();
    });
    window.on("closed", () => { records.delete(window.id); onClose(senderId); persist(); });
    window.loadURL(`${origin}${kind === "settings" ? "/desktop/settings/" : "/ui/chat?desktop=1"}`);
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
    persist();
    return true;
  }
  return { create, restore, trusted, recordFor, update, persist,
    prepareQuit: () => { persist(); closingAll = true; },
    all: () => [...records.values()],
    first: () => [...records.values()].find(record => !record.window.isDestroyed())?.window };
}

module.exports = { selection, reachableBounds, readWorkspaces, createWorkspaceWindows };

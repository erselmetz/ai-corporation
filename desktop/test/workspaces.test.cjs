const test = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createWorkspaceWindows, reachableBounds, readWorkspaces } = require("../workspaces.cjs");

class Window extends EventEmitter {
  static serial = 0;
  constructor(options) {
    super(); this.id = ++Window.serial; this.options = options; this.url = "";
    this.webContents = new EventEmitter();
    this.webContents.getURL = () => this.url;
    this.webContents.setWindowOpenHandler = handler => { this.openHandler = handler; };
  }
  getNormalBounds() { return this.options; }
  isDestroyed() { return !!this.destroyed; }
  isMinimized() { return false; }
  loadURL(url) { this.url = url; }
  show() { this.shown = true; }
  focus() { this.focused = true; }
  setTitle(title) { this.title = title; }
  close() { this.emit("close"); this.destroyed = true; this.emit("closed"); }
}
function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ersel-windows-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const file = path.join(dir, "workspaces.json");
  const create = () => createWorkspaceWindows({ BrowserWindow: Window, origin: "http://127.0.0.1:8765",
    preload: "/preload.cjs", file, workArea: () => ({ x: 0, y: 0, width: 1280, height: 900 }) });
  return { create, file };
}
test("chat Ctrl+N reaches tabs; explicit new windows share the nonmodal Settings manager", t => {
  const { create } = fixture(t); const manager = create(); manager.restore();
  const first = manager.first(); assert.match(first.url, /\/ui\/chat\?desktop=1$/);
  let prevented = false;
  first.webContents.emit("before-input-event", { preventDefault() { prevented = true; } },
    { type: "keyDown", control: true, key: "n" });
  assert.equal(prevented, false); assert.equal(manager.all().length, 1);
  manager.create("chat");
  const settings = manager.create("settings");
  assert.equal(manager.create("settings"), settings); assert.equal(settings.focused, true);
  assert.equal(settings.options.modal, undefined); assert.equal(manager.all().length, 3);
  assert.equal(first.options.webPreferences.nodeIntegration, false);
  assert.deepEqual(first.openHandler(), { action: "deny" });
});
test("only registered live windows with matching origins and routes are trusted", t => {
  const { create } = fixture(t); const manager = create(); const chat = manager.create();
  assert.ok(manager.trusted(chat.webContents, "/ui/chat"));
  assert.equal(manager.trusted({ getURL: () => chat.url }), null);
  chat.url = "http://127.0.0.1:8765/ui/chat-evil";
  assert.equal(manager.trusted(chat.webContents, "/ui/chat"), null);
  chat.url = "https://example.com/ui/chat";
  assert.equal(manager.update(chat.webContents, { agent: "other" }), false);
  chat.close(); assert.equal(manager.trusted(chat.webContents), null);
});
test("restart restores bounded identifiers and geometry without serializing actions or secrets", t => {
  const { create, file } = fixture(t); const manager = create(); const first = manager.create();
  manager.update(first.webContents, { conversation: "abc123", agent: "researcher", model: "local:3b", project: "p1",
    approval: "approved", prompt: "secret prompt", token: "secret token" });
  manager.create(); manager.create("settings"); manager.prepareQuit();
  for (const record of manager.all()) record.window.close();
  const raw = fs.readFileSync(file, "utf8"); assert.doesNotMatch(raw, /secret|approval|prompt|token/);
  const restored = create(); restored.restore();
  assert.equal(restored.all().length, 3);
  assert.deepEqual(restored.all()[0].selection, { conversation: "abc123", agent: "researcher", provider: "", model: "local:3b", project: "p1" });
  assert.ok(restored.all().every(record => record.window.options.x >= 0));
});
test("invalid stored files recover to chat and offscreen bounds are clamped", t => {
  const { create, file } = fixture(t);
  fs.writeFileSync(file, '{"version":1,"windows":"bad"}');
  assert.deepEqual(readWorkspaces(file), []);
  const manager = create(); manager.restore(); assert.equal(manager.all().length, 1);
  assert.deepEqual(reachableBounds({ x: -9000, y: 99999, width: 99999, height: -1 },
    { x: 0, y: 0, width: 1280, height: 900 }), { x: 0, y: 280, width: 1280, height: 620 });
});
test("chat navigation opens Settings separately and blocks external navigation", t => {
  const { create } = fixture(t); const manager = create(); const chat = manager.create();
  let count = 0; const event = { preventDefault() { count++; } };
  chat.webContents.emit("will-navigate", event, "http://127.0.0.1:8765/desktop/settings/");
  assert.equal(manager.all().length, 2); assert.equal(count, 1);
  chat.webContents.emit("will-navigate", event, "https://example.com"); assert.equal(count, 2);
  const settings = manager.all().find(record => record.kind === "settings").window;
  settings.webContents.emit("will-navigate", event, "http://127.0.0.1:8765/ui/chat");
  assert.equal(manager.all().length, 3);
  assert.match(settings.url, /\/desktop\/settings\/$/);
});

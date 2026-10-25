const test = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { createWorkspaceWindows } = require("../workspaces.cjs");

test("Advanced opens only allowlisted same-origin pages in sandboxed registered windows", t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ersel-shell-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  class Window extends EventEmitter {
    constructor(options) { super(); this.id = Math.random(); this.options = options;
      this.webContents = new EventEmitter(); this.webContents.getURL = () => this.url;
      this.webContents.setWindowOpenHandler = handler => { this.open = handler; }; }
    isDestroyed() { return false; } getNormalBounds() { return this.options; }
    loadURL(url) { this.url = url; }
  }
  const origin = "http://127.0.0.1:8765";
  const manager = createWorkspaceWindows({ BrowserWindow: Window, origin, preload: "preload.cjs",
    file: path.join(dir, "windows.json"), workArea: () => ({ x:0, y:0, width:1200, height:800 }) });
  const chat = manager.create();
  assert.deepEqual(chat.open({ url: origin + "/ui/knowledge" }), { action:"deny" });
  const advanced = manager.all().find(record => record.kind === "advanced").window;
  assert.equal(advanced.url, origin + "/ui/knowledge");
  assert.equal(advanced.options.webPreferences.sandbox, true);
  assert.ok(manager.trusted(advanced.webContents));
  for (const url of ["https://example.com/ui/knowledge", origin + "/api/local/session", "file:///C:/secret", "garbage"])
    assert.deepEqual(chat.open({ url }), { action:"deny" });
  assert.equal(manager.all().length, 2);
  let intercepted = false;
  chat.webContents.emit("before-input-event", { preventDefault() { intercepted = true; } }, {type:"keyDown", control:true, key:"n"});
  assert.equal(intercepted, false, "Ctrl+N reaches the renderer to create a tab");
  assert.equal(manager.create("advanced", { route:"/api/local/session" }), null);
});

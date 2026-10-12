const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (name) => fs.readFileSync(path.join(root, name), "utf8");

test("Windows distribution is per-user, preserves owner data, and has no auto-updater", () => {
  const pkg = JSON.parse(read("package.json"));
  assert.equal(pkg.build.asar, true);
  assert.equal(pkg.build.nsis.oneClick, false);
  assert.equal(pkg.build.nsis.perMachine, false);
  assert.equal(pkg.build.nsis.packElevateHelper, false);
  assert.equal(pkg.build.nsis.deleteAppDataOnUninstall, false);
  assert.equal(pkg.build.win.signAndEditExecutable, false);
  assert.equal("publish" in pkg.build, false);
  assert.equal("electron-updater" in (pkg.dependencies || {}), false);
  assert.equal(pkg.build.nsis.allowToChangeInstallationDirectory, false);
});

test("Electron renderer windows are isolated and navigation stays on owned content", () => {
  const main = read("main.cjs");
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /sandbox:\s*true/);
  assert.match(main, /webSecurity:\s*true/);
  assert.match(main, /setWindowOpenHandler\(\(\) => \(\{ action: "deny" \}\)\)/);
  assert.match(main, /new URL\(target\)\.origin !== ORIGIN/);
  assert.match(main, /shell:\s*false/);
});

test("preload exposes only bounded startup operations, never raw Electron IPC", () => {
  const preload = read("preload.cjs");
  assert.match(preload, /contextBridge\.exposeInMainWorld\("desktopBridge"/);
  assert.match(preload, /ipcRenderer\.invoke\("desktop:get-setup-state"\)/);
  assert.match(preload, /ipcRenderer\.invoke\("desktop:start"/);
  assert.doesNotMatch(preload, /contextBridge\.exposeInMainWorld\("desktopBridge",\s*ipcRenderer/);
  assert.doesNotMatch(preload, /sendSync|\.send\s*\(/);
});

test("static Next export contains only local command-center destinations", () => {
  const config = read("../desktop-ui/next.config.ts");
  const page = read("../desktop-ui/src/app/page.tsx");
  assert.match(config, /output:\s*["']export["']/);
  assert.match(config, /basePath:\s*["']\/desktop["']/);
  assert.match(page, /href:\s*["']\/ui\/chat["']/);
  assert.match(page, /href:\s*["']\/ui\/structure["']/);
  assert.match(page, /href:\s*["']\/ui\/workflow-map["']/);
  assert.doesNotMatch(page, /https?:\/\//);
});

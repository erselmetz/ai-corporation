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
  assert.ok(pkg.build.files.includes("ollama-installer.cjs"));
  assert.ok(fs.existsSync(path.join(root, "ollama-installer.cjs")));
  assert.ok(pkg.build.files.includes("local-diagnostics.cjs"));
  assert.ok(pkg.build.files.includes("local-reset.cjs"));
  assert.equal(pkg.build.nsis.include, "scripts/uninstaller.nsh");
  const uninstaller = read("scripts/uninstaller.nsh");
  assert.match(uninstaller, /MB_DEFBUTTON1/);
  assert.match(uninstaller, /Yes keeps this data/);
  assert.match(uninstaller, /No permanently removes/);
  assert.match(uninstaller, /RMDir \/r "\$LOCALAPPDATA\\ERSELMETZ AI"/);
});

test("Electron renderer windows are isolated and navigation stays on owned content", () => {
  const main = read("main.cjs") + read("workspaces.cjs");
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /sandbox:\s*true/);
  assert.match(main, /webSecurity:\s*true/);
  assert.match(main, /setWindowOpenHandler\(\(\) => \(\{ action: "deny" \}\)\)/);
  assert.match(main, /url\.origin !== origin/);
  assert.match(main, /shell:\s*false/);
});

test("preload exposes only bounded startup operations, never raw Electron IPC", () => {
  const preload = read("preload.cjs");
  assert.match(preload, /contextBridge\.exposeInMainWorld\("desktopBridge"/);
  assert.match(preload, /ipcRenderer\.invoke\("desktop:get-setup-state"\)/);
  assert.match(preload, /ipcRenderer\.invoke\("desktop:start"/);
  assert.match(preload, /requestMicrophone: \(\) => ipcRenderer\.invoke\("desktop:request-microphone"\)/);
  assert.match(preload, /previewOllamaInstaller: \(\) => ipcRenderer\.invoke\("desktop:ollama-installer-preview"\)/);
  assert.match(preload, /installOllama: \(preview\) => ipcRenderer\.invoke\("desktop:ollama-installer-install", preview\)/);
  assert.doesNotMatch(preload, /contextBridge\.exposeInMainWorld\("desktopBridge",\s*ipcRenderer/);
  assert.doesNotMatch(preload, /sendSync|\.send\s*\(/);
  assert.match(preload, /readCrashReports: \(\) => ipcRenderer\.invoke\("desktop:read-crash-reports"\)/);
  assert.match(preload, /openDiagnosticsFolder: \(\) => ipcRenderer\.invoke\("desktop:open-diagnostics-folder"\)/);
  assert.match(preload, /resetAppData: \(\) => ipcRenderer\.invoke\("desktop:reset-app-data"\)/);
});

test("local recovery IPC is app-origin and owner-permission guarded with native reset confirmation", () => {
  const main = read("main.cjs");
  const reports = main.slice(main.indexOf('ipcMain.handle("desktop:read-crash-reports"'), main.indexOf('ipcMain.handle("desktop:open-diagnostics-folder"'));
  const openFolder = main.slice(main.indexOf('ipcMain.handle("desktop:open-diagnostics-folder"'), main.indexOf('ipcMain.handle("desktop:reset-app-data"'));
  const reset = main.slice(main.indexOf('ipcMain.handle("desktop:reset-app-data"'), main.indexOf('const ollamaInstaller'));
  assert.match(reports, /isTrustedApplication\(event\)/);
  assert.match(reports, /ownerHasPermission\("system:read"\)/);
  assert.match(openFolder, /ownerHasPermission\("system:read"\)/);
  assert.match(reset, /ownerHasPermission\("backup:restore"\)/);
  assert.match(reset, /dialog\.showMessageBox/);
  assert.match(reset, /defaultId: 0, cancelId: 0/);
  assert.match(reset, /if \(!await stopBackend\(\)\)/);
  assert.match(reset, /RESET_HELPER_ARGUMENT/);
  assert.match(reset, /app\.exit\(0\)/);
  assert.match(main, /waitForParentAndRemoveAppData\(process\.env\.LOCALAPPDATA, APP_DATA, parentPid\)/);
  const resetModule = read("local-reset.cjs");
  assert.match(resetModule, /path\.basename\(target\).*APP_DATA_DIRECTORY_NAME/i);
  assert.match(resetModule, /target\.toLowerCase\(\) !== expected\.toLowerCase\(\)/);
  assert.match(resetModule, /fs\.rmSync\(target, \{ recursive: true, force: true/);
  assert.match(main, /appendLocalCrashReport\(APP_DATA/);
  const crashHandler = main.slice(main.indexOf("function appendCrashRecord"), main.indexOf("function isTrustedBootstrap"));
  assert.doesNotMatch(crashHandler, /error\.stack|error\.message/);
});

test("Ollama installer bridge is app-origin restricted and presents verified details before execution", () => {
  const main = read("main.cjs");
  const handler = main.slice(main.indexOf('ipcMain.handle("desktop:ollama-installer-install"'));
  assert.match(main, /function isTrustedApplication\(event\)/);
  assert.match(main, /if \(!isTrustedApplication\(event\)\) return \{ ok: false, message: "Request denied\." \};/);
  assert.ok(handler.indexOf("await ollamaInstaller.preview()") < handler.indexOf("await dialog.showMessageBox"));
  assert.ok(handler.indexOf("await dialog.showMessageBox") < handler.indexOf("ollamaInstaller.install(verifiedPreview)"));
  assert.match(handler, /without requesting elevation/);
  assert.match(main, /preload: path\.join\(__dirname, "preload\.cjs"\)/);
});

test("microphone requests need an explicit native confirmation and one-use audio grant", () => {
  const main = read("main.cjs");
  assert.match(main, /title: "Microphone access"/);
  assert.match(main, /buttons: \["Allow once", "Deny"\]/);
  assert.match(main, /permission === "media"/);
  assert.match(main, /details\.mediaTypes\.length === 1 && details\.mediaTypes\[0\] === "audio"/);
  assert.match(main, /microphoneGrants\.delete\(webContents\.id\)/);
  assert.match(main, /callback\(false\)/);
});

test("static Next export contains only local command-center destinations", () => {
  const config = read("../desktop-ui/next.config.ts");
  const shell = read("../desktop-ui/src/app/app-shell.tsx");
  assert.match(config, /output:\s*["']export["']/);
  assert.match(config, /basePath:\s*["']\/desktop["']/);
  for (const destination of ["/ui/chat", "/ui/login", "/ui/projects", "/ui/employees", "/ui/providers"]) {
    assert.ok(shell.includes(`"${destination}"`), `missing command-center destination: ${destination}`);
  }
  assert.doesNotMatch(shell, /https?:\/\//);
});

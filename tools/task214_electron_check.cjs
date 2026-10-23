// Real source-mode Electron/window check, isolated from the owner's app data.
const path = require("node:path");
const fs = require("node:fs");
const { spawn, execFileSync } = require("node:child_process");
const { _electron } = require(path.resolve(__dirname, "../.venv/Lib/site-packages/playwright/driver/package"));

async function run() {
  const root = path.resolve(__dirname, "..");
  const output = path.join(root, "desktop", "task214-review");
  const executablePath = path.join(output, "electron-runtime", "electron.exe");
  if (!fs.existsSync(executablePath)) throw new Error("Verified local Electron runtime is required; this check never downloads it.");
  const env = { ...process.env, LOCALAPPDATA: fs.mkdtempSync(path.join(output, "profile-")),
    ERSELMETZ_PORT: "18874", ERSELMETZ_PYTHON: path.join(root, ".venv", "Scripts", "python.exe") };
  delete env.ELECTRON_RUN_AS_NODE;
  let application;
  const evidence = { runtime: "Electron 44.7.0 source mode; not a packaged installer", checks: [] };
  try {
    application = await _electron.launch({ executablePath, args: [path.join(root, "desktop")], env, timeout: 30000 });
    const first = await application.firstWindow();
    await first.waitForURL("**/ui/chat?desktop=1", { timeout: 30000 });
    await first.locator("#chat-input").waitFor();
    const pid = await application.evaluate(() => process.pid);
    evidence.pid = pid;
    const firstState = await first.evaluate(() => window.desktopBridge.getWorkspaceState());
    if (!firstState?.id) throw new Error("Live chat main frame was not trusted");
    evidence.checks.push({ directChat: !!firstState?.id });
    await first.bringToFront();
    await application.evaluate(({ BrowserWindow }) => {
      const window = BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes("/ui/chat"));
      window.webContents.sendInputEvent({ type: "keyDown", keyCode: "N", modifiers: ["control"] });
      window.webContents.sendInputEvent({ type: "keyUp", keyCode: "N", modifiers: ["control"] });
    });
    await first.waitForTimeout(1500);
    if (application.windows().length !== 2) {
      evidence.windowDebug = await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().map(w => ({ url: w.webContents.getURL(), visible: w.isVisible() })));
      throw new Error("Ctrl+N did not create exactly one new window");
    }
    const second = application.windows().find(page => page !== first);
    await second.waitForURL("**/ui/chat?desktop=1");
    const secondState = await second.evaluate(() => window.desktopBridge.getWorkspaceState());
    if (secondState.id === firstState.id) throw new Error("Window identities were reused");
    evidence.checks.push({ ctrlN: true, separateWindowIds: true });
    await first.evaluate(() => { window.location.href = "/desktop/settings/"; });
    await first.waitForTimeout(1500);
    const settings = application.windows().find(page => page.url().includes("/desktop/settings/"));
    if (!settings || !first.url().includes("/ui/chat")) throw new Error("Settings replaced the chat window");
    await second.evaluate(() => { window.location.href = "/desktop/settings/"; });
    await first.waitForTimeout(500);
    if (application.windows().length !== 3) throw new Error("Settings is not a singleton");
    evidence.checks.push({ settingsSeparateAndSingleton: true });
    const listenerPid = () => execFileSync("powershell.exe", ["-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 18874 -State Listen).OwningProcess"],
      { encoding: "utf8", windowsHide: true }).trim();
    const originalBackendPid = listenerPid();
    const child = spawn(executablePath, [path.join(root, "desktop")], { env, windowsHide: true, stdio: "ignore" });
    await new Promise((resolve, reject) => { child.once("exit", resolve); child.once("error", reject); });
    await first.waitForTimeout(1200);
    if (application.windows().length !== 4) throw new Error("Second launch did not open a new chat window");
    if (await application.evaluate(() => process.pid) !== pid) throw new Error("Main process changed");
    evidence.checks.push({ secondLaunch: true, sameMainProcess: true });
    const backendPid = listenerPid();
    if (!backendPid || backendPid !== originalBackendPid) throw new Error("Second launch changed the backend listener process");
    evidence.backendPid = backendPid;
    await first.screenshot({ path: path.join(output, "chat-window.png") });
    await settings.screenshot({ path: path.join(output, "settings-window.png") });
    await application.close(); application = null;
    const saved = JSON.parse(fs.readFileSync(path.join(env.LOCALAPPDATA, "ERSELMETZ AI", "desktop", "workspaces.json"), "utf8"));
    if (saved.windows.length !== 4) throw new Error("Quit lost open window records");
    application = await _electron.launch({ executablePath, args: [path.join(root, "desktop")], env, timeout: 30000 });
    await application.firstWindow();
    await new Promise(resolve => setTimeout(resolve, 2500));
    if (application.windows().length !== 4) throw new Error("Restart did not restore open workspaces");
    evidence.checks.push({ restartRestoredFourWindows: true });
    evidence.status = "passed";
  } finally {
    if (application) await application.close();
    fs.writeFileSync(path.join(output, "evidence.json"), JSON.stringify(evidence, null, 2));
  }
  console.log(JSON.stringify(evidence, null, 2));
}
run().catch(error => { console.error(error.message); process.exitCode = 1; });

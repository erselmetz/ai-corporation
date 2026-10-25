// Real source-mode Electron/window check, isolated from the owner's app data.
const path = require("node:path");
const fs = require("node:fs");
const { spawn, execFileSync } = require("node:child_process");
const { _electron } = require(path.resolve(__dirname, "../.venv/Lib/site-packages/playwright/driver/package"));

async function run() {
  const root = path.resolve(__dirname, "..");
  const workspaceCheck = process.argv.includes("--workspaces");
  const output = path.join(root, "desktop", workspaceCheck ? "task215-review" : "task214-review");
  fs.mkdirSync(output, { recursive: true });
  const executablePath = path.join(root, "desktop", "task214-review", "electron-runtime", "electron.exe");
  if (!fs.existsSync(executablePath)) throw new Error("Verified local Electron runtime is required; this check never downloads it.");
  const env = { ...process.env, LOCALAPPDATA: fs.mkdtempSync(path.join(output, "profile-")),
    ERSELMETZ_PORT: "18874", ERSELMETZ_PYTHON: path.join(root, ".venv", "Scripts", "python.exe") };
  delete env.ELECTRON_RUN_AS_NODE;
  let application;
  const evidence = { runtime: "Electron 44.7.0 source mode; not a packaged installer", checks: [] };
  let fixtureProjects = [];
  if (workspaceCheck) {
    const data = path.join(env.LOCALAPPDATA, "ERSELMETZ AI"); fs.mkdirSync(data, { recursive: true });
    fixtureProjects = JSON.parse(execFileSync(env.ERSELMETZ_PYTHON, ["-c", [
      "from app.runtime.factory import create_corporation_runtime",
      "import json", "runtime = create_corporation_runtime()",
      "service = runtime.application_service",
      "projects = [service.create_project('Review Alpha'), service.create_project('Review Beta')]",
      "service.chat_workspaces().save_brief('local-owner', projects[0].id, 'Use concise answers for Review Alpha.')",
      "print(json.dumps([project.id for project in projects]))",
    ].join("\n")], { cwd: data, env: { ...env, PYTHONPATH: root }, encoding: "utf8", windowsHide: true }));
    evidence.fixtureProjects = fixtureProjects;
  }
  try {
    application = await _electron.launch({ executablePath, args: [path.join(root, "desktop")], env, timeout: 30000 });
    const first = await application.firstWindow();
    await first.waitForURL("**/ui/chat?desktop=1", { timeout: 30000 });
    await first.locator("#chat-input").waitFor();
    if (workspaceCheck) await first.waitForFunction(() => document.getElementById("chat-input")?.disabled === false, { timeout: 30000 });
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
    if (workspaceCheck) {
      await second.waitForFunction(() => document.getElementById("chat-input")?.disabled === false, { timeout: 30000 });
      await first.locator("#workspace-project").selectOption(fixtureProjects[0]);
      await first.waitForFunction(project => document.getElementById("chat-input")?.disabled === false
        && document.getElementById("workspace-project")?.value === project, fixtureProjects[0]);
      await second.locator("#workspace-project").selectOption(fixtureProjects[1]);
      await second.waitForFunction(project => document.getElementById("chat-input")?.disabled === false
        && document.getElementById("workspace-project")?.value === project, fixtureProjects[1]);
      const one = await first.evaluate(() => window.desktopBridge.getWorkspaceState());
      const two = await second.evaluate(() => window.desktopBridge.getWorkspaceState());
      if (!one.conversation || !two.conversation || one.conversation === two.conversation) throw new Error("Conversations were shared across windows");
      const crossStatus = await second.evaluate(async value => (await fetch(`/api/chat/conversations/${value.conversation}`,
        { headers: { "X-Chat-Workspace": value.workspace } })).status, { conversation: one.conversation, workspace: two.id });
      if (crossStatus !== 404) throw new Error("Cross-window conversation access was not denied");
      evidence.checks.push({ separateProjects: true, crossWindowAccessDenied: true, separateConversations: true });
      await first.screenshot({ path: path.join(output, "workspace-alpha.png") });
      await second.screenshot({ path: path.join(output, "workspace-beta.png") });
    }
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
    if (application) {
      if (!evidence.status) {
        evidence.uiFailure = [];
        for (const page of application.windows()) {
          evidence.uiFailure.push(await page.evaluate(() => ({ url: location.pathname,
            state: document.getElementById("chat-state")?.textContent,
            inputDisabled: document.getElementById("chat-input")?.disabled,
            agent: document.getElementById("chat-agent")?.value })));
          await page.screenshot({ path: path.join(output, `failure-${evidence.uiFailure.length}.png`) });
        }
      }
      await application.close();
    }
    fs.writeFileSync(path.join(output, "evidence.json"), JSON.stringify(evidence, null, 2));
  }
  console.log(JSON.stringify(evidence, null, 2));
}
run().catch(error => { console.error(error.message); process.exitCode = 1; });

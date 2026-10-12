const { app, BrowserWindow, dialog, ipcMain, session } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const { fileURLToPath } = require("node:url");

const HOST = "127.0.0.1";
const PORT = 8765;
const ORIGIN = `http://${HOST}:${PORT}`;
const APP_DATA = path.join(process.env.LOCALAPPDATA || app.getPath("userData"), "ERSELMETZ AI");
const CREDENTIAL = path.join(APP_DATA, "owner-credential.dpapi");
let bootstrapWindow;
let applicationWindow;
let backend;
let quitAfterShutdown = false;
let quitting = false;
let microphoneGrantUntil = 0;

app.setName("ERSELMETZ AI");
app.setPath("userData", path.join(APP_DATA, "desktop"));
const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) app.quit();

function isTrustedBootstrap(event) {
  if (!bootstrapWindow || event.sender !== bootstrapWindow.webContents) return false;
  try {
    const actual = new URL(event.sender.getURL());
    if (actual.protocol !== "file:") return false;
    return path.resolve(fileURLToPath(actual)).toLowerCase()
      === path.resolve(path.join(__dirname, "bootstrap.html")).toLowerCase();
  } catch { return false; }
}

function makeBootstrapWindow() {
  bootstrapWindow = new BrowserWindow({
    width: 590, height: 620, minWidth: 480, minHeight: 520, show: false,
    title: "ERSELMETZ AI — Local setup",
    autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true },
  });
  bootstrapWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  bootstrapWindow.webContents.on("will-navigate", (event, target) => {
    if (target !== require("node:url").pathToFileURL(path.join(__dirname, "bootstrap.html")).href) event.preventDefault();
  });
  bootstrapWindow.loadFile(path.join(__dirname, "bootstrap.html"));
  bootstrapWindow.once("ready-to-show", () => bootstrapWindow && bootstrapWindow.show());
  bootstrapWindow.on("closed", () => { bootstrapWindow = undefined; if (!backend && !applicationWindow) app.quit(); });
}

function spawnBackend() {
  if (app.isPackaged) {
    return spawn(path.join(process.resourcesPath, "backend", "erselmetz-backend.exe"), ["--port", String(PORT), "--ui-dir", path.join(process.resourcesPath, "desktop-ui")], {
      cwd: APP_DATA,
      windowsHide: true,
      shell: false,
      stdio: ["pipe", "pipe", "ignore"],
      env: safeBackendEnvironment(),
    });
  }
  const repository = path.resolve(__dirname, "..");
  const python = process.env.ERSELMETZ_PYTHON || path.join(repository, ".venv", "Scripts", "python.exe");
  return spawn(python, ["-m", "app.desktop_runtime", "--port", String(PORT), "--ui-dir", path.resolve(repository, "desktop-ui", "out")], {
    cwd: APP_DATA,
    windowsHide: true,
    shell: false,
    stdio: ["pipe", "pipe", "ignore"],
    env: { ...safeBackendEnvironment(), PATH: process.env.PATH, PYTHONPATH: repository },
  });
}

function handleChildErrors(child) {
  child.stdin.on("error", () => {});
}

function safeBackendEnvironment() {
  const env = {};
  for (const key of ["LOCALAPPDATA", "APPDATA", "USERPROFILE", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"]) {
    if (process.env[key]) env[key] = process.env[key];
  }
  return env;
}

function healthCheck() {
  return new Promise((resolve) => {
    const request = http.get(`${ORIGIN}/health`, { timeout: 700 }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { if (body.length < 256) body += chunk; });
      response.on("end", () => resolve(response.statusCode === 200 && body === '{"status":"ok"}'));
    });
    request.on("timeout", () => request.destroy());
    request.on("error", () => resolve(false));
  });
}

async function waitForBackend(child, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  let output = "";
  let spawnFailed = false;
  const readiness = new Promise((resolve) => {
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      output = (output + chunk).slice(-256);
      for (const line of output.split(/\r?\n/)) {
        if (line === `ERSELMETZ_READY:${PORT}`) resolve(true);
      }
    });
    child.once("error", () => { spawnFailed = true; resolve(false); });
    child.once("exit", () => resolve(false));
  });
  let ready = false;
  while (Date.now() < deadline) {
    if (spawnFailed) return false;
    if (child.exitCode !== null) return false;
    if (!ready) ready = await Promise.race([readiness, new Promise((resolve) => setTimeout(() => resolve(false), 100))]);
    if (ready) return await healthCheck();
    await new Promise((resolve) => setTimeout(resolve, 180));
  }
  return false;
}

function showStartup(message) {
  if (bootstrapWindow && !bootstrapWindow.isDestroyed()) bootstrapWindow.webContents.send("desktop:startup-state", message);
}

async function startBackend(payload) {
  if (backend) return { started: false, message: "The local service is already running." };
  if (typeof payload?.password !== "string" || payload.password.length < 12 || payload.password.length > 1024) {
    return { started: false, message: "Owner password must contain 12 to 1024 characters." };
  }
  if (typeof payload?.confirmation !== "string" || payload.confirmation.length > 1024) {
    return { started: false, message: "The password confirmation is invalid." };
  }
  const isFirstRun = !fs.existsSync(CREDENTIAL);
  if (isFirstRun && payload.password !== payload.confirmation) return { started: false, message: "The password entries do not match." };
  if (!isFirstRun && payload.confirmation) return { started: false, message: "Enter only the saved owner password." };
  showStartup("Preparing the protected local owner credential…");
  let child;
  try {
    fs.mkdirSync(APP_DATA, { recursive: true });
    child = spawnBackend();
    backend = child;
    handleChildErrors(child);
    child.once("exit", () => { if (backend === child) backend = null; });
    child.stdin.write(`${JSON.stringify({ password: payload.password, confirmation: payload.confirmation })}\n`);
    payload.password = "";
    payload.confirmation = "";
    showStartup("Starting private services on this computer…");
    if (!await waitForBackend(child)) {
      child.stdin.end();
      await new Promise((resolve) => {
        if (child.exitCode !== null) resolve();
        else { child.once("exit", resolve); setTimeout(resolve, 5000); }
      });
      if (backend === child && child.exitCode !== null) backend = null;
      if (bootstrapWindow && !bootstrapWindow.isDestroyed()) showStartup("The service did not become ready. Close another ERSELMETZ AI controller and retry.");
      return { started: false, message: "Local startup failed. Check that another ERSELMETZ AI controller is closed, then retry." };
    }
    createApplicationWindow();
    if (bootstrapWindow && !bootstrapWindow.isDestroyed()) bootstrapWindow.close();
    return { started: true };
  } catch {
    payload.password = "";
    payload.confirmation = "";
    if (child && child.stdin && !child.stdin.destroyed) child.stdin.end();
    if (backend === child) backend = null;
    return { started: false, message: "Local startup failed. Check the installation and retry." };
  }
}

function createApplicationWindow() {
  applicationWindow = new BrowserWindow({
    width: 1440, height: 960, minWidth: 850, minHeight: 620, show: false,
    title: "ERSELMETZ AI — Command Center",
    autoHideMenuBar: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true },
  });
  applicationWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  applicationWindow.webContents.on("will-navigate", (event, target) => {
    try { if (new URL(target).origin !== ORIGIN) event.preventDefault(); }
    catch { event.preventDefault(); }
  });
  applicationWindow.loadURL(`${ORIGIN}/desktop/`);
  applicationWindow.once("ready-to-show", () => applicationWindow && applicationWindow.show());
  applicationWindow.on("closed", () => { applicationWindow = undefined; app.quit(); });
}

function stopBackend() {
  const child = backend;
  if (!child) return Promise.resolve(true);
  return new Promise((resolve) => {
    let finished = false;
    const done = (ok) => { if (finished) return; finished = true; clearTimeout(timer); resolve(ok); };
    const timer = setTimeout(() => done(false), 10000);
    child.once("exit", () => done(true));
    if (!child.stdin.destroyed) child.stdin.write('{"command":"shutdown"}\n', (error) => { if (error) done(false); });
  });
}

if (hasSingleInstanceLock) app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback, details) => {
    const trusted = applicationWindow && webContents === applicationWindow.webContents
      && webContents.getURL().startsWith(`${ORIGIN}/`);
    const audioOnly = permission === "media" && Array.isArray(details?.mediaTypes)
      && details.mediaTypes.length === 1 && details.mediaTypes[0] === "audio";
    if (trusted && audioOnly && Date.now() < microphoneGrantUntil) {
      microphoneGrantUntil = 0;
      callback(true);
      return;
    }
    callback(false);
  });
  ipcMain.handle("desktop:get-setup-state", (event) => isTrustedBootstrap(event) && !fs.existsSync(CREDENTIAL));
  ipcMain.handle("desktop:start", (event, payload) => isTrustedBootstrap(event) ? startBackend(payload) : { started: false, message: "Request denied." });
  ipcMain.handle("desktop:request-microphone", async (event) => {
    const frame = event.senderFrame;
    if (!applicationWindow || event.sender !== applicationWindow.webContents
        || !event.sender.getURL().startsWith(`${ORIGIN}/`)
        || !frame || !frame.isMainFrame || !frame.url.startsWith(`${ORIGIN}/`)) return false;
    const result = await dialog.showMessageBox(applicationWindow, {
      type: "question", buttons: ["Allow once", "Deny"], defaultId: 1, cancelId: 1,
      title: "Microphone access",
      message: "Allow microphone access for this voice interaction?",
      detail: "Audio is used only for the interaction you start. Local mode keeps recognition on this device; Gemini mode sends the recording only after separate per-use consent.",
    });
    if (result.response !== 0) return false;
    microphoneGrantUntil = Date.now() + 15_000;
    return true;
  });
  makeBootstrapWindow();
});

app.on("second-instance", () => {
  const window = applicationWindow || bootstrapWindow;
  if (window) { if (window.isMinimized()) window.restore(); window.focus(); }
});

app.on("before-quit", (event) => {
  if (quitting || !backend) return;
  event.preventDefault();
  if (quitAfterShutdown) return;
  quitAfterShutdown = true;
  stopBackend().then(async (stopped) => {
    if (!stopped) {
      quitAfterShutdown = false;
      const options = { type: "warning", buttons: ["Keep app open"], title: "Service is still stopping", message: "The local service has not stopped yet. Keep the app open and try closing it again after it finishes." };
      const ownerWindow = applicationWindow || bootstrapWindow;
      if (ownerWindow) await dialog.showMessageBox(ownerWindow, options);
      else await dialog.showMessageBox(options);
      return;
    }
    await session.defaultSession.clearStorageData({ storages: ["cookies"] });
    quitting = true;
    app.quit();
  });
});

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });

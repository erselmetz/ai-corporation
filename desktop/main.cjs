const { app, BrowserWindow, desktopCapturer, dialog, ipcMain, session, shell, screen } = require("electron");
const { spawn, execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const crypto = require("node:crypto");
const { fileURLToPath } = require("node:url");
const { createWorkspaceWindows } = require("./workspaces.cjs");
const { createDisplayMediaRequestHandler } = require("./screen-capture.cjs");
const { OllamaInstaller } = require("./ollama-installer.cjs");
const { appendLocalCrashReport, readLocalCrashReports } = require("./local-diagnostics.cjs");
const { RESET_HELPER_ARGUMENT, resolveAppDataDirectory, waitForParentAndRemoveAppData } = require("./local-reset.cjs");

const HOST = "127.0.0.1";
const PORT = (() => {
  const configured = process.env.ERSELMETZ_PORT;
  const value = configured === undefined ? 8765 : Number(configured);
  if (!Number.isInteger(value) || value < 1024 || value > 65535) {
    throw new Error("ERSELMETZ_PORT must be a valid unprivileged TCP port.");
  }
  return value;
})();
const ORIGIN = `http://${HOST}:${PORT}`;
const APP_DATA = process.env.LOCALAPPDATA
  ? resolveAppDataDirectory(process.env.LOCALAPPDATA)
  : path.join(app.getPath("userData"), "ERSELMETZ AI");
const CREDENTIAL = path.join(APP_DATA, "owner-credential.dpapi");
let bootstrapWindow;
const workspaceWindows = createWorkspaceWindows({ BrowserWindow, origin: ORIGIN,
  preload: path.join(__dirname, "preload.cjs"), file: path.join(APP_DATA, "desktop", "workspaces.json"),
  workArea: () => screen.getPrimaryDisplay().workArea,
  onClose: senderId => { microphoneGrants.delete(senderId); cameraGrants.delete(senderId); },
  onCrash: details => {
    const reasons = new Set(["clean-exit", "abnormal-exit", "killed", "crashed", "oom", "launch-failed", "integrity-failure"]);
    appendCrashRecord("renderer", "renderer-gone", reasons.has(details?.reason) ? details.reason : "unknown",
      Number.isInteger(details?.exitCode) ? Math.max(-1, Math.min(255, details.exitCode)) : null);
  },
});
let backend;
let expectedBackendCommit = null;
let quitAfterShutdown = false;
let quitting = false;
const microphoneGrants = new Map();
const cameraGrants = new Map();

function resetHelperMode() {
  const marker = process.argv.indexOf(RESET_HELPER_ARGUMENT);
  if (marker < 0) return false;
  const parentPid = Number(process.argv[marker + 1]);
  process.stdout.write("RESET_HELPER_READY\n");
  void (async () => {
    try {
      if (!process.env.LOCALAPPDATA || !Number.isInteger(parentPid) || parentPid <= 0) { app.exit(2); return; }
      const removed = await waitForParentAndRemoveAppData(process.env.LOCALAPPDATA, APP_DATA, parentPid);
      if (!removed) { app.exit(3); return; }
      const args = app.isPackaged ? [] : [path.resolve(__dirname, "..")];
      const relaunched = spawn(process.execPath, args, { detached: true, windowsHide: true, stdio: "ignore", shell: false });
      const started = await new Promise((resolve) => {
        relaunched.once("spawn", () => resolve(true));
        relaunched.once("error", () => resolve(false));
      });
      if (!started) { app.exit(4); return; }
      relaunched.unref();
      app.exit(0);
    } catch { app.exit(5); }
  })();
  return true;
}

function ollamaInstallationPresent() {
  const roots = [process.env.LOCALAPPDATA, process.env.ProgramFiles, process.env["ProgramFiles(x86)"]].filter(Boolean);
  return roots.some((root) => [path.join(root, "Programs", "Ollama", "ollama.exe"), path.join(root, "Ollama", "ollama.exe")]
    .some((candidate) => { try { return fs.statSync(candidate).isFile(); } catch { return false; } }));
}

const isResetHelper = resetHelperMode();
if (!isResetHelper) {
  app.setName("ERSELMETZ AI");
  app.setPath("userData", path.join(APP_DATA, "desktop"));
}
const hasSingleInstanceLock = isResetHelper ? false : app.requestSingleInstanceLock();
if (!isResetHelper && !hasSingleInstanceLock) app.quit();

function appendCrashRecord(source, event, reason = "unknown", exitCode = null) {
  try {
    appendLocalCrashReport(APP_DATA, { source, event, reason, exitCode, appVersion: require("./package.json").version });
  } catch { /* diagnostics must never prevent normal shutdown or recovery */ }
}

if (!isResetHelper) {
  process.on("uncaughtException", () => {
    appendCrashRecord("main", "uncaught-exception");
    app.quit();
  });
  process.on("unhandledRejection", () => {
    appendCrashRecord("main", "unhandled-rejection");
    app.quit();
  });
}

function isTrustedBootstrap(event) {
  if (!bootstrapWindow || event.sender !== bootstrapWindow.webContents) return false;
  try {
    const actual = new URL(event.sender.getURL());
    if (actual.protocol !== "file:") return false;
    return path.resolve(fileURLToPath(actual)).toLowerCase()
      === path.resolve(path.join(__dirname, "bootstrap.html")).toLowerCase();
  } catch { return false; }
}

function isTrustedApplication(event) {
  return Boolean(event.senderFrame === event.sender.mainFrame
    && workspaceWindows.trusted(event.sender, "/desktop/"));
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
  bootstrapWindow.on("closed", () => { bootstrapWindow = undefined; if (!backend && !workspaceWindows.first()) app.quit(); });
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
  const version = require("./package.json").version;
  let commit = "development";
  try {
    if (app.isPackaged) {
      const stamp = JSON.parse(fs.readFileSync(path.join(process.resourcesPath, "backend", "build-stamp.json"), "utf8"));
      if (stamp.version !== version || typeof stamp.commit !== "string" || !/^[0-9a-f]{7,64}$/i.test(stamp.commit)) {
        throw new Error("Backend build stamp does not match this desktop package");
      }
      commit = stamp.commit.toLowerCase();
    } else {
      commit = execFileSync("git", ["rev-parse", "--short=12", "HEAD"], {
        cwd: path.resolve(__dirname, ".."), encoding: "utf8", timeout: 1000,
        windowsHide: true, stdio: ["ignore", "pipe", "ignore"],
      }).trim();
      if (!/^[0-9a-f]{7,64}$/i.test(commit)) commit = "development";
    }
  } catch {
    if (app.isPackaged) throw new Error("The packaged backend build identity is missing or invalid.");
  }
  expectedBackendCommit = commit.toLowerCase();
  const env = { ERSELMETZ_APP_VERSION: version, ERSELMETZ_BUILD_COMMIT: commit };
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
      response.on("end", () => {
        try {
          const health = JSON.parse(body);
          resolve(response.statusCode === 200 && health?.status === "ok"
            && health.version === require("./package.json").version
            && typeof health.commit === "string"
            && health.commit.toLowerCase() === expectedBackendCommit);
        } catch { resolve(false); }
      });
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

async function ownerHasPermission(permission) {
  try {
    const cookies = await session.defaultSession.cookies.get({ url: ORIGIN });
    if (!cookies.some((cookie) => cookie.name === "ersel_local_session" && typeof cookie.value === "string" && cookie.value.length > 0)) return false;
    const cookieHeader = cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");
    return await new Promise((resolve) => {
      const request = http.get(`${ORIGIN}/api/local/session`, {
        headers: { Accept: "application/json", Origin: ORIGIN, Cookie: cookieHeader }, timeout: 2500,
      }, (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          if (body.length < 8192) body += chunk.slice(0, 8192 - body.length);
          else request.destroy();
        });
        response.on("end", () => {
          try {
            const result = JSON.parse(body);
            resolve(response.statusCode === 200 && Array.isArray(result.permissions) && result.permissions.includes(permission));
          } catch { resolve(false); }
        });
      });
      request.on("timeout", () => request.destroy());
      request.on("error", () => resolve(false));
    });
  } catch { return false; }
}

function showStartup(message) {
  if (bootstrapWindow && !bootstrapWindow.isDestroyed()) bootstrapWindow.webContents.send("desktop:startup-state", message);
}

async function startBackend(payload) {
  if (backend) return { started: false, message: "The local service is already running." };
  const isFirstRun = !fs.existsSync(CREDENTIAL);
  if (isFirstRun && payload?.password != null && payload.password !== "") return { started: false, message: "A new app starts without a password. Add an optional lock in Settings." };
  if (!isFirstRun && (typeof payload?.password !== "string" || payload.password.length < 12 || payload.password.length > 1024)) return { started: false, message: "Enter the saved owner password." };
  const startupToken = crypto.randomBytes(32).toString("base64url");
  showStartup("Preparing the protected local owner credential…");
  let ownerPassword = isFirstRun ? null : payload.password;
  let child;
  try {
    fs.mkdirSync(APP_DATA, { recursive: true });
    child = spawnBackend();
    backend = child;
    handleChildErrors(child);
    child.once("exit", (code, signal) => {
      if (backend === child) backend = null;
      if (!quitting && (signal || (code !== null && code !== 0))) {
        appendCrashRecord("backend", "backend-exit", signal ? "killed" : "abnormal-exit",
          Number.isInteger(code) ? Math.max(-1, Math.min(255, code)) : null);
      }
    });
    child.stdin.write(`${JSON.stringify({ password: ownerPassword, confirmation: null, first_owner_run: isFirstRun, session_token: startupToken })}\n`);
    if (payload) { payload.password = ""; payload.confirmation = ""; }
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
    // The backend has already verified any configured password before it starts.
    // Install only the fresh per-launch token as the HttpOnly renderer session.
    await session.defaultSession.cookies.set({ url: ORIGIN, name: "ersel_local_session", value: startupToken, path: "/", httpOnly: true, sameSite: "strict" });
    ownerPassword = "";
    workspaceWindows.restore();
    if (bootstrapWindow && !bootstrapWindow.isDestroyed()) bootstrapWindow.close();
    return { started: true };
  } catch {
    ownerPassword = "";
    if (payload) { payload.password = ""; payload.confirmation = ""; }
    if (child && child.stdin && !child.stdin.destroyed) child.stdin.end();
    if (backend === child) backend = null;
    return { started: false, message: "Local startup failed. Check the installation and retry." };
  }
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
    const trusted = Boolean(workspaceWindows.trusted(webContents));
    const audioOnly = permission === "media" && Array.isArray(details?.mediaTypes)
      && details.mediaTypes.length === 1 && details.mediaTypes[0] === "audio";
    const videoOnly = permission === "media" && Array.isArray(details?.mediaTypes)
      && details.mediaTypes.length === 1 && details.mediaTypes[0] === "video";
    const displayCapture = trusted && permission === "display-capture"
      && webContents.getURL().startsWith(`${ORIGIN}/ui/chat`);
    if (displayCapture) {
      callback(true);
      return;
    }
    if (trusted && audioOnly && Date.now() < (microphoneGrants.get(webContents.id) || 0)) {
      microphoneGrants.delete(webContents.id);
      callback(true);
      return;
    }
    if (trusted && videoOnly && webContents.getURL().startsWith(`${ORIGIN}/ui/chat`)
        && Date.now() < (cameraGrants.get(webContents.id) || 0)) {
      cameraGrants.delete(webContents.id);
      callback(true);
      return;
    }
    callback(false);
  });
  session.defaultSession.setDisplayMediaRequestHandler(
    createDisplayMediaRequestHandler({
      isTrusted: (request) => Boolean(
        request.securityOrigin === ORIGIN
        && workspaceWindows.all().some(record => record.kind === "chat"
          && request?.frame === record.window.webContents.mainFrame
          && workspaceWindows.trusted(record.window.webContents, "/ui/chat"))
      ),
      getSources: () => desktopCapturer.getSources({
        types: ["screen", "window"],
        thumbnailSize: { width: 80, height: 45 },
        fetchWindowIcons: false,
      }),
      chooseSource: async (sources, request) => {
        const applicationWindow = workspaceWindows.all().find(record => request?.frame === record.window.webContents.mainFrame)?.window;
        if (sources.length > 24 || !applicationWindow || applicationWindow.isDestroyed()) return null;
        const buttons = [...sources.map((source) => source.name.slice(0, 120)), "Cancel"];
        const cancelId = buttons.length - 1;
        const result = await dialog.showMessageBox(applicationWindow, {
          type: "question",
          title: "Capture one screen frame",
          message: "Choose one display or window to capture.",
          detail: "The app captures one image frame without audio, then immediately stops capture. The image is attached to the open chat and is not sent to an AI Provider.",
          buttons,
          defaultId: cancelId,
          cancelId,
          noLink: true,
        });
        return result.response < sources.length ? sources[result.response] : null;
      },
    })
  );
  ipcMain.handle("desktop:workspace-state", (event) => {
    if (!event.senderFrame === event.sender.mainFrame) return null;
    const record = workspaceWindows.trusted(event.sender, "/ui/chat");
    return record ? { id: record.id, ...record.selection } : null;
  });
  ipcMain.handle("desktop:workspace-save", (event, value) =>
    Boolean(event.senderFrame === event.sender.mainFrame && workspaceWindows.update(event.sender, value)));
  ipcMain.handle("desktop:get-setup-state", (event) => isTrustedBootstrap(event) && !fs.existsSync(CREDENTIAL));
  ipcMain.handle("desktop:ollama-installed", (event) => isTrustedApplication(event) && ollamaInstallationPresent());
  ipcMain.handle("desktop:start", (event, payload) => isTrustedBootstrap(event) ? startBackend(payload) : { started: false, message: "Request denied." });
  ipcMain.handle("desktop:read-crash-reports", (event) => {
    if (!isTrustedApplication(event)) return { ok: false, message: "Request denied.", reports: [] };
    return ownerHasPermission("system:read").then((allowed) => allowed
      ? { ok: true, localOnly: true, reports: readLocalCrashReports(APP_DATA) }
      : { ok: false, message: "Sign in with system:read permission to inspect local reports.", reports: [] });
  });
  ipcMain.handle("desktop:open-diagnostics-folder", async (event) => {
    if (!isTrustedApplication(event)) return { ok: false, message: "Request denied." };
    if (!await ownerHasPermission("system:read")) return { ok: false, message: "Sign in with system:read permission to open local diagnostics." };
    try {
      const directory = path.join(APP_DATA, "diagnostics");
      fs.mkdirSync(directory, { recursive: true });
      const error = await shell.openPath(directory);
      return error ? { ok: false, message: "The local diagnostics folder could not be opened." } : { ok: true };
    } catch { return { ok: false, message: "The local diagnostics folder could not be opened." }; }
  });
  ipcMain.handle("desktop:reset-app-data", async (event) => {
    if (!isTrustedApplication(event)) return { ok: false, message: "Request denied." };
    if (!process.env.LOCALAPPDATA) return { ok: false, message: "Full app-data reset is supported only for the Windows per-user installation." };
    if (!await ownerHasPermission("backup:restore")) return { ok: false, message: "Sign in with backup:restore permission to reset application data." };
    const confirmation = await dialog.showMessageBox(BrowserWindow.fromWebContents(event.sender), {
      type: "warning", buttons: ["Cancel", "Reset app data"], defaultId: 0, cancelId: 0,
      title: "Reset all ERSELMETZ AI data?",
      message: "This removes the local owner account and all ERSELMETZ AI application data.",
      detail: "This permanently removes the local database, owner credential, conversations, backups, update installers, and local diagnostic reports. It cannot be undone. Choose Cancel to keep the data. The app will close and reopen at first-run setup.",
      noLink: true,
    });
    if (confirmation.response !== 1) return { ok: false, canceled: true, message: "App data was kept." };
    if (!await stopBackend()) return { ok: false, message: "The local service did not stop safely. Data was kept; close the app after it finishes and retry." };
    try { await session.defaultSession.clearStorageData(); }
    catch { return { ok: false, message: "The owner session could not be cleared. Data was kept." }; }
    let helper;
    try {
      const helperArgs = app.isPackaged
        ? [RESET_HELPER_ARGUMENT, String(process.pid)]
        : [path.resolve(__dirname, ".."), RESET_HELPER_ARGUMENT, String(process.pid)];
      helper = spawn(process.execPath, helperArgs, { detached: true, windowsHide: true, stdio: ["ignore", "pipe", "ignore"], shell: false });
    } catch { return { ok: false, message: "Reset helper could not be started. Data was kept." }; }
    const ready = await new Promise((resolve) => {
      let output = "";
      const timeout = setTimeout(() => resolve(false), 3000);
      helper.stdout.setEncoding("utf8");
      helper.stdout.on("data", (chunk) => {
        output = (output + chunk).slice(-80);
        if (output.includes("RESET_HELPER_READY")) { clearTimeout(timeout); resolve(true); }
      });
      helper.once("error", () => { clearTimeout(timeout); resolve(false); });
      helper.once("exit", () => { clearTimeout(timeout); resolve(false); });
    });
    if (!ready) { try { helper.kill(); } catch {} return { ok: false, message: "Reset helper did not become ready. Data was kept." }; }
    helper.unref();
    quitting = true;
    app.exit(0);
    return { ok: true, restarting: true };
  });
  const ollamaInstaller = new OllamaInstaller({
    onProgress: (progress) => {
      for (const record of workspaceWindows.all()) record.window.webContents.send("desktop:ollama-installer-progress", progress);
    },
  });
  ipcMain.handle("desktop:ollama-installer-preview", async (event) => {
    if (!isTrustedApplication(event)) return { ok: false, message: "Request denied." };
    try { return { ok: true, preview: await ollamaInstaller.preview() }; }
    catch { return { ok: false, message: "Official Ollama installer metadata or integrity data is unavailable. No installer was downloaded." }; }
  });
  ipcMain.handle("desktop:ollama-installer-install", async (event, preview) => {
    if (!isTrustedApplication(event)) return { ok: false, message: "Request denied." };
    if (!preview || typeof preview !== "object") return { ok: false, message: "Installer review is unavailable." };
    let verifiedPreview;
    try {
      verifiedPreview = await ollamaInstaller.preview();
      if (preview.version !== verifiedPreview.version || preview.source !== verifiedPreview.source
          || preview.size_bytes !== verifiedPreview.size_bytes || preview.sha256 !== verifiedPreview.sha256) {
        return { ok: false, message: "The Ollama release changed. Refresh and review the new installer details." };
      }
    } catch { return { ok: false, message: "Current official Ollama release integrity metadata is unavailable." }; }
    const result = await dialog.showMessageBox(BrowserWindow.fromWebContents(event.sender), {
      type: "warning", buttons: ["Download and run verified installer", "Cancel"], defaultId: 1, cancelId: 1,
      title: "Install Ollama for this user",
      message: `Download and run Ollama ${verifiedPreview.version}?`,
      detail: `Source: ${verifiedPreview.source}\nSize: ${verifiedPreview.size_bytes.toLocaleString()} bytes\nSHA-256: ${verifiedPreview.sha256}\n\nThe app will verify the digest and start the official installer without requesting elevation. Review any Windows prompt yourself.`,
      noLink: true,
    });
    if (result.response !== 0) return { ok: false, canceled: true };
    try { return { ok: true, ...(await ollamaInstaller.install(verifiedPreview)) }; }
    catch (error) { return { ok: false, message: error instanceof Error ? error.message.slice(0, 220) : "Verified installer could not be started." }; }
  });
  ipcMain.handle("desktop:request-camera", async (event) => {
    const frame = event.senderFrame;
    if (!workspaceWindows.trusted(event.sender)
        || !event.sender.getURL().startsWith(`${ORIGIN}/ui/chat`)
        || !frame || frame !== event.sender.mainFrame || !frame.url.startsWith(`${ORIGIN}/ui/chat`)) return false;
    const result = await dialog.showMessageBox(BrowserWindow.fromWebContents(event.sender), {
      type: "question", buttons: ["Allow once", "Deny"], defaultId: 1, cancelId: 1,
      title: "Camera access",
      message: "Allow one camera frame for this chat?",
      detail: "The camera turns on only for this capture and stops immediately afterward. The frame stays temporary and is not sent to a model unless you separately select it and consent for a chat turn.",
    });
    if (result.response !== 0) return false;
    cameraGrants.set(event.sender.id, Date.now() + 15_000);
    return true;
  });
  ipcMain.handle("desktop:request-microphone", async (event) => {
    const frame = event.senderFrame;
    if (!workspaceWindows.trusted(event.sender)
        || !event.sender.getURL().startsWith(`${ORIGIN}/`)
        || !frame || frame !== event.sender.mainFrame || !frame.url.startsWith(`${ORIGIN}/`)) return false;
    const result = await dialog.showMessageBox(BrowserWindow.fromWebContents(event.sender), {
      type: "question", buttons: ["Allow once", "Deny"], defaultId: 1, cancelId: 1,
      title: "Microphone access",
      message: "Allow microphone access for this voice interaction?",
      detail: "Audio is used only for the interaction you start. Local mode keeps recognition on this device; Gemini mode sends the recording only after separate per-use consent.",
    });
    if (result.response !== 0) return false;
    microphoneGrants.set(event.sender.id, Date.now() + 15_000);
    return true;
  });
  if (fs.existsSync(CREDENTIAL)) makeBootstrapWindow();
  else void startBackend({}).then((result) => {
    if (!result.started) { dialog.showErrorBox("ERSELMETZ AI could not start", result.message); app.quit(); }
  });
});

if (!isResetHelper) app.on("second-instance", () => {
  if (backend && workspaceWindows.first()) workspaceWindows.create("chat");
  else if (bootstrapWindow) { if (bootstrapWindow.isMinimized()) bootstrapWindow.restore(); bootstrapWindow.focus(); }
});

if (!isResetHelper) app.on("before-quit", (event) => {
  if (quitting || !backend) return;
  event.preventDefault();
  if (quitAfterShutdown) return;
  quitAfterShutdown = true;
  stopBackend().then(async (stopped) => {
    if (!stopped) {
      quitAfterShutdown = false;
      const options = { type: "warning", buttons: ["Keep app open"], title: "Service is still stopping", message: "The local service has not stopped yet. Keep the app open and try closing it again after it finishes." };
      const ownerWindow = workspaceWindows.first() || bootstrapWindow;
      if (ownerWindow) await dialog.showMessageBox(ownerWindow, options);
      else await dialog.showMessageBox(options);
      return;
    }
    await session.defaultSession.clearStorageData({ storages: ["cookies"] });
    workspaceWindows.prepareQuit();
    quitting = true;
    app.quit();
  });
});

if (!isResetHelper) app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });

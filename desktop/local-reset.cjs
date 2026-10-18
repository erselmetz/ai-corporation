const fs = require("node:fs");
const path = require("node:path");

const APP_DATA_DIRECTORY_NAME = "ERSELMETZ AI";
const RESET_HELPER_ARGUMENT = "--reset-app-data-helper";

function resolveAppDataDirectory(localAppData) {
  if (typeof localAppData !== "string" || localAppData.length === 0) throw new Error("Local app-data root is unavailable");
  const root = path.resolve(localAppData);
  const target = path.resolve(root, APP_DATA_DIRECTORY_NAME);
  if (path.dirname(target).toLowerCase() !== root.toLowerCase()
      || path.basename(target).toLowerCase() !== APP_DATA_DIRECTORY_NAME.toLowerCase()) {
    throw new Error("App-data target is outside the fixed per-user data directory");
  }
  return target;
}

function removeAppDataDirectory(localAppData, requestedTarget) {
  const expected = resolveAppDataDirectory(localAppData);
  const target = path.resolve(requestedTarget || expected);
  if (target.toLowerCase() !== expected.toLowerCase()) throw new Error("Refusing to remove an unexpected app-data path");
  fs.rmSync(target, { recursive: true, force: true, maxRetries: 5, retryDelay: 250 });
  return true;
}

async function waitForParentAndRemoveAppData(localAppData, requestedTarget, parentPid, {
  isProcessAlive = (pid) => {
    try { process.kill(pid, 0); return true; }
    catch (error) { if (error && error.code === "ESRCH") return false; throw error; }
  },
  wait = (delayMs) => new Promise((resolve) => setTimeout(resolve, delayMs)),
  now = Date.now,
  timeoutMs = 30_000,
  pollMs = 200,
} = {}) {
  if (!Number.isInteger(parentPid) || parentPid <= 0) throw new Error("Reset parent process ID is invalid");
  const deadline = now() + timeoutMs;
  while (now() < deadline && isProcessAlive(parentPid)) await wait(pollMs);
  if (isProcessAlive(parentPid)) return false;
  removeAppDataDirectory(localAppData, requestedTarget);
  return true;
}

module.exports = {
  APP_DATA_DIRECTORY_NAME, RESET_HELPER_ARGUMENT, removeAppDataDirectory,
  resolveAppDataDirectory, waitForParentAndRemoveAppData,
};

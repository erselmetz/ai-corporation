const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { resolveAppDataDirectory, waitForParentAndRemoveAppData } = require("../local-reset.cjs");

function temporaryDirectory() { return fs.mkdtempSync(path.join(os.tmpdir(), "erselmetz-reset-")); }

test("reset waits for the parent to exit, then deletes only the fixed per-user data folder", async () => {
  const localAppData = temporaryDirectory();
  try {
    const appData = resolveAppDataDirectory(localAppData);
    const sibling = path.join(localAppData, "ERSELMETZ AI Backup");
    fs.mkdirSync(path.join(appData, "projects"), { recursive: true });
    fs.writeFileSync(path.join(appData, "projects", "owner.db"), "owner data");
    fs.mkdirSync(sibling);
    fs.writeFileSync(path.join(sibling, "keep.txt"), "preserve");
    assert.equal(await waitForParentAndRemoveAppData(localAppData, appData, 123, {
      isProcessAlive: (() => { let calls = 0; return () => ++calls === 1; })(),
      wait: async (delay) => assert.equal(delay, 200),
    }), true);
    assert.equal(fs.existsSync(appData), false);
    assert.equal(fs.readFileSync(path.join(sibling, "keep.txt"), "utf8"), "preserve");
  } finally { fs.rmSync(localAppData, { recursive: true, force: true }); }
});

test("reset refuses an unexpected data path and times out without deleting anything", async () => {
  const localAppData = temporaryDirectory();
  try {
    const appData = resolveAppDataDirectory(localAppData);
    const protectedPath = path.join(localAppData, "keep-me");
    fs.mkdirSync(appData);
    fs.writeFileSync(path.join(appData, "owner.db"), "preserve");
    fs.mkdirSync(protectedPath);
    await assert.rejects(waitForParentAndRemoveAppData(localAppData, protectedPath, 123, {
      isProcessAlive: () => false,
    }), /unexpected app-data path/);
    let now = 0;
    assert.equal(await waitForParentAndRemoveAppData(localAppData, appData, 123, {
      isProcessAlive: () => true,
      wait: async (delay) => { now += delay; },
      now: () => now,
      timeoutMs: 300,
      pollMs: 100,
    }), false);
    assert.equal(fs.readFileSync(path.join(appData, "owner.db"), "utf8"), "preserve");
    await assert.rejects(waitForParentAndRemoveAppData(localAppData, appData, 123, {
      isProcessAlive: () => { const error = new Error("process lookup denied"); error.code = "EPERM"; throw error; },
    }), /process lookup denied/);
    assert.equal(fs.readFileSync(path.join(appData, "owner.db"), "utf8"), "preserve");
  } finally { fs.rmSync(localAppData, { recursive: true, force: true }); }
});

test("reset does not remove a locked profile until its parent releases the open file", { skip: process.platform !== "win32" }, async () => {
  const localAppData = temporaryDirectory();
  let descriptor;
  try {
    const appData = resolveAppDataDirectory(localAppData);
    const file = path.join(appData, "desktop", "open-profile-state.json");
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, "local profile state");
    descriptor = fs.openSync(file, "r");
    let now = 0;
    assert.equal(await waitForParentAndRemoveAppData(localAppData, appData, 123, {
      isProcessAlive: () => true,
      wait: async (delay) => { now += delay; },
      now: () => now,
      timeoutMs: 400,
      pollMs: 200,
    }), false);
    assert.equal(fs.readFileSync(file, "utf8"), "local profile state");
    fs.closeSync(descriptor);
    descriptor = undefined;
    assert.equal(await waitForParentAndRemoveAppData(localAppData, appData, 123, {
      isProcessAlive: () => false,
    }), true);
    assert.equal(fs.existsSync(appData), false);
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    fs.rmSync(localAppData, { recursive: true, force: true });
  }
});

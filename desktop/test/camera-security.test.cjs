const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const main = fs.readFileSync(path.join(__dirname, "..", "main.cjs"), "utf8");
const preload = fs.readFileSync(path.join(__dirname, "..", "preload.cjs"), "utf8");

test("camera grant requires a trusted chat main frame and native allow-once decision", () => {
  assert.match(main, /desktop:request-camera/);
  assert.match(main, /frame !== event\.sender\.mainFrame/);
  assert.match(main, /frame\.url\.startsWith\(`\$\{ORIGIN\}\/ui\/chat`\)/);
  assert.match(main, /buttons: \["Allow once", "Deny"\], defaultId: 1, cancelId: 1/);
  assert.match(main, /cameraGrants\.set\(event\.sender\.id, Date\.now\(\) \+ 15_000\)/);
  assert.match(main, /not sent to a model unless you separately select it and consent/);
});

test("Electron grants only video-only media once to the trusted chat and preload exposes one camera request", () => {
  assert.match(main, /const videoOnly = permission === "media"[\s\S]*details\.mediaTypes\[0\] === "video"/);
  assert.match(main, /trusted && videoOnly && webContents\.getURL\(\)\.startsWith\(`\$\{ORIGIN\}\/ui\/chat`\)[\s\S]*cameraGrants\.get\(webContents\.id\)[\s\S]*cameraGrants\.delete\(webContents\.id\)/);
  assert.match(preload, /requestCamera: \(\) => ipcRenderer\.invoke\("desktop:request-camera"\)/);
  assert.doesNotMatch(preload, /ipcRenderer\.send\(/);
});

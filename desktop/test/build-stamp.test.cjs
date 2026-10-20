const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const desktop = path.resolve(__dirname, "..");
const main = fs.readFileSync(path.join(desktop, "main.cjs"), "utf8");
const backendBuild = fs.readFileSync(path.join(desktop, "scripts", "build-backend.ps1"), "utf8");
const installerBuild = fs.readFileSync(path.join(desktop, "scripts", "build-installer.ps1"), "utf8");

test("packaged startup passes the build commit and refuses an unidentifiable package", () => {
  assert.match(main, /resourcesPath, "backend", "build-stamp\.json"/);
  assert.match(main, /ERSELMETZ_BUILD_COMMIT: commit/);
  assert.match(main, /packaged backend build identity is missing or invalid/);
  assert.match(backendBuild, /git -C \$repo rev-parse HEAD/);
  assert.match(backendBuild, /build-stamp\.json/);
});

test("review builds can use isolated output directories without deleting prior releases", () => {
  assert.match(backendBuild, /ERSELMETZ_BUILD_OUTPUT_ROOT/);
  assert.match(installerBuild, /ERSELMETZ_BUILD_OUTPUT_ROOT/);
  assert.match(installerBuild, /ERSELMETZ_RELEASE_OUTPUT/);
  assert.match(installerBuild, /extraResources\[0\]\.from/);
  assert.match(installerBuild, /Refusing an Electron build or release output outside the repository/);
});

test("desktop test port remains loopback-only and rejects invalid port values", () => {
  assert.match(main, /const HOST = "127\.0\.0\.1"/);
  assert.match(main, /process\.env\.ERSELMETZ_PORT/);
  assert.match(main, /value < 1024 \|\| value > 65535/);
  assert.match(main, /const ORIGIN = `http:\/\/\$\{HOST\}:\$\{PORT\}`/);
});

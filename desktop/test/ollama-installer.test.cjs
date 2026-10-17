const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { OllamaInstaller, RELEASE_API, MAX_INSTALLER_BYTES } = require("../ollama-installer.cjs");

function release(bytes) {
  return { tag_name: "v1.2.3", assets: [{
    name: "OllamaSetup.exe", size: bytes.length,
    digest: `sha256:${crypto.createHash("sha256").update(bytes).digest("hex")}`,
    browser_download_url: "https://github.com/ollama/ollama/releases/download/v1.2.3/OllamaSetup.exe",
  }] };
}

test("Ollama installer preview is pinned to official release metadata and exact asset", async () => {
  const bytes = Buffer.from("verified Ollama installer");
  const installer = new OllamaInstaller({ fetchImpl: async (url) => {
    assert.equal(url, RELEASE_API);
    return new Response(JSON.stringify(release(bytes)), { status: 200 });
  } });
  const preview = await installer.preview();
  assert.equal(preview.publisher, "ollama/ollama GitHub release");
  assert.equal(preview.size_bytes, bytes.length);
  assert.equal(preview.sha256, release(bytes).assets[0].digest.slice(7));
});

test("installer preview accepts a bounded large release and refuses sizes above its cap", async () => {
  const bytes = Buffer.from("metadata-only fixture");
  const metadata = release(bytes);
  metadata.assets[0].size = MAX_INSTALLER_BYTES;
  const installer = new OllamaInstaller({ fetchImpl: async () =>
    new Response(JSON.stringify(metadata), { status: 200 }) });
  assert.equal((await installer.preview()).size_bytes, MAX_INSTALLER_BYTES);
  metadata.assets[0].size = MAX_INSTALLER_BYTES + 1;
  await assert.rejects(installer.preview(), /size or SHA-256 digest is unavailable/);
});

test("installer verifies exact downloaded bytes before launching without shell or elevation", async () => {
  const bytes = Buffer.from("verified Ollama installer");
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "ollama-install-test-"));
  const calls = [];
  const installer = new OllamaInstaller({ tempDir, fetchImpl: async (url, options = {}) => {
    calls.push({ url, options });
    if (url === RELEASE_API) return new Response(JSON.stringify(release(bytes)), { status: 200 });
    assert.equal(options.redirect, "manual");
    return new Response(bytes, { status: 200, headers: { "content-length": String(bytes.length) } });
  }, spawnImpl: (file, args, options) => {
    assert.ok(fs.existsSync(file));
    assert.deepEqual(args, []);
    assert.equal(options.shell, false);
    assert.equal(options.windowsHide, false);
    const child = new EventEmitter();
    process.nextTick(() => child.emit("exit", 0));
    return child;
  } });
  try {
    const preview = await installer.preview();
    assert.deepEqual(await installer.install(preview), { installed: true, version: "v1.2.3" });
    assert.equal(fs.readdirSync(tempDir).length, 0);
    assert.equal(calls.length, 3);
  } finally { fs.rmSync(tempDir, { recursive: true, force: true }); }
});

test("installer refuses digest changes and unapproved download hosts", async () => {
  const bytes = Buffer.from("verified Ollama installer");
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "ollama-install-test-"));
  let launched = false;
  const installer = new OllamaInstaller({ tempDir, fetchImpl: async (url) => {
    if (url === RELEASE_API) return new Response(JSON.stringify(release(bytes)), { status: 200 });
    return new Response("", { status: 302, headers: { location: "https://example.invalid/OllamaSetup.exe" } });
  }, spawnImpl: () => { launched = true; throw new Error("must not launch"); } });
  try {
    const preview = await installer.preview();
    await assert.rejects(installer.install({ ...preview, sha256: "0".repeat(64) }), /changed/);
    await assert.rejects(installer.install(preview), /approved GitHub download hosts/);
    assert.equal(launched, false);
    assert.equal(fs.readdirSync(tempDir).length, 0);
  } finally { fs.rmSync(tempDir, { recursive: true, force: true }); }
});

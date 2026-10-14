const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { main } = require("../scripts/sign-release-manifest.cjs");

test("signs only the version-matched Windows artifact using an external Ed25519 key", async (t) => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "ersel-release-sign-"));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  const pair = crypto.generateKeyPairSync("ed25519");
  const keyPath = path.join(directory, "private.pem");
  const artifactPath = path.join(directory, "ERSELMETZ-AI-Setup-0.2.0-win-x64.exe");
  const notesPath = path.join(directory, "notes.md");
  await fs.writeFile(keyPath, pair.privateKey.export({ type: "pkcs8", format: "pem" }));
  await fs.writeFile(artifactPath, "installer bytes");
  await fs.writeFile(notesPath, "Release notes.");

  const result = await main(["0.2.0", artifactPath, notesPath], { ERSELMETZ_UPDATE_SIGNING_KEY_PATH: keyPath });
  const manifest = await fs.readFile(path.join(directory, "erselmetz-release.json"));
  const signature = (await fs.readFile(path.join(directory, "erselmetz-release.sig"), "utf8")).trim();

  assert.equal(result.version, "0.2.0");
  assert.equal(crypto.verify(null, manifest, pair.publicKey, Buffer.from(signature, "base64")), true);
  assert.equal(JSON.parse(manifest).artifact.sha256, crypto.createHash("sha256").update("installer bytes").digest("hex"));
  assert.equal(Object.hasOwn(JSON.parse(manifest), "privateKey"), false);
});

test("refuses an artifact whose filename does not match the release version", async (t) => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "ersel-release-sign-"));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  const pair = crypto.generateKeyPairSync("ed25519");
  const keyPath = path.join(directory, "private.pem");
  const notesPath = path.join(directory, "notes.md");
  await fs.writeFile(keyPath, pair.privateKey.export({ type: "pkcs8", format: "pem" }));
  await fs.writeFile(notesPath, "Release notes.");
  await assert.rejects(() => main(["0.2.0", path.join(directory, "wrong.exe"), notesPath], { ERSELMETZ_UPDATE_SIGNING_KEY_PATH: keyPath }), /does not match/);
});

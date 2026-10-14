const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

async function main(argv = process.argv.slice(2), env = process.env) {
  const [version, installerPath, releaseNotesPath] = argv;
  if (!version || !/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(version) || !installerPath || !releaseNotesPath) {
    throw new Error("Usage: node sign-release-manifest.cjs <version> <installer-path> <release-notes-file>");
  }
  const keyPath = env.ERSELMETZ_UPDATE_SIGNING_KEY_PATH
    || path.join(env.LOCALAPPDATA || "", "ERSELMETZ AI", "release-signing", "update-ed25519-private.pem");
  const privateKey = crypto.createPrivateKey(fs.readFileSync(keyPath, "utf8"));
  if (privateKey.asymmetricKeyType !== "ed25519") throw new Error("Release signing key must use Ed25519.");
  const name = `ERSELMETZ-AI-Setup-${version}-win-x64.exe`;
  if (path.basename(installerPath) !== name) throw new Error("Installer filename does not match the signed version.");
  const digest = crypto.createHash("sha256");
  let artifactBytes = 0;
  for await (const chunk of fs.createReadStream(installerPath)) {
    artifactBytes += chunk.length;
    if (artifactBytes > 2 * 1024 * 1024 * 1024) throw new Error("Installer exceeds the supported 2 GiB limit.");
    digest.update(chunk);
  }
  if (fs.statSync(releaseNotesPath).size > 12000) throw new Error("Release notes exceed the supported 12 KiB limit.");
  const releaseNotes = fs.readFileSync(releaseNotesPath, "utf8");
  if (artifactBytes === 0 || releaseNotes.trim().length === 0 || releaseNotes.length > 12000) throw new Error("Installer or release notes are empty or oversized.");
  const payload = {
    version,
    releaseNotes,
    artifact: { name, sha256: digest.digest("hex") },
    configuration: {
      fromVersion: 1,
      toVersion: 1,
      preview: "No database configuration schema change is planned; existing records remain unchanged.",
    },
  };
  const manifest = Buffer.from(`${JSON.stringify(payload, null, 2)}\n`, "utf8");
  const signature = crypto.sign(null, manifest, privateKey).toString("base64");
  const output = path.dirname(installerPath);
  fs.writeFileSync(path.join(output, "erselmetz-release.json"), manifest, { flag: "wx" });
  fs.writeFileSync(path.join(output, "erselmetz-release.sig"), `${signature}\n`, { flag: "wx" });
  return { version, artifact: name, sha256: payload.artifact.sha256, manifest: output };
}

if (require.main === module) {
  main().then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
    .catch((error) => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
}

module.exports = { main };

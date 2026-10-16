const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { Readable, Transform } = require("node:stream");
const { pipeline } = require("node:stream/promises");
const { spawn } = require("node:child_process");

const RELEASE_API = "https://api.github.com/repos/ollama/ollama/releases/latest";
const MAX_INSTALLER_BYTES = 1024 * 1024 * 1024;
const MAX_RELEASE_METADATA_BYTES = 1024 * 1024;
const ALLOWED_DOWNLOAD_HOSTS = new Set(["github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"]);

class OllamaInstaller {
  constructor({ fetchImpl = fetch, spawnImpl = spawn, tempDir = os.tmpdir(), onProgress = () => {} } = {}) {
    this.fetch = fetchImpl;
    this.spawn = spawnImpl;
    this.tempDir = tempDir;
    this.onProgress = onProgress;
  }

  async _json(url, timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await this.fetch(url, { redirect: "error", signal: controller.signal, headers: { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ERSELMETZ-AI-Desktop" } });
      if (!response.ok) throw new Error("Official release metadata unavailable");
      if (!response.body) throw new Error("Official release metadata unavailable");
      const reader = response.body.getReader();
      const chunks = [];
      let size = 0;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_RELEASE_METADATA_BYTES) {
          await reader.cancel();
          throw new Error("Official release metadata exceeds the supported size");
        }
        chunks.push(Buffer.from(value));
      }
      return JSON.parse(Buffer.concat(chunks, size).toString("utf8"));
    } finally { clearTimeout(timer); }
  }

  async preview() {
    const release = await this._json(RELEASE_API);
    if (!release || typeof release.tag_name !== "string" || !/^v?[0-9][A-Za-z0-9.+-]{0,63}$/.test(release.tag_name) || !Array.isArray(release.assets)) {
      throw new Error("Official installer metadata is invalid");
    }
    const asset = release.assets.find((item) => item?.name === "OllamaSetup.exe");
    if (!asset || !Number.isSafeInteger(asset.size) || asset.size < 1 || asset.size > MAX_INSTALLER_BYTES
        || typeof asset.browser_download_url !== "string" || !/^sha256:[0-9a-f]{64}$/.test(asset.digest || "")) {
      throw new Error("Official installer size or SHA-256 digest is unavailable; installation is disabled");
    }
    const url = new URL(asset.browser_download_url);
    if (url.protocol !== "https:" || url.hostname !== "github.com"
        || url.pathname !== `/ollama/ollama/releases/download/${release.tag_name}/OllamaSetup.exe`) {
      throw new Error("Official installer source is outside the verified Ollama release");
    }
    return { version: release.tag_name, source: url.href, size_bytes: asset.size,
      sha256: asset.digest.slice("sha256:".length), publisher: "ollama/ollama GitHub release" };
  }

  async _download(url, destination, expected) {
    let current = new URL(url);
    let response;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30 * 60 * 1000);
    try {
    for (let redirects = 0; redirects <= 4; redirects += 1) {
      if (current.protocol !== "https:" || !ALLOWED_DOWNLOAD_HOSTS.has(current.hostname)) throw new Error("Installer redirect is outside the approved GitHub download hosts");
      response = await this.fetch(current.href, { redirect: "manual", signal: controller.signal });
      if (![301, 302, 303, 307, 308].includes(response.status)) break;
      if (redirects === 4) throw new Error("Installer download exceeded the redirect limit");
      const location = response.headers.get("location");
      if (!location) throw new Error("Installer redirect was invalid");
      current = new URL(location, current);
    }
    if (!response?.ok || !response.body) throw new Error("Official installer download failed");
    const rawLength = response.headers.get("content-length");
    const length = rawLength === null ? null : Number(rawLength);
    if (length !== null && (!Number.isSafeInteger(length) || length !== expected.size_bytes)) throw new Error("Installer size did not match the verified release metadata");
    let bytes = 0;
    const hash = crypto.createHash("sha256");
    const onProgress = this.onProgress;
    const verify = new Transform({ transform(chunk, _encoding, callback) {
      bytes += chunk.length;
      if (bytes > expected.size_bytes || bytes > MAX_INSTALLER_BYTES) return callback(new Error("Installer exceeded the verified release size"));
      hash.update(chunk);
      onProgress({ downloaded: bytes, total: expected.size_bytes });
      callback(null, chunk);
    } });
    await pipeline(Readable.fromWeb(response.body), verify, fs.createWriteStream(destination, { flags: "wx", mode: 0o600 }));
    if (bytes !== expected.size_bytes || hash.digest("hex") !== expected.sha256) throw new Error("Installer SHA-256 verification failed");
    } finally { clearTimeout(timer); }
  }

  async install(approvedPreview) {
    const latest = await this.preview();
    if (!approvedPreview || approvedPreview.version !== latest.version
        || approvedPreview.size_bytes !== latest.size_bytes || approvedPreview.sha256 !== latest.sha256
        || approvedPreview.source !== latest.source) throw new Error("The Ollama installer changed; review the current source, size and digest again");
    fs.mkdirSync(this.tempDir, { recursive: true });
    const destination = path.join(this.tempDir, `ERSELMETZ-OllamaSetup-${latest.version}.exe`);
    try {
      await this._download(latest.source, destination, latest);
      await new Promise((resolve, reject) => {
        const child = this.spawn(destination, [], { shell: false, windowsHide: false, stdio: "ignore" });
        child.once("error", () => reject(new Error("Verified Ollama installer could not be started")));
        child.once("exit", (code) => code === 0 ? resolve() : reject(new Error("Ollama installer did not complete successfully")));
      });
      return { installed: true, version: latest.version };
    } finally {
      try { fs.rmSync(destination, { force: true }); } catch { /* keep only the operator-safe failure */ }
    }
  }
}

module.exports = { OllamaInstaller, RELEASE_API, MAX_INSTALLER_BYTES, ALLOWED_DOWNLOAD_HOSTS };

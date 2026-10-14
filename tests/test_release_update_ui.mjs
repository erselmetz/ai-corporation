import test from "node:test";
import assert from "node:assert/strict";
import { mountReleaseUpdatePage } from "../app/webui/static/release-update.mjs";

class Element {
  constructor() { this.textContent = ""; this.className = ""; this.disabled = false; this.hidden = false; this.listeners = {}; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  async click(type = "click") { await this.listeners[type]?.({ preventDefault() {} }); }
}

function page() {
  const ids = ["release-check", "release-state", "release-preview", "release-version", "release-notes", "release-migration", "release-prepare", "release-prepare-state"];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element()]));
  return { elements, documentRef: { getElementById: (id) => elements[id] } };
}

const release = {
  version: "0.2.0", available: true, release_notes: "Signed notes.",
  installer_name: "ERSELMETZ-AI-Setup-0.2.0-win-x64.exe", installer_sha256: "a".repeat(64),
  from_configuration: 1, to_configuration: 1, migration_preview: "Data unchanged.",
};

test("renders only verified release data and enables preparation for authorized owners", async () => {
  const { elements, documentRef } = page();
  const calls = [];
  const controller = mountReleaseUpdatePage({ documentRef, fetchImpl: async (url) => {
    calls.push(url);
    if (url === "/api/updates/release") return new Response(JSON.stringify(release), { status: 200 });
    if (url === "/api/local/session") return new Response(JSON.stringify({ permissions: ["updates:manage"] }), { status: 200 });
    return new Response("{}", { status: 500 });
  } });
  await controller.checkRelease();
  assert.deepEqual(calls, ["/api/updates/release", "/api/local/session"]);
  assert.equal(elements["release-preview"].hidden, false);
  assert.equal(elements["release-notes"].textContent, "Signed notes.");
  assert.equal(elements["release-prepare"].disabled, false);
  assert.match(elements["release-state"].textContent, /verified/);
});

test("prepares only an explicitly selected checked version and includes the session CSRF token", async () => {
  const { elements, documentRef } = page();
  const calls = [];
  const controller = mountReleaseUpdatePage({ documentRef, fetchImpl: async (url, options = {}) => {
    calls.push([url, options]);
    if (url === "/api/updates/release") return new Response(JSON.stringify(release), { status: 200 });
    if (url === "/api/local/session") return new Response(JSON.stringify({ permissions: ["updates:manage"], csrf: "csrf-owner" }), { status: 200 });
    return new Response(JSON.stringify({ message: "Verified files ready.", installer_path: "C:/local/update.exe", backup_path: "C:/local/backup.sqlite3", installer_sha256: "a".repeat(64) }), { status: 200 });
  } });
  await controller.checkRelease();
  await controller.prepareRelease();
  const [url, options] = calls.at(-1);
  assert.equal(url, "/api/updates/release/prepare");
  assert.equal(options.method, "POST");
  assert.equal(options.headers["X-Local-CSRF"], "csrf-owner");
  assert.equal(options.body, JSON.stringify({ version: "0.2.0" }));
  assert.match(elements["release-prepare-state"].textContent, /backup\.sqlite3/);
});

test("keeps preparation unavailable without manage permission or after invalid release data", async () => {
  const { elements, documentRef } = page();
  let payload = release;
  const controller = mountReleaseUpdatePage({ documentRef, fetchImpl: async (url) => {
    if (url === "/api/updates/release") return new Response(JSON.stringify(payload), { status: 200 });
    return new Response(JSON.stringify({ permissions: ["updates:read"] }), { status: 200 });
  } });
  await controller.checkRelease();
  assert.equal(elements["release-prepare"].disabled, true);
  payload = { ...release, installer_sha256: "bad" };
  await controller.checkRelease();
  assert.equal(elements["release-preview"].hidden, true);
  assert.match(elements["release-state"].textContent, /invalid/);
});

// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";

class Element {
  constructor(id) { this.id = id; this.listeners = {}; this.value = ""; this.checked = false; this.files = []; this.download = ""; this.clicked = false; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  click() { this.clicked = true; }
  async fire(type) { await this.listeners[type]?.({ preventDefault() {}, currentTarget: this }); }
  set textContent(value) { this.text = String(value); }
  get textContent() { return this.text ?? ""; }
}

const ids = ["backup-state", "backup-preview-result", "backup-inspect-result", "backup-private", "backup-file",
  "restore-passphrase", "diagnostics-export", "backup-preview", "backup-passphrase", "backup-export",
  "backup-inspect", "restore-confirmation", "backup-restore"];
const elements = Object.fromEntries(ids.map(id => [id, new Element(id)]));
const anchors = [];
globalThis.document = {
  querySelector: selector => elements[selector.slice(1)],
  createElement: () => { const anchor = new Element("anchor"); anchors.push(anchor); return anchor; },
};
globalThis.window = { confirm: () => true };
globalThis.URL.createObjectURL = () => "blob:test";
globalThis.URL.revokeObjectURL = () => {};
globalThis.setTimeout = callback => { callback(); return 0; };

const calls = [];
const response = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  json: async () => body,
  blob: async () => new Blob(["fixture"]),
});
globalThis.fetch = async (url, options = {}) => {
  calls.push([url, options]);
  if (url === "/api/local/session") return response({ csrf: "test-csrf" });
  if (url.includes("/diagnostics")) return response({ application: "ERSELMETZ AI" });
  if (url.includes("/preview")) return response({ included_tables: ["owner_preferences"] });
  if (url.includes("/export")) return response({});
  if (url.includes("/inspect")) return response({ verified: true, include_private_data: true });
  if (url.includes("/restore")) return response({ status: "restored", requires_restart: "true", recovery_copy: "pre-restore.erselbackup" });
  throw new Error(`Unexpected request: ${url}`);
};

await import("../app/webui/static/backup.mjs");

test("backup UI starts without requests and private-data opt-in is off", () => {
  assert.equal(calls.length, 0);
  assert.equal(elements["backup-private"].checked, false);
});

test("preview, safe diagnostics, and export run only after explicit owner actions", async () => {
  await elements["backup-preview"].fire("click");
  assert.equal(calls[0][0], "/api/local/backup/preview?include_private_data=false");
  assert.match(elements["backup-preview-result"].textContent, /owner_preferences/);
  await elements["diagnostics-export"].fire("click");
  assert.equal(anchors.at(-1).download, "erselmetz-ai-diagnostics.json");
  elements["backup-passphrase"].value = "test-backup-passphrase";
  await elements["backup-export"].fire("click");
  const exportCall = calls.find(([url]) => url.endsWith("/export"));
  assert.equal(JSON.parse(exportCall[1].body).include_private_data, false);
  assert.equal(exportCall[1].headers["X-Local-CSRF"], "test-csrf");
});

test("restore requires the same inspected file, passphrase, typed confirmation, and final prompt", async () => {
  const file = new Blob(["encrypted fixture"], { type: "application/vnd.erselmetz.backup" });
  Object.defineProperty(file, "name", { value: "fixture.erselbackup" });
  Object.defineProperty(file, "size", { value: 17 });
  elements["backup-file"].files = [file];
  elements["restore-passphrase"].value = "test-backup-passphrase";
  await elements["backup-inspect"].fire("click");
  assert.match(elements["backup-state"].textContent, /verified/);
  elements["restore-confirmation"].value = "RESTORE";
  await elements["backup-restore"].fire("click");
  const restoreCall = calls.find(([url]) => url.endsWith("/restore"));
  assert.ok(restoreCall);
  assert.equal(restoreCall[1].headers["X-Local-CSRF"], "test-csrf");
  assert.match(elements["backup-state"].textContent, /Restart ERSELMETZ AI/);
});

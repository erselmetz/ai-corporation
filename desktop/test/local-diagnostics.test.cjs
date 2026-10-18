const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { MAX_REPORT_BYTES, MAX_REPORTS, appendLocalCrashReport, readLocalCrashReports } = require("../local-diagnostics.cjs");

function temporaryDirectory() { return fs.mkdtempSync(path.join(os.tmpdir(), "erselmetz-crash-report-")); }

test("local crash records whitelist metadata and never persist messages, stacks, paths, or secrets", () => {
  const dataDirectory = temporaryDirectory();
  try {
    assert.equal(appendLocalCrashReport(dataDirectory, {
      source: "renderer", event: "renderer-gone", reason: "crashed", exitCode: 7,
      occurredAt: "2026-10-18T12:00:00.000Z", appVersion: "0.1.0",
      message: "API_KEY=super-secret", stack: "C:\\Users\\alice\\private.js", token: "secret-token",
    }), true);
    const reports = readLocalCrashReports(dataDirectory);
    assert.deepEqual(reports, [{ occurredAt: "2026-10-18T12:00:00.000Z", source: "renderer", event: "renderer-gone", reason: "crashed", appVersion: "0.1.0", exitCode: 7 }]);
    const raw = fs.readFileSync(path.join(dataDirectory, "diagnostics", "crash-reports.json"), "utf8");
    assert.ok(Buffer.byteLength(raw, "utf8") <= MAX_REPORT_BYTES);
    assert.doesNotMatch(raw, /super-secret|secret-token|alice|private\.js|stack|message|token/i);
  } finally { fs.rmSync(dataDirectory, { recursive: true, force: true }); }
});

test("local crash records are capped by count and oversized files fail closed", () => {
  const dataDirectory = temporaryDirectory();
  try {
    for (let index = 0; index < MAX_REPORTS + 5; index += 1) {
      assert.equal(appendLocalCrashReport(dataDirectory, { source: "main", event: "unhandled-rejection", appVersion: "0.1.0", exitCode: index }), true);
    }
    assert.equal(readLocalCrashReports(dataDirectory).length, MAX_REPORTS);
    const reportPath = path.join(dataDirectory, "diagnostics", "crash-reports.json");
    fs.writeFileSync(reportPath, " ".repeat(MAX_REPORT_BYTES + 1));
    assert.deepEqual(readLocalCrashReports(dataDirectory), []);
    assert.equal(appendLocalCrashReport(dataDirectory, { source: "backend", event: "backend-exit" }), true);
    assert.equal(readLocalCrashReports(dataDirectory).length, 1);
  } finally { fs.rmSync(dataDirectory, { recursive: true, force: true }); }
});

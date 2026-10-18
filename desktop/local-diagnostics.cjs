const fs = require("node:fs");
const path = require("node:path");
const { randomBytes } = require("node:crypto");

const MAX_REPORTS = 8;
const MAX_REPORT_BYTES = 8192;
const ALLOWED_SOURCES = new Set(["main", "renderer", "backend"]);
const ALLOWED_EVENTS = new Set(["uncaught-exception", "unhandled-rejection", "renderer-gone", "backend-exit"]);
const ALLOWED_REASONS = new Set(["clean-exit", "abnormal-exit", "killed", "crashed", "oom", "launch-failed", "integrity-failure", "unknown"]);

function normalizeCrashReport(value) {
  if (!value || typeof value !== "object") return null;
  const occurredAt = typeof value.occurredAt === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(value.occurredAt)
    ? value.occurredAt : new Date().toISOString();
  const source = ALLOWED_SOURCES.has(value.source) ? value.source : "main";
  const event = ALLOWED_EVENTS.has(value.event) ? value.event : "uncaught-exception";
  const reason = ALLOWED_REASONS.has(value.reason) ? value.reason : "unknown";
  const appVersion = typeof value.appVersion === "string" && /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(value.appVersion)
    ? value.appVersion.slice(0, 48) : "unknown";
  const exitCode = Number.isInteger(value.exitCode) && value.exitCode >= -1 && value.exitCode <= 255 ? value.exitCode : null;
  return Object.freeze({ occurredAt, source, event, reason, appVersion, exitCode });
}

function appendLocalCrashReport(dataDirectory, value) {
  const entry = normalizeCrashReport(value);
  if (!entry) return false;
  const reportPath = path.join(dataDirectory, "diagnostics", "crash-reports.json");
  let existing = [];
  try {
    if (fs.statSync(reportPath).size > MAX_REPORT_BYTES) throw new Error("oversized local diagnostic file");
    const parsed = JSON.parse(fs.readFileSync(reportPath, "utf8"));
    if (Array.isArray(parsed)) existing = parsed.map(normalizeCrashReport).filter(Boolean).slice(-MAX_REPORTS + 1);
  } catch { /* malformed or missing local report starts a fresh bounded file */ }
  const records = [...existing, entry].slice(-MAX_REPORTS);
  const serialized = JSON.stringify(records, null, 2);
  if (Buffer.byteLength(serialized, "utf8") > MAX_REPORT_BYTES) return false;
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  const temporaryPath = `${reportPath}.${randomBytes(8).toString("hex")}.tmp`;
  fs.writeFileSync(temporaryPath, serialized, { encoding: "utf8", mode: 0o600, flag: "wx" });
  fs.renameSync(temporaryPath, reportPath);
  return true;
}

function readLocalCrashReports(dataDirectory) {
  const reportPath = path.join(dataDirectory, "diagnostics", "crash-reports.json");
  try {
    if (fs.statSync(reportPath).size > MAX_REPORT_BYTES) return [];
    const parsed = JSON.parse(fs.readFileSync(reportPath, "utf8"));
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeCrashReport).filter(Boolean).slice(-MAX_REPORTS);
  } catch { return []; }
}

module.exports = { MAX_REPORTS, MAX_REPORT_BYTES, appendLocalCrashReport, normalizeCrashReport, readLocalCrashReports };

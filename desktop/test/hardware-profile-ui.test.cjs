const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("../../desktop-ui/node_modules/typescript");

const root = path.resolve(__dirname, "../..");
const summaryModule = fs.readFileSync(path.join(root, "desktop-ui/src/app/settings/hardware-summary.ts"), "utf8");
const compiled = ts.transpileModule(summaryModule, { compilerOptions: {
  module: ts.ModuleKind.CommonJS,
  target: ts.ScriptTarget.ES2020,
  jsx: ts.JsxEmit.ReactJSX,
} }).outputText;
const moduleExports = {};
vm.runInNewContext(`(function (exports) { ${compiled}\n})`, {})(moduleExports);
const summarize = moduleExports.summarizeHardwareProfile;

function field(state, value, source, reason) {
  return { state, value, unit: state === "observed" ? "bytes" : null,
    source: state === "observed" ? source : null, observed_at: "2026-10-18T00:00:00Z", reason: reason ?? null };
}

test("hardware settings expose per-field provenance and warn when CPU inference is expected", () => {
  const result = summarize({
    observed_at: "2026-10-18T00:00:00Z",
    cpu: field("observed", { name: "Example CPU", logical_processors: 8 }, "Windows WMI"),
    gpu: field("observed", [], "Windows WMI"),
    memory: field("observed", { total_bytes: 8 * 1024 ** 3, available_bytes: 3 * 1024 ** 3 }, "GlobalMemoryStatusEx"),
    disk: field("observed", { free_bytes: 12 * 1024 ** 3, total_bytes: 100 * 1024 ** 3, destination: "default" }, "Ollama destination"),
    recommendation: { ollama_model_class: "small (up to about 3B parameters, Q4)",
      cpu_warning: "No hardware GPU adapter was reported; expect Ollama to use CPU, which can make replies slower.",
      basis: "Conservative memory guidance.", fit_claim: "This heuristic does not guarantee model fit." },
  });
  assert.equal(result.state, "ready");
  assert.match(result.values.CPU, /Example CPU.*source Windows WMI.*observed 2026/);
  assert.match(result.values.GPU, /No hardware GPU adapter reported.*source Windows WMI/);
  assert.match(result.message, /expect Ollama to use CPU/);
  assert.match(result.message, /does not guarantee model fit/);
  assert.match(result.message, /does not install or download anything/);
});

test("hardware settings preserve UNKNOWN and sanitized source fields", () => {
  const unknown = field("unknown", null, null, "CPU inventory unavailable");
  const result = summarize({ cpu: unknown, gpu: unknown, memory: unknown, disk: unknown,
    recommendation: { ollama_model_class: "UNKNOWN", cpu_warning: "GPU status is unknown; Ollama may use CPU." } });
  assert.equal(result.state, "unknown");
  assert.match(result.values.CPU, /UNKNOWN.*CPU inventory unavailable.*checked 2026/);
  assert.match(result.values.Disk, /UNKNOWN.*CPU inventory unavailable/);
  assert.match(result.message, /GPU status is unknown; Ollama may use CPU/);
});

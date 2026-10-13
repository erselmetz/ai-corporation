const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const page = fs.readFileSync(path.join(root, "desktop-ui/src/app/page.tsx"), "utf8");

test("first-run checks are bounded and report unsupported evidence as unknown", () => {
  assert.match(page, /setTimeout\(\(\) => controller\.abort\(\), 2500\)/);
  assert.match(page, /boundedFetch\("\/health"\)/);
  assert.match(page, /boundedFetch\("\/api\/local\/session"\)/);
  assert.match(page, /boundedFetch\("\/api\/providers"\)/);
  assert.match(page, /boundedFetch\("\/api\/agents"\)/);
  assert.match(page, /providerAvailability: "unknown"/);
  assert.match(page, /optionalCapabilities: "unknown"/);
  assert.match(page, /Installed app verification/);
  assert.match(page, /Installed models/);
  assert.match(page, /Coordinator chat permission/);
  assert.match(page, /does not verify installer integrity/);
  assert.match(page, /No live provider health check is run/);
});

test("onboarding explains the shortest chat path and keeps operator controls separate", () => {
  assert.match(page, /href="\/ui\/login"/);
  assert.match(page, /href="\/ui\/chat"/);
  assert.match(page, /configured coordinator/);
  assert.match(page, /Advanced operator settings/);
  assert.match(page, /href="\/ui\/providers"/);
  assert.match(page, /href="\/ui\/local-models"/);
  assert.match(page, /href="\/ui\/provider-connections"/);
  assert.match(page, /href="\/ui\/employees"/);
  assert.match(page, /does not dispatch Tasks/);
});

test("provider guidance separates setup choices, readiness evidence, and operator settings", () => {
  for (const text of ["Use a local Ollama service", "Use Google Gemini", "ordinary chat", "Registered provider", "Service availability", "Installed model", "Agent assignment", "Software capacity", "Measured hardware evidence", "Everyday use:", "does not yet have a general preferences page", "Advanced operator settings", "Resource settings", "Diagnostics and activity"]) {
    assert.ok(page.includes(text), `missing provider setup guidance: ${text}`);
  }
  for (const href of ["/ui/provider-connections", "/ui/online-provider", "/ui/providers", "/ui/local-models", "/ui/assignment-policy", "/ui/login", "/ui/activity", "/ui/inventory"]) {
    assert.ok(page.includes(`href="${href}"`), `missing existing operator page: ${href}`);
  }
  assert.match(page, /request slots represent software concurrency only/);
  assert.match(page, /availability is unknown/);
});

test("first-run overview does not mutate provider or model configuration", () => {
  assert.doesNotMatch(page, /method:\s*["'](POST|PUT|PATCH|DELETE)["']/i);
  assert.doesNotMatch(page, /fetch\([^)]*(?:connect|download|assign|health-check)/i);
  assert.match(page, /Nothing is downloaded, connected, or reassigned automatically/);
});

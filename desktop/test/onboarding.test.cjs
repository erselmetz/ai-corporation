const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const page = fs.readFileSync(path.join(root, "desktop-ui/src/app/page.tsx"), "utf8");
const settingsPage = fs.readFileSync(path.join(root, "desktop-ui/src/app/settings/page.tsx"), "utf8");

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
  assert.match(page, /href="\/desktop\/settings\/"/);
  assert.match(page, /href="\/ui\/provider-connections"/);
  assert.match(page, /href="\/ui\/employees"/);
  assert.match(page, /href="\/ui\/visualization">Interactive system map/);
  assert.match(page, /does not dispatch Tasks/);
});

test("provider guidance links everyday preferences to the grouped settings hub", () => {
  for (const text of ["Use a local Ollama service", "Use Google Gemini", "ordinary chat", "Registered provider", "Service availability", "Installed model", "Agent assignment", "Software capacity", "Measured hardware evidence", "Everyday use:", "Advanced operator settings", "Resource settings", "Diagnostics and activity", "href=\"/desktop/settings/\""]) {
    assert.ok(page.includes(text), `missing provider setup guidance: ${text}`);
  }
  for (const href of ["/ui/provider-connections", "/ui/online-provider", "/ui/providers", "/ui/local-models", "/ui/assignment-policy", "/ui/login", "/ui/activity", "/ui/inventory", "/ui/readiness", "/ui/backup", "/desktop/settings/"]) {
    assert.ok(page.includes(`href="${href}"`), `missing existing operator page: ${href}`);
  }
  assert.match(page, /request slots represent software concurrency only/);
  assert.match(page, /availability is unknown/);
});

test("settings hub reads current values only through existing permission-checked endpoints", () => {
  for (const route of ["/api/local/session", "/api/local/preferences", "/api/providers", "/api/models", "/api/local/provider-connections", "/api/local/assignment-policy", "/api/capabilities/grants", "/api/system/monitor"]) {
    assert.ok(settingsPage.includes(route), `missing current settings source: ${route}`);
  }
  for (const permission of ["chat:read", "provider:read", "model:read", "provider-connection:read", "assignment-policy:read", "capability-grant:manage", "system:read"]) {
    assert.ok(settingsPage.includes(permission), `missing permission gate: ${permission}`);
  }
  assert.match(settingsPage, /credentials: "same-origin"/);
  assert.match(settingsPage, /cache: "no-store"/);
  assert.match(settingsPage, /status === 401/);
  assert.match(settingsPage, /status === 403/);
  assert.doesNotMatch(settingsPage, /method:\s*["'](POST|PUT|PATCH|DELETE)["']/i);
  assert.doesNotMatch(settingsPage, /api_key|password/i);
  assert.match(settingsPage, /hardware feasibility remains unknown/i);
  assert.match(settingsPage, /No backup is created or inspected from this overview/);
});

test("first-run overview does not mutate provider or model configuration", () => {
  assert.doesNotMatch(page, /method:\s*["'](POST|PUT|PATCH|DELETE)["']/i);
  assert.doesNotMatch(page, /fetch\([^)]*(?:connect|download|assign|health-check)/i);
  assert.match(page, /Nothing is downloaded, connected, or reassigned automatically/);
});

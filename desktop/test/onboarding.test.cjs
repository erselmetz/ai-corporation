const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const page = fs.readFileSync(path.join(root, "desktop-ui/src/app/page.tsx"), "utf8");
const settingsPage = fs.readFileSync(path.join(root, "desktop-ui/src/app/settings/page.tsx"), "utf8");
const hardwareSummary = fs.readFileSync(path.join(root, "desktop-ui/src/app/settings/hardware-summary.ts"), "utf8");
const shell = fs.readFileSync(path.join(root, "desktop-ui/src/app/app-shell.tsx"), "utf8");
const main = fs.readFileSync(path.join(root, "desktop/main.cjs"), "utf8");

test("new Electron launches start the loopback service and open Coordinator Chat with a per-launch token", () => {
  assert.match(main, /crypto\.randomBytes\(32\)\.toString\("base64url"\)/);
  assert.match(main, /session_token: startupToken/);
  assert.match(main, /name: "ersel_local_session", value: startupToken[^\n]*httpOnly: true/);
  assert.match(main, /workspaceWindows\.restore\(\)/);
  assert.match(main, /if \(fs\.existsSync\(CREDENTIAL\)\) makeBootstrapWindow\(\)/);
  const windows = fs.readFileSync(path.join(root, "desktop/workspaces.cjs"), "utf8");
  assert.match(windows, /\/ui\/chat\?desktop=1/);
  assert.match(windows, /minWidth: 600, minHeight: 620/);
});

test("Electron health handshake requires a matching version and source commit stamp", () => {
  assert.match(main, /build-stamp\.json/);
  assert.match(main, /ERSELMETZ_BUILD_COMMIT/);
  assert.match(main, /const health = JSON\.parse\(body\)/);
  assert.match(main, /health\.version === require\("\.\/package\.json"\)\.version/);
  assert.match(main, /health\.commit\.toLowerCase\(\) === expectedBackendCommit/);
});

test("first-run checks are bounded and report unsupported evidence as unknown", () => {
  assert.match(page, /setTimeout\(\(\) => controller\.abort\(\), 2500\)/);
  assert.match(page, /boundedFetch\("\/health"\)/);
  assert.match(page, /boundedFetch\("\/api\/local\/session"\)/);
  assert.match(page, /boundedFetch\("\/api\/providers"\)/);
  assert.match(page, /boundedFetch\("\/api\/agents"\)/);
  assert.match(page, /boundedFetch\("\/api\/capability-packs"\)/);
  assert.match(page, /providerAvailability: "unknown"/);
  assert.match(page, /optionalCapabilities: "checking"/);
  assert.match(page, /Installed app verification/);
  assert.match(page, /Installed models/);
  assert.match(page, /Coordinator chat permission/);
  assert.match(page, /does not verify installer integrity/);
  assert.match(page, /No live provider health check is run/);
  assert.match(page, /Pinned wheel installs and speech-model pulls need separate owner confirmation/);
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
  for (const destination of ["/ui/employees", "/ui/visualization", "/ui/projects"]) {
    assert.ok(shell.includes(`"${destination}"`), `missing shared navigation destination: ${destination}`);
  }
  assert.match(shell, /Interactive system map/);
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

test("settings hub reads scoped values and changes only the explicit desktop password lock", () => {
  for (const route of ["/api/local/session", "/api/local/preferences", "/api/providers", "/api/models", "/api/local/provider-connections", "/api/local/assignment-policy", "/api/capabilities/grants", "/api/system/monitor", "/api/system/hardware-profile"]) {
    assert.ok(settingsPage.includes(route), `missing current settings source: ${route}`);
  }
  for (const permission of ["chat:read", "provider:read", "model:read", "provider-connection:read", "assignment-policy:read", "capability-grant:manage", "system:read"]) {
    assert.ok(settingsPage.includes(permission), `missing permission gate: ${permission}`);
  }
  assert.match(settingsPage, /credentials: "same-origin"/);
  assert.match(settingsPage, /cache: "no-store"/);
  assert.match(settingsPage, /status === 401/);
  assert.match(settingsPage, /status === 403/);
  assert.match(settingsPage, /method: "POST"/);
  assert.match(settingsPage, /\/api\/local\/desktop-lock/);
  assert.match(settingsPage, /X-Local-CSRF/);
  assert.match(settingsPage, /confirmation: lockEnabled \? null : lockConfirmation/);
  assert.doesNotMatch(settingsPage, /api_key/i);
  assert.match(settingsPage, /hardware feasibility remains unknown/i);
  assert.match(settingsPage, /Hardware profile and model guidance/);
  assert.match(settingsPage, /summarizeHardwareProfile/);
  assert.match(settingsPage, /not stored or uploaded/i);
  assert.match(hardwareSummary, /UNKNOWN/);
  assert.match(hardwareSummary, /recommendation\.fit_claim/);
  assert.match(settingsPage, /No backup is created or inspected from this overview/);
});

test("first-run overview does not mutate provider or model configuration", () => {
  assert.doesNotMatch(page, /method:\s*["'](POST|PUT|PATCH|DELETE)["']/i);
  assert.doesNotMatch(page, /fetch\([^)]*(?:connect|download|assign|health-check)/i);
  assert.match(page, /Nothing is downloaded, connected, or reassigned automatically/);
});

test("settings exposes local-only recovery records and a separate owner-confirmed full reset", () => {
  assert.match(settingsPage, /Local crash reports/);
  assert.match(settingsPage, /Messages, stack traces, prompts, credentials, paths, and provider responses are excluded/);
  assert.match(settingsPage, /Reports never upload automatically/);
  assert.match(settingsPage, /Reset all app data/);
  assert.match(settingsPage, /Export a recovery backup first/);
  assert.match(settingsPage, /resetAppData\(\)/);
  const main = fs.readFileSync(path.join(root, "desktop/main.cjs"), "utf8");
  assert.match(main, /ownerHasPermission\("backup:restore"\)/);
  assert.match(main, /buttons: \["Cancel", "Reset app data"\], defaultId: 0, cancelId: 0/);
});

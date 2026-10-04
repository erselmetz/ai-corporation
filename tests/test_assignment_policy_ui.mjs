import assert from "node:assert/strict";
import test from "node:test";
import { mountAssignmentPolicy } from "../app/webui/static/assignment-policy.mjs";

class Element {
  constructor() { this.value = ""; this.text = ""; this.listeners = {}; this.disabled = false; }
  set textContent(value) { this.text = value; }
  get textContent() { return this.text; }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  addEventListener(event, fn) { this.listeners[event] = fn; }
}

function setup({ permissions = ["assignment-policy:manage"], confirmImpl = () => true } = {}) {
  const ids = [
    "assignment-policy-config", "assignment-policy-state", "assignment-policy-results",
    "assignment-policy-save", "assignment-policy-disable", "assignment-policy-preview",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element()]));
  const calls = [];
  const policy = { enabled: false, allowed_provider_ids: [], online_enabled: false,
    budget_limit: null, budget_unit: null, candidates: [] };
  const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
  const fetchImpl = async (path, options = {}) => {
    calls.push({ path, options });
    if (path === "/api/local/session") return response({ csrf: "csrf-token", permissions });
    if (path === "/api/local/assignment-policy" && options.method === "PUT") {
      Object.assign(policy, JSON.parse(options.body));
      return response(structuredClone(policy));
    }
    if (path === "/api/local/assignment-policy" && options.method === "DELETE") {
      policy.enabled = false;
      return response(structuredClone(policy));
    }
    if (path === "/api/local/assignment-policy") return response(structuredClone(policy));
    if (path.endsWith("/preview")) {
      return response({ enabled: policy.enabled, assignments: [], safe: "<script>inert</script>" });
    }
    throw new Error(`Unexpected request: ${path}`);
  };
  const mounted = mountAssignmentPolicy({
    documentRef: { getElementById: (id) => elements[id] },
    fetchImpl,
    confirmImpl,
  });
  return { elements, calls, mounted };
}

test("owner enables, previews, and disables recommendations with same-origin CSRF", async () => {
  const ui = setup();
  await ui.mounted;
  assert.equal(ui.calls.length, 3);
  ui.elements["assignment-policy-config"].value = JSON.stringify({
    enabled: true,
    allowed_provider_ids: ["local"],
    online_enabled: false,
    budget_limit: "1",
    budget_unit: "owner units",
    candidates: [],
  });
  await ui.elements["assignment-policy-save"].listeners.click();
  const put = ui.calls.find((call) => call.options.method === "PUT");
  assert.equal(put.options.credentials, "same-origin");
  assert.equal(put.options.headers["X-Local-CSRF"], "csrf-token");
  assert.equal(JSON.parse(put.options.body).enabled, true);
  assert.match(ui.elements["assignment-policy-results"].textContent, /<script>inert<\/script>/);
  assert.equal(ui.elements["assignment-policy-results"].innerHTML, undefined);
  await ui.elements["assignment-policy-disable"].listeners.click();
  const deletion = ui.calls.find((call) => call.options.method === "DELETE");
  assert.equal(deletion.options.headers["X-Local-CSRF"], "csrf-token");
  assert.match(ui.elements["assignment-policy-state"].textContent, /unchanged/);
});

test("declined enable and read-only sessions cannot mutate the policy", async () => {
  const declined = setup({ confirmImpl: () => false });
  await declined.mounted;
  declined.elements["assignment-policy-config"].value = JSON.stringify({ enabled: true });
  await declined.elements["assignment-policy-save"].listeners.click();
  assert.equal(declined.calls.some((call) => call.options.method === "PUT"), false);
  await declined.elements["assignment-policy-disable"].listeners.click();
  assert.equal(declined.calls.some((call) => call.options.method === "DELETE"), false);
  assert.match(declined.elements["assignment-policy-state"].textContent, /Policy was retained/);

  const readOnly = setup({ permissions: ["assignment-policy:read"] });
  await readOnly.mounted;
  assert.equal(readOnly.elements["assignment-policy-config"].disabled, true);
  assert.equal(readOnly.elements["assignment-policy-save"].disabled, true);
});

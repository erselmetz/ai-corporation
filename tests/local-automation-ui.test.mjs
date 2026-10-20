import test from "node:test";
import assert from "node:assert/strict";
import { createAutomationApprovalFlow } from "../app/webui/static/local-automation.mjs";

const action = { action: "click", url: "https://example.org/", role: "button", name: "Continue", value: null };

test("automation UI confirms the exact preview and executes only after digest approval", async () => {
  const calls = [];
  const statuses = [];
  const request = async (path, options = {}) => {
    calls.push({ path, options });
    if (path.endsWith("/preview")) return { action: "click", target_label: "Continue", target_digest: "t" };
    if (path.endsWith("/request-approval")) return { approval: {
      approval_id: "a".repeat(32), approval_digest: "d".repeat(64), action_summary: "click button Continue",
      target_ref: "browser:example.org", payload_digest: "p".repeat(64), target_digest: "t".repeat(64), expires_at: "soon",
    } };
    if (path.endsWith("/execute")) return { status: "action_dispatched", remote_outcome: "unknown" };
    return { status: "approved" };
  };
  const flow = createAutomationApprovalFlow({ request, confirmImpl: message => {
    assert.match(message, /Exact request:.*https:\/\/example\.org/);
    assert.match(message, /d{64}/);
    return true;
  }, onStatus: message => statuses.push(message) });
  const result = await flow("browser", action);
  assert.equal(result.remote_outcome, "unknown");
  assert.deepEqual(calls.map(call => call.path), [
    "/api/local/automation/browser/preview",
    "/api/local/automation/browser/request-approval",
    `/api/capabilities/approvals/${"a".repeat(32)}/approve`,
    "/api/local/automation/browser/execute",
  ]);
  assert.equal(calls[2].options.body.confirmed_digest, "d".repeat(64));
  assert.equal(calls[3].options.body.approval_id, "a".repeat(32));
  assert.match(statuses.at(-1), /unknown/);
});

test("declining exact action approval never calls approve or execute", async () => {
  const calls = [];
  const request = async path => {
    calls.push(path);
    if (path.endsWith("/preview")) return { action: "click", target_label: "Continue" };
    return { approval: { approval_id: "b".repeat(32), approval_digest: "e".repeat(64),
      action_summary: "click button Continue", target_ref: "browser:example.org", payload_digest: "p",
      target_digest: "t", expires_at: "soon" } };
  };
  const flow = createAutomationApprovalFlow({ request, confirmImpl: () => false });
  assert.deepEqual(await flow("browser", action), { state: "cancelled" });
  assert.deepEqual(calls, ["/api/local/automation/browser/preview", "/api/local/automation/browser/request-approval"]);
});

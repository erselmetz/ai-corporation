import assert from "node:assert/strict";
import test from "node:test";
import { mountWorkflows } from "../app/webui/static/workflows.mjs";

class El {
  constructor() { this.children = []; this.text = ""; }
  set textContent(v) { this.text = v; this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join("|"); }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(n) { this.children.push(n); }
  replaceChildren() { this.children = []; }
}
const setup = () => {
  const els = { "workflow-status": new El(), "workflow-list": new El() };
  return { els, doc: { getElementById: id => els[id], createElement: () => new El() } };
};

test("renders verified workflow state as text only", async () => {
  const { els, doc } = setup();
  const workflows = [{
    title: "<img src=x onerror=alert(1)>", state: "review", paused: false, owner_approved: false,
    preference: "local_first", fallback_enabled: false, spend_ceiling_cents: null, spent_cents: 0,
    items: [{ role: "worker", id: "i1", agent_id: "a", state: "review", reason: "Awaiting review" }],
    handoffs: [{ from: "i0", to: "i1" }],
  }];
  await mountWorkflows({ documentRef: doc, fetchImpl: async () => ({ ok: true, json: async () => ({ workflows }) }) });
  const text = els["workflow-list"].textContent;
  assert.match(text, /Owner approved: no/);
  assert.match(text, /Spend ceiling: UNKNOWN/);
  assert.match(text, /Cancellation: unsupported/);
  assert.match(text, /Handoff i0 -> i1/);
});

test("reports sign-in requirement without data", async () => {
  const { els, doc } = setup();
  await mountWorkflows({ documentRef: doc, fetchImpl: async () => ({ ok: false }) });
  assert.match(els["workflow-status"].textContent, /Sign in/);
});

import assert from "node:assert/strict";
import test from "node:test";
import { mountWorkflowMap } from "../app/webui/static/workflow-map.mjs";

class El {
  constructor(tag = "div") { this.tag = tag; this.children = []; this.text = ""; this.handlers = {}; }
  set textContent(v) { this.text = v; this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join("|"); }
  set innerHTML(_) { throw new Error("HTML injection is forbidden"); }
  append(n) { this.children.push(n); }
  replaceChildren() { this.children = []; }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  all(tag) { return this.children.flatMap(c => [...(c.tag === tag ? [c] : []), ...c.all(tag)]); }
}
const setup = () => {
  const els = Object.fromEntries(["workflow-map-status", "workflow-map-refresh", "workflow-map-list",
    "workflow-map-org", "workflow-map-detail"].map(id => [id, new El()]));
  return { els, doc: { getElementById: id => els[id], createElement: tag => new El(tag) } };
};
const node = (id, extra = {}) => ({
  id, role: "worker", state: "review", depth: 1, attempts: 1, agent_id: "w1", agent_visibility: "available",
  destination_id: "d1", reason: "", uncertain: false, output_recorded: true, review: null, approval: null, ...extra,
});
const snap = (nodes, extra = {}) => ({
  generated_at: "2026-01-01T00:00:00+00:00", stale_after_seconds: 60,
  workflows: [{ id: "w", title: "<b>Plan</b>", state: "review", paused: false, owner_approved: false, nodes,
    operational_edges: nodes.length > 1 ? [{ kind: "handoff", from: nodes[0].id, to: nodes[1].id }] : [], events: [] }],
  organization: { state: "available", positions: [{ id: "p1", title: "Boss" }, { id: "p2", title: "Dev" }],
    reporting_edges: [{ kind: "reporting", from: "p2", to: "p1" }] }, ...extra,
});
const ok = body => ({ ok: true, status: 200, json: async () => body });
const now = () => Date.parse("2026-01-01T00:00:10+00:00");

test("keeps operational links and reporting links in separate lists", async () => {
  const { els, doc } = setup();
  await mountWorkflowMap({ documentRef: doc, nowImpl: now, fetchImpl: async () => ok(snap([node("a"), node("b")])) });
  assert.match(els["workflow-map-list"].textContent, /Operational handoff: a -> b/);
  assert.doesNotMatch(els["workflow-map-list"].textContent, /reports to/);
  assert.match(els["workflow-map-org"].textContent, /Dev reports to Boss/);
  assert.doesNotMatch(els["workflow-map-org"].textContent, /handoff/);
  assert.equal(els["workflow-map-list"].all("button").length, 2);
  assert.doesNotMatch(els["workflow-map-status"].textContent, /Stale/);
});

test("flags stale snapshots and distinguishes empty data", async () => {
  const { els, doc } = setup();
  const late = () => Date.parse("2026-01-01T00:05:00+00:00");
  await mountWorkflowMap({ documentRef: doc, nowImpl: late, fetchImpl: async () => ok(snap([node("a")])) });
  assert.match(els["workflow-map-status"].textContent, /Stale: 300s old/);
  const empty = setup();
  await mountWorkflowMap({ documentRef: empty.doc, nowImpl: now, fetchImpl: async () => ok(snap([], { workflows: [] })) });
  assert.match(empty.els["workflow-map-status"].textContent, /No workflows in this app run/);
});

test("selection shows current evidence and reflects state changes", async () => {
  const { els, doc } = setup();
  let current = node("a");
  const api = await mountWorkflowMap({ documentRef: doc, nowImpl: now, fetchImpl: async () => ok(snap([current])) });
  await api.select("w", "a");
  assert.match(els["workflow-map-detail"].textContent, /Review: none recorded/);
  current = node("a", { state: "approved", review: { passed: true, evidence: "checked", at: "T" },
    approval: { evidence: "ran tests", at: "T2" } });
  await api.refresh();
  assert.match(els["workflow-map-detail"].textContent, /Review passed at T: checked/);
  assert.match(els["workflow-map-detail"].textContent, /Owner approval at T2: ran tests/);
});

test("forbidden agents and reporting data are labelled", async () => {
  const { els, doc } = setup();
  const data = snap([node("a", { agent_id: null, destination_id: null, agent_visibility: "forbidden" })],
    { organization: { state: "forbidden", positions: [], reporting_edges: [] } });
  const api = await mountWorkflowMap({ documentRef: doc, nowImpl: now, fetchImpl: async () => ok(data) });
  await api.select("w", "a");
  assert.match(els["workflow-map-detail"].textContent, /Agent: Forbidden/);
  assert.match(els["workflow-map-org"].textContent, /Reporting links: Forbidden/);
});

test("disconnect keeps the last snapshot marked stale; errors show no data", async () => {
  const { els, doc } = setup();
  let down = false;
  const api = await mountWorkflowMap({ documentRef: doc, nowImpl: now, fetchImpl: async () => {
    if (down) throw new Error("net");
    return ok(snap([node("a")]));
  } });
  down = true;
  await api.refresh();
  assert.match(els["workflow-map-status"].textContent, /Disconnected.*last snapshot from .* \(stale\)/);
  assert.equal(els["workflow-map-list"].all("button").length, 1);
  for (const [status, re] of [[401, /Sign in/], [403, /lacks permission/], [500, /could not be loaded/]]) {
    const fresh = setup();
    await mountWorkflowMap({ documentRef: fresh.doc, fetchImpl: async () => ({ ok: false, status }) });
    assert.match(fresh.els["workflow-map-status"].textContent, re);
    assert.equal(fresh.els["workflow-map-list"].children.length, 0);
  }
});
import assert from "node:assert/strict";
import test from "node:test";
import { mountStructure } from "../app/webui/static/structure.mjs";

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
  const els = Object.fromEntries(["structure-status", "structure-refresh", "structure-tree", "structure-detail"]
    .map(id => [id, new El()]));
  return { els, doc: { getElementById: id => els[id], createElement: tag => new El(tag) } };
};
const pos = (id, extra = {}) => ({
  id, title: id, responsibilities: ["r"], active: true, revision: 1, reports_to_position_id: null,
  reporting_state: "root", employee: { state: "unassigned" }, agent: { state: "not_applicable" }, ...extra,
});
const map = (positions, sections = { positions: "available", employees: "available", agents: "available" }) =>
  ({ ok: true, status: 200, json: async () => ({ generated_at: "T", sections, positions, roots: [] }) });

test("renders a keyboard-reachable tree with explicit missing and forbidden labels", async () => {
  const { els, doc } = setup();
  const data = [
    pos("<b>boss</b>", { employee: { state: "forbidden", id: "x" } }),
    pos("child", { reports_to_position_id: "<b>boss</b>", reporting_state: "linked", employee: { state: "missing", id: "g" } }),
  ];
  await mountStructure({ documentRef: doc, fetchImpl: async () => map(data, { positions: "available", employees: "forbidden", agents: "forbidden" }) });
  const buttons = els["structure-tree"].all("button");
  assert.equal(buttons.length, 2);
  assert.ok(buttons.every(b => b.type === "button"));
  assert.match(els["structure-tree"].textContent, /forbidden \(permission not granted\)/);
  assert.match(els["structure-tree"].textContent, /missing record/);
  assert.match(els["structure-status"].textContent, /Not permitted: employees, agents/);
});

test("selecting shows current details and flags stale revision or vanished positions", async () => {
  const { els, doc } = setup();
  let revision = 1; let gone = false;
  const fetchImpl = async () => map(gone ? [] : [pos("p", { revision })]);
  const api = await mountStructure({ documentRef: doc, fetchImpl });
  revision = 2;
  await api.select("p");
  assert.match(els["structure-detail"].textContent, /Stale list/);
  assert.match(els["structure-detail"].textContent, /revision 2/);
  gone = true;
  await api.select("p");
  assert.match(els["structure-detail"].textContent, /no longer exists/);
});

test("reports sign-in and permission failures without data", async () => {
  for (const [status, re] of [[401, /Sign in/], [403, /lacks permission/]]) {
    const { els, doc } = setup();
    await mountStructure({ documentRef: doc, fetchImpl: async () => ({ ok: false, status }) });
    assert.match(els["structure-status"].textContent, re);
    assert.equal(els["structure-tree"].children.length, 0);
  }
});

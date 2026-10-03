import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { createDocumentationServer } from "../server.mjs";
import { taskGroups, tasks } from "../tasks-data.mjs";

const pages = [
  "index.html",
  "documentation.html",
  "architecture.html",
  "organization.html",
  "how-it-works.html",
  "integrations.html",
  "security.html",
  "roadmap.html",
  "tasks.html",
  "updates.html",
  "about.html",
];

let server;
let baseUrl;

before(async () => {
  server = createDocumentationServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert.ok(address && typeof address === "object");
  baseUrl = `http://127.0.0.1:${address.port}`;
});

after(async () => {
  if (server?.listening) {
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

describe("documentation site", () => {
  it("serves every page and navigation links target existing pages", async () => {
    for (const filename of pages) {
      const response = await fetch(`${baseUrl}/${filename}`);
      assert.equal(response.status, 200, `${filename} should load`);
      assert.match(response.headers.get("content-type") ?? "", /text\/html/);
      const html = await response.text();
      for (const target of pages) {
        assert.ok(html.includes(`href="${target}"`), `${filename} should link to ${target}`);
      }
    }
  });

  it("serves required page assets and does not expose paths outside the allowlist", async () => {
    for (const asset of ["site.css", "tasks-data.mjs", "tasks-page.js"]) {
      assert.equal((await fetch(`${baseUrl}/${asset}`)).status, 200);
    }
    assert.equal((await fetch(`${baseUrl}/../README.md`)).status, 404);
    assert.equal((await fetch(`${baseUrl}/README.md`)).status, 404);
  });

  it("contains exactly tasks 1–100 in the requested category ranges", () => {
    assert.equal(tasks.length, 100);
    assert.deepEqual(tasks.map((task) => task.number), Array.from({ length: 100 }, (_, i) => i + 1));
    assert.deepEqual(taskGroups.map((group) => group.tasks.length), [25, 11, 18, 6, 7, 7, 11, 10, 5]);
  });

  it("marks exactly tasks 1–98 complete and all later tasks planned", () => {
    assert.ok(tasks.slice(0, 98).every((task) => task.status === "completed"));
    assert.ok(tasks.slice(98).every((task) => task.status === "planned"));
    assert.equal(tasks[51].number, 52);
    assert.equal(tasks[51].title, "Activity / Logs UI");
    assert.equal(tasks[51].status, "completed");
    assert.equal(tasks[78].title, "Automated Patch Development");
    assert.equal(tasks[78].description, "Develop proposed changes in an isolated, disposable work area.");
    assert.equal(tasks[78].status, "completed");
    assert.equal(tasks[79].title, "Automated Testing Workflow");
    assert.equal(tasks[79].description, "Run explicitly selected tests and report the actual results for a proposed change.");
    assert.equal(tasks[79].status, "completed");
    assert.equal(tasks[80].title, "Automated Code Review");
    assert.equal(tasks[80].description, "Review proposed changes for correctness, regressions, and policy compliance.");
    assert.equal(tasks[80].status, "completed");
    assert.equal(tasks[81].title, "Maintenance Sandbox");
    assert.equal(tasks[81].description, "Keep maintenance experiments isolated from the active Corporation and host state.");
    assert.equal(tasks[81].status, "completed");
    assert.equal(tasks[82].title, "Human Approval Workflow");
    assert.equal(tasks[82].description, "Require explicit human review and approval before protected changes are applied.");
    assert.equal(tasks[82].status, "completed");
    assert.equal(tasks[83].title, "Git Checkpoint Integration");
    assert.equal(tasks[83].status, "completed");
    assert.equal(tasks[84].title, "Controlled Self-Maintenance");
    assert.equal(tasks[84].description, "Orchestrate a bounded, auditable maintenance flow without unrestricted self-modification.");
    assert.equal(tasks[84].status, "completed");
    assert.equal(tasks[85].title, "MCP Integration");
    assert.equal(tasks[85].status, "completed");
    assert.equal(tasks[86].title, "GitHub Integration");
    assert.equal(tasks[86].status, "completed");
    assert.equal(tasks[87].title, "Browser/Web Research Capability");
    assert.equal(tasks[87].status, "completed");
    assert.equal(tasks[88].title, "Coding Tool Integration");
    assert.equal(tasks[88].status, "completed");
    assert.equal(tasks[89].title, "Computer-Use Capability");
    assert.equal(tasks[89].description, "Explore permissioned computer interaction with explicit user-visible safeguards.");
    assert.equal(tasks[89].status, "completed");
    assert.equal(tasks[90].title, "External Service Integration");
    assert.equal(tasks[90].description, "Connect selected services through scoped credentials and auditable adapters.");
    assert.equal(tasks[90].status, "completed");
    assert.equal(tasks[91].title, "Capability Registry");
    assert.equal(tasks[91].description, "Describe available capabilities, ownership, requirements, and policy boundaries.");
    assert.equal(tasks[91].status, "completed");
    assert.equal(tasks[92].title, "Capability Discovery");
    assert.equal(tasks[92].description, "Identify candidate capabilities without granting or activating them automatically.");
    assert.equal(tasks[92].status, "completed");
    assert.equal(tasks[93].title, "Capability Evaluation");
    assert.equal(tasks[93].description, "Evaluate evidence, risks, fit, and operational requirements before adoption.");
    assert.equal(tasks[93].status, "completed");
    assert.equal(tasks[94].title, "Controlled Capability Integration");
    assert.equal(tasks[94].description, "Integrate approved capabilities through testing, review, and explicit change control.");
    assert.equal(tasks[94].status, "completed");
    assert.equal(tasks[95].title, "Corporation Planning System");
    assert.equal(tasks[95].description, "Support transparent organization-level planning with traceable priorities and constraints.");
    assert.equal(tasks[95].status, "completed");
    assert.equal(tasks[96].title, "Organization-Level Orchestration");
    assert.equal(tasks[96].description, "Coordinate work across organizational responsibilities and approved workflows.");
    assert.equal(tasks[96].status, "completed");
    assert.equal(tasks[97].title, "Adaptive Workforce");
    assert.equal(tasks[97].description, "Adjust organizational capacity and role assignments under explicit governance.");
    assert.equal(tasks[97].status, "completed");
    assert.deepEqual(
      tasks.slice(52, 98).map(({ number, status }) => [number, status]),
      Array.from({ length: 46 }, (_, index) => [index + 53, "completed"]),
    );
  });

  it("describes the current completed and planned ranges on the roadmap page", async () => {
    const response = await fetch(`${baseUrl}/tasks.html`);
    const html = await response.text();
    assert.match(html, /Milestones 1–98 are completed foundations/);
    assert.match(html, /Tasks 99–100 remain planned/);
  });

  it("serves only read methods", async () => {
    const response = await fetch(baseUrl, { method: "POST" });
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("allow"), "GET, HEAD");
  });
});

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

  it("marks exactly tasks 1–43 complete and all later tasks planned", () => {
    assert.ok(tasks.slice(0, 43).every((task) => task.status === "completed"));
    assert.ok(tasks.slice(43).every((task) => task.status === "planned"));
    assert.equal(tasks[42].number, 43);
    assert.equal(tasks[43].number, 44);
  });

  it("serves only read methods", async () => {
    const response = await fetch(baseUrl, { method: "POST" });
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("allow"), "GET, HEAD");
  });
});

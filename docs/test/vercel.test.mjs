import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, readdir } from "node:fs/promises";
import { test } from "node:test";
import handler from "../server.mjs";

test("Vercel default export serves public assets and preserves read-only boundaries", async () => {
  assert.equal(typeof handler, "function");
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const baseUrl = `http://127.0.0.1:${server.address().port}`;
    const filenames = await readdir(new URL("../", import.meta.url));
    const assets = filenames.filter((name) => name.endsWith(".html"));
    assets.push("site.css", "tasks-data.mjs", "tasks-page.js");
    for (const asset of ["", ...assets]) {
      const response = await fetch(`${baseUrl}/${asset}`);
      assert.equal(response.status, 200, `${asset || "/"} should load`);
      assert.equal(response.headers.get("x-content-type-options"), "nosniff");
      assert.ok(response.headers.get("content-security-policy"));
      assert.ok((await response.text()).length > 0);
    }
    const head = await fetch(baseUrl, { method: "HEAD" });
    assert.equal(head.status, 200);
    assert.ok(Number(head.headers.get("content-length")) > 0);
    assert.equal(await head.text(), "");
    const post = await fetch(baseUrl, { method: "POST" });
    assert.equal(post.status, 405);
    assert.equal(post.headers.get("allow"), "GET, HEAD");
    await post.text();
    for (const privatePath of ["server.mjs", "vercel.json", "package.json", "../README.md", "app", "api/tasks"]) {
      const response = await fetch(`${baseUrl}/${privatePath}`);
      assert.equal(response.status, 404, `${privatePath} must not be public`);
      await response.text();
    }
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
      server.closeAllConnections();
    });
  }
});

test("Vercel function bundle explicitly includes the public file assets", async () => {
  const config = JSON.parse(await readFile(new URL("../vercel.json", import.meta.url), "utf8"));
  const build = config.builds.find(({ src }) => src === "server.mjs");
  assert.equal(build.use, "@vercel/node");
  assert.deepEqual(build.config.includeFiles, ["*.html", "site.css", "tasks-data.mjs", "tasks-page.js"]);
});

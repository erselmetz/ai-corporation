import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const siteRoot = path.dirname(fileURLToPath(import.meta.url));
const publicFiles = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ...[
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
  ].map((name) => [`/${name}`, [name, "text/html; charset=utf-8"]]),
  ["/site.css", ["site.css", "text/css; charset=utf-8"]],
  ["/tasks-data.mjs", ["tasks-data.mjs", "text/javascript; charset=utf-8"]],
  ["/tasks-page.js", ["tasks-page.js", "text/javascript; charset=utf-8"]],
]);

export function createDocumentationServer() {
  return createServer(async (request, response) => {
    if (request.method !== "GET" && request.method !== "HEAD") {
      response.writeHead(405, { Allow: "GET, HEAD" });
      response.end("Method not allowed");
      return;
    }

    const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
    const asset = publicFiles.get(pathname);
    if (!asset) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }

    try {
      const [filename, contentType] = asset;
      const body = await readFile(path.join(siteRoot, filename));
      response.writeHead(200, {
        "Content-Type": contentType,
        "Content-Length": body.length,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy":
          "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'",
      });
      response.end(request.method === "HEAD" ? undefined : body);
    } catch (error) {
      console.error("Unable to serve documentation file:", error);
      response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Unable to serve documentation");
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT ?? 3000);
  const host = process.env.HOST ?? "0.0.0.0";
  const server = createDocumentationServer();
  server.listen(port, host, () => {
    console.log(`Documentation website listening on http://${host}:${port}`);
  });
}

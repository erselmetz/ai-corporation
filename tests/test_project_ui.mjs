import assert from "node:assert/strict";
import test from "node:test";

import { mountProjectPage } from "../app/webui/static/projects.mjs";

function response(status, payload) {
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() {
      return payload;
    },
  };
}

class Element {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.listeners = new Map();
    this.attributes = {};
    this.value = "";
    this.text = "";
    this.hidden = false;
    this.disabled = false;
    this.className = "";
    this.name = "";
  }

  get textContent() {
    return this.text + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this.text = String(value);
    this.children = [];
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.text = "";
    this.children = children;
  }

  setAttribute(name, value) {
    this.attributes[name] = value;
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  reset() {
    for (const field of this.formFields ?? []) field.value = "";
  }
}

function pageElements() {
  const ids = [
    "project-list",
    "project-list-state",
    "project-refresh",
    "project-detail",
    "project-detail-state",
    "project-create-form",
    "project-name",
    "project-description",
    "project-create-submit",
    "project-create-state",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element("div")]));
  elements["project-create-form"].formFields = [
    elements["project-name"],
    elements["project-description"],
  ];
  const documentRef = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements[id],
  };
  return { documentRef, elements };
}

const project = {
  id: "project-1",
  name: "Research",
  description: "Research project description.",
  status: "active",
};

test("loads project list and details through the existing protected APIs", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      if (path === "/api/projects") return response(200, { items: [project] });
      return response(200, project);
    },
  });

  await controller.initialLoad;
  assert.equal(calls[0][0], "/api/projects");
  assert.equal(calls[0][1].credentials, "same-origin");
  assert.equal(elements["project-list"].children.length, 1);
  assert.match(elements["project-list"].textContent, /Research.*active.*project-1/);

  assert.equal(await controller.loadProjectDetail(project.id), true);
  assert.ok(calls.some(([path]) => path === "/api/projects/project-1"));
  assert.match(elements["project-detail"].textContent, /Research project description/);
  assert.match(elements["project-detail"].textContent, /active/);
});

test("creates only name and description, then refreshes and loads returned project through API", async () => {
  const { documentRef, elements } = pageElements();
  elements["project-name"].value = "New Project";
  elements["project-description"].value = "New project details";
  const calls = [];
  const createdProject = {
    id: "PROJECT-2",
    name: "New Project",
    description: "New project details",
    status: "active",
  };
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (options.method === "POST") return response(201, createdProject);
      if (path === "/api/projects") return response(200, { items: [project, createdProject] });
      if (path === "/api/projects/PROJECT-2") return response(200, createdProject);
      return response(200, project);
    },
  });
  await controller.initialLoad;
  await controller.createProject({ preventDefault() {} });

  const [createPath, createOptions] = calls.find(([, options]) => options.method === "POST");
  assert.equal(createPath, "/api/projects");
  assert.deepEqual(JSON.parse(createOptions.body), {
    name: "New Project",
    description: "New project details",
  });
  assert.deepEqual(createOptions.headers, {
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  assert.equal(createOptions.credentials, "same-origin");
  assert.ok(calls.some(([path], index) => path === "/api/projects" && index > 1));
  assert.ok(calls.some(([path]) => path === "/api/projects/PROJECT-2"));
  assert.equal(elements["project-list"].children.length, 2);
  assert.match(elements["project-detail"].textContent, /New Project/);
  assert.match(elements["project-create-state"].textContent, /loaded from the API/);
});

test("prevents duplicate Project submissions while the first request is pending", async () => {
  const { documentRef, elements } = pageElements();
  elements["project-name"].value = "Only once";
  let release;
  let submissions = 0;
  const created = { ...project, id: "PROJECT-2", name: "Only once" };
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (options.method === "POST") {
        submissions += 1;
        return new Promise((resolve) => {
          release = () => resolve(response(201, created));
        });
      }
      if (path === "/api/projects") return response(200, { items: [created] });
      return response(200, created);
    },
  });
  await controller.initialLoad;
  const first = controller.createProject({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(elements["project-create-submit"].disabled, true);
  await controller.createProject({ preventDefault() {} });
  assert.equal(submissions, 1);
  release();
  await first;
});

test("rejects blank names locally while allowing an omitted description", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  let submissions = 0;
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (options.method === "POST") {
        submissions += 1;
        return response(201, project);
      }
      if (path === "/api/projects") return response(200, { items: [project] });
      return response(200, project);
    },
  });
  await controller.initialLoad;
  await controller.createProject({ preventDefault() {} });
  assert.match(elements["project-create-state"].textContent, /name is required/i);
  assert.equal(submissions, 0);

  elements["project-name"].value = "Research";
  await controller.createProject({ preventDefault() {} });
  const [, createOptions] = calls.find(([, options]) => options.method === "POST");
  assert.equal(submissions, 1);
  assert.match(elements["project-create-state"].textContent, /created/i);
  assert.deepEqual(JSON.parse(createOptions.body), { name: "Research", description: "" });
});

test("clears selected details and stale list entry when a Project detail returns 404", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path) => {
      if (path === "/api/projects") return response(200, { items: [project] });
      if (path === "/api/projects/project-1") return response(404);
      return response(200, project);
    },
  });
  await controller.initialLoad;
  assert.equal(await controller.loadProjectDetail(project.id), false);
  assert.equal(elements["project-detail"].hidden, true);
  assert.match(elements["project-detail-state"].textContent, /no longer exists/i);
  assert.equal(elements["project-list"].children.length, 0);
});

test("clears cached Project list and selected details when a refresh fails", async () => {
  const { documentRef, elements } = pageElements();
  let fail = false;
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path) => {
      if (path === "/api/projects") {
        return fail ? response(503) : response(200, { items: [project] });
      }
      return response(200, project);
    },
  });
  await controller.initialLoad;
  await controller.loadProjectDetail(project.id);
  assert.equal(elements["project-list"].children.length, 1);
  assert.equal(elements["project-detail"].hidden, false);

  fail = true;
  assert.equal(await controller.loadProjects(), false);
  assert.equal(elements["project-list"].children.length, 0);
  assert.equal(elements["project-detail"].hidden, true);
  assert.match(elements["project-list-state"].textContent, /could not be completed/);
  assert.doesNotMatch(elements["project-list-state"].textContent, /No projects found/);
});

test("distinguishes authentication, authorization, conflict, validation, not-found and server errors", async () => {
  const { documentRef, elements } = pageElements();
  let listResponse = response(401);
  let createResponse = response(409);
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (options.method === "POST") return createResponse;
      if (path === "/api/projects") return listResponse;
      if (path === "/api/projects/project-1") return response(404);
      return response(500);
    },
  });
  await controller.initialLoad;
  assert.match(elements["project-list-state"].textContent, /Sign-in required/);

  listResponse = response(403);
  await controller.loadProjects();
  assert.match(elements["project-list-state"].textContent, /Access denied/);

  elements["project-name"].value = "Duplicate";
  await controller.createProject({ preventDefault() {} });
  assert.match(elements["project-create-state"].textContent, /conflicts/);

  createResponse = response(422, {
    detail: [{ loc: ["body", "name"], msg: "Project name cannot be blank", input: "" }],
  });
  await controller.createProject({ preventDefault() {} });
  assert.match(elements["project-create-state"].textContent, /name: Project name cannot be blank/);
  assert.doesNotMatch(elements["project-create-state"].textContent, /input/);

  createResponse = response(500);
  await controller.createProject({ preventDefault() {} });
  assert.match(elements["project-create-state"].textContent, /could not be completed/);

  createResponse = response(404);
  await controller.createProject({ preventDefault() {} });
  assert.match(elements["project-create-state"].textContent, /Project API returned not found/);

  listResponse = response(200, { items: [project] });
  await controller.loadProjects();
  assert.equal(await controller.loadProjectDetail(project.id), false);
  assert.match(elements["project-detail-state"].textContent, /no longer exists/);
});

test("renders successful empty collections separately from failed responses", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async () => response(200, { items: [] }),
  });
  await controller.initialLoad;
  assert.equal(elements["project-list-state"].textContent, "No projects found.");
  assert.equal(elements["project-list"].children.length, 0);
});

test("network failures are explicit and never rendered as an empty Project list", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async () => {
      throw new Error("network details must not be shown");
    },
  });
  await controller.initialLoad;
  assert.match(elements["project-list-state"].textContent, /could not be loaded/i);
  assert.doesNotMatch(elements["project-list-state"].textContent, /No projects found/);
  assert.doesNotMatch(elements["project-list-state"].textContent, /network details/);
});

test("Project UI exposes no unsupported deletion or lifecycle actions", async () => {
  const { documentRef } = pageElements();
  const calls = [];
  const controller = mountProjectPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (path === "/api/projects") return response(200, { items: [] });
      return response(200, project);
    },
  });
  await controller.initialLoad;
  assert.equal("deleteProject" in controller, false);
  assert.equal(calls.some(([, options]) => ["DELETE", "PATCH", "PUT"].includes(options.method)), false);
});

test("browser Project module has no credentials or direct internal-layer access", async () => {
  const { readFile } = await import("node:fs/promises");
  const source = await readFile(new URL("../app/webui/static/projects.mjs", import.meta.url), "utf8");
  assert.match(source, /\/api\/projects/);
  assert.doesNotMatch(source, /Bearer\s|api_key|password|secret|process\.env|os\.environ/i);
  assert.doesNotMatch(source, /ProjectRegistry|TaskRegistry|Orchestrator|ProviderRegistry|Ollama|sqlite|filesystem|database/i);
  assert.doesNotMatch(source, /method:\s*["']DELETE["']/);
});

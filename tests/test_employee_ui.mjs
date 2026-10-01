import assert from "node:assert/strict";
import test from "node:test";

import { mountEmployeeManagementPage } from "../app/webui/static/employees.mjs";

function response(status, payload) {
  return {
    status,
    ok: status >= 200 && status < 300,
    payload,
    async json() {
      return payload;
    },
  };
}

class Element {
  constructor(tagName, id = "") {
    this.tagName = tagName;
    this.id = id;
    this.children = [];
    this.listeners = new Map();
    this.attributes = {};
    this.value = "";
    this.text = "";
    this.hidden = false;
    this.disabled = false;
    this.className = "";
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

  async dispatch(type, event = {}) {
    for (const listener of this.listeners.get(type) ?? []) {
      await listener({
        preventDefault() {},
        ...event,
      });
    }
  }

  querySelector(selector) {
    if (selector.startsWith(".")) {
      const className = selector.slice(1);
      return findElement(this, (node) => node.className === className);
    }
    return null;
  }

  reset() {
    for (const field of this.formFields) field.value = "";
  }
}

function findElement(root, predicate) {
  for (const child of root.children) {
    if (predicate(child)) return child;
    const nested = findElement(child, predicate);
    if (nested) return nested;
  }
  return null;
}

function pageElements() {
  const ids = [
    "employee-list",
    "employee-list-state",
    "employee-detail",
    "employee-detail-state",
    "employee-refresh",
    "employee-create-form",
    "employee-create-submit",
    "employee-create-state",
    "employee-id",
    "employee-name",
    "employee-role",
    "employee-responsibilities",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element("div", id)]));
  elements["employee-create-form"].formFields = [
    elements["employee-id"],
    elements["employee-name"],
    elements["employee-role"],
    elements["employee-responsibilities"],
  ];
  const documentRef = {
    createElement: (tagName) => new Element(tagName),
    getElementById: (id) => elements[id],
  };
  return { documentRef, elements };
}

const employee = {
  id: "employee-1",
  name: "Avery Example",
  role: "Operations",
  responsibilities: ["Coordinate work"],
  agent_id: null,
};

test("lists employees and requests details using the existing response fields", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  const controller = mountEmployeeManagementPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      if (path === "/api/employees") return response(200, { items: [employee] });
      return response(200, employee);
    },
    confirmImpl: () => false,
  });

  await controller.initialLoad;
  const selectButton = elements["employee-list"].children[0].children[0];
  await selectButton.dispatch("click");

  assert.deepEqual(calls.map(([path]) => path), [
    "/api/employees",
    "/api/employees/employee-1",
  ]);
  assert.equal(calls[1][1].credentials, "same-origin");
  assert.match(elements["employee-detail"].textContent, /Avery Example/);
  assert.match(elements["employee-detail"].textContent, /Operations/);
  assert.match(elements["employee-detail"].textContent, /Coordinate work/);
  assert.match(elements["employee-detail"].textContent, /Not associated/);
  assert.equal(elements["employee-detail"].hidden, false);
});

test("creates only API-supported fields, prevents duplicate submits, refreshes and selects created employee", async () => {
  const { documentRef, elements } = pageElements();
  elements["employee-id"].value = "employee-2";
  elements["employee-name"].value = "Morgan Example";
  elements["employee-role"].value = "Coordinator";
  elements["employee-responsibilities"].value = "Plan work\nSupport teams";
  const createResponse = response(201, {
    ...employee,
    id: "employee-2",
    name: "Morgan Example",
    role: "Coordinator",
    responsibilities: ["Plan work", "Support teams"],
  });
  let releaseCreate;
  let postCount = 0;
  const calls = [];
  const controller = mountEmployeeManagementPage({
    documentRef,
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      if (options.method === "POST") {
        postCount += 1;
        return new Promise((resolve) => {
          releaseCreate = () => resolve(createResponse);
        });
      }
      if (path === "/api/employees") {
        return response(200, {
          items: calls.some(([requestPath, request]) => (
            requestPath === "/api/employees" && request.method === "POST"
          )) ? [employee, createResponse.payload] : [employee],
        });
      }
      return response(200, createResponse.payload);
    },
    confirmImpl: () => false,
  });

  await controller.initialLoad;
  const event = { prevented: false, preventDefault() { this.prevented = true; } };
  const firstSubmit = controller.submitNewEmployee(event);
  await Promise.resolve();
  assert.equal(elements["employee-create-submit"].disabled, true);
  await controller.submitNewEmployee({ preventDefault() {} });
  assert.equal(postCount, 1);
  assert.equal(event.prevented, true);
  releaseCreate();
  await firstSubmit;

  const post = calls.find(([, options]) => options.method === "POST");
  assert.equal(post[0], "/api/employees");
  assert.deepEqual(JSON.parse(post[1].body), {
    id: "employee-2",
    name: "Morgan Example",
    role: "Coordinator",
    responsibilities: ["Plan work", "Support teams"],
  });
  assert.equal("agent_id" in JSON.parse(post[1].body), false);
  assert.equal(elements["employee-create-submit"].disabled, false);
  assert.match(elements["employee-create-state"].textContent, /created/i);
  assert.match(elements["employee-detail"].textContent, /employee-2/);
});

test("requires confirmation before DELETE and clears selected details after successful removal", async () => {
  const { documentRef, elements } = pageElements();
  const calls = [];
  let confirmed = false;
  let confirmationText = "";
  let releaseDelete;
  const controller = mountEmployeeManagementPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      calls.push([path, options]);
      if (options.method === "DELETE") {
        return new Promise((resolve) => {
          releaseDelete = () => resolve(response(204));
        });
      }
      if (path === "/api/employees") return response(200, { items: [employee] });
      return response(200, employee);
    },
    confirmImpl: (message) => {
      confirmationText = message;
      return confirmed;
    },
  });

  await controller.initialLoad;
  await controller.loadEmployeeDetails(employee.id);
  const removeButton = elements["employee-detail"].querySelector(".danger-button");
  await removeButton.dispatch("click");
  assert.equal(calls.some(([, options]) => options.method === "DELETE"), false);
  assert.match(confirmationText, /Avery Example/);
  assert.match(confirmationText, /employee-1/);

  confirmed = true;
  const removal = removeButton.dispatch("click");
  await Promise.resolve();
  assert.equal(removeButton.disabled, true);
  await removeButton.dispatch("click");
  assert.equal(calls.filter(([, options]) => options.method === "DELETE").length, 1);
  releaseDelete();
  await removal;
  assert.equal(
    calls.some(([path, options]) => (
      path === "/api/employees/employee-1" && options.method === "DELETE"
    )),
    true,
  );
  assert.equal(elements["employee-detail"].hidden, true);
  assert.equal(elements["employee-detail-state"].textContent, "Employee employee-1 was removed.");
  assert.equal(elements["employee-list-state"].textContent, "No employees found.");
});

test("distinguishes auth failures, stale details, conflicts, and validation failures", async () => {
  const { documentRef, elements } = pageElements();
  let listResponse = response(401);
  let detailResponse = response(404);
  let createResponse = response(409);
  const controller = mountEmployeeManagementPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (options.method === "POST") return createResponse;
      if (path === "/api/employees") return listResponse;
      return detailResponse;
    },
    confirmImpl: () => true,
  });

  await controller.initialLoad;
  assert.match(elements["employee-list-state"].textContent, /Sign-in required/);
  listResponse = response(403);
  await controller.loadEmployees();
  assert.match(elements["employee-list-state"].textContent, /Access denied/);

  listResponse = response(200, { items: [employee] });
  await controller.loadEmployees();
  await controller.loadEmployeeDetails(employee.id);
  assert.match(elements["employee-detail-state"].textContent, /no longer exists/);

  elements["employee-id"].value = "employee-1";
  elements["employee-name"].value = "Avery Example";
  elements["employee-role"].value = "Operations";
  await controller.submitNewEmployee({ preventDefault() {} });
  assert.match(elements["employee-create-state"].textContent, /already exists/);

  createResponse = response(422);
  await controller.submitNewEmployee({ preventDefault() {} });
  assert.match(elements["employee-create-state"].textContent, /rejected these fields/);
});

test("keeps failed list requests distinct from a successful empty collection", async () => {
  const { documentRef, elements } = pageElements();
  let currentResponse = response(500);
  const controller = mountEmployeeManagementPage({
    documentRef,
    fetchImpl: async () => currentResponse,
    confirmImpl: () => false,
  });

  await controller.loadEmployees();
  assert.match(elements["employee-list-state"].textContent, /could not be completed/);
  currentResponse = response(200, { items: [] });
  await controller.loadEmployees();
  assert.equal(elements["employee-list-state"].textContent, "No employees found.");
});

test("clears previously selected employee details when a refreshed list request fails", async () => {
  const { documentRef, elements } = pageElements();
  let listResponse = response(200, { items: [employee] });
  const controller = mountEmployeeManagementPage({
    documentRef,
    fetchImpl: async (path) => path === "/api/employees"
      ? listResponse
      : response(200, employee),
    confirmImpl: () => false,
  });

  await controller.initialLoad;
  await controller.loadEmployeeDetails(employee.id);
  assert.equal(elements["employee-detail"].hidden, false);

  listResponse = response(401);
  await controller.loadEmployees();

  assert.equal(elements["employee-list"].children.length, 0);
  assert.equal(elements["employee-detail"].hidden, true);
  assert.match(elements["employee-list-state"].textContent, /Sign-in required/);
  assert.match(elements["employee-detail-state"].textContent, /unavailable/);
});

test("keeps removal failures visible and re-enables retry", async () => {
  const { documentRef, elements } = pageElements();
  const controller = mountEmployeeManagementPage({
    documentRef,
    fetchImpl: async (path, options = {}) => {
      if (options.method === "DELETE") return response(403);
      if (path === "/api/employees") return response(200, { items: [employee] });
      return response(200, employee);
    },
    confirmImpl: () => true,
  });

  await controller.initialLoad;
  await controller.loadEmployeeDetails(employee.id);
  const removeButton = elements["employee-detail"].querySelector(".danger-button");
  await removeButton.dispatch("click");

  assert.equal(removeButton.disabled, false);
  assert.match(elements["employee-detail-state"].textContent, /Access denied/);
  assert.equal(elements["employee-detail"].hidden, false);
});

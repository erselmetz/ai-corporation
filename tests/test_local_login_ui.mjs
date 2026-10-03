import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import test from "node:test";

const source = await readFile(new URL("../app/webui/static/local-login.mjs", import.meta.url), "utf8");
function setup(fetch) {
  const handlers = {};
  const button = { disabled: false };
  const password = { value: "test-only-password" };
  const state = { textContent: "" };
  const form = { querySelector: () => button,
    addEventListener: (_, callback) => { handlers.submit = callback; } };
  const logout = { addEventListener: (_, callback) => { handlers.logout = callback; } };
  const elements = { "#local-login": form, "#password": password, "#login-state": state, "#local-logout": logout };
  const destinations = [];
  runInNewContext(source, { document: { querySelector: (id) => elements[id] }, fetch,
    window: { location: { assign: (url) => destinations.push(url) } } });
  return { handlers, button, password, state, destinations };
}

test("login clears password immediately, suppresses duplicate submits and navigates after success", async () => {
  let resolve;
  const calls = [];
  const ui = setup((url, options) => {
    calls.push({ url, options });
    return new Promise((done) => { resolve = done; });
  });
  const pending = ui.handlers.submit({ preventDefault() {} });
  assert.equal(ui.password.value, "");
  assert.equal(ui.button.disabled, true);
  await ui.handlers.submit({ preventDefault() {} });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/local/login");
  assert.equal(calls[0].options.credentials, "same-origin");
  resolve({ ok: true, json: async () => ({ signed_in: true }) });
  await pending;
  assert.deepEqual(ui.destinations, ["/ui"]);
  assert.equal(ui.button.disabled, false);
});

test("login failure is visible, clears input and does not navigate", async () => {
  const ui = setup(async () => ({ ok: false, json: async () => ({ detail: "Invalid credentials" }) }));
  await ui.handlers.submit({ preventDefault() {} });
  assert.equal(ui.state.textContent, "Invalid credentials");
  assert.equal(ui.password.value, "");
  assert.equal(ui.button.disabled, false);
  assert.deepEqual(ui.destinations, []);
});

test("logout uses session CSRF and reports revoked session", async () => {
  const calls = [];
  const ui = setup(async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ csrf: "test-only-csrf" }) };
  });
  await ui.handlers.logout();
  assert.equal(calls[1].url, "/api/local/logout");
  assert.equal(calls[1].options.headers["X-Local-CSRF"], "test-only-csrf");
  assert.equal(ui.state.textContent, "Signed out");
});

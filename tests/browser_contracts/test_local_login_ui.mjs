// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { readFile } from "/__contracts/harness.mjs";
import { runInNewContext } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";

const source = await readFile(new URL("../app/webui/static/local-login.mjs", import.meta.url), "utf8");
function setup(fetch, { search = "", referrer = "" } = {}) {
  const handlers = {};
  const button = { disabled: false };
  const password = { value: "test-only-password" };
  const state = { textContent: "" };
  const form = { querySelector: () => button,
    addEventListener: (_, callback) => { handlers.submit = callback; } };
  const logout = { addEventListener: (_, callback) => { handlers.logout = callback; } };
  const elements = { "#local-login": form, "#password": password, "#login-state": state, "#local-logout": logout };
  const destinations = [];
  runInNewContext(source, { document: { querySelector: (id) => elements[id], referrer }, fetch,
    URL, URLSearchParams,
    window: { location: { origin: "http://127.0.0.1:8000", search, assign: (url) => destinations.push(url) } } });
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

test("sign-in returns to the same-origin app page and rejects external destinations", async () => {
  for (const [options, expected] of [
    [{ referrer: "http://127.0.0.1:8000/ui/chat" }, "/ui/chat"],
    [{ search: "?next=%2Fui%2Fmemory" }, "/ui/memory"],
    [{ search: "?next=https://example.com/ui/chat" }, "/ui"],
    [{ search: "?next=//example.com/ui/chat" }, "/ui"],
    [{ search: "?next=/ui/login" }, "/ui"],
    [{ referrer: "http://example.com/ui/chat" }, "/ui"],
  ]) {
    const ui = setup(async () => ({ ok: true, json: async () => ({ signed_in: true }) }), options);
    await ui.handlers.submit({ preventDefault() {} });
    assert.deepEqual(ui.destinations, [expected]);
  }
});

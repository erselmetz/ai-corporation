// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { applyStoredTheme } from "../app/webui/static/theme.mjs";

test("stored local theme applies to document and body", () => {
  const documentRef = { documentElement: { dataset: {} }, body: { dataset: {} } };
  const storage = { getItem: key => key === "ersel-chat-theme-v1" ? "light" : null };
  assert.equal(applyStoredTheme(documentRef, storage), "light");
  assert.equal(documentRef.documentElement.dataset.theme, "light");
  assert.equal(documentRef.body.dataset.theme, "light");
});

test("storage failure keeps the default dark theme", () => {
  const documentRef = { documentElement: { dataset: {} }, body: { dataset: {} } };
  const storage = { getItem() { throw new Error("blocked"); } };
  assert.equal(applyStoredTheme(documentRef, storage), "dark");
  assert.equal(documentRef.body.dataset.theme, "dark");
});

test("a browser refusing access to the storage property still gets dark theme", () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw new Error("storage denied"); } });
  try {
    const documentRef = { documentElement: { dataset: {} }, body: { dataset: {} } };
    assert.equal(applyStoredTheme(documentRef), "dark");
    assert.equal(documentRef.documentElement.dataset.theme, "dark");
  } finally {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else delete globalThis.localStorage;
  }
});

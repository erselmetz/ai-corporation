// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { readFile } from "/__contracts/harness.mjs";
import { runInNewContext } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";

const source = await readFile(new URL("../app/webui/static/navigation.mjs", import.meta.url), "utf8");

class Element {
  constructor(link = false) { this.link = link; }
  closest(selector) { return (selector === "a" || selector.includes("a,")) && this.link ? this : null; }
}

function setup(matches = true) {
  const handlers = { toggle: {}, navigation: {}, document: {}, media: {} };
  const classes = new Set(["has-shared-navigation"]);
  const body = { classList: {
    contains: name => classes.has(name),
    toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
  } };
  const attrs = {};
  const toggle = { textContent: "Menu", setAttribute: (name, value) => { attrs[name] = value; },
    addEventListener: (name, handler) => { handlers.toggle[name] = handler; } };
  const navigation = { inert: false, addEventListener: (name, handler) => { handlers.navigation[name] = handler; } };
  const media = { matches, addEventListener: (name, handler) => { handlers.media[name] = handler; } };
  const document = { body, getElementById: id => id === "shared-navigation-toggle" ? toggle : navigation,
    addEventListener: (name, handler) => { handlers.document[name] = handler; } };
  runInNewContext(source, { document, Element, matchMedia: () => media });
  return { attrs, body, classes, handlers, media, navigation, toggle };
}

test("shared navigation stays visible on wide screens and has a working narrow-window menu", () => {
  const ui = setup(true);
  assert.equal(ui.navigation.inert, true);
  assert.equal(ui.attrs["aria-expanded"], "false");

  ui.handlers.toggle.click();
  assert.equal(ui.classes.has("navigation-open"), true);
  assert.equal(ui.attrs["aria-expanded"], "true");
  assert.equal(ui.navigation.inert, false);

  ui.handlers.navigation.click({ target: new Element(true) });
  assert.equal(ui.classes.has("navigation-open"), false);
  assert.equal(ui.navigation.inert, true);
});

test("Escape closes the compact navigation and wide resize restores the visible rail", () => {
  const ui = setup(true);
  ui.handlers.toggle.click();
  ui.handlers.document.keydown({ key: "Escape" });
  assert.equal(ui.classes.has("navigation-open"), false);
  ui.handlers.toggle.click();
  ui.media.matches = false;
  ui.handlers.media.change();
  assert.equal(ui.classes.has("navigation-open"), false);
  assert.equal(ui.navigation.inert, false);
});

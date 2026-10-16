const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const read = (name) => fs.readFileSync(path.join(root, name), "utf8");

test("Next routes use one root navigation shell instead of page-owned sidebars", () => {
  const layout = read("desktop-ui/src/app/layout.tsx");
  const shell = read("desktop-ui/src/app/app-shell.tsx");
  const home = read("desktop-ui/src/app/page.tsx");
  const settings = read("desktop-ui/src/app/settings/page.tsx");
  assert.match(layout, /<AppShell>\{children\}<\/AppShell>/);
  assert.match(shell, /aria-label="Main navigation"/);
  assert.match(shell, /aria-controls="desktop-navigation"/);
  assert.match(shell, /aria-expanded=\{navigationOpen\}/);
  assert.doesNotMatch(home, /<aside className="rail"/);
  assert.doesNotMatch(settings, /<aside className="rail"/);
  assert.match(home, /<FirstRunWizard \/>/);
  const styles = read("desktop-ui/src/app/style.css");
  assert.match(styles, /\.navigation-toggle, \.navigation-backdrop \{ display: none; \}/);
  assert.match(styles, /@media \(max-width: 1000px\)[\s\S]*?\.navigation-toggle/);
  assert.match(styles, /\.navigation-backdrop \{ position: fixed;/);
});

test("static navigation covers Python UI destinations and compact navigation is controlled", () => {
  const middleware = read("app/local.py");
  const nav = read("app/webui/router.py");
  const script = read("app/webui/static/navigation.mjs");
  assert.match(middleware, /async def shared_local_navigation/);
  assert.match(middleware, /shared-navigation-toggle/);
  assert.match(middleware, /navigation\.mjs/);
  assert.match(nav, /\("Settings", "\/desktop\/settings\/"\)/);
  assert.match(script, /Escape/);
  assert.match(script, /navigation\.inert = compact\.matches && !value/);
  assert.match(script, /setOpen\(false\)/);
});

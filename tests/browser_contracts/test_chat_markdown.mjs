// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { renderSafeMarkdown } from "../app/webui/static/chat-markdown.mjs";

class Node {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.text = ""; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(node => node.textContent).join(""); }
  append(...nodes) { this.children.push(...nodes); }
  setAttribute() {}
  addEventListener(name, callback) { this.listeners[name] = callback; }
}
const doc = { createElement: tag => new Node(tag), createTextNode: value => ({ textContent: String(value) }) };

test("renders common Markdown with inert text nodes and no HTML execution surface", () => {
  const rendered = renderSafeMarkdown("# Hello\n\n**bold** and `code`\n\n- first\n- second\n\n```js\nconst x = 1;\n```\n\n<img src=x onerror=alert(1)>", { documentRef: doc });
  assert.match(rendered.textContent, /Hello.*bold.*code.*first.*second.*const x = 1.*<img src=x onerror=alert\(1\)>/s);
  assert.equal(rendered.children[0].tagName, "H1");
  assert.equal(rendered.children.at(-1).tagName, "P");
  assert.equal(rendered.children.some(node => node.tagName === "IMG"), false);
});

test("code copy uses the clipboard API and reports completion", async () => {
  let copied = "";
  const rendered = renderSafeMarkdown("```\nprint(1)\n```", {
    documentRef: doc,
    navigatorRef: { clipboard: { writeText: async value => { copied = value; } } },
  });
  const button = rendered.children[0].children[1];
  await button.listeners.click();
  assert.equal(copied, "print(1)");
  assert.equal(button.textContent, "Copied");
});

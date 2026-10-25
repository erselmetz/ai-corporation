// Local source-mode UI verification. Uses an existing runtime; never downloads or deploys.
const path = require("node:path");
const fs = require("node:fs");
const assert = require("node:assert/strict");
const { _electron } = require(path.resolve(__dirname, "../.venv/Lib/site-packages/playwright/driver/package"));
async function run() {
  const root = path.resolve(__dirname, "..");
  const output = path.join(root, "desktop", "task223-review"); fs.mkdirSync(output, { recursive:true });
  const env = { ...process.env, LOCALAPPDATA:fs.mkdtempSync(path.join(output, "profile-")),
    ERSELMETZ_PORT:"18883", ERSELMETZ_PYTHON:path.join(root,".venv","Scripts","python.exe") };
  delete env.ELECTRON_RUN_AS_NODE;
  let app, page;
  const result = { runtime:"Source-mode Electron; isolated local profile", checks:[], errors:[] };
  try {
    app = await _electron.launch({ executablePath:path.join(root,"desktop","task214-review","electron-runtime","electron.exe"),
      args:[path.join(root,"desktop")], env, timeout:30000 });
    page = await app.firstWindow();
    page.on("pageerror", error => result.errors.push(error.message));
    await page.waitForURL("**/ui/chat?desktop=1", {timeout:30000});
    await page.locator("#knowledge-note-form").waitFor({state:"attached"});
    await page.waitForFunction(() => document.getElementById("chat-input")?.disabled === false);
    await page.waitForFunction(() => !document.getElementById("brain-map-status").textContent.startsWith("Loading"));
    result.checks.push("Brain and intake mounted alongside live chat");
    const before = await page.locator(".chat-conversation-item").count();
    await page.keyboard.press("Control+n");
    await page.waitForFunction(n => document.querySelectorAll(".chat-conversation-item").length === n + 1, before);
    assert.equal(app.windows().length, 1);
    result.checks.push("Ctrl+N adds one conversation tab without opening a window");
    await page.keyboard.press("Control+b");
    assert.equal(await page.locator("body").evaluate(node => node.classList.contains("sidebar-collapsed")), true);
    const widths = await page.evaluate(() => [document.getElementById("shell-brain").getBoundingClientRect().width,
      document.querySelector(".chat-workspace").getBoundingClientRect().width]);
    assert.ok(Math.abs(widths[0]-widths[1]) < 2);
    result.checks.push("Hidden sidebar leaves equal Brain/chat panes");
    await page.screenshot({path:path.join(output,"shell-hidden.png")});
    await page.keyboard.press("Control+b");
    const split = page.locator("#shell-right-split"); await split.focus(); await page.keyboard.press("ArrowRight");
    assert.equal(await split.getAttribute("aria-valuenow"), "52");
    result.checks.push("Keyboard separator resizes panes");
    await page.locator("#shell-add-note").click();
    await page.locator("#knowledge-content").fill("Task 223 local shell test note. No provider call.");
    await page.locator("#knowledge-consent").check();
    await page.locator("#knowledge-save").click();
    await page.waitForFunction(() => document.getElementById("knowledge-state").textContent.includes("saved"));
    result.checks.push("Inline note uses existing retention consent and local Brain service");
    await page.locator(".chat-advanced-nav > summary").click();
    await page.locator('.chat-advanced-nav a[href="/ui/knowledge"]').click();
    await page.waitForTimeout(800);
    assert.equal(app.windows().length, 2);
    assert.ok(page.url().includes("/ui/chat"));
    result.checks.push("Advanced Brain settings opens separately; chat stays on screen");
    await page.locator("#chat-sidebar").evaluate(node => { node.scrollTop=0; });
    await page.screenshot({path:path.join(output,"shell-full.png")});
    assert.deepEqual(result.errors, []);
    result.status = "passed";
  } catch(error) { result.status="failed"; result.failure=error.stack;
    if(page) { result.debug = await page.evaluate(() => ({url:location.href, state:document.getElementById("shell-brain-state")?.textContent, scripts:[...document.scripts].map(s=>s.src), body:document.body.innerText.slice(0,3000)})).catch(()=>null); await page.screenshot({path:path.join(output,"failure.png")}).catch(()=>{}); }
    throw error; }
  finally { fs.writeFileSync(path.join(output,"result.json"),JSON.stringify(result,null,2)); if(app) await app.close(); }
}
run().catch(error => { console.error(error); process.exitCode=1; });

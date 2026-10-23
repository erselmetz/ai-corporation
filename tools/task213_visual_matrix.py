"""Capture an isolated, deterministic UI review matrix without a live provider."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright  # noqa: E402
import uvicorn  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

from app.local import create_local_app  # noqa: E402
from app.providers import AIProvider  # noqa: E402
from app.runtime.factory import create_corporation_runtime  # noqa: E402


class ReviewProvider(AIProvider):
    def generate(self, model, prompt):
        return "Local review response from a deterministic provider."


def capture(output: Path, screens: set[str] | None = None, scales: tuple[float, ...] = (1, 1.25, 1.5),
            widths: tuple[int, ...] = (480, 768, 1280, 1920), fault: str | None = None) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    with TemporaryDirectory(prefix="erselmetz-task213-") as data_dir:
        os.chdir(data_dir)
        try:
            runtime = create_corporation_runtime()
            runtime.providers.remove("ollama")
            runtime.providers.register("ollama", ReviewProvider())
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen(5)
            origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
            app = create_local_app(
                password="task213-review-only-password",
                origin=origin,
                application_service=runtime.application_service,
                desktop_ui_dir=ROOT / "desktop-ui" / "out",
            )
            axe_path = ROOT / "desktop-ui" / "node_modules" / "axe-core" / "axe.min.js"
            if not axe_path.is_file():
                raise RuntimeError("Run npm.cmd ci --prefix desktop-ui for local axe checks")

            @app.get("/__review__/axe.js", include_in_schema=False)
            def review_axe_script():
                return FileResponse(axe_path, media_type="text/javascript")

            started = Event()

            class Server(uvicorn.Server):
                async def startup(self, sockets=None):
                    await super().startup(sockets=sockets)
                    started.set()

            server = Server(uvicorn.Config(app, log_level="error", proxy_headers=False,
                                           timeout_graceful_shutdown=5))
            thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                if not started.wait(10):
                    raise RuntimeError("Isolated UI server did not start")
                results = []
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    try:
                        for scale in scales:
                            context = browser.new_context(
                                viewport={"width": 1280, "height": 900},
                                device_scale_factor=scale,
                                reduced_motion="reduce",
                            )
                            page = context.new_page()
                            page.add_init_script("""(() => {
                              window.__reviewLayoutShift = 0;
                              window.__reviewLayoutShifts = [];
                              new PerformanceObserver(list => {
                                for (const entry of list.getEntries()) {
                                  if (!entry.hadRecentInput) {
                                    window.__reviewLayoutShift += entry.value;
                                    if (window.__reviewLayoutShifts.length < 8) window.__reviewLayoutShifts.push({value: entry.value,
                                      sources: entry.sources.map(source => ({id: source.node?.id, tag: source.node?.tagName,
                                        className: typeof source.node?.className === 'string' ? source.node.className : '',
                                        from: {x: source.previousRect.x, y: source.previousRect.y, height: source.previousRect.height},
                                        to: {x: source.currentRect.x, y: source.currentRect.y, height: source.currentRect.height}}))});
                                  }
                                }
                              }).observe({type: 'layout-shift', buffered: true});
                            })()""")
                            page.goto(origin + "/ui/login")
                            page.locator("#password").fill("task213-review-only-password")
                            page.get_by_role("button", name="Sign in", exact=True).click()
                            page.wait_for_url(origin + "/ui")
                            pending_routes = []
                            if fault:
                                def unavailable(route):
                                    if fault == "loading":
                                        pending_routes.append(route)
                                    elif fault == "offline":
                                        route.abort("internetdisconnected")
                                    else:
                                        route.fulfill(status=503, json={"detail": "Local service unavailable"})
                                page.route("**/api/**", unavailable)
                            if scale == 1 and not fault:
                                page.goto(origin + "/desktop/settings/")
                                page.get_by_role("button", name="Switch to light theme").click()
                                page.goto(origin + "/ui/agents")
                                expect(page.locator("body")).to_have_attribute("data-theme", "light")
                                page.goto(origin + "/ui/chat?desktop=1")
                                expect(page.locator("body")).to_have_attribute("data-theme", "light")
                                expect(page.locator("#chat-theme-toggle")).to_have_text("Switch to dark theme")
                                page.goto(origin + "/desktop/")
                                expect(page.locator("html")).to_have_attribute("data-theme", "light")
                                page.evaluate("window.localStorage.setItem('ersel-chat-theme-v1', 'dark')")
                            for theme in ("dark", "light"):
                                page.emulate_media(color_scheme=theme, reduced_motion="reduce")
                                for width in widths:
                                    page.set_viewport_size({"width": width, "height": 900})
                                    for name, route in (
                                        ("home", "/desktop/"),
                                        ("chat", "/ui/chat?desktop=1"),
                                        ("agents", "/ui/agents"),
                                        ("employees", "/ui/employees"),
                                        ("positions", "/ui/positions"),
                                        ("providers", "/ui/providers"),
                                        ("projects", "/ui/projects"),
                                        ("memory", "/ui/memory"),
                                        ("tasks", "/ui/tasks"),
                                        ("activity", "/ui/activity"),
                                        ("inventory", "/ui/inventory"),
                                        ("backup", "/ui/backup"),
                                        ("capabilities", "/ui/settings/capabilities"),
                                        ("documentation", "/ui/documentation"),
                                        ("updates", "/ui/updates"),
                                        ("readiness", "/ui/readiness"),
                                        ("settings", "/desktop/settings/"),
                                        ("dashboard", "/ui"),
                                        ("knowledge", "/ui/knowledge"),
                                        ("automation", "/ui/automation"),
                                        ("preferences", "/ui/preferences"),
                                        ("local-models", "/ui/local-models"),
                                        ("assignment-policy", "/ui/assignment-policy"),
                                        ("online-provider", "/ui/online-provider"),
                                        ("workflows", "/ui/workflows"),
                                        ("structure", "/ui/structure"),
                                        ("workflow-map", "/ui/workflow-map"),
                                        ("visualization", "/ui/visualization"),
                                        ("provider-connections", "/ui/provider-connections"),
                                        ("employee-chat", "/ui/employee-chat"),
                                        ("sage-core", "/ui/sage-core"),
                                        ("login", "/ui/login"),
                                        ("first-run", "/desktop/?reviewFirstRun=1"),
                                        ("first-run-gemini", "/desktop/?reviewFirstRun=1"),
                                        ("first-run-ollama", "/desktop/?reviewFirstRun=1"),
                                    ):
                                        if screens is not None and name not in screens:
                                            continue
                                        for pending in pending_routes:
                                            try:
                                                pending.abort()
                                            except Exception:
                                                pass  # A previous navigation may already have cancelled it.
                                        pending_routes.clear()
                                        page.unroute("**/api/local/first-run")
                                        if name.startswith("first-run") and not fault:
                                            page.route("**/api/local/first-run", lambda route: route.fulfill(json={
                                                "enabled": True, "completed": False, "skipped": False,
                                                "credential_needs_reentry": False,
                                            }))
                                        page.goto(origin + route)
                                        page.locator("body").wait_for()
                                        if name == "chat" and not fault:
                                            expect(page.locator("#chat-identity")).to_contain_text("Local Worker", timeout=15_000)
                                        elif name == "settings" and fault != "loading":
                                            deadline = time.monotonic() + 15
                                            while time.monotonic() < deadline:
                                                states = page.locator(".settings-state").all_text_contents()
                                                if states and all(state.strip().lower() not in ("loading", "checking")
                                                  for state in states):
                                                    break
                                                page.wait_for_timeout(100)
                                            else:
                                                raise RuntimeError("Settings did not settle before screenshot")
                                        else:
                                            page.wait_for_timeout(300)
                                        if name.startswith("first-run") and not fault:
                                            expect(page.locator("#first-run-title")).to_be_visible()
                                            if name == "first-run-gemini":
                                                page.get_by_role("button", name="Use Gemini (online)", exact=True).click()
                                            elif name == "first-run-ollama":
                                                page.get_by_role("button", name="Use Ollama (local)", exact=True).click()
                                                page.wait_for_timeout(300)
                                        if fault and fault != "loading":
                                            for control in ("documentation-refresh", "activity-refresh", "employee-refresh",
                                                            "provider-refresh", "task-refresh", "project-refresh", "memory-refresh",
                                                            "inventory-refresh", "readiness-refresh", "backup-preview",
                                                            "assignment-policy-preview"):
                                                button = page.locator(f"#{control}")
                                                if button.count() and button.is_visible() and button.is_enabled():
                                                    button.click()
                                            page.wait_for_timeout(300)
                                        page.evaluate("theme => { document.documentElement.dataset.theme = theme; document.body.dataset.theme = theme; }", theme)
                                        filename = f"{name}-{theme}-{width}-{int(scale * 100)}.png"
                                        page.screenshot(path=str(output / filename), animations="disabled", caret="hide")
                                        metrics = page.evaluate("""() => ({
                                          viewport: window.innerWidth,
                                          scrollWidth: document.documentElement.scrollWidth,
                                          title: document.title,
                                          theme: getComputedStyle(document.body).colorScheme,
                                          layoutShift: window.__reviewLayoutShift || 0,
                                          layoutShifts: window.__reviewLayoutShifts || [],
                                          states: [...document.querySelectorAll('[role="status"], [role="alert"]')]
                                            .filter(element => !element.hidden).map(element => element.textContent.trim()).filter(Boolean),
                                        })""")
                                        results.append({"file": filename, "route": route, **metrics})
                                        if scale == 1 and width == 1280 and not fault:
                                            links = page.locator('a[href^="/ui"], a[href^="/desktop"]').evaluate_all(
                                                "elements => [...new Set(elements.map(element => element.getAttribute('href').split('#')[0]))]")
                                            broken = [link for link in links if context.request.get(origin + link).status >= 400]
                                            if broken:
                                                results[-1]["brokenLinks"] = broken
                                        if scale == 1 and width in (480, 1280):
                                            page.add_script_tag(url=origin + "/__review__/axe.js")
                                            accessibility = page.evaluate("""async () => {
                                              const result = await axe.run(document, {
                                                runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] }
                                              });
                                              return result.violations.map(item => ({
                                                id: item.id, impact: item.impact,
                                                targets: item.nodes.map(node => node.target).slice(0, 8)
                                              }));
                                            }""")
                                            results[-1]["axe"] = accessibility
                                        if scale == 1 and width == 480:
                                            menu_id = "chat-menu-button" if name == "chat" else (
                                                "shared-navigation-toggle" if route.startswith("/ui/") else "")
                                            if fault or name.startswith("first-run"):
                                                menu = page.locator(f"#{menu_id}") if menu_id else page.locator(".navigation-toggle")
                                                menu.focus()
                                            else:
                                                page.keyboard.press("Tab")
                                            focused = page.evaluate("document.activeElement.id")
                                            if menu_id and focused != menu_id:
                                                results[-1]["keyboard"] = f"First Tab reached {focused!r} instead of {menu_id!r}"
                                            else:
                                                page.keyboard.press("Enter")
                                                menu = page.locator(f"#{menu_id}") if menu_id else page.locator(".navigation-toggle")
                                                try:
                                                    expect(menu).to_have_attribute("aria-expanded", "true", timeout=1500)
                                                    page.keyboard.press("Escape")
                                                    expect(menu).to_have_attribute("aria-expanded", "false", timeout=1500)
                                                except AssertionError as error:
                                                    results[-1]["keyboard"] = str(error).splitlines()[0]
                                            if name == "chat" and not fault:
                                                page.evaluate("""() => {
                                                  const item = document.createElement('div');
                                                  item.className = 'chat-message chat-message-assistant';
                                                  const text = document.createElement('div');
                                                  text.className = 'chat-message-content';
                                                  text.textContent = 'Napakahabangsalitangwalangspaces'.repeat(80);
                                                  item.append(text); document.querySelector('#chat-history').append(item);
                                                }""")
                                            elif name == "agents" and not fault:
                                                page.locator(".agent-card-summary h2").first.evaluate(
                                                    "element => element.textContent = 'Napakahabangpangalan'.repeat(80)")
                                            elif name == "settings" and not fault:
                                                page.locator(".settings-values dd").first.evaluate(
                                                    "element => element.textContent = 'Napakahabangsetting'.repeat(80)")
                                            if name in ("chat", "agents", "settings") and not fault:
                                                results[-1]["longTextOverflow"] = page.evaluate(
                                                    "document.documentElement.scrollWidth > window.innerWidth")
                                            seen = set()
                                            for _ in range(100):
                                                page.keyboard.press("Tab")
                                                focus = page.evaluate("""() => {
                                                  const element = document.activeElement;
                                                  if (element === document.body) return { key: 'body' };
                                                  const all = [...document.querySelectorAll('*')];
                                                  const rect = element.getBoundingClientRect();
                                                  const style = getComputedStyle(element);
                                                  const outlineRules = [];
                                                  if (style.outlineWidth === '0px') {
                                                    const collect = rules => { for (const rule of rules) {
                                                      if (rule.selectorText && rule.style?.outline && element.matches(rule.selectorText)) outlineRules.push(rule.cssText);
                                                      if (rule.cssRules) collect(rule.cssRules);
                                                    }};
                                                    for (const sheet of document.styleSheets) collect(sheet.cssRules);
                                                  }
                                                  return { key: String(all.indexOf(element)), id: element.id || element.tagName,
                                                    hidden: !!element.closest('[aria-hidden="true"], [inert]') || !rect.width || !rect.height,
                                                    focusVisible: element.matches(':focus-visible'), outlineStyle: style.outlineStyle,
                                                    outlineWidth: style.outlineWidth,
                                                    outlineRules,
                                                    outline: style.outlineStyle !== 'none' && style.outlineWidth !== '0px' };
                                                }""")
                                                if focus["key"] in seen:
                                                    break
                                                seen.add(focus["key"])
                                                if focus.get("hidden") or focus.get("outline") is False:
                                                    results[-1].setdefault("focusFailures", []).append(focus)
                                            results[-1]["keyboardStops"] = len(seen)
                            for pending in pending_routes:
                                try:
                                    pending.abort()
                                except Exception:
                                    pass  # Navigation may already have cancelled the request.
                            pending_routes.clear()
                            context.close()
                    finally:
                        browser.close()
                (output / "matrix.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                return results
            finally:
                server.should_exit = True
                thread.join(timeout=20)
                if thread.is_alive():
                    server.force_exit = True
                    thread.join(timeout=10)
                listener.close()
                if thread.is_alive():
                    if sys.exc_info()[0] is None:
                        raise RuntimeError("Isolated UI server did not stop")
                    print("Warning: isolated UI server did not stop after a capture error", file=sys.stderr)
        finally:
            os.chdir(original_cwd)


def compare_baselines(output: Path, baselines: Path) -> list[str]:
    """Allow tiny renderer differences while catching changed layout or contrast."""
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            for expected in sorted(baselines.glob("*.png")):
                actual = output / expected.name
                if not actual.is_file():
                    failures.append(f"Missing screenshot: {expected.name}")
                    continue
                urls = ["data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
                        for path in (expected, actual)]
                result = page.evaluate("""async ([before, after]) => {
                  const load = source => new Promise((resolve, reject) => {
                    const image = new Image(); image.onload = () => resolve(image);
                    image.onerror = reject; image.src = source;
                  });
                  const [a, b] = await Promise.all([load(before), load(after)]);
                  if (a.width !== b.width || a.height !== b.height) return 1;
                  const canvas = document.createElement('canvas');
                  canvas.width = a.width; canvas.height = a.height;
                  const context = canvas.getContext('2d');
                  context.drawImage(a, 0, 0);
                  const left = context.getImageData(0, 0, a.width, a.height).data;
                  context.clearRect(0, 0, a.width, a.height);
                  context.drawImage(b, 0, 0);
                  const right = context.getImageData(0, 0, a.width, a.height).data;
                  let different = 0;
                  for (let i = 0; i < left.length; i += 4) {
                    const delta = Math.max(Math.abs(left[i] - right[i]),
                      Math.abs(left[i+1] - right[i+1]), Math.abs(left[i+2] - right[i+2]));
                    if (delta > 2) different++;
                  }
                  return different / (a.width * a.height);
                }""", urls)
                if result > 0.003:
                    failures.append(f"Visual regression: {expected.name} ({result:.2%} pixels changed)")
        finally:
            browser.close()
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "desktop" / "task213-review" / "before")
    parser.add_argument("--baselines", type=Path, help="Compare representative screenshots against checked-in baselines")
    parser.add_argument("--screens", help="Comma-separated screen names for a focused rerun")
    parser.add_argument("--scales", default="1,1.25,1.5", help="Comma-separated device-scale factors")
    parser.add_argument("--widths", default="480,768,1280,1920", help="Comma-separated CSS pixel widths")
    parser.add_argument("--fault", choices=("offline", "error", "loading"), help="Fail or hold API requests after owner login")
    args = parser.parse_args()
    rows = capture(args.output.resolve(), set(args.screens.split(",")) if args.screens else None,
                   tuple(float(value) for value in args.scales.split(",")),
                   tuple(int(value) for value in args.widths.split(",")), args.fault)
    print(f"Captured {len(rows)} screenshots in {args.output.resolve()}")
    failures = []
    for row in rows:
        if row["scrollWidth"] > row["viewport"]:
            failures.append(f"Horizontal overflow: {row['file']} ({row['scrollWidth']} > {row['viewport']})")
        if row.get("layoutShift", 0) > 0.1:
            failures.append(f"Disruptive layout shift: {row['file']} ({row['layoutShift']:.3f})")
        for violation in row.get("axe", []):
            if violation["impact"] in ("critical", "serious"):
                failures.append(f"Axe {violation['impact']}: {row['file']} {violation['id']} {violation['targets']}")
        if row.get("keyboard"):
            failures.append(f"Keyboard: {row['file']} {row['keyboard']}")
        if row.get("longTextOverflow"):
            failures.append(f"Long-text overflow: {row['file']}")
        if row.get("brokenLinks"):
            failures.append(f"Broken local links: {row['file']} {row['brokenLinks']}")
        if row.get("focusFailures"):
            failures.append(f"Invisible keyboard focus: {row['file']} {row['focusFailures']}")
    if args.baselines:
        failures.extend(compare_baselines(args.output.resolve(), args.baselines.resolve()))
    for failure in failures:
        print(failure)
    if failures:
        raise SystemExit(1)

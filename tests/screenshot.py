#!/usr/bin/env python3
"""Open the page in a headless browser, fail on console errors, exercise the controls and save screenshots.

Usage (server must be running):  python tests/screenshot.py http://127.0.0.1:8000
Needs Playwright (e.g. `uv run --with playwright python tests/screenshot.py ...`).
Set CHROME=/path/to/chrome to use an existing Chromium instead of Playwright's own download.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "figures" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def run(browser, name, width, height, scheme):
    ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=2 if width < 500 else 1)
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("body[data-ready='1']", timeout=15000)
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    page.screenshot(path=str(OUT / f"{name}_full.png"), full_page=True)
    # interactions
    page.click("button[data-mode='mid']")
    page.locator("#s-spaghetti").screenshot(path=str(OUT / f"{name}_spaghetti_2004.png"))
    page.click("button[data-mode='start']")
    page.click("button[data-mode='pre']")
    page.wait_for_timeout(400)  # a debounced redraw may still be replacing the SVG
    page.locator("#spaghetti svg").scroll_into_view_if_needed()
    box = page.locator("#spaghetti svg").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.2)
    tip = page.inner_text("#tip")
    page.locator("#s-spaghetti").screenshot(path=str(OUT / f"{name}_spaghetti_hover.png"))
    page.fill("#field-search", "OSELVAR")
    page.dispatch_event("#field-search", "change")
    head = page.inner_text("#field-head")
    page.locator("#s-field").screenshot(path=str(OUT / f"{name}_field_oselvar.png"))
    page.select_option("#drv-feature", "concept")
    page.select_option("#drv-h", "3")
    cap = page.inner_text("#strip-cap")
    page.select_option("#funnel-k", "5")
    page.select_option("#funnel-k", "3")
    page.locator("#s-hard").screenshot(path=str(OUT / f"{name}_hard.png"))
    page.locator("#s-uk").screenshot(path=str(OUT / f"{name}_uk.png"))
    n_svg = page.locator("svg").count()
    ctx.close()
    ok = not errors and overflow <= 0 and "OSELVAR" in head and tip.strip() and n_svg >= 12
    print(f"{name}: svgs={n_svg} overflow_px={overflow} errors={errors} tip='{tip.splitlines()[0] if tip else ''}' head_ok={'OSELVAR' in head} -> {'PASS' if ok else 'FAIL'}")
    return ok


with sync_playwright() as p:
    try:
        exe = os.environ.get("CHROME")  # optional path to an already installed Chromium
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    except Exception as exc:  # noqa: BLE001
        print("chromium failed, using firefox:", str(exc).splitlines()[0])
        browser = p.firefox.launch()
    results = [run(browser, "desktop_light", 1280, 900, "light"), run(browser, "desktop_dark", 1280, 900, "dark"),
               run(browser, "mobile_light", 390, 844, "light")]
    browser.close()
sys.exit(0 if all(results) else 1)

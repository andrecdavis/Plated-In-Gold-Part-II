"""Serve app/ and load it in headless Chromium; fail on any JS error; refresh app/screenshots/."""
import asyncio
import functools
import http.server
import os
import sys
import threading

from playwright.async_api import async_playwright

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=APP))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/index.html"
SHOTS = os.path.join(APP, "screenshots")
os.makedirs(SHOTS, exist_ok=True)
CHARTS = ["askChart", "ratioChart", "bridgeChart", "kmChart", "goldChart", "goldAge", "goldSellers", "aucModel", "aucFb",
          "aucShip", "trajChart", "saleCurve", "saleRel", "saleImp", "priceWf", "priceImp", "colChart"]


async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for mode in ["light", "dark"]:
            for name, w, h in [("desktop", 1366, 900), ("mobile", 390, 844)]:
                pg = await b.new_page(viewport={"width": w, "height": h}, color_scheme=mode)
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
                await pg.goto(URL, wait_until="networkidle")
                await pg.wait_for_timeout(1500)
                missing = await pg.evaluate("ids => ids.filter(i => !document.getElementById(i).querySelector('.main-svg'))", CHARTS)
                if missing:
                    errs.append(f"{mode}/{name}: charts not drawn: {missing}")

                async def shot(sel, fn, dy=-120):
                    await pg.locator(sel).scroll_into_view_if_needed()
                    await pg.evaluate(f"window.scrollBy(0,{dy})")
                    await pg.wait_for_timeout(500)
                    await pg.screenshot(path=os.path.join(SHOTS, f"{mode}_{name}_{fn}.png"))

                await pg.screenshot(path=os.path.join(SHOTS, f"{mode}_{name}_01_intro.png"))
                await shot("#headline", "02_headlines", -60)
                await shot("#askChart", "03_ask_vs_sold")
                await shot("#kmChart", "04_time_to_sale")
                await shot("#gold", "05_gold", -60)
                await shot("#goldAge", "06_gold_age")
                await pg.select_option("#fModel", "Series 9")
                await shot("#trajChart", "07_trajectories")
                await pg.select_option("#sRatio", "0.5")
                await shot("#saleCurve", "08_sale_explainer")
                await pg.select_option("#pModel", "Ultra 2")
                await shot("#priceWf", "09_price_estimator")
                await shot("#colChart", "10_collection")
                await pg.close()
        # toggle test: light -> dark re-themes charts without errors
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, color_scheme="light")
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(URL, wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        await pg.click("#themeToggle")
        await pg.wait_for_timeout(800)
        t = await pg.evaluate("[document.documentElement.dataset.theme, localStorage.getItem('theme'), document.getElementById('askChart')._fullLayout.font.color]")
        print("toggle ->", t)
        if t[0] != "dark" or t[1] != "dark" or t[2].lower() != "#e8e8e8":
            errs.append("theme toggle failed: " + str(t))
        await b.close()
    print("JS errors:", errs or "none")
    sys.exit(1 if errs else 0)

asyncio.run(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 playwright 把 us_gap_verify 下9个HTML全页截图为PNG。"""
import glob, os
from playwright.sync_api import sync_playwright

OUT = "/home/ubuntu/.hermes-bot2/media_cache/us_gap_verify"
htmls = sorted(glob.glob(f"{OUT}/*.html"))

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"])
    page = browser.new_page(viewport={"width":375,"height":800}, device_scale_factor=2)
    for h in htmls:
        png = h.replace(".html",".png")
        page.goto(f"file://{h}")
        page.wait_for_timeout(600)
        page.screenshot(path=png, full_page=True)
        print(f"SHOT {os.path.basename(png)}")
    browser.close()

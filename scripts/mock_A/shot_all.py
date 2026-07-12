from playwright.sync_api import sync_playwright
import pathlib
url="file://"+str(pathlib.Path("all_pages.html").resolve())
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":1560,"height":1000},device_scale_factor=1.5)
    pg.goto(url);pg.wait_for_timeout(800)
    pg.screenshot(path="all_pages.png",full_page=True);b.close()
print("ok")

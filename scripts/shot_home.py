from playwright.sync_api import sync_playwright
import pathlib
url = "file://" + str(pathlib.Path("home_beautify_mock.html").resolve())
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":920,"height":980}, device_scale_factor=2)
    pg.goto(url)
    pg.wait_for_timeout(700)
    pg.screenshot(path="home_beautify_mock.png", full_page=True)
    b.close()
print("done")

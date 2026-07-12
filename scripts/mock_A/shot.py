from playwright.sync_api import sync_playwright
import pathlib,sys
f=sys.argv[1] if len(sys.argv)>1 else "build.html"
out=sys.argv[2] if len(sys.argv)>2 else "out.png"
url="file://"+str(pathlib.Path(f).resolve())
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":420,"height":800},device_scale_factor=2)
    pg.goto(url);pg.wait_for_timeout(500)
    pg.screenshot(path=out,full_page=True);b.close()
print("ok",out)

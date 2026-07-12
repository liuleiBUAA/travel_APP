import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":480,"height":900}, device_scale_factor=2)
        import pathlib
        url = "file://" + str(pathlib.Path("/home/ubuntu/tools/travel_APP/scripts/mock_A/home_real.html").resolve())
        await pg.goto(url)
        await pg.wait_for_timeout(700)
        el = await pg.query_selector(".phone")
        await el.screenshot(path="/home/ubuntu/tools/travel_APP/scripts/mock_A/home_real.png")
        print("saved")
        await b.close()

asyncio.run(main())
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":760,"height":800}, device_scale_factor=2)
        import pathlib
        url = "file://" + str(pathlib.Path("/home/ubuntu/tools/travel_APP/scripts/mock_A/home_v2.html").resolve())
        await pg.goto(url)
        await pg.wait_for_timeout(800)
        blk = await pg.query_selector(".block")
        await blk.screenshot(path="/home/ubuntu/tools/travel_APP/scripts/mock_A/home_v2.png")
        print("saved")
        await b.close()

asyncio.run(main())
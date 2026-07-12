import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":760,"height":800}, device_scale_factor=2)
        import pathlib
        url = "file://" + str(pathlib.Path("/home/ubuntu/tools/travel_APP/scripts/mock_A/layout_compare.html").resolve())
        await pg.goto(url)
        await pg.wait_for_timeout(800)
        blocks = await pg.query_selector_all(".block")
        names = ["1_home","2_list","3_detail","4_profile"]
        for i,blk in enumerate(blocks):
            await blk.screenshot(path=f"/home/ubuntu/tools/travel_APP/scripts/mock_A/cmp_{names[i]}.png")
            print("saved", names[i])
        await b.close()

asyncio.run(main())
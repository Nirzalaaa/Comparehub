import asyncio
from playwright.async_api import async_playwright
from scraper import scrape_amazon

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        # Block heavy resources
        await context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot,mp4,webm}", lambda route: route.abort())

        print("Testing Amazon scraper...")
        results = await scrape_amazon(context, "iPhone 15", max_results=5)
        print(f"\nTotal products returned: {len(results)}")
        for p in results:
            print(f"  [{p.get('price')}] {p.get('name')[:80]}")
        await browser.close()

asyncio.run(main())

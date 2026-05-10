import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-IN", timezone_id="Asia/Kolkata"
        )
        
        page = await context.new_page()
        # await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())

        url = "https://www.amazon.in/s?k=iPhone+15"
        print("Goto Amazon:", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)
        print("Page Title:", await page.title())

        html = await page.content()
        with open("amazon_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("Wrote amazon_debug.html")

        # Evaluate the exact JS logic from scraper.py
        max_results = 5
        products = await page.evaluate("""(maxResults) => {
            const items = [];
            const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
            for (const card of cards) {
                if (items.length >= maxResults) break;
                const nameEl = card.querySelector('h2 a span.a-text-normal') || card.querySelector('span.a-text-normal[dir="auto"]');
                let name = nameEl ? nameEl.textContent.trim() : null;
                if (!name) {
                    const fallbackLink = card.querySelector('h2 a');
                    if (fallbackLink) name = fallbackLink.textContent.trim();
                }
                if (!name || name.length < 5) continue;

                const priceEl = card.querySelector('span.a-price-whole');
                const priceText = priceEl ? priceEl.textContent.trim().replace(/[^0-9]/g, '') : null;
                const price = priceText ? parseInt(priceText) : null;
                if (!price || price <= 0) continue;

                items.push({ name, price });
            }
            return items;
        }""", max_results)
        
        print("Extracted Products:", products)
        await browser.close()

asyncio.run(main())

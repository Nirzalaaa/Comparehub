from playwright.sync_api import sync_playwright
import time

def test_scrapers():
    with sync_playwright() as pw:
        # Myntra test
        try:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-http2'
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            print("Fetching Myntra with Chromium...")
            page.goto("https://www.myntra.com/iphone-15", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
            print("Myntra Title:", page.title())
            html = page.content()
            with open("myntra_test.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
        except Exception as e:
            print("Myntra failed:", e)

        # Meesho test
        try:
            browser = pw.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled', '--disable-http2'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            print("Fetching Meesho...")
            page.goto("https://www.meesho.com/search?q=iPhone+15", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
            print("Meesho Title:", page.title())
            html = page.content()
            with open("meesho_test.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
        except Exception as e:
            print("Meesho failed:", e)

if __name__ == "__main__":
    test_scrapers()

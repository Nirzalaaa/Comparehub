import os
import re

file_path = "e:/comparehub/backend/scraper.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Imports
code = code.replace(
    "from concurrent.futures import ThreadPoolExecutor, as_completed",
    "import asyncio\nimport aiohttp\nfrom playwright.async_api import async_playwright"
)

# 2. _get_browser_page and _close_browser (delete them entirely)
# Actually, just leave them but they won't be used, or we can strip them.

# 3. scrape_amazon
code = code.replace(
    "def scrape_amazon(query, max_results=10):",
    "async def scrape_amazon(context, query, max_results=10):"
)
code = code.replace(
    "pw = browser = page = None\n    try:\n        pw, browser, page = _get_browser_page()\n        page.goto",
    "page = await context.new_page()\n    try:\n        await page.goto"
)
code = code.replace("page.wait_for_selector(", "await page.wait_for_selector(")
code = code.replace("page.evaluate(", "await page.evaluate(")
code = code.replace("time.sleep(0.5)", "await asyncio.sleep(0.5)")
code = code.replace(
    "    finally:\n        if pw and browser:\n            _close_browser(pw, browser)",
    "    finally:\n        if 'page' in locals() and page:\n            await page.close()"
)

# 4. scrape_flipkart
code = code.replace(
    "def scrape_flipkart(query, max_results=10):",
    "async def scrape_flipkart(context, query, max_results=10):"
)
code = code.replace(
    "pw = browser = page = None\n    try:\n        pw, browser, page = _get_browser_page()\n        page.goto",
    "page = await context.new_page()\n    try:\n        await page.goto"
)
code = code.replace("time.sleep(1)", "await asyncio.sleep(1)")
code = code.replace("close_btn.count()", "await close_btn.count()")
code = code.replace("close_btn.first.click()", "await close_btn.first.click()")
code = code.replace("time.sleep(0.3)", "await asyncio.sleep(0.3)")

# 5. scrape_meesho
code = code.replace(
    "def scrape_meesho(query, max_results=10):",
    "async def scrape_meesho(context, query, max_results=10):"
)
code = code.replace(
    "pw = browser = page = None\n    try:\n        pw, browser, page = _get_browser_page()\n        page.goto",
    "page = await context.new_page()\n    try:\n        await page.goto"
)

# 6. scrape_myntra
code = code.replace(
    "def scrape_myntra(query, max_results=10):",
    "async def scrape_myntra(session, query, max_results=10):"
)
myntra_req_sync = """    try:
        r = requests.get(url, headers=headers, timeout=15)
        scripts = re.findall(r'<script.*?>.*?</script>', r.text, flags=re.DOTALL)"""
myntra_req_async = """    try:
        async with session.get(url, headers=headers, timeout=15) as r:
            text = await r.text()
            scripts = re.findall(r'<script.*?>.*?</script>', text, flags=re.DOTALL)"""
code = code.replace(myntra_req_sync, myntra_req_async)

# 7. Safe Scrape (we can just delete this whole function since we use ensure_future/gather)

# 8. search_products
old_search_products = re.search(r'def search_products\(query.*?total == 0:\n        return \[\]\n\n    combined = match_products\(results\)\n    log.info\(f"\[Scraper\] Combined: \{len\(combined\)\}"\)\n    return combined', code, re.DOTALL)

new_search_products = """async def search_products(query, max_per_platform=10):
    log.info(f"\\n{'='*50}")
    log.info(f"  Live Scraping (Async): '{query}'")
    log.info(f"{'='*50}")
    
    results = {'amazon': [], 'flipkart': [], 'meesho': [], 'myntra': []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-IN", timezone_id="Asia/Kolkata"
        )
        await context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())

        async with aiohttp.ClientSession() as session:
            amz_res, flp_res, msh_res, myn_res = await asyncio.gather(
                scrape_amazon(context, query, max_per_platform),
                scrape_flipkart(context, query, max_per_platform),
                scrape_meesho(context, query, max_per_platform),
                scrape_myntra(session, query, max_per_platform),
                return_exceptions=True
            )
            
            if not isinstance(amz_res, Exception): results['amazon'] = amz_res
            else: log.error(f"[Amazon] Failed: {amz_res}")
            if not isinstance(flp_res, Exception): results['flipkart'] = flp_res
            else: log.error(f"[Flipkart] Failed: {flp_res}")
            if not isinstance(msh_res, Exception): results['meesho'] = msh_res
            else: log.error(f"[Meesho] Failed: {msh_res}")
            if not isinstance(myn_res, Exception): results['myntra'] = myn_res
            else: log.error(f"[Myntra] Failed: {myn_res}")

        await browser.close()
        
    for p, items in results.items():
        log.info(f"[{p.title()}] → {len(items)} products")

    total = sum(len(v) for v in results.values())
    if total == 0: return []
    
    combined = match_products(results)
    return combined"""

if old_search_products:
    code = code.replace(old_search_products.group(0), new_search_products)

# 9. Smart Match Products
old_match = re.search(r'def match_products\(platform_results\):.*?return combined', code, re.DOTALL)

new_match = """def extract_model_numbers(name):
    return set(re.findall(r'\\b\\d+\\b', name.lower()))

def price_is_similar(p1, p2, threshold=0.40):
    if not p1 or not p2: return True
    diff = abs(p1 - p2)
    avg = (p1 + p2) / 2
    return (diff / avg) <= threshold

def match_products(platform_results):
    combined = []
    platforms = ['amazon', 'flipkart', 'meesho', 'myntra']
    sorted_platforms = sorted(platforms, key=lambda p: len(platform_results.get(p, [])), reverse=True)
    base_platform = sorted_platforms[0]
    base_products = platform_results.get(base_platform, [])

    if not base_products:
        for p in platforms:
            for prod in platform_results.get(p, []):
                combined.append({"name": prod['name'], "prices": {pl: None for pl in platforms}, "links": {pl: None for pl in platforms}, "rating": prod.get('rating', 0), "reviews": prod.get('reviews', 0), "image": prod.get('image')})
                combined[-1]["prices"][p] = prod['price']
                combined[-1]["links"][p] = prod.get('link')
        return combined

    used = {p: set() for p in platforms}
    stop_words = {'the', 'a', 'an', 'for', 'with', 'and', 'in', 'of', 'to', 'by', 'from', 'new', 'best', 'top', 'latest', 'edition', 'pack', 'combo', 'gb', '5g', '4g', 'lte', 'tb', 'pro', 'max', 'plus'}

    for base_prod in base_products:
        base_name_lower = base_prod['name'].lower()
        base_words = set(re.findall(r'\\b[a-z]{2,}\\b', base_name_lower)) - stop_words
        base_nums = extract_model_numbers(base_name_lower)
        base_price = base_prod['price']
        
        product = {"name": base_prod['name'], "prices": {p: None for p in platforms}, "links": {p: None for p in platforms}, "rating": base_prod.get('rating', 0), "reviews": base_prod.get('reviews', 0), "image": base_prod.get('image')}
        product["prices"][base_platform] = base_price
        product["links"][base_platform] = base_prod.get('link')

        for other_p in platforms:
            if other_p == base_platform: continue
            other_list = platform_results.get(other_p, [])
            best_match = None
            best_score = 0
            
            for i, other_prod in enumerate(other_list):
                if i in used[other_p]: continue
                
                other_name_lower = other_prod['name'].lower()
                other_words = set(re.findall(r'\\b[a-z]{2,}\\b', other_name_lower)) - stop_words
                other_nums = extract_model_numbers(other_name_lower)
                other_price = other_prod['price']
                
                if not price_is_similar(base_price, other_price, 0.40):
                    continue
                    
                common = base_words & other_words
                significant = base_words | other_words
                score = len(common) / max(len(significant), 1)
                
                clashing_nums = (base_nums ^ other_nums)
                if len(clashing_nums) > 0 and len(base_nums & other_nums) == 0:
                    score *= 0.1
                elif len(base_nums & other_nums) > 0:
                    score += 0.3
                    
                if score > best_score and score > 0.35:
                    best_score = score
                    best_match = (i, other_prod)

            if best_match:
                idx, matched_prod = best_match
                used[other_p].add(idx)
                product["prices"][other_p] = matched_prod['price']
                product["links"][other_p] = matched_prod.get('link')
                if not product["image"] and matched_prod.get('image'): product["image"] = matched_prod['image']
                if matched_prod.get('rating', 0) > product['rating']: product['rating'] = matched_prod['rating']
                if matched_prod.get('reviews', 0) > product['reviews']: product['reviews'] = matched_prod['reviews']
                    
        combined.append(product)

    for other_p in platforms:
        if other_p == base_platform: continue
        for i, prod in enumerate(platform_results.get(other_p, [])):
            if i not in used[other_p]:
                product = {"name": prod['name'], "prices": {p: None for p in platforms}, "links": {p: None for p in platforms}, "rating": prod.get('rating', 0), "reviews": prod.get('reviews', 0), "image": prod.get('image')}
                product["prices"][other_p] = prod['price']
                product["links"][other_p] = prod.get('link')
                combined.append(product)

    return combined"""

if old_match:
    code = code.replace(old_match.group(0), new_match)

# Update quick test
code = code.replace("results = search_products(", "results = asyncio.run(search_products(")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)
print("Finished rewrite.")

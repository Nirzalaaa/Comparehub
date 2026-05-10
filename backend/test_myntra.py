import requests
from bs4 import BeautifulSoup
import json
import re

def test_myntra():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    url = "https://www.myntra.com/iphone-15"
    print("Fetching Myntra:", url)
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print("Status Code:", r.status_code)
        
        # Method 1: Check for script tags that contain "searchData"
        scripts = re.findall(r'<script.*?>.*?</script>', r.text, flags=re.DOTALL)
        found = False
        for s in scripts:
            if "searchData" in s:
                print("Found searchData in script!")
                match = re.search(r'window\.__myx\s*=\s*(\{.+?\});?<', s)
                if match:
                    data = json.loads(match.group(1))
                    products = data.get('searchData', {}).get('results', {}).get('products', [])
                    print(f"Extracted {len(products)} products from __myx")
                    if products:
                        p = products[0]
                        print("Sample:", p.get('productName'), p.get('price'))
                    found = True
                    break
        
        if not found:
            # Let's see what's in the HTML body
            soup = BeautifulSoup(r.text, 'lxml')
            products = soup.select('li.product-base')
            print(f"Found {len(products)} products using bs4 (li.product-base)")
            if products:
                print(products[0].text)
            else:
                # What are the script tags?
                print("No products found. Dumping script sources and lengths:")
                for s in soup.find_all('script'):
                    content = s.string or ''
                    print(f"Script len: {len(content)}, src: {s.get('src')}")
                    if "products" in content:
                        print(" This script contains 'products'")

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_myntra()

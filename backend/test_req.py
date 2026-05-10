import requests
import json
import re

def test_myntra():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    url = "https://www.myntra.com/iphone-15"
    print("Fetching Myntra...", url)
    r = requests.get(url, headers=headers, timeout=10)
    print("Myntra Status:", r.status_code)
    
    match = re.search(r'window\.__myx\s*=\s*(\{.+?\});</script>', r.text)
    if match:
        data = json.loads(match.group(1))
        products = data.get('searchData', {}).get('results', {}).get('products', [])
        print("Myntra found products:", len(products))
        if products:
            print(products[0].get('productName'), products[0].get('price'))
    else:
        print("No script data found in Myntra")

def test_meesho():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.meesho.com",
    }
    payload = {"query": "iPhone 15", "type": "text_search", "page": 1}
    url = "https://www.meesho.com/api/v4/search"
    print("Fetching Meesho API...", url)
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    print("Meesho Status:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        catalogs = data.get('catalogs', [])
        print("Meesho catalogs found:", len(catalogs))
        if catalogs:
            print(catalogs[0].get('name'), catalogs[0].get('mined_price'))

if __name__ == "__main__":
    test_myntra()
    test_meesho()

import requests

def test_myntra():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0"
    }
    url = "https://www.myntra.com/iphone-15"
    print("Fetching Myntra:", url)
    r = requests.get(url, headers=headers, timeout=10)
    with open("myntra_req.html", "w", encoding="utf-8") as f:
        f.write(r.text)

def test_meesho():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    }
    url = "https://www.meesho.com/search?q=iPhone+15"
    print("Fetching Meesho:", url)
    r = requests.get(url, headers=headers, timeout=10)
    with open("meesho_req.html", "w", encoding="utf-8") as f:
        f.write(r.text)

if __name__ == "__main__":
    test_myntra()
    test_meesho()

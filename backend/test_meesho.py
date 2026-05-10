import requests
import json

def test_meesho():
    # Try the web search with mobile user agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    url = "https://www.meesho.com/search?q=iPhone+15"
    print("Fetching Meesho Mobile Web...")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print("Status", r.status_code)
        if r.status_code == 403:
            print("Access Denied on mobile web.")
        else:
            if "__PRELOADED_STATE__" in r.text or "__NEXT_DATA__" in r.text:
                print("Success! JSON found.")
    except Exception as e:
        print("Error:", e)
        

test_meesho()

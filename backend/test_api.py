import requests
import json

def test_api():
    url = "http://localhost:5000/api/search?q=iPhone+15"
    r = requests.get(url)
    data = r.json()
    with open("api_response.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("API returned", len(data), "items")

if __name__ == "__main__":
    test_api()

import sys
import json
sys.path.append("n:\\comparehub\\backend")
from scraper import scrape_amazon

def test():
    res = scrape_amazon("iPhone 15", max_results=3)
    with open("amz_test.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print("Test finished")

test()

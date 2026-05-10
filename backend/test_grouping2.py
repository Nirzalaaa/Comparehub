import asyncio
from scraper import search_products
import json

async def main():
    results = await search_products("samsung s24 ultra", 5)
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved to results.json")

if __name__ == "__main__":
    asyncio.run(main())

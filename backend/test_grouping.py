import asyncio
from scraper import search_products
import json

async def main():
    results = await search_products("samsung galaxy s24 ultra", 5)
    print("Found products:")
    for r in results[:5]:
        print(f"\nName: {r['name']}")
        print(f"Prices: {r['prices']}")

if __name__ == "__main__":
    asyncio.run(main())

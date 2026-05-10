#!/usr/bin/env python3
import asyncio
import time
import sys
sys.path.insert(0, '.')

from scraper import search_products

print("=" * 60)
print("  FAST SCRAPE TEST")
print("=" * 60)

start = time.time()
results = asyncio.run(search_products('phone', 3))
elapsed = time.time() - start

print(f"\nResults: {len(results)} products")
print(f"Time: {elapsed:.1f} seconds\n")

for i, p in enumerate(results[:3], 1):
    print(f"{i}. {p['name'][:50]}...")
    amazon_price = p['prices'].get('amazon')
    if amazon_price:
        print(f"   Amazon: Rs {amazon_price}")

print("=" * 60)

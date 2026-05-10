#!/usr/bin/env python3
"""
Quick test runner to verify the application works
"""
import asyncio
import sys

print("=" * 60)
print("  CompareHub – Testing Web Scraper")
print("=" * 60)

# Test imports
print("\n[1/3] Testing imports...")
try:
    from scraper import search_products
    from matcher import group_matched_products
    print("  OK - All imports successful")
except Exception as e:
    print(f"  FAILED - Import error: {e}")
    sys.exit(1)

# Test Flask
print("\n[2/3] Testing Flask app...")
try:
    from app import app
    print("  OK - Flask app loaded")
except Exception as e:
    print(f"  FAILED - Flask error: {e}")
    sys.exit(1)

# Test scraper with simple query
print("\n[3/3] Testing scraper with simple query...")
try:
    print("  Running: search_products('phone', max_per_platform=3)")
    results = asyncio.run(search_products('phone', max_per_platform=3))
    print(f"  OK - Got {len(results)} product groups")
    if results:
        print(f"  Sample: {results[0]['name']}")
except Exception as e:
    print(f"  FAILED - Scraper error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("  All tests passed! Application is ready.")
print("  Run: python app.py")
print("=" * 60)

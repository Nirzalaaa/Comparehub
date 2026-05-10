"""
CompareHub – Flask Backend Server
Live web scraping from Amazon.in, Flipkart, Meesho & Myntra
Uses in-memory cache for speed, async scraping for active queries.
Serves frontend files from parent directory.
"""

import os
import asyncio
import difflib
import re
import threading
from dotenv import load_dotenv

load_dotenv(override=True)

from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
from scraper import (
    search_products,
    scrape_raw_products,
    canonicalize_search_query,
    build_search_intelligence,
)
import logging
from cachetools import TTLCache

import google.generativeai as genai
from PIL import Image

GEMINI_API_KEY = os.getenv("COMPAREHUB_GEMINI_API_KEY", "").strip()
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api")

# Serve frontend from parent directory (n:\comparehub)
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

# In-memory TTL cache (1 hour)
product_cache = TTLCache(maxsize=150, ttl=3600)
CACHE_KEY_VERSION = "match-v7"
inflight_searches = {}
inflight_lock = threading.Lock()
POPULAR_PRODUCTS = [
    "iPhone 15",
    "iPhone 15 Pro",
    "Samsung Galaxy S24",
    "Samsung Galaxy S24 Ultra",
    "OnePlus 12",
    "Nothing Phone 2",
    "Google Pixel 8",
    "MacBook Air M3",
    "HP Pavilion Laptop",
    "Lenovo IdeaPad",
    "Sony WH-1000XM5",
    "boAt Airdopes",
    "Apple AirPods Pro",
    "LG OLED TV",
    "Samsung Smart TV",
    "Nike Shoes",
    "Adidas Sneakers",
    "Casio Watch",
    "Titan Watch",
    "Fire-Boltt Smartwatch",
]
POPULAR_PRODUCTS_BY_CATEGORY = {
    "Mobiles": ["iPhone 15", "Samsung Galaxy S24", "OnePlus 12", "Nothing Phone 2"],
    "Laptops": ["MacBook Air M3", "HP Pavilion Laptop", "Lenovo IdeaPad", "Dell Inspiron"],
    "TVs": ["LG OLED TV", "Samsung Smart TV", "Sony Bravia TV", "TCL QLED TV"],
    "Audio": ["Sony WH-1000XM5", "boAt Airdopes", "Apple AirPods Pro", "JBL Speaker"],
    "Electronics": ["Gaming Mouse", "Mechanical Keyboard", "Phone Charger", "Power Bank"],
    "Appliances": ["Washing Machine", "Refrigerator", "Water Purifier", "Microwave Oven"],
    "Watches": ["Casio Watch", "Titan Watch", "Fire-Boltt Smartwatch", "Noise Smartwatch"],
    "Fashion": ["Short Kurti", "Kurta Set", "Silver Ring", "Nike Shoes", "Saree"],
    "Home": ["Dining Table", "Office Chair", "Sofa Set", "Mattress", "Bed Sheet"],
    "Stationery": ["Ball Pen", "Gel Pen", "Notebook", "Marker", "Diary"],
    "Beauty": ["Lipstick", "Perfume", "Face Wash", "Shampoo", "Moisturizer"],
    "Grocery": ["Basmati Rice", "Atta", "Sunflower Oil", "Tea", "Snack Pack"],
}

try:
    DEFAULT_MAX_PER_PLATFORM = max(1, int(os.getenv("COMPAREHUB_MAX_PER_PLATFORM", "5")))
except ValueError:
    DEFAULT_MAX_PER_PLATFORM = 5


def _normalize_term(text):
    if not text:
        return ""
    cleaned = re.sub(r"[^a-z0-9]+", " ", canonicalize_search_query(text))
    return re.sub(r"\s+", " ", cleaned).strip()


def _dedupe_terms(items):
    seen = set()
    output = []
    for item in items:
        value = (item or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _popular_products_for_category(category):
    category_items = POPULAR_PRODUCTS_BY_CATEGORY.get(category, [])
    return _dedupe_terms(category_items + POPULAR_PRODUCTS)


def _search_intelligence_payload(query_info):
    return {
        "category": query_info["category"],
        "category_source": query_info.get("category_source"),
        "category_confidence": query_info.get("category_confidence"),
        "spell_corrected": query_info.get("spell_corrected"),
        "rewrites": query_info.get("rewrites", [])[:3],
    }


def _extract_cached_queries():
    prefix = f"{CACHE_KEY_VERSION}:"
    queries = []
    for key in list(product_cache.keys()):
        if isinstance(key, str) and key.startswith(prefix):
            query = key[len(prefix):].strip()
            if query:
                queries.append(query)
    return _dedupe_terms(queries)


def _extract_cached_product_names(limit=500):
    names = []
    for cached_results in list(product_cache.values()):
        if not isinstance(cached_results, list):
            continue
        for item in cached_results:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            if not name:
                continue
            names.append(name)
            if len(names) >= limit:
                return _dedupe_terms(names)
    return _dedupe_terms(names)


def _score_suggestion(query, candidate):
    q_norm = _normalize_term(query)
    c_norm = _normalize_term(candidate)
    if not q_norm or not c_norm:
        return 0.0

    score = difflib.SequenceMatcher(None, q_norm, c_norm).ratio() * 100
    if q_norm in c_norm:
        score += 35
        if c_norm.startswith(q_norm):
            score += 20

    q_tokens = set(q_norm.split())
    c_tokens = set(c_norm.split())
    if q_tokens and c_tokens:
        overlap = len(q_tokens & c_tokens)
        score += overlap * 12
        if overlap == len(q_tokens):
            score += 15
    return score


def _rank_candidates(query, candidates, limit=8, min_score=55):
    ranked = []
    seen = set()
    for candidate in candidates:
        label = (candidate or "").strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        score = _score_suggestion(query, label)
        if score < min_score:
            continue
        ranked.append((score, label))

    ranked.sort(key=lambda item: (-item[0], item[1].lower()))
    return [label for _, label in ranked[:limit]]


def _merge_suggestion_buckets(limit, *bucket_specs):
    merged = []
    seen = set()
    for values, bucket_type in bucket_specs:
        for value in values:
            if len(merged) >= limit:
                return merged
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append({
                "text": value,
                "type": bucket_type
            })
    return merged

def no_cache_response(data, status=200):
    """Create a JSON response with no-cache headers."""
    resp = make_response(jsonify(data), status)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


def _compact_products_payload(products):
    """Reduce payload size for faster API responses."""
    compact = []
    for item in products or []:
        if not isinstance(item, dict):
            continue
        compact.append({
            "name": item.get("name"),
            "model": item.get("model") or item.get("name"),
            "model_key": item.get("model_key"),
            "prices": item.get("prices") or {},
            "links": item.get("links") or {},
            "variants": item.get("variants") or [],
            "variant_count": item.get("variant_count") or 0,
            "confidence": item.get("confidence"),
            "rating": item.get("rating") or 0,
            "reviews": item.get("reviews") or 0,
            "image": item.get("image"),
        })
    return compact


# ── Frontend routes ──────────────────────────────────────────
@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)


@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)


# ── API routes ───────────────────────────────────────────────
@app.route('/api/status')
def api_status():
    return no_cache_response({
        "status": "online",
        "service": "CompareHub API - Live Scraping (fresh results)",
    })

@app.route('/api/search')
def api_search():
    raw_query = request.args.get('q', '').strip()
    log.info(f"[API] /api/search received q='{raw_query}'")
    query_info = build_search_intelligence(raw_query)
    query = query_info["normalized_query"]
    if not query:
        return no_cache_response({"error": "Missing query parameter 'q'"}, 400)

    try:
        cache_key = query.lower()

        # Coalesce duplicate in-flight search requests for same query.
        with inflight_lock:
            active_job = inflight_searches.get(cache_key)
            if active_job is None:
                active_job = {
                    "event": threading.Event(),
                    "results": None,
                    "error": None,
                }
                inflight_searches[cache_key] = active_job
                is_owner = True
            else:
                is_owner = False

        if not is_owner:
            log.info(f"[API] Joining in-flight scrape for: '{query}'")
            active_job["event"].wait(timeout=80)

            if active_job.get("error") is None and active_job.get("results") is not None:
                joined_results = _compact_products_payload(active_job["results"])
                return no_cache_response({
                    "query": raw_query,
                    "normalized_query": query,
                    "search_intelligence": _search_intelligence_payload(query_info),
                    "source": "coalesced",
                    "count": len(joined_results),
                    "products": joined_results
                })

        log.info(f"[API] Live scraping for: '{query}'")
        results = asyncio.run(search_products(query, max_per_platform=DEFAULT_MAX_PER_PLATFORM))
        compact_results = _compact_products_payload(results)

        if compact_results:
            response = no_cache_response({
                "query": raw_query,
                "normalized_query": query,
                "search_intelligence": _search_intelligence_payload(query_info),
                "source": "live",
                "count": len(compact_results),
                "products": compact_results
            })
        else:
            response = no_cache_response({
                "query": raw_query,
                "normalized_query": query,
                "search_intelligence": _search_intelligence_payload(query_info),
                "source": "live",
                "count": 0,
                "products": [],
                "message": "No products found. Try again or refine your search."
            })

        if is_owner:
            active_job["results"] = compact_results
            active_job["event"].set()
            with inflight_lock:
                inflight_searches.pop(cache_key, None)

        return response
    except Exception as e:
        cache_key = query.lower()
        with inflight_lock:
            active_job = inflight_searches.get(cache_key)
            if active_job is not None:
                active_job["error"] = str(e)
                active_job["event"].set()
                inflight_searches.pop(cache_key, None)

        log.error(f"[API] Scraping error: {e}")
        return no_cache_response({
            "query": raw_query,
            "normalized_query": query,
            "search_intelligence": {
                "category": query_info["category"],
                "spell_corrected": query_info.get("spell_corrected"),
                "rewrites": query_info.get("rewrites", [])[:3],
            },
            "source": "error",
            "count": 0,
            "products": [],
            "message": f"Scraping error: {str(e)}"
        }, 500)


@app.route('/api/scrape/raw')
def api_scrape_raw():
    """Return raw Amazon/Flipkart product rows from scraping pipeline."""
    raw_query = request.args.get('q', '').strip()
    query_info = build_search_intelligence(raw_query)
    query = query_info["normalized_query"]
    if not query:
        return no_cache_response({"error": "Missing query parameter 'q'"}, 400)

    try:
        try:
            max_per_platform = int(request.args.get('limit', str(DEFAULT_MAX_PER_PLATFORM)))
        except ValueError:
            max_per_platform = DEFAULT_MAX_PER_PLATFORM
        max_per_platform = max(1, min(max_per_platform, 20))

        raw_data = asyncio.run(scrape_raw_products(query, max_per_platform=max_per_platform))
        return no_cache_response({
            "query": raw_query,
            "normalized_query": query,
            "source": "live",
            "search_intelligence": _search_intelligence_payload(query_info),
            "count": raw_data.get("total", 0),
            "platforms": raw_data.get("platforms", {"amazon": [], "flipkart": []}),
        })
    except Exception as e:
        log.error(f"[API][raw] Scraping error: {e}")
        return no_cache_response({
            "query": raw_query,
            "normalized_query": query,
            "source": "error",
            "count": 0,
            "platforms": {"amazon": [], "flipkart": []},
            "message": f"Scraping error: {str(e)}"
        }, 500)


@app.route('/api/cache/clear', methods=['GET', 'POST'])
def api_cache_clear():
    """Clear the product cache manually (useful after scraper fixes)."""
    raw_query = request.args.get('q', '').strip()
    query = canonicalize_search_query(raw_query)
    if query:
        suffix = query.lower()
        keys_to_delete = [k for k in list(product_cache.keys()) if k.endswith(f":{suffix}") or k == suffix]
        if keys_to_delete:
            for key in keys_to_delete:
                del product_cache[key]
            log.info(f"[API] Cache cleared for: '{query}'")
            return no_cache_response({"message": f"Cache cleared for: '{raw_query}'", "normalized_query": query})
        return no_cache_response({"message": f"No cache entry for: '{raw_query}'", "normalized_query": query})
    else:
        count = len(product_cache)
        product_cache.clear()
        log.info(f"[API] Full cache cleared ({count} entries)")
        return no_cache_response({"message": f"Full cache cleared ({count} entries removed)"})

@app.route('/api/trending')
def api_trending():
    """Return trending search suggestions."""
    trending = POPULAR_PRODUCTS[:8]
    return no_cache_response({
        "suggestions": trending
    })


@app.route('/api/suggestions')
def api_suggestions():
    """Return fast suggestions for typeahead and no-result alternatives."""
    raw_query = request.args.get('q', '').strip()
    query_info = build_search_intelligence(raw_query)
    query = query_info["normalized_query"]
    try:
        limit = int(request.args.get('limit', '12'))
    except ValueError:
        limit = 12
    limit = max(4, min(limit, 20))

    cached_queries = _extract_cached_queries()
    cached_product_names = _extract_cached_product_names(limit=700)
    popular = _popular_products_for_category(query_info.get("category"))
    query_norm = _normalize_term(query)

    if not query_norm:
        popular = _dedupe_terms(POPULAR_PRODUCTS)
        suggestions = _merge_suggestion_buckets(
            limit,
            (cached_queries[: max(3, limit // 3)], "history"),
            (popular[:limit], "popular"),
        )
        return no_cache_response({
            "query": raw_query,
            "normalized_query": query,
            "suggestions": suggestions,
            "did_you_mean": [],
            "related_products": popular[:6],
            "trending": popular[:8],
        })

    product_matches = _rank_candidates(query, cached_product_names, limit=limit, min_score=45)
    history_matches = _rank_candidates(query, cached_queries, limit=max(4, limit // 2), min_score=42)
    popular_matches = _rank_candidates(query, popular, limit=max(4, limit // 2), min_score=38)

    suggestions = _merge_suggestion_buckets(
        limit,
        (history_matches, "history"),
        (popular_matches, "popular"),
        (product_matches, "product"),
    )

    if not suggestions:
        suggestions = _merge_suggestion_buckets(
            limit,
            (popular[:limit], "popular"),
            (cached_queries[: max(2, limit // 4)], "history"),
        )

    did_you_mean = []
    if query_info.get("spell_corrected") and _normalize_term(query_info["spell_corrected"]) != query_norm:
        did_you_mean.append(query_info["spell_corrected"])
    spelling_pool = _dedupe_terms(cached_queries + popular)
    normalized_map = {}
    for term in spelling_pool:
        normalized_map.setdefault(_normalize_term(term), term)

    close_norm_terms = difflib.get_close_matches(
        query_norm,
        list(normalized_map.keys()),
        n=6,
        cutoff=0.62,
    )
    for norm_term in close_norm_terms:
        suggestion = normalized_map.get(norm_term)
        if not suggestion:
            continue
        if _normalize_term(suggestion) == query_norm:
            continue
        did_you_mean.append(suggestion)
        if len(did_you_mean) >= 3:
            break

    if not did_you_mean:
        did_you_mean = _rank_candidates(query, spelling_pool, limit=3, min_score=55)
        did_you_mean = [term for term in did_you_mean if _normalize_term(term) != query_norm][:3]
    else:
        extras = _rank_candidates(query, spelling_pool, limit=3, min_score=55)
        for term in extras:
            if _normalize_term(term) == query_norm or term in did_you_mean:
                continue
            did_you_mean.append(term)
            if len(did_you_mean) >= 3:
                break

    related_products = product_matches[:6]
    if len(related_products) < 6:
        extra = [item for item in popular if item.casefold() not in {r.casefold() for r in related_products}]
        related_products = (related_products + extra)[:6]

    return no_cache_response({
        "query": raw_query,
        "normalized_query": query,
        "search_intelligence": _search_intelligence_payload(query_info),
        "suggestions": suggestions,
        "did_you_mean": did_you_mean,
        "related_products": related_products,
        "trending": popular[:8],
    })

@app.route('/api/identify-image', methods=['POST'])
def api_identify_image():
    """Identify product from image and return a text query."""
    if not GEMINI_API_KEY:
        return no_cache_response({"message": "Gemini API key not configured"}, 500)

    if 'image' not in request.files:
        return no_cache_response({"message": "No image uploaded"}, 400)

    file = request.files['image']
    if file.filename == '':
        return no_cache_response({"message": "No specific file selected"}, 400)

    try:
        img = Image.open(file)
        # Convert to RGB to ensure compatibility
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Shrink the image to save bandwidth and API limits
        img.thumbnail((800, 800))
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = (
            "Analyze this image and identify the primary product shown. "
            "Return ONLY the exact brand and model name of the product that would be best to use as a search query on an e-commerce site. "
            "Do not include any descriptive text, bullet points, or punctuation. "
            "If you cannot confidently identify the product, return 'UNKNOWN'."
        )
        
        response = model.generate_content([prompt, img])
        query = response.text.strip()
        
        if query == "UNKNOWN" or not query:
            return no_cache_response({"message": "Could not identify the product"}, 400)
            
        log.info(f"[API] Image search identified product: {query}")
        return no_cache_response({"query": query})
    except Exception as e:
        log.error(f"[API] Image identification error: {e}")
        return no_cache_response({"message": str(e)}, 500)

if __name__ == '__main__':
    print("=" * 50)
    print("  CompareHub - Async Live Scraping")
    print("  http://localhost:5000")
    print("  Fresh results only: no search cache")
    print("  Scrapes: Amazon, Flipkart, Myntra")
    print("  Meesho: only for selected home/beauty/stationery queries")
    print("=" * 50)
    app.run(debug=True, port=5000, use_reloader=False)


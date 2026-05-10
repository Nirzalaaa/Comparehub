"""
CompareHub â€“ Live Web Scraper Engine v2
========================================
Uses Playwright (headless Chromium) for ALL platforms.
Single shared browser instance for speed.
Smart selectors with fallback chains.
Fast-fail: 1 retry max, short delays.
"""

import re
import json
import time
import random
import difflib
import os
from matcher import ProductMatcher, group_matched_products as match_products
import logging
import requests
import asyncio
import aiohttp
from urllib.parse import quote_plus, urlparse, urlunparse, unquote
from playwright.async_api import async_playwright

# â”€â”€ Logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scraper")
PRODUCT_MATCHER = ProductMatcher()
DEFAULT_QUERY_CATEGORY = "General"
REQUEST_TIMEOUT_SECONDS = 20
HEADLESS_BROWSER = os.getenv("COMPAREHUB_HEADLESS", "1").strip().lower() not in {"0", "false", "no"}
AI_CATEGORY_ENDPOINT = os.getenv("COMPAREHUB_AI_CATEGORY_ENDPOINT", "").strip()
AI_EXTRACTION_ENDPOINT = os.getenv("COMPAREHUB_AI_EXTRACT_ENDPOINT", "").strip()
GEMINI_API_KEY = os.getenv("COMPAREHUB_GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("COMPAREHUB_GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
FORCED_USER_AGENT = os.getenv(
    "COMPAREHUB_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
).strip()
LIGHTWEIGHT_MODE = os.getenv("COMPAREHUB_LIGHTWEIGHT", "1").strip().lower() not in {"0", "false", "no"}
SUPPORTED_PLATFORMS = ("amazon", "flipkart", "meesho", "myntra")

try:
    AI_FALLBACK_MIN_RESULTS = max(1, int(os.getenv("COMPAREHUB_AI_FALLBACK_MIN_RESULTS", "2")))
except ValueError:
    AI_FALLBACK_MIN_RESULTS = 2

try:
    AI_LOW_CONFIDENCE_THRESHOLD = min(
        0.95,
        max(0.3, float(os.getenv("COMPAREHUB_LOW_CONFIDENCE_THRESHOLD", "0.56"))),
    )
except ValueError:
    AI_LOW_CONFIDENCE_THRESHOLD = 0.56

try:
    AI_FALLBACK_HTML_MAX_CHARS = max(4000, int(os.getenv("COMPAREHUB_AI_HTML_MAX_CHARS", "20000")))
except ValueError:
    AI_FALLBACK_HTML_MAX_CHARS = 20000

try:
    AI_FALLBACK_TIMEOUT_SECONDS = max(2, int(os.getenv("COMPAREHUB_AI_FALLBACK_TIMEOUT", "8")))
except ValueError:
    AI_FALLBACK_TIMEOUT_SECONDS = 8

DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]
MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
]
BROWSER_PROFILES = [
    {"user_agent": DESKTOP_USER_AGENTS[0], "viewport": {"width": 1366, "height": 768}},
    {"user_agent": DESKTOP_USER_AGENTS[1], "viewport": {"width": 1440, "height": 900}},
    {"user_agent": DESKTOP_USER_AGENTS[2], "viewport": {"width": 1536, "height": 864}},
]
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
window.chrome = { runtime: {} };
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters)
  );
}
"""
CATEGORY_PRIORITY = [
    "Mobiles",
    "Laptops",
    "TVs",
    "Audio",
    "Watches",
    "Fashion",
    "Beauty",
    "Home",
    "Stationery",
    "Grocery",
    "Appliances",
    "Electronics",
    DEFAULT_QUERY_CATEGORY,
]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  UTILITY FUNCTIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def clean_price(price_text):
    """Extract numeric price from text like 'â‚¹1,29,999'."""
    if not price_text:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
    if cleaned:
        try:
            val = float(cleaned)
            if val > 0:
                return int(val)
        except ValueError:
            pass
    return None


def clean_rating(rating_text):
    """Extract numeric rating from text."""
    if not rating_text:
        return None
    numbers = re.findall(r'(\d+\.?\d*)', rating_text)
    if numbers:
        val = float(numbers[0])
        if 0 < val <= 5:
            return round(val, 1)
    return None


def extract_number(text):
    """Extract a number from text like '1,234 ratings'."""
    if not text:
        return 0
    text = text.replace(',', '')
    nums = re.findall(r'(\d+)', text)
    return int(nums[0]) if nums else 0


def _extract_capacity_variant_snippet(lines):
    """Find variant/storage snippets like '512 GB + 12 GB' from card text lines."""
    if not lines:
        return None

    def _normalize_snippet(text):
        if not text:
            return None
        match = re.search(r"(\d+\s*(?:gb|tb)\s*\+\s*\d+\s*gb)", text, flags=re.IGNORECASE)
        if not match:
            return None
        snippet = re.sub(r"\s+", " ", match.group(1)).strip()
        snippet = re.sub(r"\b(gb|tb)\b", lambda m: m.group(1).upper(), snippet, flags=re.IGNORECASE)
        return snippet

    normalized_lines = [str(line or "").strip() for line in lines if str(line or "").strip()]
    for idx, line in enumerate(normalized_lines):
        direct = _normalize_snippet(line)
        if direct:
            return direct

        lowered = line.lower().rstrip(":")
        if lowered in {"variant", "variants", "storage", "ram"} and idx + 1 < len(normalized_lines):
            follow = _normalize_snippet(normalized_lines[idx + 1])
            if follow:
                return follow

        if "variant" in lowered:
            inline = _normalize_snippet(line)
            if inline:
                return inline

    return None


def _append_capacity_variant_to_name(name, lines):
    """Append extracted RAM/storage variant text to the title when it's missing."""
    base_name = str(name or "").strip()
    if not base_name:
        return base_name

    snippet = _extract_capacity_variant_snippet(lines)
    if not snippet:
        return base_name

    normalized_name = canonicalize_search_query(base_name)
    normalized_snippet = canonicalize_search_query(snippet)
    if normalized_snippet and normalized_snippet in normalized_name:
        return base_name

    return f"{base_name} {snippet}".strip()


def _canonicalize_product_link(link, platform=None):
    """Strip marketplace tracking noise so dedupe and matching use stable product URLs."""
    raw_link = str(link or "").strip()
    if not raw_link:
        return ""

    try:
        parsed = urlparse(raw_link)
    except Exception:
        return raw_link

    if not parsed.scheme or not parsed.netloc:
        return raw_link

    netloc = parsed.netloc.lower()
    path = parsed.path or ""

    if platform == "amazon" or "amazon." in netloc:
        dp_match = re.search(r"/dp/([A-Z0-9]{10})", path, re.IGNORECASE)
        gp_match = re.search(r"/gp/product/([A-Z0-9]{10})", path, re.IGNORECASE)
        asin = (dp_match or gp_match).group(1).upper() if (dp_match or gp_match) else None
        if asin:
            return f"https://www.amazon.in/dp/{asin}"

    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _normalize_link_for_filter(link):
    """Use only the stable URL path for relevance checks, never tracking query params."""
    raw_link = str(link or "").strip()
    if not raw_link:
        return ""
    try:
        parsed = urlparse(raw_link)
        path = unquote(parsed.path or "")
    except Exception:
        path = raw_link
    return _normalize_text_for_filter(path)


def _amazon_name_looks_low_quality(name, card_text=""):
    """Reject sponsored or fragment-like Amazon titles before validation."""
    lowered = (name or "").strip().lower()
    if not lowered:
        return True
    if lowered.startswith("+") or lowered.startswith("sponsored"):
        return True

    bad_phrases = (
        "other colors/patterns",
        "other colour/patterns",
        "other colors",
        "other colours",
        "other color",
        "other colour",
        "limited time deal",
        "see all buying options",
        "shop now",
    )
    if any(phrase in lowered for phrase in bad_phrases):
        return True

    card_text_lower = (card_text or "").lower()
    if "sponsored" in card_text_lower and lowered.startswith("+"):
        return True
    return False


QUERY_STOP_WORDS = {
    "buy", "with", "and", "for", "the", "new", "latest", "online",
    "amazon", "flipkart", "meesho", "myntra", "in", "on", "at",
    "under", "below", "above", "around", "within", "budget", "price", "rs", "inr", "than"
}
GENERIC_QUERY_ALPHA_TOKENS = {
    "phone", "mobile", "smartphone", "tv", "television", "laptop", "notebook",
    "headphone", "headphones", "earphone", "earphones", "earbud", "earbuds",
    "speaker", "soundbar", "watch", "smartwatch", "shoe", "shoes", "sneaker",
    "sneakers", "shirt", "jeans", "dress", "kurta", "kurti", "saree", "jacket", "hoodie",
    "smart", "audio", "appliance"
}
QUERY_ALIAS_PATTERNS = (
    (r"\bi[\s-]*phone\b", "iphone"),
    (r"\bone[\s-]*plus\b", "oneplus"),
    (r"\bair[\s-]*pods?\b", "airpods"),
    (r"\bmac[\s-]*book\b", "macbook"),
    (r"\bplay[\s-]*station\b", "playstation"),
    (r"\bfire[\s-]*boltt\b", "fireboltt"),
    (r"\bg[\s-]*shock\b", "gshock"),
)
QUERY_TERM_SYNONYMS = {
    "cellphone": "phone",
    "cellphones": "phone",
    "phones": "phone",
    "mobiles": "mobile",
    "smartphones": "smartphone",
    "laptops": "laptop",
    "watches": "watch",
    "television": "tv",
    "smarttv": "tv",
    "notebook": "laptop",
    "earbud": "earbuds",
    "earphone": "earphones",
    "buds": "earbuds",
    "earbuds": "earbuds",
    "fridge": "refrigerator",
    "sneakers": "sneakers",
    "trainers": "sneakers",
    "pens": "pen",
    "pencils": "pencil",
    "markers": "marker",
    "notebooks": "notebook",
    "diaries": "diary",
    "registers": "register",
    "shirts": "shirt",
    "tshirts": "tshirt",
    "tops": "top",
    "dresses": "dress",
    "kurtas": "kurta",
    "kurtis": "kurti",
    "sandals": "sandal",
    "chairs": "chair",
    "tables": "table",
    "beds": "bed",
    "mattresses": "mattress",
    "creams": "cream",
    "perfumes": "perfume",
    "snacks": "snack",
    "biscuits": "biscuit",
    "noodles": "noodle",
    "chargers": "charger",
    "cables": "cable",
}
QUERY_TOKEN_EQUIVALENTS = {
    "kurta": {"kurti"},
    "kurti": {"kurta"},
}
QUERY_SYNONYM_EXPANSIONS = {
    "Mobiles": {"phone": {"mobile", "smartphone"}, "mobile": {"phone", "smartphone"}},
    "Laptops": {"laptop": {"notebook"}, "notebook": {"laptop"}},
    "TVs": {"tv": {"television", "smarttv"}, "oled": {"oled"}, "qled": {"qled"}},
    "Audio": {"earbuds": {"buds", "earphones"}, "headphones": {"headphone"}},
    "Fashion": {
        "shoes": {"sneakers", "footwear"},
        "sneakers": {"shoes"},
        "kurta": {"kurti"},
        "kurti": {"kurta"},
    },
}
SEARCH_VOCABULARY = {
    "apple", "iphone", "samsung", "galaxy", "google", "pixel", "oneplus", "nothing",
    "motorola", "redmi", "realme", "oppo", "vivo", "poco", "sony", "boat", "boAt",
    "airpods", "jbl", "noise", "fireboltt", "lg", "hp", "lenovo", "dell", "asus",
    "acer", "macbook", "nike", "adidas", "puma", "casio", "titan", "fastrack",
    "watch", "smartwatch", "tv", "oled", "qled", "monitor", "laptop", "headphones",
    "earbuds", "speaker", "soundbar", "shoes", "sneakers", "running", "men", "women",
    "kids", "black", "white", "blue", "pink", "silver", "gold", "ultra", "plus", "pro",
    "max", "mini", "air", "pad", "buds", "wh", "wf", "xm", "airpods", "bravia",
    "kurta", "kurti", "tshirt", "tops", "leggings",
}
COMMON_QUERY_CORRECTIONS = {
    "iphon": "iphone",
    "ifone": "iphone",
    "samsng": "samsung",
    "samung": "samsung",
    "galxy": "galaxy",
    "macbok": "macbook",
    "lptop": "laptop",
    "hedphones": "headphones",
    "earbudss": "earbuds",
    "nik": "nike",
    "adids": "adidas",
}

QUERY_CATEGORY_KEYWORDS = {
    "Mobiles": {
        "iphone", "phone", "mobile", "galaxy", "pixel", "oneplus", "redmi", "realme",
        "oppo", "vivo", "poco", "nothing", "motorola", "smartphone"
    },
    "Laptops": {
        "laptop", "macbook", "notebook", "ideapad", "thinkpad", "pavilion", "rog",
        "vivobook", "inspiron", "xps", "chromebook"
    },
    "TVs": {
        "tv", "television", "qled", "oled", "bravia", "smarttv"
    },
    "Audio": {
        "headphone", "headphones", "earbuds", "earbud", "speaker", "soundbar",
        "airpods", "earphone", "audio", "buds"
    },
    "Electronics": {
        "mouse", "keyboard", "charger", "cable", "adapter", "powerbank", "tablet",
        "printer", "router", "camera", "tripod", "ssd", "pendrive", "usb", "console",
        "joystick", "webcam", "monitor", "projector"
    },
    "Appliances": {
        "refrigerator", "fridge", "washing", "microwave", "vacuum", "geyser",
        "ac", "cooler", "purifier", "appliance"
    },
    "Watches": {
        "watch", "smartwatch", "gshock", "g-shock", "casio", "fastrack", "titan",
        "fireboltt", "fire-boltt", "noise"
    },
    "Fashion": {
        "shoe", "shoes", "sneaker", "sneakers", "shirt", "shirts", "tshirt",
        "tshirts", "top", "tops", "jeans", "dress", "dresses", "kurta", "kurtas",
        "kurti", "kurtis", "saree", "leggings", "jacket", "hoodie", "sandals",
        "sandal", "lehenga", "blouse", "dupatta", "palazzo", "outfit", "footwear",
        "ring", "earring", "bracelet", "necklace", "jewellery", "jewelry",
        "nike", "adidas", "puma", "levis"
    },
    "Home": {
        "sofa", "table", "chair", "bed", "mattress", "pillow", "curtain", "cushion",
        "wardrobe", "cupboard", "lamp", "shelf", "decor", "furniture", "cabinet"
    },
    "Stationery": {
        "pen", "pencil", "notebook", "marker", "eraser", "stapler", "highlighter",
        "diary", "register", "sketchbook", "stationery"
    },
    "Beauty": {
        "cream", "makeup", "lipstick", "perfume", "serum", "shampoo", "conditioner",
        "cleanser", "moisturizer", "lotion", "sunscreen", "cosmetic", "foundation",
        "mascara", "kajal", "facewash"
    },
    "Grocery": {
        "rice", "atta", "oil", "snack", "biscuit", "coffee", "tea", "masala",
        "dal", "noodle", "cereal", "dryfruit", "flour", "sugar", "salt", "grocery"
    },
}
QUERY_CATEGORY_PHRASES = {
    "Mobiles": {"mobile phone"},
    "TVs": {"smart tv"},
    "Audio": {"wireless earbuds", "bluetooth speaker"},
    "Electronics": {"gaming mouse", "mechanical keyboard", "phone charger", "power bank", "smart ring"},
    "Appliances": {"washing machine", "air conditioner", "water purifier"},
    "Fashion": {"wedding outfit", "kurta set", "short kurti", "running shoes", "engagement ring"},
    "Home": {"dining table", "office chair", "bed sheet", "study table", "bean bag"},
    "Stationery": {"ball pen", "gel pen", "spiral notebook"},
    "Beauty": {"face wash", "hair oil", "body lotion", "lip balm"},
    "Grocery": {"olive oil", "instant noodle", "protein bar"},
}
FASHION_REWRITE_ANCHOR_TOKENS = {
    "shoe", "shoes", "sneaker", "sneakers", "shirt", "shirts", "tshirt", "tshirts",
    "top", "tops", "jeans", "dress", "dresses", "kurta", "kurtas", "kurti", "kurtis",
    "saree", "leggings", "jacket", "hoodie", "sandals", "outfit", "lehenga", "blouse",
    "dupatta", "palazzo", "footwear", "ring", "earring", "bracelet", "necklace",
}

DEVICE_QUERY_CATEGORIES = {"Mobiles", "Laptops", "TVs", "Audio", "Appliances", "Electronics", "Watches"}
PLATFORM_CATEGORY_MAP = {
    "amazon": set(QUERY_CATEGORY_KEYWORDS.keys()) | {DEFAULT_QUERY_CATEGORY},
    "flipkart": set(QUERY_CATEGORY_KEYWORDS.keys()) | {DEFAULT_QUERY_CATEGORY},
    "meesho": {"Home", "Beauty", "Stationery"},
    "myntra": {"Fashion", "Watches", "Beauty"},
}


def _normalize_text_for_filter(text):
    """Normalize text for query-to-title relevance filtering."""
    if not text:
        return ""
    text = canonicalize_search_query(text)
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-z])', r'\1 \2', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    tokens = [QUERY_TERM_SYNONYMS.get(token, token) for token in text.split()]
    return " ".join(tokens).strip()


def canonicalize_search_query(query):
    """Collapse common split brand phrases into their standard searchable forms."""
    if not query:
        return ""
    normalized = re.sub(r"\s+", " ", query.strip().lower()).replace("+", " plus ")
    for pattern, replacement in QUERY_ALIAS_PATTERNS:
        normalized = re.sub(pattern, replacement, normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _strip_price_constraints(query):
    """Remove budget phrases so matching focuses on the product itself."""
    if not query:
        return ""
    normalized = canonicalize_search_query(query)
    price_patterns = [
        r"\bunder\s+(?:rs\.?\s*)?\d+(?:[.,]\d+)?\b",
        r"\bbelow\s+(?:rs\.?\s*)?\d+(?:[.,]\d+)?\b",
        r"\babove\s+(?:rs\.?\s*)?\d+(?:[.,]\d+)?\b",
        r"\baround\s+(?:rs\.?\s*)?\d+(?:[.,]\d+)?\b",
        r"\bwithin\s+(?:rs\.?\s*)?\d+(?:[.,]\d+)?\b",
        r"\bless\s+than\s+(?:rs\.?\s*)?\d+(?:[.,]\d+)?\b",
        r"\bbetween\s+\d+(?:[.,]\d+)?\s+and\s+\d+(?:[.,]\d+)?\b",
        r"\b(?:rs\.?|inr)\s*\d+(?:[.,]\d+)?\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:rs\.?|inr)\b",
    ]
    for pattern in price_patterns:
        normalized = re.sub(pattern, " ", normalized)
    normalized = normalized.replace("₹", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_query_terms(query):
    tokens = _strip_price_constraints(query).split()
    normalized = [QUERY_TERM_SYNONYMS.get(token, token) for token in tokens]
    return [token for token in normalized if token]


def _spell_correct_query_tokens(tokens, category=None):
    vocabulary = set(SEARCH_VOCABULARY)
    vocabulary.update(*QUERY_CATEGORY_KEYWORDS.values())
    if category and category in QUERY_CATEGORY_KEYWORDS:
        vocabulary.update(QUERY_CATEGORY_KEYWORDS[category])

    corrected = []
    for token in tokens:
        if re.search(r'\d', token) or len(token) <= 2 or token in QUERY_STOP_WORDS:
            corrected.append(token)
            continue
        if token in COMMON_QUERY_CORRECTIONS:
            corrected.append(COMMON_QUERY_CORRECTIONS[token])
            continue
        if token in vocabulary:
            corrected.append(token)
            continue

        match = difflib.get_close_matches(token, list(vocabulary), n=1, cutoff=0.82)
        corrected.append(match[0] if match else token)

    return corrected


def _compact_model_query(query):
    """Join split alnum model tokens for sites that prefer compact model codes."""
    raw = canonicalize_search_query(query).split()
    compact = []
    idx = 0
    while idx < len(raw):
        token = raw[idx]
        if (
            idx + 2 < len(raw)
            and re.fullmatch(r'[a-z]{1,4}', token)
            and re.fullmatch(r'\d{1,5}', raw[idx + 1])
            and re.fullmatch(r'[a-z]{1,4}\d{1,4}', raw[idx + 2])
        ):
            compact.append(f"{token}{raw[idx + 1]}{raw[idx + 2]}")
            idx += 3
            continue
        if (
            idx + 1 < len(raw)
            and re.fullmatch(r'[a-z]{1,4}', token)
            and re.fullmatch(r'\d{1,5}[a-z]{0,3}', raw[idx + 1])
        ):
            compact.append(f"{token}{raw[idx + 1]}")
            idx += 2
            continue
        compact.append(token)
        idx += 1
    return " ".join(compact)


def _score_query_categories(query):
    """Score each category using exact token hits plus phrase boosts."""
    normalized = _normalize_text_for_filter(query)
    if not normalized:
        return {}

    tokens = set(normalized.split())
    padded_query = f" {normalized} "
    scores = {}

    for category, keywords in QUERY_CATEGORY_KEYWORDS.items():
        score = len(tokens & keywords)
        score += sum(2 for phrase in QUERY_CATEGORY_PHRASES.get(category, set()) if f" {phrase} " in padded_query)
        if score:
            scores[category] = score

    return scores


def _ai_category_fallback(query):
    """Optional remote classifier hook for ambiguous queries."""
    if not AI_CATEGORY_ENDPOINT or not query:
        return None

    try:
        response = requests.post(
            AI_CATEGORY_ENDPOINT,
            json={
                "query": query,
                "categories": [category for category in CATEGORY_PRIORITY if category != DEFAULT_QUERY_CATEGORY] + [DEFAULT_QUERY_CATEGORY],
            },
            timeout=4,
        )
        response.raise_for_status()
        if "json" in (response.headers.get("content-type") or "").lower():
            payload = response.json()
            category = str(payload.get("category", "")).strip()
        else:
            category = response.text.strip()
        if category in QUERY_CATEGORY_KEYWORDS or category == DEFAULT_QUERY_CATEGORY:
            return category
    except Exception as exc:
        log.debug(f"[Category] AI fallback unavailable: {exc}")

    return None


def classify_query_category(query):
    """Classify a query using rules first, then optional AI and matcher fallbacks."""
    normalized = _normalize_text_for_filter(query)
    if not normalized:
        return {
            "category": DEFAULT_QUERY_CATEGORY,
            "source": "empty",
            "confidence": 0.0,
            "scores": {},
        }

    scores = _score_query_categories(normalized)
    if scores:
        priority_index = {category: idx for idx, category in enumerate(CATEGORY_PRIORITY)}
        ranked = sorted(
            scores.items(),
            key=lambda item: (item[1], -priority_index[item[0]]),
            reverse=True,
        )
        top_category, top_score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        confidence = min(0.97, 0.58 + top_score * 0.08 + (0.06 if top_score > runner_up else 0))
        return {
            "category": top_category,
            "source": "rules",
            "confidence": round(confidence, 2),
            "scores": scores,
        }

    ai_category = _ai_category_fallback(normalized)
    if ai_category:
        return {
            "category": ai_category,
            "source": "ai-fallback",
            "confidence": 0.74,
            "scores": {},
        }

    inferred = PRODUCT_MATCHER.infer_category_from_text(query)
    electronics_hints = set(normalized.split()) & QUERY_CATEGORY_KEYWORDS.get("Electronics", set())
    if inferred and (inferred != "Electronics" or electronics_hints):
        return {
            "category": inferred,
            "source": "matcher-fallback",
            "confidence": 0.62 if inferred != "Electronics" else 0.57,
            "scores": {},
        }

    return {
        "category": DEFAULT_QUERY_CATEGORY,
        "source": "default",
        "confidence": 0.25,
        "scores": {},
    }


def build_search_intelligence(query):
    """Analyze a raw search and produce corrected/expanded rewrite candidates."""
    normalized_tokens = _normalize_query_terms(query)
    normalized_query = " ".join(normalized_tokens).strip()
    early_classification = classify_query_category(normalized_query) if normalized_query else {
        "category": DEFAULT_QUERY_CATEGORY,
        "source": "empty",
        "confidence": 0.0,
        "scores": {},
    }
    early_category = early_classification["category"]
    corrected_tokens = _spell_correct_query_tokens(normalized_tokens, category=early_category)
    corrected_query = canonicalize_search_query(" ".join(corrected_tokens))
    category_classification = classify_query_category(corrected_query) if corrected_query else early_classification
    category = category_classification["category"]

    rewrites = []

    def _add_rewrite(candidate_query, reason, confidence):
        candidate = canonicalize_search_query(candidate_query)
        if not candidate:
            return
        if any(existing["query"] == candidate for existing in rewrites):
            return
        rewrites.append({
            "query": candidate,
            "reason": reason,
            "confidence": confidence,
        })

    _add_rewrite(corrected_query or normalized_query or canonicalize_search_query(query), "normalized", 1.0)

    compact_query = _compact_model_query(corrected_query)
    if compact_query != corrected_query:
        _add_rewrite(compact_query, "compact-model", 0.94)

    tokens = corrected_query.split()
    expanded_tokens = list(tokens)
    for token in tokens:
        expanded_tokens.extend(sorted(QUERY_SYNONYM_EXPANSIONS.get(category, {}).get(token, set())))
    expanded_query = " ".join(dict.fromkeys(expanded_tokens))
    if expanded_query != corrected_query:
        _add_rewrite(expanded_query, "synonym-expanded", 0.88)

    if category == "Mobiles" and "mobile" not in tokens and "phone" not in tokens and "smartphone" not in tokens:
        _add_rewrite(f"{corrected_query} mobile", "category-anchor", 0.78)
    if category == "Laptops" and "laptop" not in tokens:
        _add_rewrite(f"{corrected_query} laptop", "category-anchor", 0.78)
    if category == "TVs" and "tv" not in tokens and "television" not in tokens:
        _add_rewrite(f"{corrected_query} tv", "category-anchor", 0.78)
    if category == "Audio" and not (set(tokens) & {"headphones", "earbuds", "speaker", "soundbar", "earphones"}):
        _add_rewrite(f"{corrected_query} headphones", "category-anchor", 0.7)
    if category == "Fashion" and not (set(tokens) & FASHION_REWRITE_ANCHOR_TOKENS):
        _add_rewrite(f"{corrected_query} fashion", "category-anchor", 0.64)

    return {
        "raw_query": query,
        "normalized_query": corrected_query or normalized_query,
        "category": category,
        "category_source": category_classification["source"],
        "category_confidence": category_classification["confidence"],
        "tokens": tokens,
        "rewrites": rewrites[:4],
        "spell_corrected": corrected_query if corrected_query and corrected_query != canonicalize_search_query(query) else None,
    }


def detect_query_category(query):
    """Infer a broad category from the user's query."""
    return classify_query_category(query)["category"]


def select_platforms_for_query(query, category=None):
    """Use only platforms that are likely relevant for the query category."""
    category = category or detect_query_category(query)
    if category == DEFAULT_QUERY_CATEGORY:
        return category, ["amazon", "flipkart", "myntra"]
    selected = [
        platform
        for platform, allowed_categories in PLATFORM_CATEGORY_MAP.items()
        if category in allowed_categories
    ]
    return category, selected or ["amazon", "flipkart", "myntra"]


def _query_tokens(query):
    norm = _normalize_text_for_filter(query)
    raw = norm.split()
    tokens = [t for t in raw if len(t) > 1 and t not in QUERY_STOP_WORDS]

    # Build compact model tokens for queries like "s 26" -> "s26"
    # so they match titles written as "S26".
    for i in range(len(raw) - 1):
        left = raw[i]
        right = raw[i + 1]
        if re.fullmatch(r'[a-z]{1,4}', left) and re.fullmatch(r'\d{1,3}', right):
            compact = f"{left}{right}"
            if compact not in tokens:
                tokens.append(compact)

    return tokens


def _split_query_token_types(tokens):
    alpha_tokens = set()
    model_tokens = set()
    for token in tokens:
        if re.search(r'\d', token):
            model_tokens.add(token)
        elif re.search(r'[a-z]', token):
            alpha_tokens.add(token)
    return alpha_tokens, model_tokens


def _required_distinctive_alpha_hits(alpha_tokens):
    distinctive = {
        token for token in alpha_tokens
        if token not in GENERIC_QUERY_ALPHA_TOKENS
        and token not in PRODUCT_MATCHER.variant_identifiers
    }
    if not distinctive:
        return distinctive, 0
    if len(distinctive) <= 2:
        return distinctive, len(distinctive)
    return distinctive, max(2, int(len(distinctive) * 0.67 + 0.5))


def _extract_strict_variants_from_text(text):
    normalized = PRODUCT_MATCHER.normalize(text)
    tokens = set(PRODUCT_MATCHER.tokenize(normalized))
    return tokens & PRODUCT_MATCHER.strict_variant_identifiers


def _token_in_name(token, norm_name, name_tokens, name_compact):
    """Check whether query token exists in normalized product name."""
    if token in name_tokens:
        return True

    equivalent_tokens = QUERY_TOKEN_EQUIVALENTS.get(token, set())
    if equivalent_tokens & name_tokens:
        return True

    # Handle compact model names: "s26", "a55", "iphone15"
    if re.fullmatch(r'[a-z]{1,10}\d{1,4}', token):
        if token in name_compact:
            return True
        # Also match spaced form e.g. "s 26"
        spaced = re.sub(r'([a-z]+)(\d+)', r'\1 \2', token)
        if spaced in norm_name:
            return True

    return False


def _prepare_query_match_context(query):
    """Pre-compute structured query signals once so products can be softly ranked."""
    stripped_query = _strip_price_constraints(query)
    q_tokens = _query_tokens(stripped_query)
    query_category = detect_query_category(stripped_query)
    alpha_query_tokens, model_query_tokens = _split_query_token_types(q_tokens)
    distinctive_query_tokens, required_distinctive_hits = _required_distinctive_alpha_hits(alpha_query_tokens)

    return {
        "query": stripped_query,
        "norm_query": _normalize_text_for_filter(stripped_query),
        "compact_query": _normalize_text_for_filter(stripped_query).replace(" ", ""),
        "q_tokens": q_tokens,
        "query_category": query_category,
        "query_is_accessory": PRODUCT_MATCHER.is_accessory(stripped_query),
        "query_attrs": PRODUCT_MATCHER.extract_structured_attributes(stripped_query, category_hint=query_category),
        "query_strict_variants": _extract_strict_variants_from_text(stripped_query),
        "alpha_query_tokens": alpha_query_tokens,
        "model_query_tokens": model_query_tokens,
        "query_specific_signatures": PRODUCT_MATCHER.extract_specific_model_signatures(stripped_query),
        "query_primary_signatures": PRODUCT_MATCHER.extract_primary_model_signatures(
            stripped_query,
            category_hint=query_category,
        ),
        "query_model_numbers": PRODUCT_MATCHER._extract_model_numbers(model_query_tokens),
        "distinctive_query_tokens": distinctive_query_tokens,
        "required_distinctive_hits": required_distinctive_hits,
    }


def _score_product_against_query(product, query_context):
    """Return a soft relevance score, or None for obvious hard mismatches."""
    name = PRODUCT_MATCHER.sanitize_title(product.get("name", ""))
    if name != product.get("name", ""):
        product["name"] = name

    link = product.get("link", "") or ""
    link_evidence = _normalize_link_for_filter(link)
    norm_name = _normalize_text_for_filter(name)
    if not norm_name:
        return None

    q_tokens = query_context["q_tokens"]
    query_category = query_context["query_category"]
    query_is_accessory = query_context["query_is_accessory"]
    query_attrs = query_context["query_attrs"]
    query_strict_variants = query_context["query_strict_variants"]
    alpha_query_tokens = query_context["alpha_query_tokens"]
    model_query_tokens = query_context["model_query_tokens"]
    query_specific_signatures = query_context["query_specific_signatures"]
    query_primary_signatures = query_context["query_primary_signatures"]
    query_model_numbers = query_context["query_model_numbers"]
    distinctive_query_tokens = query_context["distinctive_query_tokens"]
    required_distinctive_hits = query_context["required_distinctive_hits"]

    if (
        query_category in DEVICE_QUERY_CATEGORIES
        and not query_is_accessory
        and PRODUCT_MATCHER.is_accessory(name)
    ):
        return None
    if (
        query_category in DEVICE_QUERY_CATEGORIES
        and not query_is_accessory
        and link
        and PRODUCT_MATCHER.is_accessory(link_evidence)
    ):
        return None

    product_strict_variants = _extract_strict_variants_from_text(name)
    if product_strict_variants != query_strict_variants:
        return None

    name_tokens = set(norm_name.split())
    name_compact = norm_name.replace(" ", "")
    link_tokens = set(link_evidence.split())
    link_compact = link_evidence.replace(" ", "")
    product_specific_signatures = (
        PRODUCT_MATCHER.extract_specific_model_signatures(name)
        | PRODUCT_MATCHER.extract_specific_model_signatures(link_evidence)
    )
    product_primary_signatures = (
        PRODUCT_MATCHER.extract_primary_model_signatures(name, category_hint=query_category)
        | PRODUCT_MATCHER.extract_primary_model_signatures(link_evidence, category_hint=query_category)
    )
    product_attrs = PRODUCT_MATCHER.extract_structured_attributes(name, category_hint=query_category)

    if query_category == "TVs" and "monitor" not in q_tokens and "monitor" in name_tokens:
        return None
    if not PRODUCT_MATCHER.matches_query_attributes(query_attrs, product_attrs):
        return None

    shared_specific_signatures = query_specific_signatures & product_specific_signatures
    shared_primary_signatures = query_primary_signatures & product_primary_signatures
    if (
        query_primary_signatures
        and not shared_primary_signatures
        and any(len(signature) >= 5 for signature in query_primary_signatures)
    ):
        return None
    if query_specific_signatures and not shared_specific_signatures:
        return None

    if (
        not query_specific_signatures
        and query_model_numbers
        and PRODUCT_MATCHER._extract_numeric_suffix_signatures(product_specific_signatures)
    ):
        conflicting_suffix = False
        for signature in PRODUCT_MATCHER._extract_numeric_suffix_signatures(product_specific_signatures):
            match = re.match(r"(\d+)", signature)
            if match and match.group(1) in query_model_numbers:
                conflicting_suffix = True
                break
        if conflicting_suffix:
            return None

    hits = 0
    name_hits = 0
    alpha_content_hits = 0
    distinctive_alpha_hits = 0
    model_content_hits = 0
    for token in q_tokens:
        in_name = _token_in_name(token, norm_name, name_tokens, name_compact)
        in_link = _token_in_name(token, link_evidence, link_tokens, link_compact)
        if in_name or in_link:
            hits += 1
            if re.search(r"\d", token):
                model_content_hits += 1
            if re.search(r"[a-z]", token):
                alpha_content_hits += 1
                if token in distinctive_query_tokens:
                    distinctive_alpha_hits += 1
        if in_name:
            name_hits += 1

    token_coverage = hits / max(1, len(q_tokens)) if q_tokens else 1.0
    name_coverage = name_hits / max(1, len(q_tokens)) if q_tokens else 1.0
    alpha_coverage = (
        alpha_content_hits / max(1, len(alpha_query_tokens))
        if alpha_query_tokens else 1.0
    )
    model_coverage = (
        model_content_hits / max(1, len(model_query_tokens))
        if model_query_tokens else 1.0
    )

    exact_name_match = 1.0 if query_context["norm_query"] and norm_name == query_context["norm_query"] else 0.0
    contains_query = 1.0 if query_context["norm_query"] and query_context["norm_query"] in norm_name else 0.0
    compact_contains_query = (
        1.0
        if query_context["compact_query"] and query_context["compact_query"] in name_compact
        else 0.0
    )
    fuzzy_ratio = difflib.SequenceMatcher(None, query_context["norm_query"], norm_name).ratio()
    compact_ratio = difflib.SequenceMatcher(None, query_context["compact_query"], name_compact).ratio()

    score = 0.0
    score += exact_name_match * 120
    score += contains_query * 70
    score += compact_contains_query * 55
    score += hits * 12
    score += name_hits * 6
    score += alpha_content_hits * 10
    score += distinctive_alpha_hits * 18
    score += model_content_hits * 24
    score += token_coverage * 60
    score += name_coverage * 28
    score += alpha_coverage * 22
    score += model_coverage * 36
    score += fuzzy_ratio * 35
    score += compact_ratio * 18

    if required_distinctive_hits and distinctive_alpha_hits >= required_distinctive_hits:
        score += 14
    if model_query_tokens and model_content_hits >= len(model_query_tokens):
        score += 18
    if alpha_query_tokens and alpha_content_hits >= len(alpha_query_tokens):
        score += 10

    if shared_specific_signatures:
        score += 40
    elif shared_primary_signatures:
        score += 22

    product_brand = product_attrs.get("brand")
    if query_attrs.get("brand") and product_brand == query_attrs.get("brand"):
        score += 15
    if query_model_numbers and query_model_numbers & product_attrs.get("model_numbers", set()):
        score += 20
    if product_attrs.get("category") == query_category:
        score += 8
    if str(link).startswith("http"):
        score += 3
    score += min(5.0, _coerce_rating(product.get("rating")))

    return round(score, 3)


def filter_products_by_query(products, query, max_results=None):
    """
    Soft-rank products by query relevance.
    Keep hard contradictions out of the ranked list, but never return an empty
    result set when raw products are available.
    """
    if not products:
        return []

    query_context = _prepare_query_match_context(query)
    q_tokens = query_context["q_tokens"]
    if not q_tokens:
        return products[:max_results] if max_results else products

    ranked = []
    raw_products = []

    for prod in products:
        name = PRODUCT_MATCHER.sanitize_title(prod.get('name', ''))
        if name != prod.get('name', ''):
            prod['name'] = name

        if len(name.strip()) < 4:
            continue
        if prod.get('price') is not None and prod.get('price') <= 0:
            continue

        raw_products.append(prod)
        score = _score_product_against_query(prod, query_context)
        if score is None:
            continue
        prod["_query_score"] = score
        ranked.append(prod)

    ranked.sort(
        key=lambda item: (
            -(item.get("_query_score") or 0),
            item.get("price") or 10**12,
            -(item.get("rating") or 0),
        )
    )

    selected = ranked if ranked else raw_products
    return selected[:max_results] if max_results else selected


def filter_grouped_products_by_query(grouped_products, query, max_results=None):
    """Apply the same relevance filter to already-grouped products."""
    if not grouped_products:
        return []

    wrapped = []
    for group in grouped_products:
        links = group.get('links', {}) or {}
        synthetic_link = " ".join([v for v in links.values() if v])
        wrapped.append({
            "__group": group,
            "name": group.get("name", ""),
            "link": synthetic_link,
            "price": 1,  # keep filter semantics simple for grouped entries
        })

    filtered_wrapped = filter_products_by_query(wrapped, query, max_results=max_results)
    return [item["__group"] for item in filtered_wrapped]


def sort_grouped_products(grouped_products):
    """Prioritize groups with better platform coverage, then better price."""
    def _coverage(group):
        prices = (group.get("prices") or {}).values()
        return sum(1 for p in prices if p is not None and p > 0)

    def _best_price(group):
        prices = [p for p in (group.get("prices") or {}).values() if p is not None and p > 0]
        return min(prices) if prices else 10**12

    return sorted(
        grouped_products,
        key=lambda g: (
            -_coverage(g),
            -(g.get("confidence") or 0),
            _best_price(g),
            len((g.get("name") or "")),
        ),
    )


def _should_group_results(query, results=None):
    """Only group listings when the query is specific enough for reliable matching."""
    tokens = _query_tokens(query)
    if not tokens:
        return False
    alpha_tokens, model_tokens = _split_query_token_types(tokens)
    distinctive_alpha_tokens, _ = _required_distinctive_alpha_hits(alpha_tokens)

    if model_tokens:
        return True
    if len(distinctive_alpha_tokens) >= 2:
        return True
    return False


def _build_single_platform_groups(results):
    """Convert validated platform rows into UI-ready single-platform groups."""
    grouped = []
    for platform in SUPPORTED_PLATFORMS:
        for item in results.get(platform, []):
            grouped.append({
                "name": item.get("name"),
                "prices": {supported: (item.get("price") if supported == platform else None) for supported in SUPPORTED_PLATFORMS},
                "links": {supported: (item.get("link") if supported == platform else None) for supported in SUPPORTED_PLATFORMS},
                "rating": item.get("rating") or 0,
                "reviews": item.get("reviews") or 0,
                "image": item.get("image"),
                "confidence": item.get("confidence") or 0,
            })
    return grouped


def _coerce_positive_int(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        ivalue = int(value)
        return ivalue if ivalue > 0 else None
    cleaned = re.sub(r"[^\d]", "", str(value))
    if not cleaned:
        return None
    ivalue = int(cleaned)
    return ivalue if ivalue > 0 else None


def _coerce_rating(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        rating = float(value)
    else:
        found = re.findall(r"(\d+\.?\d*)", str(value))
        rating = float(found[0]) if found else 0.0
    return round(min(5.0, max(0.0, rating)), 1)


def _coerce_reviews(value):
    parsed = _coerce_positive_int(value)
    if parsed is None:
        return 0
    return min(parsed, 5_000_000)


def _sanitize_scraped_product(item, platform):
    """Normalize and validate a single scraper item into a stable schema."""
    if not isinstance(item, dict):
        return None

    name = re.sub(r"\s+", " ", str(item.get("name", "")).strip())
    if len(name) < 4:
        return None

    price = _coerce_positive_int(item.get("price"))
    if price is None or price > 10_000_000:
        return None

    platform_value = (item.get("platform") or platform or "").strip().lower()
    if platform_value not in SUPPORTED_PLATFORMS:
        platform_value = platform
    if platform_value not in SUPPORTED_PLATFORMS:
        return None

    link = _canonicalize_product_link(str(item.get("link") or "").strip(), platform=platform_value)
    if not link:
        return None

    image = str(item.get("image") or "").strip() or None
    search_query_used = str(item.get("search_query_used") or "").strip() or None
    rewrite_reason = str(item.get("search_rewrite_reason") or "").strip() or None

    rating_value = _coerce_rating(item.get("rating"))
    reviews_value = _coerce_reviews(item.get("reviews"))

    return {
        "name": name,
        "price": price,
        "rating": rating_value,
        "reviews": reviews_value,
        "image": image,
        "link": link,
        "platform": platform_value,
        "search_query_used": search_query_used,
        "search_rewrite_reason": rewrite_reason,
    }


def _score_product_confidence(product, query_tokens, query_attrs, query_category):
    """Estimate extraction confidence so low-confidence items can trigger fallback."""
    name = product.get("name", "")
    norm_name = _normalize_text_for_filter(name)
    name_tokens = set(norm_name.split())
    compact_name = norm_name.replace(" ", "")

    if query_tokens:
        token_hits = sum(
            1 for token in query_tokens
            if _token_in_name(token, norm_name, name_tokens, compact_name)
        )
        token_coverage = token_hits / max(1, len(query_tokens))
    else:
        token_coverage = 1.0

    model_tokens = [token for token in query_tokens if re.search(r"\d", token)]
    if model_tokens:
        model_hits = sum(
            1 for token in model_tokens
            if _token_in_name(token, norm_name, name_tokens, compact_name)
        )
        model_coverage = model_hits / max(1, len(model_tokens))
    else:
        model_coverage = 1.0

    product_attrs = PRODUCT_MATCHER.extract_structured_attributes(name, category_hint=query_category)
    attr_match = 1.0 if PRODUCT_MATCHER.matches_query_attributes(query_attrs, product_attrs) else 0.0
    has_https_link = 1.0 if str(product.get("link", "")).startswith("http") else 0.0
    rating_score = (_coerce_rating(product.get("rating")) / 5.0) if product.get("rating") else 0.0

    confidence = (
        0.16
        + token_coverage * 0.46
        + model_coverage * 0.2
        + attr_match * 0.12
        + has_https_link * 0.04
        + rating_score * 0.02
    )
    return round(max(0.0, min(0.99, confidence)), 3)


def _validate_and_rank_platform_products(platform, products, query, max_results, query_category=None):
    """Schema-validate, score confidence, and return the top records for a platform."""
    if not products:
        return [], {
            "input_count": 0,
            "accepted_count": 0,
            "dropped_count": 0,
            "avg_confidence": 0.0,
        }

    query_tokens = _query_tokens(query)
    category = query_category or detect_query_category(query)
    query_attrs = PRODUCT_MATCHER.extract_structured_attributes(query, category_hint=category)

    scored_items = []
    dropped = 0
    for raw_item in products:
        clean_item = _sanitize_scraped_product(raw_item, platform=platform)
        if not clean_item:
            dropped += 1
            continue

        # Category-aware sanity checks to reject obvious parsing artifacts.
        if category == "Mobiles" and clean_item["price"] < 3000:
            dropped += 1
            continue
        if category == "Laptops" and clean_item["price"] < 10000:
            dropped += 1
            continue
        if category == "TVs" and clean_item["price"] < 5000:
            dropped += 1
            continue

        confidence = _score_product_confidence(clean_item, query_tokens, query_attrs, category)
        clean_item["confidence"] = confidence
        query_score = raw_item.get("_query_score")
        if query_score is not None:
            clean_item["_query_score"] = query_score
        scored_items.append(clean_item)

    scored_items.sort(
        key=lambda item: (
            -(item.get("_query_score") or 0),
            -(item.get("confidence") or 0),
            item.get("price") or 10**12,
            -(item.get("rating") or 0),
        )
    )

    accepted = [item for item in scored_items if (item.get("confidence") or 0) >= 0.25]
    if not accepted:
        accepted = list(scored_items)

    if max_results:
        accepted = accepted[:max_results]

    avg_confidence = (
        round(sum(item.get("confidence", 0) for item in accepted) / len(accepted), 3)
        if accepted else 0.0
    )

    return accepted, {
        "input_count": len(products),
        "accepted_count": len(accepted),
        "dropped_count": dropped,
        "avg_confidence": avg_confidence,
    }


def _platform_search_url(platform, query):
    encoded = quote_plus(query)
    if platform == "amazon":
        return f"https://www.amazon.in/s?k={encoded}"
    if platform == "flipkart":
        return f"https://www.flipkart.com/search?q={encoded}"
    if platform == "meesho":
        return f"https://www.meesho.com/search?q={encoded}"
    if platform == "myntra":
        return f"https://www.myntra.com/{query.replace(' ', '-')}"
    return ""


async def _fetch_html_for_ai_fallback(session, platform, query):
    """Fetch lightweight HTML for AI extraction fallback."""
    url = _platform_search_url(platform, query)
    if not url:
        return ""

    referer_map = {
        "amazon": "https://www.amazon.in/",
        "flipkart": "https://www.flipkart.com/",
        "meesho": "https://www.meesho.com/",
        "myntra": "https://www.myntra.com/",
    }

    try:
        async with session.get(
            url,
            headers=_request_headers(referer=referer_map.get(platform)),
            timeout=AI_FALLBACK_TIMEOUT_SECONDS,
        ) as response:
            if response.status >= 400:
                return ""
            html = await response.text(errors="ignore")
    except Exception as exc:
        log.debug(f"[{platform.title()}] AI fallback HTML fetch failed: {exc}")
        return ""

    if not html:
        return ""
    return html[:AI_FALLBACK_HTML_MAX_CHARS]


def _ai_fallback_enabled():
    return bool(AI_EXTRACTION_ENDPOINT or GEMINI_API_KEY)


def _parse_ai_products_payload(raw_text):
    """Parse model output that may be plain JSON or JSON wrapped in markdown fences."""
    if not raw_text:
        return []

    text = str(raw_text).strip()
    candidates = [text]

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    for bracket_pattern in (r"(\[[\s\S]+\])", r"(\{[\s\S]+\})"):
        match = re.search(bracket_pattern, text)
        if match:
            candidates.append(match.group(1).strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue

        if isinstance(parsed, dict):
            products = parsed.get("products", [])
            return products if isinstance(products, list) else []
        if isinstance(parsed, list):
            return parsed

    return []


async def _extract_ai_products_from_custom_endpoint(session, platform, query, html_excerpt, max_results):
    if not AI_EXTRACTION_ENDPOINT or not html_excerpt:
        return []

    payload = {
        "platform": platform,
        "query": query,
        "max_results": max_results,
        "html": html_excerpt,
        "schema": {
            "type": "array",
            "item_fields": ["name", "price", "link"],
            "rules": [
                "Return only product records for the exact query intent.",
                "Price must be a positive integer in INR.",
                "Drop bundles/accessories unless explicitly in query.",
            ],
        },
    }

    try:
        async with session.post(
            AI_EXTRACTION_ENDPOINT,
            json=payload,
            timeout=AI_FALLBACK_TIMEOUT_SECONDS,
        ) as response:
            if response.status >= 400:
                log.debug(f"[{platform.title()}] AI fallback returned HTTP {response.status}")
                return []
            raw_text = await response.text()
    except Exception as exc:
        log.debug(f"[{platform.title()}] AI fallback request failed: {exc}")
        return []

    return _parse_ai_products_payload(raw_text)


async def _extract_ai_products_from_gemini(session, platform, query, html_excerpt, max_results):
    if not GEMINI_API_KEY or not html_excerpt:
        return []

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = (
        "You are a strict web extraction engine.\n"
        f"Extract up to {max_results} products for query '{query}' from the HTML snippet.\n"
        "Return JSON only, no markdown, no comments.\n"
        "JSON format: {\"products\":[{\"name\":str,\"price\":int,\"link\":str}]}\n"
        "Rules:\n"
        "- Keep only products matching query intent.\n"
        "- Price must be integer INR.\n"
        "- Ignore sponsored blocks, accessories, and unrelated listings.\n"
        f"- Platform: {platform}\n"
        f"HTML:\n{html_excerpt}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with session.post(
            endpoint,
            json=payload,
            timeout=AI_FALLBACK_TIMEOUT_SECONDS,
        ) as response:
            if response.status >= 400:
                log.debug(f"[{platform.title()}] Gemini fallback returned HTTP {response.status}")
                return []
            raw = await response.text()
    except Exception as exc:
        log.debug(f"[{platform.title()}] Gemini fallback request failed: {exc}")
        return []

    try:
        parsed = json.loads(raw)
    except Exception:
        return []

    parts = []
    for candidate in parsed.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if text:
                parts.append(text)

    model_text = "\n".join(parts).strip()
    return _parse_ai_products_payload(model_text)


async def _extract_ai_products_from_html(session, platform, query, html_excerpt, max_results):
    """Call configured AI fallback provider and normalize returned products."""
    if not html_excerpt:
        return []

    candidates = []
    if AI_EXTRACTION_ENDPOINT:
        candidates = await _extract_ai_products_from_custom_endpoint(
            session=session,
            platform=platform,
            query=query,
            html_excerpt=html_excerpt,
            max_results=max_results,
        )
    elif GEMINI_API_KEY:
        candidates = await _extract_ai_products_from_gemini(
            session=session,
            platform=platform,
            query=query,
            html_excerpt=html_excerpt,
            max_results=max_results,
        )

    cleaned = []
    for candidate in candidates:
        item = _sanitize_scraped_product(candidate, platform=platform)
        if not item:
            continue
        item["search_rewrite_reason"] = item.get("search_rewrite_reason") or "ai-fallback"
        cleaned = _generic_merge_unique(cleaned, [item], max_results)

    return cleaned[:max_results]


async def _ai_fallback_for_platform(session, platform, query_info, max_per_platform):
    """Run AI extraction only when the fast selector/XPath path is weak."""
    if not _ai_fallback_enabled():
        return []

    rewrites = query_info.get("rewrites", []) or [{
        "query": query_info["normalized_query"],
        "reason": "normalized",
        "confidence": 1.0,
    }]
    candidate_rewrites = rewrites[:2]

    aggregated = []
    for rewrite in candidate_rewrites:
        rewritten_query = rewrite.get("query") or query_info["normalized_query"]
        html_excerpt = await _fetch_html_for_ai_fallback(session, platform, rewritten_query)
        if not html_excerpt:
            continue

        extracted = await _extract_ai_products_from_html(
            session=session,
            platform=platform,
            query=rewritten_query,
            html_excerpt=html_excerpt,
            max_results=max_per_platform,
        )
        for item in extracted:
            item.setdefault("search_query_used", rewritten_query)
            item.setdefault("search_rewrite_reason", "ai-fallback")

        aggregated = _generic_merge_unique(aggregated, extracted, max_per_platform * 2)
        if len(aggregated) >= max(AI_FALLBACK_MIN_RESULTS, min(4, max_per_platform)):
            break

    return aggregated


def _platform_needs_ai_fallback(platform_items, quality):
    if not _ai_fallback_enabled():
        return False
    if len(platform_items) < AI_FALLBACK_MIN_RESULTS:
        return True
    avg_confidence = quality.get("avg_confidence", 0)
    return avg_confidence < AI_LOW_CONFIDENCE_THRESHOLD and len(platform_items) < max(
        AI_FALLBACK_MIN_RESULTS + 2,
        5,
    )


def _annotate_group_confidence(grouped_products, query):
    """Assign confidence to grouped results so API consumers can gate low-quality rows."""
    if not grouped_products:
        return grouped_products

    query_tokens = _query_tokens(query)
    category = detect_query_category(query)
    query_attrs = PRODUCT_MATCHER.extract_structured_attributes(query, category_hint=category)

    for group in grouped_products:
        group_name = str(group.get("name") or "")
        group_tokens = set(_normalize_text_for_filter(group_name).split())
        token_coverage = (
            sum(1 for token in query_tokens if token in group_tokens) / max(1, len(query_tokens))
            if query_tokens else 1.0
        )

        prices = [p for p in (group.get("prices") or {}).values() if p is not None and p > 0]
        coverage = len(prices) / max(1, len(SUPPORTED_PLATFORMS))
        price_quality = 1.0 if len(prices) >= 2 else (0.7 if prices else 0.0)
        group_attrs = PRODUCT_MATCHER.extract_structured_attributes(group_name, category_hint=category)
        attr_match = 1.0 if PRODUCT_MATCHER.matches_query_attributes(query_attrs, group_attrs) else 0.0

        group_confidence = (
            0.18
            + token_coverage * 0.42
            + coverage * 0.24
            + price_quality * 0.08
            + attr_match * 0.08
        )
        group["confidence"] = round(max(0.0, min(0.99, group_confidence)), 3)

    return grouped_products


def _random_browser_profile():
    """Pick a realistic desktop browser profile for Playwright sessions."""
    return random.choice(BROWSER_PROFILES).copy()


def _request_headers(mobile=False, referer=None):
    """Return lightweight headers that rotate user agents across requests."""
    user_agent = FORCED_USER_AGENT or random.choice(MOBILE_USER_AGENTS if mobile else DESKTOP_USER_AGENTS)
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    if not mobile:
        headers["Pragma"] = "no-cache"
    return headers


async def _apply_context_stealth(context):
    """Apply a shared stealth baseline to every Playwright context."""
    await context.set_extra_http_headers({
        "User-Agent": FORCED_USER_AGENT,
        "Accept-Language": "en-IN,en;q=0.9",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    })
    await context.add_init_script(STEALTH_INIT_SCRIPT)


async def _humanize_page(page):
    """Simulate light human interaction to reduce obvious bot signatures."""
    try:
        viewport = page.viewport_size or {"width": 1366, "height": 768}
        width = max(900, viewport.get("width", 1366))
        height = max(600, viewport.get("height", 768))
        await page.mouse.move(
            random.randint(80, 180),
            random.randint(90, 220),
            steps=random.randint(6, 14),
        )
        await asyncio.sleep(random.uniform(0.18, 0.45))
        await page.mouse.wheel(0, random.randint(220, 720))
        await asyncio.sleep(random.uniform(0.22, 0.55))
        await page.mouse.move(
            random.randint(width // 3, width - 120),
            random.randint(120, height - 120),
            steps=random.randint(8, 18),
        )
        await asyncio.sleep(random.uniform(0.08, 0.22))
    except Exception:
        pass


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  PLAYWRIGHT-BASED SCRAPING ENGINE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _get_browser_page():
    """Create a Playwright browser page with stealth settings."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    profile = _random_browser_profile()
    browser = pw.chromium.launch(
        headless=HEADLESS_BROWSER,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
        ]
    )
    context = browser.new_context(
        user_agent=FORCED_USER_AGENT or profile["user_agent"],
        viewport=profile["viewport"],
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        color_scheme="light",
    )
    # Block images/fonts/css for speed
    context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())
    context.add_init_script(STEALTH_INIT_SCRIPT)
    page = context.new_page()
    return pw, browser, page


def _close_browser(pw, browser):
    """Safely close browser and playwright."""
    try:
        browser.close()
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass


def _extract_html_from_json_payload(payload):
    """Best-effort extraction of HTML content from API JSON payloads."""
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""

    direct_keys = ("html", "content", "body", "source", "raw_html")
    for key in direct_keys:
        value = payload.get(key)
        if isinstance(value, str) and len(value) > 20:
            return value

    for parent_key in ("data", "result", "response"):
        nested = payload.get(parent_key)
        if isinstance(nested, str) and len(nested) > 20:
            return nested
        if isinstance(nested, dict):
            for key in direct_keys:
                value = nested.get(key)
                if isinstance(value, str) and len(value) > 20:
                    return value
    return ""


def _html_looks_blocked(html):
    lowered = (html or "").lower()
    markers = [
        "not a robot",
        "verify you are human",
        "challenge-platform",
        "cf-chl",
        "/errors/validatecaptcha",
        "solve captcha",
        "captcha required",
    ]
    return any(marker in lowered for marker in markers)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  AMAZON.IN SCRAPER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _amazon_page_is_blocked(html):
    """Detect common Amazon anti-bot / captcha responses."""
    if not html:
        return False
    if _html_looks_blocked(html):
        return True
    lowered = html.lower()
    markers = [
        "enter the characters you see below",
        "type the characters you see in this image",
        "sorry, we just need to make sure you're not a robot",
        "automated access to amazon data",
        "/errors/validatecaptcha",
    ]
    return any(marker in lowered for marker in markers)


def _amazon_extract_from_html(html, max_results):
    """Parse Amazon search cards from raw HTML using resilient selectors."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    products = []
    seen_asins = set()

    cards = soup.select(
        'div[data-component-type="s-search-result"][data-asin], '
        'div.s-result-item[data-asin], '
        'div[data-asin][data-index]'
    )

    for card in cards:
        if len(products) >= max_results:
            break

        asin = (card.get("data-asin") or "").strip()
        if not asin or asin in seen_asins:
            continue
        seen_asins.add(asin)

        title_link_el = card.select_one(
            "h2 a[href], a.a-link-normal.s-no-outline[href], a[href*='/dp/'], a[href*='/gp/']"
        )
        if not title_link_el:
            continue
        href = title_link_el.get("href") or ""
        if "/sspa/click" in href:
            continue

        title_el = (
            title_link_el.select_one("span")
            or card.select_one("h2 span.a-text-normal")
            or card.select_one("span.a-size-medium.a-color-base.a-text-normal")
            or card.select_one("span.a-size-base-plus.a-color-base.a-text-normal")
            or card.select_one("span[data-cy='title-recipe']")
        )
        name = title_el.get_text(" ", strip=True) if title_el else title_link_el.get_text(" ", strip=True)
        if not name or len(name) < 5:
            lines = [line.strip() for line in card.get_text("\n", strip=True).split("\n") if line.strip()]
            for line in lines:
                if len(line) < 12 or len(line) > 220:
                    continue
                if line.lower() in {"sponsored", "limited time deal"}:
                    continue
                if re.search(r"^\d+(\.\d+)?\s*out of 5", line.lower()):
                    continue
                if re.search(r"^[\d,\.]+\s*$", line):
                    continue
                name = line
                break
        if not name or len(name) < 5:
            continue
        card_text = card.get_text(" ", strip=True)
        if _amazon_name_looks_low_quality(name, card_text):
            continue

        price = None
        price_el = card.select_one("span.a-price > span.a-offscreen")
        if price_el:
            price = clean_price(price_el.get_text(strip=True))
        if not price:
            whole = card.select_one("span.a-price-whole")
            frac = card.select_one("span.a-price-fraction")
            if whole:
                price_text = whole.get_text(strip=True)
                if frac:
                    price_text = f"{price_text}.{frac.get_text(strip=True)}"
                price = clean_price(price_text)
        if not price:
            continue

        if not href:
            continue
        link = ("https://www.amazon.in" + href) if href and not href.startswith("http") else href

        rating_el = card.select_one("span.a-icon-alt")
        rating = clean_rating(rating_el.get_text(" ", strip=True)) if rating_el else 0

        reviews_el = card.select_one(
            "span.a-size-base.s-underline-text, "
            "span.a-size-base.s-underline-text[dir='auto'], "
            "span.a-size-base[dir='auto']"
        )
        reviews = extract_number(reviews_el.get_text(" ", strip=True)) if reviews_el else 0

        img_el = card.select_one("img.s-image, img[data-image-latency], img[src]")
        image = img_el.get("src") if img_el else None

        products.append(
            {
                "name": name,
                "price": int(price),
                "rating": rating or 0,
                "reviews": reviews or 0,
                "image": image,
                "link": link,
                "platform": "amazon",
            }
        )

    return products


def _amazon_request_headers(mobile=False):
    headers = _request_headers(mobile=mobile, referer="https://www.amazon.in/")
    if mobile:
        headers["User-Agent"] = random.choice(MOBILE_USER_AGENTS)
    headers["Cache-Control"] = "no-cache"
    return headers


def _amazon_fetch_via_requests(url, max_results, mobile=False):
    """Try a lightweight Amazon fetch before falling back to Playwright."""

    try:
        response = requests.get(
            url,
            headers=_amazon_request_headers(mobile=mobile),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        html = response.text
        if response.status_code >= 400 or _amazon_page_is_blocked(html):
            return []
        return _amazon_extract_from_html(html, max_results)
    except Exception as exc:
        log.warning(f"[Amazon] Requests fallback failed for {url}: {exc}")
        return []


def _amazon_merge_unique(existing, new_items, max_results):
    """Merge Amazon items while avoiding duplicates."""
    if len(existing) >= max_results:
        return existing

    seen_keys = set()
    for p in existing:
        link = p.get("link") or ""
        dp_match = re.search(r"/dp/([A-Z0-9]{10})", link, re.IGNORECASE)
        canonical_link = _canonicalize_product_link(link, platform="amazon")
        key = dp_match.group(1).upper() if dp_match else (canonical_link or f"{p.get('name','').lower()}|{p.get('price')}")
        seen_keys.add(key)

    for p in new_items:
        if len(existing) >= max_results:
            break
        link = p.get("link") or ""
        dp_match = re.search(r"/dp/([A-Z0-9]{10})", link, re.IGNORECASE)
        canonical_link = _canonicalize_product_link(link, platform="amazon")
        key = dp_match.group(1).upper() if dp_match else (canonical_link or f"{p.get('name','').lower()}|{p.get('price')}")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        existing.append(p)

    return existing

def _amazon_scope_for_category(category):
    """Return the most relevant Amazon browse scope for a broad category."""
    if category == "Fashion":
        return "fashion"
    if category in {"Mobiles", "Laptops", "TVs", "Audio", "Electronics", "Appliances", "Watches"}:
        return "electronics"
    return None


async def scrape_amazon(context, query, max_results=10, category=None):
    """Scrape Amazon.in with multi-pass extraction and fallback URLs."""
    products = []
    encoded_query = quote_plus(query)
    amazon_scope = _amazon_scope_for_category(category)
    search_urls = [f"https://www.amazon.in/s?k={encoded_query}"]
    if amazon_scope:
        search_urls.append(f"https://www.amazon.in/s?k={encoded_query}&i={amazon_scope}")
    search_urls.append(f"https://www.amazon.in/s?k={encoded_query}&ref=nb_sb_noss")

    # Amazon is much less hostile to a plain request than to automation.
    for idx, url in enumerate(search_urls, start=1):
        request_products = _amazon_fetch_via_requests(
            url,
            max_results=max_results,
            mobile=False,
        )
        if request_products:
            log.info(f"[Amazon] Requests fallback {idx}/{len(search_urls)} collected {len(request_products)} items")
            products = _amazon_merge_unique(products, request_products, max_results)
        if len(products) >= max_results:
            log.info(f"[Amazon] Scraped {len(products)} products")
            return products

    page = await context.new_page()
    try:
        for attempt_idx, url in enumerate(search_urls, start=1):
            if len(products) >= max_results:
                break

            log.info(f"[Amazon] Attempt {attempt_idx}/{len(search_urls)}: {url}")

            try:
                await page.set_extra_http_headers({
                    "User-Agent": FORCED_USER_AGENT,
                    "Accept-Language": "en-IN,en;q=0.9",
                })
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as nav_err:
                log.warning(f"[Amazon] Navigation failed on attempt {attempt_idx}: {nav_err}")
                continue

            await _humanize_page(page)
            # Give Amazon a little more time than before; many pages lazy-render cards.
            await asyncio.sleep(random.uniform(0.35, 0.6))
            try:
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(random.uniform(0.1, 0.2))
                await page.evaluate("window.scrollBy(0, 900)")
            except Exception:
                pass

            cards_found = False
            try:
                await page.wait_for_selector(
                    'div[data-component-type="s-search-result"], div.s-result-item[data-asin], div[data-asin][data-index]',
                    timeout=6000,
                )
                cards_found = True
            except Exception:
                log.warning("[Amazon] Selector timeout on JS path; falling back to HTML parse")

            if cards_found:
                js_products = await page.evaluate("""(maxResults) => {
                    const out = [];
                    const cards = [
                        ...document.querySelectorAll('div[data-component-type="s-search-result"][data-asin]'),
                        ...document.querySelectorAll('div.s-result-item[data-asin]'),
                        ...document.querySelectorAll('div[data-asin][data-index]')
                    ];
                    const seen = new Set();

                    const parsePrice = (card) => {
                        const offscreen = card.querySelector('span.a-price > span.a-offscreen');
                        if (offscreen && offscreen.textContent) {
                            const n = offscreen.textContent.replace(/[^0-9.]/g, '');
                            if (n) {
                                const p = parseFloat(n);
                                if (!Number.isNaN(p) && p > 0) return Math.round(p);
                            }
                        }
                        const whole = card.querySelector('span.a-price-whole');
                        const frac = card.querySelector('span.a-price-fraction');
                        if (whole && whole.textContent) {
                            const wholeNum = whole.textContent.replace(/[^0-9]/g, '');
                            const fracNum = frac && frac.textContent ? frac.textContent.replace(/[^0-9]/g, '') : '';
                            const full = fracNum ? `${wholeNum}.${fracNum}` : wholeNum;
                            const p = parseFloat(full);
                            if (!Number.isNaN(p) && p > 0) return Math.round(p);
                        }
                        return null;
                    };

                    for (const card of cards) {
                        if (out.length >= maxResults) break;

                        const asin = (card.getAttribute('data-asin') || '').trim();
                        if (!asin || seen.has(asin)) continue;
                        seen.add(asin);

                        const titleLink =
                            card.querySelector('h2 a[href]') ||
                            card.querySelector('a.a-link-normal.s-no-outline[href]') ||
                            card.querySelector('a[href*="/dp/"], a[href*="/gp/"], a[href*="/sspa/click"]');
                        if (!titleLink) continue;

                        const titleEl =
                            titleLink.querySelector('span') ||
                            card.querySelector('h2 span.a-text-normal') ||
                            card.querySelector('span.a-size-medium.a-color-base.a-text-normal') ||
                            card.querySelector('span.a-size-base-plus.a-color-base.a-text-normal') ||
                            card.querySelector("span[data-cy='title-recipe']");
                        let name = titleEl ? titleEl.textContent.trim() : titleLink.textContent.trim();
                        if (!name || name.length < 5) {
                            const lines = (card.innerText || '').split('\\n').map(t => t.trim()).filter(Boolean);
                            for (const line of lines) {
                                if (line.length < 12 || line.length > 220) continue;
                                if (/^(sponsored|limited time deal)$/i.test(line)) continue;
                                if (/^\\d+(\\.\\d+)?\\s*out of 5/i.test(line)) continue;
                                if (/^[\\d,\\.]+$/.test(line)) continue;
                                name = line;
                                break;
                            }
                        }
                        if (!name || name.length < 5) continue;

                        const price = parsePrice(card);
                        if (!price) continue;

                        const href = titleLink.getAttribute('href');
                        if (!href) continue;
                        const link = href.startsWith('http') ? href : `https://www.amazon.in${href}`;

                        const ratingEl = card.querySelector('span.a-icon-alt');
                        const ratingMatch = ratingEl ? (ratingEl.textContent || '').match(/(\d+\.?\d*)/) : null;
                        const rating = ratingMatch ? parseFloat(ratingMatch[1]) : 0;

                        const reviewsEl =
                            card.querySelector('span.a-size-base.s-underline-text') ||
                            card.querySelector('span.a-size-base[dir="auto"]');
                        const reviews = reviewsEl
                            ? parseInt((reviewsEl.textContent || '').replace(/[^0-9]/g, ''), 10) || 0
                            : 0;

                        const imgEl = card.querySelector('img.s-image, img[data-image-latency], img[src]');
                        const image = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src')) : null;

                        out.push({
                            name,
                            price,
                            rating: Math.round(rating * 10) / 10,
                            reviews,
                            image,
                            link,
                            platform: 'amazon'
                        });
                    }

                    return out;
                }""", max_results)

                products = _amazon_merge_unique(products, js_products or [], max_results)

            # Always parse HTML too; it catches server-rendered cards when JS misses some.
            html = await page.content()
            if _amazon_page_is_blocked(html):
                log.warning("[Amazon] Captcha/anti-bot page detected on this attempt")
                continue

            html_products = _amazon_extract_from_html(html, max_results)
            products = _amazon_merge_unique(products, html_products, max_results)

            if products:
                log.info(f"[Amazon] Attempt {attempt_idx}: collected {len(products)} items so far")

        log.info(f"[Amazon] Scraped {len(products)} products")

    except Exception as e:
        log.error(f"[Amazon] Error: {e}")
    finally:
        try:
            await page.close()
        except Exception:
            pass

    return products


def _flipkart_merge_unique(existing, new_items, max_results):
    """Merge Flipkart items while avoiding duplicates."""
    if len(existing) >= max_results:
        return existing

    seen = set()
    for item in existing:
        link = _canonicalize_product_link(item.get("link") or "", platform="flipkart")
        seen.add(link or f"{item.get('name', '').lower()}|{item.get('price')}")

    for item in new_items:
        if len(existing) >= max_results:
            break
        link = _canonicalize_product_link(item.get("link") or "", platform="flipkart")
        key = link or f"{item.get('name', '').lower()}|{item.get('price')}"
        if key in seen:
            continue
        seen.add(key)
        existing.append(item)

    return existing


def _flipkart_extract_from_html(html, max_results):
    """Parse Flipkart search cards from raw HTML using resilient selectors."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    products = []

    for card in soup.select("div[data-id]"):
        if len(products) >= max_results:
            break

        lines = [line.strip() for line in card.get_text("\n", strip=True).split("\n") if line.strip()]
        name_el = card.select_one("div.KzDlHZ, div._4rR01T, div.RG5Slk, a.s1Q9rs, a.IRpwTa, a.wjcEIp, div.syl9yP")
        name = name_el.get_text(" ", strip=True) if name_el else None
        if not name or len(name) < 5:
            img_alt = card.select_one("img[alt]")
            name = img_alt.get("alt", "").strip() if img_alt else None
        if not name or len(name) < 5:
            meaningful_lines = []
            for line in lines:
                lowered = line.lower()
                if len(line) < 3 or len(line) > 220:
                    continue
                if lowered in {"add to compare", "currently unavailable", "bank offer", "free delivery"}:
                    continue
                if re.search(r"(ratings?|reviews?|off on exchange|off$)", lowered):
                    continue
                if re.search(r"^\d+[.,\d]*\s*(gb|tb|mb|mah|mp|inch|cm)\b", lowered):
                    continue
                if re.search(r"^[₹\d,.\s%]+$", line):
                    continue
                meaningful_lines.append(line)
            if len(meaningful_lines) >= 2 and len(meaningful_lines[0]) <= 35:
                name = f"{meaningful_lines[0]} {meaningful_lines[1]}".strip()
            elif meaningful_lines:
                name = meaningful_lines[0]
        if not name or len(name) < 5:
            continue
        name = _append_capacity_variant_to_name(name, lines)

        price_el = card.select_one(
            "div.Nx9bqj, div._30jeq3, div._1_WHN1, div.hl05eU div.Nx9bqj, div.hZ3P6w, div.QiMO5r div.hZ3P6w"
        )
        price = clean_price(price_el.get_text(" ", strip=True)) if price_el else None
        if not price:
            for line in [line.strip() for line in card.get_text("\n", strip=True).split("\n") if line.strip()]:
                lowered = line.lower()
                if re.search(r"(gb|tb|mb|mah|mp|inch|cm|ratings?|reviews?|off on exchange|off$)", lowered):
                    continue
                if not re.fullmatch(r"[₹\d,.\s]+", line):
                    continue
                price_candidate = clean_price(line)
                if price_candidate and 50 <= price_candidate <= 500000:
                    price = price_candidate
                    break
        if not price:
            continue

        link_el = card.select_one('a[href*="/p/"], a[href*="pid="]')
        href = link_el.get("href") if link_el else None
        link = f"https://www.flipkart.com{href}" if href and not href.startswith("http") else href

        rating_el = card.select_one("div.XQDdHH, div._3LWZlK, span.Y1HWO0, div.MKiFS6")
        rating = clean_rating(rating_el.get_text(" ", strip=True)) if rating_el else 0
        if not rating:
            for el in card.select("span, div"):
                text = el.get_text(" ", strip=True)
                match = re.search(r"\b([1-5]\.\d)\b", text)
                if match:
                    rating = clean_rating(match.group(1))
                    if rating:
                        break

        reviews_el = card.select_one("span.Wphh3N, span._2_R_DZ, span.PvbNMB")
        reviews = extract_number(reviews_el.get_text(" ", strip=True)) if reviews_el else 0
        if not reviews:
            for el in card.select("span, div"):
                text = el.get_text(" ", strip=True)
                if re.search(r"(ratings?|reviews?)", text, flags=re.IGNORECASE):
                    reviews = extract_number(text)
                    if reviews:
                        break

        img_el = card.select_one('img[src*="rukminim"], img[src*="flipkart"], img[src]')
        image = img_el.get("src") if img_el else None

        products.append({
            "name": name,
            "price": int(price),
            "rating": rating or 0,
            "reviews": reviews or 0,
            "image": image,
            "link": link,
            "platform": "flipkart",
        })

    return products


def _flipkart_fetch_via_requests(url, max_results):
    """Try a direct Flipkart HTML fetch before using Playwright."""
    try:
        response = requests.get(
            url,
            headers=_request_headers(referer="https://www.flipkart.com/"),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        html = response.text
        if response.status_code >= 400 or _html_looks_blocked(html):
            return []
        return _flipkart_extract_from_html(html, max_results)
    except Exception as exc:
        log.warning(f"[Flipkart] Requests fallback failed for {url}: {exc}")
        return []


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  FLIPKART SCRAPER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def scrape_flipkart(context, query, max_results=10):
    """Scrape Flipkart using Playwright with JS extraction."""
    products = []
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    log.info(f"[Flipkart] Scraping: {url}")

    request_products = _flipkart_fetch_via_requests(url, max_results)
    if request_products:
        log.info(f"[Flipkart] Requests fallback collected {len(request_products)} items")
        products = _flipkart_merge_unique(products, request_products, max_results)
        if len(products) >= max_results:
            log.info(f"[Flipkart] Scraped {len(products)} products")
            return products

    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=12000)
        await _humanize_page(page)

        # Close login popup if it appears
        await asyncio.sleep(random.uniform(0.35, 0.6))
        try:
            close_btn = page.locator('button._2KpZ6l._2doB4z, button[aria-label="Close"], button:has(svg)')
            if await close_btn.count() > 0:
                await close_btn.first.click()
                await asyncio.sleep(random.uniform(0.2, 0.45))
        except Exception:
            pass

        # Wait for products to load
        try:
            await page.wait_for_selector('a[href*="/p/"], a[href*="pid="]', timeout=8000)
        except Exception:
            log.warning("[Flipkart] Product links didn't load")

        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(random.uniform(0.35, 0.7))

        # Extract using JS â€“ find all product containers with price
        js_products = await page.evaluate("""(maxResults) => {
            const items = [];
            const normalizeVariantSnippet = (text) => {
                if (!text) return null;
                const match = text.match(/(\\d+\\s*(?:gb|tb)\\s*\\+\\s*\\d+\\s*gb)/i);
                if (!match) return null;
                return match[1]
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .replace(/\\b(gb|tb)\\b/gi, unit => unit.toUpperCase());
            };
            const extractVariantSnippet = (lines) => {
                const normalizedLines = (lines || []).map(line => (line || '').trim()).filter(Boolean);
                for (let idx = 0; idx < normalizedLines.length; idx += 1) {
                    const line = normalizedLines[idx];
                    const direct = normalizeVariantSnippet(line);
                    if (direct) return direct;

                    const lowered = line.toLowerCase().replace(/:$/, '');
                    if (['variant', 'variants', 'storage', 'ram'].includes(lowered) && idx + 1 < normalizedLines.length) {
                        const follow = normalizeVariantSnippet(normalizedLines[idx + 1]);
                        if (follow) return follow;
                    }
                }
                return null;
            };
            // Strategy: find all links that go to product pages
            const allLinks = document.querySelectorAll('a[href*="/p/"], a[href*="pid="]');
            const seen = new Set();

            for (const link of allLinks) {
                if (items.length >= maxResults) break;

                // Get parent container
                const container = link.closest('div[data-id]') || link.parentElement?.parentElement?.parentElement;
                if (!container) continue;

                // Skip if already processed
                const containerId = container.getAttribute('data-id') || container.textContent.substring(0, 50);
                if (seen.has(containerId)) continue;
                seen.add(containerId);

                // Find name: look for the product title
                let name = null;
                const containerLines = (container.innerText || '').split('\\n').map(t => t.trim()).filter(Boolean);
                // Try various selectors
                const nameSelectors = ['div.KzDlHZ', 'div._4rR01T', 'div.RG5Slk', 'a.s1Q9rs', 'a.IRpwTa',
                    'a.wjcEIp', 'a[title]', 'div.syl9yP'];
                for (const sel of nameSelectors) {
                    const el = container.querySelector(sel);
                    if (el) {
                        name = el.textContent.trim() || el.getAttribute('title');
                        // Ensure it's not the whole card
                        if (name && name.length > 5 && name.length < 150 && !name.includes('Ratings')) break;
                        name = null;
                    }
                }
                // Fallback: use image alt
                if (!name) {
                    const img = container.querySelector('img[alt]');
                    if (img && img.getAttribute('alt')) {
                        name = img.getAttribute('alt').trim();
                    }
                }
                // Last resort title attribute
                if (!name) {
                    name = link.getAttribute('title');
                }
                // Final fallback: derive from visible text lines
                if (!name) {
                    const meaningful = [];
                    for (const line of containerLines) {
                        if (line.length < 3 || line.length > 180) continue;
                        if (/^(add to compare|currently unavailable|bank offer|free delivery)$/i.test(line)) continue;
                        if (/(ratings?|reviews?|off on exchange|off$)/i.test(line)) continue;
                        if (/^\\d+[\\d,\\.\\s]*\\s*(gb|tb|mb|mah|mp|inch|cm)\\b/i.test(line)) continue;
                        if (/^[₹\\d,\\.\\s%]+$/.test(line)) continue;
                        meaningful.push(line);
                    }
                    if (meaningful.length >= 2 && meaningful[0].length <= 35) {
                        name = `${meaningful[0]} ${meaningful[1]}`.trim();
                    } else if (meaningful.length > 0) {
                        name = meaningful[0];
                    }
                }
                if (!name || name.length < 5) continue;
                
                // Clean up any Flipkart artifacts
                name = name.replace(/^Add to Compare/i, '').trim();
                name = name.replace(/^Currently unavailable/i, '').trim();
                name = name.replace(/^Coming Soon/i, '').trim();
                if (name.length > 150) name = name.substring(0, 150);
                const variantSnippet = extractVariantSnippet(containerLines);
                if (variantSnippet && !name.toLowerCase().includes(variantSnippet.toLowerCase())) {
                    name = `${name} ${variantSnippet}`.trim();
                }

                // Find price
                let price = null;
                const priceSelectors = ['div.Nx9bqj', 'div._30jeq3', 'div._1_WHN1', 'div.hl05eU div.Nx9bqj', 'div.hZ3P6w', 'div.QiMO5r div.hZ3P6w'];
                for (const sel of priceSelectors) {
                    const el = container.querySelector(sel);
                    if (el) {
                        const priceText = el.textContent.replace(/[^0-9]/g, '');
                        if (priceText) {
                            price = parseInt(priceText);
                            if (price > 0) break;
                        }
                    }
                }
                // Broader fallback: find any element that looks like a price
                if (!price) {
                    const lines = (container.innerText || '').split('\\n').map(t => t.trim()).filter(Boolean);
                    for (const line of lines) {
                        if (/(gb|tb|mb|mah|mp|inch|cm|ratings?|reviews?|off on exchange|off$)/i.test(line)) continue;
                        if (!/^[₹\\d,\\.\\s]+$/.test(line)) continue;
                        const digits = line.replace(/[^0-9]/g, '');
                        if (!digits) continue;
                        const p = parseInt(digits, 10);
                        if (p >= 50 && p <= 500000) { price = p; break; }
                    }
                }
                if (!price) continue;

                // Rating
                let rating = 0;
                const ratingSelectors = ['div.XQDdHH', 'div._3LWZlK', 'span.Y1HWO0', 'div.MKiFS6'];
                for (const sel of ratingSelectors) {
                    const el = container.querySelector(sel);
                    if (el) {
                        const val = parseFloat((el.textContent || '').trim());
                        if (!Number.isNaN(val) && val > 0 && val <= 5) { rating = Math.round(val * 10) / 10; break; }
                    }
                }

                // Reviews
                let reviews = 0;
                const reviewSelectors = ['span.Wphh3N', 'span._2_R_DZ', 'span.PvbNMB'];
                for (const sel of reviewSelectors) {
                    const el = container.querySelector(sel);
                    if (el) {
                        const match = (el.textContent || '').match(/([\\d,]+)/);
                        if (match) { reviews = parseInt(match[1].replace(/,/g, ''), 10) || 0; break; }
                    }
                }

                // Product URL
                let productUrl = link.getAttribute('href');
                if (productUrl && !productUrl.startsWith('http')) {
                    productUrl = 'https://www.flipkart.com' + productUrl;
                }

                // Image
                let image = null;
                const imgEl = container.querySelector('img[src*="rukminim"], img[src*="flipkart"]');
                if (imgEl) image = imgEl.getAttribute('src');

                items.push({
                    name, price, rating, reviews,
                    image, link: productUrl, platform: 'flipkart'
                });
            }
            return items;
        }""", max_results)

        products = _flipkart_merge_unique(products, js_products or [], max_results)

        html = await page.content()
        html_products = _flipkart_extract_from_html(html, max_results)
        products = _flipkart_merge_unique(products, html_products, max_results)

        log.info(f"[Flipkart] Scraped {len(products)} products")

    except Exception as e:
        log.error(f"[Flipkart] Error: {e}")
    finally:
        if 'page' in locals() and page:
            await page.close()

    return products


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MEESHO SCRAPER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def scrape_meesho(context, query, max_results=10):
    """Scrape Meesho using Playwright."""
    products = []
    url = f"https://www.meesho.com/search?q={query.replace(' ', '+')}"
    log.info(f"[Meesho] Scraping: {url}")

    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=8000)
        await _humanize_page(page)

        # Wait for product cards to render
        try:
            await page.wait_for_selector('a[href*="/p/"], a[href*="/product/"]', timeout=9000)
        except Exception:
            log.warning("[Meesho] Product links didn't load")

        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(random.uniform(0.35, 0.55))

        # Extract using JS
        products = await page.evaluate("""(maxResults) => {
            const items = [];
            const links = document.querySelectorAll('a[href*="/p/"], a[href*="/product/"]');
            const seen = new Set();

            for (const link of links) {
                if (items.length >= maxResults) break;

                const href = link.getAttribute('href');
                if (seen.has(href)) continue;
                seen.add(href);

                const container = link.closest('div,li,article') || link;

                // Name: first substantial paragraph or heading
                let name = null;
                const textEls = container.querySelectorAll('p, span, h4, h5, div, a');
                for (const el of textEls) {
                    const text = el.textContent.trim();
                    if (
                        text.length > 10
                        && text.length < 200
                        && !text.match(/^\\d/)
                        && !/(free delivery|reviews?|ratings?|%\\s*off|₹|\\brs\\b)/i.test(text)
                        && !/^(\\d+%\\s*off|free delivery|\\d+\\s*ratings?)$/i.test(text)
                    ) {
                        name = text;
                        break;
                    }
                }
                if (!name) {
                    const lines = (container.innerText || '').split('\\n').map(t => t.trim()).filter(Boolean);
                    for (const line of lines) {
                        if (
                            line.length >= 10
                            && line.length <= 200
                            && !/^\\d/.test(line)
                            && !/(free delivery|reviews?|ratings?|%\\s*off|₹|\\brs\\b)/i.test(line)
                        ) {
                            name = line;
                            break;
                        }
                    }
                }
                if (!name) continue;
                name = name.replace(/\\s+/g, ' ').trim();

                // Price: detect numeric money-like token
                let price = null;
                for (const el of textEls) {
                    const text = el.textContent.trim();
                    const match = text.match(/(?:₹|rs\\.?\\s*)?\\s*([\\d,]{3,})/i);
                    if (match) {
                        const p = parseInt((match[1] || '').replace(/,/g, ''), 10);
                        if (p >= 50 && p <= 500000) { price = p; break; }
                    }
                }
                if (!price) continue;

                // Image
                let image = null;
                const imgEl = container.querySelector('img[src]');
                if (imgEl) image = imgEl.getAttribute('src');

                let productUrl = href;
                if (!productUrl.startsWith('http')) productUrl = 'https://www.meesho.com' + productUrl;

                items.push({
                    name, price, rating: 0,
                    reviews: 0, image, link: productUrl, platform: 'meesho'
                });
            }
            return items;
        }""", max_results)

        log.info(f"[Meesho] Scraped {len(products)} products")

    except Exception as e:
        log.error(f"[Meesho] Error: {e}")
    finally:
        if 'page' in locals() and page:
            await page.close()

    return products


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MYNTRA SCRAPER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def scrape_myntra(session, query, max_results=10):
    """Scrape Myntra without Playwright, using requests and __myx JSON extraction."""
    products = []
    url = f"https://www.myntra.com/{query.replace(' ', '-')}"
    log.info(f"[Myntra] Scraping: {url}")

    headers = _request_headers(referer="https://www.myntra.com/")

    try:
        async with session.get(url, headers=headers, timeout=15) as r:
            text = await r.text()
            scripts = re.findall(r'<script.*?>.*?</script>', text, flags=re.DOTALL)
        for s in scripts:
            if "searchData" in s:
                match = re.search(r'window\.__myx\s*=\s*(\{.+?\});?<', s)
                if match:
                    data = json.loads(match.group(1))
                    items = data.get('searchData', {}).get('results', {}).get('products', [])
                    for prod in items:
                        if len(products) >= max_results:
                            break
                        
                        name = prod.get('productName')
                        price = prod.get('price')
                        image = prod.get('searchImage')
                        link = f"https://www.myntra.com/{prod.get('landingPageUrl')}"

                        if name and price:
                            products.append({
                                'name': name,
                                'price': int(price),
                                'rating': 0,
                                'reviews': 0,
                                'image': image,
                                'link': link,
                                'platform': 'myntra'
                            })
                    break

        log.info(f"[Myntra] Scraped {len(products)} products")

    except Exception as e:
        log.error(f"[Myntra] Error: {e}")

    return products






# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  SAFE SCRAPER WRAPPER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _safe_scrape(func, query, max_results):
    """Run a scraper with minimal delay and error handling."""
    time.sleep(random.uniform(0.2, 0.5))  # Reduced from 0.5-1.5
    try:
        return func(query, max_results)
    except Exception as e:
        log.error(f"[{func.__name__}] Failed: {e}")
        return []


def _generic_merge_unique(existing, new_items, max_results):
    """Merge product dicts across rewritten queries without duplicating identical listings."""
    if len(existing) >= max_results:
        return existing

    seen = set()
    for item in existing:
        platform = item.get("platform") or ""
        link = _canonicalize_product_link((item.get("link") or "").strip(), platform=platform)
        key = (
            link.lower()
            or f"{(item.get('name') or '').strip().lower()}|{item.get('price')}"
        )
        seen.add(key)

    for item in new_items:
        if len(existing) >= max_results:
            break
        platform = item.get("platform") or ""
        link = _canonicalize_product_link((item.get("link") or "").strip(), platform=platform)
        key = (
            link.lower()
            or f"{(item.get('name') or '').strip().lower()}|{item.get('price')}"
        )
        if key in seen:
            continue
        seen.add(key)
        existing.append(item)

    return existing


async def _scrape_platform_with_rewrites(platform, query_info, max_per_platform, scrape_call):
    """Try rewritten queries for a platform until enough candidates are collected."""
    aggregated = []
    rewrites = query_info.get("rewrites", []) or [{"query": query_info["normalized_query"], "reason": "normalized", "confidence": 1.0}]
    target_count = min(max_per_platform, 8)
    target_relevant = min(max_per_platform, 4)
    normalized_query = query_info["normalized_query"]

    for rewrite in rewrites:
        rewritten_query = rewrite["query"]
        try:
            items = await scrape_call(rewritten_query)
        except Exception as exc:
            log.error(f"[{platform.title()}] Rewrite '{rewritten_query}' failed: {exc}")
            continue

        for item in items:
            item.setdefault("search_query_used", rewritten_query)
            item.setdefault("search_rewrite_reason", rewrite["reason"])

        aggregated = _generic_merge_unique(aggregated, items, max_per_platform * 2)
        relevant_items = filter_products_by_query(list(aggregated), normalized_query, max_results=max_per_platform)
        if len(aggregated) >= target_count and len(relevant_items) >= target_relevant:
            break

    return aggregated


async def scrape_raw_products(query, max_per_platform=5):
    """
    Fetch raw product rows for Amazon + Flipkart.
    Output rows contain only:
      name, price, rating, link, image, platform
    """
    query_info = build_search_intelligence(query)
    query = query_info["normalized_query"]
    if not query:
        return {
            "query": "",
            "category": DEFAULT_QUERY_CATEGORY,
            "platforms": {"amazon": [], "flipkart": []},
            "total": 0,
        }

    category = query_info.get("category")
    results = {"amazon": [], "flipkart": []}

    async with async_playwright() as pw:
        browser_profile = _random_browser_profile()
        browser = await pw.chromium.launch(
            headless=HEADLESS_BROWSER,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent=FORCED_USER_AGENT or browser_profile["user_agent"],
            viewport=browser_profile["viewport"],
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            color_scheme="light",
        )
        await _apply_context_stealth(context)
        await context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())

        session_timeout = aiohttp.ClientTimeout(
            total=REQUEST_TIMEOUT_SECONDS,
            connect=4,
            sock_connect=4,
            sock_read=REQUEST_TIMEOUT_SECONDS,
        )
        connector = aiohttp.TCPConnector(limit=16, limit_per_host=8, ttl_dns_cache=300)
        async with aiohttp.ClientSession(
            timeout=session_timeout,
            connector=connector,
            headers={
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-IN,en;q=0.9",
                "Connection": "keep-alive",
            },
        ) as session:
            scrape_jobs = [
                (
                    'amazon',
                    _scrape_platform_with_rewrites(
                        'amazon',
                        query_info,
                        max_per_platform,
                        lambda rewritten_query: scrape_amazon(
                            context,
                            rewritten_query,
                            max_per_platform,
                            category=category,
                        ),
                    ),
                ),
                (
                    'flipkart',
                    _scrape_platform_with_rewrites(
                        'flipkart',
                        query_info,
                        max_per_platform,
                        lambda rewritten_query: scrape_flipkart(context, rewritten_query, max_per_platform),
                    ),
                ),
            ]

            raw_results = await asyncio.gather(
                *[job[1] for job in scrape_jobs],
                return_exceptions=True
            )

            for (platform, _), raw_result in zip(scrape_jobs, raw_results):
                if isinstance(raw_result, Exception):
                    log.error(f"[{platform.title()}][raw] Failed: {raw_result}")
                    continue

                filtered_items = filter_products_by_query(raw_result, query, max_per_platform)
                validated_items, _ = _validate_and_rank_platform_products(
                    platform=platform,
                    products=filtered_items,
                    query=query,
                    max_results=max_per_platform,
                    query_category=category,
                )
                results[platform] = [
                    {
                        "name": item.get("name"),
                        "price": item.get("price"),
                        "rating": item.get("rating") or 0,
                        "link": item.get("link"),
                        "image": item.get("image"),
                        "platform": platform,
                    }
                    for item in validated_items
                ]

        await browser.close()

    total = sum(len(v) for v in results.values())
    return {
        "query": query,
        "category": category or DEFAULT_QUERY_CATEGORY,
        "platforms": results,
        "total": total,
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MAIN SEARCH â€“ CONCURRENT SCRAPING
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def search_products(query, max_per_platform=5):
    query_info = build_search_intelligence(query)
    query = query_info["normalized_query"]
    if not query:
        return []

    log.info(f"\n{'='*50}")
    log.info(f"  Live Scraping (Async): '{query}'")
    log.info(f"{'='*50}")

    category, selected_platforms = select_platforms_for_query(query, category=query_info.get("category"))
    category_source = query_info.get("category_source", "rules")
    category_confidence = query_info.get("category_confidence", 0)
    log.info(
        f"[Search] Category: {category} ({category_source}, {category_confidence:.2f}) | "
        f"Platforms: {', '.join(selected_platforms)}"
    )
    if query_info.get("spell_corrected"):
        log.info(f"[Search] Spell-corrected query: '{query_info['spell_corrected']}'")
    rewrite_log = ", ".join(f"{item['query']} ({item['reason']})" for item in query_info.get("rewrites", [])[:3])
    if rewrite_log:
        log.info(f"[Search] Rewrite candidates: {rewrite_log}")

    results = {platform: [] for platform in SUPPORTED_PLATFORMS}
    platform_quality = {
        platform: {
            "input_count": 0,
            "accepted_count": 0,
            "dropped_count": 0,
            "avg_confidence": 0.0,
        }
        for platform in SUPPORTED_PLATFORMS
    }

    async with async_playwright() as pw:
        browser_profile = _random_browser_profile()
        browser = await pw.chromium.launch(
            headless=HEADLESS_BROWSER,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent=FORCED_USER_AGENT or browser_profile["user_agent"],
            viewport=browser_profile["viewport"],
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            color_scheme="light",
        )
        await _apply_context_stealth(context)
        await context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())

        session_timeout = aiohttp.ClientTimeout(
            total=REQUEST_TIMEOUT_SECONDS,
            connect=4,
            sock_connect=4,
            sock_read=REQUEST_TIMEOUT_SECONDS,
        )
        connector = aiohttp.TCPConnector(limit=24, limit_per_host=8, ttl_dns_cache=300)
        async with aiohttp.ClientSession(
            timeout=session_timeout,
            connector=connector,
            headers={
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-IN,en;q=0.9",
                "Connection": "keep-alive",
            },
        ) as session:
            scrape_jobs = []
            if 'amazon' in selected_platforms:
                scrape_jobs.append((
                    'amazon',
                    _scrape_platform_with_rewrites(
                        'amazon',
                        query_info,
                        max_per_platform,
                        lambda rewritten_query: scrape_amazon(
                            context,
                            rewritten_query,
                            max_per_platform,
                            category=query_info.get("category"),
                        ),
                    )
                ))
            if 'flipkart' in selected_platforms:
                scrape_jobs.append((
                    'flipkart',
                    _scrape_platform_with_rewrites(
                        'flipkart',
                        query_info,
                        max_per_platform,
                        lambda rewritten_query: scrape_flipkart(context, rewritten_query, max_per_platform),
                    )
                ))
            if 'meesho' in selected_platforms:
                scrape_jobs.append((
                    'meesho',
                    _scrape_platform_with_rewrites(
                        'meesho',
                        query_info,
                        max_per_platform,
                        lambda rewritten_query: scrape_meesho(context, rewritten_query, max_per_platform),
                    )
                ))
            if 'myntra' in selected_platforms:
                scrape_jobs.append((
                    'myntra',
                    _scrape_platform_with_rewrites(
                        'myntra',
                        query_info,
                        max_per_platform,
                        lambda rewritten_query: scrape_myntra(session, rewritten_query, max_per_platform),
                    )
                ))

            raw_results = await asyncio.gather(
                *[job[1] for job in scrape_jobs],
                return_exceptions=True
            )

            for (platform, _), raw_result in zip(scrape_jobs, raw_results):
                if isinstance(raw_result, Exception):
                    log.error(f"[{platform.title()}] Failed: {raw_result}")
                    continue

                filtered_items = filter_products_by_query(raw_result, query, max_per_platform)
                validated_items, quality = _validate_and_rank_platform_products(
                    platform=platform,
                    products=filtered_items,
                    query=query,
                    max_results=max_per_platform,
                    query_category=category,
                )
                results[platform] = validated_items
                platform_quality[platform] = quality
                if len(filtered_items) != len(raw_result):
                    log.info(f"[{platform.title()}] Filtered by query relevance: {len(raw_result)} -> {len(filtered_items)}")
                log.info(
                    f"[{platform.title()}] Schema validated: "
                    f"{quality['accepted_count']}/{quality['input_count']} "
                    f"(avg_conf={quality['avg_confidence']:.3f})"
                )

            fallback_platforms = [
                platform
                for platform in selected_platforms
                if _platform_needs_ai_fallback(results.get(platform, []), platform_quality.get(platform, {}))
            ]

            if fallback_platforms:
                log.info(f"[Search] Triggering AI fallback for: {', '.join(fallback_platforms)}")
                fallback_jobs = [
                    (
                        platform,
                        _ai_fallback_for_platform(
                            session=session,
                            platform=platform,
                            query_info=query_info,
                            max_per_platform=max_per_platform,
                        ),
                    )
                    for platform in fallback_platforms
                ]
                fallback_results = await asyncio.gather(
                    *[job[1] for job in fallback_jobs],
                    return_exceptions=True,
                )

                for (platform, _), fallback_result in zip(fallback_jobs, fallback_results):
                    if isinstance(fallback_result, Exception):
                        log.error(f"[{platform.title()}] AI fallback failed: {fallback_result}")
                        continue
                    if not fallback_result:
                        continue

                    merged = _generic_merge_unique(
                        list(results.get(platform, [])),
                        fallback_result,
                        max_per_platform * 2,
                    )
                    filtered_merged = filter_products_by_query(merged, query, max_per_platform)
                    validated_merged, quality = _validate_and_rank_platform_products(
                        platform=platform,
                        products=filtered_merged,
                        query=query,
                        max_results=max_per_platform,
                        query_category=category,
                    )
                    before_count = len(results.get(platform, []))
                    results[platform] = validated_merged
                    platform_quality[platform] = quality
                    log.info(
                        f"[{platform.title()}] AI fallback merged: {before_count} -> {len(validated_merged)} "
                        f"(avg_conf={quality['avg_confidence']:.3f})"
                    )

        await browser.close()
        
    for p, items in results.items():
        quality = platform_quality.get(p, {})
        log.info(
            f"[{p.title()}] â†’ {len(items)} products "
            f"(avg_conf={quality.get('avg_confidence', 0):.3f})"
        )

    total = sum(len(v) for v in results.values())
    if total == 0: return []

    if _should_group_results(query, results=results):
        combined = match_products(results)
        combined = filter_grouped_products_by_query(combined, query)
        combined = _annotate_group_confidence(combined, query)
        combined = sort_grouped_products(combined)
    else:
        combined = _build_single_platform_groups(results)
        combined = sort_grouped_products(combined)

    # Keep API payload practical while preserving grouped comparables.
    hard_limit = max(10, max_per_platform * 2)
    if len(combined) > hard_limit:
        combined = combined[:hard_limit]

    if total > 0 and len(combined) == 0:
        log.info("[Search] Grouped results removed by strict relevance filter, returning fallback rows")
        combined = sort_grouped_products(_build_single_platform_groups(results))

    return combined


# â”€â”€ Quick test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    results = asyncio.run(search_products("headphones", 5))
    print(f"\n{'='*50}")
    print(f"  Results: {len(results)}")
    print(f"{'='*50}")
    for r in results[:5]:
        print(f"\n{r['name']}")
        for p in ['amazon', 'flipkart', 'meesho', 'myntra']:
            price = r['prices'].get(p)
            print(f"  {p:>10}: {'Rs.' + str(price) if price else 'N/A'}")
        print(f"  Rating: {r.get('rating', 'N/A')}")



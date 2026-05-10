# CompareHub — Data Dictionary

> **Project:** CompareHub — Live multi-platform product price comparison  
> **Stack:** Python (Flask) backend · Playwright / aiohttp web scraping · Vanilla HTML/CSS/JS frontend  
> **Platforms Scraped:** Amazon.in · Flipkart · Meesho · Myntra

---

## Table of Contents

1. [Product Categories](#1-product-categories)
2. [Sanitized Product Schema](#2-sanitized-product-schema-internal)
3. [Model Group — Final API Output](#3-model-group--final-api-output)
4. [API Endpoints](#4-api-endpoints)
5. [Environment Configuration & Dependencies](#5-environment-configuration--dependencies)

---

## 1. Product Categories

Recognized category labels used throughout the classifier, scraper routing, and frontend filtering.

| Category | Description | Active Platforms | Min Price (₹) |
|---|---|---|---|
| `Mobiles` | Smartphones and mobile phones | Amazon, Flipkart | 3,000 |
| `Laptops` | Notebooks and laptops | Amazon, Flipkart | 10,000 |
| `TVs` | Televisions (Smart, OLED, QLED) | Amazon, Flipkart | 5,000 |
| `Audio` | Headphones, earbuds, speakers, soundbars | Amazon, Flipkart | 1 |
| `Electronics` | Peripherals, chargers, consoles, cameras | Amazon, Flipkart | 1 |
| `Appliances` | Refrigerators, washing machines, ACs | Amazon, Flipkart | 1 |
| `Watches` | Smartwatches and analog watches | Amazon, Flipkart, Myntra | 1 |
| `Fashion` | Clothing, footwear, jewellery | Amazon, Flipkart, Myntra | 1 |
| `Beauty` | Cosmetics, skincare, haircare | Amazon, Flipkart, Meesho, Myntra | 1 |
| `Home` | Furniture, décor, bedding | Amazon, Flipkart, Meesho | 1 |
| `Stationery` | Pens, notebooks, markers | Amazon, Flipkart, Meesho | 1 |
| `Grocery` | Food, beverages, daily essentials | Amazon, Flipkart | 1 |
| `General` | Default fallback when no category matched | Amazon, Flipkart, Myntra | 1 |

> **Note:** Meesho is only queried for **Home**, **Beauty**, and **Stationery** categories.  
> Myntra is only queried for **Fashion**, **Watches**, and **Beauty** categories.

---

## 2. Sanitized Product Schema (Internal)

Output of `_sanitize_scraped_product()`. This is the validated, normalised form stored per-platform after raw scraping.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `name` | `string` | len ≥ 4 | Cleaned product title (whitespace normalised) |
| `price` | `int` | ₹1 – 10,000,000 | Price in INR (₹), integers only; currency symbols and commas stripped |
| `rating` | `float` | 0.0 – 5.0 | User rating rounded to 1 decimal place |
| `reviews` | `int` | 0 – 5,000,000 | Number of user reviews |
| `image` | `string \| null` | Valid URL or `null` | CDN URL of the product thumbnail |
| `link` | `string` | Non-empty URL | Canonicalised, tracking-stripped product URL |
| `platform` | `string` | One of 4 values | Source platform key: `amazon` / `flipkart` / `meesho` / `myntra` |
| `search_query_used` | `string \| null` | — | Exact query string sent to the platform search |
| `search_rewrite_reason` | `string \| null` | — | Label for why the query was rewritten (e.g. `"compact-model"`) |
| `confidence` | `float` | 0.0 – 0.99 | Extraction confidence score (assigned after sanitization) |
| `_query_score` | `float \| null` | Internal only | Relevance score used for ranking — stripped before API response |

---

## 3. Model Group — Final API Output

Output of `_group_variants_by_model()`. Multiple variant groups (e.g. 128GB Blue, 256GB Black) are folded into a single model group. This is the object returned by `GET /api/search`.

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Cleaned display name of the product model (storage / color / RAM stripped) |
| `model` | `string` | Alias for `name` — same value |
| `model_key` | `string` | Pipe-delimited compound key: `{category}\|{type}\|{brand}\|{variant}\|{id}` — e.g. `Mobiles\|product\|apple\|base\|iphone15` |
| `prices` | `object` | Cheapest price per platform across all variants — `{ amazon, flipkart, meesho, myntra } → int \| null` |
| `links` | `object` | Link to the cheapest variant per platform — `{ amazon, flipkart, meesho, myntra } → string \| null` |
| `rating` | `float` | Highest rating across all variants (0.0 – 5.0) |
| `reviews` | `int` | Highest review count across all variants |
| `image` | `string \| null` | Product image URL (first non-null image from any variant) |
| `variants` | `array` | List of Variant Entry objects — each holds `label`, `ram`, `storage`, `color`, `size`, `prices`, `links`, `best_price`, `best_platform` |
| `variant_count` | `int` | Number of variants in this model group |
| `confidence` | `float \| null` | Grouping confidence score (0.0 – 1.0); may be absent for single-platform results |

---

## 4. API Endpoints

All REST endpoints exposed by the Flask backend (`backend/app.py`).

| Endpoint | Method | Parameters | Purpose & Key Response Fields |
|---|---|---|---|
| `/api/search` | GET | `q` (query string) | Main product comparison search. Returns `query`, `normalized_query`, `source` (`live` / `coalesced` / `error`), `count`, `products[]`, `search_intelligence`, `message` |
| `/api/scrape/raw` | GET | `q`, `limit` (1–20, default 5) | Debug view of raw per-platform output before grouping. Returns `platforms` map of `platform → [raw product array]` and total `count` |
| `/api/suggestions` | GET | `q`, `limit` (4–20, default 12) | Typeahead autocomplete. Returns `suggestions[]` (type: `history` / `popular` / `product`), `did_you_mean[]` (≤ 3), `related_products[]` (≤ 6), `trending[]` (≤ 8) |
| `/api/trending` | GET | — | Returns `suggestions: string[8]` — fixed list of 8 popular product names for homepage UI |
| `/api/status` | GET | — | Health check. Returns `status: "online"` and human-readable `service` description string |

### `source` Field Values (`/api/search`)

| Value | Meaning |
|---|---|
| `"live"` | Fresh scraping was performed |
| `"coalesced"` | An identical concurrent request was in-flight; result was joined |
| `"error"` | Scraping failed; empty results returned |

---

## 5. Environment Configuration & Dependencies

### 5a. Environment Variables

All variables are prefixed with `COMPAREHUB_`.

| Variable | Default | Description |
|---|---|---|
| `MAX_PER_PLATFORM` | `5` | Max product listings fetched per platform per query |
| `HEADLESS` | `1` | `1` = headless Playwright browser; `0` = visible browser window |
| `LIGHTWEIGHT` | `1` | `1` = enable lightweight scraping mode |
| `USER_AGENT` | Chrome 127 UA | Override the HTTP User-Agent header sent to platforms |
| `GEMINI_API_KEY` | `""` | Google Gemini API key for AI extraction fallback |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model identifier |
| `AI_FALLBACK_MIN_RESULTS` | `2` | Trigger AI fallback when scraper yields fewer than N results |
| `LOW_CONFIDENCE_THRESHOLD` | `0.56` | Confidence score below which AI fallback may be triggered |
| `AI_HTML_MAX_CHARS` | `20000` | Max HTML characters sent to the AI for extraction |
| `AI_FALLBACK_TIMEOUT` | `8` | Timeout in seconds for the AI fallback HTML fetch |

### 5b. Backend Dependencies (`backend/requirements.txt`)

| Package | Purpose |
|---|---|
| `flask` | HTTP web framework for the API server |
| `flask-cors` | Cross-Origin Resource Sharing headers |
| `requests` | Synchronous HTTP client for scraping and AI endpoints |
| `beautifulsoup4` | HTML parsing for web scraping |
| `lxml` | Fast HTML/XML parser (used by BeautifulSoup) |
| `playwright` | Headless browser automation for JavaScript-heavy pages |
| `aiohttp` | Async HTTP client for concurrent scraping |
| `cachetools` | In-memory TTL cache — maxsize: 150, ttl: 3600 s, key format: `match-v7:{normalized_query}` |
| `thefuzz` | Fuzzy string matching for product grouping |
| `python-Levenshtein` | Levenshtein distance acceleration for thefuzz |
| `sentence-transformers` | Semantic embedding model (lazy-loaded; currently disabled) |

> **Frontend:** Pure HTML + Vanilla CSS + Vanilla JavaScript. No build step or framework required.  
> **Cache note:** The TTL cache is currently **inactive** on `/api/search` — every request triggers a fresh scrape.

---

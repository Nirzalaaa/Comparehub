# CompareHub - Quick Start Guide

## 🚀 Start the Application

```bash
cd backend
python app.py
```

The server will start on `http://localhost:5000`

## 📱 Test It

### Using PowerShell:
```powershell
# Single product search
Invoke-WebRequest -Uri 'http://localhost:5000/api/search?q=iPhone' `
  -UseBasicParsing -TimeoutSec 120 | `
  Select-Object -ExpandProperty Content | ConvertFrom-Json | `
  Select-Object count, source, @{l='First';e={$_.products[0].name}}
```

### Using curl (if installed):
```bash
curl "http://localhost:5000/api/search?q=headphones"
curl "http://localhost:5000/api/status"
```

### Using Python:
```python
import requests

# Live search (first time)
r = requests.get('http://localhost:5000/api/search?q=laptop', timeout=120)
print(r.json())

# Cached search (instant)
r = requests.get('http://localhost:5000/api/search?q=laptop', timeout=10)
print(r.json())
```

## ⚡ Key Features

✅ **Fast Results**
- First search: ~10.5 seconds
- Cached searches: <100ms (instant)

✅ **Multi-Platform**
- Amazon
- Flipkart
- Meesho
- Myntra

✅ **Smart Matching**
- Cross-platform product grouping
- Handles variants (color, size, storage)
- Shows best price for each variant

✅ **Smart Caching**
- Automatic 1-hour TTL cache
- Repeat searches are instant
- Manual cache clear available

## 🎯 Example Response

```json
{
  "query": "iPhone 15",
  "source": "cache|live",
  "count": 8,
  "products": [
    {
      "name": "Apple iPhone 15 (128GB)",
      "prices": {
        "amazon": 69999,
        "flipkart": 69999,
        "meesho": null,
        "myntra": null
      },
      "links": {
        "amazon": "https://amazon.in/...",
        "flipkart": "https://flipkart.com/...",
        ...
      },
      "image": "https://...",
      "rating": 4.5,
      "reviews": 1250
    }
    ...
  ]
}
```

## 🔧 Configuration

### Speed vs Quality Trade-off

Currently optimized for **speed**. To change:

```powershell
# Speed-first defaults
$env:COMPAREHUB_MAX_PER_PLATFORM = "5"
$env:COMPAREHUB_HEADLESS = "1"   # run scraper in background (no visible browser window)
$env:COMPAREHUB_LIGHTWEIGHT = "1"
```

**For more results (slower):**
Edit `backend/scraper.py`:
```python
async def search_products(query, max_per_platform=5):  # Change 5 to 8/10+
```

**For faster matching (lower quality):**
Edit `backend/matcher.py`:
```python
if jaccard >= 0.55 and fuzzy_score >= 75:  # Lower 0.55 to 0.45
```

**For more features (slower):**
Edit `backend/matcher.py`, uncomment the AI model:
```python
# Replace: _model = False
# With:   from sentence_transformers import SentenceTransformer
```

### Optional AI Fallback (Accuracy Boost On Weak Pages)

AI is optional. The scraper now uses a fast rule-based path first, then triggers AI only on weak/low-confidence platform results.

Set these environment variables before starting backend:

```powershell
# Option A: use your own extraction endpoint
$env:COMPAREHUB_AI_EXTRACT_ENDPOINT = "https://your-ai-extractor-endpoint"

# Option B: use Gemini directly (no custom endpoint needed)
$env:COMPAREHUB_GEMINI_API_KEY = "your-gemini-api-key"
$env:COMPAREHUB_GEMINI_MODEL = "gemini-2.0-flash"

# Optional tuning
$env:COMPAREHUB_AI_FALLBACK_MIN_RESULTS = "2"
$env:COMPAREHUB_LOW_CONFIDENCE_THRESHOLD = "0.56"
$env:COMPAREHUB_AI_HTML_MAX_CHARS = "20000"
$env:COMPAREHUB_AI_FALLBACK_TIMEOUT = "8"
```

If neither `COMPAREHUB_AI_EXTRACT_ENDPOINT` nor `COMPAREHUB_GEMINI_API_KEY` is set, AI fallback stays disabled and only fast scraper logic runs.

### Built-In Web Scraping

CompareHub now uses only our own scraping pipeline:
- Direct `requests` fetches with desktop headers
- Playwright fallback when the HTML path is blocked
- Tight price parsing and query filtering for cleaner results

```powershell
# Speed-first defaults
$env:COMPAREHUB_HEADLESS = "1"
$env:COMPAREHUB_LIGHTWEIGHT = "1"
$env:COMPAREHUB_MAX_PER_PLATFORM = "5"
```

Raw endpoint (clean JSON rows with `name`, `price`, `rating`, `link`, `image`):
`GET /api/scrape/raw?q=<query>&limit=5`

## 📝 Notes

- First request for any query takes ~10.5 seconds (live scrape)
- Repeat requests are cached for 1 hour and return in <100ms
- Default live scraping now uses a speed-first limit (`max_per_platform=5`)
- API responses are compact (name + prices + links + confidence)
- Clear cache: `/api/cache/clear`
- Amazon sometimes blocks Playwright (returns 0 products)
- Meesho often blocks or loads slowly

---
**Happy Searching! 🎉**

import urllib.request
import json

reqs = {
    'flask': '3.0.0', 
    'flask-cors': '4.0.0', 
    'requests': '2.31.0', 
    'beautifulsoup4': '4.12.2', 
    'lxml': 'No Version', 
    'playwright': 'No Version', 
    'aiohttp': 'No Version', 
    'cachetools': 'No Version', 
    'thefuzz': 'No Version', 
    'python-Levenshtein': 'No Version', 
    'sentence-transformers': 'No Version'
}

for req, current in reqs.items():
    try:
        url = "https://pypi.org/pypi/" + req + "/json"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            latest = data["info"]["version"]
            print(f"{req}: Current: {current} -> Latest: {latest}")
    except Exception as e:
        print(f"{req}: error {e}")

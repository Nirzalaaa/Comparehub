import re
from thefuzz import fuzz
import numpy as np
from urllib.parse import urlparse, urlunparse

# ── AI Semantic Model (lazy-loaded) ───────────────────────────
_model = None
_embedding_cache = {}

def _get_model():
    """Lazy-load the sentence-transformer model on first use."""
    global _model
    if _model is None:
        # Disabled for speed - use only Jaccard/fuzzy matching
        _model = False  # Sentinel: don't retry
    return _model if _model is not False else None

def _get_embedding(text):
    """Get embedding for a text, using cache to avoid re-computing."""
    model = _get_model()
    if model is None:
        return None
    if text not in _embedding_cache:
        _embedding_cache[text] = model.encode(text, convert_to_numpy=True)
    return _embedding_cache[text]

def _cosine_similarity(a, b):
    """Fast cosine similarity between two numpy vectors."""
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(np.dot(a, b) / norm)


def _pick_representative_name(matcher, members):
    """Choose the most informative product name among grouped members."""
    if not members:
        return ""

    def _score(member):
        name = (member.get("name") or "").strip()
        norm = matcher.normalize(name)
        tokens = [t for t in matcher.tokenize(norm) if t not in matcher.stop_words]
        unique_tokens = len(set(tokens))
        has_model_token = any(any(ch.isdigit() for ch in t) for t in tokens)
        has_variant = any(t in matcher.variant_identifiers for t in tokens)
        length_score = min(len(name), 120) / 120.0
        return (
            unique_tokens * 3
            + (8 if has_model_token else 0)
            + (3 if has_variant else 0)
            + length_score
        )

    best = max(members, key=_score)
    return (best.get("name") or "").strip()


def _merge_group_dicts(left, right):
    """Merge two already-grouped product dicts into one."""
    merged = {
        "name": left.get("name") or right.get("name"),
        "prices": dict(left.get("prices", {})),
        "links": dict(left.get("links", {})),
        "rating": max(left.get("rating", 0), right.get("rating", 0)),
        "reviews": max(left.get("reviews", 0), right.get("reviews", 0)),
        "image": left.get("image") or right.get("image"),
    }

    for platform, price in right.get("prices", {}).items():
        existing = merged["prices"].get(platform)
        if existing is None or (price and price < existing):
            merged["prices"][platform] = price
            merged["links"][platform] = right.get("links", {}).get(platform)

    return merged


def _stable_product_link(link):
    raw_link = str(link or "").strip()
    if not raw_link:
        return ""
    try:
        parsed = urlparse(raw_link)
    except Exception:
        return raw_link
    if not parsed.scheme or not parsed.netloc:
        return raw_link

    path = parsed.path or ""
    if "amazon." in parsed.netloc.lower():
        match = re.search(r"/dp/([A-Z0-9]{10})", path, re.IGNORECASE) or re.search(
            r"/gp/product/([A-Z0-9]{10})",
            path,
            re.IGNORECASE,
        )
        if match:
            return f"https://www.amazon.in/dp/{match.group(1).upper()}"

    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

class ProductMatcher:
    def __init__(self):
        # Noise/stopwords to remove
        self.stop_words = {"buy", "new", "best", "offer", "latest", "online", "cheap", "sale", "discount"}
        # "Hard" variants must match exactly (e.g. Pro vs non-Pro).
        self.strict_variant_identifiers = {"pro", "max", "plus", "ultra", "mini", "lite", "se", "fe"}
        # "Soft" variants are optional descriptors and should not block matching.
        self.optional_variant_identifiers = {"5g", "4g", "wi-fi", "wifi", "cellular"}
        self.variant_identifiers = self.strict_variant_identifiers | self.optional_variant_identifiers
        # Avoid grouping a phone with a case/cover listing.
        self.accessory_keywords = {
            "case", "cover", "protector", "tempered", "charger", "cable", "adapter",
            "accessory", "accessories", "bumper", "skin", "pouch", "magsafe", "guard",
            "remote", "mount", "bracket", "replacement", "protective", "earpad",
            "earpads", "cushion", "shell", "strap"
        }
        self.accessory_phrases = {
            "back case", "back cover", "mobile case", "phone case",
            "screen guard", "tempered glass", "camera protector",
            "replacement remote", "wall mount", "tv mount"
        }
        self.promotional_prefix_re = re.compile(r"^\s*(?:sponsored(?:\s+ad)?|ad)\s*[-:]\s*", re.IGNORECASE)
        self.alias_patterns = (
            (r"\bi[\s-]*phone\b", "iphone"),
            (r"\bone[\s-]*plus\b", "oneplus"),
            (r"\bair[\s-]*pods?\b", "airpods"),
            (r"\bmac[\s-]*book\b", "macbook"),
            (r"\bplay[\s-]*station\b", "playstation"),
            (r"\bfire[\s-]*boltt\b", "fireboltt"),
            (r"\bg[\s-]*shock\b", "gshock"),
        )
        self.model_prefix_words = {
            "iphone", "galaxy", "pixel", "redmi", "realme", "oneplus", "airpods",
            "macbook", "thinkpad", "ideapad", "pavilion", "vivobook", "inspiron",
            "xperia", "bravia", "motorola", "nothing", "surface", "ipad", "zbook", "omen"
        }
        self.component_prefix_words = {
            "gen", "gb", "tb", "mb", "mah", "hz", "inch", "cm", "mm", "ram",
            "qn", "snapdragon", "ddr", "uhd", "fhd", "qhd"
        }
        self._structured_cache = {}
        self.category_keywords = {
            "Mobiles": {
                "iphone", "phone", "mobile", "smartphone", "galaxy", "pixel", "oneplus",
                "redmi", "realme", "oppo", "vivo", "poco", "nothing", "motorola"
            },
            "Laptops": {
                "laptop", "macbook", "notebook", "ideapad", "thinkpad", "pavilion",
                "vivobook", "inspiron", "xps", "chromebook", "rog", "omen", "zenbook"
            },
            "TVs": {
                "tv", "television", "smarttv", "oled", "qled", "qned",
                "nanocell", "bravia"
            },
            "Audio": {
                "headphone", "headphones", "earphone", "earphones", "earbud", "earbuds",
                "buds", "airpods", "speaker", "soundbar", "neckband", "bluetooth"
            },
            "Electronics": {
                "mouse", "keyboard", "charger", "cable", "adapter", "powerbank",
                "tablet", "printer", "router", "camera", "tripod", "ssd", "pendrive",
                "usb", "console", "joystick", "webcam", "monitor", "projector"
            },
            "Watches": {
                "watch", "smartwatch", "gshock", "casio", "fastrack", "titan",
                "noise", "fireboltt", "fire-boltt"
            },
            "Fashion": {
                "shoe", "shoes", "sneaker", "sneakers", "running", "casual", "sandals",
                "slippers", "boots", "loafer", "shirt", "tshirt", "top", "jeans",
                "dress", "hoodie", "jacket", "kurta", "kurti", "saree", "leggings",
                "lehenga", "blouse", "dupatta", "palazzo", "outfit", "ring", "earring",
                "bracelet", "necklace", "jewellery", "jewelry"
            },
            "Home": {
                "sofa", "table", "chair", "bed", "mattress", "pillow", "curtain",
                "cushion", "wardrobe", "cupboard", "lamp", "shelf", "decor", "furniture",
                "cabinet"
            },
            "Stationery": {
                "pen", "pencil", "notebook", "marker", "eraser", "stapler", "highlighter",
                "diary", "register", "sketchbook", "stationery"
            },
            "Beauty": {
                "cream", "makeup", "lipstick", "perfume", "serum", "shampoo",
                "conditioner", "cleanser", "moisturizer", "lotion", "sunscreen",
                "cosmetic", "foundation", "mascara", "kajal", "facewash"
            },
            "Grocery": {
                "rice", "atta", "oil", "snack", "biscuit", "coffee", "tea", "masala",
                "dal", "noodle", "cereal", "dryfruit", "flour", "sugar", "salt", "grocery"
            },
            "Appliances": {
                "refrigerator", "fridge", "washing", "machine", "microwave", "vacuum",
                "geyser", "cooler", "purifier", "ac", "conditioner"
            },
        }
        self.brand_tokens = {
            "apple", "iphone", "samsung", "oneplus", "google", "pixel", "nothing",
            "motorola", "redmi", "xiaomi", "realme", "oppo", "vivo", "poco",
            "sony", "boat", "boat", "jbl", "noise", "hp", "lenovo", "dell", "asus",
            "acer", "lg", "mi", "tcl", "haier", "panasonic", "philips", "nike",
            "adidas", "puma", "reebok", "skechers", "casio", "titan", "fastrack",
            "fireboltt", "fire-boltt"
        }
        self.brand_aliases = {
            "iphone": "apple",
            "pixel": "google",
            "boat": "boAt",
            "fire-boltt": "fireboltt",
        }
        self.panel_keywords = {"oled", "qled", "led", "qned", "nanocell", "mini", "amoled"}
        self.audio_form_keywords = {
            "headphone": "headphones",
            "headphones": "headphones",
            "earphone": "earphones",
            "earphones": "earphones",
            "earbud": "earbuds",
            "earbuds": "earbuds",
            "airpods": "earbuds",
            "buds": "earbuds",
            "neckband": "neckband",
            "speaker": "speaker",
            "soundbar": "soundbar",
        }
        self.footwear_type_keywords = {
            "running": "running",
            "sneaker": "sneakers",
            "sneakers": "sneakers",
            "casual": "casual",
            "sandals": "sandals",
            "slippers": "slippers",
            "boots": "boots",
            "loafer": "loafers",
            "loafers": "loafers",
            "training": "training",
            "football": "football",
            "cricket": "cricket",
        }
        self.gender_keywords = {
            "men": "men",
            "mens": "men",
            "man": "men",
            "women": "women",
            "womens": "women",
            "woman": "women",
            "ladies": "women",
            "kids": "kids",
            "kid": "kids",
            "boys": "kids",
            "girls": "kids",
            "unisex": "unisex",
        }
        self.color_tokens = {
            "black", "white", "blue", "red", "green", "pink", "purple", "yellow",
            "orange", "brown", "silver", "gold", "gray", "grey", "midnight",
            "starlight", "ultramarine", "graphite", "violet", "cobalt", "phantom",
            "space", "sky", "natural", "titanium"
        }
        self.fashion_family_noise_tokens = {
            "shoe", "shoes", "footwear", "running", "road", "sport", "sports",
            "casual", "training", "walking", "trail", "court", "tennis", "gym",
            "run", "air", "zoom",
            "mens", "men", "womens", "women", "kids", "boys", "girls", "unisex"
        }
        self.consumer_signature_prefixes = self.model_prefix_words | {
            "wh", "wf", "xps", "rog", "qled", "oled", "tv", "watch"
        }

    def sanitize_title(self, text):
        """Strip marketplace promo labels from listing titles."""
        if not text:
            return ""
        cleaned = self.promotional_prefix_re.sub("", text)
        return re.sub(r"\s+", " ", cleaned).strip(" -:")

    def canonicalize_aliases(self, text):
        """Collapse split brand phrases into common searchable forms."""
        if not text:
            return ""
        normalized = re.sub(r"\s+", " ", text.strip().lower()).replace("+", " plus ")
        for pattern, replacement in self.alias_patterns:
            normalized = re.sub(pattern, replacement, normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def normalize(self, text):
        if not text:
            return ""
        # Convert to lowercase
        text = self.canonicalize_aliases(text)

        # Split alpha-numeric joins ONLY when alpha part is 2+ chars
        # so "iphone17" -> "iphone 17" but "s26" stays as-is (handled below).
        # We do NOT split single-letter prefixes like s24, a54, m55 here.
        text = re.sub(r'([a-z]{2,})(\d)', r'\1 \2', text)
        text = re.sub(r'(\d)([a-z]{2,})', r'\1 \2', text)
        
        # Standardize units globally
        text = re.sub(r'(\d+)\s*gb\b', r'\1gb', text)
        text = re.sub(r'(\d+)\s*tb\b', r'\1tb', text)
        text = re.sub(r'(\d+)\s*mb\b', r'\1mb', text)
        text = re.sub(r'(\d+)\s*kg\b', r'\1kg', text)
        text = re.sub(r'(\d+)\s*inches\b', r'\1inch', text)
        text = re.sub(r'(\d+)\s*inch\b', r'\1inch', text)
        text = re.sub(r'(\d+)\s*cm\b', r'\1cm', text)
        text = re.sub(r'(\d+)\s*mm\b', r'\1mm', text)
        
        # Remove symbols (keep alphanumeric and spaces)
        text = re.sub(r'[^a-z0-9]', ' ', text)
        
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def tokenize(self, text):
        return text.split()

    def is_accessory(self, text):
        normalized = self.normalize(text)
        if any(phrase in normalized for phrase in self.accessory_phrases):
            return True
        tokens = set(self.tokenize(normalized))
        return bool(tokens & self.accessory_keywords)

    def extract_important_tokens(self, tokens):
        """
        Extracts important tokens:
        - Words with numbers (128gb, s24, s26)
        - Brand/model words (length > 2)
        - Strict variant identifiers (pro, max)
        - Short model-prefix tokens (1-2 chars) that sit next to a number token
          e.g. the 's' in 's 26', 'a' in 'a 54'
        Removes stop words.
        """
        important = set()
        numbers = set()
        variants = set()
        model_prefixes = set()  # single/double-char prefix adjacent to a number

        token_list = list(tokens)  # preserve order for adjacency check
        token_set = set(token_list)

        # Identify which short tokens are model-name prefixes
        # (sit immediately before or after a purely-numeric token)
        for idx, token in enumerate(token_list):
            if len(token) <= 2 and token.isalpha():
                # Check if a digit-only token is adjacent
                prev_tok = token_list[idx - 1] if idx > 0 else ''
                next_tok = token_list[idx + 1] if idx < len(token_list) - 1 else ''
                if (prev_tok and prev_tok.lstrip('0').isdigit()) or \
                   (next_tok and next_tok.lstrip('0').isdigit()):
                    model_prefixes.add(token)

        for token in token_set:
            if token in self.stop_words:
                continue
                
            has_digit = bool(re.search(r'\d', token))
            
            # Keep numbers (e.g. "128gb", "s26", "26")
            if has_digit:
                important.add(token)
                numbers.add(token)
            # Keep variants (pro, max, ultra, ...)
            elif token in self.variant_identifiers:
                important.add(token)
                variants.add(token)
            # Keep model-prefix short tokens ('s', 'a', 'm' next to a number)
            elif token in model_prefixes:
                important.add(token)
            # Keep brand/model words (length > 2)
            elif len(token) > 2:
                important.add(token)
                
        return important, numbers, variants

    def _extract_storage_tokens(self, numeric_tokens):
        """Return normalized device storage tokens like {'128gb', '1tb'}.

        Small GB values are usually RAM, not product storage, so we ignore
        values below 32GB to avoid splitting the same phone into separate groups
        when one platform includes RAM in the title and another does not.
        """
        storage = set()
        for token in numeric_tokens:
            match = re.search(r'(\d+)(gb|tb|mb)$', token)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)
                if unit == "tb":
                    storage.add(f"{amount}{unit}")
                    continue
                if unit == "mb":
                    continue
                if amount >= 32:
                    storage.add(f"{amount}{unit}")
        return storage

    def _extract_model_numbers(self, numeric_tokens):
        """
        Extract likely model/version numbers from numeric-bearing tokens.
        Handles forms like "iphone17", "s24", "15", while ignoring storage/connectivity specs.
        """
        model_numbers = set()
        for token in numeric_tokens:
            if token in self.optional_variant_identifiers:
                continue
            if re.search(r'\d+(gb|tb|mb|mah|hz|inch|cm|mm)$', token):
                continue
            for raw_num in re.findall(r'\d+', token):
                if not raw_num:
                    continue
                normalized_num = str(int(raw_num))
                # Skip long year-like/spec numbers that usually don't identify phone model family.
                if len(normalized_num) > 3:
                    continue
                model_numbers.add(normalized_num)
        return model_numbers

    def _raw_alnum_tokens(self, text):
        """Tokenize a title without splitting model codes like 'xm5' or '16e'."""
        if not text:
            return []
        cleaned = re.sub(r"[^a-z0-9]+", " ", self.canonicalize_aliases(self.sanitize_title(text)))
        return [token for token in cleaned.split() if token]

    def _is_specific_model_signature(self, token):
        """Return True for exact model codes such as s24, m3, xm5, wh1000xm5, 16e."""
        if not token or len(token) < 2 or len(token) > 24:
            return False
        if not re.search(r"[a-z]", token) or not re.search(r"\d", token):
            return False
        if token in self.optional_variant_identifiers:
            return False
        if re.search(r"\d+(gb|tb|mb|mah|hz|inch|cm|mm)$", token):
            return False
        return True

    def _can_prefix_model_signature(self, token):
        """Allow short prefixes or well-known model-family words to form combined signatures."""
        return bool(token) and (len(token) <= 3 or token in self.model_prefix_words)

    def _looks_like_component_signature(self, signature):
        """Reject signatures that are likely chipset/spec fragments, not product model families."""
        match = re.match(r"([a-z]+)\d", signature or "")
        return bool(match and match.group(1) in self.component_prefix_words)

    def _is_vendor_sku_signature(self, signature, category=None):
        """Return True for seller/internal SKU-style signatures that should not dominate grouping."""
        if not signature or len(signature) < 7:
            return False
        if category not in {"Mobiles", "Laptops", "TVs", "Audio", "Watches", "Electronics"}:
            return False
        if any(signature.startswith(prefix) for prefix in self.consumer_signature_prefixes):
            return False

        digit_runs = re.findall(r"\d+", signature)
        if not digit_runs:
            return False
        if any(len(run) >= 2 for run in digit_runs):
            return False
        return True

    def extract_specific_model_signatures(self, text):
        """Extract exact model signatures from a raw listing title."""
        raw = self._raw_alnum_tokens(text)
        signatures = set()

        for token in raw:
            if self._is_specific_model_signature(token):
                signatures.add(token)

        for idx in range(len(raw) - 1):
            left = raw[idx]
            right = raw[idx + 1]

            if (
                re.fullmatch(r"[a-z]{1,10}", left)
                and self._can_prefix_model_signature(left)
                and left not in self.variant_identifiers
                and (
                    re.fullmatch(r"\d{1,5}", right)
                    or (
                        self._is_specific_model_signature(right)
                        and re.match(r"^\d", right)
                    )
                )
            ):
                combined = f"{left}{right}"
                if self._is_specific_model_signature(combined):
                    signatures.add(combined)

            if re.fullmatch(r"\d{1,5}", left) and re.fullmatch(r"[a-z]{1,2}", right):
                combined = f"{left}{right}"
                if self._is_specific_model_signature(combined):
                    signatures.add(combined)

        for idx in range(len(raw) - 2):
            first = raw[idx]
            second = raw[idx + 1]
            third = raw[idx + 2]

            if (
                re.fullmatch(r"[a-z]{1,10}", first)
                and self._can_prefix_model_signature(first)
                and first not in self.variant_identifiers
                and re.fullmatch(r"\d{1,5}", second)
                and (
                    self._is_specific_model_signature(third)
                    or re.fullmatch(r"[a-z]{1,3}", third)
                )
            ):
                combined = f"{first}{second}{third}"
                if self._is_specific_model_signature(combined):
                    signatures.add(combined)

        return signatures

    def extract_primary_model_signatures(self, text, category_hint=None):
        """Return the most discriminative model signatures for exact-family matching."""
        category = category_hint or self.infer_category_from_text(text)
        signatures = self.extract_specific_model_signatures(text)
        non_sku_signatures = {
            signature
            for signature in signatures
            if not self._is_vendor_sku_signature(signature, category)
        }
        family_signatures = {
            signature
            for signature in non_sku_signatures
            if re.fullmatch(r"[a-z]{1,5}\d[a-z0-9]*", signature)
            and not self._looks_like_component_signature(signature)
        }
        if family_signatures:
            max_len = max(len(signature) for signature in family_signatures)
            return {signature for signature in family_signatures if len(signature) == max_len}
        return non_sku_signatures or signatures

    def _extract_numeric_suffix_signatures(self, signatures):
        """Return model signatures like 16e or 8a that distinguish numbered families."""
        return {
            signature
            for signature in signatures
            if re.fullmatch(r"\d{1,4}[a-z]{1,2}", signature)
        }

    def _has_conflicting_suffix_models(self, nums_a, sigs_a, nums_b, sigs_b):
        """Reject base model vs suffixed model-family mismatches like 16 vs 16e."""
        suffix_a = self._extract_numeric_suffix_signatures(sigs_a)
        suffix_b = self._extract_numeric_suffix_signatures(sigs_b)
        model_nums_a = self._extract_model_numbers(nums_a)
        model_nums_b = self._extract_model_numbers(nums_b)

        if suffix_a and not suffix_b:
            for signature in suffix_a:
                match = re.match(r"(\d+)", signature)
                if match and match.group(1) in model_nums_b:
                    return True

        if suffix_b and not suffix_a:
            for signature in suffix_b:
                match = re.match(r"(\d+)", signature)
                if match and match.group(1) in model_nums_a:
                    return True

        return False

    def _has_conflicting_family_signatures(self, primary_a, primary_b, specific_intersection):
        """Reject close-but-different model families like WH-1000XM5 vs WF-1000XM5."""
        if not primary_a or not primary_b or (primary_a & primary_b) or not specific_intersection:
            return False

        strong_a = {signature for signature in primary_a if len(signature) >= 5}
        strong_b = {signature for signature in primary_b if len(signature) >= 5}
        strong_shared = {signature for signature in specific_intersection if len(signature) >= 4}
        if not strong_a or not strong_b or not strong_shared:
            return False

        for shared in strong_shared:
            if any(signature.endswith(shared) for signature in strong_a) and any(signature.endswith(shared) for signature in strong_b):
                return True

        return False

    def infer_category_from_text(self, text):
        """Infer a broad product category from title-like text."""
        normalized = self.normalize(text)
        tokens = set(self.tokenize(normalized))
        if not tokens:
            return "Electronics"

        scores = {}
        for category, keywords in self.category_keywords.items():
            overlap = len(tokens & keywords)
            if overlap:
                scores[category] = overlap

        if not scores:
            signatures = self.extract_specific_model_signatures(text)
            if any(re.fullmatch(r"(iphone\d+[a-z]{0,2}|s\d{2,3}|a\d{2,3}|m\d{2,3}|pixel\d+[a-z]{0,2}|oneplus\d+)", sig) for sig in signatures):
                return "Mobiles"
            if any(sig.startswith(("wh", "wf", "airpods")) for sig in signatures):
                return "Audio"
            if "macbook" in tokens or any(re.fullmatch(r"m\d", sig) for sig in signatures):
                return "Laptops"
            return "Electronics"

        preferred = [
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
        ]
        return max(preferred, key=lambda category: (scores.get(category, 0), -preferred.index(category)))

    def _extract_brand(self, ordered_tokens, token_set=None):
        token_set = token_set or set(ordered_tokens)
        matches = [token for token in ordered_tokens if token in self.brand_tokens]
        if not matches:
            matches = [token for token in token_set if token in self.brand_tokens]
        if not matches:
            return None
        canonical = self.brand_aliases.get(matches[0], matches[0])
        return canonical

    def _extract_ram_tokens(self, text, numeric_tokens):
        """Return RAM capacity markers like {'8gb'} when explicitly present."""
        normalized = self.normalize(text)
        ram = set()
        for token in numeric_tokens:
            match = re.search(r"(\d+)(gb|tb)$", token)
            if not match:
                continue
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "gb" and 1 <= amount <= 32:
                ram.add(f"{amount}{unit}")

        explicit = re.finditer(r"(\d+)\s*gb\s*ram", normalized)
        for match in explicit:
            ram.add(f"{int(match.group(1))}gb")

        return ram

    def _extract_display_sizes(self, text):
        """Extract likely display sizes in inches."""
        if not text:
            return set()
        lowered = self.sanitize_title(text).lower()
        sizes = set()
        for match in re.finditer(r"(\d{1,3}(?:\.\d)?)\s*(?:-|\s)?\s*(?:inch|inches|in\b|\"|')", lowered):
            try:
                sizes.add(f"{float(match.group(1)):.1f}")
            except ValueError:
                continue
        return sizes

    def _extract_panel_types(self, normalized_text):
        panel_types = set()
        for panel in self.panel_keywords:
            if panel in normalized_text:
                panel_types.add(panel)
        if "mini led" in self.sanitize_title(normalized_text).lower():
            panel_types.add("mini led")
        return panel_types

    def _extract_audio_forms(self, tokens):
        forms = set()
        for token in tokens:
            mapped = self.audio_form_keywords.get(token)
            if mapped:
                forms.add(mapped)
        return forms

    def _extract_tv_forms(self, tokens):
        forms = set()
        if {"tv", "television", "smarttv"} & tokens:
            forms.add("tv")
        if "monitor" in tokens:
            forms.add("monitor")
        return forms

    def _extract_laptop_chips(self, normalized_text):
        chips = set()
        for match in re.finditer(r"\bm\d\b", normalized_text):
            chips.add(match.group(0))
        for match in re.finditer(r"\bi[3579]\b", normalized_text):
            chips.add(match.group(0))
        for match in re.finditer(r"\bryzen\s*\d\b", normalized_text):
            chips.add(match.group(0).replace(" ", ""))
        for match in re.finditer(r"\ba\d{2}\b", normalized_text):
            chips.add(match.group(0))
        return chips

    def _extract_gender(self, tokens):
        genders = set()
        for token in tokens:
            mapped = self.gender_keywords.get(token)
            if mapped:
                genders.add(mapped)
        return genders

    def _extract_footwear_types(self, tokens):
        footwear = set()
        for token in tokens:
            mapped = self.footwear_type_keywords.get(token)
            if mapped:
                footwear.add(mapped)
        return footwear

    def _extract_family_tokens(self, ordered_tokens, category, brand=None):
        """Extract distinctive product-family words beyond brand/category boilerplate."""
        if not ordered_tokens:
            return set()

        generic = set(self.stop_words)
        generic |= self.variant_identifiers
        generic |= self.color_tokens
        generic |= set(self.gender_keywords.keys())
        generic |= set(self.footwear_type_keywords.keys())
        generic |= self.category_keywords.get(category, set())
        generic |= self.brand_tokens

        if category == "Fashion":
            generic |= self.fashion_family_noise_tokens

        family_tokens = []
        for token in ordered_tokens:
            if len(token) < 3:
                continue
            if token == brand:
                continue
            if token in generic:
                continue
            if re.search(r"\d", token):
                continue
            family_tokens.append(token)

        return set(family_tokens)

    def _extract_color_signatures(self, ordered_tokens, tokens):
        """Capture explicit color markers so different variants stay separated."""
        base_colors = set(self.color_tokens) - {"titanium"}
        signatures = set()

        for token in set(ordered_tokens) | set(tokens):
            if token in base_colors:
                signatures.add(token)
                continue

            matched = [
                color for color in base_colors
                if len(color) >= 4 and color in token
            ]
            if len(set(matched)) >= 2:
                signatures.add(token)

        return signatures

    def extract_structured_attributes(self, text, category_hint=None):
        """Parse a listing title into structured product signals."""
        cache_key = (text or "", category_hint or "")
        cached = getattr(self, "_structured_cache", {}).get(cache_key)
        if cached is not None:
            return cached

        sanitized = self.sanitize_title(text or "")
        normalized = self.normalize(sanitized)
        tokens = set(self.tokenize(normalized))
        ordered_raw_tokens = self._raw_alnum_tokens(sanitized)
        raw_tokens = set(ordered_raw_tokens)
        category = category_hint or self.infer_category_from_text(sanitized)
        important, numeric_tokens, variants = self.extract_important_tokens(self.tokenize(normalized))
        brand = self._extract_brand(ordered_raw_tokens, tokens | raw_tokens)
        specific_model_signatures = self.extract_specific_model_signatures(sanitized)

        attrs = {
            "category": category,
            "brand": brand,
            "important_tokens": important,
            "numeric_tokens": numeric_tokens,
            "strict_variants": variants & self.strict_variant_identifiers,
            "storage": self._extract_storage_tokens(numeric_tokens),
            "ram": self._extract_ram_tokens(sanitized, numeric_tokens),
            "model_numbers": self._extract_model_numbers(numeric_tokens),
            "specific_model_signatures": specific_model_signatures,
            "primary_model_signatures": self.extract_primary_model_signatures(sanitized, category_hint=category),
            "sku_like_signatures": {
                signature
                for signature in specific_model_signatures
                if self._is_vendor_sku_signature(signature, category)
            },
            "display_sizes": self._extract_display_sizes(sanitized),
            "panel_types": self._extract_panel_types(normalized),
            "audio_forms": self._extract_audio_forms(tokens),
            "tv_forms": self._extract_tv_forms(tokens),
            "laptop_chips": self._extract_laptop_chips(normalized),
            "footwear_types": self._extract_footwear_types(tokens),
            "gender": self._extract_gender(tokens),
            "colors": self._extract_color_signatures(ordered_raw_tokens, tokens),
            "family_tokens": self._extract_family_tokens(ordered_raw_tokens, category, brand=brand),
            "accessory": self.is_accessory(sanitized),
        }

        self._structured_cache[cache_key] = attrs
        return attrs

    def _same_or_missing(self, left, right):
        return not left or not right or bool(left & right)

    def _display_sizes_compatible(self, left, right):
        if not left or not right:
            return True
        for a in left:
            for b in right:
                try:
                    if abs(float(a) - float(b)) <= 0.6:
                        return True
                except ValueError:
                    continue
        return False

    def matches_query_attributes(self, query_attrs, product_attrs):
        """Check whether a product satisfies structured constraints implied by a query."""
        query_category = query_attrs.get("category") or "Electronics"
        product_category = product_attrs.get("category") or query_category

        if query_category not in {"Electronics", "General"} and product_category != query_category:
            return False

        query_brand = query_attrs.get("brand")
        product_brand = product_attrs.get("brand")
        if query_brand and product_brand and query_brand != product_brand:
            return False

        if query_attrs.get("accessory") != product_attrs.get("accessory"):
            return False

        if query_attrs.get("strict_variants") and product_attrs.get("strict_variants") and query_attrs["strict_variants"] != product_attrs["strict_variants"]:
            return False

        if not self._same_or_missing(query_attrs.get("colors"), product_attrs.get("colors")):
            return False

        if (
            query_attrs.get("primary_model_signatures")
            and product_attrs.get("primary_model_signatures")
            and any(len(signature) >= 5 for signature in query_attrs["primary_model_signatures"])
        ):
            if not (query_attrs["primary_model_signatures"] & product_attrs["primary_model_signatures"]):
                return False

        if query_attrs.get("specific_model_signatures") and product_attrs.get("specific_model_signatures"):
            if not (query_attrs["specific_model_signatures"] & product_attrs["specific_model_signatures"]):
                return False

        if query_attrs.get("model_numbers") and product_attrs.get("model_numbers"):
            if not (query_attrs["model_numbers"] & product_attrs["model_numbers"]):
                return False

        if query_category in {"Mobiles", "Laptops", "Watches"}:
            if query_attrs.get("storage") and product_attrs.get("storage") and query_attrs["storage"] != product_attrs["storage"]:
                return False
            if query_attrs.get("ram") and product_attrs.get("ram") and query_attrs["ram"] != product_attrs["ram"]:
                return False

        if query_category == "Laptops":
            if query_attrs.get("laptop_chips") and product_attrs.get("laptop_chips") and not (query_attrs["laptop_chips"] & product_attrs["laptop_chips"]):
                return False
            if not self._display_sizes_compatible(query_attrs.get("display_sizes"), product_attrs.get("display_sizes")):
                return False

        if query_category == "TVs":
            if query_attrs.get("panel_types") and product_attrs.get("panel_types") and not (query_attrs["panel_types"] & product_attrs["panel_types"]):
                return False
            if query_attrs.get("tv_forms") and product_attrs.get("tv_forms") and not (query_attrs["tv_forms"] & product_attrs["tv_forms"]):
                return False
            if not self._display_sizes_compatible(query_attrs.get("display_sizes"), product_attrs.get("display_sizes")):
                return False

        if query_category == "Audio":
            if query_attrs.get("audio_forms") and product_attrs.get("audio_forms") and not (query_attrs["audio_forms"] & product_attrs["audio_forms"]):
                return False

        if query_category == "Fashion":
            if query_attrs.get("footwear_types"):
                if not product_attrs.get("footwear_types"):
                    return False
                if not (query_attrs["footwear_types"] & product_attrs["footwear_types"]):
                    return False
            if query_attrs.get("gender") and product_attrs.get("gender"):
                if "unisex" not in product_attrs["gender"] and not (query_attrs["gender"] & product_attrs["gender"]):
                    return False
            if query_attrs.get("gender") and not product_attrs.get("gender") and query_attrs["gender"] != {"unisex"}:
                return False
            if query_attrs.get("family_tokens"):
                if not product_attrs.get("family_tokens"):
                    return False
                if not (query_attrs["family_tokens"] & product_attrs["family_tokens"]):
                    return False

        return True

    def is_structured_compatible(self, attrs_a, attrs_b):
        """Symmetric structured compatibility for cross-platform grouping."""
        return self.matches_query_attributes(attrs_a, attrs_b) and self.matches_query_attributes(attrs_b, attrs_a)

    def enforce_strict_validation(self, nums_a, nums_b, vars_a, vars_b):
        """
        Validates that structural markers (Storage, RAM, Versions, Variants) do not contradict.
        """
        # 1. Hard variant validation (Pro/Max/Plus etc.) must match exactly.
        strict_vars_a = vars_a & self.strict_variant_identifiers
        strict_vars_b = vars_b & self.strict_variant_identifiers
        if strict_vars_a != strict_vars_b:
            return False
            
        # 2. Storage/Memory Validation (e.g., 128gb vs 256gb)
        storage_a = self._extract_storage_tokens(nums_a)
        storage_b = self._extract_storage_tokens(nums_b)
        
        # If both mention storage, they MUST match exactly
        if storage_a and storage_b and storage_a != storage_b:
            return False
            
        # 3. Model version validation (e.g., iPhone 14 vs iPhone 15).
        model_nums_a = self._extract_model_numbers(nums_a)
        model_nums_b = self._extract_model_numbers(nums_b)
        if model_nums_a and model_nums_b and not (model_nums_a & model_nums_b):
            return False
                
        return True

    def is_match(self, prod_a, prod_b):
        """
        Main logic evaluating two product dictionaries.
        """
        name_a = self.sanitize_title(prod_a.get('name', ''))
        name_b = self.sanitize_title(prod_b.get('name', ''))

        # Never match device listings with accessory-only listings.
        if self.is_accessory(name_a) != self.is_accessory(name_b):
            return False
        
        norm_a = self.normalize(name_a)
        norm_b = self.normalize(name_b)
        
        tokens_a = self.tokenize(norm_a)
        tokens_b = self.tokenize(norm_b)
        
        imp_a, nums_a, vars_a = self.extract_important_tokens(tokens_a)
        imp_b, nums_b, vars_b = self.extract_important_tokens(tokens_b)

        specific_sigs_a = self.extract_specific_model_signatures(name_a)
        specific_sigs_b = self.extract_specific_model_signatures(name_b)
        primary_sigs_a = self.extract_primary_model_signatures(name_a)
        primary_sigs_b = self.extract_primary_model_signatures(name_b)
        specific_intersection = specific_sigs_a & specific_sigs_b
        attrs_a = self.extract_structured_attributes(name_a)
        attrs_b = self.extract_structured_attributes(name_b)

        # Strict Structural Validations
        if not self.enforce_strict_validation(nums_a, nums_b, vars_a, vars_b):
            return False
        if not self.is_structured_compatible(attrs_a, attrs_b):
            return False
        if self._has_conflicting_family_signatures(primary_sigs_a, primary_sigs_b, specific_intersection):
            return False
        if specific_sigs_a and specific_sigs_b and not specific_intersection:
            return False
        if self._has_conflicting_suffix_models(nums_a, specific_sigs_a, nums_b, specific_sigs_b):
            return False

        # Jaccard calculations
        if not imp_a or not imp_b:
            return False
            
        intersection = imp_a & imp_b
        union = imp_a | imp_b
        jaccard = len(intersection) / len(union)
        
        # Fuzzy string match
        fuzzy_score = fuzz.token_set_ratio(norm_a, norm_b)
        
        # Final Matching condition as requested by user
        overlap = len(intersection) / min(len(imp_a), len(imp_b))

        # Extra boost: if both share the same numeric model number AND the same brand,
        # count that as a near-certain match (handles naming variations like
        # "Samsung Galaxy S26" vs "SAMSUNG S 26 Ultra" where brand+model_num match).
        shared_nums = nums_a & nums_b
        shared_alpha = {t for t in intersection if not any(c.isdigit() for c in t)}
        brand_and_model_match = bool(shared_nums) and len(shared_alpha) >= 1
        
        # Group when lexical overlap is meaningful.
        # Keep fuzzy-only matching stricter to reduce false positives.
        if brand_and_model_match or overlap >= 0.50 or jaccard >= 0.35 or (fuzzy_score >= 70 and overlap >= 0.35):
            return True
        
        # ── AI Semantic Fallback ──────────────────────────────
        # Even if Jaccard/fuzzy scores are borderline, allow match
        # if neural embeddings indicate high semantic similarity.
        # This handles cases like:
        #   "Apple iPhone 15 Midnight" vs "iPhone15 Black"
        # where surface-level similarity is low but meaning is same.
        try:
            emb_a = _get_embedding(norm_a)
            emb_b = _get_embedding(norm_b)
            if emb_a is not None and emb_b is not None:
                cosine = _cosine_similarity(emb_a, emb_b)
                # Require stricter threshold for AI-only match to avoid false positives
                if cosine >= 0.82:
                    return True
        except Exception:
            pass  # Silently degrade if AI model fails
            
        return False


def _format_capacity_label(token):
    match = re.match(r"(\d+)(gb|tb|mb)$", str(token or "").strip().lower())
    if not match:
        return None
    return f"{int(match.group(1))}{match.group(2).upper()}"


def _normalize_display_case(text):
    value = str(text or "").strip()
    if not value:
        return ""
    if value.upper() == value and any(ch.isalpha() for ch in value):
        return value.title()
    return value


def _ordered_color_label(matcher, name, colors):
    ordered = []
    color_set = set(colors or set())
    for token in matcher._raw_alnum_tokens(name):
        if token in color_set and token not in ordered:
            ordered.append(token)
    if not ordered:
        ordered = sorted(color_set)
    if not ordered:
        return None
    return " ".join(token.title() for token in ordered)


def _extract_size_label(matcher, name, category=None):
    explicit = re.search(r"\bsize\s*([a-z0-9]+)\b", str(name or ""), flags=re.IGNORECASE)
    if explicit:
        value = explicit.group(1).upper()
        if value.isdigit():
            return f"Size {value}"
        return value

    if category != "Fashion":
        return None

    size_tokens = {"xs", "s", "m", "l", "xl", "xxl", "xxxl"}
    ordered = []
    for token in matcher._raw_alnum_tokens(name):
        if token in size_tokens and token not in ordered:
            ordered.append(token.upper())

    return ordered[0] if ordered else None


def _clean_model_display_name(matcher, name, attrs=None):
    sanitized = matcher.sanitize_title(name or "")
    if not sanitized:
        return ""

    attrs = attrs or matcher.extract_structured_attributes(sanitized)
    cleaned = sanitized.replace("+", " plus ")

    for token in sorted((attrs.get("storage") or set()) | (attrs.get("ram") or set()), key=len, reverse=True):
        match = re.match(r"(\d+)(gb|tb|mb)$", token)
        if not match:
            continue
        amount, unit = match.groups()
        cleaned = re.sub(
            rf"\b{amount}\s*{unit}\b(?:\s*ram\b)?",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

    for token in sorted(attrs.get("colors") or set(), key=len, reverse=True):
        cleaned = re.sub(rf"\b{re.escape(token)}\b", " ", cleaned, flags=re.IGNORECASE)

    for token in matcher.optional_variant_identifiers:
        cleaned = re.sub(rf"\b{re.escape(token)}\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\bsize\s*[a-z0-9]+\b", " ", cleaned, flags=re.IGNORECASE)
    if attrs.get("category") == "Fashion":
        cleaned = re.sub(r"\b(?:xs|s|m|l|xl|xxl|xxxl)\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\b(?:ram|rom|ssd)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\[\],]+", " ", cleaned)
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:/")
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:/")
    cleaned = re.sub(r"\bplus\b", "Plus", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bultra\b", "Ultra", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmax\b", "Max", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmini\b", "Mini", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\blite\b", "Lite", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpro\b", "Pro", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfe\b", "FE", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bse\b", "SE", cleaned, flags=re.IGNORECASE)
    return _normalize_display_case(cleaned or sanitized)


def _pick_model_display_name(matcher, variant_groups):
    candidates = []
    for group in variant_groups:
        raw_name = group.get("name", "")
        attrs = matcher.extract_structured_attributes(raw_name)
        cleaned = _clean_model_display_name(matcher, raw_name, attrs=attrs)
        if not cleaned:
            continue
        tokens = matcher.tokenize(matcher.normalize(cleaned))
        score = 0
        if attrs.get("brand") and attrs["brand"] in set(tokens):
            score += 12
        score += len(attrs.get("strict_variants") or set()) * 4
        score += len(attrs.get("primary_model_signatures") or set()) * 5
        score -= max(0, len(tokens) - 6)
        candidates.append((score, len(cleaned), cleaned))

    if not candidates:
        fallback = next((group.get("name", "") for group in variant_groups if group.get("name")), "")
        return _normalize_display_case(fallback)

    candidates.sort(key=lambda item: (-item[0], item[1], item[2].lower()))
    return candidates[0][2]


def _extract_model_group_key(matcher, name):
    attrs = matcher.extract_structured_attributes(name or "")
    primary_signatures = attrs.get("primary_model_signatures") or set()
    specific_signatures = {
        signature
        for signature in (attrs.get("specific_model_signatures") or set())
        if not re.fullmatch(r"gb\d+", signature)
    }
    variant_type = ",".join(sorted(attrs.get("strict_variants") or set())) or "base"
    cleaned_model = matcher.normalize(_clean_model_display_name(matcher, name, attrs=attrs))
    core_identity = ",".join(sorted(primary_signatures or specific_signatures)) or cleaned_model

    key_parts = [
        attrs.get("category") or "",
        "accessory" if attrs.get("accessory") else "product",
        attrs.get("brand") or "",
        variant_type,
        core_identity,
    ]
    return "|".join(key_parts)


def _build_variant_entry(matcher, group):
    name = group.get("name", "")
    attrs = matcher.extract_structured_attributes(name)
    ram = next(iter(sorted(attrs.get("ram") or set())), None)
    storage = next(iter(sorted(attrs.get("storage") or set())), None)
    color = _ordered_color_label(matcher, name, attrs.get("colors") or set())
    size = _extract_size_label(matcher, name, category=attrs.get("category"))

    label_parts = []
    if ram:
        label_parts.append(_format_capacity_label(ram))
    if storage:
        label_parts.append(_format_capacity_label(storage))
    if color:
        label_parts.append(color)
    if size:
        label_parts.append(size)
    label = " / ".join(part for part in label_parts if part) or "Standard"

    prices = dict(group.get("prices") or {})
    links = dict(group.get("links") or {})
    valid_prices = [(platform, price) for platform, price in prices.items() if price is not None and price > 0]
    best_platform = None
    best_price = None
    if valid_prices:
        best_platform, best_price = min(valid_prices, key=lambda item: item[1])

    return {
        "name": name,
        "label": label,
        "ram": _format_capacity_label(ram) if ram else None,
        "storage": _format_capacity_label(storage) if storage else None,
        "color": color,
        "size": size,
        "prices": prices,
        "links": links,
        "best_price": best_price,
        "best_platform": best_platform,
    }


def _update_model_summary(model_group, variant):
    for platform, price in (variant.get("prices") or {}).items():
        existing_price = model_group["prices"].get(platform)
        if price is None or price <= 0:
            continue
        if existing_price is None or price < existing_price:
            model_group["prices"][platform] = price
            model_group["links"][platform] = (variant.get("links") or {}).get(platform)


def _group_variants_by_model(matcher, variant_groups, platforms):
    model_groups = {}

    for group in variant_groups:
        key = _extract_model_group_key(matcher, group.get("name", ""))
        if key not in model_groups:
            model_groups[key] = {
                "name": group.get("name", ""),
                "model": group.get("name", ""),
                "model_key": key,
                "prices": {platform: None for platform in platforms},
                "links": {platform: None for platform in platforms},
                "rating": 0,
                "reviews": 0,
                "image": None,
                "variants": [],
                "_members": [],
            }

        model_group = model_groups[key]
        variant = _build_variant_entry(matcher, group)
        model_group["variants"].append(variant)
        model_group["_members"].append(group)
        _update_model_summary(model_group, variant)
        model_group["rating"] = max(model_group["rating"], group.get("rating", 0))
        model_group["reviews"] = max(model_group["reviews"], group.get("reviews", 0))
        if not model_group["image"] and group.get("image"):
            model_group["image"] = group.get("image")

    finalized = []
    for group in model_groups.values():
        group["name"] = _pick_model_display_name(matcher, group["_members"])
        group["model"] = group["name"]
        group["variant_count"] = len(group["variants"])
        group["variants"].sort(
            key=lambda variant: (
                variant.get("best_price") if variant.get("best_price") is not None else 10**12,
                variant.get("label", "").lower(),
                variant.get("name", "").lower(),
            )
        )
        group.pop("_members", None)
        finalized.append(group)

    return finalized


def group_matched_products(platform_results):
    """
    Group listings by exact variant first, then fold variants into model groups.
    """
    matcher = ProductMatcher()
    combined = []
    platforms = ['amazon', 'flipkart', 'meesho', 'myntra']
    
    # Flatten all returned products
    all_products = []
    for platform in platforms:
        for p in platform_results.get(platform, []):
            if 'platform' not in p: 
                p['platform'] = platform
            all_products.append(p)
            
    matched_flags = [False] * len(all_products)
    
    for i in range(len(all_products)):
        if matched_flags[i]: 
            continue
            
        base_product = all_products[i]
        matched_flags[i] = True
        group_members = [base_product]
        
        # Create a new merged dictionary object securely
        merged = {
            "name": base_product['name'],
            "prices": {p: None for p in platforms},
            "links": {p: None for p in platforms},
            "rating": base_product.get('rating', 0),
            "reviews": base_product.get('reviews', 0),
            "image": base_product.get('image')
        }
        
        plat = base_product.get('platform')
        merged["prices"][plat] = base_product.get('price')
        merged["links"][plat] = base_product.get('link')

        # Find all other items that match the base_product
        for j in range(i + 1, len(all_products)):
            if matched_flags[j]: 
                continue
                
            candidate = all_products[j]
            can_plat = candidate.get('platform')
            
            # Avoid overwriting a platform if it already matched, unless it's genuinely cheaper
            existing_price = merged["prices"][can_plat]
            can_price = candidate.get('price')
            existing_link = _stable_product_link(merged["links"].get(can_plat))
            candidate_link = _stable_product_link(candidate.get('link'))

            # Keep same-platform variants separate unless they are the exact same listing.
            if existing_link and candidate_link and can_plat and existing_link != candidate_link:
                continue
            
            # Compare against any product already in the group (not just base item),
            # so we can bridge naming variations across platforms.
            if any(matcher.is_match(member, candidate) for member in group_members):
                matched_flags[j] = True
                group_members.append(candidate)
                
                # Use the cheapest option if multiple matches exist on the SAME platform!
                if existing_price is None or (can_price and can_price < existing_price):
                    merged["prices"][can_plat] = can_price
                    merged["links"][can_plat] = candidate.get('link')
                
                # Merge metadata attributes safely
                if not merged["image"] and candidate.get('image'):
                    merged["image"] = candidate['image']
                if candidate.get('rating', 0) > merged['rating']:
                    merged['rating'] = candidate['rating']
                if candidate.get('reviews', 0) > merged['reviews']:
                    merged['reviews'] = candidate['reviews']

        merged["name"] = _pick_representative_name(matcher, group_members)
        combined.append(merged)

    # Second pass: collapse any near-duplicate groups that still slipped through.
    final_groups = []
    for group in combined:
        synthetic_group = {"name": group.get("name", "")}
        merged_into_existing = False
        for idx, existing in enumerate(final_groups):
            synthetic_existing = {"name": existing.get("name", "")}
            overlapping_platforms = {
                platform
                for platform in platforms
                if existing.get("prices", {}).get(platform) is not None
                and group.get("prices", {}).get(platform) is not None
            }
            conflicting_overlap = False
            for platform in overlapping_platforms:
                existing_link = _stable_product_link(existing.get("links", {}).get(platform))
                group_link = _stable_product_link(group.get("links", {}).get(platform))
                if existing_link and group_link and existing_link != group_link:
                    conflicting_overlap = True
                    break
            if conflicting_overlap:
                continue
            if matcher.is_match(synthetic_existing, synthetic_group):
                final_groups[idx] = _merge_group_dicts(existing, group)
                merged_into_existing = True
                break
        if not merged_into_existing:
            final_groups.append(group)

    grouped_models = _group_variants_by_model(matcher, final_groups, platforms)

    # Prefer model groups with broader cross-platform coverage first.
    def _coverage(group):
        return sum(1 for p in group.get("prices", {}).values() if p is not None and p > 0)

    grouped_models.sort(
        key=lambda group: (
            -_coverage(group),
            -(group.get("variant_count") or 0),
            group.get("name", "").lower(),
        )
    )
    return grouped_models

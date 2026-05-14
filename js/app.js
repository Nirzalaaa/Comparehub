// ==============================
// CompareHub – Search-Only Application
// Real-time web scraping via Flask API
// ==============================

const API_BASE = 'https://comparehub-backend.onrender.com';
let apiOnline = false;

// State
let compareList = [];
let allProducts = [];       // All products from current search
let filteredProducts = [];  // After filters applied
let searchHistory = loadSearchHistory();
let wishlist = loadWishlist();
const TYPEAHEAD_DEBOUNCE_MS = 350;
const PRODUCTS_PER_PAGE = 12;
let visibleCount = PRODUCTS_PER_PAGE;
let loadMoreObserver = null;
const FALLBACK_POPULAR_PRODUCTS = [
    'iPhone 15',
    'Samsung Galaxy S24',
    'MacBook Air M3',
    'OnePlus 12',
    'Nothing Phone 2',
    'Sony WH-1000XM5',
    'Apple AirPods Pro',
    'Samsung Smart TV',
    'Nike Shoes',
    'Casio Watch'
];
const SEARCH_PLACEHOLDER_ANIMATION = [
    'Search any product...',
    'Search any product... iPhone 15',
    'Search any product... Samsung Galaxy S24',
    'Search any product... MacBook Air',
    'Search any product... Sony Headphones'
];

let suggestionItems = [];
let activeSuggestionIndex = -1;
let suggestionDebounceTimer = null;
let suggestionFetchController = null;
let activeSuggestionFetchToken = 0;
let activeNoResultsToken = 0;
let searchInProgress = false;
let searchInProgressQuery = '';
let siriWave = null;

// Category SVG icons
const CATEGORY_ICONS = {
    "All": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
    "Mobiles": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18"/></svg>',
    "Laptops": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="2" y1="20" x2="22" y2="20"/></svg>',
    "TVs": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>',
    "Audio": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>',
    "Electronics": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><circle cx="12" cy="12" r="3"/><line x1="12" y1="1" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="23"/></svg>',
    "Appliances": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="2" width="18" height="20" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><circle cx="12" cy="15" r="2"/></svg>',
    "Watches": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="7"/><polyline points="12 9 12 12 13.5 13.5"/><path d="M9 2h6"/><path d="M9 22h6"/><path d="M16.51 17.35l.35 3.83"/><path d="M7.49 17.35l-.35 3.83"/><path d="M16.51 6.65l.35-3.83"/><path d="M7.49 6.65l-.35-3.83"/></svg>',
    "Fashion": '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.38 3.46L16 2 12 5 8 2 3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/></svg>'
};

const PRODUCT_ICONS = {
    "Mobiles": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18"/></svg>',
    "Laptops": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="2" y1="20" x2="22" y2="20"/></svg>',
    "TVs": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>',
    "Audio": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>',
    "Electronics": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="4" y="4" width="16" height="16" rx="2"/><circle cx="12" cy="12" r="3"/></svg>',
    "Appliances": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="3" y="2" width="18" height="20" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><circle cx="12" cy="15" r="2"/></svg>',
    "Watches": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><circle cx="12" cy="12" r="7"/><polyline points="12 9 12 12 13.5 13.5"/></svg>',
    "Fashion": '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><path d="M20.38 3.46L16 2 12 5 8 2 3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/></svg>'
};

// ==============================
// Initialization
// ==============================
document.addEventListener('DOMContentLoaded', () => {
    checkApiStatus();
    renderCategories();
    initSearchInput();
    initPriceFilterInputs();
    showWelcomeState();
    renderRecentSearches();
    renderWishlistSection();
    initScrollEffects();
    // Animate initial cards on page load
    setTimeout(() => initScrollReveal(), 100);
    // Restore state from URL hash if present
    restoreFromUrl();
});

// ==============================
// API Status Check
// ==============================
async function checkApiStatus() {
    try {
        const resp = await fetch(API_BASE + '/', { signal: AbortSignal.timeout(3000) });
        if (resp.ok) {
            apiOnline = true;
            document.querySelector('.status-dot').className = 'status-dot online';
            document.querySelector('.status-text').textContent = 'Live';
        }
    } catch (e) {
        apiOnline = false;
        document.querySelector('.status-dot').className = 'status-dot offline';
        document.querySelector('.status-text').textContent = 'Offline';
    }
}

// ==============================
// Search Input + Suggestions
// ==============================
function initAnimatedSearchPlaceholder(inputEl) {
    if (!inputEl) return;

    let phraseIndex = 0;
    let charIndex = 0;
    let isDeleting = false;

    const step = () => {
        if (!document.body.contains(inputEl)) return;

        if (inputEl.value.trim().length > 0) {
            inputEl.setAttribute('placeholder', SEARCH_PLACEHOLDER_ANIMATION[0]);
            window.setTimeout(step, 320);
            return;
        }

        const phrase = SEARCH_PLACEHOLDER_ANIMATION[phraseIndex];
        if (!isDeleting) {
            charIndex = Math.min(phrase.length, charIndex + 1);
            inputEl.setAttribute('placeholder', phrase.slice(0, charIndex));

            if (charIndex === phrase.length) {
                isDeleting = true;
                window.setTimeout(step, 950);
                return;
            }

            window.setTimeout(step, 65);
            return;
        }

        charIndex = Math.max(0, charIndex - 1);
        inputEl.setAttribute('placeholder', phrase.slice(0, charIndex));

        if (charIndex === 0) {
            isDeleting = false;
            phraseIndex = (phraseIndex + 1) % SEARCH_PLACEHOLDER_ANIMATION.length;
            window.setTimeout(step, 220);
            return;
        }

        window.setTimeout(step, 35);
    };

    inputEl.setAttribute('placeholder', SEARCH_PLACEHOLDER_ANIMATION[0]);
    window.setTimeout(step, 350);
}

function initSearchInput() {
    const input = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const suggestionsEl = document.getElementById('searchSuggestions');
    if (!input || !searchBtn || !suggestionsEl) return;
    initAnimatedSearchPlaceholder(input);

    input.addEventListener('input', () => {
        window.clearTimeout(suggestionDebounceTimer);
        suggestionDebounceTimer = window.setTimeout(() => {
            refreshTypeaheadSuggestions(input.value.trim());
        }, TYPEAHEAD_DEBOUNCE_MS);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown') {
            if (suggestionItems.length > 0) {
                event.preventDefault();
                moveSuggestionSelection(1);
            }
            return;
        }

        if (event.key === 'ArrowUp') {
            if (suggestionItems.length > 0) {
                event.preventDefault();
                moveSuggestionSelection(-1);
            }
            return;
        }

        if (event.key === 'Enter') {
            event.preventDefault();
            if (activeSuggestionIndex >= 0 && suggestionItems[activeSuggestionIndex]) {
                selectSuggestion(activeSuggestionIndex);
                return;
            }
            handleSearch();
            return;
        }

        if (event.key === 'Escape') {
            hideTypeaheadSuggestions();
        }
    });

    input.addEventListener('focus', () => {
        refreshTypeaheadSuggestions(input.value.trim());
    });

    input.addEventListener('blur', () => {
        window.setTimeout(() => {
            hideTypeaheadSuggestions();
        }, 140);
    });

    searchBtn.addEventListener('click', () => handleSearch());

    suggestionsEl.addEventListener('mousedown', (event) => {
        event.preventDefault();
    });

    suggestionsEl.addEventListener('click', (event) => {
        const itemEl = event.target.closest('.suggestion-item');
        if (!itemEl) return;
        const index = Number(itemEl.dataset.index);
        if (Number.isNaN(index)) return;
        selectSuggestion(index);
    });
}

function initPriceFilterInputs() {
    const minInput = document.getElementById('filterMinPrice');
    const maxInput = document.getElementById('filterMaxPrice');
    if (!minInput || !maxInput) return;

    const commitPriceFilters = () => {
        sanitizePriceFilterInputs({ commit: true });
        applyFilters();
    };

    minInput.addEventListener('blur', commitPriceFilters);
    maxInput.addEventListener('blur', commitPriceFilters);
}

async function refreshTypeaheadSuggestions(query) {
    const normalizedQuery = query.trim();
    const localSuggestions = buildLocalTypeaheadSuggestions(normalizedQuery);
    renderTypeaheadSuggestions(localSuggestions, normalizedQuery);

    if (!normalizedQuery) return;

    const token = ++activeSuggestionFetchToken;
    if (suggestionFetchController) suggestionFetchController.abort();
    suggestionFetchController = new AbortController();

    try {
        const resp = await fetch(
            `${API_BASE}/api/suggestions?q=${encodeURIComponent(normalizedQuery)}&limit=12`,
            { signal: suggestionFetchController.signal, cache: 'no-store' }
        );
        if (!resp.ok) return;

        const data = await resp.json();
        if (token !== activeSuggestionFetchToken) return;

        const liveInputValue = document.getElementById('searchInput')?.value.trim() || '';
        if (normalizeText(liveInputValue) !== normalizeText(normalizedQuery)) return;

        const apiSuggestions = (data.suggestions || []).map(item => ({
            text: typeof item === 'string' ? item : (item.text || ''),
            type: typeof item === 'string' ? 'popular' : (item.type || 'popular')
        })).filter(item => item.text);

        const merged = mergeSuggestionLists(localSuggestions, apiSuggestions, 12);
        renderTypeaheadSuggestions(merged, normalizedQuery);
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.debug('Suggestion API error:', error);
        }
    }
}

function buildLocalTypeaheadSuggestions(query) {
    const historyMatches = rankCandidates(query, searchHistory, 4, 20);
    const popularMatches = rankCandidates(query, FALLBACK_POPULAR_PRODUCTS, 4, 20);
    const productNameMatches = rankCandidates(query, allProducts.map(p => p.name), 6, 24);

    const local = [
        ...historyMatches.map(text => ({ text, type: 'history' })),
        ...popularMatches.map(text => ({ text, type: 'popular' })),
        ...productNameMatches.map(text => ({ text, type: 'product' }))
    ];

    return mergeSuggestionLists(local, [], 10);
}

function mergeSuggestionLists(primary, secondary, limit) {
    const merged = [];
    const seen = new Set();

    const consume = (list) => {
        for (const item of list) {
            if (merged.length >= limit) break;
            const text = (item?.text || '').trim();
            if (!text) continue;
            const key = text.toLowerCase();
            if (seen.has(key)) continue;
            seen.add(key);
            merged.push({
                text,
                type: item.type || 'popular'
            });
        }
    };

    consume(primary);
    consume(secondary);
    return merged;
}

function renderTypeaheadSuggestions(items, query) {
    const suggestionsEl = document.getElementById('searchSuggestions');
    if (!suggestionsEl) return;

    suggestionItems = items;
    activeSuggestionIndex = -1;

    if (!items || items.length === 0) {
        hideTypeaheadSuggestions();
        return;
    }

    suggestionsEl.innerHTML = items.map((item, index) => `
      <div class="suggestion-item" role="option" aria-selected="false" data-index="${index}">
        <span class="suggestion-text">${highlightMatch(item.text, query)}</span>
        <span class="suggestion-type">${getSuggestionTypeLabel(item.type)}</span>
      </div>
    `).join('');

    suggestionsEl.hidden = false;
}

function hideTypeaheadSuggestions() {
    const suggestionsEl = document.getElementById('searchSuggestions');
    if (!suggestionsEl) return;
    suggestionsEl.hidden = true;
    suggestionItems = [];
    activeSuggestionIndex = -1;
}

function moveSuggestionSelection(direction) {
    if (!suggestionItems.length) return;

    if (activeSuggestionIndex === -1) {
        activeSuggestionIndex = direction > 0 ? 0 : suggestionItems.length - 1;
    } else {
        activeSuggestionIndex = (activeSuggestionIndex + direction + suggestionItems.length) % suggestionItems.length;
    }

    const suggestionsEl = document.getElementById('searchSuggestions');
    const suggestionRows = suggestionsEl?.querySelectorAll('.suggestion-item') || [];
    suggestionRows.forEach((row, idx) => {
        const isActive = idx === activeSuggestionIndex;
        row.classList.toggle('active', isActive);
        row.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    const activeRow = suggestionRows[activeSuggestionIndex];
    if (activeRow) {
        activeRow.scrollIntoView({ block: 'nearest' });
    }
}

function selectSuggestion(index) {
    const item = suggestionItems[index];
    if (!item) return;
    document.getElementById('searchInput').value = item.text;
    hideTypeaheadSuggestions();
    handleSearch(item.text);
}

function getSuggestionTypeLabel(type) {
    if (type === 'history') return 'Recent';
    if (type === 'product') return 'Product';
    return 'Popular';
}

function rankCandidates(query, candidates, limit = 8, minScore = 20) {
    const uniqueCandidates = dedupeTexts(candidates).slice(0, 300);
    if (!query) return uniqueCandidates.slice(0, limit);

    return uniqueCandidates
        .map(candidate => ({
            text: candidate,
            score: scoreCandidate(query, candidate)
        }))
        .filter(item => item.score >= minScore)
        .sort((a, b) => b.score - a.score)
        .slice(0, limit)
        .map(item => item.text);
}

function scoreCandidate(query, candidate) {
    const q = normalizeText(query);
    const c = normalizeText(candidate);
    if (!q || !c) return 0;

    let score = 0;
    if (c.includes(q)) {
        score += 70;
        if (c.startsWith(q)) score += 18;
    }

    const qTokens = q.split(' ').filter(Boolean);
    const cTokens = new Set(c.split(' ').filter(Boolean));
    let overlap = 0;
    qTokens.forEach(token => {
        if (cTokens.has(token)) overlap += 1;
    });
    score += overlap * 20;

    const maxPrefixLength = Math.min(q.length, c.length, 20);
    let prefix = 0;
    while (prefix < maxPrefixLength && q[prefix] === c[prefix]) prefix += 1;
    score += prefix * 1.8;

    return score;
}

function dedupeTexts(items) {
    const seen = new Set();
    const output = [];
    (items || []).forEach(item => {
        const text = (item || '').toString().trim();
        if (!text) return;
        const key = text.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        output.push(text);
    });
    return output;
}

function normalizeText(value) {
    return canonicalizeText(value)
        .replace(/[^a-z0-9]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function canonicalizeText(value) {
    return (value || '')
        .toLowerCase()
        .replace(/\+/g, ' plus ')
        .replace(/\bi[\s-]*phone\b/g, 'iphone')
        .replace(/\bone[\s-]*plus\b/g, 'oneplus')
        .replace(/\bair[\s-]*pods?\b/g, 'airpods')
        .replace(/\bmac[\s-]*book\b/g, 'macbook')
        .replace(/\bplay[\s-]*station\b/g, 'playstation')
        .replace(/\bfire[\s-]*boltt\b/g, 'fireboltt')
        .replace(/\bg[\s-]*shock\b/g, 'gshock');
}

function loadSearchHistory() {
    try {
        const raw = localStorage.getItem('comparehub_search_history');
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed)
            ? parsed.filter(item => typeof item === 'string' && item.trim().length > 0)
            : [];
    } catch (error) {
        console.warn('Search history load skipped', error);
        return [];
    }
}

function highlightMatch(text, query) {
    const label = (text || '').toString();
    const q = query.trim();
    if (!q) return escapeHtml(label);

    const pattern = new RegExp(`(${escapeRegExp(q)})`, 'ig');
    return label
        .split(pattern)
        .map(part => part.toLowerCase() === q.toLowerCase()
            ? `<mark>${escapeHtml(part)}</mark>`
            : escapeHtml(part))
        .join('');
}

function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function escapeHtml(value) {
    return (value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizePriceValue(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number') {
        return Number.isFinite(value) && value > 0 ? Math.round(value) : null;
    }
    if (typeof value === 'string') {
        const digits = value.replace(/[^0-9.]/g, '');
        if (!digits) return null;
        const parsed = Number(digits);
        return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed) : null;
    }
    return null;
}

function normalizeRatingValue(value) {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed) || parsed <= 0) return 0;
    return Math.max(0, Math.min(5, Math.round(parsed * 10) / 10));
}

function normalizeCountValue(value) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function normalizePlatformName(value) {
    const platform = (value || '').toString().trim().toLowerCase();
    return ['amazon', 'flipkart', 'meesho', 'myntra'].includes(platform) ? platform : null;
}

function createEmptyPriceMap() {
    return { amazon: null, flipkart: null, meesho: null, myntra: null };
}

function createEmptyLinkMap() {
    return { amazon: null, flipkart: null, meesho: null, myntra: null };
}

function normalizeVariantEntry(item, fallbackName = '') {
    if (!item || typeof item !== 'object') return null;

    const name = (item.name || fallbackName || '').toString().trim();
    const prices = createEmptyPriceMap();
    const links = createEmptyLinkMap();
    const sourcePrices = item.prices && typeof item.prices === 'object' ? item.prices : {};
    const sourceLinks = item.links && typeof item.links === 'object' ? item.links : {};

    Object.keys(prices).forEach(platform => {
        prices[platform] = normalizePriceValue(sourcePrices[platform]);
        links[platform] = sourceLinks[platform] || null;
    });

    let bestPlatform = normalizePlatformName(item.best_platform || item.bestPlatform);
    let bestPrice = normalizePriceValue(item.best_price ?? item.bestPrice);
    if (!bestPlatform || !bestPrice) {
        const validOffers = Object.entries(prices).filter(([, price]) => price !== null && price !== undefined && price > 0);
        if (validOffers.length > 0) {
            const [platform, price] = validOffers.sort((a, b) => a[1] - b[1])[0];
            bestPlatform = bestPlatform || platform;
            bestPrice = bestPrice || price;
        }
    }

    return {
        name,
        label: (item.label || '').toString().trim() || 'Standard',
        ram: item.ram ? item.ram.toString().trim() : null,
        storage: item.storage ? item.storage.toString().trim() : null,
        color: item.color ? item.color.toString().trim() : null,
        size: item.size ? item.size.toString().trim() : null,
        prices,
        links,
        bestPlatform,
        bestPrice,
    };
}

function normalizeApiProduct(item, fallbackPlatform = null) {
    if (!item || typeof item !== 'object') return null;

    const name = (item.name || item.title || item.product_name || '').toString().trim();
    if (!name) return null;

    const category = item.category || detectCategory(name);
    const prices = createEmptyPriceMap();
    const links = createEmptyLinkMap();
    const sourcePrices = item.prices && typeof item.prices === 'object' ? item.prices : {};
    const sourceLinks = item.links && typeof item.links === 'object' ? item.links : {};

    Object.keys(prices).forEach(platform => {
        prices[platform] = normalizePriceValue(sourcePrices[platform]);
        if (sourceLinks[platform]) {
            links[platform] = sourceLinks[platform];
        }
    });

    const hintedPlatform = normalizePlatformName(item.platform || fallbackPlatform);
    const hintedPrice = normalizePriceValue(item.price);
    if (hintedPlatform && hintedPrice) {
        prices[hintedPlatform] = hintedPrice;
    }
    if (hintedPlatform && item.link && !links[hintedPlatform]) {
        links[hintedPlatform] = item.link;
    }

    const variants = Array.isArray(item.variants)
        ? item.variants.map(variant => normalizeVariantEntry(variant, name)).filter(Boolean)
        : [];

    const normalized = {
        name,
        model: (item.model || name).toString().trim() || name,
        modelKey: item.model_key || null,
        category,
        image: item.image || null,
        rating: normalizeRatingValue(item.rating),
        reviews: normalizeCountValue(item.reviews),
        features: Array.isArray(item.features) ? item.features : [],
        prices,
        links,
        variants,
        variantCount: Number.isFinite(Number(item.variant_count)) ? Number(item.variant_count) : variants.length,
        source: item.source || null,
        confidence: Number.isFinite(Number(item.confidence)) ? Number(item.confidence) : null,
    };

    if (hintedPlatform) {
        normalized.platform = hintedPlatform;
        if (hintedPrice && !normalized.prices[hintedPlatform]) {
            normalized.prices[hintedPlatform] = hintedPrice;
        }
    }

    const rawPrice = normalizePriceValue(item.price);
    if (rawPrice && !Object.values(normalized.prices).some(price => price)) {
        normalized.price = rawPrice;
    }

    if (!normalized.image && item.thumbnail) {
        normalized.image = item.thumbnail;
    }

    return normalized;
}

function normalizeApiProducts(data) {
    if (!data || typeof data !== 'object') return [];

    if (Array.isArray(data.products) && data.products.length > 0) {
        return data.products.map(item => normalizeApiProduct(item)).filter(Boolean);
    }

    const platformBuckets = data.platforms && typeof data.platforms === 'object' ? data.platforms : null;
    if (!platformBuckets) return [];

    const grouped = new Map();

    Object.entries(platformBuckets).forEach(([platformKey, rows]) => {
        if (!Array.isArray(rows)) return;
        const fallbackPlatform = normalizePlatformName(platformKey);

        rows.forEach(row => {
            const normalizedRow = normalizeApiProduct(row, fallbackPlatform);
            if (!normalizedRow) return;

            const key = normalizeText(normalizedRow.name) || normalizeText(row.name);
            if (!key) return;

            if (!grouped.has(key)) {
                grouped.set(key, normalizedRow);
                return;
            }

            const existing = grouped.get(key);
            if (normalizedRow.name.length > existing.name.length) {
                existing.name = normalizedRow.name;
            }
            if (!existing.category && normalizedRow.category) {
                existing.category = normalizedRow.category;
            }
            if (!existing.image && normalizedRow.image) {
                existing.image = normalizedRow.image;
            }
            existing.rating = Math.max(existing.rating || 0, normalizedRow.rating || 0);
            existing.reviews = Math.max(existing.reviews || 0, normalizedRow.reviews || 0);
            if (normalizedRow.confidence != null) {
                existing.confidence = Math.max(existing.confidence || 0, normalizedRow.confidence);
            }
            Object.keys(existing.prices || {}).forEach(platform => {
                if (!existing.prices[platform] && normalizedRow.prices?.[platform]) {
                    existing.prices[platform] = normalizedRow.prices[platform];
                }
                if (!existing.links[platform] && normalizedRow.links?.[platform]) {
                    existing.links[platform] = normalizedRow.links[platform];
                }
            });
            if (!existing.price && normalizedRow.price) {
                existing.price = normalizedRow.price;
            }
        });
    });

    return Array.from(grouped.values());
}

function getNormalizedPriceMap(product) {
    const prices = createEmptyPriceMap();
    if (!product || typeof product !== 'object') return prices;

    const sourcePrices = product.prices && typeof product.prices === 'object' ? product.prices : {};
    Object.keys(prices).forEach(platform => {
        prices[platform] = normalizePriceValue(sourcePrices[platform]);
    });

    const fallbackPlatform = normalizePlatformName(product.platform);
    const fallbackPrice = normalizePriceValue(product.price);
    if (fallbackPlatform && fallbackPrice && !prices[fallbackPlatform]) {
        prices[fallbackPlatform] = fallbackPrice;
    }

    return prices;
}

function getNormalizedLinkMap(product) {
    const links = createEmptyLinkMap();
    if (!product || typeof product !== 'object') return links;

    const sourceLinks = product.links && typeof product.links === 'object' ? product.links : {};
    Object.keys(links).forEach(platform => {
        links[platform] = sourceLinks[platform] || null;
    });

    const fallbackPlatform = normalizePlatformName(product.platform);
    if (fallbackPlatform && product.link && !links[fallbackPlatform]) {
        links[fallbackPlatform] = product.link;
    }

    return links;
}

function getNormalizedVariantList(product) {
    if (!product || typeof product !== 'object') return [];

    if (Array.isArray(product.variants) && product.variants.length > 0) {
        return product.variants.map(variant => normalizeVariantEntry(variant, product.model || product.name || '')).filter(Boolean);
    }

    const prices = getNormalizedPriceMap(product);
    const links = getNormalizedLinkMap(product);
    const hasAnyOffer = Object.values(prices).some(price => price !== null && price !== undefined && price > 0);
    if (!hasAnyOffer) return [];

    return [{
        name: product.model || product.name || '',
        label: 'Standard',
        ram: null,
        storage: null,
        color: null,
        size: null,
        prices,
        links,
        bestPrice: getLowestPrice(product),
        bestPlatform: getLowestPlatform(product),
    }];
}

function hasMultipleVariants(product) {
    return getNormalizedVariantList(product).length > 1;
}

function getActiveVariantIndex(product) {
    const variants = getNormalizedVariantList(product);
    if (!variants.length) return -1;
    if (variants.length === 1) return 0;

    const rawIndex = Number.isInteger(product?.selectedVariantIndex) ? product.selectedVariantIndex : -1;
    if (rawIndex < 0 || rawIndex >= variants.length) return -1;
    return rawIndex;
}

function getActiveVariant(product) {
    const variants = getNormalizedVariantList(product);
    if (!variants.length) return null;
    const activeIndex = getActiveVariantIndex(product);
    if (activeIndex < 0) return null;
    return variants[activeIndex] || null;
}

function isFamilySummaryMode(product) {
    return hasMultipleVariants(product) && getActiveVariantIndex(product) === -1;
}

function getVariantPlatformSummary(product) {
    const summary = {};
    const platforms = Object.keys(createEmptyPriceMap());
    const variants = getNormalizedVariantList(product);

    platforms.forEach(platform => {
        summary[platform] = { min: null, max: null, count: 0 };
    });

    variants.forEach(variant => {
        platforms.forEach(platform => {
            const price = normalizePriceValue(variant?.prices?.[platform]);
            if (!price) return;

            const current = summary[platform];
            current.min = current.min === null ? price : Math.min(current.min, price);
            current.max = current.max === null ? price : Math.max(current.max, price);
            current.count += 1;
        });
    });

    return summary;
}

function formatPlatformSummaryLabel(summary) {
    if (!summary || !summary.count || summary.min === null) return 'N/A';
    if (summary.min === summary.max) return `From ${formatPrice(summary.min)}`;
    return `${formatPrice(summary.min)} - ${formatPrice(summary.max)}`;
}

function getPlatformDisplayMap(product) {
    const display = {};
    const platforms = Object.keys(createEmptyPriceMap());

    if (isFamilySummaryMode(product)) {
        const summaries = getVariantPlatformSummary(product);
        platforms.forEach(platform => {
            const summary = summaries[platform];
            display[platform] = {
                value: summary.min,
                label: formatPlatformSummaryLabel(summary),
                link: null,
                isSummary: true,
                min: summary.min,
                max: summary.max,
                count: summary.count,
            };
        });
        return display;
    }

    const prices = getDisplayPriceMap(product);
    const links = getDisplayLinkMap(product);
    platforms.forEach(platform => {
        const price = normalizePriceValue(prices[platform]);
        display[platform] = {
            value: price,
            label: price ? formatPrice(price) : 'N/A',
            link: price && links[platform] ? links[platform] : null,
            isSummary: false,
            min: price,
            max: price,
            count: price ? 1 : 0,
        };
    });

    return display;
}

function getDisplayPriceMap(product) {
    const variant = getActiveVariant(product);
    return variant?.prices || getNormalizedPriceMap(product);
}

function getDisplayLinkMap(product) {
    const variant = getActiveVariant(product);
    return variant?.links || getNormalizedLinkMap(product);
}

function getDisplayLowestPrice(product) {
    const prices = Object.values(getDisplayPriceMap(product)).filter(p => p !== null && p !== undefined && p > 0);
    return prices.length > 0 ? Math.min(...prices) : 0;
}

function getDisplayHighestPrice(product) {
    const prices = Object.values(getDisplayPriceMap(product)).filter(p => p !== null && p !== undefined && p > 0);
    return prices.length > 0 ? Math.max(...prices) : 0;
}

function getDisplayLowestPlatform(product) {
    const min = getDisplayLowestPrice(product);
    const prices = getDisplayPriceMap(product);
    return Object.keys(prices).find(k => prices[k] === min);
}

function getDisplayHighestPlatform(product) {
    const max = getDisplayHighestPrice(product);
    const prices = getDisplayPriceMap(product);
    return Object.keys(prices).find(k => prices[k] === max);
}

// ==============================
// Welcome State (no search yet)
// ==============================
function showWelcomeState() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;
    grid.innerHTML = `
    <div class="empty-state" style="grid-column: 1/-1">
      <div class="empty-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" stroke-width="1.5">
      <div class="empty-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <h3 style="margin-bottom:8px;color:var(--text-primary)">Search for any product</h3>
      <p>Type a product name above to compare live prices from Amazon, Flipkart, Meesho & Myntra</p>
      <div class="product-actions" style="justify-content:center;flex-wrap:wrap">
        <button class="quick-search-btn" onclick="quickSearch('iPhone 15')">iPhone 15</button>
        <button class="quick-search-btn" onclick="quickSearch('Samsung Galaxy S24')">Galaxy S24</button>
        <button class="quick-search-btn" onclick="quickSearch('MacBook Air')">MacBook Air</button>
        <button class="quick-search-btn" onclick="quickSearch('Sony Headphones')">Sony Headphones</button>
        <button class="quick-search-btn" onclick="quickSearch('Samsung TV')">Samsung TV</button>
      </div>
    </div>
  `;
    document.getElementById('resultsCount').textContent = '';
    document.getElementById('dataSource').textContent = '';
    document.getElementById('dataSource').className = 'data-source';
}

function quickSearch(query) {
    document.getElementById('searchInput').value = query;
    hideTypeaheadSuggestions();
    handleSearch(query);
}

function quickSearchFromEncoded(encodedQuery) {
    try {
        const decoded = decodeURIComponent(encodedQuery || '');
        if (!decoded) return;
        quickSearch(decoded);
    } catch (error) {
        console.warn('Invalid quick search value', error);
    }
}

// ==============================
// Categories (acts as quick search)
// ==============================
function renderCategories() {
    const grid = document.getElementById('categoriesGrid');
    grid.innerHTML = CATEGORIES.map(cat => `
    <div class="category-card ${cat === 'All' ? 'active' : ''}" onclick="searchCategory('${cat}')" data-category="${cat}">
      <div class="category-icon">${CATEGORY_ICONS[cat] || CATEGORY_ICONS['All']}</div>
      <div class="category-name">${cat}</div>
    </div>
  `).join('');
}

function searchCategory(category) {
    document.querySelectorAll('.category-card').forEach(c => c.classList.remove('active'));
    const el = document.querySelector(`.category-card[data-category="${category}"]`);
    if (el) el.classList.add('active');

    if (category === 'All') {
        if (allProducts.length > 0) {
            applyFilters();
        }
        return;
    }

    // If we already have products, filter locally
    if (allProducts.length > 0) {
        document.getElementById('filterCategory').value = category;
        applyFilters();
        document.getElementById('products-section').scrollIntoView({ behavior: 'smooth' });
        return;
    }

    // Otherwise, search for the category
    document.getElementById('searchInput').value = category;
    handleSearch();
}

// ==============================
// Recent Searches
// ==============================
function renderRecentSearches() {
    const grid = document.getElementById('trendingGrid');
    if (!grid) return;
    if (searchHistory.length === 0) {
        grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;padding:20px">
        <p style="color:var(--text-muted);font-size:0.85rem">Your recent searches will appear here</p>
      </div>`;
        return;
    }
    grid.innerHTML = searchHistory.slice(0, 8).map((q, i) => {
        const encodedQuery = encodeURIComponent(q);
        return `
    <div class="trending-card" onclick="quickSearchFromEncoded('${encodedQuery}')">
      <span class="trending-rank">#${i + 1}</span>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" style="flex-shrink:0"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <div class="trending-info">
        <h4>${escapeHtml(q)}</h4>
        <p>Search again</p>
      </div>
    </div>
  `;
    }).join('');
    // Reveal new trending cards
    initScrollReveal();
}

// ==============================
// Search (Live API only)
// ==============================
function setSearchUiBusy(isBusy) {
    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');
    if (searchBtn) {
        searchBtn.disabled = isBusy;
        searchBtn.style.opacity = isBusy ? '0.7' : '';
        searchBtn.style.cursor = isBusy ? 'not-allowed' : '';
    }
    if (searchInput) {
        searchInput.setAttribute('aria-busy', isBusy ? 'true' : 'false');
    }
}

// Modern search flow with no-results UX and explicit query support.
async function handleSearch(forcedQuery = null) {
    const inputEl = document.getElementById('searchInput');
    const query = (forcedQuery !== null ? forcedQuery : inputEl.value).trim();
    inputEl.value = query;
    hideTypeaheadSuggestions();

    if (!query) {
        allProducts = [];
        filteredProducts = [];
        showWelcomeState();
        return;
    }

    if (searchInProgress) {
        if (searchInProgressQuery === query) {
            showToast('Search already running for this query...');
        } else {
            showToast('Please wait for the current search to finish.');
        }
        return;
    }

    searchInProgress = true;
    searchInProgressQuery = query;
    setSearchUiBusy(true);

    try {
        saveSearchHistory(query);
        renderRecentSearches();
    } catch (error) {
        console.warn('Search history UI update skipped', error);
    }

    showProgressLoading();
    const resultsCountEl = document.getElementById('resultsCount');
    if (resultsCountEl) {
        resultsCountEl.textContent = 'Scraping live data from selected platforms...';
    }
    const noResultsToken = ++activeNoResultsToken;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000);

        const resp = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`, {
            signal: controller.signal,
            cache: 'no-store'
        });
        clearTimeout(timeoutId);
        const data = await resp.json();

        apiOnline = true;
        document.querySelector('.status-dot').className = 'status-dot online';
        document.querySelector('.status-text').textContent = 'Live';

        document.getElementById('loadingIndicator').style.display = 'none';
        clearProgressTimers();
        document.getElementById('productsGrid').innerHTML = '';

        const normalizedProducts = normalizeApiProducts(data);
        if (normalizedProducts.length > 0) {
            allProducts = normalizedProducts.map((p, i) => {
                const variants = getNormalizedVariantList(p);
                return {
                    id: 1000 + i,
                    name: p.model || p.name,
                    model: p.model || p.name,
                    modelKey: p.modelKey || null,
                    category: p.category || detectCategory(p.name),
                    image: p.image || null,
                    rating: p.rating || 0,
                    reviews: p.reviews || 0,
                    features: Array.isArray(p.features) ? p.features : [],
                    prices: getNormalizedPriceMap(p),
                    links: getNormalizedLinkMap(p),
                    variants,
                    selectedVariantIndex: variants.length > 1 ? -1 : (variants.length === 1 ? 0 : -1),
                    showAllVariants: false,
                    variantCount: p.variantCount || variants.length,
                    source: data.source,
                    confidence: p.confidence || 0,
                };
            });

            const srcEl = document.getElementById('dataSource');
            srcEl.textContent = data.source === 'cache' ? 'CACHE RESULT' : 'LIVE SCRAPING';
            srcEl.className = `data-source ${data.source === 'cache' ? 'mock' : 'live'}`;

            document.getElementById('statProducts').textContent = allProducts.length;

            document.getElementById('filterCategory').value = 'All';
            document.getElementById('filterMinPrice').value = '0';
            document.getElementById('filterMaxPrice').value = '';
            document.getElementById('filterRating').value = '0';
            document.getElementById('sortSelect').value = 'relevance';

            visibleCount = PRODUCTS_PER_PAGE;
            applyFilters();
            document.getElementById('products-section').scrollIntoView({ behavior: 'smooth' });
            return;
        }

        allProducts = [];
        filteredProducts = [];
        document.getElementById('statProducts').textContent = '0';
        document.getElementById('resultsCount').textContent = '0 results';
        const srcEl = document.getElementById('dataSource');
        srcEl.textContent = '';
        srcEl.className = 'data-source';
        await showNoResultsState(query, noResultsToken);
    } catch (e) {
        document.getElementById('loadingIndicator').style.display = 'none';
        document.getElementById('productsGrid').innerHTML = '';
        console.error('Search error:', e);

        if (e.name === 'AbortError') {
            showToast('Search timed out. The scraping is taking too long. Try again.');
        } else {
            apiOnline = false;
            document.querySelector('.status-dot').className = 'status-dot offline';
            document.querySelector('.status-text').textContent = 'Offline';
            showToast('Backend server is offline. Start it with: python backend/app.py');
        }
        showWelcomeState();
    } finally {
        searchInProgress = false;
        searchInProgressQuery = '';
        setSearchUiBusy(false);
        clearProgressTimers();
    }
}

function detectCategory(name) {
    const n = name.toLowerCase();
    if (n.includes('watch') || n.includes('smartwatch') || n.includes('titan') || n.includes('fastrack') || n.includes('casio') || n.includes('g-shock') || n.includes('fire-boltt') || n.includes('noise') || n.includes('boat storm')) return 'Watches';
    if (n.includes('phone') || n.includes('mobile') || n.includes('galaxy') || n.includes('iphone') || n.includes('redmi') || n.includes('oneplus') || n.includes('pixel') || n.includes('realme') || n.includes('nothing') || n.includes('vivo') || n.includes('oppo') || n.includes('poco')) return 'Mobiles';
    if (n.includes('laptop') || n.includes('macbook') || n.includes('notebook') || n.includes('ideapad') || n.includes('rog') || n.includes('pavilion') || n.includes('xps') || n.includes('thinkpad')) return 'Laptops';
    if (n.includes('tv') || n.includes('television') || n.includes('bravia') || n.includes('qled') || n.includes('oled') || n.includes('smart tv')) return 'TVs';
    if (n.includes('headphone') || n.includes('earbuds') || n.includes('speaker') || n.includes('airpods') || n.includes('audio') || n.includes('soundbar') || n.includes('earphone')) return 'Audio';
    if (n.includes('washing') || n.includes('fridge') || n.includes('refrigerator') || n.includes('ac ') || n.includes('vacuum') || n.includes('geyser') || n.includes('microwave') || n.includes('purifier')) return 'Appliances';
    if (n.includes('shoe') || n.includes('jeans') || n.includes('shirt') || n.includes('dress') || n.includes('nike') || n.includes('adidas') || n.includes('levis') || n.includes('puma') || n.includes('kurta') || n.includes('saree')) return 'Fashion';
    return 'Electronics';
}

function saveSearchHistory(query) {
    const cleaned = (query || '').trim();
    if (!cleaned) return;
    const key = cleaned.toLowerCase();
    searchHistory = searchHistory.filter(s => (s || '').toLowerCase() !== key);
    searchHistory.unshift(cleaned);
    if (searchHistory.length > 15) searchHistory.pop();
    try {
        localStorage.setItem('comparehub_search_history', JSON.stringify(searchHistory));
    } catch (error) {
        console.warn('Search history save skipped', error);
    }
}

async function showNoResultsState(query, token) {
    const localAlternatives = buildLocalNoResultAlternatives(query);
    renderNoResultsState(query, localAlternatives);
    document.getElementById('products-section').scrollIntoView({ behavior: 'smooth' });

    try {
        const resp = await fetch(`${API_BASE}/api/suggestions?q=${encodeURIComponent(query)}&limit=12`, {
            cache: 'no-store',
            signal: AbortSignal.timeout(4500)
        });
        if (!resp.ok) return;

        if (token !== activeNoResultsToken) return;
        const data = await resp.json();
        if (token !== activeNoResultsToken) return;

        const mergedAlternatives = mergeNoResultAlternatives(localAlternatives, data, query);
        renderNoResultsState(query, mergedAlternatives);
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.debug('No-result suggestion fallback:', error);
        }
    }
}

function buildLocalNoResultAlternatives(query) {
    const didYouMean = rankCandidates(query, [...searchHistory, ...FALLBACK_POPULAR_PRODUCTS], 3, 26)
        .filter(item => normalizeText(item) !== normalizeText(query))
        .slice(0, 3);

    const relatedProducts = rankCandidates(query, [...allProducts.map(p => p.name), ...FALLBACK_POPULAR_PRODUCTS], 6, 20);
    const trending = dedupeTexts([...searchHistory, ...FALLBACK_POPULAR_PRODUCTS]).slice(0, 8);

    return {
        didYouMean,
        relatedProducts: relatedProducts.length > 0 ? relatedProducts : FALLBACK_POPULAR_PRODUCTS.slice(0, 6),
        trending
    };
}

function mergeNoResultAlternatives(localAlternatives, apiData, query) {
    const didYouMean = dedupeTexts([
        ...(apiData?.did_you_mean || []),
        ...(localAlternatives.didYouMean || [])
    ])
        .filter(item => normalizeText(item) !== normalizeText(query))
        .slice(0, 3);

    const relatedProducts = dedupeTexts([
        ...(apiData?.related_products || []),
        ...(localAlternatives.relatedProducts || [])
    ]).slice(0, 6);

    const trending = dedupeTexts([
        ...(apiData?.trending || []),
        ...(localAlternatives.trending || []),
        ...FALLBACK_POPULAR_PRODUCTS
    ]).slice(0, 8);

    return {
        didYouMean,
        relatedProducts: relatedProducts.length > 0 ? relatedProducts : FALLBACK_POPULAR_PRODUCTS.slice(0, 6),
        trending
    };
}

function renderNoResultsState(query, alternatives) {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;
    const safeQuery = escapeHtml(query);

    grid.innerHTML = `
      <div class="empty-state rich-empty-state" style="grid-column:1/-1">
        <div class="empty-icon">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.6">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </div>
        <h3 class="empty-title">No results found</h3>
        <p class="empty-subtitle">We could not find products for "<strong>${safeQuery}</strong>". Try these alternatives.</p>

        <div class="empty-actions">
          <button class="search-again-btn" onclick="searchAgain()">Search again</button>
        </div>

        <div class="empty-alt-grid">
          <div class="empty-alt-card">
            <h4>Did you mean...</h4>
            <div class="empty-chip-list">
              ${buildAlternativeButtons(alternatives.didYouMean, 'empty-chip did-you-mean-chip')}
            </div>
          </div>

          <div class="empty-alt-card">
            <h4>Related products</h4>
            <div class="empty-chip-list">
              ${buildAlternativeButtons(alternatives.relatedProducts, 'empty-chip related-chip')}
            </div>
          </div>

          <div class="empty-alt-card">
            <h4>Trending searches</h4>
            <div class="empty-chip-list">
              ${buildAlternativeButtons(alternatives.trending, 'empty-chip trending-chip')}
            </div>
          </div>
        </div>
      </div>
    `;
}

function buildAlternativeButtons(items, className) {
    if (!items || items.length === 0) {
        return '<span class="empty-placeholder">Try another keyword</span>';
    }

    return items.map(item => {
        const text = escapeHtml(item);
        const encoded = encodeURIComponent(item);
        return `<button class="${className}" onclick="quickSearchFromEncoded('${encoded}')">${text}</button>`;
    }).join('');
}

function searchAgain() {
    const input = document.getElementById('searchInput');
    input.focus();
    input.select();
    document.getElementById('hero').scrollIntoView({ behavior: 'smooth', block: 'center' });
    refreshTypeaheadSuggestions(input.value.trim());
}

// ==============================
// Filters & Sort
// ==============================
function sanitizePriceFilterInputs(options = {}) {
    const { commit = false } = options;
    const minInput = document.getElementById('filterMinPrice');
    const maxInput = document.getElementById('filterMaxPrice');
    if (!minInput || !maxInput) {
        return { minPrice: 0, maxPrice: Infinity };
    }

    const rawMin = minInput.value.trim();
    const rawMax = maxInput.value.trim();

    let minPrice = Number.parseInt(rawMin, 10);
    let maxPrice = Number.parseInt(rawMax, 10);

    if (!Number.isFinite(minPrice) || minPrice < 0) {
        minPrice = 0;
    }

    if (commit && (rawMin === '' || minInput.value !== String(minPrice))) {
        minInput.value = String(minPrice);
    }

    if (!rawMax) {
        if (commit) {
            maxInput.value = '';
        }
        return { minPrice, maxPrice: Infinity };
    }

    if (!Number.isFinite(maxPrice) || maxPrice < 0) {
        maxPrice = 0;
    }

    if (commit && maxPrice < minPrice) {
        maxPrice = minPrice;
    }

    if (commit && maxInput.value !== String(maxPrice)) {
        maxInput.value = String(maxPrice);
    }

    return { minPrice, maxPrice };
}

function applyFilters() {
    if (allProducts.length === 0) return;

    const category = document.getElementById('filterCategory').value;
    const { minPrice, maxPrice } = sanitizePriceFilterInputs();
    const minRating = parseFloat(document.getElementById('filterRating').value) || 0;
    const sortBy = document.getElementById('sortSelect').value;

    filteredProducts = allProducts.filter(p => {
        const lowestPrice = getLowestPrice(p);
        const matchesCategory = category === 'All' || p.category === category;
        const matchesPrice = lowestPrice >= minPrice && (maxPrice === Infinity || lowestPrice <= maxPrice);
        const matchesRating = p.rating >= minRating;
        return matchesCategory && matchesPrice && matchesRating;
    });

    switch (sortBy) {
        case 'price-low': filteredProducts.sort((a, b) => getLowestPrice(a) - getLowestPrice(b)); break;
        case 'price-high': filteredProducts.sort((a, b) => getLowestPrice(b) - getLowestPrice(a)); break;
        case 'rating': filteredProducts.sort((a, b) => (b.rating || 0) - (a.rating || 0)); break;
        case 'reviews': filteredProducts.sort((a, b) => (b.reviews || 0) - (a.reviews || 0)); break;
    }

    visibleCount = PRODUCTS_PER_PAGE;
    renderProducts();
}

// ==============================
// Price Utilities
// ==============================
function getLowestPrice(product) {
    const prices = Object.values(getNormalizedPriceMap(product)).filter(p => p !== null && p !== undefined && p > 0);
    return prices.length > 0 ? Math.min(...prices) : 0;
}

function getHighestPrice(product) {
    const prices = Object.values(getNormalizedPriceMap(product)).filter(p => p !== null && p !== undefined && p > 0);
    return prices.length > 0 ? Math.max(...prices) : 0;
}

function getLowestPlatform(product) {
    const min = getLowestPrice(product);
    const prices = getNormalizedPriceMap(product);
    return Object.keys(prices).find(k => prices[k] === min);
}

function getHighestPlatform(product) {
    const max = getHighestPrice(product);
    const prices = getNormalizedPriceMap(product);
    return Object.keys(prices).find(k => prices[k] === max);
}

function formatPrice(price) {
    const normalized = normalizePriceValue(price);
    if (!normalized) return 'N/A';
    return '\u20B9' + normalized.toLocaleString('en-IN');
}

function getPriceDiffHtml(product) {
    if (isFamilySummaryMode(product)) {
        return `
    <div class="price-diff-bar summary">
      <span class="diff-save">Variant prices change by size, color or configuration</span>
      <span class="diff-detail">Select one variant to compare exact store prices</span>
    </div>
  `;
    }

    const validPrices = Object.entries(getDisplayPriceMap(product)).filter(([k, v]) => v !== null && v !== undefined && v > 0);
    if (validPrices.length < 2) return '';
    const lowest = getDisplayLowestPrice(product);
    const highest = getDisplayHighestPrice(product);
    const diff = highest - lowest;
    if (diff <= 0) return '';
    const pct = ((diff / highest) * 100).toFixed(1);
    const lowPlatform = PLATFORM_CONFIG[getDisplayLowestPlatform(product)]?.name || '';
    const highPlatform = PLATFORM_CONFIG[getDisplayHighestPlatform(product)]?.name || '';
    const prefix = (product.variantCount || getNormalizedVariantList(product).length) > 1 ? 'Selected variant' : 'Save';
    return `
    <div class="price-diff-bar">
      <span class="diff-save">${prefix} saves ${formatPrice(diff)} (${pct}%)</span>
      <span class="diff-detail">${lowPlatform} is cheaper than ${highPlatform}</span>
    </div>
  `;
}

function getVariantLabel(variant) {
    if (!variant || typeof variant !== 'object') return 'Standard';
    const parts = [variant.ram, variant.storage, variant.color, variant.size].filter(Boolean);
    return (variant.label || parts.join(' / ') || 'Standard').toString().trim();
}

function getVariantRawDescriptor(product, variant) {
    const rawName = (variant?.name || '').toString().trim();
    if (!rawName) return '';

    const baseName = (product?.model || product?.name || '').toString().trim();
    if (!baseName) return rawName;

    const stripped = rawName
        .replace(new RegExp(escapeRegExp(baseName), 'ig'), ' ')
        .replace(/\s+/g, ' ')
        .replace(/^[\s\-–—,:/()[\]]+|[\s\-–—,:/()[\]]+$/g, '')
        .trim();

    return stripped || rawName;
}

function getPrimaryVariantLabel(product, variant) {
    const label = getVariantLabel(variant);
    if (label && label !== 'Standard') return label;

    const descriptor = getVariantRawDescriptor(product, variant);
    return descriptor || label || 'Variant';
}

function getVariantSubtitle(product, variant) {
    const label = getVariantLabel(variant);
    if (label && label !== 'Standard') return '';

    const descriptor = getVariantRawDescriptor(product, variant);
    if (!descriptor) return '';

    const primaryLabel = getPrimaryVariantLabel(product, variant);
    return normalizeText(primaryLabel) === normalizeText(descriptor) ? '' : descriptor;
}

function getVariantIdentityKey(variant) {
    if (!variant || typeof variant !== 'object') return 'standard';
    return [
        variant.ram || '',
        variant.storage || '',
        variant.size || '',
    ].join('|') || 'standard';
}

function getFeaturedVariants(variants, limit = 4) {
    if (!Array.isArray(variants) || variants.length <= limit) return variants || [];

    const featured = [];
    const usedIndices = new Set();
    const usedIdentityKeys = new Set();

    variants.forEach((variant, index) => {
        if (featured.length >= limit) return;
        const identityKey = getVariantIdentityKey(variant);
        if (usedIdentityKeys.has(identityKey)) return;
        usedIdentityKeys.add(identityKey);
        usedIndices.add(index);
        featured.push(variant);
    });

    variants.forEach((variant, index) => {
        if (featured.length >= limit) return;
        if (usedIndices.has(index)) return;
        usedIndices.add(index);
        featured.push(variant);
    });

    return featured;
}

function getSelectedVariantLabel(product) {
    const variants = getNormalizedVariantList(product);
    if (variants.length <= 1) return '';
    const activeVariant = getActiveVariant(product);
    return activeVariant ? getPrimaryVariantLabel(product, activeVariant) : '';
}

function renderVariantSection(product) {
    const variants = getNormalizedVariantList(product);
    if (!variants.length) return '';

    const showAllVariants = Boolean(product?.showAllVariants);
    const visibleVariants = showAllVariants ? variants : getFeaturedVariants(variants, 4);
    const allPlatforms = ['amazon', 'flipkart', 'myntra', 'meesho'];
    const activeIndex = getActiveVariantIndex(product);

    return `
    <div class="variant-section">
      <div class="variant-header">
        <span>Variants</span>
        <span>${variants.length}</span>
      </div>
      ${visibleVariants.map(variant => {
        const variantIndex = variants.findIndex(item => item === variant);
        const variantLabel = getPrimaryVariantLabel(product, variant);
        const variantSubtitle = getVariantSubtitle(product, variant);
        const offers = allPlatforms
            .filter(platform => variant.prices?.[platform])
            .map(platform => {
                const config = PLATFORM_CONFIG[platform];
                if (!config) return '';
                const price = variant.prices[platform];
                const link = variant.links?.[platform];
                const isBest = variant.bestPlatform === platform;
                const tag = link ? 'a' : 'span';
                const attrs = link ? `href="${link}" target="_blank" rel="noopener noreferrer"` : '';
                return `
                  <${tag} ${attrs} class="variant-offer-chip ${isBest ? 'best' : ''}">
                    <span class="variant-offer-store">${config.name}</span>
                    <span class="variant-offer-price">${formatPrice(price)}</span>
                  </${tag}>
                `;
            })
            .join('');

        return `
          <div class="variant-row ${variantIndex === activeIndex ? 'active' : ''}" onclick="selectVariant(${product.id}, ${variantIndex})" role="button" tabindex="0">
            <div class="variant-label">${escapeHtml(variantLabel)}</div>
            ${variantSubtitle ? `<div class="variant-subtitle">${escapeHtml(variantSubtitle)}</div>` : ''}
            <div class="variant-offers">
              ${offers || '<span class="variant-empty">No live offers</span>'}
            </div>
          </div>
        `;
      }).join('')}
      ${variants.length > 4 ? `
        <button type="button" class="variant-more-btn" onclick="toggleVariantExpansion(${product.id})">
          ${showAllVariants ? 'Show fewer variants' : `Show all ${variants.length} variants`}
        </button>
      ` : ''}
    </div>
  `;
}

function buildProductCardHtml(product, options) {
    const {
        isInCompare,
        allPlatforms,
        platformDisplay,
        variants,
        isFamilySummary,
        selectedVariantLabel,
        availablePlatforms,
        lowestPlatform,
    } = options;

    const summaryBits = [];
    if (availablePlatforms.length > 1) summaryBits.push(`${availablePlatforms.length} platforms compared`);
    if (variants.length > 1) summaryBits.push(`${variants.length} variants`);

    const imgHtml = product.image
        ? `<img src="${product.image}" alt="${product.name}" loading="lazy" style="max-height:160px;object-fit:contain;">`
        : (PRODUCT_ICONS[product.category] || PRODUCT_ICONS['Electronics']);

    const isInWishlist = wishlist.some(w => w.name === product.name);

    return `
      <div class="product-card" id="product-card-${product.id}">
        <div class="product-image">${imgHtml}</div>
        <div class="product-info">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:6px;margin-bottom:2px">
            <span class="product-category-tag">${product.category}</span>
            <div style="display:flex;gap:4px;flex-shrink:0">
              <button class="btn-wishlist ${isInWishlist ? 'active' : ''}" onclick="toggleWishlist(${product.id})" title="${isInWishlist ? 'Remove from wishlist' : 'Save to wishlist'}">${isInWishlist ? '\u2665' : '\u2661'}</button>
              <button class="btn-share" onclick="shareProduct(${product.id})" title="Share this product">\u{1F517}</button>
            </div>
          </div>
          <h3 class="product-name">${product.model || product.name}</h3>
          ${isFamilySummary
                ? '<div class="selected-variant-note pending">Select a variant for exact prices, buy links and comparison</div>'
                : (selectedVariantLabel ? `<div class="selected-variant-note">Showing prices for ${escapeHtml(selectedVariantLabel)}</div>` : '')
            }
          ${product.rating ? `
          <div class="product-rating">
            <span class="stars">${getStars(product.rating)}</span>
            <span class="rating-value">${product.rating}</span>
            ${product.reviews ? `<span class="review-count">(${formatReviews(product.reviews)})</span>` : ''}
          </div>` : ''}
          
          <div class="platform-prices">
            ${summaryBits.length ? `<div class="platforms-count">${summaryBits.join(' \u2022 ')}</div>` : ''}
            ${allPlatforms.map(platform => {
                const displayEntry = platformDisplay[platform];
                const isLowest = !displayEntry?.isSummary && platform === lowestPlatform && availablePlatforms.length > 1;
                const config = PLATFORM_CONFIG[platform];
                if (!config) return '';

                const price = displayEntry?.value;
                const priceLabel = displayEntry?.label || 'N/A';
                const platformLink = displayEntry?.link;
                const tag = (price && platformLink) ? 'a' : 'div';
                const linkAttrs = (price && platformLink) ? `href="${platformLink}" target="_blank" rel="noopener noreferrer"` : '';
                const title = price
                    ? (displayEntry?.isSummary
                        ? `Select a variant to see the exact ${config.name} price`
                        : (platformLink ? `Click to buy on ${config.name}` : config.name))
                    : config.name;

                return `
                <${tag} ${linkAttrs} class="platform-row ${isLowest ? 'lowest-price' : ''} ${displayEntry?.isSummary ? 'summary' : ''}" title="${title}" style="cursor:${(price && platformLink) ? 'pointer' : 'default'};text-decoration:none;color:inherit;display:flex;align-items:center; opacity: ${price ? '1' : '0.5'};">
                  <span class="platform-name">
                    <span class="p-icon ${config.class}">${config.icon}</span>
                    ${config.name}
                  </span>
                  <span class="platform-price ${displayEntry?.isSummary ? 'summary' : ''}">${escapeHtml(priceLabel)}</span>
                  ${isLowest ? '<span class="lowest-tag">BEST</span>' : ''}
                  ${platformLink ? '<span class="visit-arrow" style="margin-left:auto;font-size:0.7rem;opacity:0.5;padding-left:6px;">&#8599;</span>' : ''}
                </${tag}>
              `;
            }).join('')}
          </div>
          ${renderVariantSection(product)}
          ${getPriceDiffHtml(product)}

          <div class="product-actions">
            <button class="btn-compare ${isInCompare ? 'added' : ''} ${isFamilySummary && !isInCompare ? 'disabled' : ''}" onclick="toggleCompare(${product.id})">
              ${isInCompare ? 'Added' : (isFamilySummary ? 'Pick Variant' : 'Compare')}
            </button>
            ${(() => {
                if (isFamilySummary) {
                    return `<button class="btn-buy-best disabled" onclick="buyBest(${product.id})">Select Variant</button>`;
                }
                const links = getDisplayLinkMap(product);
                const link = links?.[lowestPlatform] || links?.amazon || links?.flipkart || links?.meesho || links?.myntra;
                return link
                    ? `<a href="${link}" target="_blank" class="btn-buy-best">Buy Best Price &#8599;</a>`
                    : `<button class="btn-buy-best" onclick="buyBest(${product.id})">Buy Best Price</button>`;
            })()}
          </div>
        </div>
      </div>
    `;
}

// ==============================
// Render Products (with pagination)
// ==============================
function renderProducts() {
    const grid = document.getElementById('productsGrid');
    const countEl = document.getElementById('resultsCount');
    if (!grid || !countEl) return;

    // Cleanup old load-more observer
    if (loadMoreObserver) {
        loadMoreObserver.disconnect();
        loadMoreObserver = null;
    }

    if (filteredProducts.length === 0) {
        countEl.textContent = `0 of ${allProducts.length} products`;
        grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1">
        <p>No products match your filters. Try adjusting the price range or rating.</p>
      </div>`;
        return;
    }

    const showing = Math.min(visibleCount, filteredProducts.length);
    const hasMore = showing < filteredProducts.length;
    countEl.textContent = `Showing ${showing} of ${filteredProducts.length} products`;

    const visibleProducts = filteredProducts.slice(0, showing);

    let html = visibleProducts.map(product => {
        const isInCompare = compareList.includes(product.id);
        const allPlatforms = ['amazon', 'flipkart', 'myntra', 'meesho'];
        const platformDisplay = getPlatformDisplayMap(product);
        const variants = getNormalizedVariantList(product);
        const isFamilySummary = isFamilySummaryMode(product);
        const selectedVariantLabel = getSelectedVariantLabel(product);
        const availablePlatforms = allPlatforms.filter(platform => platformDisplay[platform]?.value);
        const lowestPlatform = !isFamilySummary && availablePlatforms.length > 0
            ? availablePlatforms.reduce((a, b) => platformDisplay[a].value < platformDisplay[b].value ? a : b)
            : null;
        return buildProductCardHtml(product, {
            isInCompare,
            allPlatforms,
            platformDisplay,
            variants,
            isFamilySummary,
            selectedVariantLabel,
            availablePlatforms,
            lowestPlatform,
        });
    }).join('');

    if (hasMore) {
        const remaining = filteredProducts.length - showing;
        html += `
      <div class="load-more-container" id="loadMoreContainer">
        <button class="load-more-btn" onclick="loadMoreProducts()">
          <span class="load-more-icon">\u2193</span>
          Load More (${remaining} remaining)
        </button>
      </div>`;
    }

    grid.innerHTML = html;

    // Auto-load more when scrolled to bottom
    if (hasMore) {
        const loadMoreEl = document.getElementById('loadMoreContainer');
        if (loadMoreEl) {
            loadMoreObserver = new IntersectionObserver((entries) => {
                if (entries[0].isIntersecting) {
                    loadMoreProducts();
                }
            }, { threshold: 0.1, rootMargin: '200px' });
            loadMoreObserver.observe(loadMoreEl);
        }
    }

    // Activate scroll reveal on new cards
    initScrollReveal();
}

function loadMoreProducts() {
    visibleCount += PRODUCTS_PER_PAGE;
    renderProducts();
}

function getStars(rating) {
    if (!rating) return '';
    const full = Math.floor(rating);
    const half = rating % 1 >= 0.5 ? 1 : 0;
    return '<span style="color:#f59e0b">' + '\u2605'.repeat(full) + (half ? '\u00BD' : '') + '</span><span style="color:#d1d5db">' + '\u2606'.repeat(5 - full - half) + '</span>';
}

function formatReviews(count) {
    if (!count) return '0';
    if (count >= 1000) return (count / 1000).toFixed(1) + 'K';
    return count.toString();
}

// ==============================
// Comparison
// ==============================
function findProduct(productId) {
    return allProducts.find(p => p.id === productId);
}

function toggleCompare(productId) {
    const product = findProduct(productId);
    if (!product) return;

    const idx = compareList.indexOf(productId);
    if (idx > -1) {
        compareList.splice(idx, 1);
        showToast('Removed from comparison');
    } else {
        if (isFamilySummaryMode(product)) {
            showToast('Select one exact variant first so we compare the right price.');
            return;
        }
        if (compareList.length >= 4) {
            showToast('Max 4 products can be compared at once');
            return;
        }
        compareList.push(productId);
        showToast('Added to comparison');
    }
    updateCompareUI();
    renderProducts();
}

function updateCompareUI() {
    document.getElementById('compareCount').textContent = compareList.length;
    const section = document.getElementById('comparison-section');

    if (compareList.length >= 2) {
        section.classList.add('active');
        renderComparisonTable();
    } else {
        section.classList.remove('active');
    }
}

function scrollToComparison() {
    if (compareList.length < 2) {
        showToast('Add at least 2 products to compare');
        return;
    }
    document.getElementById('comparison-section').scrollIntoView({ behavior: 'smooth' });
}

function findProduct(id) {
    return allProducts.find(p => p.id === id);
}

function selectVariant(productId, variantIndex) {
    const product = findProduct(productId);
    if (!product) return;

    const variants = getNormalizedVariantList(product);
    if (!variants.length) return;

    const nextIndex = Math.max(0, Math.min(variantIndex, variants.length - 1));
    if (product.selectedVariantIndex === nextIndex) return;

    product.selectedVariantIndex = nextIndex;
    renderProducts();

    if (compareList.includes(productId)) {
        renderComparisonTable();
    }
}

function toggleVariantExpansion(productId) {
    const product = findProduct(productId);
    if (!product) return;

    product.showAllVariants = !product.showAllVariants;
    renderProducts();

    if (compareList.includes(productId)) {
        renderComparisonTable();
    }
}

function renderComparisonTable() {
    const table = document.getElementById('comparisonTable');
    const products = compareList.map(id => findProduct(id)).filter(Boolean);

    if (products.length < 2) return;
    if (products.some(product => isFamilySummaryMode(product))) {
        table.innerHTML = `
      <tbody>
        <tr>
          <td class="feature-label">Exact comparison</td>
          <td colspan="${products.length}">Select a size, color, storage or other variant for every grouped product first.</td>
        </tr>
      </tbody>
    `;
        return;
    }

    // Score calculation
    const displayLowestPrices = products.map(p => getDisplayLowestPrice(p) || 1);
    const maxPrice = Math.max(...displayLowestPrices);
    const scores = products.map(p => {
        const lowestPrice = getDisplayLowestPrice(p) || 1;
        const priceScore = maxPrice > 0 ? (1 - lowestPrice / maxPrice) : 0;
        const ratingScore = (p.rating || 0) / 5;
        const maxRev = Math.max(...products.map(pp => pp.reviews || 1));
        const reviewScore = (p.reviews || 0) / maxRev;
        return priceScore * 0.4 + ratingScore * 0.35 + reviewScore * 0.25;
    });

    const bestIdx = scores.indexOf(Math.max(...scores));

    let html = `<thead><tr><th class="feature-label">Feature</th>`;
    products.forEach((p, i) => {
        const selectedVariantLabel = getSelectedVariantLabel(p);
        html += `<th class="product-col-header">
      <div>${p.name.length > 35 ? p.name.substring(0, 35) + '\u2026' : p.name}</div>
      ${selectedVariantLabel ? `<div class="compare-variant-label">${escapeHtml(selectedVariantLabel)}</div>` : ''}
      ${i === bestIdx ? '<div class="best-pick-banner">BEST PICK</div>' : ''}
      <button class="remove-col-btn" onclick="toggleCompare(${p.id})">&times;</button>
    </th>`;
    });
    html += `</tr></thead><tbody>`;

    // Platform Price Rows
    Object.keys(PLATFORM_CONFIG).forEach(platform => {
        const config = PLATFORM_CONFIG[platform];
        const pricesForPlatform = products.map(p => getDisplayPriceMap(p)[platform]).filter(Boolean);
        if (pricesForPlatform.length === 0) return;
        const minPlatformPrice = Math.min(...pricesForPlatform);

        html += `<tr><td class="feature-label"><span class="p-icon ${config.class}" style="display:inline-flex;width:18px;height:18px;border-radius:4px;align-items:center;justify-content:center;font-size:0.6rem;font-weight:700;color:white;margin-right:6px">${config.icon}</span>${config.name} Price</td>`;
        products.forEach(p => {
            const price = getDisplayPriceMap(p)[platform];
            if (!price) { html += '<td>N/A</td>'; return; }
            const isBest = price === minPlatformPrice && pricesForPlatform.length > 1;
            html += `<td class="${isBest ? 'best-cell' : ''}">${formatPrice(price)}</td>`;
        });
        html += `</tr>`;
    });

    // Best Price Row
    html += `<tr><td class="feature-label">Best Price</td>`;
    const lowestPrices = products.map(p => getDisplayLowestPrice(p));
    const overallLowest = Math.min(...lowestPrices.filter(p => p > 0));
    products.forEach(p => {
        const lowest = getDisplayLowestPrice(p);
        const platform = getDisplayLowestPlatform(p);
        const isBest = lowest === overallLowest && lowest > 0;
        const pName = PLATFORM_CONFIG[platform]?.name || platform;
        html += `<td class="${isBest ? 'best-cell' : ''}">${formatPrice(lowest)} (${pName})</td>`;
    });
    html += `</tr>`;

    // Savings Row
    const highestPrice = Math.max(...lowestPrices);
    html += `<tr><td class="feature-label">You Save vs Highest</td>`;
    products.forEach(p => {
        const diff = highestPrice - getDisplayLowestPrice(p);
        html += `<td class="${diff > 0 ? 'best-cell' : ''}">${diff > 0 ? formatPrice(diff) + ' cheaper' : '\u2014'}</td>`;
    });
    html += `</tr>`;

    // Rating Row
    const ratings = products.map(p => p.rating || 0);
    const maxRating = Math.max(...ratings);
    html += `<tr><td class="feature-label">Rating</td>`;
    products.forEach(p => {
        html += `<td class="${(p.rating || 0) === maxRating && maxRating > 0 ? 'best-cell' : ''}">${p.rating ? p.rating + ' / 5' : 'N/A'}</td>`;
    });
    html += `</tr>`;

    // Reviews Row
    const reviews = products.map(p => p.reviews || 0);
    const maxReviews = Math.max(...reviews);
    html += `<tr><td class="feature-label">Reviews</td>`;
    products.forEach(p => {
        html += `<td class="${(p.reviews || 0) === maxReviews && maxReviews > 0 ? 'best-cell' : ''}">${p.reviews ? formatReviews(p.reviews) : 'N/A'}</td>`;
    });
    html += `</tr>`;

    // Overall Score
    html += `<tr style="background:var(--bg-secondary)"><td class="feature-label" style="font-weight:800">Overall Score</td>`;
    products.forEach((p, i) => {
        const score = (scores[i] * 100).toFixed(0);
        html += `<td class="${i === bestIdx ? 'best-cell' : ''}" style="font-size:1.2rem;font-weight:800">${score}%</td>`;
    });
    html += `</tr></tbody>`;

    table.innerHTML = html;

    // Add share comparison button below table
    const wrapper = table.closest('.comparison-table-wrapper');
    let shareBtn = wrapper?.parentElement?.querySelector('.btn-share-comparison');
    if (!shareBtn && wrapper?.parentElement) {
        shareBtn = document.createElement('button');
        shareBtn.className = 'btn-share-comparison';
        shareBtn.innerHTML = '\u{1F517} Share Comparison';
        shareBtn.onclick = shareComparison;
        wrapper.parentElement.appendChild(shareBtn);
    }
}

function buyBest(productId) {
    const product = findProduct(productId);
    if (!product) return;
    if (isFamilySummaryMode(product)) {
        showToast('Select one exact variant first to open the correct store listing.');
        return;
    }
    const platform = getDisplayLowestPlatform(product);
    if (!platform) {
        showToast('No live offer is available for this variant yet.');
        return;
    }
    const config = PLATFORM_CONFIG[platform];
    const links = getDisplayLinkMap(product);
    const prices = getDisplayPriceMap(product);
    if (links && links[platform]) {
        window.open(links[platform], '_blank');
    } else {
        showToast(`Best price on ${config?.name || platform}: ${formatPrice(prices[platform])}`);
    }
}

// ==============================
// Toast
// ==============================
function showToast(message) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ==============================
// Scroll Effects & Navigation
// ==============================
function initScrollEffects() {
    const scrollBtn = document.getElementById('scrollTopBtn');
    if (scrollBtn) {
        window.addEventListener('scroll', () => {
            scrollBtn.classList.toggle('visible', window.scrollY > 500);
        });
    }
    initScrollSpy();
}

function initScrollSpy() {
    const sections = [
        { id: 'hero', link: 'a[href="#hero"]' },
        { id: 'categories-section', link: 'a[href="#categories-section"]' },
        { id: 'products-section', link: 'a[href="#products-section"]' },
        { id: 'wishlist-section', link: 'a[href="#wishlist-section"]' },
        { id: 'trending-section', link: 'a[href="#trending-section"]' }
    ];

    const navLinks = document.querySelectorAll('.nav-links a');
    
    // Use IntersectionObserver for performant scroll-tracking
    const observerOptions = {
        root: null,
        rootMargin: '-20% 0px -70% 0px',
        threshold: 0
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                const activeSpec = sections.find(s => s.id === id);
                if (activeSpec) {
                    navLinks.forEach(link => link.classList.remove('active'));
                    const targetLink = document.querySelector(`.nav-links ${activeSpec.link}`);
                    if (targetLink) targetLink.classList.add('active');
                }
            }
        });
    }, observerOptions);

    sections.forEach(sec => {
        const el = document.getElementById(sec.id);
        if (el) observer.observe(el);
    });
}

// ==============================
// Skeleton Loading
// ==============================
function showSkeletonLoading() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;
    const skeletonCount = 6;
    let html = '';
    for (let i = 0; i < skeletonCount; i++) {
        html += `
        <div class="skeleton-card" style="animation-delay:${i * 0.08}s">
          <div class="skeleton-image"></div>
          <div class="skeleton-body">
            <div class="skeleton-line w-40"></div>
            <div class="skeleton-line thick w-80"></div>
            <div class="skeleton-line w-60"></div>
            <div class="skeleton-line w-100" style="height:32px;border-radius:var(--radius-sm);margin-top:12px"></div>
            <div class="skeleton-line w-100" style="height:32px;border-radius:var(--radius-sm)"></div>
            <div class="skeleton-row">
              <div class="skeleton-btn"></div>
              <div class="skeleton-btn"></div>
            </div>
          </div>
        </div>`;
    }
    grid.innerHTML = html;
    document.getElementById('loadingIndicator').style.display = 'none';
}

// ==============================
// Scroll Reveal (IntersectionObserver)
// ==============================
function initScrollReveal() {
    const cards = document.querySelectorAll(
        '.product-card:not(.reveal), .category-card:not(.reveal), .trending-card:not(.reveal)'
    );

    cards.forEach((card, i) => {
        card.classList.add('reveal');
        card.style.transitionDelay = `${i * 0.06}s`;
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

// ==============================
// Mobile Menu
// ==============================
function toggleMobileMenu() {
    const links = document.querySelector('.nav-links');
    if (links.style.display === 'flex') {
        links.style.display = 'none';
    } else {
        links.style.display = 'flex';
        links.style.flexDirection = 'column';
        links.style.position = 'absolute';
        links.style.top = '100%';
        links.style.left = '0';
        links.style.width = '100%';
        links.style.background = 'var(--bg-dark)';
        links.style.padding = '16px 24px';
        links.style.borderBottom = '1px solid var(--border)';
        links.style.gap = '16px';
    }
}

// ==============================
// Share Product / Comparison
// ==============================
function tryNativeShare(shareData, fallbackUrl) {
    const ua = navigator.userAgent;
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
    const isWindows = /Windows NT/i.test(ua);
    
    // Windows desktop share is often broken or unconfigured, prefer clipboard
    if (navigator.share && isMobile && !isWindows) {
        navigator.share(shareData).catch(() => {
            copyToClipboard(fallbackUrl);
        });
    } else {
        copyToClipboard(fallbackUrl);
    }
}

function shareProduct(productId) {
    const product = findProduct(productId);
    if (!product) return;

    const query = document.getElementById('searchInput')?.value?.trim() || '';
    const productIndex = allProducts.findIndex(p => p.id === productId);
    const params = new URLSearchParams();
    if (query) params.set('search', query);
    if (productIndex >= 0) params.set('product', productIndex);

    const url = `${window.location.origin}${window.location.pathname}#${params.toString()}`;
    const shareData = {
        title: `CompareHub - ${product.name}`,
        text: `Check out the best prices for ${product.name} on CompareHub!`,
        url: url
    };

    tryNativeShare(shareData, url);
}

function shareComparison() {
    const query = document.getElementById('searchInput')?.value?.trim() || '';
    const compareIndices = compareList.map(id => {
        return allProducts.findIndex(p => p.id === id);
    }).filter(i => i >= 0);

    const params = new URLSearchParams();
    if (query) params.set('search', query);
    if (compareIndices.length > 0) params.set('compare', compareIndices.join(','));

    const url = `${window.location.origin}${window.location.pathname}#${params.toString()}`;
    const shareData = {
        title: 'CompareHub - Product Comparison',
        text: `Compare products on CompareHub!`,
        url: url
    };

    tryNativeShare(shareData, url);
}

function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('\u2705 Link copied to clipboard!');
        }).catch(() => {
            fallbackCopyToClipboard(text);
        });
    } else {
        fallbackCopyToClipboard(text);
    }
}

function fallbackCopyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        showToast('\u2705 Link copied to clipboard!');
    } catch (e) {
        showToast('Could not copy link. Try manually.');
    }
    document.body.removeChild(textarea);
}

function restoreFromUrl() {
    const hash = window.location.hash;
    if (!hash || hash.length < 2) return;

    try {
        const params = new URLSearchParams(hash.substring(1));
        const searchQuery = params.get('search');
        if (!searchQuery) return;

        // Clear hash to prevent re-triggering
        history.replaceState(null, '', window.location.pathname);

        document.getElementById('searchInput').value = searchQuery;

        const productIndex = params.get('product');
        const compareIndices = params.get('compare');

        handleSearch(searchQuery).then(() => {
            if (productIndex !== null) {
                const idx = parseInt(productIndex, 10);
                if (idx >= 0 && idx < allProducts.length) {
                    const card = document.getElementById(`product-card-${allProducts[idx].id}`);
                    if (card) {
                        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        card.style.boxShadow = '0 0 0 3px var(--accent-secondary), var(--shadow-lg)';
                        setTimeout(() => { card.style.boxShadow = ''; }, 3000);
                    }
                }
            }

            if (compareIndices) {
                const indices = compareIndices.split(',').map(i => parseInt(i, 10)).filter(i => i >= 0 && i < allProducts.length);
                compareList = indices.map(i => allProducts[i].id);
                updateCompareUI();
                renderProducts();
                if (compareList.length >= 2) {
                    setTimeout(() => {
                        document.getElementById('comparison-section').scrollIntoView({ behavior: 'smooth' });
                    }, 500);
                }
            }
        }).catch(() => {});
    } catch (e) {
        console.warn('URL restore skipped', e);
    }
}

// ==============================
// Wishlist / Favorites
// ==============================
function loadWishlist() {
    try {
        const raw = localStorage.getItem('comparehub_wishlist');
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function saveWishlistToStorage() {
    try {
        localStorage.setItem('comparehub_wishlist', JSON.stringify(wishlist));
    } catch (e) {
        console.warn('Wishlist save skipped', e);
    }
}

function toggleWishlist(productId) {
    const product = findProduct(productId);
    if (!product) return;

    const existingIndex = wishlist.findIndex(w => w.name === product.name);
    if (existingIndex >= 0) {
        wishlist.splice(existingIndex, 1);
        showToast('\u2764\uFE0F Removed from wishlist');
    } else {
        const lowestPrice = getLowestPrice(product);
        const query = document.getElementById('searchInput')?.value?.trim() || '';
        wishlist.unshift({
            name: product.name,
            image: product.image || null,
            category: product.category,
            lowestPrice: lowestPrice,
            query: query,
            savedAt: Date.now()
        });
        if (wishlist.length > 50) wishlist.pop();
        showToast('\u2764\uFE0F Saved to wishlist!');
    }

    saveWishlistToStorage();
    renderWishlistSection();
    renderProducts();
}

function removeFromWishlist(index) {
    if (index < 0 || index >= wishlist.length) return;
    wishlist.splice(index, 1);
    saveWishlistToStorage();
    renderWishlistSection();
    renderProducts();
    showToast('Removed from wishlist');
}

function renderWishlistSection() {
    const grid = document.getElementById('wishlistGrid');
    if (!grid) return;

    if (wishlist.length === 0) {
        grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;padding:20px">
        <p style="color:var(--text-muted);font-size:0.85rem">\u2661 Products you save will appear here</p>
      </div>`;
        return;
    }

    grid.innerHTML = wishlist.map((item, index) => {
        const imgHtml = item.image
            ? `<img src="${item.image}" alt="${escapeHtml(item.name)}" loading="lazy">`
            : `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="3"/></svg>`;
        const priceHtml = item.lowestPrice ? `<div class="wishlist-card-price">From ${formatPrice(item.lowestPrice)}</div>` : '';
        const encodedQuery = encodeURIComponent(item.query || item.name);

        return `
      <div class="wishlist-card">
        <div class="wishlist-card-image">${imgHtml}</div>
        <div class="wishlist-card-info">
          <div class="wishlist-card-name">${escapeHtml(item.name)}</div>
          ${priceHtml}
          <div class="wishlist-card-actions">
            <button class="wishlist-search-btn" onclick="quickSearchFromEncoded('${encodedQuery}')">Search Again</button>
            <button class="wishlist-remove-btn" onclick="removeFromWishlist(${index})">Remove</button>
          </div>
        </div>
      </div>`;
    }).join('');

    initScrollReveal();
}

// ==============================
// Loading Progress Animation
// ==============================
let progressTimers = [];

function showProgressLoading() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;

    const platforms = [
        { key: 'amazon', name: 'Amazon', icon: 'A', class: 'amazon' },
        { key: 'flipkart', name: 'Flipkart', icon: 'F', class: 'flipkart' },
        { key: 'myntra', name: 'Myntra', icon: 'M', class: 'myntra' },
        { key: 'meesho', name: 'Meesho', icon: 'M', class: 'meesho' },
    ];

    grid.innerHTML = `
    <div class="progress-card">
      <div class="progress-title">Searching across platforms...</div>
      <div class="progress-subtitle">Fetching live prices from e-commerce sites</div>
      <div class="progress-steps">
        ${platforms.map(p => `
          <div class="progress-step waiting" id="progress-step-${p.key}">
            <span class="step-icon p-icon ${p.class}">${p.icon}</span>
            <span>${p.name}</span>
          </div>
        `).join('')}
      </div>
      <div class="progress-bar-track">
        <div class="progress-bar-fill" id="progressBarFill"></div>
      </div>
    </div>`;

    document.getElementById('loadingIndicator').style.display = 'none';

    // Clear any previous timers
    progressTimers.forEach(t => clearTimeout(t));
    progressTimers = [];

    // Animate steps sequentially
    const delays = [400, 1800, 3200, 5000];
    const doneDelays = [1600, 3000, 4800, 7000];

    platforms.forEach((p, i) => {
        progressTimers.push(setTimeout(() => {
            const stepEl = document.getElementById(`progress-step-${p.key}`);
            if (stepEl) {
                stepEl.classList.remove('waiting');
                stepEl.classList.add('active');
            }
            const bar = document.getElementById('progressBarFill');
            if (bar) bar.style.width = `${((i + 0.5) / platforms.length) * 100}%`;
        }, delays[i]));

        progressTimers.push(setTimeout(() => {
            const stepEl = document.getElementById(`progress-step-${p.key}`);
            if (stepEl) {
                stepEl.classList.remove('active');
                stepEl.classList.add('done');
                stepEl.querySelector('.step-icon').textContent = '\u2713';
            }
            const bar = document.getElementById('progressBarFill');
            if (bar) bar.style.width = `${((i + 1) / platforms.length) * 100}%`;
        }, doneDelays[i]));
    });
}

function clearProgressTimers() {
    progressTimers.forEach(t => clearTimeout(t));
    progressTimers = [];
}

// ==============================
// Voice & Image Search
// ==============================
function startVoiceSearch() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast("Voice search is not supported in this browser. Try Chrome.");
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    const micBtn = document.getElementById('voiceSearchBtn');
    const overlay = document.getElementById('siriOverlay');

    recognition.onstart = function() {
        if (micBtn) micBtn.classList.add('listening');
        if (overlay) overlay.classList.add('active');
        if (siriWave) siriWave.start();
        showToast("🎙️ Listening... Speak now!");
    };

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        document.getElementById('searchInput').value = transcript;
        showToast("Voice dictation complete!");
        handleSearch();
    };

    recognition.onerror = function(event) {
        console.error("Speech recognition error", event.error);
        if (event.error !== 'aborted') {
            showToast("Couldn't hear you properly, try again.");
        }
    };

    recognition.onend = function() {
        if (micBtn) micBtn.classList.remove('listening');
        if (overlay) overlay.classList.remove('active');
        if (siriWave) siriWave.stop();
    };

    // Allow clicking the overlay to cancel
    overlay.onclick = () => {
        recognition.stop();
    };

    recognition.start();
}

async function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Show a loading UI
    document.getElementById('searchInput').value = "Analyzing image...";
    setSearchUiBusy(true);

    const formData = new FormData();
    formData.append('image', file);

    try {
        const response = await fetch(`${API_BASE}/api/identify-image`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            let errorMsg = 'Image identification failed';
            try {
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.includes("application/json")) {
                    const errObj = await response.json();
                    errorMsg = errObj.message || errorMsg;
                } else {
                    errorMsg = `Server error ${response.status}: ${await response.text()}`;
                }
            } catch (e) {
                // Ignore parse errors
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        
        if (data.query) {
            document.getElementById('searchInput').value = data.query;
            showToast("Image identified!");
            handleSearch(data.query);
        } else {
            throw new Error("No product identified");
        }
    } catch (error) {
        console.error("Image upload error:", error);
        document.getElementById('searchInput').value = "";
        setSearchUiBusy(false);
        // Funny error reply as requested
        showToast("Whoops! Our AI got confused. Was that a toaster or a UFO? Try another image.");
    } finally {
        event.target.value = ''; // Reset file input
    }
}

// ==============================
// Initialize Application
// ==============================
document.addEventListener('DOMContentLoaded', () => {
    initSearchInput();
    initPriceFilterInputs();
    initScrollEffects(); // This also initializes ScrollSpy
    
    const inputEl = document.getElementById('searchInput');
    if (inputEl) {
        initAnimatedSearchPlaceholder(inputEl);
    }
    
    // Check if URL has shared parameters to restore
    restoreFromUrl();
    
    // Initial reveals
    initScrollReveal();

    // Initialize SiriWave
    const siriContainer = document.getElementById('siriWaveContainer');
    if (siriContainer && typeof SiriWave !== 'undefined') {
        siriWave = new SiriWave({
            container: siriContainer,
            width: window.innerWidth,
            height: 200,
            style: 'ios9',
            amplitude: 1,
            speed: 0.15,
            autostart: false
        });
        
        window.addEventListener('resize', () => {
            if (siriWave) siriWave.width = window.innerWidth;
        });
    }
});

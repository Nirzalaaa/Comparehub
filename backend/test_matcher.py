from matcher import ProductMatcher, _clean_model_display_name, group_matched_products
from scraper import (
    _append_capacity_variant_to_name,
    _should_group_results,
    _validate_and_rank_platform_products,
    build_search_intelligence,
    canonicalize_search_query,
    filter_products_by_query,
    select_platforms_for_query,
)

def test_nlp_matcher():
    matcher = ProductMatcher()

    # 1. Test basic match (Should be True)
    prod_a = {"name": "Apple iPhone 15 (128GB) - Midnight Black", "price": 79990}
    prod_b = {"name": "iPhone 15 128 gb black", "price": 78990}
    assert matcher.is_match(prod_a, prod_b) == True, "Basic match failed"

    # 2. Test strictly different models (Should be False)
    prod_c = {"name": "iPhone 14 128GB", "price": 69990}
    assert matcher.is_match(prod_a, prod_c) == False, "Model validation (14 vs 15) failed"

    # 3. Test different storage (Should be False)
    prod_d = {"name": "iPhone 15 256GB Black", "price": 89990}
    assert matcher.is_match(prod_a, prod_d) == False, "Storage validation failed"

    # 4. Test different variant (Should be False)
    prod_e = {"name": "iPhone 15 Pro 128GB", "price": 109990}
    assert matcher.is_match(prod_a, prod_e) == False, "Variant validation failed"

    # 5. Fuzzy threshold check (Should be False due to low Jaccard/Fuzzy)
    prod_f = {"name": "Samsung S24 Ultra 256GB Phantom Black", "price": 129990}
    assert matcher.is_match(prod_a, prod_f) == False, "Completely different item matched"

    # 6. Optional connectivity token should NOT block a match (5G vs no 5G)
    prod_g = {"name": "Apple iPhone 15 5G 128GB Black", "price": 79990}
    assert matcher.is_match(prod_a, prod_g) == True, "Optional token (5G) blocked a valid match"

    # 7. Model number inside token should still be recognized (iphone17 vs iphone 17)
    prod_h = {"name": "Apple iphone17 pro 256GB", "price": 129990}
    prod_i = {"name": "iPhone 17 Pro (256 GB) Natural Titanium", "price": 128990}
    assert matcher.is_match(prod_h, prod_i) == True, "Model-number token normalization failed"

    # 8. Device should not match accessory listing
    prod_j = {"name": "Apple iPhone 15 Pro 128GB", "price": 109990}
    prod_k = {"name": "Luxury Kase iPhone 15 Pro Back Case", "price": 499}
    assert matcher.is_match(prod_j, prod_k) == False, "Accessory matched as device"

    print("All boolean match logic passed successfully!")

def test_grouping():
    platform_results = {
        "amazon": [{"name": "Samsung Galaxy S24 Ultra 5G (Phantom Black, 256GB)", "price": 129000, "link": "amz/s24"}],
        "flipkart": [{"name": "SAMSUNG S24 ULTRA 256 GB Black", "price": 128500, "link": "flp/s24"}],
        "myntra": [{"name": "Nike Air Max Shoes", "price": 5000, "link": "myn/nike"}],
        "meesho": [{"name": "Best Nike Air Max Shoes online", "price": 4800, "link": "msh/nike"}]
    }

    grouped = group_matched_products(platform_results)
    
    assert len(grouped) == 2, f"Expected 2 groups, got {len(grouped)}"
    
    s24_group = next(g for g in grouped if g['prices']['amazon'] == 129000)
    nike_group = next(g for g in grouped if g['prices']['myntra'] == 5000)

    # S24 group
    assert s24_group['prices']['flipkart'] == 128500
    assert s24_group['variant_count'] >= 1

    # Nike group
    assert nike_group['prices']['meesho'] == 4800

    print("Grouping logic passed seamlessly!")

def test_grouping_phone_vs_accessory():
    platform_results = {
        "amazon": [{"name": "Apple iPhone 17 Pro 5G (256GB)", "price": 129900, "link": "amz/iphone17pro"}],
        "flipkart": [{"name": "iPhone 17 Pro (256 GB)", "price": 128900, "link": "flp/iphone17pro"}],
        "meesho": [],
        "myntra": [{"name": "Luxury Kase iPhone 17 Pro Back Case", "price": 499, "link": "myn/iphone17pro-case"}]
    }

    grouped = group_matched_products(platform_results)
    assert len(grouped) == 2, f"Expected 2 groups (device + accessory), got {len(grouped)}"

    device_group = next(g for g in grouped if g['prices']['amazon'] == 129900)
    assert device_group['prices']['amazon'] == 129900
    assert device_group['prices']['flipkart'] == 128900
    assert device_group['prices']['myntra'] is None

    print("Phone vs accessory grouping passed!")


def test_grouping_ignores_ram_only_title_difference():
    platform_results = {
        "amazon": [{"name": "Samsung Galaxy S24 Snapdragon 8 Gen 3 5G (Onyx Black, 128 GB) (8 GB RAM)", "price": 43999, "link": "amz/s24-128"}],
        "flipkart": [{"name": "Samsung Galaxy S24 5G Snapdragon (Cobalt Violet, 128 GB)", "price": 49999, "link": "flp/s24-128"}],
        "meesho": [],
        "myntra": []
    }

    grouped = group_matched_products(platform_results)
    assert len(grouped) == 1, f"Expected one merged S24 group, got {len(grouped)}"
    assert grouped[0]["prices"]["amazon"] == 43999
    assert grouped[0]["prices"]["flipkart"] == 49999
    assert grouped[0]["variant_count"] == 2, f"Expected two color/RAM variants inside model group, got {grouped[0]['variant_count']}"

    print("RAM-only title difference grouping passed!")


def test_model_grouping_keeps_variants_inside_product():
    platform_results = {
        "amazon": [
            {"name": "Samsung Galaxy S25 Ultra 12GB 256GB Black", "price": 70000, "link": "amz/s25-black-256"},
            {"name": "Samsung Galaxy S25 Ultra 16GB 512GB Black", "price": 80000, "link": "amz/s25-black-512"},
        ],
        "flipkart": [
            {"name": "Samsung Galaxy S25 Ultra 12GB 256GB Blue", "price": 69500, "link": "flp/s25-blue-256"},
        ],
        "meesho": [],
        "myntra": [],
    }

    grouped = group_matched_products(platform_results)
    assert len(grouped) == 1, f"Expected one model group, got {len(grouped)}"

    model_group = grouped[0]
    assert model_group["name"] == "Samsung Galaxy S25 Ultra", f"Unexpected model display name: {model_group['name']}"
    assert model_group["variant_count"] == 3, f"Expected 3 variants inside model group, got {model_group['variant_count']}"
    assert model_group["prices"]["amazon"] == 70000, "Top-level Amazon price should use best variant price"
    assert model_group["prices"]["flipkart"] == 69500, "Top-level Flipkart price should use best variant price"
    labels = {variant["label"] for variant in model_group["variants"]}
    assert "12GB / 256GB / Black" in labels
    assert "12GB / 256GB / Blue" in labels
    assert "16GB / 512GB / Black" in labels

    print("Model grouping with nested variants passed!")


def test_model_grouping_removes_color_and_size_noise():
    platform_results = {
        "amazon": [{"name": "Nike shoes red size 9", "price": 3000, "link": "amz/nike-red-9"}],
        "flipkart": [{"name": "Nike shoes blue size 8", "price": 2900, "link": "flp/nike-blue-8"}],
        "meesho": [],
        "myntra": [],
    }

    grouped = group_matched_products(platform_results)
    assert len(grouped) == 1, f"Expected one Nike model group, got {len(grouped)}"

    model_group = grouped[0]
    assert model_group["name"] == "Nike shoes", f"Expected cleaned model name, got {model_group['name']}"
    labels = {variant["label"] for variant in model_group["variants"]}
    assert "Red / Size 9" in labels
    assert "Blue / Size 8" in labels

    print("Color/size noise removal for model grouping passed!")


def test_plus_sign_variant_stays_separate():
    matcher = ProductMatcher()
    attrs = matcher.extract_structured_attributes("Samsung Galaxy S25+")
    assert attrs["strict_variants"] == {"plus"}, f"Expected plus variant detection, got {attrs['strict_variants']}"

    platform_results = {
        "amazon": [{"name": "Samsung Galaxy S25+", "price": 90000, "link": "amz/s25-plus"}],
        "flipkart": [{"name": "Samsung Galaxy S25", "price": 80000, "link": "flp/s25-base"}],
        "meesho": [],
        "myntra": [],
    }
    grouped = group_matched_products(platform_results)
    assert len(grouped) == 2, f"Expected plus and base models to stay separate, got {len(grouped)} groups"

    print("Plus-sign variant separation passed!")


def test_capacity_variant_text_is_appended_to_scraped_name():
    name = "Samsung Galaxy S26 (Black, 256 GB)"
    lines = [
        "Samsung Galaxy S26 (Black, 256 GB)",
        "Variant:",
        "256 GB + 12 GB",
        "₹87,999",
    ]
    enriched = _append_capacity_variant_to_name(name, lines)
    assert "256 GB + 12 GB" in enriched, f"Expected capacity snippet appended, got {enriched}"

    print("Capacity variant text append passed!")


def test_clean_model_name_removes_empty_parentheses():
    matcher = ProductMatcher()
    cleaned = _clean_model_display_name(matcher, "Samsung Galaxy S26 (Black, 256 GB)")
    assert cleaned == "Samsung Galaxy S26", f"Expected clean model name without empty parens, got {cleaned}"

    print("Empty parenthesis cleanup passed!")


def test_grouping_fashion_family_rules_prevent_wrong_merge():
    platform_results = {
        "amazon": [
            {"name": "Nike Mens Revolution 7 Running Shoes", "price": 3325, "link": "amz/revolution7"},
            {"name": "Nike Mens Run Defy Running Shoes", "price": 3995, "link": "amz/run-defy"},
        ],
        "flipkart": [],
        "meesho": [],
        "myntra": [
            {"name": "Nike Run Defy Men's Road-Running Shoes", "price": 3995, "link": "myn/run-defy"},
        ],
    }

    grouped = group_matched_products(platform_results)
    assert len(grouped) == 2, f"Expected Revolution and Run Defy to remain separate, got {len(grouped)} groups"
    run_defy_group = next(group for group in grouped if group["prices"]["myntra"] == 3995)
    assert run_defy_group["prices"]["amazon"] == 3995, "Run Defy should only merge with matching Run Defy listing"

    print("Fashion family grouping rules passed!")


def test_exact_model_signature_mismatch_rejected():
    matcher = ProductMatcher()
    prod_a = {"name": "Sony WH-1000XM5 Wireless Headphones", "price": 29990}
    prod_b = {"name": "Sony WH1000XM4 Bluetooth Headphones", "price": 22990}
    prod_c = {"name": "Sony WF-1000XM5 Wireless Earbuds", "price": 24990}
    prod_d = {"name": "Apple iPhone 16 128GB Black", "price": 79990}
    prod_e = {"name": "Apple iPhone 16e 128GB Black", "price": 59990}

    assert matcher.is_match(prod_a, prod_b) == False, "XM4 incorrectly matched XM5"
    assert matcher.is_match(prod_a, prod_c) == False, "WF series incorrectly matched WH series"
    assert matcher.is_match(prod_d, prod_e) == False, "iPhone 16e incorrectly matched iPhone 16"

    print("Exact model signature mismatch rejection passed!")


def test_query_filter_rejects_accessories_for_devices():
    products = [
        {"name": "Apple iPhone 15 128GB Black", "price": 79990, "link": "amz/iphone15"},
        {"name": "iPhone 15 Back Cover Silicone Case", "price": 499, "link": "amz/iphone15-case"},
    ]
    filtered = filter_products_by_query(products, "iPhone 15", max_results=10)
    assert len(filtered) == 1, f"Expected only device listing, got {len(filtered)}"
    assert filtered[0]["name"] == "Apple iPhone 15 128GB Black"

    print("Accessory rejection for device queries passed!")


def test_query_filter_soft_scores_and_keeps_numbers():
    products = [
        {"name": "Apple iPhone 14 128GB Black", "price": 69990, "link": "https://www.amazon.in/dp/B0IPHONE14"},
        {"name": "Apple iPhone 15 128GB Black", "price": 79990, "link": "https://www.amazon.in/dp/B0IPHONE15"},
        {"name": "Apple iPhone 15 256GB Blue", "price": 89990, "link": "https://www.amazon.in/dp/B0IPH15256"},
    ]
    filtered = filter_products_by_query(products, "iPhone 15 128GB", max_results=3)
    assert filtered, "Expected scored products for specific model query"
    assert filtered[0]["name"] == "Apple iPhone 15 128GB Black", "Exact model+storage match should rank first"

    print("Soft score ranking keeps numeric model matches first!")


def test_query_filter_never_returns_empty_when_raw_products_exist():
    products = [
        {"name": "iPhone 15 Back Cover Silicone Case", "price": 499, "link": "https://www.amazon.in/dp/B0CASE1501"},
        {"name": "iPhone 15 Tempered Glass Guard", "price": 299, "link": "https://www.flipkart.com/p/iphone15-glass"},
    ]
    filtered = filter_products_by_query(products, "iPhone 15", max_results=10)
    assert len(filtered) == 2, f"Expected raw fallback instead of empty results, got {len(filtered)}"

    print("Raw fallback prevents empty search results!")


def test_platform_selection_for_mobile_query():
    category, platforms = select_platforms_for_query("iPhone 15")
    assert category == "Mobiles", f"Expected Mobiles category, got {category}"
    assert platforms == ["amazon", "flipkart"], f"Expected only amazon+flipkart, got {platforms}"

    audio_category, audio_platforms = select_platforms_for_query("Sony WH 1000 XM5")
    assert audio_category == "Audio", f"Expected Audio category, got {audio_category}"
    assert audio_platforms == ["amazon", "flipkart"], f"Expected amazon+flipkart for audio, got {audio_platforms}"

    print("Platform selection for mobile queries passed!")


def test_platform_validation_keeps_low_confidence_fallback_rows():
    products = [
        {
            "name": "Samsung Galaxy S24 256GB Black",
            "price": 79990,
            "link": "https://www.amazon.in/dp/B0SAMS24BK",
            "platform": "amazon",
        }
    ]
    accepted, _quality = _validate_and_rank_platform_products(
        platform="amazon",
        products=products,
        query="iPhone 15",
        max_results=5,
        query_category="Mobiles",
    )
    assert len(accepted) == 1, "Expected low-confidence fallback row to remain instead of being dropped"

    print("Platform validation fallback passed!")


def test_specific_mobile_query_enables_grouping():
    platform_results = {
        "amazon": [{"name": "Apple iPhone 15 128GB Black", "price": 79990, "link": "amz/iphone15"}],
        "flipkart": [{"name": "iPhone 15 (Black, 128 GB)", "price": 78990, "link": "flp/iphone15"}],
        "meesho": [],
        "myntra": [],
    }
    assert _should_group_results("iPhone 15", results=platform_results) == True, "Specific mobile model queries should stay groupable"

    print("Specific mobile query grouping gate passed!")


def test_platform_selection_for_fashion_query():
    category, platforms = select_platforms_for_query("short kurti")
    assert category == "Fashion", f"Expected Fashion category, got {category}"
    assert platforms == ["amazon", "flipkart", "meesho", "myntra"], f"Expected all fashion platforms, got {platforms}"

    info = build_search_intelligence("short kurti")
    rewrite_queries = [item["query"] for item in info["rewrites"]]
    assert not any(query.endswith(" shoes") for query in rewrite_queries), "Fashion rewrite should not force shoes for kurti queries"

    print("Platform selection for fashion queries passed!")


def test_smart_category_mapping_for_non_hardcoded_queries():
    electronics_info = build_search_intelligence("gaming mouse under 2000")
    assert electronics_info["category"] == "Electronics", f"Expected Electronics, got {electronics_info['category']}"
    assert electronics_info["category_source"] == "rules", f"Expected rules source, got {electronics_info['category_source']}"

    fashion_info = build_search_intelligence("wedding outfit for men")
    assert fashion_info["category"] == "Fashion", f"Expected Fashion, got {fashion_info['category']}"

    home_category, home_platforms = select_platforms_for_query("office chair")
    assert home_category == "Home", f"Expected Home category, got {home_category}"
    assert home_platforms == ["amazon", "flipkart", "meesho"], f"Expected Home platforms, got {home_platforms}"

    grocery_category, grocery_platforms = select_platforms_for_query("basmati rice 5kg")
    assert grocery_category == "Grocery", f"Expected Grocery category, got {grocery_category}"
    assert grocery_platforms == ["amazon", "flipkart"], f"Expected grocery to stay on amazon+flipkart, got {grocery_platforms}"

    general_info = build_search_intelligence("gift hamper")
    assert general_info["category"] == "General", f"Expected General fallback, got {general_info['category']}"
    general_category, general_platforms = select_platforms_for_query("gift hamper")
    assert general_category == "General", f"Expected General fallback category, got {general_category}"
    assert general_platforms == ["amazon", "flipkart", "meesho", "myntra"], f"Expected broad fallback platforms, got {general_platforms}"

    stationery_info = build_search_intelligence("pent")
    assert stationery_info["normalized_query"] == "pen", f"Expected typo correction to pen, got {stationery_info['normalized_query']}"
    assert stationery_info["category"] == "Stationery", f"Expected Stationery, got {stationery_info['category']}"

    ring_category, ring_platforms = select_platforms_for_query("ring")
    assert ring_category == "Fashion", f"Expected ring to map to Fashion, got {ring_category}"
    assert ring_platforms == ["amazon", "flipkart", "meesho", "myntra"], f"Expected ring to use fashion platforms, got {ring_platforms}"

    print("Smart category mapping passed!")


def test_query_filter_rejects_wrong_variants():
    products = [
        {"name": "Apple iPhone 15 128GB Black", "price": 79990, "link": "amz/iphone15"},
        {"name": "Apple iPhone 15 Plus 128GB Black", "price": 89990, "link": "amz/iphone15plus"},
        {"name": "Apple iPhone 15 Pro 128GB Black", "price": 119990, "link": "amz/iphone15pro"},
    ]
    filtered = filter_products_by_query(products, "iPhone 15", max_results=10)
    assert len(filtered) == 1, f"Expected only base iPhone 15, got {len(filtered)}"
    assert filtered[0]["name"] == "Apple iPhone 15 128GB Black"

    print("Strict variant filtering passed!")


def test_split_brand_query_normalization():
    assert canonicalize_search_query("I PHONE 16") == "iphone 16"
    assert canonicalize_search_query("One Plus 12") == "oneplus 12"

    products = [
        {"name": "Apple iPhone 16 128GB Black", "price": 79990, "link": "amz/iphone16"},
        {"name": "Apple iPhone 16 Silicone Case", "price": 1990, "link": "amz/iphone16-case"},
    ]
    filtered = filter_products_by_query(products, "I PHONE 16", max_results=10)
    assert len(filtered) == 1, f"Expected normalized spaced brand query to match device only, got {len(filtered)}"
    assert filtered[0]["name"] == "Apple iPhone 16 128GB Black"

    print("Split-brand query normalization passed!")


def test_query_filter_rejects_nearby_model_variants():
    products = [
        {"name": "Sony WH-1000XM5 Wireless Headphones", "price": 29990, "link": "amz/xm5"},
        {"name": "Sony WH1000XM4 Bluetooth Headphones", "price": 22990, "link": "flp/xm4"},
        {"name": "Sony WF-1000XM5 Wireless Earbuds", "price": 24990, "link": "amz/wf-xm5"},
        {"name": "Sony WH-1000XM6 Wireless Headphones", "price": 39990, "link": "amz/xm6"},
    ]
    filtered = filter_products_by_query(products, "Sony WH-1000XM5", max_results=10)
    assert len(filtered) == 1, f"Expected only XM5 result, got {len(filtered)}"
    assert filtered[0]["name"] == "Sony WH-1000XM5 Wireless Headphones"

    print("Nearby model variant rejection passed!")


def test_query_filter_requires_distinctive_alpha_tokens():
    products = [
        {"name": "LG OLED evo AI 4K Smart TV", "price": 149990, "link": "amz/lg-oled"},
        {"name": "LG LED Smart TV", "price": 14990, "link": "amz/lg-led"},
        {"name": "LG OLED TV Replacement Remote", "price": 999, "link": "amz/lg-oled-remote"},
        {"name": "LG Ultragear OLED Gaming Monitor", "price": 109999, "link": "amz/lg-oled-monitor"},
    ]
    filtered = filter_products_by_query(products, "LG OLED TV", max_results=10)
    assert len(filtered) == 1, f"Expected only OLED TV result, got {len(filtered)}"
    assert filtered[0]["name"] == "LG OLED evo AI 4K Smart TV"

    print("Distinctive alpha token filtering passed!")


def test_query_filter_sanitizes_sponsored_titles():
    products = [
        {"name": "Sponsored Ad - Nike Womens Quest 6 Running Shoes", "price": 3325, "link": "amz/nike-quest"},
    ]
    filtered = filter_products_by_query(products, "Nike Shoes", max_results=10)
    assert len(filtered) == 1, "Expected sponsored-but-relevant listing to remain after sanitization"
    assert filtered[0]["name"] == "Nike Womens Quest 6 Running Shoes"

    print("Sponsored title sanitization passed!")


def test_search_intelligence_spell_correction_and_rewrites():
    info = build_search_intelligence("I phne 16")
    assert info["normalized_query"] == "iphone 16", f"Expected corrected iphone query, got {info['normalized_query']}"
    rewrite_queries = [item["query"] for item in info["rewrites"]]
    assert "iphone 16" in rewrite_queries, "Primary corrected rewrite missing"
    assert any(item["reason"] == "category-anchor" for item in info["rewrites"]), "Expected category-anchor rewrite"

    audio_info = build_search_intelligence("sony wh 1000 xm5")
    assert any("wh1000xm5" in item["query"] for item in audio_info["rewrites"]), "Expected compact audio model rewrite"

    print("Search intelligence rewrites passed!")


def test_structured_matching_rejects_wrong_laptop_chip():
    matcher = ProductMatcher()
    prod_a = {"name": "Apple MacBook Air M3 16GB 512GB", "price": 124990}
    prod_b = {"name": "Apple MacBook Air M2 16GB 512GB", "price": 109990}
    assert matcher.is_match(prod_a, prod_b) == False, "M2 incorrectly matched M3"

    print("Laptop chip mismatch rejection passed!")


def test_structured_matching_groups_same_laptop_spec_with_sku_codes():
    matcher = ProductMatcher()
    prod_a = {"name": "Apple MacBook Air M3 - (8 GB/256 GB SSD/macOS Sonoma) MRXQ3HN/A", "price": 99990}
    prod_b = {"name": "Apple MacBook Air M3 - (8 GB/256 GB SSD/macOS Sonoma) MRXT3HN/A", "price": 99990}
    assert matcher.is_match(prod_a, prod_b) == True, "Same-spec MacBook variants with seller SKU codes should group"

    print("Laptop SKU grouping passed!")


def test_query_filter_category_specific_fashion_rules():
    products = [
        {"name": "Nike Mens Quest 6 Running Shoes", "price": 3999, "link": "myn/nike-men-running"},
        {"name": "Nike Womens Sandals", "price": 2499, "link": "myn/nike-women-sandals"},
    ]
    filtered = filter_products_by_query(products, "Nike running shoes men", max_results=10)
    assert len(filtered) == 1, f"Expected only men's running shoes, got {len(filtered)}"
    assert filtered[0]["name"] == "Nike Mens Quest 6 Running Shoes"

    print("Fashion category rules passed!")


def test_query_filter_matches_kurti_and_kurta_variants():
    products = [
        {"name": "Libas Women Floral Printed Short Kurta", "price": 799, "link": "myn/short-kurta"},
        {"name": "Libas Women Printed Long Kurti", "price": 899, "link": "myn/long-kurti"},
    ]
    filtered = filter_products_by_query(products, "short kurti", max_results=10)
    assert len(filtered) == 1, f"Expected only short kurta/kurti match, got {len(filtered)}"
    assert filtered[0]["name"] == "Libas Women Floral Printed Short Kurta"

    print("Kurti/Kurta query normalization passed!")


def test_query_filter_category_specific_tv_rules():
    products = [
        {"name": "Samsung 55 Inch OLED Smart TV", "price": 89990, "link": "amz/samsung-oled-tv"},
        {"name": "Samsung 55 Inch QLED Smart TV", "price": 79990, "link": "amz/samsung-qled-tv"},
    ]
    filtered = filter_products_by_query(products, "Samsung OLED TV", max_results=10)
    assert len(filtered) == 1, f"Expected only OLED TV result, got {len(filtered)}"
    assert filtered[0]["name"] == "Samsung 55 Inch OLED Smart TV"

    print("TV category rules passed!")


def test_query_filter_rejects_accessory_slug_mismatch():
    products = [
        {
            "name": "Sony WH-1000XM5 Wireless Headphones",
            "price": 1900,
            "link": "https://www.amazon.in/SOULWIT-WH-1000XM5-Reinforced-Protective-Connectors/dp/B0FVXC9LYP/",
            "platform": "amazon",
        },
        {
            "name": "Sony WH-1000XM5 Wireless Headphones",
            "price": 27830,
            "link": "https://www.amazon.in/Sony-WH-1000XM5-Wireless-Cancelling-Headphones/dp/B09XS7JWHH/",
            "platform": "amazon",
        },
    ]
    filtered = filter_products_by_query(products, "Sony WH-1000XM5", max_results=10)
    assert len(filtered) == 1, f"Expected accessory-slug mismatch to be rejected, got {len(filtered)} results"
    assert filtered[0]["price"] == 27830

    print("Accessory slug mismatch rejection passed!")

if __name__ == "__main__":
    test_nlp_matcher()
    test_grouping()
    test_grouping_phone_vs_accessory()
    test_grouping_ignores_ram_only_title_difference()
    test_model_grouping_keeps_variants_inside_product()
    test_model_grouping_removes_color_and_size_noise()
    test_plus_sign_variant_stays_separate()
    test_capacity_variant_text_is_appended_to_scraped_name()
    test_clean_model_name_removes_empty_parentheses()
    test_grouping_fashion_family_rules_prevent_wrong_merge()
    test_exact_model_signature_mismatch_rejected()
    test_query_filter_rejects_accessories_for_devices()
    test_query_filter_soft_scores_and_keeps_numbers()
    test_query_filter_never_returns_empty_when_raw_products_exist()
    test_platform_selection_for_mobile_query()
    test_platform_validation_keeps_low_confidence_fallback_rows()
    test_specific_mobile_query_enables_grouping()
    test_platform_selection_for_fashion_query()
    test_smart_category_mapping_for_non_hardcoded_queries()
    test_query_filter_rejects_wrong_variants()
    test_split_brand_query_normalization()
    test_query_filter_rejects_nearby_model_variants()
    test_query_filter_requires_distinctive_alpha_tokens()
    test_query_filter_sanitizes_sponsored_titles()
    test_search_intelligence_spell_correction_and_rewrites()
    test_structured_matching_rejects_wrong_laptop_chip()
    test_structured_matching_groups_same_laptop_spec_with_sku_codes()
    test_query_filter_category_specific_fashion_rules()
    test_query_filter_matches_kurti_and_kurta_variants()
    test_query_filter_category_specific_tv_rules()
    test_query_filter_rejects_accessory_slug_mismatch()

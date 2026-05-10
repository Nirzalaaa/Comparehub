import asyncio
from matcher import ProductMatcher
import logging

logging.basicConfig(level=logging.INFO)

matcher = ProductMatcher()

prod_a = {"name": "boAt Rockerz 450 Bluetooth On Ear Headphones with Mic (Sage Green)", "price": 1499, "platform": "amazon"}
prod_b = {"name": "boat rockerz 450 wireless headphone", "price": 1499, "platform": "flipkart"}

print("is_match:", matcher.is_match(prod_a, prod_b))

norm_a = matcher.normalize(prod_a.get('name'))
norm_b = matcher.normalize(prod_b.get('name'))
print("norm_a:", norm_a)
print("norm_b:", norm_b)

tokens_a = matcher.tokenize(norm_a)
tokens_b = matcher.tokenize(norm_b)
print("tokens_a:", tokens_a)
print("tokens_b:", tokens_b)

imp_a, nums_a, vars_a = matcher.extract_important_tokens(tokens_a)
imp_b, nums_b, vars_b = matcher.extract_important_tokens(tokens_b)

print("imp_a:", imp_a)
print("imp_b:", imp_b)

strict = matcher.enforce_strict_validation(nums_a, nums_b, vars_a, vars_b)
print("Strict:", strict)

intersection = imp_a & imp_b
union = imp_a | imp_b
jaccard = len(intersection) / len(union) if union else 0
print("Jaccard:", jaccard)

from thefuzz import fuzz
fuzzy_score = fuzz.token_set_ratio(norm_a, norm_b)
print("Fuzzy Score:", fuzzy_score)

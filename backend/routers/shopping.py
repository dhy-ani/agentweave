"""
Shopping suggestions router.

Takes a style description + price range → returns ranked product suggestions
from real brands with live search URLs, split into within-budget and
outside-budget buckets.

No external API key required — uses the CLIP style embedding to drive
keyword extraction, then maps to a curated brand catalogue.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import re, sys, os, urllib.parse
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ai.model_cache import embed_text

router = APIRouter(prefix="/shopping", tags=["Shopping"])

# ── Brand catalogue ───────────────────────────────────────────────────────────
# Each brand: name, tier label, avg_price (mid-point of typical item range),
# price_min, price_max, search_url_template, vibe tags (for CLIP matching)

BRANDS = [
    # Budget
    dict(name="H&M",          tier="Budget",    price_min=10,  price_max=60,
         avg_price=30,  url="https://www2.hm.com/en_us/search-results.html?q={q}",
         vibe="casual affordable trendy everyday basics streetwear"),
    dict(name="Zara",         tier="Budget",    price_min=20,  price_max=90,
         avg_price=50,  url="https://www.zara.com/us/en/search?searchTerm={q}",
         vibe="minimalist chic European sophisticated casual office"),
    dict(name="ASOS",         tier="Budget",    price_min=15,  price_max=80,
         avg_price=40,  url="https://www.asos.com/us/search/?q={q}",
         vibe="trendy edgy youthful streetwear party casual"),
    dict(name="Shein",        tier="Budget",    price_min=5,   price_max=40,
         avg_price=18,  url="https://www.shein.com/catalog/search.html?q={q}",
         vibe="ultra affordable fast fashion trendy variety"),
    dict(name="Forever 21",   tier="Budget",    price_min=8,   price_max=50,
         avg_price=22,  url="https://www.forever21.com/us/shop/catalog/search/f21/q/{q}",
         vibe="youthful trendy party casual affordable"),
    # Mid-range
    dict(name="Uniqlo",       tier="Mid-Range", price_min=20,  price_max=120,
         avg_price=50,  url="https://www.uniqlo.com/us/en/search?q={q}",
         vibe="minimalist functional quality basics Japanese clean simple"),
    dict(name="Mango",        tier="Mid-Range", price_min=30,  price_max=150,
         avg_price=70,  url="https://shop.mango.com/us/search?q={q}",
         vibe="Mediterranean chic sophisticated casual office elegant"),
    dict(name="J.Crew",       tier="Mid-Range", price_min=40,  price_max=200,
         avg_price=90,  url="https://www.jcrew.com/r/search?search_term={q}",
         vibe="preppy classic American casual office smart"),
    dict(name="Banana Republic",tier="Mid-Range",price_min=50, price_max=250,
         avg_price=110, url="https://bananarepublic.gap.com/browse/search.do?searchText={q}",
         vibe="polished professional office sophisticated classic"),
    dict(name="Everlane",     tier="Mid-Range", price_min=25,  price_max=180,
         avg_price=80,  url="https://www.everlane.com/search?utf8=&query={q}",
         vibe="minimalist sustainable ethical quality basics"),
    dict(name="Free People",  tier="Mid-Range", price_min=50,  price_max=250,
         avg_price=120, url="https://www.freepeople.com/search/?q={q}",
         vibe="boho bohemian romantic flowy festival indie"),
    dict(name="Anthropologie", tier="Mid-Range",price_min=60,  price_max=300,
         avg_price=140, url="https://www.anthropologie.com/search?q={q}",
         vibe="eclectic romantic artsy boho unique statement"),
    # Premium
    dict(name="Ted Baker",    tier="Premium",   price_min=100, price_max=500,
         avg_price=220, url="https://www.tedbaker.com/us/search?q={q}",
         vibe="British elegant occasion smart luxurious print floral"),
    dict(name="Club Monaco",  tier="Premium",   price_min=80,  price_max=450,
         avg_price=200, url="https://www.clubmonaco.com/en/search?q={q}",
         vibe="modern minimalist sophisticated New York chic upscale"),
    dict(name="Theory",       tier="Premium",   price_min=150, price_max=600,
         avg_price=280, url="https://www.theory.com/search?q={q}",
         vibe="tailored professional minimalist luxury office power"),
    dict(name="Nordstrom",    tier="Premium",   price_min=80,  price_max=600,
         avg_price=200, url="https://www.nordstrom.com/sr?keyword={q}",
         vibe="curated luxury department upscale variety designer"),
    # Luxury
    dict(name="Net-a-Porter", tier="Luxury",    price_min=300, price_max=5000,
         avg_price=900, url="https://www.net-a-porter.com/en-us/shop/search?q={q}",
         vibe="luxury designer couture high fashion runway editorial"),
    dict(name="Farfetch",     tier="Luxury",    price_min=200, price_max=5000,
         avg_price=700, url="https://www.farfetch.com/shopping/women/search/items.aspx?q={q}",
         vibe="luxury designer boutique curated high end fashion week"),
]

# ── Style → clothing category map ─────────────────────────────────────────────
CATEGORIES = [
    ("blouse",        "tops"),
    ("shirt",         "tops"),
    ("t-shirt",       "tops"),
    ("sweater",       "knitwear"),
    ("blazer",        "outerwear"),
    ("jacket",        "outerwear"),
    ("coat",          "outerwear"),
    ("trench coat",   "outerwear"),
    ("trousers",      "bottoms"),
    ("jeans",         "bottoms"),
    ("skirt",         "bottoms"),
    ("shorts",        "bottoms"),
    ("dress",         "dresses"),
    ("midi dress",    "dresses"),
    ("maxi dress",    "dresses"),
    ("jumpsuit",      "dresses"),
    ("boots",         "shoes"),
    ("sneakers",      "shoes"),
    ("heels",         "shoes"),
    ("sandals",       "shoes"),
    ("loafers",       "shoes"),
    ("bag",           "accessories"),
    ("handbag",       "accessories"),
    ("scarf",         "accessories"),
    ("belt",          "accessories"),
    ("sunglasses",    "accessories"),
]

OCCASION_ITEMS = {
    "casual":     ["jeans", "t-shirt", "sneakers", "casual shirt"],
    "work":       ["trousers", "blazer", "blouse", "loafers"],
    "date night": ["dress", "heels", "clutch bag", "midi dress"],
    "formal":     ["tailored trousers", "blazer", "dress shoes", "formal dress"],
    "gym":        ["leggings", "sports top", "trainers", "gym jacket"],
    "brunch":     ["midi dress", "loafers", "casual blouse", "linen trousers"],
    "party":      ["mini dress", "heels", "statement top", "jumpsuit"],
    "outdoor":    ["jeans", "boots", "jacket", "knit sweater"],
}


def _build_search_url(brand: dict, query: str) -> str:
    return brand["url"].format(q=urllib.parse.quote_plus(query))


def _style_to_queries(caption: str, occasion: str, body_type: str, gender: str) -> list[str]:
    """Extract 3-5 searchable item keywords from a style caption."""
    occasion_items = OCCASION_ITEMS.get(occasion.lower(), ["outfit"])
    # Pull category words that appear in caption
    found = [kw for kw, _ in CATEGORIES if kw in caption.lower()]
    queries = list(dict.fromkeys(found + occasion_items))[:5]
    if not queries:
        queries = ["outfit", "dress", "top"]
    return queries


def _score_brand_for_style(brand: dict, style_vec: np.ndarray) -> float:
    vibe_vec = embed_text(brand["vibe"])
    return float(np.dot(style_vec, vibe_vec))


def _tier_label_color(tier: str) -> str:
    return {"Budget": "green", "Mid-Range": "blue",
            "Premium": "purple", "Luxury": "amber"}.get(tier, "gray")


# ── Request / Response models ─────────────────────────────────────────────────

class ShoppingRequest(BaseModel):
    style_caption: str         # From the trend recommendation
    occasion: Optional[str] = "casual"
    body_type: Optional[str] = ""
    gender: Optional[str] = ""
    price_min: float = 0
    price_max: float = 150


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/suggest")
def suggest_shopping(data: ShoppingRequest):
    try:
        style_vec = embed_text(data.style_caption).astype("float32")

        queries = _style_to_queries(
            data.style_caption, data.occasion, data.body_type, data.gender
        )

        suggestions = []
        seen_brands = set()

        for brand in BRANDS:
            if brand["name"] in seen_brands:
                continue

            # Pick the most relevant item query for this brand
            best_query = queries[0]
            best_score = -1.0
            for q in queries:
                q_vec = embed_text(f"{q} {brand['vibe']}")
                s = float(np.dot(style_vec, q_vec))
                if s > best_score:
                    best_score, best_query = s, q

            vibe_score = _score_brand_for_style(brand, style_vec)

            # Estimated price: midpoint of brand range
            est_price = brand["avg_price"]

            within_budget = data.price_min <= est_price <= data.price_max

            suggestions.append({
                "brand":         brand["name"],
                "tier":          brand["tier"],
                "tier_color":    _tier_label_color(brand["tier"]),
                "item":          best_query.title(),
                "est_price":     est_price,
                "price_range":   f"${brand['price_min']}–${brand['price_max']}",
                "within_budget": within_budget,
                "search_url":    _build_search_url(brand, f"{best_query} {data.occasion}"),
                "relevance":     round(vibe_score, 4),
                "style_note":    _style_note(brand["tier"], best_query, data.occasion),
            })
            seen_brands.add(brand["name"])

        # Sort by relevance within each budget group
        within  = sorted([s for s in suggestions if s["within_budget"]],
                         key=lambda x: -x["relevance"])
        outside = sorted([s for s in suggestions if not s["within_budget"]],
                         key=lambda x: -x["relevance"])

        return {
            "within_budget":  within,
            "outside_budget": outside,
            "search_queries": queries,
            "price_range":    {"min": data.price_min, "max": data.price_max},
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _style_note(tier: str, item: str, occasion: str) -> str:
    notes = {
        "Budget":    f"Great everyday value — find {item}s that nail the {occasion} look without breaking the bank.",
        "Mid-Range": f"Quality-to-price sweet spot — curated {item}s built to last beyond the season.",
        "Premium":   f"Investment piece — a {item} here elevates your entire {occasion} wardrobe.",
        "Luxury":    f"Statement buy — a designer {item} that defines your {occasion} identity.",
    }
    return notes.get(tier, "")

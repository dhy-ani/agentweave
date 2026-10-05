"""Pure helpers of routers/shopping.py and routers/stylegenie.py."""
import numpy as np
import pytest

from routers import shopping, stylegenie
from routers.shopping import (
    BRANDS, _build_search_url, _score_brand_for_style, _style_note, _style_to_queries, _tier_label_color,
)
from ai import score_calibration
from routers.stylegenie import TrendPrompt, _build_result, _expand_prompt, _match_description
from tests.fakes import unit_vector_for


# -- shopping ------------------------------------------------------------------------

def test_build_search_url_quotes_query_for_brand_template():
    hm = next(b for b in BRANDS if b["name"] == "H&M")
    assert _build_search_url(hm, "midi dress & co/2") == (
        "https://www2.hm.com/en_us/search-results.html?q=midi+dress+%26+co%2F2"
    )


def test_every_brand_template_has_query_placeholder_and_sane_prices():
    for brand in BRANDS:
        assert "{q}" in brand["url"]
        assert brand["price_min"] <= brand["avg_price"] <= brand["price_max"]
    assert len({b["name"] for b in BRANDS}) == len(BRANDS)


def test_style_to_queries_puts_caption_categories_before_occasion_items():
    queries = _style_to_queries("A flowing Skirt with a denim JACKET", "Work", "", "")
    assert queries == ["jacket", "skirt", "trousers", "blazer", "blouse"]


def test_style_to_queries_deduplicates_and_caps_at_five():
    queries = _style_to_queries("jeans and sneakers", "casual", "", "")
    assert queries == ["jeans", "sneakers", "t-shirt", "casual shirt"]
    many = _style_to_queries("blouse shirt sweater blazer jacket coat", "casual", "", "")
    assert len(many) == 5
    assert many == ["blouse", "shirt", "sweater", "blazer", "jacket"]


def test_style_to_queries_substring_matches_categories():
    # "t-shirt" also contains "shirt"; "midi dress" also contains "dress".
    assert _style_to_queries("a white t-shirt", "unknown", "", "") == ["shirt", "t-shirt", "outfit"]
    assert _style_to_queries("black midi dress", "gym", "", "")[:2] == ["dress", "midi dress"]


def test_style_to_queries_unknown_occasion_falls_back_to_outfit():
    assert _style_to_queries("something abstract", "space walk", "", "") == ["outfit"]


@pytest.mark.parametrize("occasion", list(shopping.OCCASION_ITEMS))
def test_style_to_queries_uses_occasion_items(occasion):
    assert _style_to_queries("", occasion, "", "") == shopping.OCCASION_ITEMS[occasion][:5]


@pytest.mark.parametrize("tier, color", [
    ("Budget", "green"), ("Mid-Range", "blue"), ("Premium", "purple"), ("Luxury", "amber"), ("Other", "gray"),
])
def test_tier_label_color(tier, color):
    assert _tier_label_color(tier) == color


def test_style_note_mentions_item_and_occasion_per_tier():
    assert _style_note("Budget", "blazer", "work") == (
        "Great everyday value — find blazers that nail the work look without breaking the bank."
    )
    assert _style_note("Mid-Range", "coat", "x") == (
        "Quality-to-price sweet spot — curated coats built to last beyond the season."
    )
    assert _style_note("Premium", "coat", "gala") == (
        "Investment piece — a coat here elevates your entire gala wardrobe."
    )
    assert _style_note("Luxury", "bag", "gala") == (
        "Statement buy — a designer bag that defines your gala identity."
    )
    assert _style_note("Unknown", "bag", "gala") == ""


def test_score_brand_for_style_is_dot_product_with_vibe_embedding():
    brand = BRANDS[0]
    style = unit_vector_for("style")
    expected = float(np.dot(style, unit_vector_for(brand["vibe"])))
    assert _score_brand_for_style(brand, style) == pytest.approx(expected)


# -- stylegenie -----------------------------------------------------------------------

@pytest.mark.parametrize("score, start", [
    (100.0, "Strong match"),
    (75.0, "Strong match"),
    (74.9, "Good match"),
    (40.0, "Good match"),
    (39.9, "Loose match"),
    (0.0, "Loose match"),
])
def test_match_description_thresholds(score, start):
    assert _match_description(score, None).startswith(start)
    assert "cluster" not in _match_description(score, None)


def test_match_description_mentions_cluster_share_rounded():
    desc = _match_description(85.0, 12.6)
    assert desc == ("Strong match to your style search. Shares its visual cluster with 13% "
                    "of the curated collection.")
    assert "0%" in _match_description(85.0, 0.0)


def test_expand_prompt_only_prompt_when_no_profile():
    assert _expand_prompt(TrendPrompt(prompt="red dress")) == ["red dress"]


def test_expand_prompt_adds_gender_and_body_type_prompts():
    data = TrendPrompt(prompt="p", gender="female", body_type="pear", weather="rainy", occasion="work")
    assert _expand_prompt(data) == [
        "p",
        "female fashion outfit work rainy",
        "flattering outfit for pear body shape work",
    ]


def test_expand_prompt_strips_missing_occasion_and_weather():
    data = TrendPrompt(prompt="p", gender="male", body_type="apple", weather=None, occasion=None)
    assert _expand_prompt(data) == ["p", "male fashion outfit", "flattering outfit for apple body shape"]


def test_build_result_fields(monkeypatch, corpus):
    # Identity calibration so the expected score is easy to read: cosine 0.876 -> 87.6.
    monkeypatch.setattr(score_calibration, "load_calibration", lambda: {"text": np.linspace(0, 1, 101)})
    result = _build_result(3, 0.876)
    assert result == {
        "result": "Style match: caption 3",
        "image": "look_3.jpg",
        "trendiness_score": 87.6,
        "match_score": 87.6,
        "similarity": 0.876,
        "cluster_share_pct": 25.0,
        "future_projection": _match_description(87.6, 25.0),
        "source": "trend-vector",
    }


def test_retrieval_sizes():
    assert (stylegenie.MMR_CANDIDATES, stylegenie.IMAGE_SEARCH_CANDIDATES, stylegenie.RESULTS) == (30, 20, 10)

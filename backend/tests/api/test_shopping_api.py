import numpy as np
import pytest

from ai import model_cache
from routers.shopping import BRANDS, OCCASION_ITEMS


def _suggest(client, **payload):
    body = {"style_caption": "a black leather jacket with jeans", **payload}
    return client.post("/shopping/suggest", json=body)


def test_suggest_splits_brands_by_budget_inclusive(client):
    body = _suggest(client, price_min=50, price_max=50).json()
    within = {s["brand"] for s in body["within_budget"]}
    assert within == {b["name"] for b in BRANDS if b["avg_price"] == 50} == {"Zara", "Uniqlo"}
    assert len(body["within_budget"]) + len(body["outside_budget"]) == len(BRANDS)
    assert all(s["within_budget"] for s in body["within_budget"])
    assert not any(s["within_budget"] for s in body["outside_budget"])
    assert body["price_range"] == {"min": 50, "max": 50}


def test_suggest_default_budget_is_0_to_150(client):
    body = _suggest(client).json()
    assert {s["brand"] for s in body["within_budget"]} == {b["name"] for b in BRANDS if b["avg_price"] <= 150}
    assert body["price_range"] == {"min": 0, "max": 150}


def test_suggest_groups_are_sorted_by_relevance(client):
    body = _suggest(client, price_min=0, price_max=100).json()
    for group in ("within_budget", "outside_budget"):
        rel = [s["relevance"] for s in body[group]]
        assert rel == sorted(rel, reverse=True)


def test_suggest_relevance_is_style_vibe_similarity(client):
    caption = "a black leather jacket with jeans"
    style = model_cache.embed_text(caption)
    body = _suggest(client, price_min=0, price_max=10_000).json()
    hm = next(s for s in body["within_budget"] if s["brand"] == "H&M")
    expected = round(float(np.dot(style, model_cache.embed_text(BRANDS[0]["vibe"]))), 4)
    assert hm["relevance"] == expected


def test_suggest_item_is_best_matching_query_for_each_brand(client):
    caption = "a black leather jacket with jeans"
    body = _suggest(client, occasion="outdoor", price_min=0, price_max=10_000).json()
    queries = body["search_queries"]
    assert queries == ["jacket", "jeans", "boots", "knit sweater"]
    style = model_cache.embed_text(caption)
    for s in body["within_budget"]:
        brand = next(b for b in BRANDS if b["name"] == s["brand"])
        scores = [float(np.dot(style, model_cache.embed_text(f"{q} {brand['vibe']}"))) for q in queries]
        best = queries[int(np.argmax(scores))]
        assert s["item"] == best.title()
        assert s["search_url"] == brand["url"].format(q=f"{best} outdoor".replace(" ", "+"))


def test_suggest_entry_shape(client):
    body = _suggest(client, occasion="work", price_min=0, price_max=10_000).json()
    theory = next(s for s in body["within_budget"] if s["brand"] == "Theory")
    assert theory["tier"] == "Premium" and theory["tier_color"] == "purple"
    assert theory["est_price"] == 280
    assert theory["price_range"] == "$150–$600"
    assert theory["style_note"].startswith("Investment piece")
    assert "work wardrobe" in theory["style_note"]


def test_suggest_everything_outside_impossible_budget(client):
    body = _suggest(client, price_min=6000, price_max=7000).json()
    assert body["within_budget"] == []
    assert len(body["outside_budget"]) == len(BRANDS)


@pytest.mark.parametrize("occasion", ["casual", "date night"])
def test_suggest_queries_include_occasion_items(client, occasion):
    body = _suggest(client, style_caption="something", occasion=occasion).json()
    assert body["search_queries"] == OCCASION_ITEMS[occasion]


def test_suggest_model_failure_returns_500(client, fake_models):
    fake_models.fail_with = RuntimeError("text tower missing")
    resp = _suggest(client)
    assert resp.status_code == 500
    assert resp.json()["detail"] == "text tower missing"


def test_suggest_requires_style_caption(client):
    assert client.post("/shopping/suggest", json={}).status_code == 422

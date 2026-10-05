import numpy as np
import pytest

from ai import model_cache
from routers.stylegenie import TrendPrompt, _expand_prompt
from tests.fakes import image_bytes, image_key, solid_image, unit_vector_for


def test_trend_vector_returns_ten_mmr_ranked_results(client, corpus):
    payload = {"prompt": "oversized denim jacket", "gender": "female", "occasion": "brunch"}
    query = model_cache.embed_text_ensemble(_expand_prompt(TrendPrompt(**payload)))
    corpus.vectors[17] = query  # exact match planted in the corpus

    resp = client.post("/stylegenie/trend_vector", json=payload)

    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 10
    assert results[0]["image"] == "look_17.jpg"
    assert results[0]["match_score"] == 100.0
    assert results[0]["result"] == "Style match: caption 17"
    assert results[0]["future_projection"].startswith("Strong match")
    assert results[0]["cluster_share_pct"] == 25.0
    assert len({r["image"] for r in results}) == 10
    for r in results:
        assert r["trendiness_score"] == r["match_score"]
        assert r["source"] == "trend-vector"


def test_trend_vector_results_come_from_top_30_candidates(client, corpus):
    query = model_cache.embed_text_ensemble(["minimal"])
    sims = corpus.vectors @ query
    top30 = {f"look_{i}.jpg" for i in np.argsort(-sims)[:30]}
    results = client.post("/stylegenie/trend_vector", json={"prompt": "minimal"}).json()["results"]
    assert {r["image"] for r in results} <= top30


def test_trend_vector_requires_prompt(client):
    assert client.post("/stylegenie/trend_vector", json={}).status_code == 422


def test_trend_vector_empty_corpus_returns_404(client, corpus):
    corpus.vectors = corpus.vectors[:0]
    resp = client.post("/stylegenie/trend_vector", json={"prompt": "anything"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No results found."


def test_trend_vector_model_failure_returns_500(client, fake_models):
    fake_models.fail_with = RuntimeError("model exploded")
    resp = client.post("/stylegenie/trend_vector", json={"prompt": "x"})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Trend vector search failed: model exploded"


def test_image_search_ranks_identical_look_first(client, corpus):
    image = solid_image((20, 140, 90))
    corpus.vectors[5] = unit_vector_for(image_key(image))
    resp = client.post("/stylegenie/image_search",
                       files={"file": ("ref.png", image_bytes(image), "image/png")})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 10
    assert results[0]["image"] == "look_5.jpg"
    assert results[0]["match_score"] == 100.0
    scores = [r["match_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_image_search_with_small_corpus_returns_all_items(client, corpus):
    corpus.vectors = corpus.vectors[:4]
    files = {"file": ("ref.png", image_bytes(solid_image()), "image/png")}
    assert len(client.post("/stylegenie/image_search", files=files).json()["results"]) == 4


def test_image_search_rejects_invalid_image(client):
    resp = client.post("/stylegenie/image_search", files={"file": ("x.png", b"nope", "image/png")})
    assert resp.status_code == 400


def test_image_search_model_failure_returns_500(client, fake_models):
    fake_models.fail_with = RuntimeError("vision down")
    resp = client.post("/stylegenie/image_search",
                       files={"file": ("ref.png", image_bytes(solid_image()), "image/png")})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Image search failed: vision down"


@pytest.mark.parametrize("path", ["/stylegenie/trend_vector", "/stylegenie/image_search"])
def test_stylegenie_rejects_get(client, path):
    assert client.get(path).status_code == 405

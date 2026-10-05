import json
import logging

import numpy as np
import pytest

from ai import artifacts, retrieval
from ai.retrieval import TrendCorpus, image_filename, match_score, mmr_rerank
from tests.fakes import make_corpus


def _unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


# -- match_score ---------------------------------------------------------------

@pytest.mark.parametrize("cos_sim, expected", [
    (0.0, 0.0),
    (1.0, 100.0),
    (0.5, 50.0),
    (0.82345, 82.3),
    (0.82351, 82.4),
    (-0.4, 0.0),
    (1.7, 100.0),
])
def test_match_score_maps_cosine_to_clamped_percentage_with_one_decimal(cos_sim, expected):
    assert match_score(cos_sim) == expected


def test_match_score_accepts_numpy_scalars():
    assert match_score(np.float32(0.25)) == 25.0


# -- image_filename ------------------------------------------------------------

@pytest.mark.parametrize("path, expected", [
    ("C:\\data\\images\\look_1.jpg", "look_1.jpg"),
    ("datasets/processedImages/look_2.jpg", "look_2.jpg"),
    ("look_3.jpg", "look_3.jpg"),
    ("", ""),
])
def test_image_filename_handles_windows_and_posix_separators(path, expected):
    assert image_filename(path) == expected


# -- TrendCorpus ---------------------------------------------------------------

def _corpus_from(vectors, **kwargs):
    vectors = np.asarray(vectors, dtype=np.float32)
    n = len(vectors)
    return TrendCorpus(vectors, {str(i): f"cap {i}" for i in range(n)},
                       {str(i): f"x/y/img{i}.jpg" for i in range(n)}, **kwargs)


def test_search_returns_top_k_indices_sorted_by_descending_similarity():
    corpus = _corpus_from([_unit(1, 0, 0), _unit(0, 1, 0), _unit(1, 1, 0), _unit(-1, 0, 0)])
    idx, sims = corpus.search(_unit(1, 0.2, 0), k=3)
    assert idx.tolist() == [0, 2, 1]
    assert np.all(np.diff(sims) <= 0)
    np.testing.assert_allclose(sims, corpus.vectors[idx] @ _unit(1, 0.2, 0), rtol=1e-6)


def test_search_with_k_larger_than_corpus_returns_whole_corpus():
    corpus = _corpus_from([_unit(1, 0), _unit(0, 1)])
    idx, sims = corpus.search(_unit(0, 1), k=50)
    assert idx.tolist() == [1, 0]
    assert len(sims) == 2


def test_search_k_one_returns_single_best_match():
    corpus = make_corpus(n=20)
    idx, sims = corpus.search(corpus.vectors[13], k=1)
    assert idx.tolist() == [13]
    assert sims[0] == pytest.approx(1.0, abs=1e-5)


def test_search_flattens_query_and_casts_to_float32():
    corpus = _corpus_from([_unit(1, 0), _unit(0, 1)])
    idx, _ = corpus.search(np.array([[0.0, 2.0]], dtype=np.float64), k=1)
    assert idx.tolist() == [1]


def test_search_on_empty_corpus_returns_no_results():
    corpus = _corpus_from(np.zeros((0, 3)))
    idx, sims = corpus.search(_unit(1, 0, 0), k=10)
    assert len(idx) == 0 and len(sims) == 0


def test_search_with_k_zero_returns_no_results():
    corpus = _corpus_from([_unit(1, 0)])
    idx, sims = corpus.search(_unit(1, 0), k=0)
    assert len(idx) == 0 and len(sims) == 0


def test_search_breaks_ties_by_corpus_order():
    corpus = _corpus_from([_unit(0, 1), _unit(1, 0), _unit(1, 0), _unit(1, 0)])
    idx, _ = corpus.search(_unit(1, 0), k=3)
    assert sorted(idx.tolist()) == [1, 2, 3]


def test_corpus_len_filename_caption_and_cluster_share_lookups():
    corpus = _corpus_from([_unit(1, 0), _unit(0, 1)],
                          clusters={"0": 3}, cluster_share_pct={3: 42.5})
    assert len(corpus) == 2
    assert corpus.filename(1) == "img1.jpg"
    assert corpus.filename(99) == ""
    assert corpus.caption(0) == "cap 0"
    assert corpus.caption(99) == "Outfit"
    assert corpus.caption(99, default="") == ""
    assert corpus.cluster_share(0) == 42.5
    assert corpus.cluster_share(1) is None


def test_cluster_share_for_cluster_zero_is_reported():
    corpus = _corpus_from([_unit(1, 0)], clusters={"0": 0}, cluster_share_pct={0: 10.0})
    assert corpus.cluster_share(0) == 10.0


# -- MMR -----------------------------------------------------------------------

def test_mmr_with_lambda_one_is_pure_relevance_order():
    query = _unit(1, 0, 0)
    cands = np.stack([_unit(0.2, 1, 0), _unit(1, 0.1, 0), _unit(1, 0.5, 0), _unit(0, 0, 1)])
    assert mmr_rerank(query, cands, top_k=4, lambda_=1.0) == [1, 2, 0, 3]


def test_mmr_prefers_diverse_item_over_near_duplicate():
    query = _unit(1, 1, 0)
    cands = np.stack([_unit(1, 0, 0), _unit(1, 0.05, 0), _unit(0, 1, 0)])
    # Pure relevance takes the near-duplicate of the best item second.
    assert mmr_rerank(query, cands, top_k=3, lambda_=1.0) == [1, 0, 2]
    assert mmr_rerank(query, cands, top_k=3, lambda_=0.7) == [1, 2, 0]


def test_mmr_with_lambda_zero_first_pick_is_first_candidate_then_most_dissimilar():
    query = _unit(1, 0)
    cands = np.stack([_unit(1, 0), _unit(1, 0.1), _unit(-1, 0.05)])
    # No relevance term: the first pick is argmax of zeros (index 0), then the
    # candidate least similar to it.
    assert mmr_rerank(query, cands, top_k=2, lambda_=0.0) == [0, 2]


# Scenario found by search so that the expected order differs from min / mean /
# sum redundancy aggregation, from pure relevance and from lambda 0, 0.4 or 0.6.
_MMR_QUERY = _unit(-0.8, -0.3, -0.9)
_MMR_CANDS = np.stack([_unit(0.3, 0.9, 0.1), _unit(-0.9, -0.3, 0.3),
                       _unit(-0.7, 0.0, -0.3), _unit(-0.9, 0.6, -0.4)])


def test_mmr_redundancy_uses_max_similarity_to_any_selected_item():
    assert mmr_rerank(_MMR_QUERY, _MMR_CANDS, top_k=4, lambda_=0.5) == [2, 0, 3, 1]


@pytest.mark.parametrize("lambda_, expected", [
    (1.0, [2, 3, 1, 0]),
    (0.6, [2, 3, 1, 0]),
    (0.4, [2, 0, 1, 3]),
    (0.0, [0, 1, 3, 2]),
])
def test_mmr_order_depends_on_lambda(lambda_, expected):
    assert mmr_rerank(_MMR_QUERY, _MMR_CANDS, top_k=4, lambda_=lambda_) == expected


def test_mmr_default_lambda_is_tuned_value():
    assert retrieval.MMR_LAMBDA == 0.7
    query = _unit(1, 1, 0)
    cands = np.stack([_unit(1, 0, 0), _unit(1, 0.05, 0), _unit(0, 1, 0)])
    assert mmr_rerank(query, cands, top_k=3) == [1, 2, 0]


def test_mmr_returns_at_most_top_k_unique_indices():
    corpus = make_corpus(n=25)
    order = mmr_rerank(corpus.vectors[0], corpus.vectors, top_k=10)
    assert len(order) == 10
    assert len(set(order)) == 10
    assert order[0] == 0


def test_mmr_with_top_k_above_candidate_count_returns_every_candidate():
    corpus = make_corpus(n=5)
    assert sorted(mmr_rerank(corpus.vectors[0], corpus.vectors, top_k=10)) == [0, 1, 2, 3, 4]


def test_mmr_with_no_candidates_returns_empty_list():
    assert mmr_rerank(_unit(1, 0), np.zeros((0, 2), dtype=np.float32)) == []


# -- get_corpus (files on disk) --------------------------------------------------

@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(retrieval, "CORPUS_FILE", str(tmp_path / "corpus_embeddings.npy"))
    monkeypatch.setattr(retrieval, "CORPUS_META_FILE", str(tmp_path / "corpus_embeddings.meta.json"))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": {"clip_vision_int8.onnx": {"sha256": "abc", "size": 1}}}))
    monkeypatch.setattr(artifacts, "MANIFEST_PATH", str(manifest))
    retrieval.get_corpus.cache_clear()
    yield tmp_path
    retrieval.get_corpus.cache_clear()


def _write_corpus(d, n=4, clusters=None, meta_sha="abc"):
    np.save(d / "corpus_embeddings.npy", np.eye(n, 8, dtype=np.float64))
    (d / "index_to_caption.json").write_text(json.dumps({str(i): f"c{i}" for i in range(n)}))
    (d / "index_to_image_path.json").write_text(json.dumps({str(i): f"a\\b\\{i}.jpg" for i in range(n)}))
    if clusters is not None:
        (d / "index_to_cluster.json").write_text(json.dumps(clusters))
    if meta_sha is not None:
        (d / "corpus_embeddings.meta.json").write_text(json.dumps({"clip_vision_sha256": meta_sha}))


def test_get_corpus_loads_vectors_as_float32_with_cluster_shares(data_dir):
    _write_corpus(data_dir, n=4, clusters={"0": 1, "1": 1, "2": 1, "3": 2})
    corpus = retrieval.get_corpus()
    assert corpus.vectors.dtype == np.float32
    assert len(corpus) == 4
    assert corpus.filename(2) == "2.jpg"
    assert corpus.caption(3) == "c3"
    assert corpus.cluster_share_pct == {1: 75.0, 2: 25.0}
    assert corpus.cluster_share(3) == 25.0


def test_get_corpus_cluster_share_is_rounded_to_one_decimal(data_dir):
    _write_corpus(data_dir, n=3, clusters={"0": 0, "1": 1, "2": 1})
    assert retrieval.get_corpus().cluster_share_pct == {0: 33.3, 1: 66.7}


def test_get_corpus_without_cluster_file_omits_cluster_signal(data_dir):
    _write_corpus(data_dir, n=2, clusters=None)
    corpus = retrieval.get_corpus()
    assert corpus.clusters == {} and corpus.cluster_share_pct == {}
    assert corpus.cluster_share(0) is None


def test_get_corpus_rejects_row_count_mismatch(data_dir):
    _write_corpus(data_dir, n=3)
    (data_dir / "index_to_image_path.json").write_text(json.dumps({"0": "a.jpg"}))
    with pytest.raises(RuntimeError, match="3 rows but index_to_image_path.json has 1"):
        retrieval.get_corpus()


def test_get_corpus_is_cached(data_dir):
    _write_corpus(data_dir, n=2)
    assert retrieval.get_corpus() is retrieval.get_corpus()


def test_stale_corpus_logs_warning(data_dir, caplog):
    _write_corpus(data_dir, n=2, meta_sha="different")
    with caplog.at_level(logging.WARNING, logger="ai.retrieval"):
        retrieval.get_corpus()
    assert "different vision model" in caplog.text


def test_fresh_corpus_does_not_warn(data_dir, caplog):
    _write_corpus(data_dir, n=2, meta_sha="abc")
    with caplog.at_level(logging.WARNING, logger="ai.retrieval"):
        retrieval.get_corpus()
    assert "different vision model" not in caplog.text


@pytest.mark.parametrize("missing", ["meta", "manifest_entry"])
def test_stale_check_is_skipped_when_metadata_is_unavailable(data_dir, caplog, missing):
    _write_corpus(data_dir, n=2, meta_sha=None if missing == "meta" else "zzz")
    if missing == "manifest_entry":
        (data_dir / "manifest.json").write_text(json.dumps({"files": {}}))
    with caplog.at_level(logging.WARNING, logger="ai.retrieval"):
        retrieval.get_corpus()
    assert "different vision model" not in caplog.text


# -- tests added from mutation-testing survivors --------------------------------------

def test_search_matches_full_sort_for_every_k():
    corpus = make_corpus(n=30, seed=3)
    query = make_corpus(n=1, seed=99).vectors[0]
    order = np.argsort(-(corpus.vectors @ query))
    for k in range(1, 31):
        idx, _ = corpus.search(query, k)
        assert idx.tolist() == order[:k].tolist()


def test_search_similarities_are_float32_for_float64_queries():
    corpus = make_corpus(n=5)
    _, sims = corpus.search(corpus.vectors[0].astype(np.float64), 3)
    assert sims.dtype == np.float32


def test_mmr_default_top_k_is_ten():
    corpus = make_corpus(n=25)
    assert len(mmr_rerank(corpus.vectors[0], corpus.vectors)) == 10


def test_stale_corpus_warning_text(data_dir, caplog):
    _write_corpus(data_dir, n=2, meta_sha="different")
    with caplog.at_level(logging.WARNING, logger="ai.retrieval"):
        retrieval.get_corpus()
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "Corpus embeddings were built with a different vision model; re-run ai/build_corpus_embeddings.py"
    ]

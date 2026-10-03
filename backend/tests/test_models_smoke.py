"""
Parity smoke test against the real ONNX models. Runs only when the model files
are present in backend/ai/models (local checkouts after scripts/publish_models.sh
or a Vercel build); skipped in CI and in mutation runs (`-m "not models"`).
"""
import os

import numpy as np
import pytest
from PIL import Image

from ai import artifacts, body_shape_classifier, model_cache, retrieval
from tests.conftest import REAL_MODEL_DIR

pytestmark = [
    pytest.mark.models,
    pytest.mark.skipif(
        not all(os.path.isfile(os.path.join(REAL_MODEL_DIR, f)) for f in artifacts.SERVING_FILES),
        reason="ONNX model files not present in backend/ai/models",
    ),
]


@pytest.fixture
def real_models(monkeypatch):
    monkeypatch.setenv("AGENTWEAVE_MODEL_DIR", REAL_MODEL_DIR)
    monkeypatch.setattr(model_cache, "_backend", None)
    monkeypatch.setattr(body_shape_classifier, "_pose", None)
    model_cache._embed_text_cached.cache_clear()
    retrieval.get_corpus.cache_clear()
    yield
    model_cache._embed_text_cached.cache_clear()
    retrieval.get_corpus.cache_clear()


def test_real_clip_embeddings_are_unit_norm_and_semantically_ordered(real_models):
    texts = model_cache.embed_texts(["a red evening dress", "a red gown", "a pickup truck"])
    assert texts.shape == (2 + 1, 512)
    np.testing.assert_allclose(np.linalg.norm(texts, axis=1), 1.0, atol=1e-4)
    assert texts[0] @ texts[1] > texts[0] @ texts[2]

    image = model_cache.embed_image(Image.new("RGB", (300, 400), (180, 20, 30)))
    assert image.shape == (512,)
    assert np.linalg.norm(image) == pytest.approx(1.0, abs=1e-4)


def test_real_corpus_search_matches_its_own_vector(real_models):
    corpus = retrieval.get_corpus()
    idx, sims = corpus.search(corpus.vectors[0], 5)
    assert idx[0] == 0 and sims[0] == pytest.approx(1.0, abs=1e-4)


def test_real_pose_model_finds_nobody_in_blank_image(real_models):
    with pytest.raises(ValueError, match="No keypoints"):
        body_shape_classifier.run_pose_estimation(Image.new("RGB", (480, 640), (255, 255, 255)))
    assert body_shape_classifier.pose_model_loaded()

from types import SimpleNamespace

import numpy as np
import pytest

from ai import model_cache
from tests.fakes import unit_vector_for


@pytest.mark.parametrize("raw, expected", [(" ONNX ", "onnx"), ("torch", "torch"), ("Torch\n", "torch")])
def test_backend_name_is_normalised(monkeypatch, raw, expected):
    monkeypatch.setenv("AGENTWEAVE_BACKEND", raw)
    assert model_cache.backend_name() == expected


def test_backend_name_defaults_to_onnx(monkeypatch):
    monkeypatch.delenv("AGENTWEAVE_BACKEND", raising=False)
    assert model_cache.backend_name() == "onnx"


def test_backend_name_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("AGENTWEAVE_BACKEND", "tensorflow")
    with pytest.raises(ValueError, match="'tensorflow'"):
        model_cache.backend_name()


def test_embed_text_is_cached_and_returns_independent_copies(fake_models):
    first = model_cache.embed_text("red dress")
    first[:] = 0  # caller mutation must not poison the cache
    second = model_cache.embed_text("red dress")
    np.testing.assert_allclose(second, unit_vector_for("red dress"))
    assert fake_models.text_calls == [["red dress"]]


def test_embed_texts_and_image_delegate_to_backend(fake_models):
    out = model_cache.embed_texts(("a", "b"))
    assert out.shape == (2, 512)
    assert fake_models.text_calls == [["a", "b"]]
    from tests.fakes import solid_image

    vec = model_cache.embed_image(solid_image())
    assert vec.shape == (512,) and fake_models.image_calls == 1


def test_embed_text_ensemble_is_normalised_mean():
    prompts = ["casual look", "summer outfit", "denim"]
    expected = np.mean([unit_vector_for(p) for p in prompts], axis=0)
    expected /= np.linalg.norm(expected)
    out = model_cache.embed_text_ensemble(prompts)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, expected, rtol=1e-5, atol=1e-6)
    assert np.linalg.norm(out) == pytest.approx(1.0, abs=1e-6)


def test_loaded_models_is_empty_before_first_use(monkeypatch):
    monkeypatch.setattr(model_cache, "_backend", None)
    assert model_cache.loaded_models() == {}


def test_loaded_models_and_lora_flag_come_from_backend(fake_models):
    assert model_cache.loaded_models() == {"clip_vision": True, "clip_text": True}
    assert model_cache.is_lora_active() is True


def test_get_backend_builds_onnx_backend_lazily_without_loading_models(monkeypatch):
    monkeypatch.setattr(model_cache, "_backend", None)
    monkeypatch.setenv("AGENTWEAVE_BACKEND", "onnx")
    backend = model_cache._get_backend()
    assert isinstance(backend, model_cache._OnnxBackend)
    assert model_cache._get_backend() is backend
    assert model_cache._backend_name == "onnx"
    assert backend.loaded() == {"clip_vision": False, "clip_text": False}
    assert backend.is_lora_active() is True  # committed manifest: lora_merged = true


def test_onnx_backend_delegates_to_clip_session_wrapper():
    backend = model_cache._OnnxBackend.__new__(model_cache._OnnxBackend)
    calls = []
    backend.clip = SimpleNamespace(
        embed_texts=lambda p: calls.append(("t", p)) or np.ones((len(p), 2)),
        embed_images=lambda imgs: calls.append(("i", len(imgs))) or np.array([[1.0, 0.0]]),
    )
    assert backend.embed_texts(["x"]).shape == (1, 2)
    np.testing.assert_array_equal(backend.embed_image("img"), [1.0, 0.0])
    assert calls == [("t", ["x"]), ("i", 1)]


def test_torch_backend_is_selected_and_delegates(monkeypatch):
    fake_mod = SimpleNamespace(
        embed_texts=lambda p: np.zeros((len(p), 512)),
        embed_image=lambda img: np.ones(512),
        is_lora_active=lambda: False,
        is_loaded=lambda: True,
    )
    monkeypatch.setattr(model_cache, "_import_sibling", lambda name: fake_mod)
    monkeypatch.setattr(model_cache, "_backend", None)
    monkeypatch.setenv("AGENTWEAVE_BACKEND", "torch")
    backend = model_cache._get_backend()
    assert isinstance(backend, model_cache._TorchBackend)
    assert backend.embed_texts(["a"]).shape == (1, 512)
    assert backend.embed_image(None).sum() == 512
    assert backend.is_lora_active() is False
    assert backend.loaded() == {"clip": True}


def test_import_sibling_resolves_within_package():
    assert model_cache._import_sibling("retrieval").__name__ == "ai.retrieval"


def test_import_sibling_falls_back_to_top_level_import_for_scripts(monkeypatch):
    # Offline scripts put ai/ on sys.path and import model_cache as a top-level module.
    import os
    import sys

    monkeypatch.syspath_prepend(os.path.dirname(model_cache.__file__))
    monkeypatch.setattr(model_cache, "__package__", "")
    monkeypatch.delitem(sys.modules, "artifacts", raising=False)
    module = model_cache._import_sibling("artifacts")
    assert module.__name__ == "artifacts"


def test_onnx_lora_flag_defaults_to_false_when_manifest_lacks_it(monkeypatch, tmp_path):
    from ai import artifacts

    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"files": {}}')
    monkeypatch.setattr(artifacts, "MANIFEST_PATH", str(manifest))
    backend = model_cache._OnnxBackend.__new__(model_cache._OnnxBackend)
    assert backend.is_lora_active() is False


def test_torch_backend_imports_clip_torch_and_passes_image(monkeypatch):
    imported = []
    seen = []
    fake_mod = SimpleNamespace(embed_image=lambda img: seen.append(img) or np.ones(2))
    monkeypatch.setattr(model_cache, "_import_sibling", lambda name: imported.append(name) or fake_mod)
    backend = model_cache._TorchBackend()
    image = object()
    backend.embed_image(image)
    assert imported == ["clip_torch"]
    assert seen == [image]

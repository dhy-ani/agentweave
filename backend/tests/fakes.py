"""
Deterministic stand-ins for the ML models, installed at the facade boundary
(ai.model_cache._backend and ai.body_shape_classifier._pose) so the routers,
model_cache and retrieval code under test stay real and no model file is needed.
"""
from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image

from ai.retrieval import TrendCorpus

DIM = 512


def unit_vector_for(key: str | bytes, dim: int = DIM) -> np.ndarray:
    """Stable pseudo-random unit vector derived from `key` (independent of PYTHONHASHSEED)."""
    data = key.encode("utf-8") if isinstance(key, str) else key
    seed = int.from_bytes(hashlib.sha256(data).digest()[:8], "little")
    vec = np.random.default_rng(seed).standard_normal(dim)
    return (vec / np.linalg.norm(vec)).astype(np.float32)


def image_key(image: Image.Image) -> bytes:
    return image.convert("RGB").tobytes()


class FakeClipBackend:
    """Mimics model_cache._OnnxBackend: unit-norm float32 [512] embeddings."""

    def __init__(self) -> None:
        self.text_calls: list[list[str]] = []
        self.image_calls = 0
        self.fail_with: Exception | None = None

    def embed_texts(self, prompts: list[str]) -> np.ndarray:
        if self.fail_with:
            raise self.fail_with
        self.text_calls.append(list(prompts))
        return np.stack([unit_vector_for(p) for p in prompts])

    def embed_image(self, image) -> np.ndarray:
        if self.fail_with:
            raise self.fail_with
        self.image_calls += 1
        return unit_vector_for(image_key(image))

    def is_lora_active(self) -> bool:
        return True

    def loaded(self) -> dict[str, bool]:
        return {"clip_vision": True, "clip_text": True}


class FakePose:
    """Mimics onnx_inference.PoseOnnx: returns preset keypoints (None = nobody detected)."""

    def __init__(self, keypoints: list[list[float]] | None = None) -> None:
        self.result = keypoints
        self.loaded = True
        self.last_image = None

    def keypoints(self, image) -> list[list[float]] | None:
        self.last_image = image
        return self.result


def body_keypoints(shoulder_w: float, hip_w: float, waist_w: float) -> list[list[float]]:
    """17 COCO keypoints with the given shoulder / hip / waist widths.

    The classifier measures the waist as elbow distance * 0.85, so the elbows
    are placed waist_w / 0.85 apart.
    """
    kpts = [[0.5, 0.5, 0.9] for _ in range(17)]
    elbow_w = waist_w / 0.85
    kpts[5], kpts[6] = [0.5 - shoulder_w / 2, 0.2, 0.9], [0.5 + shoulder_w / 2, 0.2, 0.9]
    kpts[7], kpts[8] = [0.5 - elbow_w / 2, 0.4, 0.9], [0.5 + elbow_w / 2, 0.4, 0.9]
    kpts[11], kpts[12] = [0.5 - hip_w / 2, 0.6, 0.9], [0.5 + hip_w / 2, 0.6, 0.9]
    return kpts


def make_corpus(n: int = 40, seed: int = 7, with_clusters: bool = True) -> TrendCorpus:
    rng = np.random.default_rng(seed)
    vectors = rng.standard_normal((n, DIM)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    captions = {str(i): f"caption {i}" for i in range(n)}
    # Windows-style paths, as in the committed index_to_image_path.json.
    image_paths = {str(i): f"C:\\datasets\\processedImages\\look_{i}.jpg" for i in range(n)}
    clusters: dict[str, int] = {}
    share: dict[int, float] = {}
    if with_clusters:
        clusters = {str(i): i % 4 for i in range(n)}
        share = {c: 25.0 for c in range(4)}
    return TrendCorpus(vectors, captions, image_paths, clusters, share)


def solid_image(color=(200, 30, 30), size=(64, 96)) -> Image.Image:
    return Image.new("RGB", size, color)


def image_bytes(image: Image.Image, fmt: str = "PNG", **save_kwargs) -> bytes:
    import io

    buf = io.BytesIO()
    image.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()

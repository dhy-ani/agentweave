"""
Single entry point for CLIP embeddings used by the routers and offline scripts.

Backends (selected by AGENTWEAVE_BACKEND, read on first use):
  onnx  (default) -- ONNX Runtime + numpy (ai/onnx_inference.py). This is what
                     the API serves; it never imports torch or transformers.
  torch           -- HF transformers + merged LoRA (ai/clip_torch.py), for the
                     training / evaluation scripts. Imported lazily so the
                     serving process never pays for torch.

All embeddings are float32 and L2-normalised, so a dot product is the cosine
similarity.
"""
from __future__ import annotations

import importlib
import os
import threading
from functools import lru_cache
from typing import Any

import numpy as np

CHECKPOINT = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
EMBED_DIM = 512
SUPPORTED_BACKENDS = ("onnx", "torch")

_backend: Any = None
_backend_name: str | None = None
_lock = threading.Lock()


def _import_sibling(name: str):
    # Routers import this module as `ai.model_cache`; offline scripts put ai/
    # on sys.path and import it as `model_cache`. Resolve siblings either way.
    return importlib.import_module(f"{__package__}.{name}" if __package__ else name)


class _OnnxBackend:
    def __init__(self) -> None:
        self.clip = _import_sibling("onnx_inference").ClipOnnx()

    def embed_texts(self, prompts: list[str]) -> np.ndarray:
        return self.clip.embed_texts(prompts)

    def embed_image(self, image) -> np.ndarray:
        return self.clip.embed_images([image])[0]

    def is_lora_active(self) -> bool:
        manifest = _import_sibling("artifacts").load_manifest()
        return bool(manifest.get("lora_merged", False))

    def loaded(self) -> dict[str, bool]:
        return self.clip.loaded


class _TorchBackend:
    def __init__(self) -> None:
        self.mod = _import_sibling("clip_torch")

    def embed_texts(self, prompts: list[str]) -> np.ndarray:
        return self.mod.embed_texts(prompts)

    def embed_image(self, image) -> np.ndarray:
        return self.mod.embed_image(image)

    def is_lora_active(self) -> bool:
        return self.mod.is_lora_active()

    def loaded(self) -> dict[str, bool]:
        return {"clip": self.mod.is_loaded()}


def backend_name() -> str:
    name = os.environ.get("AGENTWEAVE_BACKEND", "onnx").strip().lower()
    if name not in SUPPORTED_BACKENDS:
        raise ValueError(f"AGENTWEAVE_BACKEND must be one of {SUPPORTED_BACKENDS}, got {name!r}")
    return name


def _get_backend():
    global _backend, _backend_name
    if _backend is None:
        with _lock:
            if _backend is None:
                _backend_name = backend_name()
                _backend = _TorchBackend() if _backend_name == "torch" else _OnnxBackend()
    return _backend


def loaded_models() -> dict[str, bool]:
    return _backend.loaded() if _backend is not None else {}


def is_lora_active() -> bool:
    return _get_backend().is_lora_active()


@lru_cache(maxsize=1024)
def _embed_text_cached(prompt: str) -> np.ndarray:
    vec = _get_backend().embed_texts([prompt])[0]
    vec.setflags(write=False)
    return vec


def embed_text(prompt: str) -> np.ndarray:
    # Cached: /shopping/suggest re-embeds the same ~100 brand/vibe strings on
    # every request.
    return _embed_text_cached(prompt).copy()


def embed_texts(prompts: list[str]) -> np.ndarray:
    return _get_backend().embed_texts(list(prompts))


def embed_image(image) -> np.ndarray:
    return _get_backend().embed_image(image)


def embed_text_ensemble(prompts: list[str]) -> np.ndarray:
    avg = embed_texts(prompts).mean(axis=0)
    return (avg / np.linalg.norm(avg)).astype(np.float32)

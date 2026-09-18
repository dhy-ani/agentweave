"""
Shared helper: compute (and disk-cache) CLIP image embeddings for every
image in datasets/curated_manifest.csv.

Why this exists: train_classifier.py, tune_clustering.py, and
evaluate_retrieval.py all need embeddings for the full curated set, and
each image embed costs real wall-clock time on this CPU-only box. Without
a shared cache, running all three scripts back-to-back would re-embed the
same 205 images three separate times.

By default, embeddings come from ai.model_cache.embed_image -- i.e.
whatever the live API currently serves (LoRA-tuned once
backend/ai/data/lora_adapter/ exists, zero-shot base CLIP otherwise). The
cache is tagged by `is_lora_active()` so it's automatically invalidated
when you go from zero-shot to LoRA-tuned (or vice versa).

evaluate_retrieval.py additionally needs a *fixed* zero-shot baseline for
its ablation (i.e. still zero-shot even after the adapter exists), so a
custom `embedder` + explicit `tag` can be passed to cache that separately.
"""
import os
import sys

import numpy as np
from PIL import Image

_AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_AI_DIR)
sys.path.append(os.path.join(_AI_DIR, "..", "..", "datasets"))

from data_split import load_manifest, PROCESSED_DIR  # noqa: E402
import model_cache  # noqa: E402

CACHE_DIR = os.path.join(_AI_DIR, "data")


def get_all_embeddings(embedder=None, tag=None, force_recompute=False, verbose=True):
    """Returns (filenames, labels, vectors[N,512]) for every image in
    curated_manifest.csv, in manifest order.

    embedder: callable(PIL.Image) -> np.ndarray[512]. Defaults to
        model_cache.embed_image (the live-API embedder).
    tag: cache-key suffix. Required when a custom embedder is passed
        (so different embedders don't clobber each other's cache file).
        Defaults to "lora" / "zeroshot_base" based on model_cache's
        current state when using the default embedder.
    """
    rows = load_manifest()
    filenames = [r["filename"] for r in rows]
    labels = [r["verified_label"] for r in rows]

    if embedder is None:
        embedder = model_cache.embed_image
        if tag is None:
            tag = "lora" if model_cache.is_lora_active() else "zeroshot_base"
    elif tag is None:
        raise ValueError("get_all_embeddings: a custom embedder requires an explicit `tag`")

    cache_file = os.path.join(CACHE_DIR, f"embedding_cache_{tag}.npz")

    if not force_recompute and os.path.exists(cache_file):
        cached = np.load(cache_file, allow_pickle=True)
        if list(cached["filenames"]) == filenames:
            if verbose:
                print(f"[embedding_cache] loaded cached '{tag}' embeddings ({len(filenames)} images)")
            return filenames, labels, cached["vectors"]

    if verbose:
        print(f"[embedding_cache] computing '{tag}' embeddings for {len(filenames)} images...")
    vectors = []
    for fname in filenames:
        img = Image.open(os.path.join(PROCESSED_DIR, fname)).convert("RGB")
        vectors.append(embedder(img))
    vectors = np.asarray(vectors, dtype="float32")

    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez(cache_file, filenames=np.array(filenames), vectors=vectors)
    if verbose:
        print(f"[embedding_cache] cached to {cache_file}")
    return filenames, labels, vectors


def zero_shot_embedder():
    """A CLIP image embedder that never loads the LoRA adapter, for use as
    evaluate_retrieval.py's fixed zero-shot baseline even after the adapter
    has been trained (model_cache would otherwise always prefer it)."""
    import torch
    from transformers import CLIPModel, CLIPProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    base = CLIPModel.from_pretrained(model_cache.CHECKPOINT)
    processor = CLIPProcessor.from_pretrained(model_cache.CHECKPOINT)
    base.to(device)
    base.eval()

    def embed(image):
        inputs = processor(images=image, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            feats = model_cache._as_tensor(base.get_image_features(**inputs))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().numpy().flatten().astype("float32")

    return embed

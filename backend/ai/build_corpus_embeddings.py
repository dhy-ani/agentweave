"""
Re-embed the curated trend corpus with the serving model and save it as
ai/data/corpus_embeddings.npy (row i <-> key "i" of index_to_image_path.json).

Run this whenever the ONNX models are re-exported so corpus and query
embeddings always come from the same model:

    python ai/build_corpus_embeddings.py              # ONNX (serving) backend
    AGENTWEAVE_BACKEND=torch python ai/build_corpus_embeddings.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from ai import artifacts, model_cache  # noqa: E402
from ai.retrieval import CORPUS_FILE, CORPUS_META_FILE, DATA_DIR, image_filename  # noqa: E402

IMAGE_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "datasets", "processedImages"))


def main() -> None:
    with open(os.path.join(DATA_DIR, "index_to_image_path.json"), encoding="utf-8") as f:
        index_to_path = json.load(f)

    vectors = np.zeros((len(index_to_path), model_cache.EMBED_DIM), dtype=np.float32)
    for i in range(len(index_to_path)):
        path = os.path.join(IMAGE_DIR, image_filename(index_to_path[str(i)]))
        with Image.open(path) as img:
            vectors[i] = model_cache.embed_image(img.convert("RGB"))

    np.save(CORPUS_FILE, vectors)
    meta = {"backend": model_cache.backend_name(), "count": len(vectors)}
    if meta["backend"] == "onnx":
        meta["clip_vision_sha256"] = artifacts.load_manifest()["files"]["clip_vision_int8.onnx"]["sha256"]
    with open(CORPUS_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    print(f"Saved {vectors.shape} corpus embeddings to {CORPUS_FILE}")


if __name__ == "__main__":
    main()

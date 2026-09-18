"""
Build the live FAISS retrieval index + metadata used by backend/routers/stylegenie.py.

Fixes vs. the original script (Part A1 of the ML overhaul plan):
  - The original called `merge_clip_with_captions(path)` with a single image
    path, but that function's real signature is
    `merge_clip_with_captions(image_dir, clip_vector_path, output_path, device)`
    — a batch operation over a precomputed CLIP-vectors JSON, not a per-image
    captioner. That call would raise a TypeError (missing required args) the
    moment it actually ran, which combined with an `os.path.exists("ai/caption_images.py")`
    guard meant the script would only get partway through before crashing —
    explaining why the shipped `ai/data/*` artifacts only covered 77 of the
    283 raw images. Fixed by loading BLIP once (via ai.caption_images) and
    generating a caption per image directly with `generate_caption`.
  - Reads from datasets/curated_manifest.csv + datasets/processedImages/
    (the curated, deduped, quality-filtered, relabeled dataset from
    datasets/curate_dataset.py) instead of the raw uncurated scrape, so the
    index now covers the full curated set instead of truncating partway
    through an uncurated 283-image folder.
  - Uses ai.model_cache.embed_image (the same singleton the live API uses)
    instead of ai.extract_vector.extract_image_vector, which reloaded its own
    CLIP model from scratch on every call. This also means the index is
    automatically built from LoRA-adapted embeddings once a trained adapter
    is present (see ai/model_cache.py), keeping ingestion and serving in sync.
  - No longer generates ai/data/index_to_timestamp.json. The old file was
    populated with a fresh `datetime.now()` for every single image (not even
    randomized — see ai/generate_timestamps.py for the actually-random
    version used elsewhere), and it fed a fabricated "trendiness" score.
    That's removed from the live path in routers/stylegenie.py (Part A7);
    ai/generate_timestamps.py itself is left in place but unused.
  - Additionally writes ai/data/index_to_label.json (verified aesthetic
    category per index) so cluster-share stats and evaluation scripts don't
    have to re-derive labels from filenames.
"""
import csv
import json
import os
import sys

import faiss
import numpy as np
from tqdm import tqdm
from PIL import Image

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ai.model_cache import embed_image
from ai.caption_images import load_blip_model, generate_caption

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "datasets"))
PROCESSED_DIR = os.path.join(DATASETS_DIR, "processedImages")
RAW_DIR = os.path.join(DATASETS_DIR, "rawImages")
MANIFEST_PATH = os.path.join(DATASETS_DIR, "curated_manifest.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "ai", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

VECTOR_FILE = os.path.join(OUTPUT_DIR, "image_vectors.npy")
CAPTION_FILE = os.path.join(OUTPUT_DIR, "index_to_caption.json")
IMAGE_PATH_FILE = os.path.join(OUTPUT_DIR, "index_to_image_path.json")
LABEL_FILE = os.path.join(OUTPUT_DIR, "index_to_label.json")
INDEX_FILE = os.path.join(OUTPUT_DIR, "trends.index")

EMBED_DIM = 512


def _load_manifest_rows():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
        image_dir = PROCESSED_DIR
        print(f"[generate_faiss_data] using curated manifest: {len(rows)} images from {image_dir}")
        return rows, image_dir

    # Fallback so this can still run before curation exists (e.g. for a
    # smoke test) — labels are derived straight from filenames.
    print("[generate_faiss_data] WARNING: no curated_manifest.csv found; "
          "falling back to uncurated datasets/rawImages with filename-derived labels")
    sys.path.append(DATASETS_DIR)
    from category_labels import label_from_filename

    rows = []
    for fname in sorted(os.listdir(RAW_DIR)):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        try:
            label = label_from_filename(fname)
        except ValueError:
            label = "unknown"
        rows.append({"filename": fname, "verified_label": label})
    return rows, RAW_DIR


def main():
    rows, image_dir = _load_manifest_rows()
    if not rows:
        raise SystemExit("No images found to index.")

    blip_model, blip_processor = load_blip_model()

    vectors = []
    index_to_caption = {}
    index_to_image_path = {}
    index_to_label = {}

    idx = 0
    for row in tqdm(rows, desc="Embedding + captioning"):
        fname = row["filename"]
        path = os.path.join(image_dir, fname)
        if not os.path.isfile(path):
            print(f"  skip missing file: {fname}")
            continue

        try:
            img = Image.open(path).convert("RGB")
            vec = embed_image(img)
            caption = generate_caption(img, blip_model, blip_processor)
            if not caption or caption.isspace():
                caption = f"Outfit from {fname}"
        except Exception as e:
            print(f"  skip {fname}: {e}")
            continue

        vectors.append(vec)
        index_to_caption[str(idx)] = caption
        index_to_image_path[str(idx)] = path
        index_to_label[str(idx)] = row.get("verified_label", "unknown")
        idx += 1

    if not vectors:
        raise SystemExit("No vectors were produced — aborting without overwriting existing index.")

    vectors_arr = np.array(vectors).astype("float32")
    np.save(VECTOR_FILE, vectors_arr)

    with open(CAPTION_FILE, "w") as f:
        json.dump(index_to_caption, f, indent=2)
    with open(IMAGE_PATH_FILE, "w") as f:
        json.dump(index_to_image_path, f, indent=2)
    with open(LABEL_FILE, "w") as f:
        json.dump(index_to_label, f, indent=2)

    dim = vectors_arr.shape[1]
    assert dim == EMBED_DIM, f"expected {EMBED_DIM}-d embeddings, got {dim}"
    index = faiss.IndexFlatL2(dim)
    index.add(vectors_arr)
    faiss.write_index(index, INDEX_FILE)

    print(f"[generate_faiss_data] indexed {len(vectors)}/{len(rows)} images "
          f"(dim={dim}) -> {INDEX_FILE}")


if __name__ == "__main__":
    main()

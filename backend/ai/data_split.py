"""
Shared, reproducible train/val/test split over datasets/curated_manifest.csv,
stratified per verified_label. Every script that needs a held-out split
(finetune_clip_lora.py, train_classifier.py, evaluate_retrieval.py) uses this
so the same images are held out everywhere -- otherwise a "zero-shot vs.
fine-tuned" comparison would be meaningless.

Cached to backend/ai/data/split.json after the first call so re-runs are
stable even if manifest row order changes.
"""
import csv
import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
MANIFEST_PATH = os.path.join(DATASETS_DIR, "curated_manifest.csv")
PROCESSED_DIR = os.path.join(DATASETS_DIR, "processedImages")
SPLIT_CACHE = os.path.join(BASE_DIR, "data", "split.json")

SEED = 42
TRAIN_FRAC = 0.7
VAL_FRAC = 0.15
# remainder (~0.15) is test


def load_manifest():
    with open(MANIFEST_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def _stratified_split(rows, seed=SEED):
    by_label = {}
    for row in rows:
        by_label.setdefault(row["verified_label"], []).append(row["filename"])

    rng = random.Random(seed)
    train, val, test = [], [], []
    for label, files in by_label.items():
        files = files[:]
        rng.shuffle(files)
        n = len(files)
        if n == 1:
            train += files  # nothing to hold out
            continue
        if n == 2:
            train += files[:1]
            val += files[1:]
            continue
        n_test = max(1, round(n * (1 - TRAIN_FRAC - VAL_FRAC)))
        n_val = max(1, round(n * VAL_FRAC))
        # keep at least 1 for train regardless of how small the class is
        n_test = min(n_test, n - 2)
        n_val = min(n_val, n - n_test - 1)
        test_f = files[:n_test]
        val_f = files[n_test:n_test + n_val]
        train_f = files[n_test + n_val:]
        train += train_f
        val += val_f
        test += test_f
    return train, val, test


def get_splits(force_rebuild=False):
    """Returns (train_files, val_files, test_files) -- lists of filenames
    (relative to datasets/processedImages/)."""
    if not force_rebuild and os.path.exists(SPLIT_CACHE):
        with open(SPLIT_CACHE) as f:
            d = json.load(f)
        return d["train"], d["val"], d["test"]

    rows = load_manifest()
    train, val, test = _stratified_split(rows)
    os.makedirs(os.path.dirname(SPLIT_CACHE), exist_ok=True)
    with open(SPLIT_CACHE, "w") as f:
        json.dump({"train": train, "val": val, "test": test, "seed": SEED}, f, indent=2)
    return train, val, test


def label_map():
    """filename -> verified_label"""
    return {row["filename"]: row["verified_label"] for row in load_manifest()}


if __name__ == "__main__":
    train, val, test = get_splits(force_rebuild=True)
    labels = label_map()
    print(f"train={len(train)} val={len(val)} test={len(test)}")
    from collections import Counter
    print("train label coverage:", len(set(labels[f] for f in train)))
    print("val label coverage:", len(set(labels[f] for f in val)))
    print("test label coverage:", len(set(labels[f] for f in test)))

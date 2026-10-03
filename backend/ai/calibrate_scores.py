"""
Offline: fit the match-score calibration used by ai/score_calibration.py.

For each modality, collect cosine similarities of known-relevant pairs in the
curated set (same verified aesthetic label) using the serving embeddings, then
store 101 quantiles (0th..100th percentile):

  text   category prompt (datasets/category_labels.py) vs. images of that label
  image  every image vs. every other image of the same label

Also reports how well calibrated scores separate relevant from irrelevant
pairs (ROC AUC), so the mapping's usefulness is measured, not assumed.

Usage (from backend/, serving models present):
    python ai/calibrate_scores.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "..", "datasets"))

from ai import model_cache  # noqa: E402
from ai.retrieval import DATA_DIR, get_corpus  # noqa: E402
from ai.score_calibration import CALIBRATION_FILE  # noqa: E402
from category_labels import LABEL_TO_PROMPT  # noqa: E402

QUANTILES = np.linspace(0, 100, 101)


def roc_auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Probability a random relevant pair outscores a random irrelevant one."""
    scores = np.concatenate([pos, neg])
    ranks = scores.argsort().argsort() + 1.0
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main() -> None:
    corpus = get_corpus()
    with open(os.path.join(DATA_DIR, "index_to_label.json"), encoding="utf-8") as f:
        index_labels = json.load(f)
    labels = np.array([index_labels[str(i)] for i in range(len(corpus))])
    vectors = corpus.vectors.astype(np.float64)

    text_pos, text_neg = [], []
    for label, prompt in LABEL_TO_PROMPT.items():
        if not (labels == label).any():
            continue
        sims = vectors @ model_cache.embed_text(prompt).astype(np.float64)
        text_pos.append(sims[labels == label])
        text_neg.append(sims[labels != label])
    text_pos, text_neg = np.concatenate(text_pos), np.concatenate(text_neg)

    image_sims = vectors @ vectors.T
    same = labels[:, None] == labels[None, :]
    off_diag = ~np.eye(len(labels), dtype=bool)
    image_pos, image_neg = image_sims[same & off_diag], image_sims[~same]

    out = {"method": "empirical quantiles of same-aesthetic pair similarity", "model_backend": model_cache.backend_name()}
    for name, pos, neg in (("text", text_pos, text_neg), ("image", image_pos, image_neg)):
        out[name] = {
            "quantiles": np.round(np.percentile(pos, QUANTILES), 6).tolist(),
            "n_relevant_pairs": int(len(pos)),
            "n_irrelevant_pairs": int(len(neg)),
            "relevant_median": round(float(np.median(pos)), 4),
            "irrelevant_median": round(float(np.median(neg)), 4),
            "roc_auc": round(roc_auc(pos, neg), 4),
        }
        print(f"{name}: relevant median {out[name]['relevant_median']}, irrelevant median "
              f"{out[name]['irrelevant_median']}, AUC {out[name]['roc_auc']} ({len(pos)} relevant pairs)")

    with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {CALIBRATION_FILE}")


if __name__ == "__main__":
    main()

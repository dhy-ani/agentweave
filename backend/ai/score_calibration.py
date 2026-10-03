"""
Turns raw cosine similarity into a match score people can read.

CLIP similarities live on very different scales per modality: a text prompt
rarely scores above ~0.35 against even its best image, while image-to-image
pairs of the same look sit around 0.6-0.9. Showing raw cosine as a percentage
made every text result read as a "29% / loose" match.

ai/calibrate_scores.py measures, per modality, the similarities of known
same-aesthetic pairs in the curated set and stores their quantiles. A score of
50 means "as close as a typical same-aesthetic pair"; 90 means closer than
90% of them. Without the calibration file the raw cosine percentage is used.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

CALIBRATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "score_calibration.json")
MODALITIES = ("text", "image")


@lru_cache(maxsize=1)
def load_calibration(path: str = CALIBRATION_FILE) -> dict[str, np.ndarray]:
    if not os.path.exists(path):
        logger.warning("No score calibration at %s; match scores fall back to raw cosine", path)
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {m: np.asarray(data[m]["quantiles"], dtype=np.float64) for m in MODALITIES if m in data}


def calibrated_score(cos_sim: float, modality: str, calibration: dict[str, np.ndarray] | None = None) -> float:
    """Percentile (0-100) of `cos_sim` among same-aesthetic pairs for this modality."""
    table = (load_calibration() if calibration is None else calibration).get(modality)
    if table is None or len(table) < 2:
        return round(100.0 * max(0.0, min(1.0, float(cos_sim))), 1)
    levels = np.linspace(0.0, 100.0, len(table))
    return round(float(np.interp(float(cos_sim), table, levels)), 1)

import json

import numpy as np
import pytest

from ai import score_calibration
from ai.score_calibration import calibrated_score, load_calibration

TEXT = np.array([0.10, 0.20, 0.30])  # 0th, 50th, 100th percentile of relevant pairs
IMAGE = np.array([0.40, 0.60, 0.80])
CAL = {"text": TEXT, "image": IMAGE}


@pytest.mark.parametrize("cos_sim, expected", [
    (0.10, 0.0),
    (0.20, 50.0),
    (0.25, 75.0),
    (0.30, 100.0),
    (0.05, 0.0),    # below the weakest relevant pair clamps to 0
    (0.95, 100.0),  # above the strongest clamps to 100
])
def test_text_scores_are_percentiles_of_relevant_pairs(cos_sim, expected):
    assert calibrated_score(cos_sim, "text", CAL) == expected


def test_modalities_use_their_own_scale():
    assert calibrated_score(0.30, "text", CAL) == 100.0
    assert calibrated_score(0.30, "image", CAL) == 0.0
    assert calibrated_score(0.70, "image", CAL) == 75.0


def test_scores_are_monotonic_in_similarity():
    sims = np.linspace(-1, 1, 41)
    scores = [calibrated_score(s, "text", CAL) for s in sims]
    assert scores == sorted(scores)


def test_rounds_to_one_decimal():
    assert calibrated_score(0.2123, "text", CAL) == 56.1


@pytest.mark.parametrize("cal", [{}, {"text": np.array([0.5])}])
def test_falls_back_to_raw_cosine_without_a_usable_table(cal):
    assert calibrated_score(0.291, "text", cal) == 29.1
    assert calibrated_score(1.7, "text", cal) == 100.0
    assert calibrated_score(-0.2, "text", cal) == 0.0


def test_unknown_modality_falls_back_to_raw_cosine():
    assert calibrated_score(0.5, "audio", CAL) == 50.0


def test_load_calibration_reads_quantiles(tmp_path):
    path = tmp_path / "cal.json"
    path.write_text(json.dumps({"text": {"quantiles": [0.1, 0.3]}, "image": {"quantiles": [0.5, 0.9]}, "method": "x"}), encoding="utf-8")
    load_calibration.cache_clear()
    try:
        cal = load_calibration(str(path))
    finally:
        load_calibration.cache_clear()
    assert set(cal) == {"text", "image"}
    np.testing.assert_allclose(cal["text"], [0.1, 0.3])
    assert cal["image"].dtype == np.float64


def test_missing_calibration_file_returns_empty(tmp_path):
    load_calibration.cache_clear()
    try:
        assert load_calibration(str(tmp_path / "missing.json")) == {}
    finally:
        load_calibration.cache_clear()


def test_default_uses_the_committed_calibration_file(monkeypatch):
    monkeypatch.setattr(score_calibration, "load_calibration", lambda: CAL)
    assert calibrated_score(0.20, "text") == 50.0


def test_committed_calibration_is_sorted_and_separates_modalities():
    load_calibration.cache_clear()
    cal = load_calibration()
    load_calibration.cache_clear()
    for name in ("text", "image"):
        q = cal[name]
        assert len(q) == 101
        assert np.all(np.diff(q) >= 0)
    assert np.median(cal["text"]) < np.median(cal["image"])


def test_a_two_point_table_is_enough_to_calibrate():
    cal = {"text": np.array([0.2, 0.4])}
    assert calibrated_score(0.3, "text", cal) == 50.0


def test_fallback_rounds_to_one_decimal():
    assert calibrated_score(0.12345, "text", {}) == 12.3

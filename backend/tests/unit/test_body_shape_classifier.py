import pytest

from ai import body_shape_classifier as bsc
from ai import model_cache
from ai.body_shape_classifier import classify_body_shape, run_pose_estimation
from tests.fakes import body_keypoints


# sh = shoulder width / hip width, wh = waist width / hip width (hip width = 1).
@pytest.mark.parametrize("sh, wh, expected", [
    (1.30, 0.60, "hourglass"),
    (1.15, 0.79, "hourglass"),          # sh boundary is inclusive
    (1.15, 0.80, "inverted_triangle"),  # wh boundary flips to inverted triangle
    (1.40, 1.00, "inverted_triangle"),
    (1.149, 0.79, "rectangle"),         # just below the wide-shoulder threshold
    (0.70, 0.70, "pear"),
    (0.849, 0.849, "pear"),
    (0.85, 0.50, "rectangle"),          # sh = 0.85 is no longer narrow
    (0.50, 0.85, "rectangle"),          # wh = 0.85 is no longer narrow
    (0.50, 0.95, "rectangle"),          # wide waist but narrow shoulders: not apple
    (1.00, 0.90, "apple"),              # wh boundary is inclusive
    (0.85, 0.95, "apple"),              # sh lower bound inclusive
    (1.149, 0.95, "apple"),
    (1.00, 0.899, "rectangle"),
    (1.00, 0.85, "rectangle"),
])
def test_classify_body_shape_rules(sh, wh, expected):
    assert classify_body_shape(body_keypoints(shoulder_w=sh, hip_w=1.0, waist_w=wh)) == expected


def test_classification_is_scale_invariant():
    small = body_keypoints(shoulder_w=0.13, hip_w=0.10, waist_w=0.06)
    assert classify_body_shape(small) == "hourglass"


def test_zero_hip_width_returns_unknown():
    assert classify_body_shape(body_keypoints(shoulder_w=0.3, hip_w=0.0, waist_w=0.2)) == "unknown"


def test_hip_width_just_below_guard_returns_unknown():
    assert classify_body_shape(body_keypoints(shoulder_w=0.3, hip_w=0.99e-4, waist_w=0.2)) == "unknown"


def test_hip_width_at_guard_threshold_is_classified():
    kpts = body_keypoints(shoulder_w=2e-4, hip_w=1.0, waist_w=1e-4)
    kpts[11], kpts[12] = [0.0, 0.6], [1e-4, 0.6]
    assert classify_body_shape(kpts) != "unknown"


def test_waist_proxy_applies_085_scale_to_elbow_distance():
    # Elbows 1.0 apart -> waist 0.85 (not apple); 1.06 apart -> waist 0.901 (apple).
    kpts = body_keypoints(shoulder_w=1.0, hip_w=1.0, waist_w=0.85)
    kpts[7], kpts[8] = [0.0, 0.4], [1.0, 0.4]
    assert classify_body_shape(kpts) == "rectangle"
    kpts[7], kpts[8] = [0.0, 0.4], [1.06, 0.4]
    assert classify_body_shape(kpts) == "apple"


def test_distances_use_both_coordinates_and_ignore_visibility():
    kpts = body_keypoints(shoulder_w=1.3, hip_w=1.0, waist_w=0.6)
    # Same hip width laid out vertically, with an extreme visibility score.
    kpts[11], kpts[12] = [0.5, 0.0, 99.0], [0.5, 1.0, -99.0]
    assert classify_body_shape(kpts) == "hourglass"


@pytest.mark.parametrize("sh, wh, expected", [
    # Ratios are rounded to 3 decimals before the thresholds are applied.
    (1.1496, 0.60, "hourglass"),
    (1.1494, 0.60, "rectangle"),
    (1.30, 0.7996, "inverted_triangle"),
    (1.30, 0.7994, "hourglass"),
])
def test_ratios_are_rounded_to_three_decimals(sh, wh, expected):
    assert classify_body_shape(body_keypoints(shoulder_w=sh, hip_w=1.0, waist_w=wh)) == expected


def test_ratios_are_relative_to_hip_width():
    # Hip width 2: shoulders 2.6 / waist 1.2 are ratios 1.3 / 0.6.
    assert classify_body_shape(body_keypoints(shoulder_w=2.6, hip_w=2.0, waist_w=1.2)) == "hourglass"
    assert classify_body_shape(body_keypoints(shoulder_w=2.6, hip_w=2.0, waist_w=1.9)) == "inverted_triangle"


def test_dist_is_euclidean_on_xy():
    assert bsc._dist([0, 0, 5], [3, 4, -5]) == pytest.approx(5.0)


# -- run_pose_estimation ---------------------------------------------------------

def test_run_pose_estimation_returns_keypoints_from_onnx_pose(fake_pose):
    fake_pose.result = body_keypoints(1.3, 1.0, 0.6)
    image = object()
    assert run_pose_estimation(image) == fake_pose.result
    assert fake_pose.last_image is image


@pytest.mark.parametrize("result", [None, []])
def test_run_pose_estimation_without_person_raises(fake_pose, result):
    fake_pose.result = result
    with pytest.raises(ValueError, match="No keypoints detected"):
        run_pose_estimation(object())


def test_run_pose_estimation_with_too_few_keypoints_raises(fake_pose):
    fake_pose.result = [[0.1, 0.1]] * 12
    with pytest.raises(ValueError) as exc:
        run_pose_estimation(object())
    assert str(exc.value) == "Incomplete keypoints. Make sure the image shows a full body."


def test_run_pose_estimation_accepts_exactly_thirteen_keypoints(fake_pose):
    fake_pose.result = [[0.1, 0.1]] * 13
    assert len(run_pose_estimation(object())) == 13


def test_torch_backend_uses_ultralytics(monkeypatch):
    monkeypatch.setenv("AGENTWEAVE_BACKEND", "torch")
    expected = body_keypoints(1.0, 1.0, 1.0)
    image = object()
    seen = []
    monkeypatch.setattr(bsc, "_ultralytics_keypoints", lambda img: seen.append(img) or expected)
    monkeypatch.setattr(bsc, "_get_pose", lambda: pytest.fail("ONNX pose must not be used"))
    assert run_pose_estimation(image) == expected
    assert seen == [image]


class _FakeTensor:
    def __init__(self, value):
        self.value = value

    def cpu(self):
        return self

    def numpy(self):
        import numpy as np

        return np.asarray(self.value)


class _FakeKeypoints:
    def __init__(self, people):
        self.xyn = [_FakeTensor(p) for p in people]

    def __len__(self):
        return len(self.xyn)


def _fake_yolo(results):
    calls = []

    def model(image, verbose):
        calls.append((image, verbose))
        return results

    return model, calls


def test_ultralytics_keypoints_returns_first_person_xyn(monkeypatch):
    first = [[0.1, 0.2]] * 17
    model, calls = _fake_yolo([type("R", (), {"keypoints": _FakeKeypoints([first, [[0.9, 0.9]] * 17])})()])
    monkeypatch.setattr(bsc, "_ultralytics_model", lambda: model)
    image = object()
    assert bsc._ultralytics_keypoints(image) == first
    assert calls == [(image, False)]


@pytest.mark.parametrize("results", [
    [],
    [type("R", (), {"keypoints": None})()],
    [type("R", (), {"keypoints": _FakeKeypoints([])})()],
])
def test_ultralytics_keypoints_without_person_returns_none(monkeypatch, results):
    model, _ = _fake_yolo(results)
    monkeypatch.setattr(bsc, "_ultralytics_model", lambda: model)
    assert bsc._ultralytics_keypoints(object()) is None


def test_pose_model_loaded_reflects_lazy_pose(monkeypatch, fake_pose):
    assert bsc.pose_model_loaded() is True
    fake_pose.loaded = False
    assert bsc.pose_model_loaded() is False
    monkeypatch.setattr(bsc, "_pose", None)
    assert bsc.pose_model_loaded() is False


def test_get_pose_creates_onnx_pose_once_without_loading_model(monkeypatch):
    monkeypatch.setattr(bsc, "_pose", None)
    pose = bsc._get_pose()
    assert type(pose).__name__ == "PoseOnnx"
    assert pose.loaded is False
    assert bsc._get_pose() is pose
    assert model_cache.backend_name() == "onnx"

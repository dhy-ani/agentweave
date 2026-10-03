"""Pre/post-processing of the ONNX path, tested with synthetic arrays and stub sessions."""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from ai import onnx_inference as oi
from ai.onnx_inference import (
    CLIP_MEAN, CLIP_PAD_ID, CLIP_STD, ClipOnnx, PoseOnnx, letterbox, preprocess_clip_image,
)

BOS_ID = 49406


class StubSession:
    """Stands in for ort.InferenceSession: records feeds, returns preset outputs."""

    def __init__(self, output, input_name="images"):
        self.output = output
        self.feeds = None
        self._input_name = input_name

    def get_inputs(self):
        return [SimpleNamespace(name=self._input_name)]

    def run(self, output_names, feeds):
        self.feeds = feeds
        return [self.output]


def _expected_pixel(rgb):
    return (np.array(rgb, dtype=np.float32).reshape(3, 1, 1) / 255.0 - CLIP_MEAN) / CLIP_STD


# -- CLIP image preprocessing ----------------------------------------------------

@pytest.mark.parametrize("size", [(224, 224), (300, 600), (640, 320), (100, 50)])
def test_clip_preprocess_outputs_normalised_224_square(size):
    out = preprocess_clip_image(Image.new("RGB", size, (10, 120, 250)))
    assert out.shape == (3, 224, 224)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, np.broadcast_to(_expected_pixel((10, 120, 250)), out.shape), atol=1e-5)


def test_clip_preprocess_converts_non_rgb_modes():
    out = preprocess_clip_image(Image.new("L", (50, 50), 255))
    np.testing.assert_allclose(out[:, 0, 0], _expected_pixel((255, 255, 255)).ravel(), atol=1e-5)


def _three_bands(size, horizontal):
    """Image split into red / green / blue thirds along the long side (quarter, half, quarter)."""
    img = Image.new("RGB", size, (0, 255, 0))
    w, h = size
    if horizontal:
        img.paste((255, 0, 0), (0, 0, w // 4, h))
        img.paste((0, 0, 255), (3 * w // 4, 0, w, h))
    else:
        img.paste((255, 0, 0), (0, 0, w, h // 4))
        img.paste((0, 0, 255), (0, 3 * h // 4, w, h))
    return img


@pytest.mark.parametrize("size, horizontal", [((300, 600), False), ((600, 300), True)])
def test_clip_preprocess_center_crops_the_long_side(size, horizontal):
    # After resizing the short side to 224 the long side is 448; the centre
    # 224 crop is exactly the green middle half.
    out = preprocess_clip_image(_three_bands(size, horizontal))
    green = _expected_pixel((0, 255, 0)).ravel()
    inner = out[:, 8:-8, 8:-8].reshape(3, -1)
    np.testing.assert_allclose(inner.mean(axis=1), green, atol=1e-3)
    np.testing.assert_allclose(out[:, 112, 112], green, atol=1e-4)


def test_clip_preprocess_keeps_aspect_ratio_when_resizing():
    # Portrait 100x300 resizes to 224x672; the centre crop (rows 224..448)
    # is exactly the white middle third of the original.
    img = Image.new("RGB", (100, 300), (0, 0, 0))
    img.paste((255, 255, 255), (0, 100, 100, 200))
    out = preprocess_clip_image(img)
    white = _expected_pixel((255, 255, 255)).ravel()
    np.testing.assert_allclose(out[:, 6:-6, :].reshape(3, -1).mean(axis=1), white, atol=1e-3)


# -- CLIP tokenizer (committed ai/assets/clip_tokenizer.json) ----------------------

def test_tokenize_adds_bos_eos_and_pads_batch_to_longest():
    ids, mask = ClipOnnx().tokenize(["a red dress", "a long flowing red summer dress"])
    assert ids.dtype == np.int64 and mask.dtype == np.int64
    assert ids.shape == mask.shape and ids.shape[0] == 2
    assert ids[0, 0] == BOS_ID and ids[1, 0] == BOS_ID
    short_len = int(mask[0].sum())
    assert ids[0, short_len - 1] == CLIP_PAD_ID           # EOS
    assert np.all(ids[0, short_len:] == CLIP_PAD_ID)       # padding
    assert np.all(mask[0, short_len:] == 0)
    assert mask[1].all()


def test_tokenize_truncates_to_77_tokens_keeping_eos():
    ids, mask = ClipOnnx().tokenize(["word " * 200])
    assert ids.shape == (1, oi.CLIP_MAX_TOKENS)
    assert ids[0, 0] == BOS_ID and ids[0, -1] == CLIP_PAD_ID
    assert mask.sum() == 77


def test_tokenizer_is_loaded_once():
    clip = ClipOnnx()
    assert clip._get_tokenizer() is clip._get_tokenizer()


# -- CLIP embeddings with stub sessions -------------------------------------------

def test_embed_texts_feeds_token_ids_and_returns_unit_vectors():
    clip = ClipOnnx()
    session = StubSession(np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float32))
    clip._text = SimpleNamespace(get=lambda: session)
    out = clip.embed_texts(["red dress", "blue jeans"])
    np.testing.assert_allclose(out, [[0.6, 0.8], [0.0, 1.0]], rtol=1e-6)
    assert out.dtype == np.float32
    ids, mask = clip.tokenize(["red dress", "blue jeans"])
    np.testing.assert_array_equal(session.feeds["input_ids"], ids)
    np.testing.assert_array_equal(session.feeds["attention_mask"], mask)


def test_embed_images_batches_preprocessed_pixels_and_normalises():
    clip = ClipOnnx()
    session = StubSession(np.array([[0.0, 5.0], [1.0, 0.0]], dtype=np.float32))
    clip._vision = SimpleNamespace(get=lambda: session)
    images = [Image.new("RGB", (30, 40), (255, 0, 0)), Image.new("RGB", (40, 30), (0, 0, 255))]
    out = clip.embed_images(images)
    np.testing.assert_allclose(out, [[0.0, 1.0], [1.0, 0.0]])
    assert session.feeds["pixel_values"].shape == (2, 3, 224, 224)
    np.testing.assert_allclose(session.feeds["pixel_values"][1], preprocess_clip_image(images[1]))


def test_clip_loaded_flags_are_false_until_sessions_are_created():
    assert ClipOnnx().loaded == {"clip_vision": False, "clip_text": False}


def test_l2_normalize_normalises_last_axis():
    out = oi._l2_normalize(np.array([[3.0, 4.0]], dtype=np.float64))
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, [[0.6, 0.8]])


# -- Lazy sessions -----------------------------------------------------------------

def test_lazy_session_resolves_and_creates_session_once(monkeypatch):
    created = []

    def fake_session(path, opts, providers):
        created.append((path, providers))
        return SimpleNamespace(path=path)

    monkeypatch.setattr(oi.ort, "InferenceSession", fake_session)
    resolved = []
    lazy = oi._LazySession(lambda: resolved.append(1) or "/models/x.onnx")
    assert lazy.loaded is False
    first = lazy.get()
    assert lazy.get() is first
    assert lazy.loaded is True
    assert resolved == [1]
    assert created == [("/models/x.onnx", ["CPUExecutionProvider"])]


def test_session_options_honour_thread_override(monkeypatch):
    monkeypatch.setenv("AGENTWEAVE_ORT_THREADS", "3")
    opts = oi._session_options()
    assert opts.intra_op_num_threads == 3
    assert opts.graph_optimization_level == oi.ort.GraphOptimizationLevel.ORT_ENABLE_ALL


def test_session_options_default_threads(monkeypatch):
    monkeypatch.delenv("AGENTWEAVE_ORT_THREADS", raising=False)
    assert oi._session_options().intra_op_num_threads == 0


# -- YOLO letterbox ------------------------------------------------------------------

def test_letterbox_wide_image_scales_and_pads_vertically():
    tensor, gain, (pad_w, pad_h) = letterbox(Image.new("RGB", (320, 160), (255, 255, 255)))
    assert tensor.shape == (1, 3, 640, 640) and tensor.dtype == np.float32
    assert gain == 2.0
    assert (pad_w, pad_h) == (0.0, 160.0)
    pad = 114 / 255.0
    assert tensor[0, :, 159, 320] == pytest.approx([pad] * 3)
    assert tensor[0, :, 160, 320] == pytest.approx([1.0] * 3)
    assert tensor[0, :, 479, 320] == pytest.approx([1.0] * 3)
    assert tensor[0, :, 480, 320] == pytest.approx([pad] * 3)


def test_letterbox_tall_image_pads_horizontally():
    tensor, gain, (pad_w, pad_h) = letterbox(Image.new("RGB", (100, 200), (0, 0, 0)), size=200)
    assert gain == 1.0
    assert (pad_w, pad_h) == (50.0, 0.0)
    assert tensor.shape == (1, 3, 200, 200)
    assert tensor[0, 0, 100, 49] == pytest.approx(114 / 255.0)
    assert tensor[0, 0, 100, 50] == 0.0
    assert tensor[0, 0, 100, 149] == 0.0
    assert tensor[0, 0, 100, 150] == pytest.approx(114 / 255.0)


def test_letterbox_odd_padding_puts_extra_row_at_bottom():
    # 640x639: half a pixel of padding; ultralytics rounds (pad - 0.1) so top = 0.
    tensor, gain, (pad_w, pad_h) = letterbox(Image.new("RGB", (640, 639), (0, 0, 0)))
    assert gain == 1.0 and pad_h == 0.5
    assert tensor[0, 0, 0, 0] == 0.0
    assert tensor[0, 0, 638, 0] == 0.0
    assert tensor[0, 0, 639, 0] == pytest.approx(114 / 255.0)


def test_letterbox_odd_padding_on_left_side():
    tensor, _, (pad_w, _) = letterbox(Image.new("RGB", (637, 640), (0, 0, 0)))
    assert pad_w == 1.5
    # round(1.4) = 1 column on the left, 2 on the right
    assert tensor[0, 0, 10, 0] == pytest.approx(114 / 255.0)
    assert tensor[0, 0, 10, 1] == 0.0
    assert tensor[0, 0, 10, 637] == 0.0
    assert tensor[0, 0, 10, 638] == pytest.approx(114 / 255.0)


def test_letterbox_downscales_large_images():
    tensor, gain, pads = letterbox(Image.new("RGB", (1280, 1280), (255, 0, 0)))
    assert gain == 0.5 and pads == (0.0, 0.0)
    assert tensor[0, 0].min() == pytest.approx(1.0)
    assert tensor[0, 1].max() == 0.0


def test_letterbox_converts_grayscale_to_three_channels():
    tensor, _, _ = letterbox(Image.new("L", (64, 64), 255), size=64)
    assert tensor.shape == (1, 3, 64, 64)
    assert tensor.min() == pytest.approx(1.0)


# -- YOLO decode -------------------------------------------------------------------

def _raw_predictions(n=10, best=None, conf=0.9, kpts_xy=None):
    preds = np.zeros((n, 56), dtype=np.float32)
    preds[:, 4] = 0.05
    if best is not None:
        preds[best, 4] = conf
        kp = np.zeros((17, 3), dtype=np.float32)
        kp[:, 2] = 0.8
        if kpts_xy is not None:
            kp[:, :2] = kpts_xy
        preds[best, 5:] = kp.ravel()
    return preds.T[None]  # (1, 56, n) like the model head


def _pose_with(raw):
    pose = PoseOnnx()
    session = StubSession(raw)
    pose._session = SimpleNamespace(get=lambda: session, loaded=True)
    return pose, session


def test_pose_decode_undoes_letterbox_and_normalises_to_original_size():
    # 320x160 image: gain 2, vertical pad 160.
    xy = np.tile([[100.0, 260.0]], (17, 1))
    xy[1] = [640.0, 480.0]
    pose, session = _pose_with(_raw_predictions(best=3, kpts_xy=xy))
    kpts = pose.keypoints(Image.new("RGB", (320, 160)))
    assert len(kpts) == 17 and all(len(k) == 2 for k in kpts)
    assert kpts[0] == pytest.approx([50 / 320, 50 / 160])
    assert kpts[1] == pytest.approx([1.0, 1.0])
    assert session.feeds["images"].shape == (1, 3, 640, 640)


def test_pose_decode_clips_keypoints_inside_the_padding():
    xy = np.tile([[-40.0, 100.0]], (17, 1))   # left of image and in the top pad
    xy[2] = [700.0, 600.0]                    # beyond right / bottom
    pose, _ = _pose_with(_raw_predictions(best=0, kpts_xy=xy))
    kpts = pose.keypoints(Image.new("RGB", (320, 160)))
    assert kpts[0] == [0.0, 0.0]
    assert kpts[2] == [1.0, 1.0]


def test_pose_decode_picks_most_confident_detection():
    raw = _raw_predictions(n=6, best=4, conf=0.95, kpts_xy=np.full((17, 2), 320.0))
    raw[0, 4, 1] = 0.6
    raw[0, 5:, 1] = 0.0
    pose, _ = _pose_with(raw)
    kpts = pose.keypoints(Image.new("RGB", (640, 640)))
    assert kpts[0] == pytest.approx([0.5, 0.5])


def test_pose_decode_returns_none_below_confidence_threshold():
    pose, _ = _pose_with(_raw_predictions(best=2, conf=0.2499))
    assert pose.keypoints(Image.new("RGB", (64, 64))) is None


def test_pose_decode_accepts_confidence_at_threshold():
    pose, _ = _pose_with(_raw_predictions(best=2, conf=oi.YOLO_CONF_THRESHOLD))
    assert pose.keypoints(Image.new("RGB", (64, 64))) is not None


def test_pose_loaded_reflects_session():
    assert PoseOnnx().loaded is False


# -- tests added from mutation-testing survivors --------------------------------------

def test_clip_preprocess_crop_offset_floors_odd_margins():
    # 224x451: the long side stays 451, margin 227 -> top = 113 (floor), not round(113.5).
    rows = np.repeat(np.arange(451, dtype=np.uint8)[:, None], 224, axis=1)
    img = Image.fromarray(np.stack([rows] * 3, axis=-1))
    out = preprocess_clip_image(img)
    first_row = out[0, 0, 100] * CLIP_STD[0, 0, 0] + CLIP_MEAN[0, 0, 0]
    assert first_row * 255 == pytest.approx(113, abs=0.5)


def test_clip_preprocess_crop_offset_floors_odd_margins_horizontally():
    cols = np.repeat(np.arange(451, dtype=np.uint8)[None, :], 224, axis=0)
    img = Image.fromarray(np.stack([cols] * 3, axis=-1))
    out = preprocess_clip_image(img)
    first_col = out[0, 100, 0] * CLIP_STD[0, 0, 0] + CLIP_MEAN[0, 0, 0]
    assert first_col * 255 == pytest.approx(113, abs=0.5)


def test_letterbox_resizes_with_bilinear_filter():
    rng = np.random.default_rng(0)
    img = Image.fromarray(rng.integers(0, 255, (50, 100, 3), dtype=np.uint8))
    tensor, _, _ = letterbox(img, size=200)
    expected = np.asarray(img.resize((200, 100), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    np.testing.assert_allclose(tensor[0, :, 50:150, :].transpose(1, 2, 0), expected, atol=1e-6)


def test_lazy_session_passes_session_options(monkeypatch):
    captured = {}
    monkeypatch.setattr(oi.ort, "InferenceSession",
                        lambda path, opts, providers: captured.update(opts=opts) or object())
    oi._LazySession(lambda: "x.onnx").get()
    assert isinstance(captured["opts"], oi.ort.SessionOptions)


def test_sessions_resolve_the_expected_model_files(monkeypatch):
    monkeypatch.setattr(oi.artifacts, "resolve", lambda name: f"/models/{name}")
    clip = ClipOnnx()
    assert clip._vision._resolve_path() == "/models/clip_vision_int8.onnx"
    assert clip._text._resolve_path() == "/models/clip_text_int8.onnx"
    assert PoseOnnx()._session._resolve_path() == "/models/yolov8n_pose.onnx"


def test_pose_decode_removes_horizontal_padding():
    # 160x320 portrait: gain 2, horizontal pad 160.
    xy = np.tile([[260.0, 100.0]], (17, 1))
    pose, _ = _pose_with(_raw_predictions(best=1, kpts_xy=xy))
    kpts = pose.keypoints(Image.new("RGB", (160, 320)))
    assert kpts[0] == pytest.approx([50 / 160, 50 / 320])

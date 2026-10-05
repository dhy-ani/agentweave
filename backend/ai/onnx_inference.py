"""
Serving-time inference with ONNX Runtime + numpy only (no torch/transformers).

- CLIP text/image embeddings from the int8 ONNX export of the LoRA-merged
  model (ai/export_onnx.py). Preprocessing mirrors CLIPProcessor exactly:
  shortest side -> 224 (bicubic), center crop 224, /255, CLIP mean/std;
  CLIP BPE via the HF `tokenizers` library with max_length 77 truncation.
- YOLOv8n-pose: letterbox to 640, run, decode the raw (1, 56, 8400) head,
  undo the letterbox and return normalised keypoints like ultralytics' `xyn`.

Each ONNX session is created lazily on first use so an endpoint that only
needs the text tower never pays for loading the vision tower or YOLO.
"""
from __future__ import annotations

import os
import threading
from typing import Callable

import numpy as np
import onnxruntime as ort
from PIL import Image
from tokenizers import Tokenizer

try:
    from . import artifacts
except ImportError:  # imported as a top-level module by scripts that put ai/ on sys.path
    import artifacts  # type: ignore[no-redef]

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TOKENIZER_PATH = os.path.join(ASSETS_DIR, "clip_tokenizer.json")

CLIP_IMAGE_SIZE = 224
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32).reshape(3, 1, 1)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32).reshape(3, 1, 1)
CLIP_MAX_TOKENS = 77
CLIP_PAD_ID = 49407  # <|endoftext|>; padding after EOS cannot affect the causal text tower

YOLO_SIZE = 640
YOLO_PAD_VALUE = 114
YOLO_CONF_THRESHOLD = 0.25
NUM_KEYPOINTS = 17


def _session_options() -> ort.SessionOptions:
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    threads = os.environ.get("AGENTWEAVE_ORT_THREADS")
    if threads:
        opts.intra_op_num_threads = int(threads)
    return opts


class _LazySession:
    """Thread-safe, create-once ONNX Runtime session for one model file."""

    def __init__(self, resolve_path: Callable[[], str]):
        self._resolve_path = resolve_path
        self._session: ort.InferenceSession | None = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._session is not None

    def get(self) -> ort.InferenceSession:
        if self._session is None:
            with self._lock:
                if self._session is None:
                    self._session = ort.InferenceSession(
                        self._resolve_path(), _session_options(), providers=["CPUExecutionProvider"]
                    )
        return self._session


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    return (x / np.linalg.norm(x, axis=-1, keepdims=True)).astype(np.float32)


# -- CLIP ---------------------------------------------------------------------

def preprocess_clip_image(image: Image.Image) -> np.ndarray:
    """PIL image -> float32 [3, 224, 224], identical to CLIPImageProcessor."""
    image = image.convert("RGB")
    width, height = image.size
    short, long = (width, height) if width <= height else (height, width)
    new_short, new_long = CLIP_IMAGE_SIZE, int(CLIP_IMAGE_SIZE * long / short)
    new_w, new_h = (new_short, new_long) if width <= height else (new_long, new_short)
    image = image.resize((new_w, new_h), Image.Resampling.BICUBIC)

    top = (new_h - CLIP_IMAGE_SIZE) // 2
    left = (new_w - CLIP_IMAGE_SIZE) // 2
    image = image.crop((left, top, left + CLIP_IMAGE_SIZE, top + CLIP_IMAGE_SIZE))

    pixels = np.asarray(image, dtype=np.float32).transpose(2, 0, 1) / 255.0
    return (pixels - CLIP_MEAN) / CLIP_STD


class ClipOnnx:
    def __init__(self) -> None:
        self._vision = _LazySession(lambda: artifacts.resolve("clip_vision_int8.onnx"))
        self._text = _LazySession(lambda: artifacts.resolve("clip_text_int8.onnx"))
        self._tokenizer: Tokenizer | None = None

    @property
    def loaded(self) -> dict[str, bool]:
        return {"clip_vision": self._vision.loaded, "clip_text": self._text.loaded}

    def _get_tokenizer(self) -> Tokenizer:
        if self._tokenizer is None:
            tok = Tokenizer.from_file(TOKENIZER_PATH)
            tok.enable_truncation(max_length=CLIP_MAX_TOKENS)
            tok.enable_padding(pad_id=CLIP_PAD_ID, pad_token="<|endoftext|>")
            self._tokenizer = tok
        return self._tokenizer

    def tokenize(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        encodings = self._get_tokenizer().encode_batch(texts)
        ids = np.array([e.ids for e in encodings], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        return ids, mask

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        ids, mask = self.tokenize(texts)
        (embeds,) = self._text.get().run(None, {"input_ids": ids, "attention_mask": mask})
        return _l2_normalize(embeds)

    def embed_images(self, images: list[Image.Image]) -> np.ndarray:
        batch = np.stack([preprocess_clip_image(img) for img in images])
        (embeds,) = self._vision.get().run(None, {"pixel_values": batch})
        return _l2_normalize(embeds)


# -- YOLOv8-pose --------------------------------------------------------------

def letterbox(image: Image.Image, size: int = YOLO_SIZE) -> tuple[np.ndarray, float, tuple[float, float]]:
    """Resize keeping aspect ratio and pad to size x size, matching ultralytics' LetterBox."""
    image = image.convert("RGB")
    width, height = image.size
    gain = min(size / height, size / width)
    new_w, new_h = round(width * gain), round(height * gain)
    pad_w, pad_h = (size - new_w) / 2, (size - new_h) / 2
    top, left = round(pad_h - 0.1), round(pad_w - 0.1)

    if (new_w, new_h) != (width, height):
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
    canvas = np.full((size, size, 3), YOLO_PAD_VALUE, dtype=np.uint8)
    canvas[top:top + new_h, left:left + new_w] = np.asarray(image)

    tensor = canvas.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    return tensor, gain, (pad_w, pad_h)


class PoseOnnx:
    def __init__(self) -> None:
        self._session = _LazySession(lambda: artifacts.resolve("yolov8n_pose.onnx"))

    @property
    def loaded(self) -> bool:
        return self._session.loaded

    def keypoints(self, image: Image.Image) -> list[list[float]] | None:
        """17 COCO keypoints [x, y] normalised to the original image size for the
        most confident person, or None if nobody is detected."""
        width, height = image.size
        tensor, gain, (pad_w, pad_h) = letterbox(image)
        session = self._session.get()
        (raw,) = session.run(None, {session.get_inputs()[0].name: tensor})

        preds = raw[0].T  # (8400, 56): cx, cy, w, h, person_conf, 17 x (x, y, visibility)
        best = int(np.argmax(preds[:, 4]))
        if preds[best, 4] < YOLO_CONF_THRESHOLD:
            return None

        kpts = preds[best, 5:].reshape(NUM_KEYPOINTS, 3)[:, :2].astype(np.float64)
        kpts[:, 0] = np.clip((kpts[:, 0] - pad_w) / gain, 0, width) / width
        kpts[:, 1] = np.clip((kpts[:, 1] - pad_h) / gain, 0, height) / height
        return kpts.tolist()

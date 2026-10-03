"""
Body-shape classification from YOLOv8n-pose keypoints.

Pose estimation runs on the ONNX export (ai/onnx_inference.PoseOnnx) by
default; AGENTWEAVE_BACKEND=torch switches to ultralytics for comparison.
Both are loaded lazily on the first /analyze-body request.
"""
from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
from PIL import Image

from . import model_cache

_pose = None


@lru_cache(maxsize=1)
def _ultralytics_model():
    from ultralytics import YOLO

    return YOLO(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yolov8n-pose.pt"))


def _ultralytics_keypoints(image: Image.Image) -> list[list[float]] | None:
    results = _ultralytics_model()(image, verbose=False)
    if not results or results[0].keypoints is None or len(results[0].keypoints) == 0:
        return None
    return results[0].keypoints.xyn[0].cpu().numpy().tolist()


def _get_pose():
    global _pose
    if _pose is None:
        from .onnx_inference import PoseOnnx

        _pose = PoseOnnx()
    return _pose


def pose_model_loaded() -> bool:
    return _pose is not None and _pose.loaded


def run_pose_estimation(image: Image.Image) -> list[list[float]]:
    if model_cache.backend_name() == "torch":
        keypoints = _ultralytics_keypoints(image)
    else:
        keypoints = _get_pose().keypoints(image)

    if not keypoints:
        raise ValueError("No keypoints detected.")
    if len(keypoints) < 13:
        raise ValueError("Incomplete keypoints. Make sure the image shows a full body.")
    return keypoints


def _dist(a, b):
    return float(np.linalg.norm(np.array(a[:2]) - np.array(b[:2])))


def classify_body_shape(keypoints):
    """
    Uses shoulder width, hip width, and a waist proxy derived from mid-torso
    keypoints to classify into: hourglass, pear, inverted_triangle, rectangle, apple.

    YOLOv8 COCO keypoint indices used:
      5  = left shoulder,  6  = right shoulder
      11 = left hip,       12 = right hip
      7  = left elbow,     8  = right elbow   (used as waist proxy midpoint)
    """
    left_shoulder  = keypoints[5][:2]
    right_shoulder = keypoints[6][:2]
    left_hip       = keypoints[11][:2]
    right_hip      = keypoints[12][:2]

    shoulder_w = _dist(left_shoulder, right_shoulder)
    hip_w      = _dist(left_hip, right_hip)

    # Waist proxy: average x-span at the elbow vertical level
    # (elbows hang near the waist when arms are relaxed)
    left_elbow  = keypoints[7][:2]
    right_elbow = keypoints[8][:2]
    waist_w = _dist(left_elbow, right_elbow) * 0.85  # scale factor correction

    # Guard against zero-width measurements
    if hip_w < 1e-4:
        return "unknown"

    sh_ratio   = round(shoulder_w / hip_w, 3)   # shoulders vs hips
    wh_ratio   = round(waist_w / hip_w, 3)       # waist vs hips

    # Classification rules (ordered by specificity)
    if sh_ratio >= 1.15 and wh_ratio < 0.80:
        return "hourglass"          # wide shoulders, defined waist, full hips
    elif sh_ratio >= 1.15 and wh_ratio >= 0.80:
        return "inverted_triangle"  # wide shoulders, no waist definition
    elif sh_ratio < 0.85 and wh_ratio < 0.85:
        return "pear"               # narrow shoulders, full hips
    elif wh_ratio >= 0.90 and 0.85 <= sh_ratio <= 1.15:
        return "apple"              # full waist / midsection, average shoulders
    else:
        return "rectangle"          # balanced proportions, little definition

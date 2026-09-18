import os
import numpy as np
from PIL import Image

# Lazy-loaded: ultralytics + its dependencies (opencv, etc.) cost real idle
# memory, and this model is only needed by the /analyze-body endpoint --
# loading it eagerly at import time (as before) meant every server start
# paid that cost even for requests that never touch body-shape analysis.
_model = None


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        weights_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yolov8n-pose.pt")
        _model = YOLO(weights_path)
    return _model


def run_pose_estimation(image: Image.Image):
    results = _get_model()(image)

    if not results or not results[0].keypoints:
        raise ValueError("No keypoints detected.")

    keypoints_tensor = results[0].keypoints.xyn[0]
    keypoints = keypoints_tensor.cpu().numpy().tolist()

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

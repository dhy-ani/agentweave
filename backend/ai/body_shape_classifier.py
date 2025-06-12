import numpy as np
from PIL import Image
from ultralytics import YOLO

# Load YOLOv8 pose model once
model = YOLO("yolov8n-pose.pt")

def run_pose_estimation(image: Image.Image):
    results = model(image)

    if not results or not results[0].keypoints:
        raise ValueError("No keypoints detected.")

    keypoints_tensor = results[0].keypoints.xyn[0]
    keypoints = keypoints_tensor.cpu().numpy().tolist()

    if len(keypoints) < 13:
        raise ValueError("Incomplete keypoints. Make sure image shows full body.")

    return keypoints


def classify_body_shape(keypoints):
    left_shoulder = keypoints[5][:2]
    right_shoulder = keypoints[6][:2]
    left_hip = keypoints[11][:2]
    right_hip = keypoints[12][:2]

    shoulder_width = np.linalg.norm(np.array(left_shoulder) - np.array(right_shoulder))
    hip_width = np.linalg.norm(np.array(left_hip) - np.array(right_hip))

    ratio = round(shoulder_width / hip_width, 2)

    if ratio < 0.85:
        return "pear"
    elif 0.85 <= ratio <= 1.15:
        return "hourglass"
    elif ratio > 1.15:
        return "inverted triangle"
    elif abs(shoulder_width - hip_width) < 20:
        return "rectangle"
    else:
        return "apple"

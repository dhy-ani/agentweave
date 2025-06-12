from fastapi import APIRouter, File, UploadFile
from PIL import Image
import io

from ai.body_shape_classifier import run_pose_estimation, classify_body_shape

router = APIRouter(tags= ["StyleGenie"])

@router.post("/analyze-body")
async def analyze_body(file: UploadFile = File(...)):
    try:
        print("📥 Received file:", file.filename)
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        print("🖼 Image loaded")

        keypoints = run_pose_estimation(image)
        print("📌 Keypoints extracted")

        shape = classify_body_shape(keypoints)
        print("🎯 Predicted shape:", shape)

        return {"body_type": shape}

    except Exception as e:
        print("❌ Error:", str(e))
        return {"error": f"Prediction failed: {str(e)}"}

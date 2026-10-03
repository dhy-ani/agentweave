import logging

from fastapi import APIRouter, File, UploadFile
from starlette.concurrency import run_in_threadpool

from ai.body_shape_classifier import classify_body_shape, run_pose_estimation
from image_io import read_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["StyleGenie"])


@router.post("/analyze-body")
async def analyze_body(file: UploadFile = File(...)):
    image = await read_image(file)
    try:
        keypoints = await run_in_threadpool(run_pose_estimation, image)
        shape = classify_body_shape(keypoints)
    except Exception as exc:
        # The frontend expects a 200 with an `error` field for "no person found" style failures.
        logger.info("Body analysis failed for %s: %s", file.filename, exc)
        return {"error": f"Prediction failed: {exc}"}
    logger.info("Predicted body shape: %s", shape)
    return {"body_type": shape}

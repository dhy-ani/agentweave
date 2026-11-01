"""
AgentWeave / StyleGenie API: a stateless ML service with no database.

User data (profile, saved looks, swipes, shopping clicks, closet items) lives
in Firestore and is read and written by the frontend. The /closet endpoints
verify a Firebase ID token (auth.py) and only store or delete image files.

Runs unchanged under uvicorn (local, Render) and as a Vercel Function, which
detects the module-level `app` in this file (Vercel project root: backend/).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import settings

settings.configure_logging()
logger = logging.getLogger("agentweave")

from ai import model_cache  # noqa: E402
from ai.body_shape_classifier import pose_model_loaded  # noqa: E402
import auth  # noqa: E402
from routers.analyze_body import router as analyze_body_router  # noqa: E402
from routers.closet import STATIC_MOUNT, router as closet_router  # noqa: E402
from routers.shopping import router as shopping_router  # noqa: E402
from routers.stylegenie import router as stylegenie_router  # noqa: E402
from storage import LocalStorage, get_storage  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth.log_startup_config()
    logger.info("Stateless ML service; model backend: %s; auth: %s; storage: %s",
                model_cache.backend_name(), auth.auth_mode(), get_storage().name)
    yield


app = FastAPI(title="AgentWeave - StyleGenie Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info("%s %s -> %d (%.0f ms)", request.method, request.url.path, response.status_code,
                (time.perf_counter() - started) * 1000)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    try:
        return await request_validation_exception_handler(request, exc)
    except ValueError:
        # The input cannot be echoed back as JSON (e.g. NaN in an embedding).
        errors = [{k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


app.include_router(analyze_body_router)
app.include_router(stylegenie_router)
app.include_router(closet_router)
app.include_router(shopping_router)


@app.get("/")
def read_root():
    return {"status": "StyleGenie backend is running"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_backend": model_cache.backend_name(),
        "models_loaded": {**model_cache.loaded_models(), "pose": pose_model_loaded()},
        "torch_imported": "torch" in sys.modules,
        "auth": auth.auth_mode(),
        "storage": get_storage().name,
    }


def _curated_image_dir() -> str | None:
    """Curated dataset images: copied into backend/static/images by the Vercel build
    (scripts/vercel_build.py); read from ../datasets in a normal checkout."""
    candidates = [
        os.environ.get("AGENTWEAVE_IMAGE_DIR"),
        os.path.join(BACKEND_DIR, "static", "images"),
        os.path.join(BACKEND_DIR, "..", "datasets", "processedImages"),
        os.path.join(BACKEND_DIR, "..", "datasets", "rawImages"),
    ]
    return next((os.path.abspath(c) for c in candidates if c and os.path.isdir(c)), None)


if image_dir := _curated_image_dir():
    app.mount("/images", StaticFiles(directory=image_dir), name="images")
else:
    logger.warning("No curated image directory found; /images will 404")

if isinstance(storage := get_storage(), LocalStorage):
    # LocalStorage keeps closet images at <root>/closet/{uid}/{item_id}.jpg;
    # routers/closet.py builds their image_url from this mount's name.
    closet_dir = os.path.join(storage.root, "closet")
    os.makedirs(closet_dir, exist_ok=True)
    app.mount(f"/{STATIC_MOUNT}", StaticFiles(directory=closet_dir), name=STATIC_MOUNT)

"""
AgentWeave / StyleGenie API.

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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import settings

settings.configure_logging()
logger = logging.getLogger("agentweave")

from ai import model_cache  # noqa: E402
from ai.body_shape_classifier import pose_model_loaded  # noqa: E402
from db.database import engine  # noqa: E402
from db.schema import init_schema  # noqa: E402
from routers import user  # noqa: E402
from routers.analyze_body import router as analyze_body_router  # noqa: E402
from routers.shopping import router as shopping_router  # noqa: E402
from routers.stylegenie import router as stylegenie_router  # noqa: E402
from routers.wardrobe import router as wardrobe_router  # noqa: E402
from storage import LocalStorage, get_storage  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema(engine)
    logger.info("Database ready (%s); model backend: %s", engine.dialect.name, model_cache.backend_name())
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


app.include_router(analyze_body_router)
app.include_router(stylegenie_router)
app.include_router(user.router)
app.include_router(wardrobe_router)
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
        "database": engine.dialect.name,
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
    app.mount("/wardrobe-images", StaticFiles(directory=storage.root), name="wardrobe-images")

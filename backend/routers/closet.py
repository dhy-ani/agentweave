"""
Closet router: store a user's clothing photos and suggest outfits from them.

The backend keeps no records. Item metadata and embeddings live in the user's
Firestore documents (written by the frontend); this router only stores and
deletes the image files and runs CLIP. Every endpoint needs a Firebase ID
token, and storage keys are always built from the token's uid
(closet/{uid}/{item_id}.jpg), so a user can never address another user's files.

image_url returned by POST /closet/items:
  Vercel Blob     the public blob URL.
  LocalStorage    a full URL to this server's /closet-images mount,
                  e.g. http://localhost:8001/closet-images/{uid}/{item_id}.jpg
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Annotated, Optional

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Request, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ai.model_cache import EMBED_DIM, embed_image, embed_text_ensemble
from ai.retrieval import get_corpus
from auth import current_uid
from image_io import read_image, to_jpeg
from storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/closet", tags=["Closet"])

STATIC_MOUNT = "closet-images"
ITEM_ID_PATTERN = r"^[0-9a-f]{32}$"
MAX_ITEMS = 200
MAX_CATEGORY_LENGTH = 40
# Firebase uids (email, Google, anonymous, emulator) are 28 alphanumerics;
# anything outside this set could not be used safely as a path segment.
_SAFE_UID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def closet_uid(uid: str = Depends(current_uid)) -> str:
    if not _SAFE_UID.fullmatch(uid):
        raise HTTPException(status_code=400, detail="This account id cannot be used for closet storage.")
    return uid


def storage_key(uid: str, item_id: str) -> str:
    return f"closet/{uid}/{item_id}.jpg"


def embedding_out(vec: np.ndarray) -> list[float]:
    """L2-normalised and rounded to 6 decimals for storage in Firestore."""
    vec = np.asarray(vec, dtype=np.float64)
    norm = np.linalg.norm(vec)
    if not norm > 0:
        raise ValueError("Image embedding is zero.")
    return [round(float(x), 6) for x in vec / norm]


@router.post("/items")
async def upload_item(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(..., max_length=MAX_CATEGORY_LENGTH),
    uid: str = Depends(closet_uid),
):
    category = category.strip().lower()
    if not category:
        raise HTTPException(status_code=422, detail="category must not be empty.")
    image = await read_image(file)
    item_id = uuid.uuid4().hex
    try:
        embedding = embedding_out(await run_in_threadpool(embed_image, image))
    except Exception as exc:
        logger.exception("Embedding closet image failed")
        raise HTTPException(status_code=500, detail="Could not analyse the uploaded image.") from exc

    jpeg = await run_in_threadpool(to_jpeg, image)
    try:
        image_url = await run_in_threadpool(get_storage().save, storage_key(uid, item_id), jpeg, "image/jpeg")
    except Exception as exc:
        logger.exception("Storing closet image failed")
        raise HTTPException(status_code=502, detail="Could not store the uploaded image.") from exc
    if image_url is None:
        image_url = str(request.url_for(STATIC_MOUNT, path=f"{uid}/{item_id}.jpg"))

    return {"item_id": item_id, "image_url": image_url, "category": category, "embedding": embedding}


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str = Path(..., pattern=ITEM_ID_PATTERN, description="32 lowercase hex characters"),
    uid: str = Depends(closet_uid),
):
    try:
        await run_in_threadpool(get_storage().delete, storage_key(uid, item_id))
    except Exception as exc:
        logger.exception("Deleting closet image %s failed", item_id)
        raise HTTPException(status_code=502, detail="Could not delete the stored image.") from exc
    return {"deleted": True}


Embedding = Annotated[
    list[Annotated[float, Field(allow_inf_nan=False)]],
    Field(min_length=EMBED_DIM, max_length=EMBED_DIM),
]


class ClosetItem(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=MAX_CATEGORY_LENGTH)
    embedding: Embedding


class SuggestRequest(BaseModel):
    occasion: Optional[str] = "casual"
    weather: Optional[str] = "mild"
    gender: Optional[str] = ""
    body_type: Optional[str] = ""
    items: list[ClosetItem] = Field(max_length=MAX_ITEMS)


def outfit_prompts(occasion: str, weather: str, gender: str, body_type: str) -> list[str]:
    prompts = [
        f"A stylish {gender} outfit for {occasion} in {weather} weather.",
        f"Fashionable {occasion} look, {weather} weather.",
    ]
    if body_type:
        prompts.append(f"Flattering {body_type} body shape outfit for {occasion}.")
    return prompts


def best_per_category(query: np.ndarray, items: list[ClosetItem]) -> list[ClosetItem]:
    """The highest-scoring item of each category, best category first.

    Items with an all-zero embedding are skipped; ties keep the earlier item."""
    best: dict[str, tuple[ClosetItem, float]] = {}
    for item in items:
        vec = np.asarray(item.embedding)
        norm = np.linalg.norm(vec)
        if norm == 0:
            continue
        sim = float(np.dot(query, vec / norm))
        if item.category not in best or sim > best[item.category][1]:
            best[item.category] = (item, sim)
    return [item for item, _ in sorted(best.values(), key=lambda x: -x[1])]


@router.post("/suggest")
def suggest_outfit(data: SuggestRequest, uid: str = Depends(closet_uid)):
    if not data.items:
        raise HTTPException(status_code=400, detail="Your closet is empty: add some items first.")
    occasion = data.occasion or "casual"
    weather = data.weather or "mild"
    query = embed_text_ensemble(outfit_prompts(occasion, weather, data.gender or "", data.body_type or ""))
    outfit = best_per_category(query, data.items)

    corpus = get_corpus()
    top, _ = corpus.search(query, 1)
    trend_idx = int(top[0])

    suggestion = (
        f"For {occasion} in {weather} weather, try: {', '.join(i.category for i in outfit)}."
        if outfit else "No matching items found."
    )
    return {
        "suggestion": suggestion,
        "outfit": [{"id": i.id, "category": i.category} for i in outfit],
        "trend_inspiration": {"image": corpus.filename(trend_idx), "caption": corpus.caption(trend_idx, "")},
    }

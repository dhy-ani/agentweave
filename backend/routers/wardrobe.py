"""
Wardrobe router: upload clothing items and get outfit suggestions.

Item metadata and CLIP embeddings live in the database (WardrobeItem); image
bytes go through storage.get_storage(), so no request depends on the local
disk of the instance that handled the upload.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai.model_cache import embed_image, embed_text_ensemble
from ai.retrieval import get_corpus
from db.database import get_db
from db.models import User, WardrobeItem, placeholder_email
from image_io import read_image, to_jpeg
from storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wardrobe", tags=["Wardrobe"])

def _get_or_create_user(firebase_uid: str, db: Session) -> User:
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        # users.email is NOT NULL + unique; /users/upsert replaces this placeholder.
        user = User(firebase_uid=firebase_uid, email=placeholder_email(firebase_uid))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _item_out(item: WardrobeItem) -> dict:
    return {
        "id": item.id,
        "item_uuid": item.item_uuid,
        "filename": item.filename,
        "image_url": item.image_url,
        "category": item.category,
        "color": item.color,
        "description": item.description,
        "added_at": item.added_at.isoformat(),
    }


def _item_vector(item: WardrobeItem) -> np.ndarray | None:
    if item.clip_embedding:
        vec = np.frombuffer(item.clip_embedding, dtype=np.float32)
    elif item.clip_vector:  # rows written before embeddings moved to LargeBinary
        vec = np.asarray(json.loads(item.clip_vector), dtype=np.float32)
    else:
        return None
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else None


@router.post("/upload")
async def upload_clothing_item(
    file: UploadFile = File(...),
    firebase_uid: str = Form(...),
    category: str = Form("other"),
    color: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    image = await read_image(file)
    item_id = str(uuid.uuid4())
    filename = f"{item_id}.jpg"

    vec = await run_in_threadpool(embed_image, image)
    jpeg = await run_in_threadpool(to_jpeg, image)
    storage = get_storage()
    try:
        image_url = await run_in_threadpool(storage.save, filename, jpeg, "image/jpeg")
    except Exception as exc:
        logger.exception("Storing wardrobe image failed")
        raise HTTPException(status_code=502, detail="Could not store the uploaded image.") from exc

    user = _get_or_create_user(firebase_uid, db)
    db_item = WardrobeItem(
        user_id=user.id,
        item_uuid=item_id,
        filename=filename,
        image_url=image_url,
        category=category.lower().strip(),
        color=color.strip() or None,
        description=description.strip() or None,
        clip_embedding=vec.astype(np.float32).tobytes(),
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"success": True, "item_id": item_id, "category": category, "image_url": image_url}


@router.get("/items")
def list_wardrobe_items(firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_or_create_user(firebase_uid, db)
    items = (db.query(WardrobeItem)
             .filter(WardrobeItem.user_id == user.id)
             .order_by(WardrobeItem.added_at.desc())
             .all())
    return {"items": [_item_out(i) for i in items]}


@router.delete("/items/{item_uuid}")
def delete_wardrobe_item(item_uuid: str, firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_or_create_user(firebase_uid, db)
    item = db.query(WardrobeItem).filter(
        WardrobeItem.item_uuid == item_uuid,
        WardrobeItem.user_id == user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    try:
        get_storage().delete(item.filename, item.image_url)
    except Exception:
        # The DB row is the source of truth; an orphaned object is harmless.
        logger.exception("Deleting stored image for %s failed", item_uuid)

    db.delete(item)
    db.commit()
    return {"success": True}


class SuggestRequest(BaseModel):
    firebase_uid: str
    occasion: Optional[str] = "casual"
    weather: Optional[str] = "mild"
    gender: Optional[str] = ""
    body_type: Optional[str] = ""


@router.post("/suggest")
def suggest_outfit_from_wardrobe(data: SuggestRequest, db: Session = Depends(get_db)):
    user = _get_or_create_user(data.firebase_uid, db)
    items = db.query(WardrobeItem).filter(WardrobeItem.user_id == user.id).all()
    if not items:
        raise HTTPException(status_code=400, detail="Wardrobe is empty.")

    prompts = [
        f"A stylish {data.gender} outfit for {data.occasion} in {data.weather} weather.",
        f"Fashionable {data.occasion} look, {data.weather} weather.",
    ]
    if data.body_type:
        prompts.append(f"Flattering {data.body_type} body shape outfit for {data.occasion}.")
    query = embed_text_ensemble(prompts)

    # Best-scoring item per category.
    best: dict[str, tuple[dict, float]] = {}
    for item in items:
        vec = _item_vector(item)
        if vec is None:
            continue
        sim = float(np.dot(query, vec))
        if item.category not in best or sim > best[item.category][1]:
            best[item.category] = (_item_out(item), sim)
    outfit = [item for item, _ in sorted(best.values(), key=lambda x: -x[1])]

    corpus = get_corpus()
    top, _ = corpus.search(query, 1)
    trend_idx = int(top[0])

    pieces = [
        f"{i['color'] + ' ' if i.get('color') else ''}{i.get('description') or i.get('category')}"
        for i in outfit
    ]
    suggestion = (
        f"For {data.occasion} in {data.weather} weather, try: {', '.join(pieces)}."
        if pieces else "No matching items found."
    )
    return {
        "outfit": outfit,
        "suggestion": suggestion,
        "trend_inspiration": {"image": corpus.filename(trend_idx), "caption": corpus.caption(trend_idx, "")},
    }

"""
Wardrobe router — upload clothing items and get outfit suggestions.
Items are now stored in the SQL database (WardrobeItem table).
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from pydantic import BaseModel
from typing import Optional
import os, sys, json, uuid
from datetime import datetime
from PIL import Image
import io
import numpy as np
import faiss
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ai.model_cache import embed_image, embed_text_ensemble
from db.database import get_db
from db.models import User, WardrobeItem

router = APIRouter(prefix="/wardrobe", tags=["Wardrobe"])

_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WARDROBE_UPLOAD_DIR = os.path.join(_base, "uploads", "wardrobe")
os.makedirs(WARDROBE_UPLOAD_DIR, exist_ok=True)

# FAISS + Pinterest trend metadata
try:
    faiss_index = faiss.read_index(os.path.join(_base, "ai/data/trends.index"))
    with open(os.path.join(_base, "ai/data/index_to_caption.json")) as f:
        index_to_caption = json.load(f)
    with open(os.path.join(_base, "ai/data/index_to_image_path.json")) as f:
        index_to_image_path = json.load(f)
except Exception as e:
    raise RuntimeError(f"Wardrobe router: failed to load FAISS: {e}")


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_user(firebase_uid: str, db: Session) -> User:
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Call /users/upsert first.")
    return user


def _item_out(item: WardrobeItem) -> dict:
    return {
        "id": item.id,
        "item_uuid": item.item_uuid,
        "filename": item.filename,
        "category": item.category,
        "color": item.color,
        "description": item.description,
        "added_at": item.added_at.isoformat(),
    }


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_clothing_item(
    file: UploadFile = File(...),
    firebase_uid: str = Form(...),
    category: str = Form("other"),
    color: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _get_user(firebase_uid, db)

    img_bytes = await file.read()
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    ext = os.path.splitext(file.filename)[-1] or ".jpg"
    item_id = str(uuid.uuid4())
    saved_path = os.path.join(WARDROBE_UPLOAD_DIR, f"{item_id}{ext}")
    img.save(saved_path)

    vec = embed_image(img).tolist()

    db_item = WardrobeItem(
        user_id=user.id,
        item_uuid=item_id,
        filename=f"{item_id}{ext}",
        category=category.lower().strip(),
        color=color.strip() or None,
        description=description.strip() or None,
        clip_vector=json.dumps(vec),
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    return {"success": True, "item_id": item_id, "category": category}


# ── List items ────────────────────────────────────────────────────────────────

@router.get("/items")
def list_wardrobe_items(firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_user(firebase_uid, db)
    items = (db.query(WardrobeItem)
             .filter(WardrobeItem.user_id == user.id)
             .order_by(WardrobeItem.added_at.desc())
             .all())
    return {"items": [_item_out(i) for i in items]}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/items/{item_uuid}")
def delete_wardrobe_item(item_uuid: str, firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_user(firebase_uid, db)
    item = db.query(WardrobeItem).filter(
        WardrobeItem.item_uuid == item_uuid,
        WardrobeItem.user_id == user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    # Remove image file
    fpath = os.path.join(WARDROBE_UPLOAD_DIR, item.filename)
    if os.path.exists(fpath):
        os.remove(fpath)

    db.delete(item)
    db.commit()
    return {"success": True}


# ── Outfit suggestion ─────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    firebase_uid: str
    occasion: Optional[str] = "casual"
    weather: Optional[str] = "mild"
    gender: Optional[str] = ""
    body_type: Optional[str] = ""


@router.post("/suggest")
def suggest_outfit_from_wardrobe(data: SuggestRequest, db: Session = Depends(get_db)):
    user = _get_user(data.firebase_uid, db)
    items = db.query(WardrobeItem).filter(WardrobeItem.user_id == user.id).all()

    if not items:
        raise HTTPException(status_code=400, detail="Wardrobe is empty.")

    prompts = [
        f"A stylish {data.gender} outfit for {data.occasion} in {data.weather} weather.",
        f"Fashionable {data.occasion} look, {data.weather} weather.",
    ]
    if data.body_type:
        prompts.append(f"Flattering {data.body_type} body shape outfit for {data.occasion}.")

    query_vec = embed_text_ensemble(prompts).astype("float32")

    # Score each wardrobe item
    scored = []
    for item in items:
        if not item.clip_vector:
            continue
        vec = np.array(json.loads(item.clip_vector), dtype="float32")
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        sim = float(np.dot(query_vec, vec))
        scored.append((_item_out(item), sim))

    # Pick best per category
    categories: dict[str, tuple] = {}
    for item_dict, sim in scored:
        cat = item_dict["category"]
        if cat not in categories or sim > categories[cat][1]:
            categories[cat] = (item_dict, sim)

    outfit = [item for item, _ in sorted(categories.values(), key=lambda x: -x[1])]

    # Pinterest trend inspiration
    k = min(5, faiss_index.ntotal)
    D, I = faiss_index.search(query_vec.reshape(1, -1), k=k)
    trend_idx = str(int(I[0][0]))
    trend_img = os.path.basename(index_to_image_path.get(trend_idx, ""))
    trend_caption = index_to_caption.get(trend_idx, "")

    pieces = [
        f"{i.get('color', '') + ' ' if i.get('color') else ''}{i.get('description') or i.get('category')}"
        for i in outfit
    ]
    suggestion = (
        f"For {data.occasion} in {data.weather} weather, try: {', '.join(pieces)}."
        if pieces else "No matching items found."
    )

    return {
        "outfit": outfit,
        "suggestion": suggestion,
        "trend_inspiration": {"image": trend_img, "caption": trend_caption},
    }

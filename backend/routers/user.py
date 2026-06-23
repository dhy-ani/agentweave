"""
User router — profile CRUD backed by SQL.

Auth: we trust the Firebase UID passed in the request body/header.
      In production you'd verify the Firebase ID token here; for now
      the UID is sent from the client after firebase.auth() signs in.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_db
from db.models import User, SavedOutfit, StylePreference, ShoppingClick

router = APIRouter(prefix="/users", tags=["Users"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class UserUpsert(BaseModel):
    firebase_uid: str
    email: str
    display_name: Optional[str] = None
    body_type: Optional[str] = None
    gender: Optional[str] = None


class OutfitSave(BaseModel):
    firebase_uid: str
    image_filename: str
    caption: str
    trendiness_score: float = 0.0
    future_projection: Optional[str] = None
    occasion: Optional[str] = None
    weather: Optional[str] = None


class SwipeRecord(BaseModel):
    firebase_uid: str
    image_filename: str
    caption: str
    liked: bool
    occasion: Optional[str] = None


class ShoppingClickRecord(BaseModel):
    firebase_uid: str
    brand: str
    item: str
    tier: str
    est_price: float
    occasion: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, uid: str) -> User:
    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Call /users/upsert first.")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upsert", summary="Create or update user profile")
def upsert_user(data: UserUpsert, db: Session = Depends(get_db)):
    """Called right after Firebase sign-in to sync the user into the SQL DB."""
    user = db.query(User).filter(User.firebase_uid == data.firebase_uid).first()
    if user:
        # Update mutable fields
        if data.display_name is not None: user.display_name = data.display_name
        if data.body_type    is not None: user.body_type    = data.body_type
        if data.gender       is not None: user.gender       = data.gender
    else:
        user = User(
            firebase_uid=data.firebase_uid,
            email=data.email,
            display_name=data.display_name,
            body_type=data.body_type,
            gender=data.gender,
        )
        db.add(user)

    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.get("/{firebase_uid}/profile", summary="Get user profile")
def get_profile(firebase_uid: str, db: Session = Depends(get_db)):
    return _user_out(_get_or_404(db, firebase_uid))


@router.patch("/{firebase_uid}/profile", summary="Update body type / gender")
def update_profile(firebase_uid: str, data: UserUpsert, db: Session = Depends(get_db)):
    user = _get_or_404(db, firebase_uid)
    if data.body_type    is not None: user.body_type    = data.body_type
    if data.gender       is not None: user.gender       = data.gender
    if data.display_name is not None: user.display_name = data.display_name
    db.commit()
    db.refresh(user)
    return _user_out(user)


# ── Saved outfits ─────────────────────────────────────────────────────────────

@router.post("/outfits/save", summary="Save a liked outfit")
def save_outfit(data: OutfitSave, db: Session = Depends(get_db)):
    user = _get_or_404(db, data.firebase_uid)
    outfit = SavedOutfit(
        user_id=user.id,
        image_filename=data.image_filename,
        caption=data.caption,
        trendiness_score=data.trendiness_score,
        future_projection=data.future_projection,
        occasion=data.occasion,
        weather=data.weather,
    )
    db.add(outfit)
    db.commit()
    db.refresh(outfit)
    return {"saved": True, "outfit_id": outfit.id}


@router.get("/{firebase_uid}/outfits", summary="List saved outfits")
def list_outfits(firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_or_404(db, firebase_uid)
    outfits = (db.query(SavedOutfit)
               .filter(SavedOutfit.user_id == user.id)
               .order_by(SavedOutfit.saved_at.desc())
               .all())
    return {"outfits": [_outfit_out(o) for o in outfits]}


@router.delete("/outfits/{outfit_id}", summary="Delete a saved outfit")
def delete_outfit(outfit_id: int, firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_or_404(db, firebase_uid)
    outfit = db.query(SavedOutfit).filter(
        SavedOutfit.id == outfit_id, SavedOutfit.user_id == user.id
    ).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Outfit not found.")
    db.delete(outfit)
    db.commit()
    return {"deleted": True}


# ── Swipe preferences ─────────────────────────────────────────────────────────

@router.post("/swipe", summary="Record a swipe (like / dislike)")
def record_swipe(data: SwipeRecord, db: Session = Depends(get_db)):
    user = _get_or_404(db, data.firebase_uid)
    # Upsert: if same user+image already recorded, update the preference
    existing = db.query(StylePreference).filter(
        StylePreference.user_id == user.id,
        StylePreference.image_filename == data.image_filename,
    ).first()
    if existing:
        existing.liked = data.liked
    else:
        db.add(StylePreference(
            user_id=user.id,
            image_filename=data.image_filename,
            caption=data.caption,
            liked=data.liked,
            occasion=data.occasion,
        ))
    db.commit()
    return {"recorded": True}


@router.get("/{firebase_uid}/preferences", summary="Get liked style history")
def get_preferences(firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_or_404(db, firebase_uid)
    prefs = (db.query(StylePreference)
             .filter(StylePreference.user_id == user.id, StylePreference.liked == True)
             .order_by(StylePreference.recorded_at.desc())
             .limit(50).all())
    return {"liked_styles": [_pref_out(p) for p in prefs]}


# ── Shopping clicks ───────────────────────────────────────────────────────────

@router.post("/shopping/click", summary="Record a brand click")
def record_shopping_click(data: ShoppingClickRecord, db: Session = Depends(get_db)):
    user = _get_or_404(db, data.firebase_uid)
    db.add(ShoppingClick(
        user_id=user.id,
        brand=data.brand,
        item=data.item,
        tier=data.tier,
        est_price=data.est_price,
        occasion=data.occasion,
    ))
    db.commit()
    return {"recorded": True}


@router.get("/{firebase_uid}/shopping/history", summary="Shopping click history")
def shopping_history(firebase_uid: str, db: Session = Depends(get_db)):
    user = _get_or_404(db, firebase_uid)
    clicks = (db.query(ShoppingClick)
              .filter(ShoppingClick.user_id == user.id)
              .order_by(ShoppingClick.clicked_at.desc())
              .limit(100).all())
    return {"history": [_click_out(c) for c in clicks]}


# ── Output serialisers ────────────────────────────────────────────────────────

def _user_out(u: User):
    return {
        "id": u.id, "firebase_uid": u.firebase_uid, "email": u.email,
        "display_name": u.display_name, "body_type": u.body_type,
        "gender": u.gender, "created_at": u.created_at.isoformat(),
    }

def _outfit_out(o: SavedOutfit):
    return {
        "id": o.id, "image_filename": o.image_filename, "caption": o.caption,
        "trendiness_score": o.trendiness_score, "future_projection": o.future_projection,
        "occasion": o.occasion, "weather": o.weather, "saved_at": o.saved_at.isoformat(),
    }

def _pref_out(p: StylePreference):
    return {
        "image_filename": p.image_filename, "caption": p.caption,
        "liked": p.liked, "occasion": p.occasion, "recorded_at": p.recorded_at.isoformat(),
    }

def _click_out(c: ShoppingClick):
    return {
        "brand": c.brand, "item": c.item, "tier": c.tier,
        "est_price": c.est_price, "occasion": c.occasion,
        "clicked_at": c.clicked_at.isoformat(),
    }

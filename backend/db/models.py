"""
ORM models.  All tables are created via create_all() on startup.
Compatible with both SQLite and MySQL — no dialect-specific types used.
"""
from datetime import datetime
from sqlalchemy import (
    String, Text, Float, Boolean, Integer,
    DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int]         = mapped_column(Integer, primary_key=True, index=True)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    email: Mapped[str]      = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    body_type: Mapped[str | None]    = mapped_column(String(32), nullable=True)
    gender: Mapped[str | None]       = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime]     = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]     = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    saved_outfits:    Mapped[list["SavedOutfit"]]    = relationship(back_populates="user", cascade="all, delete-orphan")
    wardrobe_items:   Mapped[list["WardrobeItem"]]   = relationship(back_populates="user", cascade="all, delete-orphan")
    style_preferences:Mapped[list["StylePreference"]]= relationship(back_populates="user", cascade="all, delete-orphan")
    shopping_history: Mapped[list["ShoppingClick"]]  = relationship(back_populates="user", cascade="all, delete-orphan")


class SavedOutfit(Base):
    __tablename__ = "saved_outfits"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int]     = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    image_filename: Mapped[str]      = mapped_column(String(255))
    caption: Mapped[str]             = mapped_column(Text)
    trendiness_score: Mapped[float]  = mapped_column(Float, default=0.0)
    future_projection: Mapped[str | None] = mapped_column(Text, nullable=True)
    occasion: Mapped[str | None]     = mapped_column(String(64), nullable=True)
    weather: Mapped[str | None]      = mapped_column(String(32), nullable=True)
    source: Mapped[str]              = mapped_column(String(32), default="trend-vector")
    saved_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="saved_outfits")


class WardrobeItem(Base):
    __tablename__ = "wardrobe_items"

    id: Mapped[int]         = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int]    = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_uuid: Mapped[str]  = mapped_column(String(36), unique=True, index=True)  # UUID for file reference
    filename: Mapped[str]   = mapped_column(String(255))
    category: Mapped[str]   = mapped_column(String(32), default="other")
    color: Mapped[str | None]       = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    clip_vector: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded list[float]
    added_at: Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="wardrobe_items")


class StylePreference(Base):
    """
    Tracks implicit likes/dislikes from swipe gestures so the model
    can personalise future recommendations.
    """
    __tablename__ = "style_preferences"
    __table_args__ = (UniqueConstraint("user_id", "image_filename", name="uq_user_image"),)

    id: Mapped[int]         = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int]    = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    image_filename: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str]        = mapped_column(Text)
    liked: Mapped[bool]         = mapped_column(Boolean)   # True = swipe right, False = swipe left
    occasion: Mapped[str | None]= mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="style_preferences")


class ShoppingClick(Base):
    """Records which brand/item the user clicked through to shop."""
    __tablename__ = "shopping_clicks"

    id: Mapped[int]         = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int]    = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand: Mapped[str]      = mapped_column(String(64))
    item: Mapped[str]       = mapped_column(String(128))
    tier: Mapped[str]       = mapped_column(String(32))
    est_price: Mapped[float]= mapped_column(Float)
    occasion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="shopping_history")

"""
Database engine + session factory.

DATABASE_URL selects the backend:
  unset                    -> SQLite file backend/agentweave.db (local dev)
                              or /tmp/agentweave.db on Vercel (ephemeral)
  postgres://... / postgresql://...  -> Postgres via psycopg 3
  any other SQLAlchemy URL is used as-is
"""
from __future__ import annotations

import logging
import os
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

import settings  # noqa: F401  (loads backend/.env before DATABASE_URL is read)

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_url() -> str:
    if os.environ.get("VERCEL"):
        logger.warning("DATABASE_URL is not set on Vercel: using SQLite in /tmp, which is "
                       "per-instance and wiped on cold start. Set DATABASE_URL to a Postgres database.")
        return f"sqlite:///{os.path.join(tempfile.gettempdir(), 'agentweave.db')}"
    return f"sqlite:///{os.path.join(BACKEND_DIR, 'agentweave.db')}"


def normalize_database_url(url: str) -> str:
    """Map the postgres:// / postgresql:// URLs handed out by hosting providers to psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_database_url(os.environ.get("DATABASE_URL") or _default_url())
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

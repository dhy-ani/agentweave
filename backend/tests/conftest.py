"""
Shared test setup.

Environment variables are set *before* any application module is imported:
db.database reads DATABASE_URL, image_io reads AGENTWEAVE_MAX_UPLOAD_MB and
main mounts the upload directory at import time. settings.py loads backend/.env
with setdefault semantics, so explicit values here always win over a
developer's local .env (e.g. a real BLOB_READ_WRITE_TOKEN is never used).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_SESSION_TMP = Path(tempfile.mkdtemp(prefix="agentweave-tests-"))
REAL_MODEL_DIR = str(BACKEND_DIR / "ai" / "models")

os.environ.update({
    "DATABASE_URL": f"sqlite:///{(_SESSION_TMP / 'session.db').as_posix()}",
    "AGENTWEAVE_UPLOAD_DIR": str(_SESSION_TMP / "uploads"),
    # Empty model dir + unroutable release URL: a test that accidentally
    # reaches for a real model fails fast instead of loading or downloading one.
    "AGENTWEAVE_MODEL_DIR": str(_SESSION_TMP / "models"),
    "AGENTWEAVE_MODEL_CACHE_DIR": str(_SESSION_TMP / "model-cache"),
    "AGENTWEAVE_MODEL_BASE_URL": "http://127.0.0.1:9/no-network-in-tests",
    "AGENTWEAVE_BACKEND": "onnx",
    "AGENTWEAVE_MAX_UPLOAD_MB": "4.5",
    "BLOB_READ_WRITE_TOKEN": "",
    "VERCEL": "",
    "CORS_ORIGINS": "",
    "LOG_LEVEL": "WARNING",
})

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from ai import body_shape_classifier, model_cache  # noqa: E402
from db import database  # noqa: E402
from db.schema import init_schema  # noqa: E402
from storage import LocalStorage  # noqa: E402
from tests.fakes import FakeClipBackend, FakePose, body_keypoints, make_corpus  # noqa: E402


_OWNER_PID = os.getpid()


def pytest_sessionstart(session):
    # mutmut runs several pytest sessions in one process (and forks workers),
    # so recreate the directory if an earlier session already removed it.
    _SESSION_TMP.mkdir(parents=True, exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
    database.engine.dispose()  # release the SQLite file so Windows can delete it
    if os.getpid() == _OWNER_PID:  # never from a forked mutmut worker
        shutil.rmtree(_SESSION_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def fake_models(monkeypatch):
    """Every test runs against deterministic fake models (no ONNX files needed)."""
    backend = FakeClipBackend()
    pose = FakePose(body_keypoints(shoulder_w=1.3, hip_w=1.0, waist_w=0.6))
    monkeypatch.setattr(model_cache, "_backend", backend)
    monkeypatch.setattr(model_cache, "_backend_name", "onnx")
    monkeypatch.setattr(body_shape_classifier, "_pose", pose)
    model_cache._embed_text_cached.cache_clear()
    yield backend
    model_cache._embed_text_cached.cache_clear()


@pytest.fixture
def fake_pose():
    return body_shape_classifier._pose


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """Fresh in-memory database per test. db.database.get_db resolves
    SessionLocal at call time, so the real dependency serves this engine."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_schema(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    yield session_factory
    engine.dispose()


@pytest.fixture
def db_session(isolated_db):
    session = isolated_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def corpus(monkeypatch):
    """Small synthetic trend corpus used by the retrieval endpoints."""
    import routers.stylegenie
    import routers.wardrobe

    fake = make_corpus()
    monkeypatch.setattr(routers.stylegenie, "get_corpus", lambda: fake)
    monkeypatch.setattr(routers.wardrobe, "get_corpus", lambda: fake)
    return fake


@pytest.fixture
def upload_storage(tmp_path, monkeypatch):
    import main
    import routers.wardrobe

    store = LocalStorage(str(tmp_path / "uploads"))
    monkeypatch.setattr(routers.wardrobe, "get_storage", lambda: store)
    monkeypatch.setattr(main, "get_storage", lambda: store)
    return store


@pytest.fixture
def client(upload_storage, corpus):
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as test_client:
        yield test_client

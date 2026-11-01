"""
Shared test setup.

Environment variables are set *before* any application module is imported:
image_io reads AGENTWEAVE_MAX_UPLOAD_MB and main mounts the upload directory at
import time. settings.py loads backend/.env
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
    # Real signature verification against the test keypair (tests/tokens.py);
    # a developer's emulator setting in backend/.env must not leak in.
    "FIREBASE_PROJECT_ID": "demo-test",
    "FIREBASE_AUTH_EMULATOR_HOST": "",
})

import auth  # noqa: E402
from ai import body_shape_classifier, model_cache  # noqa: E402
from storage import LocalStorage  # noqa: E402
from tests import tokens  # noqa: E402
from tests.fakes import FakeClipBackend, FakePose, body_keypoints, make_corpus  # noqa: E402


_OWNER_PID = os.getpid()


def pytest_sessionstart(session):
    # mutmut runs several pytest sessions in one process (and forks workers),
    # so recreate the directory if an earlier session already removed it.
    _SESSION_TMP.mkdir(parents=True, exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
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
def signing_certs(monkeypatch):
    """Google's cert endpoint is replaced by the test cert (no network). Tests
    sign tokens with tests.tokens; `fetches` counts cert downloads."""
    state = {"certs": {tokens.KID: tokens.keypair()[1]}, "max_age": 3600, "fetches": 0}

    def fetch():
        state["fetches"] += 1
        return dict(state["certs"]), state["max_age"]

    monkeypatch.setattr(auth, "_cert_cache", auth.CertCache(fetch=fetch))
    return state


@pytest.fixture
def corpus(monkeypatch):
    """Small synthetic trend corpus used by the retrieval endpoints."""
    import routers.closet
    import routers.stylegenie

    fake = make_corpus()
    monkeypatch.setattr(routers.stylegenie, "get_corpus", lambda: fake)
    monkeypatch.setattr(routers.closet, "get_corpus", lambda: fake)
    return fake


@pytest.fixture
def upload_storage(monkeypatch):
    """LocalStorage at AGENTWEAVE_UPLOAD_DIR, the directory main mounted at
    /closet-images on import, so uploaded image URLs resolve; emptied after each test."""
    import main
    import routers.closet

    store = LocalStorage(os.environ["AGENTWEAVE_UPLOAD_DIR"])
    monkeypatch.setattr(routers.closet, "get_storage", lambda: store)
    monkeypatch.setattr(main, "get_storage", lambda: store)
    yield store
    closet_dir = Path(store.root) / "closet"
    shutil.rmtree(closet_dir, ignore_errors=True)
    closet_dir.mkdir(parents=True, exist_ok=True)  # the static mount needs it to exist


@pytest.fixture
def client(upload_storage, corpus):
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as test_client:
        yield test_client

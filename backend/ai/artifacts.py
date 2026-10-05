"""
Model artifact resolution for the serving runtime.

ONNX weights are too large for git, so they are published as GitHub Release
assets (see scripts/publish_models.sh) and described by the committed
ai/models/manifest.json (file name, size, sha256). Resolution order:

  1. AGENTWEAVE_MODEL_DIR (default: backend/ai/models) -- local dev / CI.
  2. AGENTWEAVE_MODEL_CACHE_DIR (default: <tmp>/agentweave-models) -- files
     downloaded by a previous invocation of a warm serverless instance.
  3. Download from AGENTWEAVE_MODEL_BASE_URL into the cache dir, verifying
     size and SHA-256 against the manifest before the file is used.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MANIFEST_PATH = os.path.join(DEFAULT_MODEL_DIR, "manifest.json")
DEFAULT_BASE_URL = "https://github.com/dhy-ani/agentweave/releases/download/models-v1"
SERVING_FILES = ("clip_vision_int8.onnx", "clip_text_int8.onnx", "yolov8n_pose.onnx")

_CHUNK = 1 << 20
_lock = threading.Lock()


class ArtifactError(RuntimeError):
    pass


def model_dir() -> str:
    return os.environ.get("AGENTWEAVE_MODEL_DIR", DEFAULT_MODEL_DIR)


def cache_dir() -> str:
    return os.environ.get(
        "AGENTWEAVE_MODEL_CACHE_DIR", os.path.join(tempfile.gettempdir(), "agentweave-models")
    )


def base_url() -> str:
    return os.environ.get("AGENTWEAVE_MODEL_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matches_size(path: str, expected: dict | None) -> bool:
    if not os.path.isfile(path):
        return False
    return expected is None or os.path.getsize(path) == expected["size"]


def _download(name: str, expected: dict, dest: str) -> None:
    url = f"{base_url()}/{name}"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(dest), prefix=f".{name}.")
    digest = hashlib.sha256()
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, os.fdopen(fd, "wb") as out:
            for chunk in iter(lambda: resp.read(_CHUNK), b""):
                digest.update(chunk)
                out.write(chunk)
        size = os.path.getsize(tmp_path)
        if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
            raise ArtifactError(
                f"{name}: checksum mismatch (got {size} bytes, sha256 {digest.hexdigest()[:12]}...)"
            )
        os.replace(tmp_path, dest)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    logger.info("Downloaded %s (%.1f MB) in %.1fs", name, expected["size"] / 1e6,
                time.perf_counter() - started)


def resolve(name: str) -> str:
    """Return a local path to model file `name`, downloading it if necessary."""
    try:
        expected = load_manifest()["files"].get(name)
    except FileNotFoundError:
        expected = None

    local = os.path.join(model_dir(), name)
    if _matches_size(local, expected):
        return local

    cached = os.path.join(cache_dir(), name)
    with _lock:
        if _matches_size(cached, expected):
            return cached
        if expected is None:
            raise ArtifactError(f"{name} not found in {model_dir()} and not listed in {MANIFEST_PATH}")
        logger.info("%s not found locally; downloading from %s", name, base_url())
        _download(name, expected, cached)
    return cached


def fetch_all(dest_dir: str = DEFAULT_MODEL_DIR) -> list[str]:
    """Ensure every manifest file is present and verified in dest_dir (build-time bundling)."""
    paths = []
    for name, expected in load_manifest()["files"].items():
        dest = os.path.join(dest_dir, name)
        if not (_matches_size(dest, expected) and sha256_of(dest) == expected["sha256"]):
            _download(name, expected, dest)
        paths.append(dest)
    return paths


def write_manifest(directory: str = DEFAULT_MODEL_DIR, files: tuple[str, ...] = SERVING_FILES,
                   **metadata) -> dict:
    """Regenerate manifest.json from the files present in `directory`.
    Extra keyword metadata (e.g. lora_merged=True) is merged into the existing manifest."""
    try:
        manifest = load_manifest()
    except FileNotFoundError:
        manifest = {}
    manifest.update(metadata)
    manifest.update({
        "release": base_url().rsplit("/", 1)[-1],
        "files": {
            name: {"size": os.path.getsize(path), "sha256": sha256_of(path)}
            for name in files
            if os.path.isfile(path := os.path.join(directory, name))
        },
    })
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return manifest

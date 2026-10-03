"""
Object storage for user-uploaded wardrobe images.

LocalStorage       development: files under backend/uploads/wardrobe, served by
                   the app's /wardrobe-images static mount.
VercelBlobStorage  used when BLOB_READ_WRITE_TOKEN is set (serverless functions
                   have a read-only filesystem, so uploads must live elsewhere).

Vercel documents Blob through its JS and Python SDKs only. The official Python
SDK (`vercel`) currently pulls in sandbox/workflow/queue packages we don't
need, so VercelBlobStorage speaks the same small HTTP protocol that SDK uses
(vercel 0.11.x, vercel/_internal/blob): PUT {api}/?pathname=... with the file
as the body, and POST {api}/delete with {"urls": [...]}.
"""
from __future__ import annotations

import logging
import os
import tempfile
from functools import lru_cache
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads", "wardrobe")

BLOB_API_URL = os.environ.get("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob")
BLOB_API_VERSION = "11"


class Storage(Protocol):
    name: str

    def save(self, key: str, data: bytes, content_type: str) -> str | None:
        """Persist `data` under `key`; return a public URL, or None when the app serves it."""

    def delete(self, key: str, url: str | None) -> None: ...


class LocalStorage:
    name = "local"

    def __init__(self, root: str = DEFAULT_UPLOAD_DIR):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key: str) -> str:
        path = os.path.abspath(os.path.join(self.root, key))
        if os.path.dirname(path) != os.path.abspath(self.root):
            raise ValueError(f"Invalid storage key: {key!r}")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> str | None:
        with open(self._path(key), "wb") as f:
            f.write(data)
        return None

    def delete(self, key: str, url: str | None) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)


class VercelBlobStorage:
    name = "vercel-blob"

    def __init__(self, token: str, prefix: str = "wardrobe/"):
        self._prefix = prefix
        self._client = httpx.Client(
            headers={"authorization": f"Bearer {token}", "x-api-version": BLOB_API_VERSION},
            timeout=30.0,
        )

    def save(self, key: str, data: bytes, content_type: str) -> str | None:
        resp = self._client.put(
            BLOB_API_URL,
            params={"pathname": f"{self._prefix}{key}"},
            content=data,
            headers={
                "x-content-type": content_type,
                "x-vercel-blob-access": "public",
                # Random suffix keeps user upload URLs unguessable.
                "x-add-random-suffix": "1",
            },
        )
        resp.raise_for_status()
        return resp.json()["url"]

    def delete(self, key: str, url: str | None) -> None:
        if not url:
            return
        self._client.post(f"{BLOB_API_URL}/delete", json={"urls": [url]}).raise_for_status()


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if token:
        return VercelBlobStorage(token)
    if os.environ.get("VERCEL"):
        logger.warning("BLOB_READ_WRITE_TOKEN is not set: wardrobe uploads are stored in /tmp "
                       "and will disappear when the function instance is recycled")
        return LocalStorage(os.path.join(tempfile.gettempdir(), "agentweave-uploads"))
    return LocalStorage(os.environ.get("AGENTWEAVE_UPLOAD_DIR", DEFAULT_UPLOAD_DIR))

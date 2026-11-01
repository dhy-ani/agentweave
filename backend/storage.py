"""
Object storage for user-uploaded closet images.

Keys are relative paths such as closet/{uid}/{item_id}.jpg.

LocalStorage       development: files under backend/uploads/<key>; closet
                   images are served by the app's /closet-images static mount.
VercelBlobStorage  used when BLOB_READ_WRITE_TOKEN is set (serverless functions
                   have a read-only filesystem, so uploads must live elsewhere).

Vercel documents Blob through its JS and Python SDKs only. The official Python
SDK (`vercel`) currently pulls in sandbox/workflow/queue packages we don't
need, so VercelBlobStorage speaks the same small HTTP protocol that SDK uses
(vercel 0.11.x, vercel/_internal/blob): PUT {api}/?pathname=... with the file
as the body, GET {api}?prefix=... to list, and POST {api}/delete with
{"urls": [...]}.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from functools import lru_cache
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads")

BLOB_API_URL = os.environ.get("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob")
BLOB_API_VERSION = "11"

_SEGMENT = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*")


def validate_key(key: str) -> str:
    """A key is '/'-separated segments of [A-Za-z0-9_.-], none starting with '.'."""
    if not all(_SEGMENT.fullmatch(part) for part in key.split("/")):
        raise ValueError(f"Invalid storage key: {key!r}")
    return key


class Storage(Protocol):
    name: str

    def save(self, key: str, data: bytes, content_type: str) -> str | None:
        """Persist `data` under `key`; return a public URL, or None when the app serves it."""

    def delete(self, key: str) -> None:
        """Remove `key`; deleting a missing key is not an error."""


class LocalStorage:
    name = "local"

    def __init__(self, root: str = DEFAULT_UPLOAD_DIR):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def path(self, key: str) -> str:
        return os.path.join(os.path.abspath(self.root), *validate_key(key).split("/"))

    def save(self, key: str, data: bytes, content_type: str) -> str | None:
        path = self.path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return None

    def delete(self, key: str) -> None:
        path = self.path(key)
        if os.path.exists(path):
            os.remove(path)


class VercelBlobStorage:
    name = "vercel-blob"

    def __init__(self, token: str):
        self._client = httpx.Client(
            headers={"authorization": f"Bearer {token}", "x-api-version": BLOB_API_VERSION},
            timeout=30.0,
        )

    def save(self, key: str, data: bytes, content_type: str) -> str | None:
        resp = self._client.put(
            BLOB_API_URL,
            params={"pathname": validate_key(key)},
            content=data,
            headers={
                "x-content-type": content_type,
                "x-vercel-blob-access": "public",
                # The key already holds a random uuid4, and a fixed pathname
                # lets delete() find the object from the key alone.
                "x-add-random-suffix": "0",
            },
        )
        resp.raise_for_status()
        return resp.json()["url"]

    def delete(self, key: str) -> None:
        resp = self._client.get(BLOB_API_URL, params={"prefix": validate_key(key), "limit": "10"})
        resp.raise_for_status()
        urls = [b["url"] for b in resp.json().get("blobs", []) if b.get("pathname") == key]
        if urls:
            self._client.post(f"{BLOB_API_URL}/delete", json={"urls": urls}).raise_for_status()


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if token:
        return VercelBlobStorage(token)
    if os.environ.get("VERCEL"):
        logger.warning("BLOB_READ_WRITE_TOKEN is not set: closet uploads are stored in /tmp "
                       "and will disappear when the function instance is recycled")
        return LocalStorage(os.path.join(tempfile.gettempdir(), "agentweave-uploads"))
    return LocalStorage(os.environ.get("AGENTWEAVE_UPLOAD_DIR", DEFAULT_UPLOAD_DIR))

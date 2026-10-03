import json
import os
from types import SimpleNamespace

import httpx
import pytest

import storage
from storage import LocalStorage, VercelBlobStorage, get_storage


# -- LocalStorage ----------------------------------------------------------------

def test_local_storage_creates_root_and_round_trips_files(tmp_path):
    root = tmp_path / "nested" / "uploads"
    store = LocalStorage(str(root))
    assert root.is_dir()
    assert store.name == "local"
    assert store.save("item.jpg", b"jpeg-bytes", "image/jpeg") is None
    assert (root / "item.jpg").read_bytes() == b"jpeg-bytes"
    store.delete("item.jpg", None)
    assert not (root / "item.jpg").exists()


def test_local_storage_delete_of_missing_file_is_a_no_op(tmp_path):
    LocalStorage(str(tmp_path)).delete("never-saved.jpg", None)


@pytest.mark.parametrize("key", ["../escape.jpg", "sub/dir.jpg", "..", "/etc/passwd"])
def test_local_storage_rejects_keys_outside_root(tmp_path, key):
    store = LocalStorage(str(tmp_path / "root"))
    with pytest.raises(ValueError, match="Invalid storage key"):
        store.save(key, b"x", "image/jpeg")
    with pytest.raises(ValueError):
        store.delete(key, None)


# -- VercelBlobStorage -------------------------------------------------------------

@pytest.fixture
def blob(monkeypatch):
    """VercelBlobStorage whose httpx client talks to an in-memory MockTransport."""
    requests: list[httpx.Request] = []
    responses: list[httpx.Response] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responses.pop(0) if responses else httpx.Response(200, json={"url": "https://blob.test/x"})

    real_client = httpx.Client
    created: list[dict] = []

    def client_factory(**kwargs):
        created.append(kwargs)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(storage, "httpx", SimpleNamespace(Client=client_factory))
    monkeypatch.setattr(storage, "BLOB_API_URL", "https://blob.test/api/blob")
    store = VercelBlobStorage("tok_123")
    return SimpleNamespace(store=store, requests=requests, responses=responses, created=created)


def test_blob_client_sends_auth_and_api_version_headers(blob):
    assert blob.store.name == "vercel-blob"
    assert blob.created[0]["timeout"] == 30.0
    blob.store.save("a.jpg", b"img", "image/jpeg")
    headers = blob.requests[0].headers
    assert headers["authorization"] == "Bearer tok_123"
    assert headers["x-api-version"] == "11"


def test_blob_save_puts_public_object_with_random_suffix(blob):
    blob.responses.append(httpx.Response(200, json={"url": "https://blob.test/wardrobe/a-xyz.jpg"}))
    url = blob.store.save("a.jpg", b"img-bytes", "image/jpeg")
    req = blob.requests[0]
    assert url == "https://blob.test/wardrobe/a-xyz.jpg"
    assert req.method == "PUT"
    assert req.url.host == "blob.test" and req.url.path == "/api/blob"
    assert req.url.params["pathname"] == "wardrobe/a.jpg"
    assert req.content == b"img-bytes"
    assert req.headers["x-content-type"] == "image/jpeg"
    assert req.headers["x-vercel-blob-access"] == "public"
    assert req.headers["x-add-random-suffix"] == "1"


def test_blob_save_raises_on_http_error(blob):
    blob.responses.append(httpx.Response(403, json={"error": "forbidden"}))
    with pytest.raises(httpx.HTTPStatusError):
        blob.store.save("a.jpg", b"x", "image/jpeg")


def test_blob_delete_posts_url_list(blob):
    blob.store.delete("a.jpg", "https://blob.test/wardrobe/a-xyz.jpg")
    req = blob.requests[0]
    assert req.method == "POST"
    assert str(req.url) == "https://blob.test/api/blob/delete"
    assert json.loads(req.content) == {"urls": ["https://blob.test/wardrobe/a-xyz.jpg"]}


def test_blob_delete_without_url_makes_no_request(blob):
    blob.store.delete("a.jpg", None)
    blob.store.delete("a.jpg", "")
    assert blob.requests == []


def test_blob_delete_raises_on_http_error(blob):
    blob.responses.append(httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        blob.store.delete("a.jpg", "https://blob.test/x")


def test_blob_custom_prefix(monkeypatch, blob):
    store = VercelBlobStorage("t", prefix="other/")
    store.save("b.jpg", b"x", "image/jpeg")
    assert blob.requests[-1].url.params["pathname"] == "other/b.jpg"


# -- get_storage ----------------------------------------------------------------------

@pytest.fixture
def fresh_get_storage():
    get_storage.cache_clear()
    yield
    get_storage.cache_clear()


def test_get_storage_uses_blob_when_token_set(monkeypatch, fresh_get_storage):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "tok")
    assert isinstance(get_storage(), VercelBlobStorage)


def test_get_storage_on_vercel_without_token_falls_back_to_tmp(monkeypatch, tmp_path, fresh_get_storage):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(storage.tempfile, "gettempdir", lambda: str(tmp_path))
    store = get_storage()
    assert isinstance(store, LocalStorage)
    assert store.root == os.path.join(str(tmp_path), "agentweave-uploads")


def test_get_storage_locally_uses_upload_dir_override(monkeypatch, tmp_path, fresh_get_storage):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "")
    monkeypatch.setenv("VERCEL", "")
    monkeypatch.setenv("AGENTWEAVE_UPLOAD_DIR", str(tmp_path / "up"))
    store = get_storage()
    assert isinstance(store, LocalStorage) and store.root == str(tmp_path / "up")
    assert get_storage() is store


def test_get_storage_locally_defaults_to_backend_uploads(monkeypatch, fresh_get_storage):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "")
    monkeypatch.setenv("VERCEL", "")
    monkeypatch.delenv("AGENTWEAVE_UPLOAD_DIR", raising=False)
    monkeypatch.setattr(storage, "LocalStorage", lambda root: SimpleNamespace(root=root))
    assert get_storage().root == storage.DEFAULT_UPLOAD_DIR

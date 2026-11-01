import json
import logging
import os
from types import SimpleNamespace

import httpx
import pytest

import storage
from storage import LocalStorage, VercelBlobStorage, get_storage


# -- keys / LocalStorage ----------------------------------------------------------

@pytest.mark.parametrize("key", ["item.jpg", "closet/uid_1-A/0123abcd.jpg", "a/b/c.d.jpg", "x-1_y"])
def test_validate_key_accepts_safe_relative_paths(key):
    assert storage.validate_key(key) == key


@pytest.mark.parametrize("key", [
    "", "../escape.jpg", "closet/../x.jpg", "..", ".hidden", "closet/./a.jpg", "/etc/passwd",
    "closet//a.jpg", "closet/a.jpg/", "a\\b.jpg", "C:x.jpg", "sp ace.jpg", "uid/é.jpg", "a.jpg\n",
])
def test_validate_key_rejects_unsafe_keys(key):
    with pytest.raises(ValueError, match="Invalid storage key"):
        storage.validate_key(key)


def test_local_storage_creates_root_and_round_trips_nested_files(tmp_path):
    root = tmp_path / "nested" / "uploads"
    store = LocalStorage(str(root))
    assert root.is_dir()
    assert store.name == "local"
    assert store.save("closet/u1/item.jpg", b"jpeg-bytes", "image/jpeg") is None
    assert (root / "closet" / "u1" / "item.jpg").read_bytes() == b"jpeg-bytes"
    assert store.path("closet/u1/item.jpg") == str(root / "closet" / "u1" / "item.jpg")
    store.save("closet/u1/item.jpg", b"new", "image/jpeg")  # overwrite in an existing dir
    assert (root / "closet" / "u1" / "item.jpg").read_bytes() == b"new"
    store.delete("closet/u1/item.jpg")
    assert not (root / "closet" / "u1" / "item.jpg").exists()


def test_local_storage_root_is_made_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = LocalStorage("rel")
    assert store.path("a.jpg") == os.path.join(str(tmp_path), "rel", "a.jpg")


def test_local_storage_delete_of_missing_file_is_a_no_op(tmp_path):
    LocalStorage(str(tmp_path)).delete("closet/never/saved.jpg")


@pytest.mark.parametrize("key", ["../escape.jpg", "closet/../../x.jpg", "..", "/etc/passwd"])
def test_local_storage_rejects_keys_outside_root(tmp_path, key):
    store = LocalStorage(str(tmp_path / "root"))
    with pytest.raises(ValueError, match="Invalid storage key"):
        store.save(key, b"x", "image/jpeg")
    with pytest.raises(ValueError):
        store.delete(key)
    assert not (tmp_path / "escape.jpg").exists()


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
    blob.store.save("closet/u/a.jpg", b"img", "image/jpeg")
    headers = blob.requests[0].headers
    assert headers["authorization"] == "Bearer tok_123"
    assert headers["x-api-version"] == "11"


def test_blob_save_puts_public_object_at_the_exact_key(blob):
    blob.responses.append(httpx.Response(200, json={"url": "https://blob.test/closet/u/a.jpg"}))
    url = blob.store.save("closet/u/a.jpg", b"img-bytes", "image/jpeg")
    req = blob.requests[0]
    assert url == "https://blob.test/closet/u/a.jpg"
    assert req.method == "PUT"
    assert req.url.host == "blob.test" and req.url.path == "/api/blob"
    assert req.url.params["pathname"] == "closet/u/a.jpg"
    assert req.content == b"img-bytes"
    assert req.headers["x-content-type"] == "image/jpeg"
    assert req.headers["x-vercel-blob-access"] == "public"
    assert req.headers["x-add-random-suffix"] == "0"


def test_blob_save_rejects_unsafe_key_without_request(blob):
    with pytest.raises(ValueError):
        blob.store.save("../x.jpg", b"x", "image/jpeg")
    with pytest.raises(ValueError):
        blob.store.delete("../x.jpg")
    assert blob.requests == []


def test_blob_save_raises_on_http_error(blob):
    blob.responses.append(httpx.Response(403, json={"error": "forbidden"}))
    with pytest.raises(httpx.HTTPStatusError):
        blob.store.save("a.jpg", b"x", "image/jpeg")


def test_blob_delete_lists_by_prefix_and_deletes_exact_pathname_only(blob):
    blob.responses.append(httpx.Response(200, json={"blobs": [
        {"url": "https://blob.test/closet/u/a.jpg", "pathname": "closet/u/a.jpg"},
        {"url": "https://blob.test/closet/u/a.jpg.bak", "pathname": "closet/u/a.jpg.bak"},
    ]}))
    blob.store.delete("closet/u/a.jpg")
    listing, deletion = blob.requests
    assert listing.method == "GET"
    assert listing.url.path == "/api/blob"
    assert listing.url.params["prefix"] == "closet/u/a.jpg"
    assert listing.url.params["limit"] == "10"
    assert deletion.method == "POST"
    assert str(deletion.url) == "https://blob.test/api/blob/delete"
    assert json.loads(deletion.content) == {"urls": ["https://blob.test/closet/u/a.jpg"]}


@pytest.mark.parametrize("listing", [{"blobs": []}, {}, {"blobs": [{"url": "u", "pathname": "closet/u/a.jpgx"}]}])
def test_blob_delete_of_missing_object_makes_no_delete_request(blob, listing):
    blob.responses.append(httpx.Response(200, json=listing))
    blob.store.delete("closet/u/a.jpg")
    assert [r.method for r in blob.requests] == ["GET"]


def test_blob_delete_raises_when_listing_fails(blob):
    blob.responses.append(httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        blob.store.delete("closet/u/a.jpg")
    assert len(blob.requests) == 1


def test_blob_delete_raises_on_http_error(blob):
    blob.responses.append(httpx.Response(200, json={"blobs": [{"url": "https://blob.test/x", "pathname": "x"}]}))
    blob.responses.append(httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        blob.store.delete("x")


# -- get_storage ----------------------------------------------------------------------

@pytest.fixture
def fresh_get_storage():
    get_storage.cache_clear()
    yield
    get_storage.cache_clear()


def test_get_storage_uses_blob_when_token_set(monkeypatch, fresh_get_storage):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "tok")
    assert isinstance(get_storage(), VercelBlobStorage)


def test_get_storage_on_vercel_without_token_falls_back_to_tmp(monkeypatch, tmp_path, fresh_get_storage, caplog):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(storage.tempfile, "gettempdir", lambda: str(tmp_path))
    with caplog.at_level(logging.WARNING, logger="storage"):
        store = get_storage()
    assert isinstance(store, LocalStorage)
    assert store.root == os.path.join(str(tmp_path), "agentweave-uploads")
    assert "BLOB_READ_WRITE_TOKEN is not set" in caplog.text


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

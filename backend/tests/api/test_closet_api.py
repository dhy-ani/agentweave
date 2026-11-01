"""/closet endpoints: auth, user isolation, validation and outfit suggestions."""
import io
import os

import numpy as np
import pytest
from PIL import Image

import image_io
from ai import model_cache
from routers import closet
from tests import tokens
from tests.fakes import image_bytes, solid_image, unit_vector_for

ALICE = tokens.bearer("alice-uid")
BOB = tokens.bearer("bob-uid")


def _upload(client, headers=ALICE, rgb=(200, 30, 30), category="tops", **kwargs):
    files = {"file": ("item.png", image_bytes(solid_image(rgb)), "image/png")}
    data = {} if category is None else {"category": category}
    return client.post("/closet/items", data=data, files=files, headers=headers, **kwargs)


def _stored(store, uid, item_id):
    return store.path(f"closet/{uid}/{item_id}.jpg")


# -- authentication -----------------------------------------------------------------

@pytest.mark.parametrize("method, path, kwargs", [
    ("post", "/closet/items", {"files": {"file": ("a.png", b"x", "image/png")}, "data": {"category": "tops"}}),
    ("post", "/closet/items", {}),
    ("delete", "/closet/items/" + "a" * 32, {}),
    ("post", "/closet/suggest", {"json": {"items": []}}),
])
@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer"},
    {"Authorization": "Basic YWxpY2U6cHc="},
    {"Authorization": "Bearer not-a-jwt"},
    {"Authorization": f"Bearer {tokens.token(aud='other-project')}"},
    {"Authorization": f"Bearer {tokens.unsigned(tokens.claims('alice-uid'))}"},
])
def test_closet_endpoints_require_a_valid_token(client, method, path, kwargs, headers):
    resp = getattr(client, method)(path, headers=headers, **kwargs) if method != "delete" else \
        client.delete(path, headers=headers)
    assert resp.status_code == 401
    assert isinstance(resp.json()["detail"], str) and resp.json()["detail"]
    assert resp.headers["www-authenticate"] == "Bearer"


def test_expired_token_detail_says_why(client):
    resp = client.post("/closet/suggest", json={"items": []},
                       headers=tokens.bearer(exp=1, iat=0, auth_time=0))
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid ID token: Token has expired."}


def test_emulator_tokens_work_in_emulator_mode(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    headers = {"Authorization": f"Bearer {tokens.unsigned(tokens.claims('emu-uid'))}"}
    assert _upload(client, headers=headers).status_code == 200


def test_closet_without_project_id_is_503(client, monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "")
    resp = _upload(client)
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Authentication is not configured on the server."}


@pytest.mark.parametrize("uid", ["../bob-uid", "a/b", "a.b", "user@example.com", "é"])
def test_uids_unsafe_for_paths_are_refused(client, uid, upload_storage):
    resp = _upload(client, headers=tokens.bearer(uid))
    assert resp.status_code == 400
    assert resp.json() == {"detail": "This account id cannot be used for closet storage."}
    assert client.delete("/closet/items/" + "a" * 32, headers=tokens.bearer(uid)).status_code == 400


# -- upload ---------------------------------------------------------------------------

def test_upload_stores_jpeg_under_the_token_uid_and_returns_embedding(client, upload_storage, fake_models):
    resp = _upload(client, category=" Tops ")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"item_id", "image_url", "category", "embedding"}
    item_id = body["item_id"]
    assert len(item_id) == 32 and int(item_id, 16) >= 0 and item_id == item_id.lower()
    assert body["category"] == "tops"
    assert body["image_url"] == f"http://testserver/closet-images/alice-uid/{item_id}.jpg"

    stored = Image.open(io.BytesIO(open(_stored(upload_storage, "alice-uid", item_id), "rb").read()))
    assert stored.format == "JPEG" and stored.size == (64, 96)

    emb = np.asarray(body["embedding"])
    assert emb.shape == (512,)
    assert np.linalg.norm(emb) == pytest.approx(1.0, abs=1e-5)
    raw = unit_vector_for(solid_image((200, 30, 30)).tobytes()).astype(np.float64)
    assert body["embedding"] == [round(float(x), 6) for x in raw / np.linalg.norm(raw)]  # float64 maths
    assert all(round(x, 6) == x for x in body["embedding"])
    assert fake_models.image_calls == 1


def test_uploaded_image_url_is_served(client, upload_storage):
    body = _upload(client).json()
    path = body["image_url"].removeprefix("http://testserver")
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(resp.content)).format == "JPEG"


def test_two_uploads_get_different_ids(client, upload_storage):
    assert _upload(client).json()["item_id"] != _upload(client).json()["item_id"]


def test_upload_returns_object_storage_url_when_storage_has_one(client, upload_storage, monkeypatch):
    saved = {}

    def save(key, data, content_type):
        saved.update(key=key, content_type=content_type, jpeg=data[:3])
        return f"https://blob.test/{key}"

    monkeypatch.setattr(upload_storage, "save", save)
    body = _upload(client, headers=BOB).json()
    assert saved["key"] == f"closet/bob-uid/{body['item_id']}.jpg"
    assert saved["content_type"] == "image/jpeg"
    assert saved["jpeg"] == b"\xff\xd8\xff"
    assert body["image_url"] == f"https://blob.test/closet/bob-uid/{body['item_id']}.jpg"


def test_upload_ignores_a_uid_form_field(client, upload_storage):
    files = {"file": ("item.png", image_bytes(solid_image()), "image/png")}
    body = client.post("/closet/items", data={"category": "tops", "firebase_uid": "bob-uid", "uid": "bob-uid"},
                       files=files, headers=ALICE).json()
    assert os.path.exists(_stored(upload_storage, "alice-uid", body["item_id"]))
    assert "/alice-uid/" in body["image_url"]
    assert not os.path.exists(os.path.join(upload_storage.root, "closet", "bob-uid"))


def test_upload_storage_failure_returns_502(client, upload_storage, monkeypatch):
    def broken(*args):
        raise OSError("disk full")

    monkeypatch.setattr(upload_storage, "save", broken)
    resp = _upload(client)
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Could not store the uploaded image."}


def test_upload_embedding_failure_returns_500_and_stores_nothing(client, upload_storage, fake_models):
    fake_models.fail_with = RuntimeError("model crashed")
    resp = _upload(client)
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Could not analyse the uploaded image."}
    assert not os.listdir(os.path.join(upload_storage.root, "closet"))


def test_upload_rejects_oversized_image_with_413(client, monkeypatch):
    monkeypatch.setattr(image_io, "MAX_UPLOAD_BYTES", 100)
    resp = _upload(client)
    assert resp.status_code == 413
    assert "larger than" in resp.json()["detail"]


def test_upload_rejects_invalid_image_with_400(client):
    resp = client.post("/closet/items", data={"category": "tops"},
                       files={"file": ("x.png", b"not an image", "image/png")}, headers=ALICE)
    assert resp.status_code == 400


@pytest.mark.parametrize("category", [None, "", "   ", "x" * 41])
def test_upload_requires_a_sensible_category(client, category, upload_storage):
    resp = _upload(client, category=category)
    assert resp.status_code == 422
    assert not os.listdir(os.path.join(upload_storage.root, "closet"))


def test_upload_accepts_a_40_char_category(client, upload_storage):
    assert _upload(client, category="x" * 40).json()["category"] == "x" * 40


def test_upload_requires_file(client):
    assert client.post("/closet/items", data={"category": "tops"}, headers=ALICE).status_code == 422


def test_embedding_out_computes_in_float64():
    vec = np.array([0.18905338644981384, -0.5227484703063965, -0.41306355595588684, -2.44146728515625],
                   dtype=np.float32)
    assert closet.embedding_out(vec) == [0.074495, -0.205985, -0.162765, -0.962044]  # float32: -0.205986


def test_embedding_out_normalises_and_rounds():
    assert closet.embedding_out(np.array([3.0, 4.0])) == [0.6, 0.8]
    assert closet.embedding_out(np.array([1.0, 1.0, 1.0])) == [0.57735] * 3 or \
        closet.embedding_out(np.array([1.0, 1.0, 1.0])) == [0.57735] * 3
    assert closet.embedding_out(np.array([1.0, 2.0, 2.0])) == [0.333333, 0.666667, 0.666667]
    with pytest.raises(ValueError, match="^Image embedding is zero.$"):
        closet.embedding_out(np.zeros(4))
    with pytest.raises(ValueError):
        closet.embedding_out(np.array([np.nan, 1.0]))


# -- delete ---------------------------------------------------------------------------

def test_delete_removes_own_file(client, upload_storage):
    item_id = _upload(client).json()["item_id"]
    path = _stored(upload_storage, "alice-uid", item_id)
    assert os.path.exists(path)
    resp = client.delete(f"/closet/items/{item_id}", headers=ALICE)
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}
    assert not os.path.exists(path)


def test_delete_is_idempotent(client, upload_storage):
    item_id = _upload(client).json()["item_id"]
    for _ in range(2):
        assert client.delete(f"/closet/items/{item_id}", headers=ALICE).json() == {"deleted": True}
    assert client.delete("/closet/items/" + "0" * 32, headers=ALICE).json() == {"deleted": True}


def test_user_cannot_delete_another_users_file(client, upload_storage):
    item_id = _upload(client, headers=ALICE).json()["item_id"]
    resp = client.delete(f"/closet/items/{item_id}", headers=BOB)
    assert resp.json() == {"deleted": True}  # bob's (nonexistent) path, not alice's
    assert os.path.exists(_stored(upload_storage, "alice-uid", item_id))


def test_delete_always_uses_the_token_uid_key(client, upload_storage, monkeypatch):
    keys = []
    monkeypatch.setattr(upload_storage, "delete", keys.append)
    client.delete("/closet/items/" + "ab" * 16, headers=BOB, params={"uid": "alice-uid"})
    assert keys == ["closet/bob-uid/" + "ab" * 16 + ".jpg"]


@pytest.mark.parametrize("item_id", [
    "a" * 31, "a" * 33, "A" * 32, "g" * 32, "..%2F..%2Fbob-uid%2F" + "a" * 20, "a" * 31 + "%2E",
    "12345678-1234-1234-1234-123456789abc",
])
def test_delete_rejects_malformed_item_ids(client, upload_storage, monkeypatch, item_id):
    keys = []
    monkeypatch.setattr(upload_storage, "delete", keys.append)
    resp = client.delete(f"/closet/items/{item_id}", headers=ALICE)
    assert resp.status_code in (404, 422)
    assert keys == []


def test_delete_rejects_malformed_item_id_with_422(client):
    resp = client.delete("/closet/items/not-hex", headers=ALICE)
    assert resp.status_code == 422


def test_delete_storage_failure_returns_502(client, upload_storage, monkeypatch):
    def broken(key):
        raise OSError("blob api down")

    monkeypatch.setattr(upload_storage, "delete", broken)
    resp = client.delete("/closet/items/" + "a" * 32, headers=ALICE)
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Could not delete the stored image."}


# -- suggest --------------------------------------------------------------------------

def _item(item_id, category, vec):
    return {"id": item_id, "category": category, "embedding": [float(x) for x in vec]}


def _query_for(occasion="casual", weather="mild", gender="", body_type=""):
    return model_cache.embed_text_ensemble(closet.outfit_prompts(occasion, weather, gender, body_type))


def test_suggest_picks_best_item_per_category_ordered_by_similarity(client, corpus):
    q = _query_for("work", "cold", body_type="pear")
    other = unit_vector_for("unrelated")
    corpus.vectors[9] = q
    items = [
        _item("top-worse", "tops", other),
        _item("top-best", "tops", q * 3),  # not unit length: normalised before scoring
        _item("shoe", "shoes", 0.5 * q + 0.5 * other),
        _item("zero", "bags", np.zeros(512)),  # unusable embedding is skipped
    ]
    resp = client.post("/closet/suggest", headers=ALICE, json={
        "occasion": "work", "weather": "cold", "body_type": "pear", "items": items,
    })
    assert resp.status_code == 200
    assert resp.json() == {
        "suggestion": "For work in cold weather, try: tops, shoes.",
        "outfit": [{"id": "top-best", "category": "tops"}, {"id": "shoe", "category": "shoes"}],
        "trend_inspiration": {"image": "look_9.jpg", "caption": "caption 9"},
    }


def test_suggest_scores_cosine_not_raw_dot_product(client, corpus):
    q = _query_for()
    o = unit_vector_for("unrelated")
    perp = o - np.dot(o, q) * q
    perp /= np.linalg.norm(perp)
    items = [
        _item("long-but-off", "tops", 5 * (0.6 * q + 0.8 * perp)),  # cosine 0.6, dot 3.0
        _item("short-but-on", "tops", 0.2 * q),  # cosine 1.0, dot 0.2
    ]
    body = client.post("/closet/suggest", headers=ALICE, json={"items": items}).json()
    assert body["outfit"] == [{"id": "short-but-on", "category": "tops"}]


def test_suggest_skips_zero_embeddings_wherever_they_are(client, corpus):
    items = [_item("zero", "bags", np.zeros(512)), _item("t", "tops", unit_vector_for("t")),
             _item("zero2", "tops", np.zeros(512))]
    body = client.post("/closet/suggest", headers=ALICE, json={"items": items}).json()
    assert body["outfit"] == [{"id": "t", "category": "tops"}]


def test_suggest_tie_keeps_first_item(client, corpus):
    v = unit_vector_for("same")
    body = client.post("/closet/suggest", headers=ALICE, json={
        "items": [_item("first", "tops", v), _item("second", "tops", v)],
    }).json()
    assert body["outfit"] == [{"id": "first", "category": "tops"}]


def test_suggest_with_only_zero_embeddings(client, corpus):
    body = client.post("/closet/suggest", headers=ALICE, json={"items": [_item("z", "tops", np.zeros(512))]}).json()
    assert body["outfit"] == []
    assert body["suggestion"] == "No matching items found."


def test_suggest_uses_default_prompts(client, corpus, fake_models):
    client.post("/closet/suggest", headers=ALICE, json={"items": [_item("t", "tops", unit_vector_for("t"))]})
    assert fake_models.text_calls[-1] == [
        "A stylish  outfit for casual in mild weather.",
        "Fashionable casual look, mild weather.",
    ]


def test_suggest_treats_null_fields_as_defaults(client, corpus, fake_models):
    body = client.post("/closet/suggest", headers=ALICE, json={
        "occasion": None, "weather": None, "gender": None, "body_type": None,
        "items": [_item("t", "tops", unit_vector_for("t"))],
    }).json()
    assert body["suggestion"] == "For casual in mild weather, try: tops."
    assert fake_models.text_calls[-1] == [
        "A stylish  outfit for casual in mild weather.",
        "Fashionable casual look, mild weather.",
    ]


def test_suggest_includes_gender_and_body_type_prompts(client, corpus, fake_models):
    client.post("/closet/suggest", headers=ALICE, json={
        "occasion": "party", "weather": "warm", "gender": "female", "body_type": "apple",
        "items": [_item("t", "tops", unit_vector_for("t"))],
    })
    assert fake_models.text_calls[-1] == [
        "A stylish female outfit for party in warm weather.",
        "Fashionable party look, warm weather.",
        "Flattering apple body shape outfit for party.",
    ]


def test_suggest_with_empty_closet_returns_400(client, corpus):
    resp = client.post("/closet/suggest", headers=ALICE, json={"items": []})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Your closet is empty: add some items first."}


def test_suggest_accepts_200_items(client, corpus):
    items = [_item(f"i{n}", f"c{n % 7}", unit_vector_for(str(n))) for n in range(200)]
    resp = client.post("/closet/suggest", headers=ALICE, json={"items": items})
    assert resp.status_code == 200
    assert len(resp.json()["outfit"]) == 7


@pytest.mark.parametrize("payload", [
    {},
    {"items": [_item(f"i{n}", "tops", unit_vector_for(str(n))) for n in range(201)]},
    {"items": [{"id": "a", "category": "tops", "embedding": [0.1] * 511}]},
    {"items": [{"id": "a", "category": "tops", "embedding": [0.1] * 513}]},
    {"items": [{"id": "a", "category": "tops", "embedding": ["x"] * 512}]},
    {"items": [{"id": "", "category": "tops", "embedding": [0.1] * 512}]},
    {"items": [{"id": "a" * 129, "category": "tops", "embedding": [0.1] * 512}]},
    {"items": [{"id": "a", "category": "", "embedding": [0.1] * 512}]},
    {"items": [{"id": "a", "category": "x" * 41, "embedding": [0.1] * 512}]},
    {"items": [{"id": "a", "category": "tops"}]},
    {"items": "nope"},
])
def test_suggest_validation_errors_are_422(client, corpus, payload):
    assert client.post("/closet/suggest", headers=ALICE, json=payload).status_code == 422


def test_suggest_rejects_non_finite_embeddings(client, corpus):
    body = '{"items": [{"id": "a", "category": "tops", "embedding": [NaN' + ", 0.1" * 511 + "]}]}"
    resp = client.post("/closet/suggest", headers={**ALICE, "Content-Type": "application/json"}, content=body)
    assert resp.status_code == 422
    assert resp.json() == {"detail": [{
        "type": "finite_number", "loc": ["body", "items", 0, "embedding", 0],
        "msg": "Input should be a finite number",
    }]}


def test_ordinary_validation_errors_keep_fastapi_format(client, corpus):
    resp = client.post("/closet/suggest", headers=ALICE, json={"items": "nope"})
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["input"] == "nope"


def test_suggest_limits():
    assert (closet.MAX_ITEMS, model_cache.EMBED_DIM, closet.MAX_CATEGORY_LENGTH) == (200, 512, 40)


def test_storage_key_format():
    assert closet.storage_key("uid1", "ab" * 16) == "closet/uid1/" + "ab" * 16 + ".jpg"

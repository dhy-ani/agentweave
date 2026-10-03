import io
import json

import numpy as np
import pytest
from PIL import Image

from ai import model_cache
from db.models import User, WardrobeItem
from routers import wardrobe
from tests.fakes import image_bytes, solid_image, unit_vector_for


def _upload(client, uid="alice", rgb=(200, 30, 30), **form):
    data = {"firebase_uid": uid, **form}
    files = {"file": ("item.png", image_bytes(solid_image(rgb)), "image/png")}
    return client.post("/wardrobe/upload", data=data, files=files)


def test_upload_stores_jpeg_and_embedding(client, upload_storage, db_session):
    resp = _upload(client, category=" Tops ", color=" navy ", description=" linen shirt ")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True and body["image_url"] is None
    assert body["category"] == " Tops "  # echoed as submitted

    stored = Image.open(io.BytesIO(open(f"{upload_storage.root}/{body['item_id']}.jpg", "rb").read()))
    assert stored.format == "JPEG"

    item = db_session.query(WardrobeItem).one()
    assert item.item_uuid == body["item_id"]
    assert item.filename == f"{body['item_id']}.jpg"
    assert (item.category, item.color, item.description) == ("tops", "navy", "linen shirt")
    vec = np.frombuffer(item.clip_embedding, dtype=np.float32)
    assert vec.shape == (512,)
    assert np.linalg.norm(vec) == pytest.approx(1.0, abs=1e-5)


def test_upload_creates_user_with_placeholder_email(client, db_session):
    _upload(client, uid="new-user")
    user = db_session.query(User).filter_by(firebase_uid="new-user").one()
    assert user.email == "new-user@users.agentweave.invalid"


def test_upload_blank_optional_fields_are_null_and_category_defaults(client, db_session):
    _upload(client, color="   ", description="")
    item = db_session.query(WardrobeItem).one()
    assert item.category == "other" and item.color is None and item.description is None


def test_upload_returns_object_storage_url(client, upload_storage, monkeypatch):
    monkeypatch.setattr(upload_storage, "save", lambda key, data, ct: f"https://blob.test/{key}")
    body = _upload(client).json()
    assert body["image_url"] == f"https://blob.test/{body['item_id']}.jpg"
    items = client.get("/wardrobe/items", params={"firebase_uid": "alice"}).json()["items"]
    assert items[0]["image_url"] == body["image_url"]


def test_upload_storage_failure_returns_502_and_saves_nothing(client, upload_storage, monkeypatch, db_session):
    def broken(*args):
        raise OSError("disk full")

    monkeypatch.setattr(upload_storage, "save", broken)
    resp = _upload(client)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Could not store the uploaded image."
    assert db_session.query(WardrobeItem).count() == 0


def test_upload_requires_firebase_uid(client):
    files = {"file": ("item.png", image_bytes(solid_image()), "image/png")}
    assert client.post("/wardrobe/upload", files=files).status_code == 422


def test_upload_rejects_invalid_image(client):
    resp = client.post("/wardrobe/upload", data={"firebase_uid": "a"},
                       files={"file": ("x.png", b"not an image", "image/png")})
    assert resp.status_code == 400


def test_items_lists_only_the_users_items(client):
    a = _upload(client, uid="alice", category="tops").json()["item_id"]
    _upload(client, uid="bob", category="shoes")
    items = client.get("/wardrobe/items", params={"firebase_uid": "alice"}).json()["items"]
    assert [i["item_uuid"] for i in items] == [a]
    assert set(items[0]) == {"id", "item_uuid", "filename", "image_url", "category", "color",
                             "description", "added_at"}


def test_items_for_unknown_user_is_empty(client):
    assert client.get("/wardrobe/items", params={"firebase_uid": "ghost"}).json() == {"items": []}


def test_delete_removes_item_and_file(client, upload_storage, db_session):
    item_id = _upload(client).json()["item_id"]
    resp = client.delete(f"/wardrobe/items/{item_id}", params={"firebase_uid": "alice"})
    assert resp.json() == {"success": True}
    assert db_session.query(WardrobeItem).count() == 0
    import os
    assert not os.path.exists(f"{upload_storage.root}/{item_id}.jpg")


def test_user_cannot_delete_another_users_item(client, db_session):
    item_id = _upload(client, uid="alice").json()["item_id"]
    resp = client.delete(f"/wardrobe/items/{item_id}", params={"firebase_uid": "bob"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Item not found."
    assert db_session.query(WardrobeItem).count() == 1


def test_delete_still_removes_row_when_storage_delete_fails(client, upload_storage, monkeypatch, db_session):
    item_id = _upload(client).json()["item_id"]

    def broken(*args):
        raise OSError("blob api down")

    monkeypatch.setattr(upload_storage, "delete", broken)
    resp = client.delete(f"/wardrobe/items/{item_id}", params={"firebase_uid": "alice"})
    assert resp.status_code == 200
    assert db_session.query(WardrobeItem).count() == 0


# -- suggest ---------------------------------------------------------------------------

def _add_item(db, user, uuid, category, vec=None, legacy=None, color=None, description=None):
    db.add(WardrobeItem(
        user_id=user.id, item_uuid=uuid, filename=f"{uuid}.jpg", category=category,
        color=color, description=description,
        clip_embedding=None if vec is None else np.asarray(vec, dtype=np.float32).tobytes(),
        clip_vector=None if legacy is None else json.dumps(list(map(float, legacy))),
    ))
    db.commit()


def _query_for(occasion="work", weather="cold", gender="", body_type=""):
    prompts = [f"A stylish {gender} outfit for {occasion} in {weather} weather.",
               f"Fashionable {occasion} look, {weather} weather."]
    if body_type:
        prompts.append(f"Flattering {body_type} body shape outfit for {occasion}.")
    return model_cache.embed_text_ensemble(prompts)


def test_suggest_with_empty_wardrobe_returns_400(client):
    resp = client.post("/wardrobe/suggest", json={"firebase_uid": "alice"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Wardrobe is empty."


def test_suggest_picks_best_item_per_category_ordered_by_similarity(client, db_session, corpus):
    q = _query_for(body_type="pear")
    user = User(firebase_uid="alice", email="a@x.test")
    db_session.add(user)
    db_session.commit()
    other = unit_vector_for("unrelated")
    _add_item(db_session, user, "top-best", "tops", vec=q * 3, color="white", description="silk blouse")
    _add_item(db_session, user, "top-worse", "tops", vec=other)
    _add_item(db_session, user, "shoe", "shoes", legacy=0.5 * q + 0.5 * other)  # legacy JSON vector
    _add_item(db_session, user, "zero", "bags", vec=np.zeros(512))  # unusable embedding
    _add_item(db_session, user, "none", "hats")  # no embedding at all
    corpus.vectors[9] = q

    resp = client.post("/wardrobe/suggest", json={
        "firebase_uid": "alice", "occasion": "work", "weather": "cold", "body_type": "pear",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert [i["item_uuid"] for i in body["outfit"]] == ["top-best", "shoe"]
    assert body["suggestion"] == "For work in cold weather, try: white silk blouse, shoes."
    assert body["trend_inspiration"] == {"image": "look_9.jpg", "caption": "caption 9"}


def test_suggest_only_uses_own_items(client, db_session, corpus):
    for uid in ("alice", "bob"):
        db_session.add(User(firebase_uid=uid, email=f"{uid}@x.test"))
    db_session.commit()
    bob = db_session.query(User).filter_by(firebase_uid="bob").one()
    _add_item(db_session, bob, "bobs", "tops", vec=unit_vector_for("b"))
    assert client.post("/wardrobe/suggest", json={"firebase_uid": "alice"}).status_code == 400


def test_suggest_when_no_item_has_an_embedding(client, db_session, corpus):
    user = User(firebase_uid="alice", email="a@x.test")
    db_session.add(user)
    db_session.commit()
    _add_item(db_session, user, "none", "tops")
    body = client.post("/wardrobe/suggest", json={"firebase_uid": "alice"}).json()
    assert body["outfit"] == []
    assert body["suggestion"] == "No matching items found."


def test_suggest_uses_default_occasion_and_weather_prompts(client, db_session, corpus, fake_models):
    user = User(firebase_uid="alice", email="a@x.test")
    db_session.add(user)
    db_session.commit()
    _add_item(db_session, user, "t", "tops", vec=unit_vector_for("t"))
    client.post("/wardrobe/suggest", json={"firebase_uid": "alice"})
    assert fake_models.text_calls[-1] == [
        "A stylish  outfit for casual in mild weather.",
        "Fashionable casual look, mild weather.",
    ]


def test_item_vector_normalises_and_handles_missing_data():
    item = WardrobeItem(clip_embedding=np.array([3, 4], dtype=np.float32).tobytes())
    np.testing.assert_allclose(wardrobe._item_vector(item), [0.6, 0.8])
    assert wardrobe._item_vector(WardrobeItem(clip_vector="[0, 2]")).tolist() == [0.0, 1.0]
    assert wardrobe._item_vector(WardrobeItem()) is None
    assert wardrobe._item_vector(WardrobeItem(clip_vector="[0, 0]")) is None

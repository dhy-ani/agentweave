from datetime import datetime, timedelta

import pytest

from db.models import SavedOutfit, ShoppingClick, StylePreference, User


def _upsert(client, uid="alice", email="alice@example.com", **extra):
    return client.post("/users/upsert", json={"firebase_uid": uid, "email": email, **extra})


def _save_outfit(client, uid="alice", image="look_1.jpg", **extra):
    return client.post("/users/outfits/save", json={
        "firebase_uid": uid, "image_filename": image, "caption": f"caption {image}", **extra,
    })


# -- profile ----------------------------------------------------------------------------

def test_upsert_creates_user(client):
    body = _upsert(client, display_name="Alice", body_type="pear", gender="female").json()
    assert body["firebase_uid"] == "alice"
    assert body["email"] == "alice@example.com"
    assert (body["display_name"], body["body_type"], body["gender"]) == ("Alice", "pear", "female")
    assert isinstance(body["id"], int)
    datetime.fromisoformat(body["created_at"])


def test_upsert_updates_only_provided_fields(client):
    first = _upsert(client, display_name="Alice", body_type="pear", gender="female").json()
    second = _upsert(client, email="changed@example.com", body_type="apple").json()
    assert second["id"] == first["id"]
    assert second["body_type"] == "apple"
    assert second["display_name"] == "Alice" and second["gender"] == "female"
    assert second["email"] == "alice@example.com"  # a real email is not overwritten


def test_upsert_updates_display_name_and_gender(client):
    _upsert(client, display_name="A", gender="female")
    body = _upsert(client, display_name="B", gender="male").json()
    assert (body["display_name"], body["gender"]) == ("B", "male")


def test_upsert_replaces_placeholder_email_from_wardrobe_user(client, db_session):
    db_session.add(User(firebase_uid="alice", email="alice@users.agentweave.invalid"))
    db_session.commit()
    assert _upsert(client, email="alice@example.com").json()["email"] == "alice@example.com"


def test_upsert_requires_email(client):
    assert client.post("/users/upsert", json={"firebase_uid": "x"}).status_code == 422


def test_get_profile(client):
    _upsert(client, body_type="hourglass")
    body = client.get("/users/alice/profile").json()
    assert body["body_type"] == "hourglass" and body["firebase_uid"] == "alice"


def test_get_profile_of_unknown_user_is_404(client):
    resp = client.get("/users/ghost/profile")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found. Call /users/upsert first."


def test_patch_profile_updates_fields_but_not_email(client):
    _upsert(client, display_name="Alice", body_type="pear", gender="female")
    body = client.patch("/users/alice/profile", json={
        "firebase_uid": "alice", "email": "other@example.com", "body_type": "rectangle", "gender": "nb",
    }).json()
    assert (body["body_type"], body["gender"], body["display_name"]) == ("rectangle", "nb", "Alice")
    assert body["email"] == "alice@example.com"
    body = client.patch("/users/alice/profile", json={
        "firebase_uid": "alice", "email": "x", "display_name": "Al",
    }).json()
    assert (body["display_name"], body["body_type"]) == ("Al", "rectangle")


def test_patch_profile_of_unknown_user_is_404(client):
    resp = client.patch("/users/ghost/profile", json={"firebase_uid": "ghost", "email": "g@x"})
    assert resp.status_code == 404


# -- outfits --------------------------------------------------------------------------------

def test_save_and_list_outfits_newest_first(client, db_session):
    _upsert(client)
    first = _save_outfit(client, image="a.jpg", trendiness_score=87.5, occasion="work", weather="cold",
                         future_projection="Strong match").json()
    second = _save_outfit(client, image="b.jpg").json()
    assert first["saved"] is True and second["outfit_id"] != first["outfit_id"]
    # Make the order unambiguous regardless of clock resolution.
    db_session.get(SavedOutfit, first["outfit_id"]).saved_at = datetime(2024, 1, 1)
    db_session.get(SavedOutfit, second["outfit_id"]).saved_at = datetime(2024, 1, 2)
    db_session.commit()

    outfits = client.get("/users/alice/outfits").json()["outfits"]
    assert [o["image_filename"] for o in outfits] == ["b.jpg", "a.jpg"]
    a = outfits[1]
    assert a["caption"] == "caption a.jpg" and a["trendiness_score"] == 87.5
    assert (a["occasion"], a["weather"], a["future_projection"]) == ("work", "cold", "Strong match")
    assert a["saved_at"] == "2024-01-01T00:00:00"
    assert outfits[0]["trendiness_score"] == 0.0


def test_list_outfits_is_scoped_to_user(client):
    _upsert(client, "alice", "a@x.test")
    _upsert(client, "bob", "b@x.test")
    _save_outfit(client, "alice", "a.jpg")
    assert client.get("/users/bob/outfits").json() == {"outfits": []}


def test_save_outfit_for_unknown_user_is_404(client):
    assert _save_outfit(client, uid="ghost").status_code == 404


def test_delete_own_outfit(client):
    _upsert(client)
    oid = _save_outfit(client).json()["outfit_id"]
    resp = client.delete(f"/users/outfits/{oid}", params={"firebase_uid": "alice"})
    assert resp.json() == {"deleted": True}
    assert client.get("/users/alice/outfits").json()["outfits"] == []


def test_cannot_delete_another_users_outfit(client):
    _upsert(client, "alice", "a@x.test")
    _upsert(client, "bob", "b@x.test")
    oid = _save_outfit(client, "alice").json()["outfit_id"]
    resp = client.delete(f"/users/outfits/{oid}", params={"firebase_uid": "bob"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Outfit not found."
    assert len(client.get("/users/alice/outfits").json()["outfits"]) == 1


def test_delete_missing_outfit_is_404(client):
    _upsert(client)
    assert client.delete("/users/outfits/999", params={"firebase_uid": "alice"}).status_code == 404


# -- swipes / preferences ----------------------------------------------------------------------

def _swipe(client, liked, image="look_1.jpg", uid="alice", occasion=None):
    return client.post("/users/swipe", json={
        "firebase_uid": uid, "image_filename": image, "caption": "cap", "liked": liked, "occasion": occasion,
    })


def test_swipe_upserts_one_preference_per_image(client, db_session):
    _upsert(client)
    assert _swipe(client, True, occasion="party").json() == {"recorded": True}
    assert _swipe(client, False).json() == {"recorded": True}
    prefs = db_session.query(StylePreference).all()
    assert len(prefs) == 1
    assert prefs[0].liked is False
    assert prefs[0].occasion == "party"


def test_preferences_returns_only_liked_newest_first(client, db_session):
    _upsert(client)
    _swipe(client, True, image="a.jpg", occasion="work")
    _swipe(client, True, image="b.jpg")
    _swipe(client, False, image="c.jpg")
    base = datetime(2024, 5, 1)
    for offset, name in enumerate(["a.jpg", "b.jpg", "c.jpg"]):
        db_session.query(StylePreference).filter_by(image_filename=name).one().recorded_at = (
            base + timedelta(days=offset))
    db_session.commit()

    liked = client.get("/users/alice/preferences").json()["liked_styles"]
    assert [p["image_filename"] for p in liked] == ["b.jpg", "a.jpg"]
    assert liked[1] == {"image_filename": "a.jpg", "caption": "cap", "liked": True, "occasion": "work",
                        "recorded_at": "2024-05-01T00:00:00"}


def test_preferences_are_limited_to_50(client, db_session):
    _upsert(client)
    user = db_session.query(User).one()
    db_session.add_all(StylePreference(user_id=user.id, image_filename=f"{i}.jpg", caption="c", liked=True)
                       for i in range(55))
    db_session.commit()
    assert len(client.get("/users/alice/preferences").json()["liked_styles"]) == 50


def test_swipe_for_unknown_user_is_404(client):
    assert _swipe(client, True, uid="ghost").status_code == 404


# -- shopping clicks -----------------------------------------------------------------------------

def test_shopping_click_and_history(client, db_session):
    _upsert(client)
    resp = client.post("/users/shopping/click", json={
        "firebase_uid": "alice", "brand": "Zara", "item": "Blazer", "tier": "Budget", "est_price": 50,
        "occasion": "work",
    })
    assert resp.json() == {"recorded": True}
    client.post("/users/shopping/click", json={
        "firebase_uid": "alice", "brand": "Theory", "item": "Coat", "tier": "Premium", "est_price": 280,
    })
    db_session.query(ShoppingClick).filter_by(brand="Zara").one().clicked_at = datetime(2024, 1, 1)
    db_session.query(ShoppingClick).filter_by(brand="Theory").one().clicked_at = datetime(2024, 2, 1)
    db_session.commit()

    history = client.get("/users/alice/shopping/history").json()["history"]
    assert [h["brand"] for h in history] == ["Theory", "Zara"]
    assert history[1] == {"brand": "Zara", "item": "Blazer", "tier": "Budget", "est_price": 50.0,
                          "occasion": "work", "clicked_at": "2024-01-01T00:00:00"}


def test_shopping_history_is_limited_to_100(client, db_session):
    _upsert(client)
    user = db_session.query(User).one()
    db_session.add_all(ShoppingClick(user_id=user.id, brand="b", item="i", tier="t", est_price=1.0)
                       for _ in range(105))
    db_session.commit()
    assert len(client.get("/users/alice/shopping/history").json()["history"]) == 100


@pytest.mark.parametrize("path", ["/users/ghost/outfits", "/users/ghost/preferences",
                                  "/users/ghost/shopping/history"])
def test_reads_for_unknown_user_are_404(client, path):
    assert client.get(path).status_code == 404


def test_shopping_click_for_unknown_user_is_404(client):
    resp = client.post("/users/shopping/click", json={
        "firebase_uid": "ghost", "brand": "b", "item": "i", "tier": "t", "est_price": 1,
    })
    assert resp.status_code == 404

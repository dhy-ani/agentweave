import image_io
from tests.fakes import body_keypoints, image_bytes, solid_image


def _png(**kwargs):
    return {"file": ("photo.png", image_bytes(solid_image(**kwargs)), "image/png")}


def test_root_reports_running(client):
    assert client.get("/").json() == {"status": "StyleGenie backend is running"}


def test_health_reports_runtime_without_torch(client):
    body = client.get("/health").json()
    assert body == {
        "status": "ok",
        "model_backend": "onnx",
        "models_loaded": {"clip_vision": True, "clip_text": True, "pose": True},
        "torch_imported": False,
        "database": "sqlite",
        "storage": "local",
    }


def test_cors_allows_default_frontend_origin(client):
    resp = client.options("/health", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
    })
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client):
    resp = client.options("/health", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET",
    })
    assert "access-control-allow-origin" not in resp.headers


def test_analyze_body_returns_body_type(client, fake_pose):
    fake_pose.result = body_keypoints(shoulder_w=0.7, hip_w=1.0, waist_w=0.7)
    resp = client.post("/analyze-body", files=_png())
    assert resp.status_code == 200
    assert resp.json() == {"body_type": "pear"}


def test_analyze_body_without_person_returns_error_message(client, fake_pose):
    fake_pose.result = None
    resp = client.post("/analyze-body", files=_png())
    assert resp.status_code == 200
    assert resp.json() == {"error": "Prediction failed: No keypoints detected."}


def test_analyze_body_with_partial_body_returns_error_message(client, fake_pose):
    fake_pose.result = [[0.5, 0.5]] * 5
    assert "Incomplete keypoints" in client.post("/analyze-body", files=_png()).json()["error"]


def test_analyze_body_rejects_oversized_upload_with_413(client, monkeypatch):
    monkeypatch.setattr(image_io, "MAX_UPLOAD_BYTES", 100)
    resp = client.post("/analyze-body", files=_png(size=(64, 64)))
    assert resp.status_code == 413
    assert "larger than" in resp.json()["detail"]


def test_analyze_body_rejects_non_image_with_400(client):
    resp = client.post("/analyze-body", files={"file": ("x.txt", b"hello", "text/plain")})
    assert resp.status_code == 400


def test_analyze_body_requires_file(client):
    assert client.post("/analyze-body").status_code == 422

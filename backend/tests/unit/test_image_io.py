import asyncio
import io

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

import image_io
from image_io import read_image, to_jpeg
from tests.fakes import image_bytes


def _read(data: bytes) -> Image.Image:
    return asyncio.run(read_image(UploadFile(io.BytesIO(data), filename="upload")))


def _exif_jpeg(size=(40, 20), orientation=6) -> bytes:
    exif = Image.Exif()
    exif[0x0112] = orientation  # Orientation
    exif[0x010F] = "PhoneMaker"  # Make
    return image_bytes(Image.new("RGB", size, (255, 0, 0)), "JPEG", exif=exif.tobytes())


def test_read_image_returns_rgb_image():
    image = _read(image_bytes(Image.new("RGBA", (12, 8), (1, 2, 3, 128))))
    assert image.mode == "RGB"
    assert image.size == (12, 8)
    assert image.getpixel((0, 0)) == (1, 2, 3)


def test_read_image_applies_exif_orientation():
    image = _read(_exif_jpeg(size=(40, 20), orientation=6))
    assert image.size == (20, 40)


def test_read_image_rejects_non_images_with_400():
    with pytest.raises(HTTPException) as exc:
        _read(b"definitely not an image")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Uploaded file is not a valid image."


def test_read_image_rejects_truncated_image_with_400():
    data = image_bytes(Image.new("RGB", (200, 200), (9, 9, 9)), "JPEG")
    with pytest.raises(HTTPException) as exc:
        _read(data[: len(data) // 2])
    assert exc.value.status_code == 400


def test_read_image_rejects_empty_upload_with_400():
    with pytest.raises(HTTPException) as exc:
        _read(b"")
    assert exc.value.status_code == 400


def test_read_image_over_limit_raises_413(monkeypatch):
    data = image_bytes(Image.new("RGB", (32, 32), (5, 5, 5)))
    monkeypatch.setattr(image_io, "MAX_UPLOAD_BYTES", len(data) - 1)
    with pytest.raises(HTTPException) as exc:
        _read(data)
    assert exc.value.status_code == 413
    assert "larger than" in exc.value.detail and "MB" in exc.value.detail


def test_read_image_exactly_at_limit_is_accepted(monkeypatch):
    data = image_bytes(Image.new("RGB", (32, 32), (5, 5, 5)))
    monkeypatch.setattr(image_io, "MAX_UPLOAD_BYTES", len(data))
    assert _read(data).size == (32, 32)


def test_read_image_limit_is_checked_while_streaming(monkeypatch):
    # Limit hit in the first chunk: the rest of the upload must not be consumed.
    monkeypatch.setattr(image_io, "MAX_UPLOAD_BYTES", 10)
    monkeypatch.setattr(image_io, "_READ_CHUNK", 16)
    stream = io.BytesIO(b"x" * 1000)
    with pytest.raises(HTTPException):
        asyncio.run(read_image(UploadFile(stream)))
    assert stream.tell() == 16


def test_413_message_reports_limit_in_megabytes(monkeypatch):
    monkeypatch.setattr(image_io, "MAX_UPLOAD_BYTES", 2_500_000)
    monkeypatch.setattr(image_io, "_READ_CHUNK", 3_000_000)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_image(UploadFile(io.BytesIO(b"x" * 2_500_001))))
    assert "2.5 MB" in exc.value.detail


def test_default_upload_limit_matches_vercel_body_limit():
    assert image_io.MAX_UPLOAD_BYTES == 4_500_000


def test_to_jpeg_reencodes_and_strips_exif():
    original = Image.open(io.BytesIO(_exif_jpeg()))
    assert dict(original.getexif())  # source carries EXIF
    out = Image.open(io.BytesIO(to_jpeg(original)))
    assert out.format == "JPEG"
    assert dict(out.getexif()) == {}
    assert out.size == original.size


def test_to_jpeg_quality_controls_size():
    noisy = Image.effect_noise((128, 128), 80).convert("RGB")
    assert len(to_jpeg(noisy, quality=30)) < len(to_jpeg(noisy)) < len(to_jpeg(noisy, quality=100))


def test_413_message_text(monkeypatch):
    monkeypatch.setattr(image_io, "MAX_UPLOAD_BYTES", 1_000_000)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_image(UploadFile(io.BytesIO(b"x" * 1_000_001))))
    assert exc.value.detail == "Image is larger than 1.0 MB. Please upload a smaller or downscaled image."


def test_to_jpeg_default_quality_is_90():
    noisy = Image.effect_noise((64, 64), 80).convert("RGB")
    assert to_jpeg(noisy) == to_jpeg(noisy, quality=90)

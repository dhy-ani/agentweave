"""Validated image uploads shared by every endpoint that accepts a file."""
from __future__ import annotations

import io
import os

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

# Vercel rejects request bodies over 4.5 MB before they reach the function, so
# enforce the same ceiling everywhere to get identical behaviour locally.
MAX_UPLOAD_BYTES = int(float(os.environ.get("AGENTWEAVE_MAX_UPLOAD_MB", "4.5")) * 1_000_000)
_READ_CHUNK = 1 << 16


async def read_image(file: UploadFile) -> Image.Image:
    """Read an uploaded image as upright RGB, enforcing the size limit (413) and validity (400)."""
    buf = bytearray()
    while chunk := await file.read(_READ_CHUNK):
        buf.extend(chunk)
        if len(buf) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image is larger than {MAX_UPLOAD_BYTES / 1e6:.1f} MB. "
                       "Please upload a smaller or downscaled image.",
            )
    try:
        image = Image.open(io.BytesIO(buf))
        image.load()
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.") from exc
    return image.convert("RGB")


def to_jpeg(image: Image.Image, quality: int = 90) -> bytes:
    """Re-encode for storage. Drops EXIF (e.g. GPS location) from user photos."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

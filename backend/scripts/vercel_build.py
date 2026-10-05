"""
Vercel build step (vercel.json "buildCommand"); runs after dependencies are installed.

1. Copies the curated dataset images (../datasets/processedImages, outside the
   backend/ root directory) into static/images so they ship with the function
   and are served at /images/... . Requires the project setting "Include files
   outside the root directory in the Build Step" (on by default).
2. Downloads the ONNX models listed in ai/models/manifest.json into ai/models/
   (SHA-256 verified) so cold starts don't download ~170 MB into /tmp.
   Set AGENTWEAVE_BUNDLE_MODELS=0 to skip and download lazily at runtime.
"""
from __future__ import annotations

import os
import shutil
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from ai import artifacts  # noqa: E402

SOURCE_IMAGES = os.path.abspath(os.path.join(BACKEND_DIR, "..", "datasets", "processedImages"))
TARGET_IMAGES = os.path.join(BACKEND_DIR, "static", "images")


def copy_images() -> None:
    if not os.path.isdir(SOURCE_IMAGES):
        print(f"WARNING: {SOURCE_IMAGES} not found; /images will not be served by this deployment")
        return
    shutil.rmtree(TARGET_IMAGES, ignore_errors=True)
    shutil.copytree(SOURCE_IMAGES, TARGET_IMAGES)
    print(f"Copied {len(os.listdir(TARGET_IMAGES))} curated images to {TARGET_IMAGES}")


def bundle_models() -> None:
    if os.environ.get("AGENTWEAVE_BUNDLE_MODELS", "1") == "0":
        print("AGENTWEAVE_BUNDLE_MODELS=0: models will be downloaded at runtime")
        return
    for path in artifacts.fetch_all():
        print(f"Bundled {os.path.basename(path)} ({os.path.getsize(path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    copy_images()
    bundle_models()

"""
Process-wide configuration read from the environment (see .env.example).

Importing this module loads backend/.env (if present) without overriding
variables that are already set, so it must be imported before anything that
reads os.environ at import time.
"""
from __future__ import annotations

import logging
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3100",
    "https://dhy-ani.github.io",
)


def _load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(BACKEND_DIR, ".env"))


def cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

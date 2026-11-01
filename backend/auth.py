"""
Firebase ID token verification for endpoints that act on a user's own files.

Follows "Verify ID tokens using a third-party JWT library"
(https://firebase.google.com/docs/auth/admin/verify-id-tokens), without the
firebase-admin dependency:

  header   alg == "RS256"; kid names one of Google's securetoken x509 certs
  payload  exp in the future; iat and auth_time in the past;
           aud == FIREBASE_PROJECT_ID;
           iss == "https://securetoken.google.com/<FIREBASE_PROJECT_ID>";
           sub a non-empty string (at most 128 chars), which is the uid
  signature verified with the public key of the cert named by kid; the certs
           are cached in memory for the Cache-Control max-age of the response.

Emulator mode (FIREBASE_AUTH_EMULATOR_HOST set): the Auth emulator issues
unsigned tokens (alg "none"), so the signature check is skipped, exactly as the
Admin SDK does; every claim check above still applies. Unsigned tokens are
never accepted otherwise.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Callable

import httpx
import jwt
from cryptography import x509
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

CERTS_URL = ("https://www.googleapis.com/robot/v1/metadata/x509/"
             "securetoken@system.gserviceaccount.com")
ISSUER_PREFIX = "https://securetoken.google.com/"
ALGORITHM = "RS256"
# Tolerated clock difference between Google's servers and this one.
CLOCK_SKEW_SECONDS = 10
MAX_UID_LENGTH = 128


class AuthError(Exception):
    """The token is missing, malformed or fails a check (-> HTTP 401)."""


class AuthConfigError(Exception):
    """The server cannot verify tokens: missing config or signing keys (-> HTTP 503)."""


def project_id() -> str:
    return os.environ.get("FIREBASE_PROJECT_ID", "").strip()


def emulator_host() -> str:
    return os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "").strip()


def emulator_mode() -> bool:
    return bool(emulator_host())


def max_age_seconds(cache_control: str) -> int:
    """`max-age` from a Cache-Control header, in seconds; 0 (don't cache) if absent."""
    match = re.search(r"max-age=(\d+)", cache_control)
    return int(match.group(1)) if match else 0


def fetch_certs() -> tuple[dict[str, str], int]:
    """Google's current signing certs ({kid: PEM}) and how long they may be cached."""
    resp = httpx.get(CERTS_URL, timeout=10.0)
    resp.raise_for_status()
    return resp.json(), max_age_seconds(resp.headers.get("cache-control", ""))


class CertCache:
    """Public keys by kid, refreshed once the previous response's max-age has passed."""

    def __init__(self, fetch: Callable[[], tuple[dict[str, str], int]] = fetch_certs,
                 clock: Callable[[], float] = time.time):
        self._fetch = fetch
        self._clock = clock
        self._keys: dict[str, object] = {}
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def keys(self) -> dict[str, object]:
        with self._lock:
            if self._clock() >= self._expires_at:
                try:
                    certs, max_age = self._fetch()
                    self._keys = {kid: x509.load_pem_x509_certificate(pem.encode()).public_key()
                                  for kid, pem in certs.items()}
                except Exception as exc:
                    logger.exception("Fetching Firebase signing certificates failed")
                    raise AuthConfigError("Could not fetch Firebase signing keys.") from exc
                self._expires_at = self._clock() + max_age
            return self._keys


_cert_cache = CertCache()


def _number(claims: dict, name: str) -> float:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuthError(f"Token has no valid '{name}' claim.")
    return value


def validate_claims(claims: dict, project: str, now: float) -> str:
    """Check the payload claims; return the uid (sub)."""
    if claims.get("aud") != project:
        raise AuthError("Token has the wrong audience (aud).")
    if claims.get("iss") != ISSUER_PREFIX + project:
        raise AuthError("Token has the wrong issuer (iss).")
    if _number(claims, "exp") <= now - CLOCK_SKEW_SECONDS:
        raise AuthError("Token has expired.")
    if _number(claims, "iat") > now + CLOCK_SKEW_SECONDS:
        raise AuthError("Token was issued in the future (iat).")
    if _number(claims, "auth_time") > now + CLOCK_SKEW_SECONDS:
        raise AuthError("Token has an authentication time in the future (auth_time).")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > MAX_UID_LENGTH:
        raise AuthError("Token has no valid subject (sub).")
    return sub


def verify_id_token(token: str, project: str, *, emulator: bool = False,
                    certs: CertCache | None = None, now: float | None = None) -> str:
    """Verify a Firebase ID token and return its uid. Raises AuthError if it is not valid."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError("Token is malformed.") from exc

    # PyJWT checks the signature (and nbf, which Firebase tokens don't carry);
    # validate_claims checks every Firebase claim with one clock and leeway.
    no_claim_checks = {"verify_exp": False, "verify_iat": False, "verify_aud": False}
    try:
        if emulator:
            claims = jwt.decode(token, options={"verify_signature": False, **no_claim_checks})
        else:
            if header.get("alg") != ALGORITHM:
                raise AuthError("Token must be signed with RS256.")
            # PyJWT has already rejected a kid that is not a string.
            key = (certs or _cert_cache).keys().get(header.get("kid"))
            if key is None:
                raise AuthError("Token was signed with an unknown key (kid).")
            claims = jwt.decode(token, key=key, algorithms=[ALGORITHM], options=no_claim_checks)
    except jwt.InvalidSignatureError as exc:
        raise AuthError("Token signature is invalid.") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Token is malformed.") from exc

    return validate_claims(claims, project, time.time() if now is None else now)


_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def current_uid(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    """FastAPI dependency: the uid of the verified `Authorization: Bearer <ID token>`."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign-in required: send a Firebase ID token "
                            "as 'Authorization: Bearer <token>'.", headers=_CHALLENGE)
    project = project_id()
    if not project:
        logger.error("FIREBASE_PROJECT_ID is not set: authenticated endpoints are unavailable")
        raise HTTPException(status_code=503, detail="Authentication is not configured on the server.")
    try:
        return verify_id_token(credentials.credentials, project, emulator=emulator_mode())
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid ID token: {exc}", headers=_CHALLENGE) from exc
    except AuthConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def auth_mode() -> str:
    """Reported by /health."""
    return "firebase-emulator" if emulator_mode() else "firebase"


def log_startup_config() -> None:
    if emulator_mode():
        logger.warning("FIREBASE_AUTH_EMULATOR_HOST=%s: Firebase Auth EMULATOR MODE is ON. Unsigned "
                       "ID tokens are accepted. Never set this in production.", emulator_host())
    if not project_id():
        logger.warning("FIREBASE_PROJECT_ID is not set: /closet endpoints will return 503")

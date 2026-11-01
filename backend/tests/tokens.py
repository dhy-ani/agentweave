"""Test-only Firebase ID tokens: an RSA keypair, a self-signed x509 cert and a token factory."""
from __future__ import annotations

import base64
import datetime as dt
import json
import time
from functools import lru_cache

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

PROJECT_ID = "demo-test"
KID = "test-kid-1"


def keypair(name: str = "main") -> tuple[rsa.RSAPrivateKey, str]:
    """(private key, PEM x509 cert of its public key); one per name, generated once."""
    return _keypair(name)


@lru_cache(maxsize=None)
def _keypair(name: str) -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"securetoken-{name}")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=30))
            .sign(key, hashes.SHA256()))
    return key, cert.public_bytes(serialization.Encoding.PEM).decode()


def claims(uid: str = "alice-uid", project: str = PROJECT_ID, now: float | None = None, **overrides) -> dict:
    now = time.time() if now is None else now
    payload = {
        "iss": f"https://securetoken.google.com/{project}",
        "aud": project,
        "auth_time": int(now) - 60,
        "user_id": uid,
        "sub": uid,
        "iat": int(now) - 30,
        "exp": int(now) + 3600,
        "firebase": {"identities": {}, "sign_in_provider": "password"},
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not ...}  # `...` drops a claim


def sign(payload: dict, kid: str | None = KID, key_name: str = "main", alg: str = "RS256") -> str:
    headers = {} if kid is None else {"kid": kid}
    return jwt.encode(payload, keypair(key_name)[0], algorithm=alg, headers=headers)


def token(uid: str = "alice-uid", **overrides) -> str:
    return sign(claims(uid, **overrides))


def unsigned(payload: dict) -> str:
    """An emulator-style token: header {"alg": "none"} and an empty signature."""
    def b64(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(payload)}."


def bearer(uid: str = "alice-uid", **overrides) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(uid, **overrides)}"}

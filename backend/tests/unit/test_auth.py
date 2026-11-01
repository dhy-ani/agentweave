"""auth.py: Firebase ID token verification (no network; signed with tests/tokens.py keys)."""
import base64
import hashlib
import hmac
import json
import logging
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import auth
from tests import tokens
from tests.tokens import KID, PROJECT_ID, claims, sign, unsigned

NOW = 1_800_000_000.0


def verify(token, **kwargs):
    kwargs.setdefault("now", NOW)
    return auth.verify_id_token(token, PROJECT_ID, **kwargs)


def signed(**overrides):
    return sign(claims(now=NOW, **overrides))


def rejected(token, match, **kwargs):
    with pytest.raises(auth.AuthError, match=match):
        verify(token, **kwargs)


# -- valid tokens ------------------------------------------------------------------

def test_valid_token_returns_sub_as_uid():
    assert verify(signed(uid="user-123")) == "user-123"


def test_uid_of_128_chars_is_accepted():
    assert verify(signed(uid="u" * 128)) == "u" * 128


def test_verify_uses_current_time_by_default():
    assert auth.verify_id_token(tokens.token("now-user"), PROJECT_ID) == "now-user"


def test_small_clock_skew_is_tolerated():
    skew = auth.CLOCK_SKEW_SECONDS
    assert verify(signed(iat=NOW + skew, auth_time=NOW + skew, exp=NOW - skew + 1)) == "alice-uid"


def test_clock_skew_is_small():
    assert 0 < auth.CLOCK_SKEW_SECONDS <= 60


# -- claim checks --------------------------------------------------------------------

def test_wrong_audience_is_rejected():
    rejected(signed(aud="another-project"), "audience")


def test_audience_list_is_rejected():
    rejected(signed(aud=[PROJECT_ID]), "audience")


def test_missing_audience_is_rejected():
    rejected(signed(aud=...), "audience")


def test_wrong_issuer_is_rejected():
    rejected(signed(iss="https://securetoken.google.com/another-project"), "issuer")
    rejected(signed(iss=f"https://evil.example/{PROJECT_ID}"), "issuer")


def test_missing_issuer_is_rejected():
    rejected(signed(iss=...), "issuer")


def test_expired_token_is_rejected():
    rejected(signed(exp=NOW - auth.CLOCK_SKEW_SECONDS), "expired")
    rejected(signed(exp=NOW - 3600), "expired")


@pytest.mark.parametrize("value", [..., "2099-01-01", None, True])
def test_missing_or_non_numeric_exp_is_rejected(value):
    rejected(signed(exp=value), "'exp'")


def test_iat_in_the_future_is_rejected():
    rejected(signed(iat=NOW + auth.CLOCK_SKEW_SECONDS + 1), "issued in the future")


@pytest.mark.parametrize("value", [..., "0", None, False])
def test_missing_or_non_numeric_iat_is_rejected(value):
    rejected(signed(iat=value), "'iat'")


def test_auth_time_in_the_future_is_rejected():
    rejected(signed(auth_time=NOW + auth.CLOCK_SKEW_SECONDS + 1), "auth_time")


def test_missing_auth_time_is_rejected():
    rejected(signed(auth_time=...), "'auth_time'")


def test_float_timestamps_are_accepted():
    assert verify(signed(iat=NOW - 1.5, auth_time=NOW - 2.5, exp=NOW + 10.5)) == "alice-uid"


@pytest.mark.parametrize("sub", [..., "", "u" * 129])
def test_missing_empty_or_too_long_sub_is_rejected(sub):
    rejected(signed(sub=sub), "subject")


def test_non_string_sub_is_rejected():
    # PyJWT itself refuses a non-string sub while decoding.
    rejected(signed(sub=12345), "Token is malformed")


def test_nbf_in_the_future_is_rejected():
    rejected(sign(claims(nbf=time.time() + 3600)), "Token is malformed")


def test_validate_claims_rejects_non_string_sub_directly():
    with pytest.raises(auth.AuthError, match="subject"):
        auth.validate_claims(claims(now=NOW, sub=12345), PROJECT_ID, NOW)


def test_validate_claims_returns_sub():
    assert auth.validate_claims(claims("bob", now=NOW), PROJECT_ID, NOW) == "bob"


@pytest.mark.parametrize("make, message", [
    (lambda: signed(aud="x"), "Token has the wrong audience (aud)."),
    (lambda: signed(iss="x"), "Token has the wrong issuer (iss)."),
    (lambda: signed(exp=NOW - 3600), "Token has expired."),
    (lambda: signed(exp=...), "Token has no valid 'exp' claim."),
    (lambda: signed(iat=NOW + 3600), "Token was issued in the future (iat)."),
    (lambda: signed(auth_time=NOW + 3600), "Token has an authentication time in the future (auth_time)."),
    (lambda: signed(sub=""), "Token has no valid subject (sub)."),
    (lambda: "not-a-jwt", "Token is malformed."),
    (lambda: signed(sub=12345), "Token is malformed."),
    (lambda: sign(claims(now=NOW), key_name="attacker"), "Token signature is invalid."),
    (lambda: sign(claims(now=NOW), kid="gone"), "Token was signed with an unknown key (kid)."),
    (lambda: unsigned(claims(now=NOW)), "Token must be signed with RS256."),
])
def test_error_messages_are_exact(make, message):
    with pytest.raises(auth.AuthError) as err:
        verify(make())
    assert str(err.value) == message


# -- header and signature ------------------------------------------------------------

def test_wrong_signature_is_rejected(signing_certs):
    other_key_token = sign(claims(now=NOW), key_name="attacker")  # signed by another key, same kid
    rejected(other_key_token, "signature is invalid")


def test_tampered_payload_is_rejected():
    header, _, signature = signed(uid="alice").split(".")
    _, payload, _ = signed(uid="mallory").split(".")
    rejected(f"{header}.{payload}.{signature}", "signature is invalid")


def test_unknown_kid_is_rejected():
    rejected(sign(claims(now=NOW), kid="rotated-away"), "unknown key")


def test_missing_kid_is_rejected():
    rejected(sign(claims(now=NOW), kid=None), "unknown key")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _hand_made(header: dict, payload: dict, sign_with=None) -> str:
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}"
    signature = sign_with(signing_input.encode()) if sign_with else b"sig"
    return f"{signing_input}.{_b64(signature)}"


def test_non_string_kid_is_rejected():
    rejected(_hand_made({"alg": "RS256", "kid": ["x"]}, claims(now=NOW)), "malformed")


def test_kid_from_another_cert_in_the_set_is_used(signing_certs):
    signing_certs["certs"]["second"] = tokens.keypair("second")[1]
    assert verify(sign(claims("carol", now=NOW), kid="second", key_name="second")) == "carol"


@pytest.mark.parametrize("alg", ["RS512", "PS256", "HS256"])
def test_algorithms_other_than_rs256_are_rejected(alg):
    if alg == "HS256":
        token = jwt.encode(claims(now=NOW), "secret-secret-secret-secret-1234", algorithm="HS256",
                           headers={"kid": KID})
    else:
        token = sign(claims(now=NOW), alg=alg)
    rejected(token, "RS256")


def test_hs256_signed_with_public_cert_is_rejected():
    # Classic algorithm-confusion attack: HMAC keyed with the public cert.
    cert = tokens.keypair()[1].encode()
    token = _hand_made({"alg": "HS256", "kid": KID}, claims(now=NOW),
                       sign_with=lambda data: hmac.new(cert, data, hashlib.sha256).digest())
    rejected(token, "RS256")


def test_alg_none_is_rejected_outside_emulator_mode():
    rejected(unsigned(claims(now=NOW)), "RS256")


def test_rs256_header_with_empty_signature_is_rejected():
    header, payload, _ = signed().split(".")
    with pytest.raises(auth.AuthError):
        verify(f"{header}.{payload}.")


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c", "....", "eyJhbGciOiJSUzI1NiJ9.e30"])
def test_malformed_tokens_are_rejected(token):
    rejected(token, "malformed")


def test_bad_payload_with_valid_header_is_malformed():
    header = signed().split(".")[0]
    rejected(f"{header}.@@@.sig", "Token is malformed")


def test_payload_that_is_not_an_object_is_malformed():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    key = tokens.keypair()[0]
    token = _hand_made({"alg": "RS256", "kid": KID}, [1, 2],
                       sign_with=lambda data: key.sign(data, padding.PKCS1v15(), hashes.SHA256()))
    rejected(token, "Token is malformed")


# -- emulator mode -------------------------------------------------------------------

def test_emulator_mode_accepts_unsigned_token():
    assert verify(unsigned(claims("emu-user", now=NOW)), emulator=True) == "emu-user"


def test_emulator_mode_does_not_fetch_signing_keys(signing_certs):
    verify(unsigned(claims(now=NOW)), emulator=True)
    assert signing_certs["fetches"] == 0


@pytest.mark.parametrize("overrides, match", [
    ({"aud": "other"}, "audience"),
    ({"iss": "https://securetoken.google.com/other"}, "issuer"),
    ({"exp": NOW - 3600}, "expired"),
    ({"sub": ""}, "subject"),
    ({"sub": ...}, "subject"),
])
def test_emulator_mode_still_checks_claims(overrides, match):
    rejected(unsigned(claims(now=NOW, **overrides)), match, emulator=True)


def test_emulator_mode_rejects_malformed_token():
    rejected("x.y.z", "malformed", emulator=True)


def test_emulator_mode_from_environment(monkeypatch):
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "")
    assert auth.emulator_mode() is False and auth.auth_mode() == "firebase"
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "   ")
    assert auth.emulator_mode() is False
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", " 127.0.0.1:9099 ")
    assert auth.emulator_mode() is True and auth.auth_mode() == "firebase-emulator"
    assert auth.emulator_host() == "127.0.0.1:9099"
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST")
    assert auth.emulator_mode() is False


def test_project_id_from_environment(monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", " agentweave-e9cd8 ")
    assert auth.project_id() == "agentweave-e9cd8"
    monkeypatch.delenv("FIREBASE_PROJECT_ID")
    assert auth.project_id() == ""


# -- cert cache ----------------------------------------------------------------------

class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def counting_fetch(max_age=600):
    calls = []

    def fetch():
        calls.append(1)
        return {KID: tokens.keypair()[1]}, max_age
    return fetch, calls


def test_cert_cache_honours_max_age():
    fetch, calls = counting_fetch(600)
    clock = Clock()
    cache = auth.CertCache(fetch=fetch, clock=clock)
    first = cache.keys()
    assert set(first) == {KID} and len(calls) == 1
    clock.t += 599
    assert cache.keys() is first and len(calls) == 1
    clock.t += 1  # exactly max-age later the response is stale
    cache.keys()
    assert len(calls) == 2


def test_cert_cache_without_max_age_refetches_every_time():
    fetch, calls = counting_fetch(0)
    cache = auth.CertCache(fetch=fetch, clock=Clock())
    cache.keys()
    cache.keys()
    assert len(calls) == 2


def test_cert_cache_parses_pem_into_public_keys():
    fetch, _ = counting_fetch()
    key = auth.CertCache(fetch=fetch, clock=Clock()).keys()[KID]
    assert key.public_numbers() == tokens.keypair()[0].public_key().public_numbers()


def test_cert_cache_fetch_failure_raises_config_error(caplog):
    def broken():
        raise httpx.ConnectError("offline")

    cache = auth.CertCache(fetch=broken, clock=Clock())
    with caplog.at_level(logging.ERROR, logger="auth"), pytest.raises(auth.AuthConfigError):
        cache.keys()
    assert caplog.messages == ["Fetching Firebase signing certificates failed"]


def test_cert_cache_retries_after_a_failed_fetch():
    results = [httpx.ConnectError("offline"), ({KID: tokens.keypair()[1]}, 60)]

    def flaky():
        r = results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    cache = auth.CertCache(fetch=flaky, clock=Clock())
    with pytest.raises(auth.AuthConfigError):
        cache.keys()
    assert set(cache.keys()) == {KID}


def test_cert_cache_rejects_invalid_pem():
    cache = auth.CertCache(fetch=lambda: ({KID: "not a cert"}, 60), clock=Clock())
    with pytest.raises(auth.AuthConfigError):
        cache.keys()


def test_verify_uses_module_cert_cache(signing_certs):
    verify(signed())
    verify(signed())
    assert signing_certs["fetches"] == 1


def test_verify_refetches_after_max_age(signing_certs, monkeypatch):
    clock = Clock(NOW)
    signing_certs["max_age"] = 100
    monkeypatch.setattr(auth._cert_cache, "_clock", clock)
    verify(signed())
    clock.t += 100
    verify(signed())
    assert signing_certs["fetches"] == 2


def test_cert_cache_defaults():
    cache = auth.CertCache()
    assert cache._fetch is auth.fetch_certs
    assert cache._clock is time.time
    assert cache._expires_at == 0.0 and cache._keys == {}


@pytest.mark.parametrize("header, seconds", [
    ("public, max-age=19302, must-revalidate, no-transform", 19302),
    ("max-age=0", 0),
    ("no-cache", 0),
    ("", 0),
])
def test_max_age_seconds(header, seconds):
    assert auth.max_age_seconds(header) == seconds


def test_fetch_certs_reads_google_endpoint(monkeypatch):
    seen = {}

    def fake_get(url, timeout):
        seen.update(url=url, timeout=timeout)
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"k1": "PEM"}, request=request,
                              headers={"Cache-Control": "public, max-age=21600"})

    monkeypatch.setattr(auth, "httpx", SimpleNamespace(get=fake_get))
    assert auth.fetch_certs() == ({"k1": "PEM"}, 21600)
    assert seen == {"url": "https://www.googleapis.com/robot/v1/metadata/x509/"
                           "securetoken@system.gserviceaccount.com", "timeout": 10.0}


def test_fetch_certs_raises_on_http_error(monkeypatch):
    def fake_get(url, timeout):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(auth, "httpx", SimpleNamespace(get=fake_get))
    with pytest.raises(httpx.HTTPStatusError):
        auth.fetch_certs()


def test_fetch_certs_without_cache_control(monkeypatch):
    monkeypatch.setattr(auth, "httpx", SimpleNamespace(
        get=lambda url, timeout: httpx.Response(200, json={}, request=httpx.Request("GET", url))))
    assert auth.fetch_certs() == ({}, 0)


# -- current_uid dependency -----------------------------------------------------------

def creds(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_current_uid_returns_verified_uid():
    assert auth.current_uid(creds(tokens.token("dep-user", project=PROJECT_ID))) == "dep-user"


def test_current_uid_without_credentials_is_401():
    with pytest.raises(HTTPException) as err:
        auth.current_uid(None)
    assert err.value.status_code == 401
    assert err.value.headers == {"WWW-Authenticate": "Bearer"}
    assert err.value.detail == ("Sign-in required: send a Firebase ID token as "
                                "'Authorization: Bearer <token>'.")


def test_current_uid_with_invalid_token_is_401_with_reason():
    with pytest.raises(HTTPException) as err:
        auth.current_uid(creds(tokens.token(aud="other")))
    assert err.value.status_code == 401
    assert err.value.detail == "Invalid ID token: Token has the wrong audience (aud)."
    assert err.value.headers == {"WWW-Authenticate": "Bearer"}


def test_current_uid_without_project_id_is_503(monkeypatch, caplog):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "")
    with caplog.at_level(logging.ERROR, logger="auth"), pytest.raises(HTTPException) as err:
        auth.current_uid(creds(tokens.token()))
    assert err.value.status_code == 503
    assert err.value.detail == "Authentication is not configured on the server."
    assert caplog.messages == ["FIREBASE_PROJECT_ID is not set: authenticated endpoints are unavailable"]


def test_current_uid_when_keys_cannot_be_fetched_is_503(monkeypatch):
    def broken():
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(auth, "_cert_cache", auth.CertCache(fetch=broken))
    with pytest.raises(HTTPException) as err:
        auth.current_uid(creds(tokens.token()))
    assert err.value.status_code == 503
    assert err.value.detail == "Could not fetch Firebase signing keys."


def test_current_uid_rejects_unsigned_token_unless_emulator(monkeypatch):
    token = unsigned(claims("emu"))
    with pytest.raises(HTTPException) as err:
        auth.current_uid(creds(token))
    assert err.value.status_code == 401
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    assert auth.current_uid(creds(token)) == "emu"


# -- startup logging -----------------------------------------------------------------

def test_startup_warns_loudly_in_emulator_mode(monkeypatch, caplog):
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    with caplog.at_level(logging.WARNING, logger="auth"):
        auth.log_startup_config()
    assert caplog.messages == ["FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099: Firebase Auth EMULATOR MODE "
                               "is ON. Unsigned ID tokens are accepted. Never set this in production."]
    assert "FIREBASE_PROJECT_ID is not set" not in caplog.text


def test_startup_is_quiet_in_normal_mode(caplog):
    with caplog.at_level(logging.WARNING, logger="auth"):
        auth.log_startup_config()
    assert caplog.text == ""


def test_startup_warns_without_project_id(monkeypatch, caplog):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "")
    with caplog.at_level(logging.WARNING, logger="auth"):
        auth.log_startup_config()
    assert caplog.messages == ["FIREBASE_PROJECT_ID is not set: /closet endpoints will return 503"]

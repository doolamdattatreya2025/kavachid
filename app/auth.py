"""
Signed, short-lived attribute tokens.

Instead of handing a relying party (a bank, an app, a landlord) your
raw date of birth, KavachID hands them a signed claim like
`is_adult: true`. The relying party verifies the signature and trusts
the claim without ever seeing the underlying document.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

_JWT_SECRET = os.environ.get("KAVACHID_JWT_SECRET", secrets.token_hex(32))
_ALGORITHM = "HS256"
_DEFAULT_TTL_SECONDS = 120  # short-lived on purpose


def issue_attribute_token(claims: dict, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **claims,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "iss": "kavachid-demo",
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)


def verify_attribute_token(token: str) -> dict:
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise ValueError(f"Invalid or expired token: {exc}") from exc

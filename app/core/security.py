# app/core/security.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import hashlib
from uuid import uuid4

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _pepper_password(password: str) -> str:
    """
    Apply a global pepper (if configured) to the password.

    This MUST be used in both hashing and verification so they match.
    """
    # If PASSWORD_PEPPER is missing or empty, this is effectively a no-op.
    pepper = getattr(settings, "PASSWORD_PEPPER", "") or ""
    return password + pepper


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches hashed_password."""
    try:
        return _pwd_context.verify(_pepper_password(plain_password), hashed_password)
    except Exception:
        # If the stored hash is invalid/corrupt, treat as non-match
        return False


def get_password_hash(password: str) -> str:
    """Hash a password for storing in the database."""
    return _pwd_context.hash(_pepper_password(password))


# Backwards-compatible alias used by existing repositories
def hash_password(password: str) -> str:
    return get_password_hash(password)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access",
) -> str:
    """
    Create a signed JWT with standard claims.

    - data: payload claims (will be copied)
    - expires_delta: expiry window; if omitted, use ACCESS_TOKEN_EXPIRE_MINUTES
    - token_type: "access" or "refresh" (stored in the "type" claim)
    """
    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expires_delta

    to_encode.update(
        {
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": token_type,
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "type": "access",
        "jti": str(uuid4())
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")



def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid4())
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str, verify_exp: bool = True) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT and optionally verify exp.

    Returns the payload dict on success, or None on failure.
    """
    options = {"verify_exp": verify_exp}
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options=options,
        )
        return payload
    except JWTError:
        return None


def datetime_from_timestamp(ts: Union[int, float]) -> datetime:
    """Convert a UNIX timestamp (seconds) to timezone-aware datetime."""
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


# ---------------------------------------------------------------------------
# Authorization header helpers
# ---------------------------------------------------------------------------

def get_bearer_token(request: Request) -> str:
    """
    Extract Bearer token from Authorization header.

    This is synchronous; do *not* "await" it.
    """
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    return parts[1]


# ---------------------------------------------------------------------------
# Token hashing helpers (for blacklist, API keys, etc.)
# ---------------------------------------------------------------------------

def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_access_token(token: str) -> str:
    return _sha256_hex(token)


def hash_refresh_token(token: str) -> str:
    """Alias used by other modules (e.g. invitations / refresh-token storage)."""
    return _sha256_hex(token)


def datetime_from_timestamp(ts: int):
    return datetime.fromtimestamp(ts, tz=timezone.utc)
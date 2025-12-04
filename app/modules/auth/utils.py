# app/modules/auth/utils.py

"""
General helper functions for the Auth module.
Includes:
- Extracting bearer token from Authorization header
- Normalizing email
"""

from fastapi import HTTPException, status, Request
from typing import Optional

from pydantic import str


def extract_bearer_token(request: Request) -> str:
    """
    Extracts "Bearer <token>" from the Authorization header.
    Raises 401 if missing or invalid.
    """
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authorization header missing"
        )

    try:
        scheme, token = auth.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid Authorization header"
        )

    return token


def normalize_email(email: str) -> str:
    """
    Lowercase + trimmed email normalization.
    """
    return email.strip().lower()

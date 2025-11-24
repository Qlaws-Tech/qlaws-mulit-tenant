from fastapi import Request
from typing import Optional
from jose import jwt, JWTError
from app.core.config import settings


def get_current_user_id(request: Request) -> Optional[str]:
    """
    Extracts the 'sub' (User ID) from the Bearer token in the Authorization header.
    Returns None if token is missing or invalid (does not raise HTTP exception).
    Used primarily for Audit Logging where we want to know 'who' did it,
    but the request might already be authenticated by RLS dependencies.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    try:
        # Expect "Bearer <token>"
        token = auth_header.split(" ")[1]

        # Decode without verification (Verification happens in RLS dependency)
        # We just need the ID for logging purposes here.
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except (JWTError, IndexError):
        return None
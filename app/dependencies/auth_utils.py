# app/dependencies/auth_utils.py

"""
Utilities for extracting user identity and tenant context from JWT.
Used by:
- database dependencies (to get tenant_id)
- routers (to get current user_id)
- permissions (via get_current_user / get_current_user_id)
"""

from typing import Any, Dict

from fastapi import Request, HTTPException, status

from app.core.security import get_bearer_token, decode_token


def _decode_request_token(request: Request, verify_exp: bool = True) -> Dict[str, Any]:
    """
    Internal helper:
    - read Bearer token from Authorization header
    - decode JWT
    - raise 401 if anything is wrong
    """
    token = get_bearer_token(request)
    payload = decode_token(token, verify_exp=verify_exp)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Normalize tenant id so callers can reliably use payload["tenant_id"]
    tid = payload.get("tid") or payload.get("tenant_id")
    if tid:
        payload["tenant_id"] = tid

    return payload


def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency to extract the user_id (sub) from the JWT.

    Example:
        def some_route(user_id: str = Depends(get_current_user_id)):
            ...
    """
    payload = _decode_request_token(request, verify_exp=True)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID missing from token",
        )

    return user_id


def get_current_token_payload(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to get the *full* decoded JWT payload.

    - Does NOT require a 'jti' claim.
    - Ensures payload["tenant_id"] is set if 'tid' or 'tenant_id' exists.
    """
    return _decode_request_token(request, verify_exp=True)


def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Backwards-compatible helper used by some older code.

    Returns a small dict with:
      - user_id
      - tenant_id (if present)
      - payload (the full decoded JWT)
    """
    payload = _decode_request_token(request, verify_exp=True)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID missing from token",
        )

    return {
        "user_id": user_id,
        "tenant_id": payload.get("tenant_id"),
        "payload": payload,
    }

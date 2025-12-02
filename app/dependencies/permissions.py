# app/dependencies/permissions.py

from __future__ import annotations

from typing import Iterable, Set, List
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from app.core.security import get_bearer_token, decode_token
from app.dependencies.database import get_tenant_db_connection
from app.modules.users.repository import UserRepository


def _normalize_permissions(perms: Iterable[str] | None) -> Set[str]:
    """
    Normalize permissions into a set of strings.
    """
    if not perms:
        return set()
    return {str(p) for p in perms}


async def _get_effective_permissions(
    request: Request,
    conn=Depends(get_tenant_db_connection),
) -> Set[str]:
    """
    Extract effective permissions from the JWT.
    If they are not present in the token, fall back to loading from DB.
    """
    token = get_bearer_token(request)
    payload = decode_token(token)

    # 1) Prefer permissions embedded in the token
    perms = payload.get("permissions")
    if perms is not None:
        return _normalize_permissions(perms)

    # 2) Fallback: load from DB via UserRepository
    user_id_str = payload.get("sub")
    tenant_id = getattr(request.state, "tenant_id", None)

    if not user_id_str or not tenant_id:
        # No way to resolve permissions, treat as no permissions
        return set()

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        return set()

    repo = UserRepository(conn)
    ctx = await repo.get_user_context(user_id, tenant_id)
    return _normalize_permissions(getattr(ctx, "permissions", []))


def require_permission(required_perm: str):
    """
    Dependency factory enforcing a *single* permission.

    Usage:
        @router.get("/something", dependencies=[Depends(require_permission("user.read"))])
        async def handler(...):
            ...
    """

    async def permission_checker(
        request: Request,
        conn=Depends(get_tenant_db_connection),
    ) -> bool:
        effective_permissions = await _get_effective_permissions(request, conn)

        # Wildcards:
        #   "*"           => full access
        #   "tenant.*"    => any tenant-scoped permission
        if "*" in effective_permissions:
            return True

        # Direct match
        if required_perm in effective_permissions:
            return True

        # Prefix wildcard: "tenant.manage" is satisfied by "tenant.*"
        if "." in required_perm:
            prefix = required_perm.split(".", 1)[0] + ".*"
            if prefix in effective_permissions:
                return True

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {required_perm}",
        )

    return permission_checker


def require_permissions(required: List[str]):
    """
    Backward-compatible factory enforcing a *set* of permissions.
    Any endpoint that previously did something like:

        dependencies=[Depends(require_permissions(["user.read", "user.update"]))]

    will work with this version.

    It does NOT take a 'user' object anymore; it reads from the JWT / DB.
    """

    async def checker(
        request: Request,
        conn=Depends(get_tenant_db_connection),
    ) -> bool:
        effective_permissions = await _get_effective_permissions(request, conn)

        missing = [p for p in required if p not in effective_permissions]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing)}",
            )

        return True

    return checker

from fastapi import Depends, HTTPException, status, Request
from jose import jwt
from app.core.config import settings
from app.dependencies.database import get_db_connection
from app.modules.users.repository import UserRepository


def require_permission(required_perm: str):
    """
    Factory to create a dependency that checks for a specific permission key.
    """

    async def permission_checker(
            request: Request,
            conn=Depends(get_db_connection)  # Raw connection
    ):
        # 1. Extract User/Tenant from Token
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing Authorization Header")

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            tenant_id = payload.get("tid")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid Token")

        # 2. CRITICAL FIX: Set RLS Context
        try:
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)",
                str(tenant_id)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Permission Check Failed: {str(e)}")

        # 3. Fetch Effective Permissions
        repo = UserRepository(conn)
        context = await repo.get_user_context(user_id, tenant_id)

        if not context:
            raise HTTPException(status_code=403, detail="User context not found")

        # 4. Check Permission
        roles = context.get("roles", [])
        effective_permissions = set(context.get("permissions", []))

        # FIX: Robust Admin Bypass Logic
        # 1. Check for "Admin" role (Case-Insensitive)
        is_admin_role = any(r.lower() == "admin" for r in roles)
        # 2. Check for Wildcard Permission "*"
        has_wildcard = "*" in effective_permissions
        # 3. Check for legacy/specific admin permission
        has_manage_perm = "tenant.manage" in effective_permissions

        if is_admin_role or has_wildcard or has_manage_perm:
            return True  # Admin bypass success

        # Standard Check
        if required_perm not in effective_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {required_perm}"
            )

        return True

    return permission_checker
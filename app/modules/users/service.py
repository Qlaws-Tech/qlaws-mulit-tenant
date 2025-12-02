# app/modules/users/service.py

from uuid import UUID
from typing import List

from fastapi import HTTPException, status

from app.modules.users.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    CurrentUserResponse,
)
from app.modules.users.repository import UserRepository
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate
from app.core.security import get_password_hash


class UserService:
    def __init__(self, conn):
        self.conn = conn
        self.user_repo = UserRepository(conn)
        self.audit_repo = AuditRepository(conn)

    # ---------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------
    async def list_users(self) -> List[UserResponse]:
        # Fetch current tenant from RLS context variable set by middleware/dependency
        tenant_id = await self.conn.fetchval(
            "SELECT current_setting('app.current_tenant_id', true)::uuid"
        )
        if not tenant_id:
            # Fallback or error if no context
            return []

        rows = await self.user_repo.list_users_for_tenant(tenant_id)

        results = []
        for r in rows:
            d = dict(r)
            # Ensure 'roles' is a list. The repo might return 'tenant_role' string.
            if "roles" not in d:
                # Pop tenant_role to clean up dict and use it for roles list
                role = d.pop("tenant_role", None)
                d["roles"] = [role] if role else []

            results.append(UserResponse(**d))

        return results

    async def get_user(self, user_id: UUID) -> UserResponse:
        # Use get_user_context to ensure we get tenant-scoped info (roles, etc.)
        tenant_id = await self.conn.fetchval(
            "SELECT current_setting('app.current_tenant_id', true)::uuid"
        )
        if not tenant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tenant context missing")

        # Reuse get_user_context which returns a Pydantic model compatible with UserResponse
        ctx = await self.user_repo.get_user_context(user_id, tenant_id)
        if not ctx:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        # Convert UserContext to UserResponse
        return UserResponse(
            user_id=ctx.user_id,
            tenant_id=ctx.tenant_id,
            email=ctx.email,
            display_name=ctx.display_name,
            roles=ctx.roles,
            permissions=ctx.permissions
        )

    async def create_user(self, payload: UserCreate) -> UserResponse:
        # 1. Get current tenant
        tenant_id_str = await self.conn.fetchval(
            "SELECT current_setting('app.current_tenant_id', true)"
        )
        if not tenant_id_str:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tenant context missing")

        # 2. Prepare payload for repo (expects dict with hashed password)
        hashed = get_password_hash(payload.password)
        repo_payload = {
            "email": payload.email,
            "display_name": payload.display_name,
            "hashed_password": hashed,
            "tenant_id": tenant_id_str,
            "tenant_role": "member",  # Default role
            "status": "active"
        }

        # 3. Create (returns dict)
        result = await self.user_repo.create_user(repo_payload)
        user_data = result["user"]
        mem_data = result["membership"]

        user_id = user_data["user_id"]
        email = user_data["primary_email"]

        # 4. Audit
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="user.create",
                resource_type="user",
                resource_id=str(user_id),
                details={"email": email},
            )
        )

        # 5. Return Pydantic model
        return UserResponse(
            user_id=user_id,
            tenant_id=mem_data["tenant_id"],
            email=email,
            display_name=user_data["display_name"],
            created_at=user_data["created_at"],
            roles=[mem_data["tenant_role"]],
            permissions=[]
        )

    async def update_user(self, user_id: UUID, payload: UserUpdate) -> UserResponse:
        # Ensure user exists in this tenant
        existing = await self.get_user(user_id)

        # Update profile (repo returns dict or None)
        updated_data = await self.user_repo.update_user_profile(
            user_id,
            display_name=payload.display_name
        )
        if not updated_data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found or update failed")

        # Audit
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="user.update",
                resource_type="user",
                resource_id=str(user_id),
                details=payload.dict(exclude_unset=True),
            )
        )

        # Return updated state
        # We need to re-fetch to get full context or patch the existing object
        # Simplest is to call get_user again to ensure roles/permissions are included
        return await self.get_user(user_id)

    async def deactivate_user(self, user_id: UUID, tenant_id: UUID):
        await self.user_repo.deactivate_user_in_tenant(user_id, tenant_id)
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="user.deactivate",
                resource_type="user",
                resource_id=str(user_id),
                details={"tenant_id": str(tenant_id)},
            )
        )

    # ---------------------------------------------------------
    # CURRENT USER CONTEXT
    # ---------------------------------------------------------
    async def get_current_user_profile(self, user_id: UUID, tenant_id: UUID) -> CurrentUserResponse:
        ctx = await self.user_repo.get_user_context(user_id, tenant_id)
        if not ctx:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User context not found")

        redirect_url = self._compute_redirect_url(ctx.permissions)

        return CurrentUserResponse(
            **ctx.dict(),
            redirect_url=redirect_url,
        )

    def _compute_redirect_url(self, permissions: list[str]) -> str:
        """
        Simple redirect logic based on permissions.
        """
        if "tenant.manage" in permissions:
            return "/admin/overview"
        if "user.read" in permissions:
            return "/users"
        return "/dashboard"
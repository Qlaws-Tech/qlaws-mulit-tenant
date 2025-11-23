from uuid import UUID
from typing import List, Optional
from fastapi import HTTPException, status, BackgroundTasks
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserResponse, UserUpdate, UserContextResponse
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate
from app.core.cache import cache
from app.core.email import send_email


class UserService:
    def __init__(self, repo: UserRepository, audit_repo: AuditRepository):
        self.repo = repo
        self.audit_repo = audit_repo

    async def on_board_user(self, user_data: UserCreate, background_tasks: BackgroundTasks = None,
                            current_user_id: str = None, ip_address: str = None) -> UserResponse:
        """
        Creates a new user, logs the action, and triggers a welcome email asynchronously.
        """
        user_data.email = user_data.email.lower()
        new_user = await self.repo.create_user(user_data)

        # --- Background Task: Send Email ---
        if background_tasks:
            subject = "Welcome to QLaws"
            body = f"Hello {new_user.display_name}, your account has been created successfully."
            background_tasks.add_task(send_email, subject, new_user.email, body)

        # --- Audit Log ---
        # FIX: Included ip_address in the log payload
        await self.audit_repo.log_event(AuditLogCreate(
            action_type="user.create",
            actor_user_id=UUID(current_user_id) if current_user_id else None,
            resource_type="user",
            resource_id=str(new_user.user_id),
            details={"email": new_user.email, "role": new_user.tenant_role},
            ip_address=ip_address
        ))

        return new_user

    async def get_tenant_users(self) -> List[UserResponse]:
        return await self.repo.get_users_by_tenant()

    async def get_by_id(self, user_id: UUID) -> UserResponse:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    async def update_user(self, user_id: UUID, data: UserUpdate, current_user_id: str = None,
                          ip_address: str = None) -> UserResponse:
        updated_user = await self.repo.update_user_status(
            user_id,
            status=data.status,
            role=data.role
        )

        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")

        # FIX: Included ip_address and actor_user_id
        await self.audit_repo.log_event(AuditLogCreate(
            action_type="user.update",
            actor_user_id=UUID(current_user_id) if current_user_id else None,
            resource_type="user",
            resource_id=str(user_id),
            details=data.model_dump(exclude_unset=True),
            ip_address=ip_address
        ))

        return updated_user

    async def remove_user(self, user_id: UUID, current_user_id: str = None, ip_address: str = None):
        success = await self.repo.delete_user_from_tenant(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        # FIX: Included ip_address and actor_user_id
        await self.audit_repo.log_event(AuditLogCreate(
            action_type="user.delete",
            actor_user_id=UUID(current_user_id) if current_user_id else None,
            resource_type="user",
            resource_id=str(user_id),
            ip_address=ip_address
        ))

    async def get_me(self, user_id: str, tenant_id: str) -> UserContextResponse:
        # ... (Logic for get_me remains unchanged) ...
        cache_key = f"user_context:{tenant_id}:{user_id}"
        cached_data = await cache.get(cache_key)

        if cached_data:
            return UserContextResponse(**cached_data)

        raw_context = await self.repo.get_user_context(user_id, tenant_id)

        if not raw_context:
            raise HTTPException(404, "User context not found")

        permissions = set(raw_context.get("permissions", []))
        roles = set(raw_context.get("roles", []))

        redirect_url = "/dashboard"

        if "tenant.manage" in permissions or "Admin" in roles:
            redirect_url = "/admin/overview"
        elif "litigation.view" in permissions:
            redirect_url = "/cases"
        elif not permissions and not roles:
            redirect_url = "/onboarding/welcome"

        response = UserContextResponse(
            user_id=raw_context['user_id'],
            email=raw_context['primary_email'],
            display_name=raw_context['display_name'],
            tenant_id=raw_context['tenant_id'],
            tenant_name=raw_context['tenant_name'],
            roles=list(roles),
            permissions=list(permissions),
            redirect_url=redirect_url
        )

        await cache.set(cache_key, response.model_dump(mode='json'), expire=60)

        return response
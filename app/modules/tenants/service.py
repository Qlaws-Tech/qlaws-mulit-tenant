# app/modules/tenants/service.py

from fastapi import HTTPException, status

from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import (
    TenantCreate,
    TenantOnboardingResponse,
    TenantResponse,
)
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreate
from app.modules.users.repository import UserRepository
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate
from app.core.security import get_password_hash


class TenantService:
    """
    Handles tenant onboarding and management.
    """

    def __init__(
            self,
            tenant_repo: TenantRepository,
            user_repo: UserRepository,
            role_repo: RoleRepository,
    ):
        self.tenant_repo = tenant_repo
        self.user_repo = user_repo
        self.role_repo = role_repo

        # Underlying asyncpg connection (tests set mock_tenant_repo.conn)
        self.conn = tenant_repo.conn
        self.audit_repo = AuditRepository(self.conn)

    # ------------------------------------------------------------------
    # Onboard Tenant
    # ------------------------------------------------------------------
    async def onboard_tenant(self, payload: TenantCreate) -> TenantOnboardingResponse:
        """
        Orchestrates the creation of a Tenant + Admin User + Admin Role.
        Executed in a single transaction.
        """
        # 1. Check domain availability (fast check before transaction)
        if payload.domain:
            existing = await self.tenant_repo.get_by_domain(payload.domain)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Domain already taken",
                )

        # 2. Transactional creation
        async with self.conn.transaction():
            # 2.1 Create Tenant
            tenant = await self.tenant_repo.create(payload)

            # 2.2 Create Admin User
            # UserRepository.create_user expects a dict and returns a dict:
            # { "user": { "user_id": ... }, "membership": { ... } }
            # It also expects an already hashed password.
            hashed_pw = get_password_hash(payload.admin_password)

            admin_user_data = await self.user_repo.create_user({
                "email": payload.admin_email,
                "display_name": payload.admin_name,
                "hashed_password": hashed_pw,
                "tenant_id": str(tenant.tenant_id),
                "tenant_role": "Firm Admin",
                "status": "active"
            })

            # FIX: Extract ID/Email from dictionary (admin_user_data is NOT an object)
            user_id = admin_user_data["user"]["user_id"]
            user_email = admin_user_data["user"]["primary_email"]
            user_tenant_id = admin_user_data["membership"]["user_tenant_id"]

            # 2.3 Set RLS context for Role creation
            # RoleRepository depends on current_setting('app.current_tenant_id')
            await self.conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)",
                str(tenant.tenant_id)
            )

            # 2.4 Create "Admin" Role
            admin_role = await self.role_repo.create_role(
                RoleCreate(
                    name="Admin",
                    description="Super Administrator",
                    permission_keys=["*"]  # Assign all permissions
                )
            )

            # 2.5 Assign Role to User
            await self.conn.execute(
                """
                INSERT INTO user_roles (user_tenant_id, role_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                user_tenant_id,
                admin_role.role_id
            )

            # 2.6 Audit log
            await self.audit_repo.log_event(
                AuditLogCreate(
                    action_type="tenant.onboard",
                    resource_type="tenant",
                    resource_id=str(tenant.tenant_id),
                    details={
                        "tenant_name": tenant.name,
                        "admin_email": payload.admin_email,
                        "admin_user_id": str(user_id),
                        "admin_role_id": str(admin_role.role_id),
                    },
                ),
                actor_user_id=user_id,
            )

        # 3. Return onboarding response
        return TenantOnboardingResponse(
            tenant_id=tenant.tenant_id,
            admin_email=user_email,
        )

    # ------------------------------------------------------------------
    # Other helpers
    # ------------------------------------------------------------------
    async def list_tenants(self) -> list[TenantResponse]:
        return await self.tenant_repo.list_tenants()

    async def get_tenant(self, tenant_id) -> TenantResponse:
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
        return tenant
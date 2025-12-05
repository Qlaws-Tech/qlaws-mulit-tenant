from fastapi import HTTPException, status

from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import (
    TenantCreate,
    TenantOnboardingResponse,
    TenantResponse,
)
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreate, RoleResponse
from app.modules.users.repository import UserRepository
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate
from app.modules.groups.repository import GroupRepository
from app.modules.groups.schemas import GroupCreate
from app.core.security import get_password_hash


class TenantService:
    """
    Handles tenant onboarding and management.

    Enhancements:
    - Provision tenant environment on signup (default group, membership).
    - Configure default RBAC roles: Admin, Drafter, Reviewer, Commenter.
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
        self.group_repo = GroupRepository(self.conn)

    # ------------------------------------------------------------------
    # Onboard Tenant
    # ------------------------------------------------------------------
    async def onboard_tenant(self, payload: TenantCreate) -> TenantOnboardingResponse:
        """
        Orchestrates the creation of a Tenant + Admin User + default RBAC roles
        + initial tenant environment (groups, etc.).

        All operations run in a single transaction so that a failure rolls
        back everything.
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

            admin_user_data = await self.user_repo.create_user(
                {
                    "email": payload.admin_email,
                    "display_name": payload.admin_name,
                    "hashed_password": hashed_pw,
                    "tenant_id": str(tenant.tenant_id),
                    # This is the human-readable tenant role label
                    "tenant_role": "Firm Admin",
                    "status": "active",
                }
            )

            # Extract IDs/emails from dictionary (admin_user_data is NOT an object)
            user_id = admin_user_data["user"]["user_id"]
            user_email = admin_user_data["user"]["primary_email"]
            user_tenant_id = admin_user_data["membership"]["user_tenant_id"]

            # 2.3 Set RLS context for tenant-scoped resources
            # RoleRepository, GroupRepository, AuditRepository, etc.
            # all depend on current_setting('app.current_tenant_id').
            await self.conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)",
                str(tenant.tenant_id),
            )

            # 2.4 Create default RBAC roles for this tenant
            # Admin, Drafter, Reviewer, Commenter
            rbac_roles = await self._create_default_rbac_roles()
            admin_role: RoleResponse = rbac_roles["Admin"]

            # 2.5 Assign "Admin" RBAC role to the onboarding admin user
            await self.conn.execute(
                """
                INSERT INTO user_roles (user_tenant_id, role_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                user_tenant_id,
                admin_role.role_id,
            )

            # 2.6 Provision tenant environment (default groups, etc.)
            await self._provision_tenant_environment(
                tenant=tenant,
                admin_user_id=user_id,
            )

            # 2.7 Audit overall onboarding
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
    # Default RBAC roles
    # ------------------------------------------------------------------
    async def _create_default_rbac_roles(self) -> dict[str, RoleResponse]:
        """
        Configure default RBAC roles for a new tenant.

        Roles:
        - Admin: full access (all permissions, "*")
        - Drafter: can create & edit drafts, and comment
        - Reviewer: can review and comment
        - Commenter: can only comment

        NOTE:
        - RoleRepository.create_role() will auto-create any missing permission
          keys in the `permissions` table.
        - These permission keys can be used by require_permissions(...) guards
          in routers.
        """
        role_definitions: list[tuple[str, str, list[str]]] = [
            (
                "Admin",
                "Super Administrator with full access",
                ["*"],
            ),
            (
                "Drafter",
                "Can create and edit drafts, and comment on documents",
                [
                    "doc.create",
                    "doc.edit",
                    "doc.comment",
                ],
            ),
            (
                "Reviewer",
                "Can review drafts and comment on documents",
                [
                    "doc.review",
                    "doc.comment",
                ],
            ),
            (
                "Commenter",
                "Can only comment on documents",
                [
                    "doc.comment",
                ],
            ),
        ]

        roles: dict[str, RoleResponse] = {}
        for name, description, perm_keys in role_definitions:
            role = await self.role_repo.create_role(
                RoleCreate(
                    name=name,
                    description=description,
                    permission_keys=perm_keys,
                )
            )
            roles[name] = role

        return roles

    # ------------------------------------------------------------------
    # Tenant environment provisioning
    # ------------------------------------------------------------------
    async def _provision_tenant_environment(
        self,
        tenant: TenantResponse,
        admin_user_id,
    ) -> None:
        """
        Provision initial tenant environment on signup.

        Assumes:
        - Connection is inside the onboarding transaction.
        - app.current_tenant_id is already set for this connection.
        """
        from uuid import UUID

        # 1) Create a default "Everyone" group for the tenant
        everyone_group = await self.group_repo.create(
            GroupCreate(
                name="Everyone",
                description="Default group that can contain all members of the tenant.",
            )
        )

        # 2) Add the admin user to the default group
        await self.group_repo.add_member(
            group_id=everyone_group.group_id,
            user_id=UUID(str(admin_user_id)),
            tenant_id=tenant.tenant_id,
        )

        # 3) Audit environment provisioning step
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="tenant.provision_environment",
                resource_type="tenant",
                resource_id=str(tenant.tenant_id),
                details={
                    "default_group_id": str(everyone_group.group_id),
                    "default_group_name": everyone_group.name,
                },
            ),
            actor_user_id=admin_user_id,
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

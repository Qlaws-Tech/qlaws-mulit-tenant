from fastapi import HTTPException
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate, TenantOnboardingResponse
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreate


class TenantService:
    def __init__(self, repo: TenantRepository, user_repo: UserRepository, role_repo: RoleRepository):
        self.repo = repo
        self.user_repo = user_repo
        self.role_repo = role_repo

    async def onboard_tenant(self, data: TenantCreate) -> TenantOnboardingResponse:
        # 1. Check Domain Uniqueness
        if data.domain:
            existing = await self.repo.get_by_domain(data.domain)
            if existing:
                raise HTTPException(status_code=409, detail="Domain already taken")

        # 2. Atomic Onboarding Transaction
        # We wrap the creation of Tenant, Role, and User in a single transaction.
        # This ensures that if any step fails, the database remains clean.
        async with self.repo.conn.transaction():

            # A. Create Tenant
            # This method internally runs "SET app.current_tenant_id = ..." to satisfy RLS
            tenant = await self.repo.create(data)

            # B. Create Admin Role (Bootstrap)
            # The RLS context from step A is still active here
            admin_role = await self.role_repo.create_role(RoleCreate(
                name="Admin",
                description="Super Administrator",
                permission_keys=["*"]  # Wildcard permission for Super Admin
            ))

            # C. Create Admin User
            # FIX: Explicitly pass tenant.tenant_id to the user repository.
            # This ensures the user link is created correctly even if the session variable
            # state is fragile inside complex transaction blocks.
            admin_user = await self.user_repo.create_user(
                UserCreate(
                    email=data.admin_email,
                    password=data.admin_password,
                    display_name=data.admin_name,
                    role="admin"
                ),
                tenant_id=tenant.tenant_id  # <--- Explicit Passing prevents "invalid input syntax for uuid"
            )

            # D. Assign Role to User
            # Link the newly created user to the Admin role via the user_roles table
            await self.repo.conn.execute(
                """
                INSERT INTO user_roles (user_tenant_id, role_id) 
                SELECT user_tenant_id, $2 
                FROM user_tenants WHERE user_id = $1
                """,
                admin_user.user_id, admin_role.role_id
            )

        return TenantOnboardingResponse(
            **tenant.model_dump(),
            admin_email=admin_user.email
        )
from asyncpg import Connection
from typing import Optional, List
from uuid import UUID
from app.modules.users.schemas import UserCreate, UserResponse, UserUpdate
from passlib.context import CryptContext

# Setup password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create_user(self, user: UserCreate, tenant_id: Optional[UUID] = None) -> UserResponse:
        """
        Creates a global user and links them to the current tenant.
        """
        # 1. Hash Password
        hashed_pw = pwd_context.hash(user.password)

        # 2. Insert User
        user_query = """
            INSERT INTO users (primary_email, display_name, hashed_password)
            VALUES ($1, $2, $3)
            ON CONFLICT (lower(primary_email)) 
            DO UPDATE SET updated_at = now()
            RETURNING user_id, primary_email, display_name;
        """
        user_row = await self.conn.fetchrow(
            user_query,
            user.email,
            user.display_name,
            hashed_pw
        )

        # 3. Link User to Tenant
        # CRITICAL FIX: We use COALESCE to prioritize the explicit 'tenant_id' ($4).
        # If $4 is NULL, we try the session variable.
        # We perform the cast ::uuid INSIDE SQL to avoid Python string issues.
        link_query = """
            INSERT INTO user_tenants (tenant_id, user_id, tenant_email, tenant_role, status)
            VALUES (
                COALESCE($4::uuid, current_setting('app.current_tenant_id', true)::uuid), 
                $1, $2, $3, 'active'
            )
            RETURNING created_at, status;
        """

        # Prepare explicit ID string if provided
        tid_val = str(tenant_id) if tenant_id else None

        link_row = await self.conn.fetchrow(
            link_query,
            user_row['user_id'],
            user.email,
            user.role,
            tid_val  # <--- $4 passed here
        )

        return UserResponse(
            user_id=user_row['user_id'],
            email=user_row['primary_email'],
            display_name=user_row['display_name'],
            status=link_row['status'],
            tenant_role=user.role,
            created_at=link_row['created_at']
        )

    # ... (Keep get_users_by_tenant, get_user_by_id, update_user_status, delete_user_from_tenant, get_user_context as they were) ...
    async def get_users_by_tenant(self) -> List[UserResponse]:
        query = """
            SELECT u.user_id, u.primary_email as email, u.display_name, 
                   ut.status, ut.tenant_role, ut.created_at
            FROM user_tenants ut
            JOIN users u ON ut.user_id = u.user_id
        """
        rows = await self.conn.fetch(query)
        return [UserResponse(**dict(row)) for row in rows]

    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        query = """
            SELECT u.user_id, u.primary_email as email, u.display_name, 
                   ut.status, ut.tenant_role, ut.created_at
            FROM user_tenants ut
            JOIN users u ON ut.user_id = u.user_id
            WHERE ut.user_id = $1
        """
        row = await self.conn.fetchrow(query, user_id)
        return UserResponse(**dict(row)) if row else None

    async def update_user_status(self, user_id: UUID, status: str, role: Optional[str] = None) -> Optional[
        UserResponse]:
        query = """
            UPDATE user_tenants 
            SET status = COALESCE($2, status),
                tenant_role = COALESCE($3, tenant_role),
                updated_at = now()
            WHERE user_id = $1
            RETURNING user_id
        """
        if await self.conn.fetchval(query, user_id, status, role):
            return await self.get_user_by_id(user_id)
        return None

    async def delete_user_from_tenant(self, user_id: UUID) -> bool:
        result = await self.conn.execute("DELETE FROM user_tenants WHERE user_id = $1", user_id)
        return "DELETE 0" not in result

    async def get_user_context(self, user_id: str, tenant_id: str):
        query = """
            WITH user_base AS (
                SELECT 
                    u.user_id, u.primary_email, u.display_name,
                    ut.tenant_id, t.name as tenant_name
                FROM user_tenants ut
                JOIN users u ON ut.user_id = u.user_id
                JOIN tenants t ON ut.tenant_id = t.tenant_id
                WHERE ut.user_id = $1::uuid AND ut.tenant_id = $2::uuid
            ),
            direct_roles AS (
                SELECT r.name, p.key
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.role_id
                LEFT JOIN role_permissions rp ON r.role_id = rp.role_id
                LEFT JOIN permissions p ON rp.permission_id = p.permission_id
                WHERE ur.user_tenant_id = (SELECT user_tenant_id FROM user_tenants WHERE user_id = $1::uuid AND tenant_id = $2::uuid)
            ),
            group_roles AS (
                SELECT r.name, p.key
                FROM group_members gm
                JOIN group_roles gr ON gm.group_id = gr.group_id
                JOIN roles r ON gr.role_id = r.role_id
                LEFT JOIN role_permissions rp ON r.role_id = rp.role_id
                LEFT JOIN permissions p ON rp.permission_id = p.permission_id
                WHERE gm.user_tenant_id = (SELECT user_tenant_id FROM user_tenants WHERE user_id = $1::uuid AND tenant_id = $2::uuid)
            )
            SELECT 
                ub.*,
                ARRAY(
                    SELECT DISTINCT name FROM direct_roles
                    UNION
                    SELECT DISTINCT name FROM group_roles
                ) as roles,
                ARRAY(
                    SELECT DISTINCT key FROM direct_roles WHERE key IS NOT NULL
                    UNION
                    SELECT DISTINCT key FROM group_roles WHERE key IS NOT NULL
                ) as permissions
            FROM user_base ub;
        """
        row = await self.conn.fetchrow(query, str(user_id), str(tenant_id))
        return dict(row) if row else None
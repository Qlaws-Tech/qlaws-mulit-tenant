from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import asyncpg

from app.modules.users.schemas import UserContext


class UserRepository:
    """
    Data-access layer for users and user_tenants.

    IMPORTANT:
    - DB column is `user_id` (NOT `id`) in `users`.
    - DB column is `user_tenant_id` in `user_tenants`.
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    # -------------------------------------------------------------------------
    # helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _as_dict(obj: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return obj.__dict__

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------

    async def create_user(self, payload: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
        """
        Create a new user and its user_tenants membership row.
        Returns a dictionary: {'user': {...}, 'membership': {...}}
        """
        data = self._as_dict(payload)

        email: str = data["email"]
        display_name: str = data.get("display_name") or data.get("name") or email
        hashed_password: str = data.get("hashed_password") or data.get("password_hash")
        if not hashed_password:
            raise ValueError("create_user expects 'hashed_password' or 'password_hash'")

        tenant_id_raw = data.get("tenant_id")
        if not tenant_id_raw:
            raise ValueError("create_user expects 'tenant_id' in payload")
        tenant_id = UUID(str(tenant_id_raw))

        tenant_role: str = data.get("tenant_role") or data.get("role") or "member"
        status: str = data.get("status") or "active"
        tenant_email: str = data.get("tenant_email") or email
        # NEW: persona stored per tenant membership
        persona: Optional[str] = data.get("persona") or data.get("user_persona")

        # 1) Insert into USERS
        user_row = await self.conn.fetchrow(
            """
            INSERT INTO users (
                primary_email,
                display_name,
                hashed_password
            )
            VALUES ($1, $2, $3)
            RETURNING
                user_id,
                primary_email,
                display_name,
                created_at,
                updated_at,
                password_updated_at
            """,
            email,
            display_name,
            hashed_password,
        )

        user_id: UUID = user_row["user_id"]

        # 2) Insert into USER_TENANTS
        ut_row = await self.conn.fetchrow(
            """
            INSERT INTO user_tenants (
                tenant_id,
                user_id,
                tenant_email,
                tenant_role,
                status,
                persona
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING
                user_tenant_id,
                tenant_id,
                user_id,
                tenant_email,
                tenant_role,
                status,
                persona,
                created_at,
                last_accessed_at
            """,
            tenant_id,
            user_id,
            tenant_email,
            tenant_role,
            status,
            persona,
        )

        return {
            "user": dict(user_row),
            "membership": dict(ut_row),
        }

    # -------------------------------------------------------------------------
    # AUTH / LOOKUPS
    # -------------------------------------------------------------------------

    async def get_user_by_email_for_login(
        self,
        email: str,
        tenant_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        row = await self.conn.fetchrow(
            """
            SELECT
                u.user_id,
                u.primary_email,
                u.display_name,
                u.hashed_password,
                u.is_verified,
                u.mfa_enabled,
                u.locale,
                u.timezone,
                ut.user_tenant_id,
                ut.tenant_id,
                ut.tenant_email,
                ut.tenant_role,
                ut.status AS tenant_status,
                ut.persona
            FROM users u
            JOIN user_tenants ut
              ON ut.user_id = u.user_id
            WHERE
                u.primary_email = $1
                AND ut.tenant_id = $2
                AND ut.status = 'active'
            """,
            email,
            tenant_id,
        )
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Fetches global user data. Use get_user_context for tenant-aware data.
        """
        row = await self.conn.fetchrow(
            """
            SELECT
                user_id,
                primary_email,
                display_name,
                is_verified,
                locale,
                timezone,
                mfa_enabled,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE user_id = $1
            """,
            user_id,
        )
        return dict(row) if row else None

    # -------------------------------------------------------------------------
    # USER CONTEXT (for /users/me etc.)
    # -------------------------------------------------------------------------

    async def get_user_context(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> Optional[UserContext]:
        """
        Fetch user + tenant-scoped context:
        - user basic info
        - tenant info
        - roles in that tenant
        - permissions as *keys* (strings), not UUIDs
        - persona (Partner, Paralegal, etc.) for this tenant
        """
        row = await self.conn.fetchrow(
            """
            SELECT
                u.user_id,
                u.primary_email AS email,
                COALESCE(u.display_name, u.primary_email) AS display_name,
                t.tenant_id,
                t.name AS tenant_name,
                COALESCE(
                    ARRAY_AGG(DISTINCT ut.tenant_role)
                    FILTER (WHERE ut.tenant_role IS NOT NULL),
                    '{}'
                ) AS roles,
                COALESCE(
                    ARRAY_AGG(DISTINCT p.key)
                    FILTER (WHERE p.key IS NOT NULL),
                    '{}'
                ) AS permissions,
                MAX(ut.persona) AS persona
            FROM users u
            JOIN user_tenants ut
                ON ut.user_id = u.user_id
            JOIN tenants t
                ON t.tenant_id = ut.tenant_id
            -- role + permission join chain
            LEFT JOIN roles r
                ON r.tenant_id = t.tenant_id
               AND r.name = ut.tenant_role
            LEFT JOIN role_permissions rp
                ON rp.tenant_id = t.tenant_id
            LEFT JOIN permissions p
                ON p.permission_id = rp.permission_id
            WHERE u.user_id = $1
              AND t.tenant_id = $2
            GROUP BY
                u.user_id,
                u.primary_email,
                u.display_name,
                t.tenant_id,
                t.name
            """,
            user_id,
            tenant_id,
        )

        if not row:
            return None

        roles = row["roles"] or []
        permissions = row["permissions"] or []
        persona = row["persona"]

        # Pydantic expects list[str] for roles & permissions
        return UserContext(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            tenant_id=row["tenant_id"],
            tenant_name=row["tenant_name"],
            roles=list(roles),
            permissions=list(permissions),
            persona=persona,
        )

    # -------------------------------------------------------------------------
    # MANAGEMENT
    # -------------------------------------------------------------------------

    async def list_users_for_tenant(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        rows = await self.conn.fetch(
            """
            SELECT
                u.user_id,
                u.primary_email as email,
                u.display_name,
                ut.tenant_id,
                ut.tenant_email,
                ut.tenant_role,
                ut.persona,
                ut.status AS tenant_status,
                u.is_verified,
                u.mfa_enabled,
                u.created_at,
                u.updated_at
            FROM users u
            JOIN user_tenants ut
              ON ut.user_id = u.user_id
            WHERE ut.tenant_id = $1
            ORDER BY u.created_at ASC
            """,
            tenant_id,
        )
        # Adapt keys for UserResponse
        results = []
        for r in rows:
            d = dict(r)
            # roles comes from tenant_role
            d["roles"] = [d.pop("tenant_role")] if d.get("tenant_role") else []

            # Fetch tenant-wide permissions
            perm_rows = await self.conn.fetch(
                """
                SELECT DISTINCT p.key
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.permission_id
                WHERE rp.tenant_id = $1
                """,
                tenant_id,
            )
            permission_keys = [row["key"] for row in perm_rows]
            d["permissions"] = permission_keys

            results.append(d)
        return results

    async def update_user_profile(
        self,
        user_id: UUID,
        display_name: Optional[str] = None,
        locale: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: List[str] = []
        values: List[Any] = []
        if display_name is not None:
            fields.append("display_name = $" + str(len(values) + 1))
            values.append(display_name)
        if locale is not None:
            fields.append("locale = $" + str(len(values) + 1))
            values.append(locale)
        if timezone is not None:
            fields.append("timezone = $" + str(len(values) + 1))
            values.append(timezone)

        if not fields:
            return await self.get_user_by_id(user_id)

        values.append(user_id)
        sql = f"""
            UPDATE users
               SET {", ".join(fields)},
                   updated_at = now()
             WHERE user_id = ${len(values)}
         RETURNING
                user_id,
                primary_email as email,
                display_name,
                is_verified,
                locale,
                timezone,
                mfa_enabled,
                created_at,
                updated_at,
                last_login_at
        """
        row = await self.conn.fetchrow(sql, *values)
        return dict(row) if row else None

    async def deactivate_user_in_tenant(self, user_id: UUID, tenant_id: UUID):
        await self.conn.execute(
            """
            UPDATE user_tenants
            SET status = 'deactivated', updated_at = now()
            WHERE user_id = $1 AND tenant_id = $2
            """,
            user_id,
            tenant_id,
        )

    # NEW: persona update per tenant
    async def update_user_persona(
        self,
        user_id: UUID,
        tenant_id: UUID,
        persona: Optional[str],
    ) -> None:
        """
        Update persona on user_tenants for a specific tenant.
        """
        await self.conn.execute(
            """
            UPDATE user_tenants
            SET persona = $3, updated_at = now()
            WHERE user_id = $1 AND tenant_id = $2
            """,
            user_id,
            tenant_id,
            persona,
        )

        # -------------------------------------------------------------------------
        # PASSWORD MANAGEMENT
        # -------------------------------------------------------------------------

        async def update_password(
                self,
                user_id: UUID,
                hashed_password: str,
        ) -> bool:
            """
            Update user's password.

            Args:
                user_id: User's ID
                hashed_password: Already hashed password (use get_password_hash())
            """
            result = await self.conn.execute(
                """
                UPDATE users
                SET hashed_password = $2,
                    password_updated_at = now(),
                    updated_at = now()
                WHERE user_id = $1
                """,
                user_id,
                hashed_password,
            )
            return "UPDATE 1" in result

        async def get_password_hash(self, user_id: UUID) -> Optional[str]:
            """
            Get user's current password hash (for verification).
            """
            row = await self.conn.fetchrow(
                "SELECT hashed_password FROM users WHERE user_id = $1",
                user_id,
            )
            return row["hashed_password"] if row else None

        async def verify_current_password(
                self,
                user_id: UUID,
                plain_password: str,
        ) -> bool:
            """
            Verify user's current password.
            """
            from app.core.security import verify_password

            hashed = await self.get_password_hash(user_id)
            if not hashed:
                return False

            return verify_password(plain_password, hashed)

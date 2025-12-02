# app/modules/auth/mfa/repository.py

from asyncpg import Connection
from uuid import UUID
from typing import Optional, List

from app.modules.auth.mfa.schemas import (
    MFAEnrollRequest,
    MFAEnrollResponse,
    MFADeviceResponse,
)


class MFARepository:
    """
    Repository for MFA methods.
    Assumes a table like:

      CREATE TABLE mfa_methods (
          mfa_method_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
          user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
          tenant_id      UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
          method_type    TEXT NOT NULL,
          method_name    TEXT NOT NULL,
          secret         TEXT NOT NULL,
          enabled        BOOLEAN NOT NULL DEFAULT false,
          created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
          last_used_at   TIMESTAMPTZ
      );
    """

    def __init__(self, conn: Connection):
        self.conn = conn

    async def create_method(
        self,
        user_id: UUID,
        tenant_id: UUID,
        payload: MFAEnrollRequest,
        secret: str,
    ) -> MFAEnrollResponse:
        row = await self.conn.fetchrow(
            """
            INSERT INTO mfa_methods (
                user_id,
                tenant_id,
                method_type,
                method_name,
                secret,
                enabled
            )
            VALUES ($1, $2, $3, $4, $5, false)
            RETURNING mfa_method_id, method_type, method_name, secret, enabled, created_at
            """,
            user_id,
            tenant_id,
            payload.device_type,
            payload.device_name,
            secret,
        )
        return MFAEnrollResponse(
            device_id=row["mfa_method_id"],
            device_type=row["method_type"],
            device_name=row["method_name"],
            secret=row["secret"],
            enabled=row["enabled"],
            created_at=row["created_at"],
        )

    async def list_methods(self, user_id: UUID, tenant_id: UUID) -> List[MFADeviceResponse]:
        rows = await self.conn.fetch(
            """
            SELECT mfa_method_id, method_type, method_name,
                   enabled, created_at, last_used_at
            FROM mfa_methods
            WHERE user_id = $1 AND tenant_id = $2
            ORDER BY created_at DESC
            """,
            user_id,
            tenant_id,
        )
        return [
            MFADeviceResponse(
                device_id=r["mfa_method_id"],
                device_type=r["method_type"],
                device_name=r["method_name"],
                enabled=r["enabled"],
                created_at=r["created_at"],
                last_used_at=r["last_used_at"],
            )
            for r in rows
        ]

    async def get_method(self, device_id: UUID, user_id: UUID, tenant_id: UUID) -> Optional[MFADeviceResponse]:
        row = await self.conn.fetchrow(
            """
            SELECT mfa_method_id, method_type, method_name,
                   enabled, created_at, last_used_at
            FROM mfa_methods
            WHERE mfa_method_id = $1 AND user_id = $2 AND tenant_id = $3
            """,
            device_id,
            user_id,
            tenant_id,
        )
        if not row:
            return None
        return MFADeviceResponse(
            device_id=row["mfa_method_id"],
            device_type=row["method_type"],
            device_name=row["method_name"],
            enabled=row["enabled"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )

    async def enable_method(self, device_id: UUID, user_id: UUID, tenant_id: UUID) -> None:
        await self.conn.execute(
            """
            UPDATE mfa_methods
            SET enabled = true
            WHERE mfa_method_id = $1 AND user_id = $2 AND tenant_id = $3
            """,
            device_id,
            user_id,
            tenant_id,
        )

    async def delete_method(self, device_id: UUID, user_id: UUID, tenant_id: UUID) -> None:
        await self.conn.execute(
            """
            DELETE FROM mfa_methods
            WHERE mfa_method_id = $1 AND user_id = $2 AND tenant_id = $3
            """,
            device_id,
            user_id,
            tenant_id,
        )

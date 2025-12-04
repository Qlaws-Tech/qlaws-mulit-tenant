# app/modules/invitations/repository.py

"""
Repository for invitation CRUD:
- Create invitation
- Lookup by token
- Mark accepted / revoked
"""

from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List

from asyncpg import Connection

from app.modules.invitations.schemas import InvitationCreate, InvitationResponse
from app.core.security import hash_refresh_token  # SHA-256 helper


class InvitationRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    async def create_invitation(
        self,
        tenant_id: UUID,
        invited_by_user_id: UUID,
        payload: InvitationCreate,
        token_plain: str,
    ) -> InvitationResponse:
        token_hash = hash_refresh_token(token_plain)
        expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)

        row = await self.conn.fetchrow(
            """
            INSERT INTO invitations (
                tenant_id,
                email,
                invited_by_user_id,
                roles,
                group_ids,
                token_hash,
                expires_at
            )
            VALUES ($1, lower($2), $3, $4, $5, $6, $7)
            RETURNING invitation_id, email, roles, group_ids,
                      status, expires_at, created_at
            """,
            tenant_id,
            payload.email,
            invited_by_user_id,
            payload.roles,
            payload.group_ids,
            token_hash,
            expires_at,
        )

        return InvitationResponse(**dict(row))

    # ---------------------------------------------------------
    # LOOKUP BY TOKEN
    # ---------------------------------------------------------
    async def get_by_token(self, token_plain: str) -> Optional[dict]:
        token_hash = hash_refresh_token(token_plain)

        row = await self.conn.fetchrow(
            """
            SELECT invitation_id,
                   tenant_id,
                   email,
                   invited_by_user_id,
                   roles,
                   group_ids,
                   status,
                   expires_at,
                   created_at
            FROM invitations
            WHERE token_hash = $1
            """,
            token_hash,
        )
        return dict(row) if row else None

    # ---------------------------------------------------------
    # MARK ACCEPTED
    # ---------------------------------------------------------
    async def mark_accepted(self, invitation_id: UUID):
        await self.conn.execute(
            """
            UPDATE invitations
            SET status = 'accepted'
            WHERE invitation_id = $1
            """,
            invitation_id,
        )

    # ---------------------------------------------------------
    # REVOKE
    # ---------------------------------------------------------
    async def revoke(self, tenant_id: UUID, invitation_id: UUID) -> bool:
        result = await self.conn.execute(
            """
            UPDATE invitations
            SET status = 'revoked'
            WHERE tenant_id = $1 AND invitation_id = $2
            """,
            tenant_id,
            invitation_id,
        )
        return result.startswith("UPDATE") and not result.endswith(" 0")

    # ---------------------------------------------------------
    # LIST (PER TENANT)
    # ---------------------------------------------------------
    async def list_for_tenant(self, tenant_id: UUID) -> List[InvitationResponse]:
        rows = await self.conn.fetch(
            """
            SELECT invitation_id, email, roles, group_ids,
                   status, expires_at, created_at
            FROM invitations
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            """,
            tenant_id,
        )
        return [InvitationResponse(**dict(r)) for r in rows]

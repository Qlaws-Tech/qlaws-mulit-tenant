from asyncpg import Connection
from uuid import UUID
from datetime import datetime
from typing import List
from app.modules.invitations.schemas import InvitationCreate, InvitationResponse

class InvitationRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create(self, email: str, role_ids: List[UUID], token_hash: str, inviter_id: str, expires_at: datetime) -> InvitationResponse:
        # RLS automatically attaches tenant_id
        query = """
            INSERT INTO invitations (email, invited_by, role_ids, token_hash, expires_at, status)
            VALUES ($1, $2::uuid, $3, $4, $5, 'pending')
            RETURNING invitation_id, email, status, expires_at, created_at
        """
        row = await self.conn.fetchrow(query, email, inviter_id, role_ids, token_hash, expires_at)
        return InvitationResponse(**dict(row))

    async def get_pending_by_hash(self, token_hash: str):
        # Global lookup (token contains entropy), but we should check expiry
        query = """
            SELECT invitation_id, tenant_id, email, role_ids, status
            FROM invitations 
            WHERE token_hash = $1 AND status = 'pending' AND expires_at > now()
        """
        # Note: This query might need to run as system user/bypass RLS
        # because the accepting user is anonymous/not logged in yet!
        return await self.conn.fetchrow(query, token_hash)

    async def mark_accepted(self, invitation_id: UUID):
        await self.conn.execute(
            "UPDATE invitations SET status = 'accepted', accepted_at = now() WHERE invitation_id = $1",
            invitation_id
        )
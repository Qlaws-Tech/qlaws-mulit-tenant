# app/modules/invitations/Service.py

"""
InvitationService:
- Orchestrates invitation creation
- Acceptance → creates user + tenant membership + group membership
- Integrates Audit logging
"""

import secrets
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import HTTPException, status


from app.modules.invitations.repository import InvitationRepository
from app.modules.invitations.schemas import (
    InvitationCreate,
    InvitationResponse,
    InvitationAcceptRequest,
)
from app.modules.users.repository import UserRepository
from app.modules.groups.repository import GroupRepository
from app.modules.roles.repository import RoleRepository
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate
from app.core.security import get_password_hash


class InvitationService:
    def __init__(
        self,
        repo: InvitationRepository,
        user_repo: UserRepository,
        group_repo: GroupRepository,
        role_repo: RoleRepository,
        audit_repo: AuditRepository,
        conn,
    ):
        self.repo = repo
        self.user_repo = user_repo
        self.group_repo = group_repo
        self.role_repo = role_repo
        self.audit_repo = audit_repo
        self.conn = conn

    # ---------------------------------------------------------
    # CREATE INVITATION
    # ---------------------------------------------------------
    async def create_invitation(
        self,
        tenant_id: UUID,
        invited_by_user_id: UUID,
        payload: InvitationCreate,
        ip_address: str | None,
    ) -> tuple[InvitationResponse, str]:
        """
        Returns (invitation_response, raw_token_for_email)
        """
        # Raw token sent via email
        token_plain = secrets.token_urlsafe(32)

        # Persist invitation (repository is responsible for hashing token etc.)
        invitation = await self.repo.create_invitation(
            tenant_id=tenant_id,
            invited_by_user_id=invited_by_user_id,
            payload=payload,
            token_plain=token_plain,
        )

        # Audit
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="invitation.create",
                resource_type="invitation",
                resource_id=str(invitation.invitation_id),
                details={
                    "tenant_id": str(tenant_id),
                    "email": invitation.email,
                    "roles": invitation.roles,
                    "group_ids": [str(g) for g in invitation.group_ids],
                    "expires_at": invitation.expires_at.isoformat()
                    if invitation.expires_at
                    else None,
                },
            ),
            actor_user_id=invited_by_user_id,
            ip_address=ip_address,
        )

        return invitation, token_plain

    # ---------------------------------------------------------
    # ACCEPT INVITATION
    # ---------------------------------------------------------
    async def accept_invitation(
            self,
            body: InvitationAcceptRequest,
            ip_address: Optional[str],
    ):
        """
        - Verify token
        - Check not expired / revoked / accepted
        - Create user + tenant membership
        - Add groups
        - Mark invitation accepted
        - Audit everything
        """
        # 1. Lookup invitation by token
        data = await self.repo.get_by_token(body.token)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invitation token",
            )

        if data["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation not pending",
            )

        if data["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation expired",
            )

        tenant_id: UUID = data["tenant_id"]
        email: str = data["email"]
        roles: list[str] = data["roles"]
        group_ids: list[UUID] = data["group_ids"]
        invitation_id: UUID = data["invitation_id"]

        # 2. Create user + membership in transaction
        async with self.conn.transaction():
            # 2.1 Hash password and create user payload
            hashed_password = get_password_hash(body.password)

            # FIXED: Pass single payload dict with all required fields
            user_payload = {
                "email": email,
                "display_name": body.display_name,
                "hashed_password": hashed_password,
                "tenant_id": tenant_id,
                "tenant_role": roles[0] if roles else "member",
                "status": "active",
            }

            user_result = await self.user_repo.create_user(user_payload)

            # Extract user_id from result
            user_id = user_result["user"]["user_id"]
            user_tenant_id = user_result["membership"]["user_tenant_id"]

            # 2.2 Add to groups
            for gid in group_ids:
                await self.group_repo.add_member(gid, user_id, tenant_id)

            # 2.3 Assign additional roles if more than one
            if len(roles) > 1:
                for role_name in roles[1:]:
                    # Get role_id by name
                    role_row = await self.conn.fetchrow(
                        "SELECT role_id FROM roles WHERE tenant_id = $1 AND name = $2",
                        tenant_id,
                        role_name,
                    )
                    if role_row:
                        await self.role_repo.assign_role(
                            user_tenant_id=user_tenant_id,
                            role_id=role_row["role_id"],
                        )

            # 2.4 Mark invitation accepted
            await self.repo.mark_accepted(invitation_id)

        # 3. Audit
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="invitation.accept",
                resource_type="invitation",
                resource_id=str(invitation_id),
                details={
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "roles": roles,
                    "group_ids": [str(g) for g in group_ids],
                },
            ),
            actor_user_id=user_id,
            ip_address=ip_address,
        )

        return {"message": "Invitation accepted"}

    # ---------------------------------------------------------
    # REVOKE INVITATION
    # ---------------------------------------------------------
    async def revoke_invitation(
        self,
        tenant_id: UUID,
        invitation_id: UUID,
        actor_user_id: UUID,
        ip_address: str | None,
    ):
        success = await self.repo.revoke(tenant_id, invitation_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )

        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="invitation.revoke",
                resource_type="invitation",
                resource_id=str(invitation_id),
                details={"tenant_id": str(tenant_id)},
            ),
            actor_user_id=actor_user_id,
            ip_address=ip_address,
        )

        return {"message": "Invitation revoked"}

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------
    async def list_invitations(self, tenant_id: UUID):
        return await self.repo.list_for_tenant(tenant_id)

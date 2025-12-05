# app/modules/invitations/router.py

from fastapi import APIRouter, Depends, Request, status
from uuid import UUID

from app.dependencies.database import get_tenant_db_connection
from app.dependencies.auth_utils import get_current_user_id
from app.dependencies.permissions import require_permission

from app.modules.invitations.schemas import (
    InvitationCreate,
    InvitationResponse,
    InvitationAcceptRequest,
)
from app.modules.invitations.repository import InvitationRepository
from app.modules.invitations.Service import InvitationService
from app.modules.users.repository import UserRepository
from app.modules.groups.repository import GroupRepository
from app.modules.roles.repository import RoleRepository
from app.modules.audit.repository import AuditRepository


router = APIRouter(prefix="/api/v1/invitations", tags=["Invitations"])


async def get_invitation_service(conn = Depends(get_tenant_db_connection)) -> InvitationService:
    """
    Provide InvitationService with all required repositories.
    """
    inv_repo = InvitationRepository(conn)
    user_repo = UserRepository(conn)
    group_repo = GroupRepository(conn)
    role_repo = RoleRepository(conn)
    audit_repo = AuditRepository(conn)
    return InvitationService(inv_repo, user_repo, group_repo, role_repo, audit_repo, conn)


# ---------------------------------------------------------
# CREATE INVITATION
# ---------------------------------------------------------
@router.post(
    "/",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("invitation.create"))],
)
async def create_invitation(
    request: Request,
    body: InvitationCreate,
    service: InvitationService = Depends(get_invitation_service),
):
    tenant_id = request.state.tenant_id
    # get_current_user_id returns a str, convert to UUID for the service layer
    invited_by_user_id = UUID(get_current_user_id(request))
    ip = request.client.host if request.client else None

    invitation, token_plain = await service.create_invitation(
        tenant_id=tenant_id,
        invited_by_user_id=invited_by_user_id,
        payload=body,
        ip_address=ip,
    )

    # You would send email here with token_plain embedded in link.
    # e.g., https://app/accept-invitation?token=token_plain

    return invitation


# ---------------------------------------------------------
# ACCEPT INVITATION (PUBLIC / NO AUTH)
# ---------------------------------------------------------
@router.post("/accept")
async def accept_invitation(
    request: Request,
    body: InvitationAcceptRequest,
    service: InvitationService = Depends(get_invitation_service),
):
    ip = request.client.host if request.client else None
    return await service.accept_invitation(body, ip)


# ---------------------------------------------------------
# LIST INVITATIONS (TENANT ADMIN)
# ---------------------------------------------------------
@router.get(
    "/",
    response_model=list[InvitationResponse],
    dependencies=[Depends(require_permission("invitation.read"))],
)
async def list_invitations(
    request: Request,
    service: InvitationService = Depends(get_invitation_service),
):
    tenant_id = request.state.tenant_id
    return await service.list_invitations(tenant_id)


# ---------------------------------------------------------
# REVOKE INVITATION
# ---------------------------------------------------------
@router.delete(
    "/{invitation_id}",
    dependencies=[Depends(require_permission("invitation.revoke"))],
)
async def revoke_invitation(
    invitation_id: UUID,
    request: Request,
    service: InvitationService = Depends(get_invitation_service),
):
    tenant_id = request.state.tenant_id
    actor_user_id = UUID(get_current_user_id(request))
    ip = request.client.host if request.client else None
    return await service.revoke_invitation(tenant_id, invitation_id, actor_user_id, ip)
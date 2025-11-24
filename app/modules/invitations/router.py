from fastapi import APIRouter, Depends, Request
from app.dependencies.rls import get_tenant_db_connection
from app.dependencies.database import get_db_connection
from app.dependencies.permissions import require_permission
from app.modules.invitations.Service import InvitationService
from app.modules.invitations.repository import InvitationRepository
from app.modules.invitations.schemas import InvitationCreate, InvitationAccept
from app.modules.users.repository import UserRepository
from app.dependencies.auth_utils import get_current_user_id

router = APIRouter()

# Protected: Send Invite
@router.post("/", status_code=201, dependencies=[Depends(require_permission("user.create"))])
async def send_invite(
    request: Request,
    data: InvitationCreate,
    conn = Depends(get_tenant_db_connection)
):
    inviter_id = get_current_user_id(request)
    service = InvitationService(InvitationRepository(conn), UserRepository(conn))
    return await service.send_invitation(data, inviter_id)

# Public: Accept Invite
@router.post("/accept", status_code=200)
async def accept_invite(
    data: InvitationAccept,
    conn = Depends(get_db_connection) # Raw connection
):
    service = InvitationService(InvitationRepository(conn), UserRepository(conn))
    return await service.accept_invitation(data)
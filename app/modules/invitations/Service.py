from fastapi import HTTPException
from uuid import uuid4
import hashlib
from datetime import datetime, timedelta, timezone
from app.core.email import send_email
from app.modules.invitations.repository import InvitationRepository
from app.modules.invitations.schemas import InvitationCreate, InvitationAccept
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.core.config import settings


class InvitationService:
    def __init__(self, repo: InvitationRepository, user_repo: UserRepository):
        self.repo = repo
        self.user_repo = user_repo

    async def send_invitation(self, data: InvitationCreate, inviter_id: str, tenant_name: str = "The Organization"):
        # 1. Check if user already exists in tenant (Optional optimization)

        # 2. Generate Token
        raw_token = str(uuid4())
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)  # 7 day validity

        # 3. Save
        invite = await self.repo.create(data.email, data.role_ids, token_hash, inviter_id, expires_at)

        # 4. Send Email
        link = f"https://app.qlaws.com/join?token={raw_token}"
        body = f"You have been invited to join {tenant_name}. Click here to setup your account: {link}"
        # In prod, use BackgroundTasks
        await send_email("You've been invited!", data.email, body)

        return {"message": "Invitation sent", "debug_token": raw_token}

    async def accept_invitation(self, data: InvitationAccept):
        # 1. Verify Token
        token_hash = hashlib.sha256(data.token.encode()).hexdigest()

        # CRITICAL: We need to bypass RLS here because the user is anonymous.
        # In a real app, we'd use a System Connection or temporarily disable RLS.
        # For this architecture, ensure the Repo method handles context appropriately
        # or the DB allows looking up invitations by token globally (via index).
        invite = await self.repo.get_pending_by_hash(token_hash)

        if not invite:
            raise HTTPException(404, "Invitation invalid or expired")

        tenant_id = invite['tenant_id']

        # 2. Create User
        # We need to set context to the tenant_id from the invite to create the user link
        await self.user_repo.conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))
        print("Sending Email ...")
        try:
            user = await self.user_repo.create_user(UserCreate(
                email=invite['email'],
                password=data.password,
                display_name=data.display_name,
                role="member"
            ))
            print("sent Email successfully ...")
        except Exception as e:
            raise HTTPException(400, f"Failed to create user: {str(e)}")

        # 3. Assign Roles (from invite)
        if invite['role_ids']:
            # SQL to insert into user_roles...
            pass

        # 4. Mark Invitation Accepted
        await self.repo.mark_accepted(invite['invitation_id'])

        return {"message": "Account created successfully. Please login."}
from pydantic import BaseModel, EmailStr, UUID4, Field
from datetime import datetime
from typing import List, Optional

class InvitationCreate(BaseModel):
    email: EmailStr
    role_ids: List[UUID4] = [] # Roles to assign upon acceptance

class InvitationAccept(BaseModel):
    token: str
    password: str = Field(..., min_length=8)
    display_name: str

class InvitationResponse(BaseModel):
    invitation_id: UUID4
    email: str
    status: str
    expires_at: datetime
    created_at: datetime
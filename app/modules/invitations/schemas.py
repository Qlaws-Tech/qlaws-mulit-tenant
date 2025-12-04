# app/modules/invitations/schemas.py

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from typing import List, Optional
from datetime import datetime


class InvitationCreate(BaseModel):
    """
    Request body to create an invitation for a user to join a tenant.
    """
    model_config = ConfigDict(from_attributes=True)
    email: str
    roles: List[str] = Field(default_factory=list)
    group_ids: List[UUID] = Field(default_factory=list)
    expires_in_days: int = Field(default=7, ge=1, le=90)


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    invitation_id: UUID
    email: str
    roles: List[str]
    group_ids: List[UUID]
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationAcceptRequest(BaseModel):
    """
    Payload used when an invited user accepts an invitation.
    """
    token: str  # plain invitation token from email
    display_name: str
    password: str = Field(..., min_length=8)

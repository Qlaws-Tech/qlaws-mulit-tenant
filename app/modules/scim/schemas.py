# app/modules/scim/schemas.py

from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


# -----------------------------
# SCIM INPUT MODELS
# -----------------------------

class SCIMName(BaseModel):
    givenName: Optional[str] = None
    familyName: Optional[str] = None


class SCIMEmail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    value: str
    primary: bool = True


class SCIMUserCreate(BaseModel):
    schemas: List[str]
    userName: str
    name: Optional[SCIMName] = None
    emails: Optional[List[SCIMEmail]] = None
    active: bool = True
    externalId: Optional[str] = None


# -----------------------------
# SCIM OUTPUT MODELS
# -----------------------------

class SCIMMeta(BaseModel):
    resourceType: str = "User"
    created: datetime
    lastModified: datetime
    location: str


class SCIMUserResponse(BaseModel):
    id: UUID
    userName: str
    name: Optional[SCIMName] = None
    emails: Optional[List[SCIMEmail]] = None
    active: bool
    externalId: Optional[str] = None
    meta: SCIMMeta

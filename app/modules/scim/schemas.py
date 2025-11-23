from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any

# SCIM has complex nested objects
class ScimName(BaseModel):
    givenName: str
    familyName: str

class ScimEmail(BaseModel):
    value: EmailStr
    primary: bool = False

class ScimUserCreate(BaseModel):
    # IdPs send this specific schema URN
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    userName: str
    name: ScimName
    emails: List[ScimEmail]
    active: bool = True
    externalId: Optional[str] = None

class ScimResponse(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id: str
    userName: str
    active: bool
    meta: Dict[str, Any]
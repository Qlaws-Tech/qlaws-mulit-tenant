from pydantic import BaseModel, UUID4, Field
from typing import Dict, Any, Optional
from datetime import datetime

class SSOConfig(BaseModel):
    client_id: str
    client_secret: str  # <--- Sensitive! Must be encrypted.
    issuer_url: str

class SsoProviderCreate(BaseModel):
    provider_type: str = Field(..., pattern="^(oidc|saml)$")
    name: str
    config: SSOConfig   # Nested JSON structure
    is_default: bool = False

class SsoProviderResponse(BaseModel):
    sso_id: UUID4
    name: str
    provider_type: str
    # We generally DO NOT return the full config (especially secret)
    # in list views for security, but will include it here for testing.
    config: Dict[str, Any]
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True
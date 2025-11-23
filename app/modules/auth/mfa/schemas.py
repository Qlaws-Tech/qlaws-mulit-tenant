from pydantic import BaseModel, UUID4
from datetime import datetime


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str  # Used to generate QR Code on frontend


class MfaVerifyRequest(BaseModel):
    secret: str
    code: str


class MfaMethodResponse(BaseModel):
    mfa_id: UUID4
    method_type: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True
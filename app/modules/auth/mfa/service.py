import pyotp
from fastapi import HTTPException
from uuid import UUID
from app.modules.auth.mfa.repository import MfaRepository
from app.modules.auth.mfa.schemas import MfaSetupResponse


class MfaService:
    def __init__(self, repo: MfaRepository):
        self.repo = repo

    def generate_secret(self, email: str) -> MfaSetupResponse:
        """Generates a fresh random secret and URI."""
        secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="QLaws")
        return MfaSetupResponse(secret=secret, provisioning_uri=uri)

    async def setup_totp(self, user_id: UUID, tenant_id: str, secret: str, code: str):
        """
        Verifies the code provided by the user against the secret.
        If valid, saves the method to DB.
        """
        totp = pyotp.TOTP(secret)
        if not totp.verify(code):
            raise HTTPException(400, detail="Invalid TOTP code")

        # Save to DB
        return await self.repo.create_totp_method(user_id, secret, tenant_id)

    async def enable_totp(self, mfa_id: UUID):
        return await self.repo.enable_method(mfa_id)
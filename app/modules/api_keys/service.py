# app/modules/api_keys/service.py

import secrets
import hashlib
from typing import Optional, List

from fastapi import HTTPException, status

from app.modules.api_keys.schemas import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyWithPlain,
    ApiKeyInfo,
)
from app.modules.api_keys.repository import ApiKeyRepository
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate


class ApiKeyService:
    """
    High-level API key management + validation.
    Used both by REST API and by SCIMService for Bearer tokens.
    """

    def __init__(self, repo: ApiKeyRepository, audit_repo: Optional[AuditRepository] = None):
        self.repo = repo
        self.audit_repo = audit_repo or AuditRepository(repo.conn)

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    async def create_api_key(self, payload: ApiKeyCreate) -> ApiKeyWithPlain:
        plain_key = self._generate_token()
        hashed = self._hash_token(plain_key)

        created = await self.repo.create(
            name=payload.name,
            hashed_key=hashed,
            scopes=payload.scopes,
        )

        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="api_key.create",
                resource_type="api_key",
                resource_id=str(created.api_key_id),
                details={"name": created.name, "scopes": created.scopes},
            )
        )

        return ApiKeyWithPlain(
            api_key_id=created.api_key_id,
            name=created.name,
            scopes=created.scopes,
            created_at=created.created_at,
            plain_key=plain_key,
        )

    # ---------------------------------------------------------
    # LIST / DELETE
    # ---------------------------------------------------------
    async def list_keys(self) -> List[ApiKeyResponse]:
        return await self.repo.list_keys()

    async def delete_key(self, api_key_id) -> None:
        await self.repo.delete(api_key_id)
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="api_key.delete",
                resource_type="api_key",
                resource_id=str(api_key_id),
                details={},
            )
        )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    async def validate_token(
        self,
        token: str,
        required_scope: Optional[str] = None,
    ) -> Optional[ApiKeyInfo]:
        """
        Used by SCIMService and any other API-key-based integration.
        Returns ApiKeyInfo if token is valid and has required scope.
        """
        hashed = self._hash_token(token)
        info = await self.repo.get_by_hashed_key(hashed)
        if not info:
            return None

        if required_scope and required_scope not in info.scopes:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"API key missing required scope: {required_scope}",
            )

        return info

    # ---------------------------------------------------------
    # INTERNAL UTILS
    # ---------------------------------------------------------
    def _generate_token(self) -> str:
        # URL-safe random token
        return secrets.token_urlsafe(32)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

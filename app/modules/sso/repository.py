# app/modules/sso/repository.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from asyncpg import Connection

from app.modules.sso.schemas import SSOProviderCreate, SSOProviderUpdate, SSOProviderResponse
from app.core.encryption import encrypt_value, decrypt_value


class SSOProviderRepository:
    """
    Tenant-scoped SSO Provider repository.

    - Stores SSO config with sensitive fields encrypted (e.g., client_secret).
    - Uses RLS via current_setting('app.current_tenant_id').
    """

    def __init__(self, conn: Connection):
        self.conn = conn

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    async def create(self, payload: SSOProviderCreate) -> SSOProviderResponse:
        enc_config = self._encrypt_config(payload.config)

        row = await self.conn.fetchrow(
            """
            INSERT INTO sso_providers (
                tenant_id,
                name,
                provider_type,
                enabled,
                description,
                config
            )
            VALUES (
                current_setting('app.current_tenant_id', true)::uuid,
                $1,
                $2,
                $3,
                $4,
                $5::jsonb
            )
            RETURNING
                sso_provider_id,
                tenant_id,
                name,
                provider_type,
                enabled,
                description,
                config,
                created_at
            """,
            payload.name,
            payload.provider_type,
            payload.enabled,
            payload.description,
            enc_config,
        )

        # For the API response on creation, we want plaintext config
        return SSOProviderResponse(
            sso_provider_id=row["sso_provider_id"],
            provider_type=row["provider_type"],
            name=row["name"],
            description=row["description"],
            enabled=row["enabled"],
            config=payload.config,
            created_at=row["created_at"],
        )

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------
    async def list_providers(self) -> List[SSOProviderResponse]:
        rows = await self.conn.fetch(
            """
            SELECT
                sso_provider_id,
                name,
                provider_type,
                enabled,
                description,
                config,
                created_at
            FROM sso_providers
            ORDER BY created_at DESC
            """
        )
        providers: List[SSOProviderResponse] = []
        for r in rows:
            dec_config = self._decrypt_config(dict(r["config"]))
            providers.append(
                SSOProviderResponse(
                    sso_provider_id=r["sso_provider_id"],
                    provider_type=r["provider_type"],
                    name=r["name"],
                    description=r["description"],
                    enabled=r["enabled"],
                    config=dec_config,
                    created_at=r["created_at"],
                )
            )
        return providers

    async def get_by_id(self, provider_id: UUID) -> Optional[SSOProviderResponse]:
        r = await self.conn.fetchrow(
            """
            SELECT
                sso_provider_id,
                name,
                provider_type,
                enabled,
                description,
                config,
                created_at
            FROM sso_providers
            WHERE sso_provider_id = $1
            """,
            provider_id,
        )
        if not r:
            return None

        dec_config = self._decrypt_config(dict(r["config"]))
        return SSOProviderResponse(
            sso_provider_id=r["sso_provider_id"],
            provider_type=r["provider_type"],
            name=r["name"],
            description=r["description"],
            enabled=r["enabled"],
            config=dec_config,
            created_at=r["created_at"],
        )

    # ------------------------------------------------------------------
    # UPDATE / DELETE
    # ------------------------------------------------------------------
    async def update(self, provider_id: UUID, payload: SSOProviderUpdate) -> Optional[SSOProviderResponse]:
        existing = await self.get_by_id(provider_id)
        if not existing:
            return None

        new_name = payload.name or existing.name
        new_description = payload.description if payload.description is not None else existing.description
        new_enabled = payload.enabled if payload.enabled is not None else existing.enabled
        new_config = payload.config if payload.config is not None else existing.config

        enc_config = self._encrypt_config(new_config)

        await self.conn.execute(
            """
            UPDATE sso_providers
            SET name = $2,
                description = $3,
                enabled = $4,
                config = $5::jsonb
            WHERE sso_provider_id = $1
            """,
            provider_id,
            new_name,
            new_description,
            new_enabled,
            enc_config,
        )

        return await self.get_by_id(provider_id)

    async def delete(self, provider_id: UUID):
        await self.conn.execute(
            "DELETE FROM sso_providers WHERE sso_provider_id = $1",
            provider_id,
        )

    # ------------------------------------------------------------------
    # CONFIG ENCRYPTION HELPERS
    # ------------------------------------------------------------------
    def _encrypt_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypts known sensitive fields in the config.
        """
        cfg = dict(cfg) if cfg else {}
        if "client_secret" in cfg and cfg["client_secret"]:
            cfg["client_secret"] = encrypt_value(cfg["client_secret"])
        return cfg

    def _decrypt_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(cfg) if cfg else {}
        if "client_secret" in cfg and cfg["client_secret"]:
            try:
                cfg["client_secret"] = decrypt_value(cfg["client_secret"])
            except Exception:
                # If decryption fails (e.g., legacy config), leave as-is
                pass
        return cfg

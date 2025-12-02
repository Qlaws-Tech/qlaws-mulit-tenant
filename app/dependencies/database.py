# app/dependencies/database.py

from fastapi import Depends, HTTPException, status
from typing import AsyncGenerator
from app.core.database import db
from app.dependencies.auth_utils import get_current_token_payload


async def get_db_connection() -> AsyncGenerator:
    """
    System-level connection WITHOUT tenant RLS context.
    Used for health checks, system endpoints, etc.
    """
    # Use a special tenant (or no RLS enforcement) as designed in your DB.
    async for conn in db.get_connection("00000000-0000-0000-0000-000000000000"):
        yield conn


async def get_tenant_db_connection(
    token_payload: dict = Depends(get_current_token_payload),
) -> AsyncGenerator:
    """
    Tenant-scoped connection WITH RLS context based on token's tid.
    """
    tenant_id = token_payload.get("tid")
    if not tenant_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Tenant ID missing in token",
        )

    async for conn in db.get_connection(tenant_id):
        yield conn

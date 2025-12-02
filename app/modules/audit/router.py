# app/modules/audit/router.py

from fastapi import APIRouter, Depends
from typing import List

from app.dependencies.database import get_tenant_db_connection
from app.dependencies.permissions import require_permissions
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogEntry

router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
)


def get_audit_repo(conn=Depends(get_tenant_db_connection)) -> AuditRepository:
    return AuditRepository(conn)


@router.get(
    "/logs",
    response_model=List[AuditLogEntry],
    dependencies=[Depends(require_permissions(["audit.read"]))],
)
async def list_audit_logs(
    repo: AuditRepository = Depends(get_audit_repo),
):
    # Simple list with default limit; can be extended with query params
    return await repo.list_logs()

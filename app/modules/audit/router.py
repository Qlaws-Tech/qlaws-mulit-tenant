from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from datetime import datetime
from app.dependencies.rls import get_tenant_db_connection
from app.modules.audit.repository import AuditRepository
from app.modules.audit.service import AuditService
from app.modules.audit.schemas import AuditLogResponse

router = APIRouter()

async def get_audit_service(conn = Depends(get_tenant_db_connection)):
    return AuditService(AuditRepository(conn))

@router.get("/", response_model=List[AuditLogResponse])
async def view_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    service: AuditService = Depends(get_audit_service)
):
    """
    Search audit logs for the current tenant.
    Protected by RLS.
    """
    return await service.get_tenant_logs(user_id, action, start_date, end_date, limit, offset)
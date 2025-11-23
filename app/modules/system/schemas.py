from pydantic import BaseModel

class CleanupResult(BaseModel):
    audit_logs_deleted: int
    expired_tokens_deleted: int
    revoked_tokens_deleted: int
    message: str
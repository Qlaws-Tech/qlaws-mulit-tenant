# app/modules/system/schemas.py

from pydantic import BaseModel


class CleanupResult(BaseModel):
    expired_tokens_deleted: int
    expired_password_tokens_deleted: int
    expired_blacklist_entries_deleted: int
    message: str

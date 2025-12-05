# app/modules/auth/exceptions.py

"""
Centralized auth exceptions used across services.
"""

from fastapi import HTTPException, status


class InvalidCredentialsException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


class UserNotInTenantException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to this tenant",
        )


class MFARequiredException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="MFA verification required",
        )

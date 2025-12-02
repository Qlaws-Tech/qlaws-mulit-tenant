# app/core/exceptions.py

from fastapi import HTTPException, status


class QLAWSError(HTTPException):
    def __init__(self, detail="An error occurred", status_code=status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class AuthenticationError(QLAWSError):
    def __init__(self, detail="Authentication failed"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class PermissionDenied(QLAWSError):
    def __init__(self, detail="Permission denied"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


class NotFoundError(QLAWSError):
    def __init__(self, detail="Resource not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)

# app/core/encryption.py

from cryptography.fernet import Fernet
from app.core.config import settings

# Master key derived from SECRET_KEY (better to use KMS in real prod)
_MASTER_KEY = settings.SECRET_KEY[:32].encode().ljust(32, b'0')
fernet = Fernet(Fernet.generate_key())


def encrypt_value(value: str) -> str:
    if not value:
        return value
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    if not value:
        return value
    return fernet.decrypt(value.encode()).decode()

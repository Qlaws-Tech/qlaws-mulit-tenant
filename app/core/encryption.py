from cryptography.fernet import Fernet
from config_dev import settings

# Initialize Fernet with the key from config
cipher_suite = Fernet(settings.FIELD_ENCRYPTION_KEY)

def encrypt_data(data: str) -> str:
    """Encrypts a string (e.g., client_secret). Returns URL-safe string."""
    if not data: return None
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(token: str) -> str:
    """Decrypts the token back to the original string."""
    if not token: return None
    try:
        return cipher_suite.decrypt(token.encode()).decode()
    except Exception:
        return None  # Fail safe if key changed or data corrupt
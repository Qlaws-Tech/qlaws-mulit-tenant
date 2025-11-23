from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "QLaws Backend"

    # --- Database Settings (Renamed to Uppercase) ---
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_USER: str = "qlaws_app"
    DATABASE_PASSWORD: str = "app_password"
    DATABASE_NAME: str = "qlaws_db"

    DATABASE_POOL_MIN_SIZE: int = 1
    DATABASE_POOL_SIZE: int = 5

    # --- Security & Auth ---
    AUTH_MODE: str = "local"
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    FIELD_ENCRYPTION_KEY: str = "J8bT3qX5zW9yR1pU2vN4mS7oK6lI0aE8dC5fB2gH1jL="

    # External Auth
    AUTH_DOMAIN: Optional[str] = None
    AUTH_AUDIENCE: Optional[str] = None
    AUTH_ALGORITHM: str = "RS256"

    # --- Infrastructure ---
    REDIS_URL: str = "redis://localhost:6379/0"

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@qlaws.com"

    # --- System Operations ---
    SYSTEM_KEY: str = "sys_admin_secret_123"

    # Pydantic Config
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        # Updated to use uppercase attributes
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"


settings = Settings()
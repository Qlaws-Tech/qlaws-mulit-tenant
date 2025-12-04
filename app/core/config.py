# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
from typing import Optional


class Settings(BaseSettings):
    # -------------------------------------------------
    # Project
    # -------------------------------------------------
    APP_NAME: str = "QLaws Backend"
    PROJECT_NAME: str = "QLaws Backend"
    DEBUG: bool = False
    ENVIRONMENT: str = "local"

    # -------------------------------------------------
    # Database Settings
    # -------------------------------------------------
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str = "postgres"
    DATABASE_NAME: str = "qlaws"

    # -------------------------------------------------
    # Redis / Cache
    # -------------------------------------------------
    REDIS_URL: str = "REDIS_URL=redis://localhost:6379/0"

    # -------------------------------------------------
    # JWT / Auth
    # -------------------------------------------------
    JWT_SECRET_KEY: str = "CHANGE_ME_SUPER_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # (e.g., 7 days)

    # Optional “pepper” for password hashing (extra static secret)
    # You can override this in .env:
    #   PASSWORD_PEPPER=some-very-long-random-string
    PASSWORD_PEPPER: str = "CHANGE_ME_TO_A_RANDOM_LONG_STRING"

    # -------------------------------------------------
    # Email Settings (adjust or override in .env)
    # -------------------------------------------------
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    EMAIL_FROM: Optional[str] = None

    # -------------------------------------------------
    # Frontend / URLs
    # -------------------------------------------------
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # -------------------------------------------------
    # Pydantic Settings
    # -------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",        # ignore unknown env vars
        case_sensitive=False,
    )

    # -------------------------------------------------
    # Computed / convenience properties
    # -------------------------------------------------
    @computed_field
    @property
    def DATABASE_URL(self) -> str:  # type: ignore[override]
        """
        Convenience DSN string for libraries that want a URL.
        """
        return (
            f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    @computed_field
    @property
    def SECRET_KEY(self) -> str:  # type: ignore[override]
        """
        Alias so code can use settings.SECRET_KEY like before.
        """
        return self.JWT_SECRET_KEY

    @computed_field
    @property
    def ALGORITHM(self) -> str:  # type: ignore[override]
        """
        Alias so code can use settings.ALGORITHM like before.
        """
        return self.JWT_ALGORITHM


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "QLaws Backend"

    # Database
    database_host: str = "localhost"
    database_port: int = 5432
    database_user: str = "qlaws_app"
    database_password: str = "app_password"
    database_name: str = "qlaws_db"
    database_pool_min_size: int = 1
    database_pool_size: int = 5

    # --- Auth Strategy Flag ---
    # Options: "local" (Your current JWT), "external" (Auth0/Okta/Keycloak)
    AUTH_MODE: str = "local"

    # --- Local Auth Settings ---
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- External Auth Settings (Auth0/Keycloak/Okta) ---
    # Used only if AUTH_MODE="external"
    AUTH_DOMAIN: Optional[str] = "your-tenant.auth0.com"
    AUTH_AUDIENCE: Optional[str] = "https://api.qlaws.com"
    AUTH_ALGORITHM: str = "RS256"

    # Auth / Security
    auth_provider: str = "jwt"
    jwt_secret_key: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Security
    FIELD_ENCRYPTION_KEY: str = "J8bT3qX5zW9yR1pU2vN4mS7oK6lI0aE8dC5fB2gH1jL="

    # --- NEW: SMTP Settings (Email) ---
    SMTP_HOST: str = "smtp.mailgun.org"
    SMTP_PORT: int = 587
    SMTP_USER: str = "postmaster@yourdomain.com"
    SMTP_PASSWORD: str = "secret"
    EMAILS_FROM_EMAIL: str = "noreply@qlaws.com"

    # --- NEW: Redis Settings (Caching) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"

settings = Settings()
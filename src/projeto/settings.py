from pydantic_settings import BaseSettings
from pylogkit import get_logger


class Settings(BaseSettings):
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str
    DB_DATABASE: str
    LOG_LEVEL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    SQLITE_DEV: int
    FRONTEND_PUBLIC_URL: str | None = None

    MINIO_USER: str | None = None
    MINIO_PASSWORD: str | None = None
    MINIO_URL: str | None = None
    MINIO_SECURE: bool | None = None
    MINIO_PUBLIC_URL: str | None = None

    # SMTP Settings
    SMTP_HOST: str | None = None
    SMTP_PORT: int | str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str | None = None
    EMAILS_FROM_NAME: str | None = None


SETTINGS = Settings()  # pyright: ignore[reportCallIssue]

LOGGER = get_logger("mylogger", level=SETTINGS.LOG_LEVEL)  # pyright: ignore[reportArgumentType]

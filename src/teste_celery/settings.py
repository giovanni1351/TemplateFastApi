from pydantic_settings import BaseSettings
from pylogkit import get_logger


class Settings(BaseSettings):
    # Celery / Flower
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    FLOWER_URL: str = "http://localhost:5555"

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

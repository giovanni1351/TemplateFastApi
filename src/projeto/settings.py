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


SETTINGS = Settings()  # pyright: ignore[reportCallIssue]

LOGGER = get_logger("mylogger", level=SETTINGS.LOG_LEVEL)  # pyright: ignore[reportArgumentType]

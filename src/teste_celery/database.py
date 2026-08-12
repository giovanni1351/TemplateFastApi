from pathlib import Path
from typing import Annotated
from urllib.parse import quote_plus

from fastapi import Depends
from settings import LOGGER, SETTINGS
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# nome do projeto (diretório) — em dev cada projeto usa seu próprio sqlite,
# evitando colisão de tabelas quando vários projetos vivem no mesmo repositório
PROJECT_NAME = Path(__file__).resolve().parent.name


def generate_connection_string() -> str:
    if SETTINGS.SQLITE_DEV == 1:
        return f"sqlite+aiosqlite:///database_{PROJECT_NAME}.db"
    return (
        f"postgresql+asyncpg://{SETTINGS.DB_USER}:{quote_plus(SETTINGS.DB_PASSWORD)}@{
            SETTINGS.DB_HOST
        }:"
        f"{SETTINGS.DB_PORT}/{SETTINGS.DB_DATABASE}"
    )


async_engine: AsyncEngine = create_async_engine(
    generate_connection_string(),
    pool_recycle=450,
)
engine: Engine = create_engine(
    generate_connection_string(),
    pool_recycle=450,
)


async def get_async_session():  # noqa: ANN201
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]

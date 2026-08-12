from logging.config import fileConfig  # noqa: I001
import asyncio
from pathlib import Path
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel  # pyright: ignore[reportUnusedImport]

# convenção de nomes ANTES de importar os models: constraints nomeadas são
# obrigatórias para o batch mode do SQLite (ALTER via copy-and-move)
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

import schemas as schemas  # noqa: E402
from alembic import context  # noqa: E402
from database import generate_connection_string  # noqa: E402
from sqlalchemy.ext.asyncio import async_engine_from_config  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# tabela de versão exclusiva deste projeto (permite compartilhar o banco de dev)
PROJECT_NAME = Path(__file__).resolve().parent.parent.name
VERSION_TABLE = f"alembic_version_{PROJECT_NAME}"

config.set_main_option("sqlalchemy.url", generate_connection_string())


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001, ANN201
    """Ignora tabelas que não pertencem a este projeto (banco compartilhado)."""
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
        include_object=include_object,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def run_async_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(run_async_migrations())


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        dialect_opts={"foreign_keys": 1},
        version_table=VERSION_TABLE,
        include_object=include_object,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

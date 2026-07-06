"""Integração com alembic: gera e aplica migrations por projeto.

- Projeto `projeto` usa o alembic.ini da raiz do repositório (setup original).
- Outros projetos ganham um setup próprio em src/<projeto>/ (alembic.ini +
  migrations/), criado automaticamente na primeira migration:
    * `version_table` exclusiva (alembic_version_<projeto>) para poder
      compartilhar o mesmo banco de dev sem conflito;
    * `include_object` que ignora tabelas de outros projetos (não gera DROPs
      de tabelas que não estão no metadata do projeto).
"""

import re
import subprocess
import sys
from pathlib import Path

ENV_PY = '''from logging.config import fileConfig  # noqa: I001
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
'''

ALEMBIC_INI = """[alembic]
script_location = %(here)s/migrations
prepend_sys_path = %(here)s
path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

SCRIPT_MAKO = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
'''


class MigrationError(ValueError):
    """Erro de migration com a saída do alembic."""


def ensure_alembic(base_dir: Path, pdir: Path) -> Path:
    """Garante o setup alembic do projeto e retorna o caminho do .ini."""
    if pdir.name == "projeto":
        return base_dir / "alembic.ini"
    ini_path = pdir / "alembic.ini"
    migrations_dir = pdir / "migrations"
    if not ini_path.exists():
        ini_path.write_text(ALEMBIC_INI, encoding="utf-8")
    if not (migrations_dir / "env.py").exists():
        migrations_dir.mkdir(exist_ok=True)
        (migrations_dir / "env.py").write_text(ENV_PY, encoding="utf-8")
    if not (migrations_dir / "script.py.mako").exists():
        (migrations_dir / "script.py.mako").write_text(SCRIPT_MAKO, encoding="utf-8")
    (migrations_dir / "versions").mkdir(exist_ok=True)
    return ini_path


def _run_alembic(base_dir: Path, ini_path: Path, args: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ini_path), *args],
        cwd=base_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-15:])
        raise MigrationError(f"alembic {' '.join(args[:1])} falhou:\n{tail}")
    return output


def _is_empty_revision(path: Path) -> bool:
    """Detecta migration sem operações (upgrade só com pass)."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return False
    in_upgrade = False
    body: list[str] = []
    for line in source.splitlines():
        if line.startswith("def upgrade"):
            in_upgrade = True
            continue
        if in_upgrade:
            if line.startswith("def "):
                break
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", '"""', "'''")):
                body.append(stripped)
    return all(item in {"pass", '"""Upgrade schema."""'} for item in body)


def run_migrate(base_dir: Path, pdir: Path, message: str) -> dict:
    """Gera a migration (autogenerate) e aplica (upgrade head).

    Se o autogenerate não detectar mudanças, a revisão vazia é descartada.
    """
    ini_path = ensure_alembic(base_dir, pdir)
    revision_out = _run_alembic(
        base_dir, ini_path, ["revision", "--autogenerate", "-m", message]
    )
    match = re.search(r"Generating (.+?\.py)", revision_out)
    generated: Path | None = Path(match.group(1).strip()) if match else None

    if generated is not None and _is_empty_revision(generated):
        generated.unlink()
        return {
            "project": pdir.name,
            "message": message,
            "revision_file": None,
            "applied": False,
            "no_changes": True,
        }

    _run_alembic(base_dir, ini_path, ["upgrade", "head"])
    return {
        "project": pdir.name,
        "message": message,
        "revision_file": str(generated) if generated else None,
        "applied": True,
        "no_changes": False,
    }

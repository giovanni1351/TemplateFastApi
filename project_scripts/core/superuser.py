"""Criação de superusuário (admin) em qualquer projeto.

Roda um subprocesso com o PYTHONPATH do projeto escolhido, usando o
`database.py`/`settings.py` do próprio projeto — portanto funciona com
qualquer banco configurado no .env (SQLite em dev, PostgreSQL em produção).

Se o email já existir, o usuário é promovido a admin e a senha é atualizada.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPT = """
import asyncio
import json
import os


async def main() -> None:
    from auth import get_password_hash
    from database import async_engine, generate_connection_string
    from schemas.user import User
    from sqlmodel import select
    from sqlmodel.ext.asyncio.session import AsyncSession

    nome = os.environ["GER_SU_NOME"]
    sobrenome = os.environ["GER_SU_SOBRENOME"]
    email = os.environ["GER_SU_EMAIL"]
    senha = os.environ["GER_SU_PASSWORD"]
    backend = generate_connection_string().split("://", 1)[0]

    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        existing = (
            await session.exec(select(User).where(User.email == email))
        ).first()
        if existing is not None:
            existing.nome = nome
            existing.sobrenome = sobrenome
            existing.is_admin = True
            existing.password = get_password_hash(senha)
            session.add(existing)
            await session.commit()
            print(
                "GER_SU_RESULT:"
                + json.dumps(
                    {
                        "status": "atualizado",
                        "id": str(existing.id),
                        "email": email,
                        "database": backend,
                    }
                )
            )
            return
        user = User(
            nome=nome,
            sobrenome=sobrenome,
            email=email,
            password=get_password_hash(senha),
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        print(
            "GER_SU_RESULT:"
            + json.dumps(
                {
                    "status": "criado",
                    "id": str(user.id),
                    "email": email,
                    "database": backend,
                }
            )
        )


asyncio.run(main())
"""


class SuperuserError(ValueError):
    """Erro na criação do superusuário, com mensagem amigável."""


def create_superuser(
    base_dir: Path,
    pdir: Path,
    *,
    nome: str,
    sobrenome: str,
    email: str,
    password: str,
) -> dict:
    nome, sobrenome, email = nome.strip(), sobrenome.strip(), email.strip()
    if not nome:
        raise SuperuserError("o nome é obrigatório")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise SuperuserError(f"email inválido: '{email}'")
    if len(password) < 4:
        raise SuperuserError("a senha deve ter pelo menos 4 caracteres")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(pdir)
    env["GER_SU_NOME"] = nome
    env["GER_SU_SOBRENOME"] = sobrenome
    env["GER_SU_EMAIL"] = email
    env["GER_SU_PASSWORD"] = password

    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=base_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-8:])
        hint = ""
        lowered = output.lower()
        if "no such table" in lowered or "does not exist" in lowered:
            hint = (
                f"\nDica: a tabela 'user' não existe no banco — rode primeiro: "
                f"python gerenciar.py migrate {pdir.name}"
            )
        elif "connect" in lowered or "connection" in lowered:
            hint = "\nDica: verifique as variáveis de banco no .env (DB_HOST, DB_PORT...)"
        raise SuperuserError(f"falha ao criar superusuário:\n{tail}{hint}")

    for line in result.stdout.splitlines():
        if line.startswith("GER_SU_RESULT:"):
            data = json.loads(line.removeprefix("GER_SU_RESULT:"))
            data["project"] = pdir.name
            return data
    raise SuperuserError("o script não retornou resultado (saída inesperada)")

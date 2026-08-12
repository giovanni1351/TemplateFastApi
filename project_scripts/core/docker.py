"""Gerenciamento do docker-compose.yaml do repositório.

O arquivo gerado é dividido em blocos delimitados por marcadores:

    # <servico:postgres> ... # </servico:postgres>
    # <volume:postgres_data> ... # </volume:postgres_data>

Os blocos marcados são regenerados pelo gerenciador (idempotente); qualquer
serviço/volume adicionado manualmente fora dos marcadores é preservado.
"""

import re
import shutil
from pathlib import Path

from project_scripts.core.generator import GENERATED_HEADER

COMPOSE_FILE = "docker-compose.yaml"
INIT_SQL_REL = "docker/postgres-init.sql"

# extensões que exigem imagem própria do postgres
VECTOR_ALIASES = {"vector", "pgvector"}
POSTGIS_ALIASES = {"postgis"}

EXTENSION_RE = re.compile(r"^[a-z0-9_\-]+$")
VERSION_RE = re.compile(r"^\d{2}$")


class DockerError(ValueError):
    """Erro de configuração docker com mensagem amigável."""


# ---------------------------------------------------------------------------
# helpers de marcadores


def _service_block(name: str, body: str) -> str:
    return f"  # <servico:{name}>\n{body.rstrip()}\n  # </servico:{name}>"


def _volume_block(name: str) -> str:
    return f"  # <volume:{name}>\n  {name}:\n  # </volume:{name}>"


def has_managed_markers(text: str) -> bool:
    return "# <servico:" in text


def _find_block(lines: list[str], kind: str, name: str) -> tuple[int, int] | None:
    """Retorna [início, fim) das linhas do bloco marcado, incluindo marcadores."""
    open_marker = f"# <{kind}:{name}>"
    close_marker = f"# </{kind}:{name}>"
    start = end = None
    for i, line in enumerate(lines):
        if line.strip() == open_marker:
            start = i
        elif line.strip() == close_marker:
            end = i
            break
    if start is None or end is None or end < start:
        return None
    return start, end + 1


def _top_level_index(lines: list[str], key: str) -> int | None:
    for i, line in enumerate(lines):
        if line.rstrip() == f"{key}:":
            return i
    return None


def _section_end(lines: list[str], section_start: int) -> int:
    """Fim (exclusivo) de uma seção top-level: próxima linha sem indentação."""
    for i in range(section_start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith((" ", "\t", "#")):
            return i
    return len(lines)


def upsert_block(text: str, kind: str, name: str, block: str) -> str:
    """Substitui o bloco marcado ou o insere no fim da seção correspondente."""
    section = "services" if kind == "servico" else "volumes"
    lines = text.splitlines()

    found = _find_block(lines, kind, name)
    if found is not None:
        start, end = found
        lines[start:end] = block.splitlines()
        return "\n".join(lines) + "\n"

    section_start = _top_level_index(lines, section)
    if section_start is None:
        # cria a seção no fim do arquivo
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{section}:")
        lines.extend(block.splitlines())
        return "\n".join(lines) + "\n"

    insert_at = _section_end(lines, section_start)
    # recua para antes das linhas em branco que fecham a seção
    while insert_at > section_start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new_lines = block.splitlines()
    if insert_at > section_start + 1:
        new_lines = ["", *new_lines]
    lines[insert_at:insert_at] = new_lines
    return "\n".join(lines) + "\n"


def remove_block(text: str, kind: str, name: str) -> str:
    lines = text.splitlines()
    found = _find_block(lines, kind, name)
    if found is None:
        return text
    start, end = found
    while start > 0 and not lines[start - 1].strip():
        start -= 1
    del lines[start:end]
    return "\n".join(lines) + "\n"


def list_marked_services(text: str) -> list[str]:
    return re.findall(r"# <servico:([\w-]+)>", text)


def list_all_services(text: str) -> list[str]:
    """Nomes de serviços (chaves com 2 espaços de indentação) da seção services."""
    lines = text.splitlines()
    start = _top_level_index(lines, "services")
    if start is None:
        return []
    end = _section_end(lines, start)
    names: list[str] = []
    for line in lines[start + 1 : end]:
        m = re.match(r"^  ([\w-]+):\s*$", line)
        if m:
            names.append(m.group(1))
    return names


# ---------------------------------------------------------------------------
# normalização de opções


def validate_postgres_version(version: str) -> str:
    version = str(version).strip()
    if not VERSION_RE.match(version):
        raise DockerError(
            f"versão do postgres inválida: '{version}'. "
            "Use apenas a versão major, ex: 15, 16, 17."
        )
    return version


def normalize_extensions(extensions: list[str]) -> list[str]:
    """Normaliza a lista de extensões (minúsculas, sem duplicatas, valida nomes)."""
    result: list[str] = []
    for raw in extensions:
        for part in str(raw).split(","):
            ext = part.strip().lower()
            if not ext:
                continue
            if ext in VECTOR_ALIASES:
                ext = "vector"
            if not EXTENSION_RE.match(ext):
                raise DockerError(
                    f"nome de extensão inválido: '{part.strip()}'. "
                    "Use nomes como: vector, pg_trgm, unaccent, uuid-ossp, postgis."
                )
            if ext not in result:
                result.append(ext)
    return result


def postgres_image(version: str, extensions: list[str]) -> str:
    has_vector = any(e in VECTOR_ALIASES for e in extensions)
    has_postgis = any(e in POSTGIS_ALIASES for e in extensions)
    if has_vector and has_postgis:
        raise DockerError(
            "vector (pgvector) e postgis exigem imagens docker diferentes — "
            "para usar as duas é preciso uma imagem customizada. "
            "Escolha uma delas ou monte seu próprio Dockerfile do postgres."
        )
    if has_vector:
        return f"pgvector/pgvector:pg{version}"
    if has_postgis:
        return f"postgis/postgis:{version}-3.5"
    return f"postgres:{version}"


# ---------------------------------------------------------------------------
# renderização dos blocos


def render_header() -> str:
    return (
        f"{GENERATED_HEADER}\n"
        "# Blocos entre '# <servico:x>'/'# <volume:x>' são regenerados pelo gerenciador;\n"
        "# serviços adicionados manualmente fora dos marcadores são preservados.\n"
        "# As variáveis ${...} vêm do arquivo .env na raiz do repositório.\n"
    )


def render_postgres(project: str, image: str, extensions: list[str]) -> str:
    body = f"""  postgres:
    image: {image}
    container_name: {project}-postgres
    restart: always
    environment:
      POSTGRES_USER: ${{DB_USER:-db_user}}
      POSTGRES_PASSWORD: ${{DB_PASSWORD:-senha_secreta}}
      POSTGRES_DB: ${{DB_DATABASE:-app_db}}
    ports:
      - "${{DB_PORT:-5433}}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data"""
    if extensions:
        body += f"\n      - ./{INIT_SQL_REL}:/docker-entrypoint-initdb.d/10-extensions.sql"
    return _service_block("postgres", body)


def render_minio(project: str) -> str:
    body = f"""  minio:
    image: minio/minio
    container_name: {project}-minio
    restart: always
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${{MINIO_USER:-admin}}
      MINIO_ROOT_PASSWORD: ${{MINIO_PASSWORD:-senha_secreta}}
    ports:
      - "9000:9000" # API S3
      - "9001:9001" # Console web
    volumes:
      - minio_data:/data"""
    return _service_block("minio", body)


def _celery_env() -> str:
    return """      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1"""


def render_backend(project: str, *, minio: bool = False, celery: bool = False) -> str:
    depends = ["postgres"]
    if minio:
        depends.append("minio")
    if celery:
        depends.append("redis")
    depends_lines = "\n".join(f"      - {d}" for d in depends)
    body = f"""  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {project}-backend
    restart: always
    command: /app/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000 --workers 3 --app-dir src/{project}
    env_file:
      - .env
    environment:
      # dentro da rede do compose o banco é o serviço 'postgres'
      SQLITE_DEV: "0"
      DB_HOST: postgres
      DB_PORT: "5432\""""
    if minio:
        body += "\n      MINIO_URL: minio:9000"
    if celery:
        body += f"\n{_celery_env()}"
    body += f"""
    ports:
      - "8000:8000"
    depends_on:
{depends_lines}"""
    return _service_block("backend", body)


def render_redis(project: str) -> str:
    body = f"""  redis:
    image: redis:7-alpine
    container_name: {project}-redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data"""
    return _service_block("redis", body)


def _celery_service(
    project: str, service: str, command: str, *, ports: str = "", extra_depends: str = ""
) -> str:
    body = f"""  {service}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {project}-{service}
    restart: always
    working_dir: /app/src/{project}
    command: {command}
    env_file:
      - .env
    environment:
      SQLITE_DEV: "0"
      DB_HOST: postgres
      DB_PORT: "5432"
{_celery_env()}"""
    if ports:
        body += f"\n    ports:\n      - \"{ports}\""
    body += "\n    depends_on:\n      - redis\n      - postgres"
    if extra_depends:
        body += f"\n      - {extra_depends}"
    return _service_block(service, body)


def render_celery_worker(project: str) -> str:
    return _celery_service(
        project,
        "celery-worker",
        "/app/.venv/bin/celery -A celery_app worker --loglevel=info",
    )


def render_celery_beat(project: str) -> str:
    return _celery_service(
        project,
        "celery-beat",
        "/app/.venv/bin/celery -A celery_app beat --loglevel=info",
    )


def render_flower(project: str) -> str:
    return _celery_service(
        project,
        "flower",
        "/app/.venv/bin/celery -A celery_app flower --address=0.0.0.0 --port=5555",
        ports="5555:5555",
        extra_depends="celery-worker",
    )


def render_init_sql(extensions: list[str]) -> str:
    lines = [
        "-- Gerado pelo gerenciador do template.",
        "-- Executado pelo postgres apenas na PRIMEIRA inicialização do volume.",
        "-- Se o volume já existir, rode os CREATE EXTENSION manualmente (psql)",
        "-- ou recrie o volume com: docker compose down -v",
    ]
    lines.extend(f'CREATE EXTENSION IF NOT EXISTS "{ext}";' for ext in extensions)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# operações principais


def _read_compose(base_dir: Path) -> tuple[Path, str]:
    path = base_dir / COMPOSE_FILE
    if path.is_file():
        return path, path.read_text(encoding="utf-8")
    return path, ""


def _base_text() -> str:
    return render_header() + "\nservices:\n"


def _prepare_compose_text(
    base_dir: Path, *, force: bool
) -> tuple[Path, str, str | None]:
    """Carrega o compose gerenciado; se existir um não gerenciado, exige force.

    Retorna (path, texto_base, caminho_do_backup ou None).
    """
    path, text = _read_compose(base_dir)
    backup: str | None = None
    if text and not has_managed_markers(text):
        if not force:
            raise DockerError(
                f"já existe um {COMPOSE_FILE} não gerenciado pelo gerenciador. "
                "Use --force para substituí-lo (um backup .bak é criado)."
            )
        backup = str(path) + ".bak"
        shutil.copy2(path, backup)
        text = ""
    if not text:
        text = _base_text()
    return path, text, backup


def _project_of_compose(text: str) -> str | None:
    m = re.search(r"container_name: ([\w-]+)-(?:backend|postgres)", text)
    return m.group(1) if m else None


def setup_compose(
    base_dir: Path,
    project: str,
    *,
    postgres_version: str = "17",
    extensions: list[str] | None = None,
    minio: bool = True,
    force: bool = False,
) -> dict:
    """Gera/atualiza o docker-compose com postgres, minio (opcional) e backend."""
    version = validate_postgres_version(postgres_version)
    exts = normalize_extensions(extensions or [])
    image = postgres_image(version, exts)

    path, text, backup = _prepare_compose_text(base_dir, force=force)
    has_celery = "# <servico:celery-worker>" in text

    text = upsert_block(text, "servico", "postgres", render_postgres(project, image, exts))
    text = upsert_block(text, "volume", "postgres_data", _volume_block("postgres_data"))
    if minio:
        text = upsert_block(text, "servico", "minio", render_minio(project))
        text = upsert_block(text, "volume", "minio_data", _volume_block("minio_data"))
    else:
        text = remove_block(text, "servico", "minio")
        text = remove_block(text, "volume", "minio_data")
    text = upsert_block(
        text, "servico", "backend", render_backend(project, minio=minio, celery=has_celery)
    )

    created = [str(path)]
    warnings: list[str] = []
    init_sql = base_dir / INIT_SQL_REL
    if exts:
        init_sql.parent.mkdir(parents=True, exist_ok=True)
        init_sql.write_text(render_init_sql(exts), encoding="utf-8")
        created.append(str(init_sql))
        warnings.append(
            "as extensões só são criadas na primeira inicialização do volume do "
            "postgres; se o volume já existir, rode o CREATE EXTENSION manualmente "
            "ou recrie com 'docker compose down -v'"
        )
    elif init_sql.is_file():
        init_sql.unlink()
        warnings.append(f"{INIT_SQL_REL} removido (nenhuma extensão selecionada)")

    path.write_text(text, encoding="utf-8")

    return {
        "project": project,
        "file": str(path),
        "backup": backup,
        "postgres": {"version": version, "image": image, "extensions": exts},
        "minio": minio,
        "celery": has_celery,
        "services": list_all_services(text),
        "created": created,
        "warnings": warnings,
        "next_steps": [
            "confira usuário/senha/porta do banco no .env (DB_USER, DB_PASSWORD, DB_PORT...)",
            "suba os serviços: docker compose up -d --build",
        ],
    }


def add_celery_services(
    base_dir: Path,
    project: str,
    *,
    beat: bool = True,
    flower: bool = True,
) -> dict:
    """Adiciona redis + celery worker/beat/flower ao compose (cria a base se faltar)."""
    path, text = _read_compose(base_dir)
    warnings: list[str] = []
    if not text or not has_managed_markers(text):
        base = setup_compose(base_dir, project, force=bool(text))
        warnings.append(
            "docker-compose gerado com padrões (postgres 17, sem extensões, com minio) "
            "— rode 'docker-setup' para ajustar postgres/extensões"
        )
        if base.get("backup"):
            warnings.append(f"compose anterior preservado em {base['backup']}")
        text = path.read_text(encoding="utf-8")

    text = upsert_block(text, "servico", "redis", render_redis(project))
    text = upsert_block(text, "volume", "redis_data", _volume_block("redis_data"))
    text = upsert_block(text, "servico", "celery-worker", render_celery_worker(project))
    services = ["redis", "celery-worker"]
    if beat:
        text = upsert_block(text, "servico", "celery-beat", render_celery_beat(project))
        services.append("celery-beat")
    else:
        text = remove_block(text, "servico", "celery-beat")
    if flower:
        text = upsert_block(text, "servico", "flower", render_flower(project))
        services.append("flower")
    else:
        text = remove_block(text, "servico", "flower")

    # backend passa a depender do redis e enxergar o broker
    if "# <servico:backend>" in text:
        minio = "# <servico:minio>" in text
        text = upsert_block(
            text, "servico", "backend", render_backend(project, minio=minio, celery=True)
        )

    path.write_text(text, encoding="utf-8")
    return {
        "project": project,
        "file": str(path),
        "services_added": services,
        "services": list_all_services(text),
        "warnings": warnings,
    }


def compose_status(base_dir: Path) -> dict:
    """Estado atual do docker-compose: serviços gerenciados e manuais."""
    path, text = _read_compose(base_dir)
    if not text:
        return {"file": str(path), "exists": False, "managed": False, "services": []}
    managed = set(list_marked_services(text))
    services = [
        {"name": name, "managed": name in managed} for name in list_all_services(text)
    ]
    return {
        "file": str(path),
        "exists": True,
        "managed": has_managed_markers(text),
        "project": _project_of_compose(text),
        "services": services,
    }

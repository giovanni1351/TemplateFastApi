"""Criação de projetos novos a partir do template python_default.

Processa marcadores de feature nos arquivos do template:
    # <admin> ... # </admin>     mantido apenas se o projeto usa admin
    # <rbac> ... # </rbac>       mantido apenas se o projeto usa rbac
    # <no-admin># código         vira código real quando admin está OFF
    # <no-rbac># código          vira código real quando rbac está OFF
"""

import re
import shutil
from pathlib import Path
from subprocess import run

BLOCK_OPEN = re.compile(r"^\s*# <(admin|rbac)>\s*$")
BLOCK_CLOSE = re.compile(r"^\s*# </(admin|rbac)>\s*$")
ALT_LINE = re.compile(r"^(\s*)# <no-(admin|rbac)># ?(.*)$")


class ProjectError(ValueError):
    """Erro de criação de projeto com mensagem amigável."""


def process_markers(source: str, features: dict[str, bool]) -> str:
    """Processa os marcadores de feature de um arquivo de template."""
    out: list[str] = []
    stack: list[str] = []
    for line in source.splitlines():
        m_open = BLOCK_OPEN.match(line)
        if m_open:
            stack.append(m_open.group(1))
            continue
        m_close = BLOCK_CLOSE.match(line)
        if m_close:
            if not stack or stack[-1] != m_close.group(1):
                raise ProjectError(f"marcador desbalanceado no template: {line.strip()}")
            stack.pop()
            continue
        if any(not features.get(f, False) for f in stack):
            continue  # dentro de bloco de feature desligada
        m_alt = ALT_LINE.match(line)
        if m_alt:
            indent, feature, code = m_alt.groups()
            if not features.get(feature, False):
                out.append(indent + code)
            continue  # feature ligada: linha alternativa descartada
        out.append(line)
    if stack:
        raise ProjectError(f"marcador não fechado no template: {stack[-1]}")
    # remove linhas em branco triplicadas geradas pela remoção de blocos
    text = "\n".join(out)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.rstrip("\n") + "\n"


# arquivos processados com marcadores; os demais são copiados como estão
MARKER_FILES = {
    "app.py",
    "router.py",
    "routes/user.py",
    "schemas/user.py",
    "schemas/__init__.py",
    "admin/admin_setup.py",
    "admin/admin_view.py",
}

# partes do template condicionais a features
RBAC_ONLY = {
    "utils/rbac_router.py",
    "schemas/rbac.py",
    "admin/admin_rbac.py",
}
ADMIN_ONLY_DIRS = {"admin", "middleware"}

UV_PACKAGES = (
    "alembic asyncpg aiosqlite bcrypt fastapi fastcrud itsdangerous minio "
    "passlib pwdlib pydantic pydantic-settings pyjwt pylogkit "
    "sqladmin sqlmodel tzdata uvicorn python-multipart"
)


def create_project(
    base_dir: Path,
    name: str,
    *,
    admin: bool = True,
    rbac: bool = True,
    init_uv: bool = False,
    force: bool = False,
) -> dict:
    """Cria um projeto novo em src/<name> a partir do template."""
    normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
    if not normalized.isidentifier():
        raise ProjectError(f"nome de projeto inválido: '{name}'")

    template_dir = base_dir / "project_scripts" / "python_default"
    admin_template_dir = base_dir / "project_scripts" / "admin_template"
    target = base_dir / "src" / normalized
    if target.exists() and not force:
        raise ProjectError(
            f"o projeto '{normalized}' já existe em {target}. Use --force para sobrescrever."
        )

    features = {"admin": admin, "rbac": rbac}
    created_files: list[str] = []

    for src_path in sorted(template_dir.rglob("*")):
        if src_path.is_dir() or "__pycache__" in src_path.parts:
            continue
        rel = src_path.relative_to(template_dir).as_posix()
        if rel in RBAC_ONLY and not rbac:
            continue
        top_dir = rel.split("/", 1)[0]
        if top_dir in ADMIN_ONLY_DIRS and not admin:
            continue
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if rel in MARKER_FILES:
            content = process_markers(src_path.read_text(encoding="utf-8"), features)
            dest.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(src_path, dest)
        created_files.append(rel)

    if admin:
        templates_target = target / "templates"
        for src_path in sorted(admin_template_dir.rglob("*")):
            if src_path.is_dir():
                continue
            rel = src_path.relative_to(admin_template_dir).as_posix()
            if not rbac and re.search(r"rbac_[^/]+\.html$", rel):
                continue
            dest = templates_target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest)
            created_files.append(f"templates/{rel}")

    # setup alembic próprio do projeto (version_table exclusiva)
    from project_scripts.core.migrations import ensure_alembic

    ensure_alembic(base_dir, target)

    uv_ran = False
    if init_uv:
        run("uv init", cwd=base_dir, shell=True, check=False)
        run(f"uv add {UV_PACKAGES}", cwd=base_dir, shell=True, check=False)
        uv_ran = True

    return {
        "project": normalized,
        "path": str(target),
        "features": features,
        "files": len(created_files),
        "uv_init": uv_ran,
        "next_steps": [
            "configure o .env na raiz (veja .env.example)",
            f"gere e aplique as migrations: python gerenciar.py migrate {normalized}",
            f"suba com: uv run python -m uvicorn app:app --app-dir src/{normalized}",
        ],
    }

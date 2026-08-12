"""Adiciona Celery (worker/beat/flower) a um projeto existente.

Gera `celery_app.py` e `tasks.py` no projeto, acrescenta as configurações no
`settings.py`/`.env`, registra o painel do Flower dentro do admin (iframe) e
adiciona os serviços correspondentes no docker-compose.
"""

import re
from pathlib import Path
from subprocess import run

from project_scripts.core.analyzer import project_features
from project_scripts.core.docker import add_celery_services
from project_scripts.core.generator import GENERATED_HEADER

CELERY_UV_PACKAGES = '"celery[redis]" flower'


class CeleryError(ValueError):
    """Erro de configuração do celery com mensagem amigável."""


# ---------------------------------------------------------------------------
# arquivos gerados no projeto


def render_celery_app(project: str, *, beat: bool) -> str:
    text = f'''{GENERATED_HEADER}
from celery import Celery  # type: ignore[import-untyped]
from settings import SETTINGS

celery_app = Celery(
    "{project}",
    broker=SETTINGS.CELERY_BROKER_URL,
    backend=SETTINGS.CELERY_RESULT_BACKEND,
    include=["tasks"],
)

celery_app.conf.update(
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
'''
    if beat:
        text += '''
# agenda do celery beat — adicione/edite entradas aqui
celery_app.conf.beat_schedule = {
    "exemplo-a-cada-5-minutos": {
        "task": "tasks.exemplo",
        "schedule": 300.0,
    },
}
'''
    return text


def render_tasks() -> str:
    return f'''{GENERATED_HEADER}
from celery_app import celery_app
from settings import LOGGER


@celery_app.task
def exemplo() -> str:
    """Task de exemplo — troque pelo seu processamento real."""
    LOGGER.info("task de exemplo executada")
    return "ok"
'''


def render_admin_flower() -> str:
    return f'''{GENERATED_HEADER}
from settings import SETTINGS
from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import Response


class FlowerAdmin(BaseView):
    name = "Celery (Flower)"
    icon = "fa-solid fa-fan"

    @expose("/celery", methods=["GET"], identity="celery-flower")
    async def flower_index(self, request: Request) -> Response:
        return await self.templates.TemplateResponse(
            request,
            "sqladmin/celery_flower.html",
            {{
                "title": "Celery — Flower",
                "subtitle": "Workers, filas e tasks em tempo real",
                "flower_url": SETTINGS.FLOWER_URL,
            }},
        )
'''


FLOWER_TEMPLATE = """{% extends "sqladmin/layout.html" %}

{% block content %}
<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
    <div class="p-4 sm:p-6 border-b border-gray-200 flex items-center justify-between flex-wrap gap-3">
        <div>
            <h3 class="text-lg font-semibold text-gray-800">Flower — monitoramento do Celery</h3>
            <p class="text-sm text-gray-500 mt-1">Workers, filas e tasks em tempo real</p>
        </div>
        <a href="{{ flower_url }}" target="_blank" rel="noopener"
           class="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors font-medium text-sm">
            Abrir em nova aba
        </a>
    </div>
    <iframe src="{{ flower_url }}" class="w-full border-0"
            style="height: calc(100vh - 240px); min-height: 500px;" title="Flower"></iframe>
</div>
<p class="text-xs text-gray-400 mt-3">
    Se o painel não carregar, verifique se o serviço flower está no ar
    (docker compose up -d flower) e se FLOWER_URL no .env aponta para uma URL
    acessível pelo seu navegador.
</p>
{% endblock %}
"""

SETTINGS_FIELDS = """    # Celery / Flower
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    FLOWER_URL: str = "http://localhost:5555"
"""

ENV_BLOCK = """
# Celery / Flower — URLs usadas rodando FORA do docker (dentro do compose os
# serviços já apontam para redis://redis:6379 automaticamente)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
FLOWER_URL=http://localhost:5555
"""

CSP_IMPORTS = """from urllib.parse import urlparse

from settings import SETTINGS

# origem do Flower liberada no frame-src (painel embutido no admin)
_flower = urlparse(SETTINGS.FLOWER_URL)
FLOWER_ORIGIN = f"{_flower.scheme}://{_flower.netloc}"

"""

CSP_OLD_LINE = '"font-src \'self\' data:;"'
CSP_NEW_LINES = (
    "\"font-src 'self' data:; \"\n"
    '                f"frame-src \'self\' {FLOWER_ORIGIN};"'
)


# ---------------------------------------------------------------------------
# patches em arquivos existentes do projeto


def _patch_settings(pdir: Path) -> bool:
    path = pdir / "settings.py"
    if not path.is_file():
        raise CeleryError(f"settings.py não encontrado no projeto '{pdir.name}'")
    text = path.read_text(encoding="utf-8")
    if "CELERY_BROKER_URL" in text:
        return False
    match = re.search(r"^class Settings\(BaseSettings\):\s*$", text, flags=re.MULTILINE)
    if not match:
        raise CeleryError(
            "não encontrei 'class Settings(BaseSettings):' no settings.py — "
            "adicione CELERY_BROKER_URL/CELERY_RESULT_BACKEND/FLOWER_URL manualmente"
        )
    insert_at = match.end()
    text = text[:insert_at] + "\n" + SETTINGS_FIELDS + text[insert_at:]
    path.write_text(text, encoding="utf-8")
    return True


def _patch_env_file(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if "CELERY_BROKER_URL" in text:
        return False
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + ENV_BLOCK, encoding="utf-8")
    return True


def _patch_csp(pdir: Path) -> tuple[bool, str | None]:
    """Libera a origem do Flower no frame-src do CSP do admin."""
    path = pdir / "middleware" / "csp.py"
    if not path.is_file():
        return False, None
    text = path.read_text(encoding="utf-8")
    if "frame-src" in text:
        return False, None
    if CSP_OLD_LINE not in text:
        return False, (
            "não consegui ajustar o CSP automaticamente — adicione "
            '"frame-src \'self\' <url do flower>;" no middleware/csp.py '
            "para o iframe do Flower funcionar no admin"
        )
    text = text.replace(CSP_OLD_LINE, CSP_NEW_LINES, 1)
    text = CSP_IMPORTS + text
    path.write_text(text, encoding="utf-8")
    return True, None


def _register_admin_view(pdir: Path) -> bool:
    setup_path = pdir / "admin" / "admin_setup.py"
    if not setup_path.is_file():
        return False
    content = setup_path.read_text(encoding="utf-8")
    if "admin_celery" in content:
        return False
    content += (
        "    from admin.admin_celery import FlowerAdmin\n\n"
        "    admin.add_view(FlowerAdmin)\n"
    )
    setup_path.write_text(content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# operação principal


def add_celery(
    base_dir: Path,
    pdir: Path,
    *,
    beat: bool = True,
    flower: bool = True,
    admin_view: bool = True,
    add_deps: bool = False,
    force: bool = False,
) -> dict:
    """Adiciona celery (worker/beat/flower) ao projeto e ao docker-compose."""
    project = pdir.name
    features = project_features(pdir)
    celery_path = pdir / "celery_app.py"
    if celery_path.exists() and not force:
        raise CeleryError(
            f"o projeto '{project}' já tem celery_app.py. Use --force para regenerar."
        )

    created: list[str] = []
    warnings: list[str] = []

    celery_path.write_text(render_celery_app(project, beat=beat), encoding="utf-8")
    created.append(str(celery_path))
    tasks_path = pdir / "tasks.py"
    if not tasks_path.exists() or force:
        tasks_path.write_text(render_tasks(), encoding="utf-8")
        created.append(str(tasks_path))

    if _patch_settings(pdir):
        created.append(f"{pdir / 'settings.py'} (CELERY_*/FLOWER_URL adicionados)")
    for env_name in (".env", ".env.example"):
        if _patch_env_file(base_dir / env_name):
            created.append(f"{base_dir / env_name} (bloco celery adicionado)")

    flower_admin = False
    if flower and admin_view:
        if features["admin"]:
            view_path = pdir / "admin" / "admin_celery.py"
            view_path.write_text(render_admin_flower(), encoding="utf-8")
            created.append(str(view_path))
            template_path = pdir / "templates" / "sqladmin" / "celery_flower.html"
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(FLOWER_TEMPLATE, encoding="utf-8")
            created.append(str(template_path))
            if _register_admin_view(pdir):
                created.append(f"{pdir / 'admin' / 'admin_setup.py'} (FlowerAdmin registrado)")
            patched, csp_warning = _patch_csp(pdir)
            if patched:
                created.append(f"{pdir / 'middleware' / 'csp.py'} (frame-src do Flower liberado)")
            elif csp_warning:
                warnings.append(csp_warning)
            flower_admin = True
        else:
            warnings.append(
                "o projeto não tem painel admin — o Flower fica acessível só pela porta 5555"
            )

    compose = add_celery_services(base_dir, project, beat=beat, flower=flower)
    created.append(f"{compose['file']} (serviços: {', '.join(compose['services_added'])})")
    warnings.extend(compose["warnings"])

    deps_installed = False
    if add_deps:
        run(f"uv add {CELERY_UV_PACKAGES}", cwd=base_dir, shell=True, check=False)
        deps_installed = True

    next_steps: list[str] = []
    if not deps_installed:
        next_steps.append(f"instale as dependências: uv add {CELERY_UV_PACKAGES}")
    next_steps.append("suba a stack: docker compose up -d --build")
    next_steps.append(
        "dev local: docker compose up -d redis e, a partir de src/"
        f"{project}: uv run celery -A celery_app worker --loglevel=info "
        "(no Windows adicione --pool=solo)"
    )
    if flower:
        next_steps.append(
            "flower local: uv run celery -A celery_app flower (porta 5555)"
        )
    if flower_admin:
        next_steps.append("o painel do Flower aparece no admin em /admin/celery")

    return {
        "project": project,
        "beat": beat,
        "flower": flower,
        "flower_admin": flower_admin,
        "deps_installed": deps_installed,
        "compose_services": compose["services_added"],
        "created": created,
        "warnings": warnings,
        "next_steps": next_steps,
    }

# Gerado pelo gerenciador do template. Edite via `python gerenciar.py` ou manualmente.
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
            {
                "title": "Celery — Flower",
                "subtitle": "Workers, filas e tasks em tempo real",
                "flower_url": SETTINGS.FLOWER_URL,
            },
        )

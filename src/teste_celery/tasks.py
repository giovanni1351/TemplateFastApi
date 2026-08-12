# Gerado pelo gerenciador do template. Edite via `python gerenciar.py` ou manualmente.
from celery_app import celery_app
from settings import LOGGER


@celery_app.task
def exemplo() -> str:
    """Task de exemplo — troque pelo seu processamento real."""
    LOGGER.info("task de exemplo executada")
    return "ok"

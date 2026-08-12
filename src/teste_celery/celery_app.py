# Gerado pelo gerenciador do template. Edite via `python gerenciar.py` ou manualmente.
from celery import Celery  # type: ignore[import-untyped]
from settings import SETTINGS

celery_app = Celery(
    "teste_celery",
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

# agenda do celery beat — adicione/edite entradas aqui
celery_app.conf.beat_schedule = {
    "exemplo-a-cada-5-minutos": {
        "task": "tasks.exemplo",
        "schedule": 300.0,
    },
}

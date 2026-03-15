from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "trinetra",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.pdf_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.pdf_tasks.process_pdf_task": {"queue": "pdf_processing"},
        "app.tasks.pdf_tasks.send_email_task": {"queue": "email_sending"},
    },
    task_default_queue="default",
)

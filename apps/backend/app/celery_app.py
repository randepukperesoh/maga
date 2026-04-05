import os

from celery import Celery


def _broker_url() -> str:
    return os.getenv("REDIS_URL", "redis://redis:6379/0")


celery_app = Celery(
    "rod_system_designer",
    broker=_broker_url(),
    backend=_broker_url(),
    include=["app.tasks.training"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

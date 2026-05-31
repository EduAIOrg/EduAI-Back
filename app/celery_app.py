"""Celery application configuration."""
import logging
from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "eduai",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "app.tasks.document_tasks",
        "app.tasks.quiz_tasks",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

logger.info("Celery app configured")

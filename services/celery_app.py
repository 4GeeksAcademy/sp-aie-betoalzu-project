from __future__ import annotations

import os

from celery import Celery
from dotenv import load_dotenv


load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "nexova",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["services.incident_analysis"],
)
celery_app.conf.update(
    accept_content=["json"],
    result_serializer="json",
    task_serializer="json",
    result_expires=60 * 60 * 24 * 30,
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
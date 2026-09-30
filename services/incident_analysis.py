from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from celery import Task
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlmodel import Session

from services.api.incident_analyzer import analyze_csv, build_summary
from services.celery_app import celery_app
from services.database import engine
from services.models import IncidentAnalysisDeadLetter, IncidentAnalysisTaskRecord


logger = logging.getLogger(__name__)
UPLOAD_DIR = Path(
    os.getenv(
        "INCIDENT_UPLOAD_DIR",
        str(Path(__file__).resolve().parent.parent / "data" / "incident_analysis"),
    )
)


def _upload_path(reference: str) -> Path:
    reference_path = Path(reference)
    if reference_path.name != reference or reference_path.suffix != ".csv":
        raise ValueError("Invalid incident upload reference")
    return UPLOAD_DIR / reference_path


def _remove_upload(args: tuple[Any, ...]) -> None:
    if not args:
        return
    try:
        _upload_path(str(args[0])).unlink(missing_ok=True)
    except Exception:
        logger.exception("Unable to clean incident upload reference=%s", args[0])


class IncidentAnalysisTask(Task):
    abstract = True

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        attempt_number = self.request.retries + 1
        delay_seconds = 2 ** attempt_number
        logger.warning(
            "incident_analysis task_id=%s attempt=%s status=retry delay_seconds=%s error=%s",
            task_id,
            attempt_number,
            delay_seconds,
            str(exc),
        )

    def on_success(self, retval, task_id, args, kwargs):
        _remove_upload(args)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        attempt_number = self.request.retries + 1
        try:
            with Session(engine) as session:
                if session.get(IncidentAnalysisDeadLetter, task_id) is None:
                    session.add(
                        IncidentAnalysisDeadLetter(
                            task_id=task_id,
                            attempt_number=attempt_number,
                            error_message=str(exc),
                        )
                    )
                    session.commit()
        except Exception as dlq_error:
            logger.exception(
                "incident_analysis task_id=%s attempt=%s status=dlq_write_failure "
                "original_error=%s dlq_error=%s",
                task_id,
                attempt_number,
                str(exc),
                str(dlq_error),
            )
        finally:
            _remove_upload(args)

        logger.error(
            "incident_analysis task_id=%s attempt=%s status=failure error=%s",
            task_id,
            attempt_number,
            str(exc),
            exc_info=(type(exc), exc, exc.__traceback__),
        )


@celery_app.task(
    bind=True,
    base=IncidentAnalysisTask,
    name="services.incident_analysis.analyze_incident_csv",
    autoretry_for=(OSError, OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=2,
    retry_jitter=False,
)
def analyze_incident_csv(self, file_reference: str) -> dict[str, Any]:
    started_at = time.perf_counter()
    attempt_number = self.request.retries + 1
    logger.info(
        "incident_analysis task_id=%s attempt=%s status=started",
        self.request.id,
        attempt_number,
    )

    try:
        with Session(engine) as session:
            task_record = session.get(IncidentAnalysisTaskRecord, self.request.id)
            if task_record is None:
                raise ValueError("Incident analysis task record is missing")
            summary = task_record.result_summary

        if summary is None:
            analysis = analyze_csv(_upload_path(file_reference))
            summary = build_summary(analysis)
            with Session(engine) as session:
                task_record = session.get(IncidentAnalysisTaskRecord, self.request.id)
                if task_record is None:
                    raise ValueError("Incident analysis task record is missing")
                if task_record.result_summary is None:
                    task_record.result_summary = summary
                    session.add(task_record)
                    session.commit()
                else:
                    summary = task_record.result_summary
    except Exception as error:
        duration_seconds = time.perf_counter() - started_at
        will_retry = isinstance(error, (OSError, OperationalError, InterfaceError)) and self.request.retries < 3
        logger.error(
            "incident_analysis task_id=%s attempt=%s status=%s duration_seconds=%.3f error=%s",
            self.request.id,
            attempt_number,
            "retry" if will_retry else "failure",
            duration_seconds,
            str(error),
            exc_info=True,
        )
        raise

    duration_seconds = time.perf_counter() - started_at
    logger.info(
        "incident_analysis task_id=%s attempt=%s status=success duration_seconds=%.3f",
        self.request.id,
        attempt_number,
        duration_seconds,
    )
    return summary
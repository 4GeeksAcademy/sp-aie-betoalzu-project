from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import update
from sqlmodel import Session, select

from services.database import engine
from services.models import JobRun

JOB_NAME = "nightly_export"
VALID_STATUSES = {"pending", "processing", "completed", "failed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_run(target_date: date, job_name: str = JOB_NAME, session: Session | None = None) -> JobRun:
    owns_session = session is None
    session = session or Session(engine)
    try:
        run = JobRun(job_name=job_name, target_date=target_date, status="pending")
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    finally:
        if owns_session:
            session.close()


def get_run(run_id: int, session: Session | None = None) -> JobRun | None:
    owns_session = session is None
    session = session or Session(engine)
    try:
        return session.get(JobRun, run_id)
    finally:
        if owns_session:
            session.close()


def update_run(
    run_id: int,
    status: str,
    *,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error_message: str | None = None,
    session: Session | None = None,
) -> JobRun:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid job run status: {status}")
    owns_session = session is None
    session = session or Session(engine)
    try:
        run = session.get(JobRun, run_id)
        if run is None:
            raise ValueError(f"Job run {run_id} does not exist")
        run.status = status
        run.started_at = started_at if started_at is not None else run.started_at
        run.finished_at = finished_at if finished_at is not None else run.finished_at
        run.error_message = error_message
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    finally:
        if owns_session:
            session.close()


def try_acquire_processing(run_id: int, session: Session | None = None) -> bool:
    """Atomically claim a pending run unless another real run owns the date."""
    owns_session = session is None
    session = session or Session(engine)
    try:
        run = session.get(JobRun, run_id)
        if run is None or run.status != "pending":
            return False
        other_processing = select(JobRun.id).where(
            JobRun.job_name == run.job_name,
            JobRun.target_date == run.target_date,
            JobRun.status == "processing",
            JobRun.id != run_id,
        )
        completed = select(JobRun.id).where(
            JobRun.job_name == run.job_name,
            JobRun.target_date == run.target_date,
            JobRun.status == "completed",
            JobRun.error_message.is_(None),
        )
        statement = (
            update(JobRun)
            .where(JobRun.id == run_id, JobRun.status == "pending")
            .where(~other_processing.exists(), ~completed.exists())
            .values(status="processing", started_at=_now())
        )
        result = session.exec(statement)
        try:
            session.commit()
        except Exception:
            session.rollback()
            return False
        return result.rowcount == 1
    finally:
        if owns_session:
            session.close()


def has_processing_lock(target_date: date, job_name: str = JOB_NAME, session: Session | None = None) -> bool:
    owns_session = session is None
    session = session or Session(engine)
    try:
        statement = select(JobRun.id).where(
            JobRun.job_name == job_name,
            JobRun.target_date == target_date,
            JobRun.status == "processing",
        )
        return session.exec(statement).first() is not None
    finally:
        if owns_session:
            session.close()


def has_completed_for_date(target_date: date, job_name: str = JOB_NAME, session: Session | None = None) -> bool:
    owns_session = session is None
    session = session or Session(engine)
    try:
        statement = select(JobRun.id).where(
            JobRun.job_name == job_name,
            JobRun.target_date == target_date,
            JobRun.status == "completed",
            JobRun.error_message.is_(None),
        )
        return session.exec(statement).first() is not None
    finally:
        if owns_session:
            session.close()
from __future__ import annotations

import csv
import json
import logging
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

from sqlmodel import Session, select

from services.database import engine, init_db
from services.job_runs import (
    JOB_NAME,
    create_run,
    has_completed_for_date,
    has_processing_lock,
    try_acquire_processing,
    update_run,
)
from services.models import TelemetryEventRecord

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PIPELINE_ENTRYPOINT = ROOT / "data" / "pipelines" / "pipeline.py"
CSV_COLUMNS = ("id", "timestamp", "service", "event_type", "level", "value", "message", "tags")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

logger = logging.getLogger(JOB_NAME)


def resolve_target_date(value: str | None = None) -> date:
    raw_value = value if value is not None else os.getenv("TARGET_DATE")
    if raw_value is None or raw_value == "":
        return datetime.now(timezone.utc).date() - timedelta(days=1)
    if not DATE_PATTERN.fullmatch(raw_value):
        raise ValueError("TARGET_DATE must use YYYY-MM-DD format")
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("TARGET_DATE must be a valid calendar date") from exc


def _utc_window(target_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _write_csv(rows: list[TelemetryEventRecord], output: TextIO) -> None:
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "id": str(row.id),
                "timestamp": row.timestamp.isoformat(),
                "service": row.service,
                "event_type": row.event_type,
                "level": row.level,
                "value": row.value,
                "message": row.message or "",
                "tags": json.dumps(row.tags, sort_keys=True, separators=(",", ":")),
            }
        )


def export_telemetry_csv(target_date: date, output_path: Path, session: Session) -> bool:
    """Export one UTC day, preserving an existing audit file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        return False

    start, end = _utc_window(target_date)
    rows = session.exec(
        select(TelemetryEventRecord)
        .where(TelemetryEventRecord.timestamp >= start, TelemetryEventRecord.timestamp < end)
        .order_by(TelemetryEventRecord.timestamp, TelemetryEventRecord.id)
    ).all()
    try:
        with output_path.open("x", newline="", encoding="utf-8") as output:
            _write_csv(rows, output)
    except FileExistsError:
        return False
    return True


def run_pipeline() -> None:
    subprocess.run(
        [sys.executable, str(PIPELINE_ENTRYPOINT)],
        cwd=ROOT,
        check=True,
    )


def _skip_run(run_id: int, reason: str) -> None:
    update_run(run_id, "completed", finished_at=datetime.now(timezone.utc), error_message=reason)
    logger.info("job=%s status=completed reason=%s run_id=%s", JOB_NAME, reason, run_id)


def execute(target_date: date) -> None:
    init_db()
    run = create_run(target_date)
    logger.info("job=%s status=pending target_date=%s run_id=%s", JOB_NAME, target_date, run.id)

    if not try_acquire_processing(run.id):
        if has_completed_for_date(target_date):
            _skip_run(run.id, "already_completed")
        elif has_processing_lock(target_date):
            _skip_run(run.id, "processing_lock_occupied")
        else:
            update_run(
                run.id,
                "failed",
                finished_at=datetime.now(timezone.utc),
                error_message="processing claim was not acquired",
            )
        return

    logger.info("job=%s status=processing target_date=%s run_id=%s", JOB_NAME, target_date, run.id)
    output_path = RAW_DIR / f"telemetry_{target_date.isoformat()}.csv"
    try:
        with Session(engine) as session:
            created = export_telemetry_csv(target_date, output_path, session)
        logger.info(
            "job=%s status=processing csv=%s action=%s run_id=%s",
            JOB_NAME,
            output_path,
            "created" if created else "preserved",
            run.id,
        )
        run_pipeline()
        update_run(run.id, "completed", finished_at=datetime.now(timezone.utc))
        logger.info("job=%s status=completed target_date=%s run_id=%s", JOB_NAME, target_date, run.id)
    except Exception as exc:
        message = str(exc)
        logger.error("job=%s status=failed error=%s run_id=%s", JOB_NAME, message, run.id)
        try:
            update_run(run.id, "failed", finished_at=datetime.now(timezone.utc), error_message=message)
        except Exception:
            logger.exception("job=%s status=failed persistence_error=true run_id=%s", JOB_NAME, run.id)
        raise


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    target_date = resolve_target_date()
    execute(target_date)


if __name__ == "__main__":
    main()
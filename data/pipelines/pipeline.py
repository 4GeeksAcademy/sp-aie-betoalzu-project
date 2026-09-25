from __future__ import annotations

import hashlib
import json
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from prefect import flow, task
from prefect.states import State
from sqlalchemy import text
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.database import engine
from services.models import TelemetryEventRecord

logger = logging.getLogger(__name__)
EVENT_TYPES = {
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "kit_cost_variance_detected",
}
PIPELINE_NAME = "weekly_office_program_performance"


def latest_week_start() -> date:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday()) - timedelta(days=7)


def validate_week_start(week_start: date) -> date:
    if week_start.weekday() != 0:
        raise ValueError("week_start must be the Monday of an ISO week")
    return week_start


def _table_names() -> tuple[str, str]:
    if engine.dialect.name == "postgresql":
        return ("reporting.weekly_office_program_performance", "reporting.pipeline_runs")
    return ("reporting_weekly_office_program_performance", "reporting_pipeline_runs")


def ensure_reporting_tables() -> None:
    performance_table, runs_table = _table_names()
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS reporting"))
            uuid_type = "UUID"
            json_type = "JSONB"
        else:
            uuid_type = "TEXT"
            json_type = "JSON"
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {performance_table} (
                id {uuid_type} PRIMARY KEY,
                office TEXT NOT NULL,
                programme_id TEXT NOT NULL,
                week_start DATE NOT NULL,
                total_material_cost NUMERIC NOT NULL DEFAULT 0,
                kits_delivered_count INTEGER NOT NULL DEFAULT 0,
                shortage_events_count INTEGER NOT NULL DEFAULT 0,
                cost_variance_events_count INTEGER NOT NULL DEFAULT 0,
                currency TEXT NOT NULL,
                computed_at TIMESTAMP NOT NULL,
                UNIQUE (office, programme_id, week_start)
            )
        """))
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {runs_table} (
                run_id {uuid_type} PRIMARY KEY,
                pipeline_name TEXT NOT NULL,
                status TEXT NOT NULL,
                week_start DATE NOT NULL,
                started_at TIMESTAMP NOT NULL,
                finished_at TIMESTAMP,
                records_read INTEGER NOT NULL DEFAULT 0,
                records_written INTEGER NOT NULL DEFAULT 0,
                rows_upserted INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                triggered_by TEXT NOT NULL DEFAULT 'scheduled',
                metadata {json_type} NOT NULL
            )
        """))


@task(retries=2, retry_delay_seconds=5)
def create_pipeline_run(week_start: date, trigger: str) -> str:
    """Create the audit row; two retries cover transient database disconnects."""
    ensure_reporting_tables()
    run_id = str(uuid4())
    _, runs_table = _table_names()
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(text(f"""
            INSERT INTO {runs_table}
            (run_id, pipeline_name, status, week_start, started_at, triggered_by, metadata)
            VALUES (:run_id, :pipeline_name, 'running', :week_start, :started_at, :triggered_by, :metadata)
        """), {
            "run_id": run_id, "pipeline_name": PIPELINE_NAME, "week_start": week_start,
            "started_at": now, "triggered_by": trigger, "metadata": json.dumps({"source": "telemetry_events"}),
        })
    return run_id


@task(retries=2, retry_delay_seconds=5)
def extract_business_events(week_start: date) -> list[dict[str, Any]]:
    """Read only the four business event types from telemetry_events."""
    end_date = week_start + timedelta(days=7)
    with Session(engine) as session:
        statement = select(TelemetryEventRecord).where(
            TelemetryEventRecord.event_type.in_(EVENT_TYPES),
            TelemetryEventRecord.timestamp >= datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc),
            TelemetryEventRecord.timestamp < datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        return [
            {"timestamp": event.timestamp, "event_type": event.event_type, "tags": event.tags or {}}
            for event in session.exec(statement)
        ]


def _cache_key(context: dict[str, Any], parameters: dict[str, Any]) -> str:
    payload = json.dumps(parameters["events"], default=str, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"weekly-aggregate:{digest}"


@task(cache_key_fn=_cache_key, cache_expiration=timedelta(minutes=15))
def aggregate_weekly_performance(events: list[dict[str, Any]], week_start: date) -> list[dict[str, Any]]:
    """Aggregate by office/program/week; cache key is the event payload for 15 minutes."""
    grouped: dict[tuple[str, str, date], dict[str, Any]] = defaultdict(lambda: {
        "total_material_cost": 0.0, "kits_delivered_count": 0,
        "shortage_events_count": 0, "cost_variance_events_count": 0,
    })
    for event in events:
        tags = event["tags"]
        office = str(tags.get("office", "")).lower()
        programme_id = str(tags.get("programme_id", ""))
        if not office or not programme_id:
            continue
        currency = str(tags.get("currency") or ("EUR" if office == "valencia" else "USD")).upper()
        key = (office, programme_id, week_start)
        row = grouped[key]
        existing_currency = row.get("currency")
        if existing_currency and existing_currency != currency:
            raise ValueError(f"Mixed currencies for {office}/{programme_id}")
        row["currency"] = currency
        if event["event_type"] == "inbound_order_created":
            row["total_material_cost"] += float(tags.get("unit_cost", 0)) * int(tags.get("quantity", 1))
        elif event["event_type"] == "outbound_order_created":
            row["kits_delivered_count"] += 1
        elif event["event_type"] == "stock_threshold_triggered":
            row["shortage_events_count"] += 1
        elif event["event_type"] == "kit_cost_variance_detected":
            row["cost_variance_events_count"] += 1
    return [dict(office=office, programme_id=programme, week_start=week, **values)
            for (office, programme, week), values in grouped.items()]


@task(retries=2, retry_delay_seconds=5)
def load_reporting_table(staging_rows: list[dict[str, Any]], week_start: date) -> int:
    """Replace the calculated values at the natural key, making reruns idempotent."""
    ensure_reporting_tables()
    performance_table, _ = _table_names()
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        for row in staging_rows:
            connection.execute(text(f"""
                INSERT INTO {performance_table}
                (id, office, programme_id, week_start, total_material_cost,
                 kits_delivered_count, shortage_events_count, cost_variance_events_count,
                 currency, computed_at)
                VALUES (:id, :office, :programme_id, :week_start, :total_material_cost,
                        :kits_delivered_count, :shortage_events_count, :cost_variance_events_count,
                        :currency, :computed_at)
                ON CONFLICT (office, programme_id, week_start) DO UPDATE SET
                    total_material_cost = excluded.total_material_cost,
                    kits_delivered_count = excluded.kits_delivered_count,
                    shortage_events_count = excluded.shortage_events_count,
                    cost_variance_events_count = excluded.cost_variance_events_count,
                    currency = excluded.currency,
                    computed_at = excluded.computed_at
            """), {**row, "id": str(uuid4()), "computed_at": now})
    return len(staging_rows)


@task
def export_eval_snapshot(staging_rows: list[dict[str, Any]], week_start: date) -> None:
    """Optional secondary output; its failure must not block the reporting table."""
    output_dir = ROOT / "data" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"weekly_{week_start.isoformat()}.json").write_text(
        json.dumps(staging_rows, default=str, indent=2), encoding="utf-8"
    )


@task(retries=2, retry_delay_seconds=5)
def record_run_status(run_id: str, status: str, records_read: int, rows_written: int, error_message: str | None = None) -> None:
    _, runs_table = _table_names()
    with engine.begin() as connection:
        connection.execute(text(f"""
            UPDATE {runs_table}
            SET status = :status, finished_at = :finished_at, records_read = :records_read,
                records_written = :records_written, rows_upserted = :rows_written,
                error_message = :error_message
            WHERE run_id = :run_id
        """), {"run_id": run_id, "status": status, "finished_at": datetime.now(timezone.utc),
               "records_read": records_read, "records_written": rows_written,
               "rows_written": rows_written, "error_message": error_message})


@flow(name=PIPELINE_NAME)
def weekly_office_program_performance_flow(week_start: date | None = None, trigger: str = "scheduled") -> dict[str, Any]:
    target_week = validate_week_start(week_start or latest_week_start())
    run_id = create_pipeline_run(target_week, trigger)
    events: list[dict[str, Any]] = []
    try:
        events = extract_business_events(target_week)
        rows = aggregate_weekly_performance(events, target_week)
        rows_written = load_reporting_table(rows, target_week)
        optional_state: State = export_eval_snapshot(rows, target_week, return_state=True)
        if optional_state.is_failed():
            logger.warning("Optional eval snapshot failed: %s", optional_state.message)
        record_run_status(run_id, "completed", len(events), rows_written)
        return {"run_id": run_id, "status": "completed", "records_read": len(events), "rows_upserted": rows_written}
    except Exception as exc:
        record_run_status(run_id, "failed", len(events), 0, str(exc))
        raise


def get_weekly_office_program_performance(week_start: date) -> list[dict[str, Any]]:
    ensure_reporting_tables()
    performance_table, _ = _table_names()
    with engine.begin() as connection:
        result = connection.execute(text(f"""
            SELECT office, programme_id, total_material_cost, kits_delivered_count,
                   shortage_events_count, cost_variance_events_count, currency
            FROM {performance_table} WHERE week_start = :week_start
            ORDER BY office, programme_id
        """), {"week_start": week_start})
        return [dict(row._mapping) for row in result]


def get_latest_pipeline_run() -> dict[str, Any] | None:
    ensure_reporting_tables()
    _, runs_table = _table_names()
    with engine.begin() as connection:
        result = connection.execute(text(f"SELECT * FROM {runs_table} ORDER BY started_at DESC LIMIT 1"))
        row = result.first()
        if row is None:
            return None
        value = dict(row._mapping)
        if isinstance(value.get("metadata"), str):
            value["metadata"] = json.loads(value["metadata"])
        return value


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    weekly_office_program_performance_flow()

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from sqlmodel import Session, select

from services.database import engine
from services.models import TelemetryEventRecord


def _fetch_events(
    start_date: str,
    end_date: str,
    event_types: list[str] | None = None,
    session: Session | None = None,
) -> pd.DataFrame:
    """Load telemetry rows in a time window, filtered in SQL when possible."""
    needs_close = session is None
    session = session or Session(engine)
    try:
        start_dt = pd.to_datetime(start_date, utc=True).to_pydatetime()
        end_dt = pd.to_datetime(end_date, utc=True).to_pydatetime()
        stmt = select(TelemetryEventRecord).where(
            TelemetryEventRecord.timestamp >= start_dt,
            TelemetryEventRecord.timestamp < end_dt,
        )
        if event_types:
            stmt = stmt.where(TelemetryEventRecord.event_type.in_(event_types))
        rows = session.exec(stmt).all()
    finally:
        if needs_close:
            session.close()

    if not rows:
        return pd.DataFrame(columns=["timestamp", "event_type", "level", "tags", "value"])

    df = pd.DataFrame([
        {
            "timestamp": row.timestamp,
            "event_type": row.event_type,
            "level": row.level,
            "tags": row.tags or {},
            "value": row.value,
        }
        for row in rows
    ])
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def events_per_day(start_date: str, end_date: str, session: Session | None = None) -> list[dict[str, Any]]:
    """Count events per day for the given time window."""
    df = _fetch_events(start_date, end_date, session=session)
    if df.empty:
        return []

    df["date"] = df["timestamp"].dt.date.astype(str)
    result = (
        df.groupby("date", as_index=False)["event_type"]
        .count()
        .rename(columns={"event_type": "count"})
        .sort_values("date")
    )
    result = result.rename(columns={"count": "count"})
    return result.to_dict(orient="records")


def error_rate_by_type(start_date: str, end_date: str, session: Session | None = None) -> list[dict[str, Any]]:
    """Compute error counts for the main technical event types."""
    df = _fetch_events(
        start_date,
        end_date,
        event_types=["login_failed", "user_login_failed", "api_error_returned", "frontend_error_captured"],
        session=session,
    )
    if df.empty:
        return []

    df["date"] = df["timestamp"].dt.date.astype(str)
    result = (
        df.groupby(["date", "event_type"], as_index=False)
        .size()
        .rename(columns={"size": "error_count"})
        .sort_values(["date", "event_type"])
    )
    return result.to_dict(orient="records")


def latency_by_day(start_date: str, end_date: str, session: Session | None = None) -> list[dict[str, Any]]:
    """Compute average latency in milliseconds by day."""
    df = _fetch_events(start_date, end_date, event_types=["api_latency_recorded", "page_load_timed"], session=session)
    if df.empty:
        return []

    df["latency_ms"] = pd.to_numeric(
        df["tags"].apply(lambda tags: tags.get("latency_ms") if isinstance(tags, dict) else None),
        errors="coerce",
    )
    df = df.dropna(subset=["latency_ms"])
    if df.empty:
        return []

    df["date"] = df["timestamp"].dt.date.astype(str)
    result = (
        df.groupby("date", as_index=False)["latency_ms"]
        .mean()
        .rename(columns={"latency_ms": "avg_latency_ms"})
        .sort_values("date")
    )
    return result.to_dict(orient="records")


def auth_failure_rate(start_date: str, end_date: str, session: Session | None = None) -> list[dict[str, Any]]:
    """Compute daily login failure ratio for user authentication events."""
    df = _fetch_events(start_date, end_date, event_types=["user_login_failed", "user_login_succeeded"], session=session)
    if df.empty:
        return []

    df["date"] = df["timestamp"].dt.date.astype(str)
    totals = (
        df.groupby(["date", "event_type"], as_index=False)
        .size()
        .pivot(index="date", columns="event_type", values="size")
        .fillna(0)
    ).reset_index()
    totals["failure_rate"] = 0.0
    failed = totals["user_login_failed"] if "user_login_failed" in totals.columns else 0
    succeeded = totals["user_login_succeeded"] if "user_login_succeeded" in totals.columns else 0
    totals["failure_rate"] = (
        failed / (failed + succeeded)
    ).replace([float("inf"), float("nan")], 0.0)
    return totals[["date", "failure_rate"]].to_dict(orient="records")


def build_operational_report(start_date: str, end_date: str, session: Session | None = None) -> dict[str, list[dict[str, Any]]]:
    """Build the technical dashboard payload."""
    return {
        "events_per_day": events_per_day(start_date, end_date, session=session),
        "error_rate_by_type": error_rate_by_type(start_date, end_date, session=session),
        "latency_by_day": latency_by_day(start_date, end_date, session=session),
        "auth_failure_rate": auth_failure_rate(start_date, end_date, session=session),
    }


def default_window() -> tuple[str, str]:
    """Return UTC start/end for the last 7 days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")

from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine, select

from services import job_runs
from services.models import JobRun, TelemetryEventRecord
from scripts import nightly_export


@pytest.fixture()
def test_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_engine = create_engine(f"sqlite:///{tmp_path / 'nightly.db'}", poolclass=NullPool)
    SQLModel.metadata.create_all(database_engine)
    monkeypatch.setattr(job_runs, "engine", database_engine)
    monkeypatch.setattr(nightly_export, "engine", database_engine)
    return database_engine


def test_resolve_target_date(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARGET_DATE", "2026-09-28")
    assert nightly_export.resolve_target_date() == date(2026, 9, 28)
    assert nightly_export.resolve_target_date("2026-09-27") == date(2026, 9, 27)
    with pytest.raises(ValueError):
        nightly_export.resolve_target_date("2026-9-28")


def test_resolve_target_date_defaults_to_previous_utc_day(monkeypatch: pytest.MonkeyPatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 29, 0, 5, tzinfo=tz)

    monkeypatch.delenv("TARGET_DATE", raising=False)
    monkeypatch.setattr(nightly_export, "datetime", FixedDateTime)
    assert nightly_export.resolve_target_date() == date(2026, 9, 28)


def test_export_filters_utc_window_and_preserves_existing_file(test_engine, tmp_path: Path):
    with Session(test_engine) as session:
        session.add_all(
            [
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="first",
                    tags={"b": 2, "a": 1},
                ),
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="outside",
                    tags={},
                ),
            ]
        )
        session.commit()
        output_path = tmp_path / "telemetry.csv"
        assert nightly_export.export_telemetry_csv(date(2026, 9, 28), output_path, session) is True

    with output_path.open(newline="", encoding="utf-8") as output:
        rows = list(csv.DictReader(output))
    assert [row["event_type"] for row in rows] == ["first"]
    assert rows[0]["tags"] == '{"a":1,"b":2}'
    output_path.write_text("keep", encoding="utf-8")
    with Session(test_engine) as session:
        assert nightly_export.export_telemetry_csv(date(2026, 9, 28), output_path, session) is False
    assert output_path.read_text(encoding="utf-8") == "keep"


def test_run_pipeline_uses_current_interpreter_and_checks_exit(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(nightly_export.subprocess, "run", fake_run)
    nightly_export.run_pipeline()
    assert calls == [
        ([nightly_export.sys.executable, str(nightly_export.PIPELINE_ENTRYPOINT)], {"cwd": nightly_export.ROOT, "check": True})
    ]


def test_execute_completes_and_records_failure(test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(nightly_export, "init_db", lambda: None)
    monkeypatch.setattr(nightly_export, "RAW_DIR", tmp_path)
    monkeypatch.setattr(nightly_export, "run_pipeline", lambda: None)
    target = date(2026, 9, 28)
    nightly_export.execute(target)
    with Session(test_engine) as session:
        completed = session.exec(select(JobRun)).all()
    assert [(run.status, run.error_message) for run in completed] == [("completed", None)]

    monkeypatch.setattr(nightly_export, "run_pipeline", lambda: (_ for _ in ()).throw(RuntimeError("pipeline failed")))
    with pytest.raises(RuntimeError, match="pipeline failed"):
        nightly_export.execute(date(2026, 9, 27))
    with Session(test_engine) as session:
        failed = session.exec(select(JobRun).where(JobRun.target_date == date(2026, 9, 27))).one()
    assert failed.status == "failed"
    assert failed.error_message == "pipeline failed"


def test_completed_and_processing_invocations_are_noops(test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(nightly_export, "init_db", lambda: None)
    monkeypatch.setattr(nightly_export, "RAW_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(nightly_export, "run_pipeline", lambda: calls.append(True))
    target = date(2026, 9, 28)
    nightly_export.execute(target)
    nightly_export.execute(target)
    assert calls == [True]

    locked = job_runs.create_run(date(2026, 9, 27))
    assert job_runs.try_acquire_processing(locked.id)
    nightly_export.execute(date(2026, 9, 27))
    assert calls == [True]


def test_only_one_concurrent_processing_lock_is_acquired(test_engine):
    first = job_runs.create_run(date(2026, 9, 28))
    second = job_runs.create_run(date(2026, 9, 28))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(job_runs.try_acquire_processing, [first.id, second.id]))
    assert sum(results) == 1
    with Session(test_engine) as session:
        processing = session.exec(
            select(JobRun).where(JobRun.target_date == date(2026, 9, 28), JobRun.status == "processing")
        ).all()
    assert len(processing) == 1
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from data.pipelines.pipeline import (
    get_latest_pipeline_run,
    get_weekly_office_program_performance,
    latest_week_start,
    weekly_office_program_performance_flow,
)
from services.api.users.auth import get_admin_user, get_current_user

reporting_api = APIRouter(prefix="/reporting", tags=["reporting"])


@reporting_api.get("/weekly-office-program-performance")
def weekly_performance(week_start: date | None = Query(default=None), _: object = Depends(get_current_user)):
    target_week = week_start or latest_week_start()
    if target_week.weekday() != 0:
        raise HTTPException(status_code=400, detail="week_start must be a Monday")
    return {"week_start": target_week.isoformat(), "entries": get_weekly_office_program_performance(target_week)}


@reporting_api.get("/pipeline-runs/latest")
def latest_run(_: object = Depends(get_current_user)):
    return get_latest_pipeline_run() or {"status": "never_run"}


@reporting_api.post("/pipeline-runs", status_code=202)
def trigger_pipeline(week_start: date | None = Query(default=None), _: object = Depends(get_admin_user)):
    target_week = week_start or latest_week_start()
    try:
        return weekly_office_program_performance_flow(target_week, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

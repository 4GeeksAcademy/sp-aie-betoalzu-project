from __future__ import annotations

import codecs
import logging
import time
from pathlib import Path
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlmodel import Session

from services.api.incident_analyzer import (
    EmptyFileError,
    InvalidCsvFormatError,
    build_metrics_csv,
    validate_csv_file,
)
from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB
from services.celery_app import celery_app
from services.database import engine
from services.incident_analysis import UPLOAD_DIR
from services.models import IncidentAnalysisTaskRecord


incidents_api = APIRouter()
logger = logging.getLogger(__name__)


def _json_error(message: str, status_code: int):
    return JSONResponse(content={"error": message}, status_code=status_code)


def _remove_upload_file(file_path: Path) -> None:
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        logger.exception("incident_analysis upload cleanup failed reference=%s", file_path.name)


@incidents_api.post("/api/incidents/analyze", status_code=202)
async def analyze_incidents(file: UploadFile | None = File(default=None), current_user: UserInDB = Depends(get_current_user)):
    queued_at = time.perf_counter()

    if file is None:
        return _json_error("Debe enviarse un fichero CSV en el campo 'file'.", 400)

    if not file.filename:
        return _json_error("Debe seleccionarse un fichero CSV.", 400)

    if not file.filename.lower().endswith(".csv"):
        return _json_error("El fichero debe tener extension .csv.", 415)

    task_id = str(uuid4())
    file_reference = f"{uuid4().hex}.csv"
    file_path = UPLOAD_DIR / file_reference
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    has_non_whitespace = False
    byte_count = 0
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with file_path.open("xb") as stored_file:
            while chunk := await file.read(1024 * 1024):
                byte_count += len(chunk)
                has_non_whitespace = has_non_whitespace or bool(decoder.decode(chunk).strip())
                stored_file.write(chunk)
            has_non_whitespace = has_non_whitespace or bool(decoder.decode(b"", final=True).strip())

        if byte_count == 0 or not has_non_whitespace:
            _remove_upload_file(file_path)
            return _json_error("El fichero CSV esta vacio.", 400)

        validate_csv_file(file_path)
    except EmptyFileError as error:
        _remove_upload_file(file_path)
        return _json_error(str(error), 400)
    except InvalidCsvFormatError as error:
        _remove_upload_file(file_path)
        return _json_error(str(error), 422)
    except UnicodeDecodeError:
        _remove_upload_file(file_path)
        return _json_error("El fichero debe estar codificado en UTF-8.", 415)
    except OSError:
        _remove_upload_file(file_path)
        logger.exception("incident_analysis upload persistence failed")
        return _json_error("No fue posible guardar el fichero para su analisis.", 503)

    try:
        with Session(engine) as session:
            session.add(
                IncidentAnalysisTaskRecord(
                    task_id=task_id,
                    owner_id=current_user.id,
                    source_filename=Path(file.filename).name[:255],
                )
            )
            session.commit()

        celery_app.send_task(
            "services.incident_analysis.analyze_incident_csv",
            args=[file_reference],
            task_id=task_id,
        )
    except Exception:
        logger.exception("incident_analysis task_id=%s status=enqueue_failure", task_id)
        _remove_upload_file(file_path)
        try:
            with Session(engine) as session:
                task_record = session.get(IncidentAnalysisTaskRecord, task_id)
                if task_record is not None:
                    session.delete(task_record)
                    session.commit()
        except Exception:
            logger.exception("incident_analysis task_id=%s owner_record_cleanup_failure", task_id)
        return _json_error("No fue posible encolar el analisis.", 503)
    finally:
        await file.close()

    duration_ms = (time.perf_counter() - queued_at) * 1000
    logger.info(
        "incident_analysis task_id=%s attempt=0 status=pending queue_duration_ms=%.3f",
        task_id,
        duration_ms,
    )
    return {"task_id": task_id}


def _owned_task_record(task_id: str, current_user: UserInDB) -> IncidentAnalysisTaskRecord | None:
    with Session(engine) as session:
        record = session.get(IncidentAnalysisTaskRecord, task_id)
        if record is None or record.owner_id != current_user.id:
            return None
        return record


def _task_status(task_id: str) -> tuple[str, object | None]:
    task_result = AsyncResult(task_id, app=celery_app)
    state = task_result.state
    if state == "SUCCESS":
        return "success", task_result.result
    if state == "FAILURE":
        return "failure", {"error": "No se pudo completar el analisis."}
    if state == "STARTED":
        return "started", None
    return "pending", None


@incidents_api.get("/tasks/{task_id}")
async def get_incident_analysis_task(task_id: str, current_user: UserInDB = Depends(get_current_user)):
    if _owned_task_record(task_id, current_user) is None:
        return _json_error("La tarea no existe.", 404)
    try:
        task_status, result = _task_status(task_id)
    except Exception:
        logger.exception("incident_analysis task_id=%s status=query_failure", task_id)
        return _json_error("No se pudo consultar el estado de la tarea.", 503)
    return {"task_id": task_id, "status": task_status, "result": result}


@incidents_api.get("/api/incidents/results/export")
async def export_incident_results(task_id: str = Query(...), current_user: UserInDB = Depends(get_current_user)):
    task_record = _owned_task_record(task_id, current_user)
    if task_record is None:
        return _json_error("La tarea no existe.", 404)
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        if task_result.state not in {"SUCCESS", "FAILURE"}:
            return _json_error("El analisis aun no ha terminado.", 409)
        if task_result.state == "FAILURE":
            return _json_error("No se pudo exportar un analisis fallido.", 422)
        summary = task_result.result
    except Exception:
        logger.exception("incident_analysis task_id=%s status=export_query_failure", task_id)
        return _json_error("No se pudo consultar el resultado de la tarea.", 503)

    file_stem = Path(task_record.source_filename).stem.replace('"', "").replace("\r", "").replace("\n", "")
    file_name = file_stem + "-metrics.csv"
    return Response(
        build_metrics_csv(summary),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
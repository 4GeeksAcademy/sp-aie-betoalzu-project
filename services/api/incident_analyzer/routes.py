from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response

from services.api.incident_analyzer import (
    AnalysisResult,
    EmptyFileError,
    InvalidCsvFormatError,
    analyze_csv_stream,
    build_metrics_csv,
    build_summary,
)
from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB


incidents_api = APIRouter()
_last_analysis: AnalysisResult | None = None


def _json_error(message: str, status_code: int):
    return JSONResponse(content={"error": message}, status_code=status_code)


@incidents_api.post("/api/incidents/analyze")
async def analyze_incidents(file: UploadFile | None = File(default=None), current_user: UserInDB = Depends(get_current_user)):
    global _last_analysis

    if file is None:
        return _json_error("Debe enviarse un fichero CSV en el campo 'file'.", 400)

    if not file.filename:
        return _json_error("Debe seleccionarse un fichero CSV.", 400)

    if not file.filename.lower().endswith(".csv"):
        return _json_error("El fichero debe tener extension .csv.", 415)

    payload = await file.read()
    if not payload:
        return _json_error("El fichero CSV esta vacio.", 400)

    try:
        text_stream = io.StringIO(payload.decode("utf-8-sig"))
    except UnicodeDecodeError:
        return _json_error("El fichero debe estar codificado en UTF-8.", 415)

    try:
        _last_analysis = analyze_csv_stream(text_stream, file.filename)
    except EmptyFileError as error:
        return _json_error(str(error), 400)
    except InvalidCsvFormatError as error:
        return _json_error(str(error), 422)

    return build_summary(_last_analysis)


@incidents_api.get("/api/incidents/results/export")
async def export_incident_results(current_user: UserInDB = Depends(get_current_user)):
    global _last_analysis
    if _last_analysis is None:
        return _json_error("No hay analisis previo para exportar.", 404)

    file_name = _last_analysis.source_file.rsplit(".", 1)[0] + "-metrics.csv"
    return Response(
        build_metrics_csv(_last_analysis),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
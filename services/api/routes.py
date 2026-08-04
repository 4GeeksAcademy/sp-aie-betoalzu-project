from __future__ import annotations

import io

from flask import Blueprint, Response, jsonify, request

from services.api.analyzer import (
    AnalysisResult,
    EmptyFileError,
    InvalidCsvFormatError,
    analyze_csv_stream,
    build_metrics_csv,
    build_summary,
)


incidents_api = Blueprint("incidents_api", __name__)
_last_analysis: AnalysisResult | None = None


def _json_error(message: str, status_code: int):
    response = jsonify({"error": message})
    response.status_code = status_code
    return response


@incidents_api.post("/api/incidents/analyze")
def analyze_incidents():
    global _last_analysis

    upload = request.files.get("file")
    if upload is None:
        return _json_error("Debe enviarse un fichero CSV en el campo 'file'.", 400)

    if not upload.filename:
        return _json_error("Debe seleccionarse un fichero CSV.", 400)

    if not upload.filename.lower().endswith(".csv"):
        return _json_error("El fichero debe tener extension .csv.", 415)

    payload = upload.stream.read()
    if not payload:
        return _json_error("El fichero CSV esta vacio.", 400)

    try:
        text_stream = io.StringIO(payload.decode("utf-8-sig"))
    except UnicodeDecodeError:
        return _json_error("El fichero debe estar codificado en UTF-8.", 415)

    try:
        _last_analysis = analyze_csv_stream(text_stream, upload.filename)
    except EmptyFileError as error:
        return _json_error(str(error), 400)
    except InvalidCsvFormatError as error:
        return _json_error(str(error), 422)

    return jsonify(build_summary(_last_analysis))


@incidents_api.get("/api/incidents/results/export")
def export_incident_results():
    if _last_analysis is None:
        return _json_error("No hay analisis previo para exportar.", 404)

    file_name = _last_analysis.source_file.rsplit(".", 1)[0] + "-metrics.csv"
    return Response(
        build_metrics_csv(_last_analysis),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
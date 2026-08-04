from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from tinydb import TinyDB

from services.api.analyzer import (
    AnalysisResult,
    EmptyFileError,
    InvalidCsvFormatError,
    analyze_csv_stream,
    build_metrics_csv,
    build_summary,
)
from services.api.suppliers import Country, Supplier, SupplierCategory, SupplierCreate, SupplierStatus, SupplierUpdate


incidents_api = APIRouter()
_last_analysis: AnalysisResult | None = None
_ROOT_DIR = Path(__file__).resolve().parents[2]
_SUPPLIERS_DB_PATH = _ROOT_DIR / "scripts" / "suppliers_db.json"


class SupplierRateUpdate(BaseModel):
    monthly_rate: float = Field(gt=0)


class SupplierStatusUpdate(BaseModel):
    status: SupplierStatus


def _json_error(message: str, status_code: int):
    return JSONResponse(content={"error": message}, status_code=status_code)


def _serialize_supplier(document) -> dict:
    supplier_payload = dict(document)
    validated = Supplier.model_validate(supplier_payload)
    serialized = validated.model_dump(mode="json")
    serialized["id"] = document.doc_id
    return serialized


def _open_suppliers_table():
    db = TinyDB(_SUPPLIERS_DB_PATH)
    return db, db.table("suppliers")


@incidents_api.post("/api/incidents/analyze")
async def analyze_incidents(file: UploadFile | None = File(default=None)):
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
async def export_incident_results():
    if _last_analysis is None:
        return _json_error("No hay analisis previo para exportar.", 404)

    file_name = _last_analysis.source_file.rsplit(".", 1)[0] + "-metrics.csv"
    return Response(
        build_metrics_csv(_last_analysis),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@incidents_api.post("/suppliers", status_code=201)
def create_supplier(supplier: SupplierCreate):
    db, table = _open_suppliers_table()
    try:
        supplier_data = supplier.model_dump(mode="json")
        supplier_id = table.insert(supplier_data)
        created_supplier = table.get(doc_id=supplier_id)
        return _serialize_supplier(created_supplier)
    finally:
        db.close()


@incidents_api.get("/suppliers")
def list_suppliers(
    country: Country | None = Query(default=None),
    category: SupplierCategory | None = Query(default=None),
):
    db, table = _open_suppliers_table()
    try:
        results: list[dict] = []
        for document in table.all():
            if country is not None and document.get("country") != country.value:
                continue

            if category is not None:
                categories = document.get("categories", [])
                if category.value not in categories:
                    continue

            results.append(_serialize_supplier(document))

        return results
    finally:
        db.close()


@incidents_api.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int):
    db, table = _open_suppliers_table()
    try:
        supplier = table.get(doc_id=supplier_id)
        if supplier is None:
            return _json_error("Proveedor no encontrado.", 404)

        return _serialize_supplier(supplier)
    finally:
        db.close()


@incidents_api.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierUpdate):
    db, table = _open_suppliers_table()
    try:
        supplier = table.get(doc_id=supplier_id)
        if supplier is None:
            return _json_error("Proveedor no encontrado.", 404)

        update_payload = payload.model_dump(exclude_unset=True, mode="json")
        if not update_payload:
            return _json_error("Debe enviarse al menos un campo para actualizar.", 400)

        merged_supplier = {
            **supplier,
            **update_payload,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        validated = Supplier.model_validate(merged_supplier)
        table.update(validated.model_dump(mode="json"), doc_ids=[supplier_id])

        updated_supplier = table.get(doc_id=supplier_id)
        return _serialize_supplier(updated_supplier)
    finally:
        db.close()


@incidents_api.patch("/suppliers/{supplier_id}/rate")
def update_supplier_rate(supplier_id: int, payload: SupplierRateUpdate):
    db, table = _open_suppliers_table()
    try:
        supplier = table.get(doc_id=supplier_id)
        if supplier is None:
            return _json_error("Proveedor no encontrado.", 404)

        table.update(
            {
                "monthly_rate": payload.monthly_rate,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            doc_ids=[supplier_id],
        )

        updated_supplier = table.get(doc_id=supplier_id)
        return _serialize_supplier(updated_supplier)
    finally:
        db.close()


@incidents_api.patch("/suppliers/{supplier_id}/status")
def update_supplier_status(supplier_id: int, payload: SupplierStatusUpdate):
    db, table = _open_suppliers_table()
    try:
        supplier = table.get(doc_id=supplier_id)
        if supplier is None:
            return _json_error("Proveedor no encontrado.", 404)

        table.update(
            {
                "status": payload.status.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            doc_ids=[supplier_id],
        )

        updated_supplier = table.get(doc_id=supplier_id)
        return _serialize_supplier(updated_supplier)
    finally:
        db.close()


@incidents_api.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int):
    db, table = _open_suppliers_table()
    try:
        supplier = table.get(doc_id=supplier_id)
        if supplier is None:
            return _json_error("Proveedor no encontrado.", 404)

        table.remove(doc_ids=[supplier_id])
        return {"id": supplier_id, "deleted": True}
    finally:
        db.close()
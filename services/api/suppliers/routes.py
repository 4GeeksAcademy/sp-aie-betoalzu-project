from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from tinydb import TinyDB

from services.api.suppliers import Country, Supplier, SupplierCategory, SupplierCreate, SupplierStatus, SupplierUpdate
from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB


suppliers_api = APIRouter()
_ROOT_DIR = Path(__file__).resolve().parents[3]
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


@suppliers_api.post("/suppliers", status_code=201)
def create_supplier(supplier: SupplierCreate, current_user: UserInDB = Depends(get_current_user)):
    db, table = _open_suppliers_table()
    try:
        supplier_data = supplier.model_dump(mode="json")
        supplier_id = table.insert(supplier_data)
        created_supplier = table.get(doc_id=supplier_id)
        return _serialize_supplier(created_supplier)
    finally:
        db.close()


@suppliers_api.get("/suppliers")
def list_suppliers(
    country: Country | None = Query(default=None),
    category: SupplierCategory | None = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
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


@suppliers_api.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int, current_user: UserInDB = Depends(get_current_user)):
    db, table = _open_suppliers_table()
    try:
        supplier = table.get(doc_id=supplier_id)
        if supplier is None:
            return _json_error("Proveedor no encontrado.", 404)

        return _serialize_supplier(supplier)
    finally:
        db.close()


@suppliers_api.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierUpdate, current_user: UserInDB = Depends(get_current_user)):
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


@suppliers_api.patch("/suppliers/{supplier_id}/rate")
def update_supplier_rate(supplier_id: int, payload: SupplierRateUpdate, current_user: UserInDB = Depends(get_current_user)):
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


@suppliers_api.patch("/suppliers/{supplier_id}/status")
def update_supplier_status(supplier_id: int, payload: SupplierStatusUpdate, current_user: UserInDB = Depends(get_current_user)):
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


@suppliers_api.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int, current_user: UserInDB = Depends(get_current_user)):
    db, table = _open_suppliers_table()
    try:
        supplier = table.get(doc_id=supplier_id)
        if supplier is None:
            return _json_error("Proveedor no encontrado.", 404)

        table.remove(doc_ids=[supplier_id])
        return {"id": supplier_id, "deleted": True}
    finally:
        db.close()
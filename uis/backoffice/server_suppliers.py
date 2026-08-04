"""Servidor de proveedores — lee/escribe directamente JSON (sin TinyDB).

El archivo scripts/suppliers_db.json tiene formato:
  {"suppliers": {"1": {...datos...}, "2": {...datos...}, ...}}
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


_ROOT_DIR = Path(__file__).resolve().parents[2]
_SUPPLIERS_DB_PATH = _ROOT_DIR / "scripts" / "suppliers_db.json"


# ── Enums ────────────────────────────────────────────────────────────────

class Country(str, Enum):
    SPAIN = "Spain"
    USA = "USA"

class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"

class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"

class SupplierCategory(str, Enum):
    JOB_BOARDS = "job_boards"
    ATS_SOFTWARE = "ats_software"
    ASSESSMENT_TOOLS = "assessment_tools"
    TRAINING_PLATFORMS = "training_platforms"
    PAYROLL_AND_HR_SOFTWARE = "payroll_and_hr_software"
    VIDEO_INTERVIEW = "video_interview"
    BACKGROUND_CHECK = "background_check"
    OFFICE_AND_FACILITIES = "office_and_facilities"
    IT_AND_SOFTWARE_LICENSES = "it_and_software_licenses"


# ── Helpers ──────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _check_currency(country: Country, currency: Currency) -> None:
    expected = Currency.EUR if country == Country.SPAIN else Currency.USD
    if currency != expected:
        raise ValueError(f"{country.value} requiere moneda {expected.value}")


# ── Modelos Pydantic ─────────────────────────────────────────────────────

class SupplierBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1)
    country: Country
    categories: list[SupplierCategory] = Field(min_length=1)
    monthly_rate: float = Field(gt=0)
    currency: Currency
    status: SupplierStatus
    contract_renewal_date: date | None = None
    contact_email: EmailStr | None = None
    notes: str | None = None

    @field_validator("categories")
    @classmethod
    def no_dupes(cls, v):
        if len(v) != len(set(v)):
            raise ValueError("categorías duplicadas")
        return v

    @model_validator(mode="after")
    def currency_check(self):
        _check_currency(self.country, self.currency)
        return self

class SupplierCreate(SupplierBase):
    updated_at: str = Field(default_factory=_utc_now)

class SupplierUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1)
    country: Country | None = None
    categories: list[SupplierCategory] | None = Field(default=None, min_length=1)
    monthly_rate: float | None = Field(default=None, gt=0)
    currency: Currency | None = None
    status: SupplierStatus | None = None
    contract_renewal_date: date | None = None
    contact_email: EmailStr | None = None
    notes: str | None = None

    @field_validator("categories")
    @classmethod
    def no_dupes(cls, v):
        if v is not None and len(v) != len(set(v)):
            raise ValueError("categorías duplicadas")
        return v

    @model_validator(mode="after")
    def currency_check(self):
        if self.country is not None and self.currency is not None:
            _check_currency(self.country, self.currency)
        return self

class Supplier(SupplierBase):
    updated_at: str = Field(default_factory=_utc_now)


# ── Persistencia directa en JSON ─────────────────────────────────────────

def _read_dict() -> dict[str, dict[str, Any]]:
    """Retorna {id_str: data_dict} desde el archivo JSON."""
    try:
        raw = json.loads(_SUPPLIERS_DB_PATH.read_bytes())
    except Exception:
        return {}
    suppliers = raw.get("suppliers", {})
    return suppliers if isinstance(suppliers, dict) else {}

def _write_dict(data: dict[str, dict[str, Any]]) -> None:
    _SUPPLIERS_DB_PATH.write_text(
        json.dumps({"suppliers": data}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def _validate_dict(d: dict) -> dict:
    """Valida con Pydantic y retorna dump en JSON."""
    validated = Supplier.model_validate(d)
    return validated.model_dump(mode="json")

def _serialize(id_str: str, d: dict) -> dict:
    """Retorna el dict listo para respuesta API, con `id` numérico."""
    v = _validate_dict(d)
    return {"id": int(id_str), **v}

def _next_id(data: dict[str, dict]) -> str:
    if not data:
        return "1"
    return str(max(int(k) for k in data) + 1)

def _json_error(msg: str, code: int):
    return JSONResponse(content={"error": msg}, status_code=code)


# ── FastAPI app ──────────────────────────────────────────────────────────

app = FastAPI(title="Suppliers API")


@app.post("/suppliers", status_code=201)
def create_supplier(supplier: SupplierCreate):
    data = _read_dict()
    sid = _next_id(data)
    d = supplier.model_dump(mode="json")
    data[sid] = d
    _write_dict(data)
    return _serialize(sid, d)


@app.get("/suppliers")
def list_suppliers(country: Country | None = Query(None), category: SupplierCategory | None = Query(None)):
    data = _read_dict()
    results = []
    for sid, d in data.items():
        if country is not None and d.get("country") != country.value:
            continue
        if category is not None:
            cats = d.get("categories", [])
            if category.value not in cats:
                continue
        results.append(_serialize(sid, d))
    return results


@app.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int):
    data = _read_dict()
    sid = str(supplier_id)
    d = data.get(sid)
    if d is None:
        return _json_error("Proveedor no encontrado.", 404)
    return _serialize(sid, d)


@app.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierUpdate):
    data = _read_dict()
    sid = str(supplier_id)
    d = data.get(sid)
    if d is None:
        return _json_error("Proveedor no encontrado.", 404)
    update = payload.model_dump(exclude_unset=True, mode="json")
    if not update:
        return _json_error("Debe enviarse al menos un campo.", 400)
    merged = {**d, **update, "updated_at": _utc_now()}
    _validate_dict(merged)  # valida antes de guardar
    data[sid] = merged
    _write_dict(data)
    return _serialize(sid, merged)


@app.patch("/suppliers/{supplier_id}/status")
def update_supplier_status(supplier_id: int, payload: dict):
    data = _read_dict()
    sid = str(supplier_id)
    d = data.get(sid)
    if d is None:
        return _json_error("Proveedor no encontrado.", 404)
    status = payload.get("status")
    if status not in ("active", "suspended"):
        return _json_error("Status debe ser 'active' o 'suspended'.", 422)
    d["status"] = status
    d["updated_at"] = _utc_now()
    _write_dict(data)
    return _serialize(sid, d)


@app.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int):
    data = _read_dict()
    sid = str(supplier_id)
    if sid not in data:
        return _json_error("Proveedor no encontrado.", 404)
    del data[sid]
    _write_dict(data)
    return {"id": supplier_id, "deleted": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
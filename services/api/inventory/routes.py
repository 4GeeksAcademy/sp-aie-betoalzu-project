from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from services.schemas import (
    AssetCreate,
    AssetUpdate,
    AssetEntryCreate,
    AssetExitCreate,
)
from services.api.inventory.services import (
    create_asset,
    list_assets,
    get_asset,
    update_asset,
    create_entry,
    create_exit,
    list_orders,
)
from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB

inventory_api = APIRouter(prefix="/inventory")


def _json_error(message: str, status_code: int):
    return JSONResponse(content={"error": message}, status_code=status_code)


# ---------------------------------------------------------------------------
# Products (Assets)
# ---------------------------------------------------------------------------


@inventory_api.get("/products")
def get_products():
    """Lista todos los activos con current_stock calculado."""
    return [asset.model_dump(mode="json") for asset in list_assets()]


@inventory_api.post("/products", status_code=201)
def post_product(payload: AssetCreate):
    """Registra un nuevo activo."""
    try:
        return create_asset(payload).model_dump(mode="json")
    except ValueError as exc:
        return _json_error(str(exc), 409)


@inventory_api.get("/products/{product_id}")
def get_product_by_id(product_id: int):
    """Obtiene un activo con su stock actual."""
    asset = get_asset(product_id)
    if asset is None:
        return _json_error("Asset not found.", 404)
    return asset.model_dump(mode="json")


@inventory_api.put("/products/{product_id}")
def put_product(product_id: int, payload: AssetUpdate):
    """Actualiza un activo existente."""
    try:
        result = update_asset(product_id, payload)
        if result is None:
            return _json_error("Asset not found.", 404)
        return result.model_dump(mode="json")
    except ValueError as exc:
        return _json_error(str(exc), 409)


# ---------------------------------------------------------------------------
# Orders (Inbound / Outbound)
# ---------------------------------------------------------------------------


@inventory_api.post("/orders/inbound", status_code=201)
def post_inbound_order(
    payload: AssetEntryCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Registra una entrega de activos (AssetEntry).

    Requiere autenticación. El user_uuid se extrae del token JWT.
    """
    try:
        return create_entry(payload, user_uuid=str(current_user.id)).model_dump(mode="json")
    except ValueError as exc:
        return _json_error(str(exc), 404)


@inventory_api.post("/orders/outbound", status_code=201)
def post_outbound_order(
    payload: AssetExitCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Registra una asignación o consumo (AssetExit).

    Requiere autenticación. El user_uuid se extrae del token JWT.

    Valida:
    - Stock suficiente (HTTP 400 si no).
    - assigned_to obligatorio si exit_type=allocation.
    - assigned_to debe ser nulo si exit_type=consumption.
    """
    try:
        return create_exit(payload, user_uuid=str(current_user.id)).model_dump(mode="json")
    except ValueError as exc:
        return _json_error(str(exc), 400)


@inventory_api.get("/orders")
def get_orders():
    """Lista todas las entradas y salidas con datos del activo."""
    return list_orders()

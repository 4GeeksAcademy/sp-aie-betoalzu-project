from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tinydb import TinyDB, Query

from services.schemas import (
    AssetCreate,
    AssetUpdate,
    AssetEntryCreate,
    AssetExitCreate,
    AssetResponse,
    AssetEntryResponse,
    AssetExitResponse,
    OrderResponse,
    Office,
    ExitType,
)

_ROOT_DIR = Path(__file__).resolve().parents[3]
_INVENTORY_DB_PATH = _ROOT_DIR / "data" / "inventory_db.json"


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db_path() -> Path:
    _INVENTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _INVENTORY_DB_PATH


def _open_tables():
    """Open the TinyDB and return (db, assets_table, entries_table, exits_table)."""
    db = TinyDB(str(_get_db_path()))
    return db, db.table("assets"), db.table("entries"), db.table("exits")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_asset(doc: dict) -> dict:
    return {
        "id": doc.doc_id,
        "name": doc["name"],
        "sku": doc["sku"],
        "category": doc["category"],
        "office": doc["office"],
    }


def _serialize_entry(doc: dict) -> dict:
    return {
        "id": doc.doc_id,
        "asset_id": doc["asset_id"],
        "quantity": doc["quantity"],
        "supplier": doc["supplier"],
        "office": doc["office"],
        "created_at": doc["created_at"],
        "user_uuid": doc["user_uuid"],
    }


def _serialize_exit(doc: dict) -> dict:
    return {
        "id": doc.doc_id,
        "asset_id": doc["asset_id"],
        "quantity": doc["quantity"],
        "exit_type": doc["exit_type"],
        "assigned_to": doc.get("assigned_to"),
        "office": doc["office"],
        "created_at": doc["created_at"],
        "user_uuid": doc["user_uuid"],
    }


def compute_current_stock(asset_id: int) -> int:
    """Calculate current_stock = SUM(entries) - SUM(exits) for a given asset."""
    _db, _assets_table, entries_table, exits_table = _open_tables()
    try:
        EntryQ = Query()
        ExitQ = Query()

        total_in = sum(
            e["quantity"]
            for e in entries_table.search(EntryQ.asset_id == asset_id)
        )
        total_out = sum(
            e["quantity"]
            for e in exits_table.search(ExitQ.asset_id == asset_id)
        )
        return total_in - total_out
    finally:
        _db.close()


# ---------------------------------------------------------------------------
# Asset CRUD
# ---------------------------------------------------------------------------


def create_asset(payload: AssetCreate) -> dict:
    db, assets_table, _, _ = _open_tables()
    try:
        AssetQ = Query()
        existing = assets_table.search(AssetQ.sku == payload.sku)
        if existing:
            raise ValueError(f"Asset with SKU '{payload.sku}' already exists.")

        doc_data = payload.model_dump(mode="json")
        doc_id = assets_table.insert(doc_data)
        doc = assets_table.get(doc_id=doc_id)
        return _serialize_asset(doc)
    finally:
        db.close()


def list_assets() -> list[dict]:
    db, assets_table, _, _ = _open_tables()
    try:
        results = []
        for doc in assets_table.all():
            asset = _serialize_asset(doc)
            asset["current_stock"] = compute_current_stock(doc.doc_id)
            results.append(asset)
        return results
    finally:
        db.close()


def get_asset(asset_id: int) -> dict | None:
    db, assets_table, _, _ = _open_tables()
    try:
        doc = assets_table.get(doc_id=asset_id)
        if doc is None:
            return None
        asset = _serialize_asset(doc)
        asset["current_stock"] = compute_current_stock(doc.doc_id)
        return asset
    finally:
        db.close()


def update_asset(asset_id: int, payload: AssetUpdate) -> dict | None:
    db, assets_table, _, _ = _open_tables()
    try:
        doc = assets_table.get(doc_id=asset_id)
        if doc is None:
            return None

        update_data = payload.model_dump(exclude_unset=True, mode="json")
        if not update_data:
            return _serialize_asset(doc)

        assets_table.update(update_data, doc_ids=[asset_id])
        updated = assets_table.get(doc_id=asset_id)
        asset = _serialize_asset(updated)
        asset["current_stock"] = compute_current_stock(asset_id)
        return asset
    finally:
        db.close()


# ---------------------------------------------------------------------------
# AssetEntry (Inbound)
# ---------------------------------------------------------------------------


def create_entry(payload: AssetEntryCreate, user_uuid: str) -> dict:
    db, assets_table, entries_table, _ = _open_tables()
    try:
        doc = assets_table.get(doc_id=payload.asset_id)
        if doc is None:
            raise ValueError(f"Asset with id '{payload.asset_id}' not found.")

        doc_data = payload.model_dump(mode="json")
        doc_data["user_uuid"] = user_uuid  # Override with authenticated user's UUID
        doc_data["created_at"] = _utc_now_str()
        doc_id = entries_table.insert(doc_data)
        created = entries_table.get(doc_id=doc_id)
        return _serialize_entry(created)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# AssetExit (Outbound)
# ---------------------------------------------------------------------------


def create_exit(payload: AssetExitCreate, user_uuid: str) -> dict:
    db, assets_table, entries_table, exits_table = _open_tables()
    try:
        # Check asset exists
        asset_doc = assets_table.get(doc_id=payload.asset_id)
        if asset_doc is None:
            raise ValueError(f"Asset with id '{payload.asset_id}' not found.")

        # Check sufficient stock
        EntryQ = Query()
        ExitQ = Query()

        total_in = sum(
            e["quantity"]
            for e in entries_table.search(EntryQ.asset_id == payload.asset_id)
        )
        total_out = sum(
            e["quantity"]
            for e in exits_table.search(ExitQ.asset_id == payload.asset_id)
        )
        available = total_in - total_out

        if payload.quantity > available:
            raise ValueError(
                f"Insufficient stock for asset '{asset_doc['name']}'. "
                f"Available: {available}, requested: {payload.quantity}."
            )

        doc_data = payload.model_dump(mode="json")
        doc_data["user_uuid"] = user_uuid  # Override with authenticated user's UUID
        doc_data["created_at"] = _utc_now_str()
        doc_id = exits_table.insert(doc_data)
        created = exits_table.get(doc_id=doc_id)
        return _serialize_exit(created)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Orders listing
# ---------------------------------------------------------------------------


def list_orders() -> list[dict]:
    db, assets_table, entries_table, exits_table = _open_tables()
    try:
        results = []

        for doc in entries_table.all():
            asset_doc = assets_table.get(doc_id=doc["asset_id"])
            results.append(
                OrderResponse(
                    id=doc.doc_id,
                    type="entry",
                    asset_id=doc["asset_id"],
                    asset_name=asset_doc["name"] if asset_doc else "Unknown",
                    asset_sku=asset_doc["sku"] if asset_doc else "Unknown",
                    quantity=doc["quantity"],
                    office=Office(doc["office"]),
                    user_uuid=doc["user_uuid"],
                    created_at=doc["created_at"],
                    supplier=doc["supplier"],
                    exit_type=None,
                    assigned_to=None,
                ).model_dump(mode="json")
            )

        for doc in exits_table.all():
            asset_doc = assets_table.get(doc_id=doc["asset_id"])
            results.append(
                OrderResponse(
                    id=doc.doc_id,
                    type="exit",
                    asset_id=doc["asset_id"],
                    asset_name=asset_doc["name"] if asset_doc else "Unknown",
                    asset_sku=asset_doc["sku"] if asset_doc else "Unknown",
                    quantity=doc["quantity"],
                    office=Office(doc["office"]),
                    user_uuid=doc["user_uuid"],
                    created_at=doc["created_at"],
                    supplier=None,
                    exit_type=ExitType(doc["exit_type"]),
                    assigned_to=doc.get("assigned_to"),
                ).model_dump(mode="json")
            )

        return results
    finally:
        db.close()

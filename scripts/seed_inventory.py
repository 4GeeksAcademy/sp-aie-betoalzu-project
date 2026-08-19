#!/usr/bin/env python3
"""Seed inventory data (assets, entries, exits) into TinyDB.

Usage:
    python scripts/seed_inventory.py

Creates the following seed data:

Assets (6):
  - Portátil 14" Business (NXV-IT-001) — hardware — Valencia
  - Portátil 14" Business (NXV-IT-002) — hardware — Miami
  - Ratón ergonómico (NXV-PER-001) — peripherals — Valencia
  - Hub USB-C (NXV-PER-002) — peripherals — Miami
  - Resma de papel A4 (NXV-OFF-001) — office_supplies — Valencia
  - Cuaderno de formación en liderazgo (NXV-TRN-001) — training_materials — Valencia

AssetEntries (4):
  - NXV-IT-001: 10 uds (TechDistrib Valencia S.L.) + 5 uds (Nexova IT Procurement)
  - NXV-PER-001: 20 uds (TechDistrib Valencia S.L.)
  - NXV-OFF-001: 50 uds (Office Depot Miami)

AssetExits (3):
  - NXV-IT-001: 2 uds — allocation → "Ana García"
  - NXV-IT-001: 1 ud — allocation → "Carlos López"
  - NXV-OFF-001: 10 uds — consumption → null
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tinydb import TinyDB, Query


INVENTORY_DB_PATH = ROOT_DIR / "data" / "inventory_db.json"

# Sample user UUID from TinyDB users (1st user doc_id)
DEFAULT_USER_UUID = "1"


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_inventory() -> dict[str, int]:
    INVENTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = TinyDB(str(INVENTORY_DB_PATH))
    assets_table = db.table("assets")
    entries_table = db.table("entries")
    exits_table = db.table("exits")

    # Clear existing data for a clean seed
    assets_table.truncate()
    entries_table.truncate()
    exits_table.truncate()

    AssetQ = Query()

    # -------------------------------------------------------------------
    # Assets
    # -------------------------------------------------------------------
    assets_data = [
        {"name": "Portátil 14\" Business", "sku": "NXV-IT-001", "category": "hardware", "office": "Valencia"},
        {"name": "Portátil 14\" Business", "sku": "NXV-IT-002", "category": "hardware", "office": "Miami"},
        {"name": "Ratón ergonómico", "sku": "NXV-PER-001", "category": "peripherals", "office": "Valencia"},
        {"name": "Hub USB-C", "sku": "NXV-PER-002", "category": "peripherals", "office": "Miami"},
        {"name": "Resma de papel A4", "sku": "NXV-OFF-001", "category": "office_supplies", "office": "Valencia"},
        {"name": "Cuaderno de formación en liderazgo", "sku": "NXV-TRN-001", "category": "training_materials", "office": "Valencia"},
    ]

    asset_ids = {}
    for a in assets_data:
        doc_id = assets_table.insert(a)
        asset_ids[a["sku"]] = doc_id

    # -------------------------------------------------------------------
    # AssetEntries (Inbound)
    # -------------------------------------------------------------------
    entries_data = [
        {"asset_id": asset_ids["NXV-IT-001"], "quantity": 10, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-IT-001"], "quantity": 5, "supplier": "Nexova IT Procurement", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-PER-001"], "quantity": 20, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-OFF-001"], "quantity": 50, "supplier": "Office Depot Miami", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
    ]

    for e in entries_data:
        entries_table.insert(e)

    # -------------------------------------------------------------------
    # AssetExits (Outbound)
    # -------------------------------------------------------------------
    exits_data = [
        {"asset_id": asset_ids["NXV-IT-001"], "quantity": 2, "exit_type": "allocation", "assigned_to": "Ana García", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-IT-001"], "quantity": 1, "exit_type": "allocation", "assigned_to": "Carlos López", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-OFF-001"], "quantity": 10, "exit_type": "consumption", "assigned_to": None, "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
    ]

    for ex in exits_data:
        exits_table.insert(ex)

    db.close()

    return {
        "assets": len(assets_data),
        "entries": len(entries_data),
        "exits": len(exits_data),
    }


def main() -> int:
    try:
        stats = seed_inventory()
    except Exception as exc:
        print(f"Error durante el seed de inventario: {exc}")
        return 1

    print("Seed de inventario finalizado correctamente.")
    print(f"Assets creados: {stats['assets']}")
    print(f"Entries creadas: {stats['entries']}")
    print(f"Exits creadas: {stats['exits']}")
    print(f"Base de datos TinyDB: {INVENTORY_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
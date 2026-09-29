#!/usr/bin/env python3
"""Seed inventory data (assets, entries, exits) into TinyDB.

Usage:
    python scripts/seed_inventory.py

Creates a demo inventory that matches the business requirements for Nexova:

Assets (7):
  - 3 categories covered: training_materials, certification, onboarding_equipment
  - program assigned to every category
  - realistic stock movement across Valencia and Miami

InboundOrders (13):
  - mixed between Valencia and Miami
  - enough volume to support later reporting and analytics

OutboundOrders (13):
  - includes low-stock scenarios for stock_threshold_triggered

The seeded data intentionally includes:
  - 2 assets with stock below the operational threshold (triggering low-stock alerts)
  - 1 high-cost certification batch to simulate a kit_cost_variance_detected condition
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

    # -------------------------------------------------------------------
    # Assets: 7 products covering the required categories and programs.
    # -------------------------------------------------------------------
    assets_data = [
        {
            "name": "Manual de liderazgo",
            "sku": "NXV-TRN-001",
            "category": "training_materials",
            "office": "Valencia",
            "currency": "EUR",
            "unit_cost": 18.5,
            "program": "formación de liderazgo",
        },
        {
            "name": "Kit de certificación B2B",
            "sku": "NXV-CERT-001",
            "category": "certification",
            "office": "Valencia",
            "currency": "EUR",
            "unit_cost": 42.0,
            "program": "ventas B2B",
        },
        {
            "name": "Laptop de onboarding",
            "sku": "NXV-ONB-001",
            "category": "onboarding_equipment",
            "office": "Valencia",
            "currency": "EUR",
            "unit_cost": 620.0,
            "program": "Onboarding",
        },
        {
            "name": "Módulo de formación comercial",
            "sku": "NXV-TRN-002",
            "category": "training_materials",
            "office": "Miami",
            "currency": "USD",
            "unit_cost": 22.0,
            "program": "formación de liderazgo",
        },
        {
            "name": "Pack de certificación Q2",
            "sku": "NXV-CERT-002",
            "category": "certification",
            "office": "Miami",
            "currency": "USD",
            "unit_cost": 54.0,
            "program": "ventas B2B",
        },
        {
            "name": "Kit de bienvenida para soporte",
            "sku": "NXV-ONB-002",
            "category": "onboarding_equipment",
            "office": "Miami",
            "currency": "USD",
            "unit_cost": 590.0,
            "program": "Onboarding",
        },
        {
            "name": "Guía de onboarding para clientes",
            "sku": "NXV-ONB-003",
            "category": "onboarding_equipment",
            "office": "Valencia",
            "currency": "EUR",
            "unit_cost": 120.0,
            "program": "Onboarding",
        },
    ]

    asset_ids = {}
    for asset in assets_data:
        doc_id = assets_table.insert(asset)
        asset_ids[asset["sku"]] = doc_id

    # -------------------------------------------------------------------
    # Inbound orders (13): split across Valencia and Miami.
    # This dataset is intentionally designed so that some items fall below
    # their operational threshold and one certification kit shows a cost jump.
    # -------------------------------------------------------------------
    entries_data = [
        {"asset_id": asset_ids["NXV-TRN-001"], "quantity": 20, "supplier": "Imprenta Valencia S.L.", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-TRN-001"], "quantity": 12, "supplier": "L&D Print Hub", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-001"], "quantity": 10, "supplier": "CertiPro Valencia", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-001"], "quantity": 8, "supplier": "Nexova Collaboration", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-001"], "quantity": 15, "supplier": "TechDistrib Valencia", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-001"], "quantity": 12, "supplier": "Northwest Hardware", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-TRN-002"], "quantity": 18, "supplier": "Miami Learning Lab", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-TRN-002"], "quantity": 9, "supplier": "Formación Global", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-002"], "quantity": 14, "supplier": "SalesCert Alliance", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-002"], "quantity": 10, "supplier": "SkillBridge Miami", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-002"], "quantity": 16, "supplier": "OnboardWorks Miami", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-002"], "quantity": 8, "supplier": "HireCore Valencia", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-003"], "quantity": 11, "supplier": "Welcome Pack Iberia", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
    ]

    for entry in entries_data:
        entries_table.insert(entry)

    # -------------------------------------------------------------------
    # Outbound orders (13): allocations and consumptions to consume the stock.
    # -------------------------------------------------------------------
    exits_data = [
        {"asset_id": asset_ids["NXV-TRN-001"], "quantity": 12, "exit_type": "allocation", "assigned_to": "Ana García", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-TRN-001"], "quantity": 6, "exit_type": "allocation", "assigned_to": "Laura Ortiz", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-TRN-001"], "quantity": 2, "exit_type": "consumption", "assigned_to": None, "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-001"], "quantity": 9, "exit_type": "allocation", "assigned_to": "Carmen Díaz", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-001"], "quantity": 7, "exit_type": "allocation", "assigned_to": "Marco Silva", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-001"], "quantity": 10, "exit_type": "allocation", "assigned_to": "Kai Chen", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-001"], "quantity": 7, "exit_type": "allocation", "assigned_to": "Nora López", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-TRN-002"], "quantity": 12, "exit_type": "allocation", "assigned_to": "Paula García", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-TRN-002"], "quantity": 6, "exit_type": "consumption", "assigned_to": None, "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-002"], "quantity": 9, "exit_type": "allocation", "assigned_to": "Marta Ríos", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-CERT-002"], "quantity": 5, "exit_type": "allocation", "assigned_to": "Eduardo Flores", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-002"], "quantity": 11, "exit_type": "allocation", "assigned_to": "Sofía Álvarez", "office": "Miami", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
        {"asset_id": asset_ids["NXV-ONB-003"], "quantity": 8, "exit_type": "allocation", "assigned_to": "Pablo Navarro", "office": "Valencia", "user_uuid": DEFAULT_USER_UUID, "created_at": _utc_now_str()},
    ]

    for exit_order in exits_data:
        exits_table.insert(exit_order)

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
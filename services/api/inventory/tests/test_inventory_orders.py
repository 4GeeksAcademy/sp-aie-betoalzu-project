from __future__ import annotations

import pytest
from tinydb import TinyDB

import services.api.inventory.services as inventory_services
from services.cache import backend_cache


@pytest.fixture
def inventory_db(tmp_path, monkeypatch):
    db_path = tmp_path / "inventory_db.json"
    monkeypatch.setattr(inventory_services, "_get_db_path", lambda: db_path)
    db = TinyDB(str(db_path))
    db.table("assets")
    db.table("entries")
    db.table("exits")
    yield db
    db.close()


def test_list_orders_reads_latest_data_after_initial_empty_cache(inventory_db):
    backend_cache.clear()

    assert inventory_services.list_orders() == []

    asset_table = inventory_db.table("assets")
    entry_table = inventory_db.table("entries")
    exit_table = inventory_db.table("exits")

    asset_id = asset_table.insert(
        {
            "name": "Kit de certificación B2B",
            "sku": "NXV-CERT-001",
            "category": "certification",
            "office": "Valencia",
            "currency": "EUR",
            "unit_cost": 42.0,
            "program": "ventas B2B",
        }
    )
    entry_table.insert(
        {
            "asset_id": asset_id,
            "quantity": 10,
            "supplier": "CertiPro Valencia",
            "office": "Valencia",
            "user_uuid": "1",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    exit_table.insert(
        {
            "asset_id": asset_id,
            "quantity": 4,
            "exit_type": "allocation",
            "assigned_to": "Ana García",
            "office": "Valencia",
            "user_uuid": "1",
            "created_at": "2026-01-01T00:00:01+00:00",
        }
    )

    orders = inventory_services.list_orders()
    assert len(orders) == 2
    assert {order["type"] for order in orders} == {"entry", "exit"}

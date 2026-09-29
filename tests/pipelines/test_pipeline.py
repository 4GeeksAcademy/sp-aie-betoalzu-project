from datetime import date

from data.pipelines.pipeline import (
    aggregate_weekly_performance,
    calculate_total_material_cost,
    count_cost_variance_events,
    count_kits_delivered,
    count_shortage_events,
)


WEEK_START = date(2026, 9, 21)


def event(event_type: str, **tags: object) -> dict:
    return {"event_type": event_type, "tags": tags}


def test_calculate_total_material_cost_uses_unit_cost_and_quantity() -> None:
    events = [
        event("inbound_order_created", unit_cost=120, quantity=2),
        event("inbound_order_created", unit_cost=35.5, quantity=1),
    ]

    assert calculate_total_material_cost.fn(events) == 275.5


def test_kpi_count_tasks_count_only_their_business_event() -> None:
    events = [
        event("outbound_order_created", office="valencia", programme_id="leadership"),
        event("stock_threshold_triggered", office="valencia", programme_id="leadership"),
        event("kit_cost_variance_detected", office="valencia", programme_id="leadership"),
        event("outbound_order_created", office="valencia", programme_id="leadership"),
    ]

    assert count_kits_delivered.fn(events) == 2
    assert count_shortage_events.fn(events) == 1
    assert count_cost_variance_events.fn(events) == 1


def test_kpi_tasks_ignore_malformed_events_defensively() -> None:
    events = [None, {"event_type": "inbound_order_created", "tags": None}, event(
        "inbound_order_created", unit_cost="invalid", quantity=1
    )]

    assert calculate_total_material_cost.fn(events) == 0
    assert count_kits_delivered.fn(events) == 0


def test_aggregate_weekly_performance_returns_the_four_report_kpis() -> None:
    events = [
        event("inbound_order_created", office="valencia", programme_id="b2b-sales", currency="EUR", unit_cost=100, quantity=2),
        event("outbound_order_created", office="valencia", programme_id="b2b-sales", currency="EUR"),
        event("stock_threshold_triggered", office="valencia", programme_id="b2b-sales", currency="EUR"),
        event("kit_cost_variance_detected", office="valencia", programme_id="b2b-sales", currency="EUR"),
    ]

    rows = aggregate_weekly_performance.fn(events, WEEK_START)

    assert rows == [{
        "office": "valencia",
        "programme_id": "b2b-sales",
        "week_start": WEEK_START,
        "total_material_cost": 200.0,
        "kits_delivered_count": 1,
        "shortage_events_count": 1,
        "cost_variance_events_count": 1,
        "currency": "EUR",
    }]

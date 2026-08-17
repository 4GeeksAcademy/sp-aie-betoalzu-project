"""CRUD service layer for the Centralized Incident Manager.

Uses TinyDB for persistence (matching the pattern of suppliers and users).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tinydb import TinyDB, Query

from services.api.incidents.models import (
    IncidentCreate,
    IncidentUpdate,
    IncidentOut,
    IncidentStatus,
    IncidentStatusUpdate,
    VALID_TRANSITIONS,
    _TERMINAL_STATUSES,
)

_ROOT_DIR = Path(__file__).resolve().parents[3]
_INCIDENTS_DB_PATH = _ROOT_DIR / "data" / "incidents_db.json"


def _get_db_path() -> Path:
    _INCIDENTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _INCIDENTS_DB_PATH


def _open_incidents_table():
    db = TinyDB(str(_get_db_path()))
    return db, db.table("incidents")


def _serialize_incident(doc) -> IncidentOut:
    """Convert a TinyDB document into an IncidentOut."""
    return IncidentOut(
        id=doc.doc_id,
        title=doc["title"],
        description=doc.get("description"),
        category=doc["category"],
        origin=doc["origin"],
        branch=doc["branch"],
        status=doc["status"],
        reported_by=doc.get("reported_by"),
        assigned_to=doc.get("assigned_to"),
        ticket_id=doc.get("ticket_id"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _raise_if_terminal(doc: dict, new_status: IncidentStatus) -> None:
    """Raise ValueError if the incident is in a terminal state."""
    current = IncidentStatus(doc["status"])
    if current in _TERMINAL_STATUSES:
        raise ValueError(
            f"Cannot transition from terminal status '{current.value}' to '{new_status.value}'."
        )


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def create_incident(payload: IncidentCreate) -> IncidentOut:
    """Create a new incident and return it."""
    now = _utc_now_str()
    data = payload.model_dump(mode="json", exclude_none=True)
    data.update({"created_at": now, "updated_at": now})
    default_fields = {"description": "", "reported_by": None, "assigned_to": None, "ticket_id": None}
    for key, default in default_fields.items():
        data.setdefault(key, default)

    db, table = _open_incidents_table()
    try:
        doc_id = table.insert(data)
        doc = table.get(doc_id=doc_id)
        return _serialize_incident(doc)
    finally:
        db.close()


def get_incident(incident_id: int) -> IncidentOut | None:
    """Return an incident by its doc_id, or None."""
    db, table = _open_incidents_table()
    try:
        doc = table.get(doc_id=incident_id)
        if doc is None:
            return None
        return _serialize_incident(doc)
    finally:
        db.close()


def _get_raw(incident_id: int):
    """Internal helper: return the raw TinyDB document."""
    _, table = _open_incidents_table()
    return table.get(doc_id=incident_id)


def list_incidents(
    status: str | None = None,
    category: str | None = None,
    branch: str | None = None,
    origin: str | None = None,
) -> list[IncidentOut]:
    """List incidents with optional filters."""
    db, table = _open_incidents_table()
    try:
        results: list[IncidentOut] = []
        for doc in table.all():
            if status is not None and doc.get("status") != status:
                continue
            if category is not None and doc.get("category") != category:
                continue
            if branch is not None and doc.get("branch") != branch:
                continue
            if origin is not None and doc.get("origin") != origin:
                continue
            results.append(_serialize_incident(doc))
        return results
    finally:
        db.close()


def update_incident(incident_id: int, payload: IncidentUpdate) -> IncidentOut:
    """Update an incident (partial update). Returns the updated incident.

    Raises ValueError if the incident is in a terminal state.
    """
    db, table = _open_incidents_table()
    try:
        doc = table.get(doc_id=incident_id)
        if doc is None:
            raise ValueError(f"Incident with id {incident_id} not found.")

        _raise_if_terminal(doc, doc["status"])

        update_data = payload.model_dump(mode="json", exclude_none=True)
        if not update_data:
            return _serialize_incident(doc)

        update_data["updated_at"] = _utc_now_str()

        merged = {**doc, **update_data}
        table.update(merged, doc_ids=[incident_id])
        updated = table.get(doc_id=incident_id)
        return _serialize_incident(updated)
    finally:
        db.close()


def update_incident_status(incident_id: int, payload: IncidentStatusUpdate) -> IncidentOut:
    """Transition an incident to a new status.

    Validates that the transition is allowed by VALID_TRANSITIONS.
    Raises ValueError on invalid transition.
    """
    new_status = payload.status

    db, table = _open_incidents_table()
    try:
        doc = table.get(doc_id=incident_id)
        if doc is None:
            raise ValueError(f"Incident with id {incident_id} not found.")

        current_status = IncidentStatus(doc["status"])

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{current_status.value}' to '{new_status.value}'. "
                f"Allowed transitions: {[s.value for s in allowed] if allowed else 'none (terminal status)'}."
            )

        table.update(
            {"status": new_status.value, "updated_at": _utc_now_str()},
            doc_ids=[incident_id],
        )
        updated = table.get(doc_id=incident_id)
        return _serialize_incident(updated)
    finally:
        db.close()


def delete_incident(incident_id: int) -> bool:
    """Delete an incident by id. Returns True if deleted, False if not found."""
    db, table = _open_incidents_table()
    try:
        doc = table.get(doc_id=incident_id)
        if doc is None:
            return False
        table.remove(doc_ids=[incident_id])
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Summary / Aggregation
# ---------------------------------------------------------------------------


def get_summary() -> dict[str, Any]:
    """Return aggregated summary statistics for the dashboard."""
    db, table = _open_incidents_table()
    try:
        all_docs = table.all()
        total = len(all_docs)

        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_branch: dict[str, int] = {}
        by_origin: dict[str, int] = {}

        # Track oldest open incident
        oldest_open: str | None = None
        open_critical_count = 0

        for doc in all_docs:
            s = doc.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

            cat = doc.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

            br = doc.get("branch", "unknown")
            by_branch[br] = by_branch.get(br, 0) + 1

            o = doc.get("origin", "unknown")
            by_origin[o] = by_origin.get(o, 0) + 1

            if s == "open":
                created = doc.get("created_at", "")
                if created and (oldest_open is None or created < oldest_open):
                    oldest_open = created

            # SLA breaches are critical
            if doc.get("category") == "sla_breach" and s in ("open", "in_progress"):
                open_critical_count += 1

        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
            "by_branch": by_branch,
            "by_origin": by_origin,
            "open_oldest": oldest_open,
            "open_critical_count": open_critical_count,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Idempotency helpers (for CSV seed)
# ---------------------------------------------------------------------------


def exists_by_ticket_id(ticket_id: str) -> bool:
    """Check if an incident with the given ticket_id already exists."""
    db, table = _open_incidents_table()
    try:
        Q = Query()
        return table.contains(Q.ticket_id == ticket_id)
    finally:
        db.close()


def exists_by_title_and_date(title: str, created_at: str) -> bool:
    """Fallback idempotency check when ticket_id is not available."""
    db, table = _open_incidents_table()
    try:
        Q = Query()
        return table.contains((Q.title == title) & (Q.created_at == created_at))
    finally:
        db.close()


def clear_all_incidents() -> int:
    """Remove all incident records from the database. Returns count of removed records."""
    db, table = _open_incidents_table()
    try:
        removed = len(table.all())
        table.truncate()
        return removed
    finally:
        db.close()


def bulk_insert_incidents(records: list[dict]) -> int:
    """Insert multiple incident records at once. Returns count of inserted records."""
    db, table = _open_incidents_table()
    try:
        now = _utc_now_str()
        inserted = 0
        for record in records:
            record.setdefault("created_at", now)
            record["updated_at"] = now
            table.insert(record)
            inserted += 1
        return inserted
    finally:
        db.close()
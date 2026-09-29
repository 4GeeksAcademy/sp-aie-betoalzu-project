"""REST API routes for the Centralized Incident Manager.

Endpoints:
  GET    /api/incidents              → List incidents (with optional filters)
  POST   /api/incidents              → Create a new incident
  GET    /api/incidents/summary       → Aggregated summary statistics
  POST   /api/incidents/seed          → Seed from CSV (transformed)
  GET    /api/incidents/{id}          → Get incident detail
  PUT    /api/incidents/{id}          → Update incident
  PATCH  /api/incidents/{id}/status   → Transition incident status
  DELETE /api/incidents/{id}          → Delete incident
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse

from services.api.incidents.models import (
    IncidentCategory,
    IncidentCreate,
    IncidentStatus,
    IncidentUpdate,
    IncidentStatusUpdate,
    SeedResult,
)
from services.api.incidents.services import (
    create_incident,
    get_incident,
    list_incidents,
    update_incident,
    update_incident_status,
    delete_incident,
    get_summary,
    exists_by_ticket_id,
    exists_by_title_and_date,
    bulk_insert_incidents,
    clear_all_incidents,
)
from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB


incidents_api = APIRouter()
_ROOT_DIR = Path(__file__).resolve().parents[3]
_CSV_PATH = _ROOT_DIR / "scripts" / "incidents-nexova.csv"


def _json_error(message: str, status_code: int):
    return JSONResponse(content={"error": message}, status_code=status_code)


# ---------------------------------------------------------------------------
# CSV → Nexova mapping helpers
# ---------------------------------------------------------------------------

CSV_STATUS_MAP = {
    "OPEN": "open",
    "CLOSED": "resolved",
    "DISCARDED": "discarded",
}

CSV_CATEGORY_MAP = {
    "TECHNICAL": "technical_failure",
    "BILLING": "process_error",
    "ACCESS": "technical_failure",
    "HR_QUERY": "process_error",
    "COMPLAINT": "client_complaint",
}

VALID_CSV_CATEGORIES = set(CSV_CATEGORY_MAP.keys())
VALID_CSV_STATUSES = set(CSV_STATUS_MAP.keys())


def _transform_csv_row(row: dict) -> dict | None:
    """Transform a raw CSV row into a Nexova incident record.

    Applies the same shared validation as the CSV analyzer:
      - client_company required
      - known category, status
      - description >= 5 chars
      - agent_id matches AGT-XX
      - email with '@'
      - CLOSED requires score
      - score in 1-5

    Returns None if the row is invalid and should be discarded.
    """
    import re

    ticket_id = row.get("ticket_id", "").strip()
    client_company = row.get("client_company", "").strip()
    description_raw = row.get("description", "").strip()
    date_raw = row.get("date", "").strip()
    csv_category = row.get("category", "").strip()
    csv_status = row.get("status", "").strip()
    agent_id = row.get("agent_id", "").strip()
    customer_email = row.get("customer_email", "").strip()
    raw_score = row.get("satisfaction_score", "").strip()

    # Shared validation
    reasons: list[str] = []

    if not client_company:
        reasons.append("missing_client_company")
    if csv_category not in VALID_CSV_CATEGORIES:
        reasons.append(f"invalid_category '{csv_category}'")
    if len(description_raw) < 5:
        reasons.append("invalid_description (too short)")
    if not re.match(r"^AGT-\d{2}$", agent_id):
        reasons.append(f"invalid_agent '{agent_id}'")
    if csv_status not in VALID_CSV_STATUSES:
        reasons.append(f"invalid_status '{csv_status}'")
    if not customer_email or "@" not in customer_email:
        reasons.append("invalid_email")
    if csv_status == "CLOSED" and not raw_score:
        reasons.append("closed_no_score")
    if raw_score:
        try:
            parsed_score = int(raw_score)
            if parsed_score < 1 or parsed_score > 5:
                reasons.append(f"score_out_of_range ({raw_score})")
        except ValueError:
            reasons.append(f"score_out_of_range (not int: '{raw_score}')")

    if reasons:
        print(f"[SEED] Discarded ticket_id={ticket_id}: {'; '.join(reasons)}")
        return None

    # --- Build title (first 120 chars of description) ---
    title = description_raw[:120].strip()
    if not title:
        print(f"[SEED] Discarded (empty title): ticket_id={ticket_id}")
        return None

    # --- Parse date ---
    try:
        created_at = datetime.strptime(date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        print(f"[SEED] Discarded (invalid date '{date_raw}'): ticket_id={ticket_id}")
        return None

    category = CSV_CATEGORY_MAP[csv_category]
    status = CSV_STATUS_MAP[csv_status]

    # --- Idempotency ---
    if ticket_id:
        if exists_by_ticket_id(ticket_id):
            print(f"[SEED] Skipped (duplicate ticket_id): {ticket_id}")
            return None
    else:
        if exists_by_title_and_date(title, created_at):
            print(f"[SEED] Skipped (duplicate title+date): {title}")
            return None

    return {
        "title": title,
        "description": description_raw,
        "category": category,
        "origin": "customer",
        "branch": "central",
        "status": status,
        "ticket_id": ticket_id or None,
        "created_at": created_at,
    }


def _seed_from_csv(file_path: Path) -> SeedResult:
    """Read a CSV file, transform rows, and bulk-insert into TinyDB.

    Clears existing data before seeding. Returns a SeedResult with seed statistics.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    content = file_path.read_bytes()
    # Handle BOM
    if content[:3] == b"\xef\xbb\xbf":
        content = content[3:]

    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    if reader.fieldnames is None:
        raise ValueError("CSV file has no headers.")

    # Clear previous data
    clear_all_incidents()

    total_rows = 0
    inserted = 0
    discarded = 0
    skipped = 0

    for row in reader:
        total_rows += 1
        transformed = _transform_csv_row(row)
        if transformed is None:
            discarded += 1
            continue

        bulk_insert_incidents([transformed])
        inserted += 1

    return SeedResult(
        total_rows=total_rows,
        inserted=inserted,
        discarded=discarded,
        skipped=skipped,
        status="ok",
    )


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@incidents_api.get("/api/incidents")
def list_all_incidents(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    branch: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """List incidents with optional filters."""
    try:
        return [
            inc.model_dump(mode="json")
            for inc in list_incidents(
                status=status,
                category=category,
                branch=branch,
                origin=origin,
            )
        ]
    except Exception:
        return _json_error("Error al listar incidencias.", 500)


@incidents_api.post("/api/incidents", status_code=201)
def create_new_incident(
    payload: IncidentCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Create a new incident."""
    try:
        incident = create_incident(payload)
        return incident.model_dump(mode="json")
    except ValueError as exc:
        return _json_error(str(exc), 400)


@incidents_api.get("/api/incidents/summary")
def incidents_summary(
    current_user: UserInDB = Depends(get_current_user),
):
    """Return aggregated summary statistics."""
    try:
        return get_summary().model_dump(mode="json")
    except Exception:
        return _json_error("Error al obtener el resumen de incidencias.", 500)


@incidents_api.post("/api/incidents/seed")
def seed_incidents_from_csv(
    current_user: UserInDB = Depends(get_current_user),
):
    """Seed incidents from the project's incidents-nexova.csv file.

    Transforms CSV fields into the Nexova incident model.
    """
    try:
        result = _seed_from_csv(_CSV_PATH)
        return result.model_dump(mode="json")
    except (FileNotFoundError, ValueError) as exc:
        return _json_error(str(exc), 500)


@incidents_api.get("/api/incidents/{incident_id}")
def get_incident_by_id(
    incident_id: int,
    current_user: UserInDB = Depends(get_current_user),
):
    """Get a single incident by ID."""
    incident = get_incident(incident_id)
    if incident is None:
        return _json_error("Incidencia no encontrada.", 404)
    return incident.model_dump(mode="json")


@incidents_api.put("/api/incidents/{incident_id}")
def update_incident_by_id(
    incident_id: int,
    payload: IncidentUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update an incident (partial update)."""
    try:
        incident = update_incident(incident_id, payload)
        return incident.model_dump(mode="json")
    except ValueError as exc:
        return _json_error(str(exc), 400)


@incidents_api.patch("/api/incidents/{incident_id}/status")
def transition_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Transition an incident to a new status.

    Validates state machine transitions:
      open → in_progress | discarded
      in_progress → resolved | discarded
      resolved/discarded → (terminal, no further transitions)
    """
    try:
        incident = update_incident_status(incident_id, payload)
        return incident.model_dump(mode="json")
    except ValueError as exc:
        return _json_error(str(exc), 400)


@incidents_api.delete("/api/incidents/{incident_id}")
def delete_incident_by_id(
    incident_id: int,
    current_user: UserInDB = Depends(get_current_user),
):
    """Delete an incident by ID."""
    try:
        deleted = delete_incident(incident_id)
        if not deleted:
            return _json_error("Incidencia no encontrada.", 404)
        return {"message": "Incidencia eliminada correctamente."}
    except Exception:
        return _json_error("Error al eliminar la incidencia.", 500)
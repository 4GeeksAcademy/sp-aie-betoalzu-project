#!/usr/bin/env python3
"""Seed incidents from incidents-nexova.csv into the Centralized Incident Manager (TinyDB).

Usage:
    python scripts/seed_incidents.py

Applies the transformations defined in gestor-incidentes-centralizado.md:
  - CSV status → model status (OPEN→open, CLOSED→resolved, DISCARDED→discarded)
  - CSV category → model category (TECHNICAL→technical_failure, BILLING→process_error, etc.)
  - description → title (first 120 chars)
  - origin → always "customer"
  - branch → always "central"

Expected result (96 valid records after seed):
  by_status:  open=27, resolved=56, discarded=13
  by_category: technical_failure=49, process_error=35, client_complaint=12
"""

from __future__ import annotations

import csv
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.api.incidents.services import (
    bulk_insert_incidents,
)


# ---------------------------------------------------------------------------
# Mapping tables
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

VALID_CSV_STATUSES = set(CSV_STATUS_MAP.keys())
VALID_CSV_CATEGORIES = set(CSV_CATEGORY_MAP.keys())


def transform_row(row: dict) -> dict | None:
    """Transform a single CSV row into a Nexova incident record.

    Applies the same shared validation logic as the CSV analyzer:
      - client_company must be present
      - category must be a known CSV category
      - description must be at least 5 characters
      - agent_id must match AGT-XX pattern
      - status must be a known CSV status
      - email must contain '@'
      - CLOSED records must have a satisfaction_score
      - score must be between 1 and 5

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

    # ------------------------------------------------------------------
    # Shared validation (same rules as the CSV analyzer)
    # ------------------------------------------------------------------
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
            reasons.append(f"score_out_of_range (not an int: '{raw_score}')")

    if reasons:
        print(f"  [SKIP] ticket_id={ticket_id}: {'; '.join(reasons)}")
        return None

    # --- Build title (first 120 chars of description) ---
    title = description_raw[:120].strip()
    if not title:
        print(f"  [SKIP] ticket_id={ticket_id}: empty title after truncation")
        return None

    # --- Parse date ---
    try:
        created_at = datetime.strptime(date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        print(f"  [SKIP] ticket_id={ticket_id}: invalid date '{date_raw}'")
        return None

    category = CSV_CATEGORY_MAP[csv_category]
    status = CSV_STATUS_MAP[csv_status]

    return {
        "title": title,
        "description": description_raw,
        "category": category,
        "origin": "customer",
        "branch": "central",
        "status": status,
        "ticket_id": ticket_id if ticket_id else None,
        "created_at": created_at,
    }


def seed_from_csv(file_path: Path) -> dict:
    """Read CSV, transform, and bulk-insert into TinyDB.

    Returns seed statistics.
    """
    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    content = file_path.read_bytes()
    # Strip BOM if present
    if content[:3] == b"\xef\xbb\xbf":
        content = content[3:]

    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    if reader.fieldnames is None:
        return {"error": "CSV has no headers."}

    # Clear existing incidents for a clean seed
    from tinydb import TinyDB
    db_path = ROOT_DIR / "data" / "incidents_db.json"
    if db_path.exists():
        db_path.unlink()
        print("  Cleared existing incidents database.")

    total_rows = 0
    valid_records: list[dict] = []
    discarded = 0

    for row in reader:
        total_rows += 1
        transformed = transform_row(row)
        if transformed is None:
            discarded += 1
            continue
        valid_records.append(transformed)

    inserted = bulk_insert_incidents(valid_records)

    return {
        "total_rows": total_rows,
        "valid": len(valid_records),
        "inserted": inserted,
        "discarded": discarded,
    }


def main() -> int:
    csv_path = ROOT_DIR / "scripts" / "incidents-nexova.csv"
    print(f"Seeding incidents from: {csv_path}")
    print()

    result = seed_from_csv(csv_path)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return 1

    print()
    print("=" * 50)
    print("  SEED COMPLETE")
    print("=" * 50)
    print(f"  Total CSV rows read:    {result['total_rows']}")
    print(f"  Valid records:          {result['valid']}")
    print(f"  Inserted into DB:       {result['inserted']}")
    print(f"  Discarded (invalid):    {result['discarded']}")
    print()

    # Verify counts
    from services.api.incidents.services import get_summary
    try:
        summary = get_summary()
    except Exception as exc:
        print(f"ERROR: No se pudo obtener el resumen de incidencias: {exc}")
        return 1
    print("  --- Summary ---")
    print(f"  Total in DB: {summary['total']}")
    print(f"  By status:   {summary['by_status']}")
    print(f"  By category: {summary['by_category']}")

    # Expected counts from the spec
    expected_status = {"open": 27, "resolved": 56, "discarded": 13}
    expected_category = {"technical_failure": 49, "process_error": 35, "client_complaint": 12}

    print()
    print("  --- Expected vs Actual ---")
    all_ok = True
    for key, expected in expected_status.items():
        actual = summary["by_status"].get(key, 0)
        status_icon = "✓" if actual == expected else "✗"
        print(f"  {status_icon} status '{key}': expected={expected}, actual={actual}")
        if actual != expected:
            all_ok = False

    for key, expected in expected_category.items():
        actual = summary["by_category"].get(key, 0)
        status_icon = "✓" if actual == expected else "✗"
        print(f"  {status_icon} category '{key}': expected={expected}, actual={actual}")
        if actual != expected:
            all_ok = False

    if all_ok:
        print()
        print("  ✅ All counts match the expected values!")
    else:
        print()
        print("  ⚠️  Some counts differ from expected. Review discards above.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
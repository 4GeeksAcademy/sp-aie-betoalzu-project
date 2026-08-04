from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


VALID_CATEGORIES = ("TECHNICAL", "BILLING", "ACCESS", "HR_QUERY", "COMPLAINT")
VALID_STATUSES = ("OPEN", "CLOSED", "DISCARDED")
REQUIRED_HEADERS = (
    "ticket_id",
    "date",
    "client_company",
    "category",
    "description",
    "agent_id",
    "status",
    "customer_email",
    "satisfaction_score",
)
AGENT_PATTERN = re.compile(r"AGT-\d{2}")

INVALID_RULE_LABELS = {
    "missing_client_company": "Missing client_company",
    "invalid_category": "Invalid or missing category",
    "invalid_description": "Missing or short description",
    "invalid_agent": "Invalid or missing agent_id",
    "invalid_status": "Invalid or missing status",
    "invalid_email": "Invalid or missing email",
    "closed_no_score": "Closed ticket, no score",
    "score_out_of_range": "Score out of range",
}

SCORE_LABELS = {
    1: "Very dissatisfied",
    2: "Dissatisfied",
    3: "Neutral",
    4: "Satisfied",
    5: "Very satisfied",
}


class AnalysisError(Exception):
    pass


class EmptyFileError(AnalysisError):
    pass


class InvalidCsvFormatError(AnalysisError):
    pass


@dataclass
class AnalysisResult:
    source_file: str
    total_records: int
    valid_records: int
    invalid_records: int
    invalid_rules: Counter
    categories: Counter
    statuses: Counter
    scores: Counter


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _validate_headers(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise EmptyFileError("El fichero CSV esta vacio o no contiene cabecera.")

    missing_headers = [header for header in REQUIRED_HEADERS if header not in fieldnames]
    if missing_headers:
        raise InvalidCsvFormatError(
            "El fichero CSV no tiene el formato esperado. Faltan columnas requeridas: "
            + ", ".join(missing_headers)
        )


def analyze_csv_stream(handle: TextIO, source_file: str) -> AnalysisResult:
    invalid_rules: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    scores: Counter[int] = Counter()

    total_records = 0
    valid_records = 0

    try:
        reader = csv.DictReader(handle)
        _validate_headers(reader.fieldnames)

        for row in reader:
            if row is None:
                continue

            total_records += 1
            row_errors: list[str] = []

            client_company = _clean(row.get("client_company"))
            category = _clean(row.get("category"))
            description = _clean(row.get("description"))
            agent_id = _clean(row.get("agent_id"))
            status = _clean(row.get("status"))
            customer_email = _clean(row.get("customer_email"))
            raw_score = _clean(row.get("satisfaction_score"))

            if not client_company:
                row_errors.append("missing_client_company")

            if category not in VALID_CATEGORIES:
                row_errors.append("invalid_category")

            if len(description) < 5:
                row_errors.append("invalid_description")

            if not AGENT_PATTERN.fullmatch(agent_id):
                row_errors.append("invalid_agent")

            if status not in VALID_STATUSES:
                row_errors.append("invalid_status")

            if not customer_email or "@" not in customer_email:
                row_errors.append("invalid_email")

            score_value: int | None = None
            if status == "CLOSED" and not raw_score:
                row_errors.append("closed_no_score")

            if raw_score:
                try:
                    score_value = int(raw_score)
                    if not 1 <= score_value <= 5:
                        row_errors.append("score_out_of_range")
                except ValueError:
                    row_errors.append("score_out_of_range")

            if row_errors:
                invalid_rules.update(row_errors)
                continue

            valid_records += 1
            categories[category] += 1
            statuses[status] += 1

            if status == "CLOSED" and score_value is not None:
                scores[score_value] += 1
    except csv.Error as error:
        raise InvalidCsvFormatError(
            "El fichero CSV no tiene un formato valido o no puede procesarse."
        ) from error

    invalid_records = total_records - valid_records

    return AnalysisResult(
        source_file=source_file,
        total_records=total_records,
        valid_records=valid_records,
        invalid_records=invalid_records,
        invalid_rules=invalid_rules,
        categories=categories,
        statuses=statuses,
        scores=scores,
    )


def analyze_csv(file_path: Path) -> AnalysisResult:
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        return analyze_csv_stream(handle, file_path.name)


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def build_summary(result: AnalysisResult) -> dict[str, object]:
    closed_tickets = result.statuses.get("CLOSED", 0)
    scored_tickets = sum(result.scores.values())
    average_score = (
        sum(score * count for score, count in result.scores.items()) / scored_tickets
        if scored_tickets
        else 0.0
    )

    return {
        "source_file": result.source_file,
        "total_records": result.total_records,
        "valid_records": result.valid_records,
        "invalid_records": result.invalid_records,
        "invalid_rules": {
            key: result.invalid_rules.get(key, 0)
            for key in (
                "missing_client_company",
                "invalid_category",
                "invalid_description",
                "invalid_agent",
                "invalid_status",
                "invalid_email",
                "closed_no_score",
                "score_out_of_range",
            )
        },
        "categories": {
            category: result.categories.get(category, 0) for category in VALID_CATEGORIES
        },
        "statuses": {
            status: result.statuses.get(status, 0) for status in VALID_STATUSES
        },
        "scores": {str(score): result.scores.get(score, 0) for score in range(1, 6)},
        "closed_tickets": closed_tickets,
        "scored_tickets": scored_tickets,
        "average_score": round(average_score, 2),
    }


def print_report(result: AnalysisResult) -> None:
    print("=" * 60)
    print("  NEXOVA - SUPPORT TICKET ANALYSIS")
    print(f"  Source file: {result.source_file}")
    print("=" * 60)
    print()
    print(f"TOTAL RECORDS IN FILE .......... {result.total_records}")
    print(f"  |- Valid records ................ {result.valid_records}")
    print(f"  '- Invalid / incomplete .......... {result.invalid_records}")
    print()
    print("INVALID RECORDS BREAKDOWN")

    active_invalid_rules = [
        (key, result.invalid_rules.get(key, 0))
        for key in (
            "missing_client_company",
            "invalid_category",
            "invalid_description",
            "invalid_agent",
            "invalid_status",
            "invalid_email",
            "closed_no_score",
            "score_out_of_range",
        )
        if result.invalid_rules.get(key, 0) > 0
    ]

    if not active_invalid_rules:
        print("  (No invalid records)")
    else:
        for index, (key, count) in enumerate(active_invalid_rules):
            branch = "|-" if index < len(active_invalid_rules) - 1 else "'-"
            label = INVALID_RULE_LABELS[key]
            print(f"  {branch} {label:.<32} {count}")

    print()
    print("BREAKDOWN BY CATEGORY (valid records)")
    for index, category in enumerate(VALID_CATEGORIES):
        count = result.categories.get(category, 0)
        branch = "|-" if index < len(VALID_CATEGORIES) - 1 else "'-"
        print(f"  {branch} {category:.<29} {count:>2}  ({_pct(count, result.valid_records)})")

    print()
    print("BREAKDOWN BY STATUS (valid records)")
    for index, status in enumerate(VALID_STATUSES):
        count = result.statuses.get(status, 0)
        branch = "|-" if index < len(VALID_STATUSES) - 1 else "'-"
        print(f"  {branch} {status:.<31} {count:>2}  ({_pct(count, result.valid_records)})")

    print()
    print("SATISFACTION INDEX (closed tickets)")
    closed_tickets = result.statuses.get("CLOSED", 0)
    scored_tickets = sum(result.scores.values())
    average_score = (
        sum(score * count for score, count in result.scores.items()) / scored_tickets
        if scored_tickets
        else 0.0
    )

    print(f"  Scored tickets: {scored_tickets} of {closed_tickets}")
    print(f"  Average score: {average_score:.2f} / 5.00")

    for score in range(1, 6):
        count = result.scores.get(score, 0)
        branch = "|-" if score < 5 else "'-"
        print(f"  {branch} Score {score} ({SCORE_LABELS[score]}) ... {count}")

    print()
    print("=" * 60)


def build_metrics_rows(result: AnalysisResult) -> list[tuple[str, int | str]]:
    closed_tickets = result.statuses.get("CLOSED", 0)
    scored_tickets = sum(result.scores.values())
    average_score = (
        sum(score * count for score, count in result.scores.items()) / scored_tickets
        if scored_tickets
        else 0.0
    )

    rows: list[tuple[str, int | str]] = [
        ("total_records", result.total_records),
        ("valid_records", result.valid_records),
        ("invalid_records", result.invalid_records),
    ]

    for key in (
        "missing_client_company",
        "invalid_category",
        "invalid_description",
        "invalid_agent",
        "invalid_status",
        "invalid_email",
        "closed_no_score",
        "score_out_of_range",
    ):
        rows.append((f"invalid_{key}", result.invalid_rules.get(key, 0)))

    for category in VALID_CATEGORIES:
        rows.append((f"category_{category}", result.categories.get(category, 0)))

    for status in VALID_STATUSES:
        rows.append((f"status_{status}", result.statuses.get(status, 0)))

    rows.extend(
        [
            ("closed_tickets", closed_tickets),
            ("scored_tickets", scored_tickets),
            ("average_score", f"{average_score:.2f}"),
        ]
    )

    for score in range(1, 6):
        rows.append((f"score_{score}", result.scores.get(score, 0)))

    return rows


def build_metrics_csv(result: AnalysisResult) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerows(build_metrics_rows(result))
    return buffer.getvalue()


def export_metrics(result: AnalysisResult, output_file: Path) -> None:
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        handle.write(build_metrics_csv(result))
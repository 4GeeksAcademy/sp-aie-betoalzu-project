from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar


VALID_CATEGORIES: ClassVar[list[str]] = ["TECHNICAL", "BILLING", "ACCESS", "HR_QUERY", "COMPLAINT"]
VALID_STATUSES: ClassVar[list[str]] = ["OPEN", "CLOSED", "DISCARDED"]
REQUIRED_HEADERS: ClassVar[list[str]] = [
    "ticket_id",
    "date",
    "client_company",
    "category",
    "description",
    "agent_id",
    "status",
    "customer_email",
    "satisfaction_score",
]

AGENT_PATTERN: re.Pattern = re.compile(r"^AGT-\d{2}$")

INVALID_RULE_LABELS: list[str] = [
    "missing_client_company",
    "invalid_category",
    "invalid_description",
    "invalid_agent",
    "invalid_status",
    "invalid_email",
    "closed_no_score",
    "score_out_of_range",
]

SCORE_LABELS: list[int] = [1, 2, 3, 4, 5]


class AnalysisError(Exception):
    """Base exception for analysis errors."""


class EmptyFileError(AnalysisError):
    """Raised when the CSV file is empty."""


class InvalidCsvFormatError(AnalysisError):
    """Raised when the CSV format is invalid (missing headers)."""


@dataclass
class IncidentInvalidRules:
    missing_client_company: int = 0
    invalid_category: int = 0
    invalid_description: int = 0
    invalid_agent: int = 0
    invalid_status: int = 0
    invalid_email: int = 0
    closed_no_score: int = 0
    score_out_of_range: int = 0


@dataclass
class AnalysisResult:
    source_file: str
    total_records: int
    valid_records: int
    invalid_records: int
    invalid_rules: IncidentInvalidRules
    categories: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, int] = field(default_factory=dict)
    scores: dict[int, int] = field(default_factory=dict)


def analyze_csv_stream(text_stream: io.StringIO, source_file: str) -> AnalysisResult:
    """Analyze a CSV text stream and return the analysis result.

    Args:
        text_stream: StringIO stream with CSV content (UTF-8 decoded).
        source_file: Original filename for reference.

    Returns:
        An AnalysisResult with validation metrics.

    Raises:
        EmptyFileError: If the CSV content is empty.
        InvalidCsvFormatError: If required headers are missing.
    """
    raw_text = text_stream.read()
    if not raw_text.strip():
        raise EmptyFileError("El fichero CSV esta vacio.")

    # Remove BOM if present
    if raw_text.startswith("\ufeff"):
        raw_text = raw_text[1:]

    reader = csv.reader(io.StringIO(raw_text))
    rows = list(reader)

    if not rows:
        raise EmptyFileError("El fichero CSV esta vacio o no contiene cabecera.")

    headers = [h.strip() for h in rows[0]]
    missing_headers = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing_headers:
        raise InvalidCsvFormatError(
            f"El fichero CSV no tiene el formato esperado. "
            f"Faltan columnas requeridas: {', '.join(missing_headers)}"
        )

    invalid_rules = IncidentInvalidRules()
    categories: dict[str, int] = {k: 0 for k in VALID_CATEGORIES}
    statuses: dict[str, int] = {k: 0 for k in VALID_STATUSES}
    scores: dict[int, int] = {k: 0 for k in SCORE_LABELS}

    total_records = 0
    valid_records = 0

    for row_values in rows[1:]:
        # Skip entirely empty rows
        if len(row_values) == 1 and row_values[0].strip() == "":
            continue

        total_records += 1
        row = dict(zip(headers, row_values))

        client_company = row.get("client_company", "").strip()
        category = row.get("category", "").strip()
        description = row.get("description", "").strip()
        agent_id = row.get("agent_id", "").strip()
        status = row.get("status", "").strip()
        customer_email = row.get("customer_email", "").strip()
        raw_score = row.get("satisfaction_score", "").strip()

        row_errors: list[str] = []

        if not client_company:
            row_errors.append("missing_client_company")
        if category not in VALID_CATEGORIES:
            row_errors.append("invalid_category")
        if len(description) < 5:
            row_errors.append("invalid_description")
        if not AGENT_PATTERN.match(agent_id):
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
                parsed_score = int(raw_score)
                if parsed_score < 1 or parsed_score > 5:
                    row_errors.append("score_out_of_range")
                else:
                    score_value = parsed_score
            except ValueError:
                row_errors.append("score_out_of_range")

        if row_errors:
            for rule in row_errors:
                setattr(invalid_rules, rule, getattr(invalid_rules, rule) + 1)
            continue

        valid_records += 1
        categories[category] += 1
        statuses[status] += 1
        if status == "CLOSED" and score_value is not None:
            scores[score_value] += 1

    return AnalysisResult(
        source_file=source_file,
        total_records=total_records,
        valid_records=valid_records,
        invalid_records=total_records - valid_records,
        invalid_rules=invalid_rules,
        categories=categories,
        statuses=statuses,
        scores=scores,
    )


def analyze_csv(file_path: Path) -> AnalysisResult:
    """Read a CSV file from disk and analyze it.

    Args:
        file_path: Path to the CSV file.

    Returns:
        An AnalysisResult with validation metrics.

    Raises:
        EmptyFileError: If the CSV content is empty.
        InvalidCsvFormatError: If required headers are missing.
    """
    with open(file_path, encoding="utf-8-sig") as f:
        text_stream = io.StringIO(f.read())

    return analyze_csv_stream(text_stream, file_path.name)


def build_summary(result: AnalysisResult) -> dict:
    """Build a human-readable summary dict from an analysis result.

    Returns a dictionary suitable for JSON serialization, including
    the average satisfaction score for closed tickets.
    """
    closed_tickets = result.statuses.get("CLOSED", 0)
    scored_tickets = sum(result.scores.values())
    average_score = (
        sum(int(score) * count for score, count in result.scores.items()) / scored_tickets
        if scored_tickets > 0
        else 0.0
    )

    return {
        "source_file": result.source_file,
        "total_records": result.total_records,
        "valid_records": result.valid_records,
        "invalid_records": result.invalid_records,
        "invalid_rules": {
            "missing_client_company": result.invalid_rules.missing_client_company,
            "invalid_category": result.invalid_rules.invalid_category,
            "invalid_description": result.invalid_rules.invalid_description,
            "invalid_agent": result.invalid_rules.invalid_agent,
            "invalid_status": result.invalid_rules.invalid_status,
            "invalid_email": result.invalid_rules.invalid_email,
            "closed_no_score": result.invalid_rules.closed_no_score,
            "score_out_of_range": result.invalid_rules.score_out_of_range,
        },
        "categories": result.categories,
        "statuses": result.statuses,
        "scores": {str(k): v for k, v in result.scores.items()},
        "closed_tickets": closed_tickets,
        "scored_tickets": scored_tickets,
        "average_score": round(average_score, 2),
    }


def print_report(result: AnalysisResult) -> None:
    """Print a human-readable report of the analysis to stdout."""
    summary = build_summary(result)

    print(f"\n{'=' * 50}")
    print(f"INCIDENT ANALYSIS REPORT")
    print(f"{'=' * 50}")
    print(f"Source file:       {summary['source_file']}")
    print(f"Total records:     {summary['total_records']}")
    print(f"Valid records:     {summary['valid_records']}")
    print(f"Invalid records:   {summary['invalid_records']}")
    print(f"\n--- Invalid Rules ---")
    for rule, count in summary["invalid_rules"].items():
        if count > 0:
            print(f"  {rule}: {count}")
    print(f"\n--- Categories ---")
    for cat, count in summary["categories"].items():
        if count > 0:
            print(f"  {cat}: {count}")
    print(f"\n--- Statuses ---")
    for st, count in summary["statuses"].items():
        if count > 0:
            print(f"  {st}: {count}")
    if summary["closed_tickets"] > 0:
        print(f"\nClosed tickets:    {summary['closed_tickets']}")
        print(f"Scored tickets:    {summary['scored_tickets']}")
        print(f"Average score:     {summary['average_score']}")
    print(f"{'=' * 50}\n")


def build_metrics_rows(result: AnalysisResult) -> list[tuple[str, str | int | float]]:
    """Build flat metric rows for CSV export."""
    summary = build_summary(result)
    rows: list[tuple[str, str | int | float]] = [
        ("total_records", summary["total_records"]),
        ("valid_records", summary["valid_records"]),
        ("invalid_records", summary["invalid_records"]),
    ]

    for rule, count in summary["invalid_rules"].items():
        rows.append((f"invalid_{rule}", count))

    for key, count in summary["categories"].items():
        rows.append((f"category_{key}", count))

    for key, count in summary["statuses"].items():
        rows.append((f"status_{key}", count))

    rows.append(("closed_tickets", summary["closed_tickets"]))
    rows.append(("scored_tickets", summary["scored_tickets"]))
    rows.append(("average_score", summary["average_score"]))

    for score, count in summary["scores"].items():
        rows.append((f"score_{score}", count))

    return rows


def build_metrics_csv(result: AnalysisResult) -> str:
    """Build a CSV string with analysis metrics."""
    rows = build_metrics_rows(result)
    body = "\n".join(f"{metric},{value}" for metric, value in rows)
    return f"metric,value\n{body}\n"


def export_metrics(result: AnalysisResult, output_path: Path) -> None:
    """Write the metrics CSV to a file."""
    csv_content = build_metrics_csv(result)
    output_path.write_text(csv_content, encoding="utf-8")
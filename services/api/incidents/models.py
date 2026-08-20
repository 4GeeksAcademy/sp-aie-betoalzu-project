"""Nexova Incident models — Centralized Incident Manager.

Follows the business schema defined in gestor-incidentes-centralizado.md:
  - Categories: technical_failure, process_error, client_complaint, candidate_issue,
                 staff_issue, sla_breach, data_quality, other
  - Statuses: open -> in_progress -> resolved | discarded
  - Origins: customer, branch, internal
  - Branches: central, valencia_operations, miami_office, remote
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IncidentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"


class IncidentCategory(str, Enum):
    TECHNICAL_FAILURE = "technical_failure"
    PROCESS_ERROR = "process_error"
    CLIENT_COMPLAINT = "client_complaint"
    CANDIDATE_ISSUE = "candidate_issue"
    STAFF_ISSUE = "staff_issue"
    SLA_BREACH = "sla_breach"
    DATA_QUALITY = "data_quality"
    OTHER = "other"


class IncidentOrigin(str, Enum):
    CUSTOMER = "customer"
    BRANCH = "branch"
    INTERNAL = "internal"


class IncidentBranch(str, Enum):
    CENTRAL = "central"
    VALENCIA_OPERATIONS = "valencia_operations"
    MIAMI_OFFICE = "miami_office"
    REMOTE = "remote"


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {IncidentStatus.IN_PROGRESS, IncidentStatus.DISCARDED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.RESOLVED, IncidentStatus.DISCARDED},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.DISCARDED: set(),
}

_TERMINAL_STATUSES = {IncidentStatus.RESOLVED, IncidentStatus.DISCARDED}

# ---------------------------------------------------------------------------
# Branch display names (bilingual)
# ---------------------------------------------------------------------------

BRANCH_DISPLAY: dict[IncidentBranch, dict[str, str]] = {
    IncidentBranch.CENTRAL: {"es": "Central — Sede Valencia", "en": "Central — Valencia HQ"},
    IncidentBranch.VALENCIA_OPERATIONS: {"es": "Valencia — Operaciones", "en": "Valencia — Operations"},
    IncidentBranch.MIAMI_OFFICE: {"es": "Miami Office", "en": "Miami Office"},
    IncidentBranch.REMOTE: {"es": "Remoto (sin sede fija)", "en": "Remote (no fixed office)"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    """Payload for creating a new incident."""

    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    title: str = Field(min_length=1, max_length=120)
    description: str | None = None
    category: IncidentCategory
    origin: IncidentOrigin
    branch: IncidentBranch = IncidentBranch.CENTRAL
    status: IncidentStatus = IncidentStatus.OPEN
    reported_by: str | None = Field(default=None, max_length=255)
    assigned_to: str | None = Field(default=None, max_length=255)
    ticket_id: str | None = Field(default=None, max_length=50)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title cannot be empty")
        return stripped


class IncidentUpdate(BaseModel):
    """Payload for updating an incident (partial)."""

    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True, extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    category: IncidentCategory | None = None
    origin: IncidentOrigin | None = None
    branch: IncidentBranch | None = None
    reported_by: str | None = None
    assigned_to: str | None = None
    ticket_id: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("title cannot be empty")
            return stripped
        return v


class IncidentStatusUpdate(BaseModel):
    """Payload for transitioning incident status."""

    status: IncidentStatus


class IncidentOut(BaseModel):
    """Safe output representation of an incident."""

    model_config = ConfigDict(use_enum_values=True)

    id: int
    title: str
    description: str | None = None
    category: str
    origin: str
    branch: str
    status: str
    reported_by: str | None = None
    assigned_to: str | None = None
    ticket_id: str | None = None
    created_at: str
    updated_at: str


class IncidentSummary(BaseModel):
    """Summary statistics for the dashboard."""

    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_branch: dict[str, int]
    by_origin: dict[str, int]
    open_oldest: str | None = None
    open_critical_count: int = 0
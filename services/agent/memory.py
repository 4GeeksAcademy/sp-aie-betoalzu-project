from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MemoryCategory = Literal[
    "escalation_procedure",
    "customer_preference",
    "incident_pattern",
]
APPROVER_ROLES = {"admin", "manager"}
ALLOWED_CATEGORIES = {
    "escalation_procedure",
    "customer_preference",
    "incident_pattern",
}
_PROHIBITED_TERMS = re.compile(
    r"\b(candidate|candidato|candidata|cv|curriculum|entrevista|"
    r"salario|sueldo|compensacion|remuneracion|headhunting|negociacion salarial)\b",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_INDIVIDUAL_TICKET = re.compile(
    r"\b(?:este|ese|unico|individual)\s+(?:ticket|incidente)\b|"
    r"\b(?:ticket|incidente)\s*(?:id|#|n[ºo.]?)?\s*[A-Z]{0,5}-?\d+\b",
    re.IGNORECASE,
)


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    business_area: Literal["support"] = "support"
    category: MemoryCategory
    customer_id: str | None = Field(default=None, max_length=120)
    subject: str = Field(min_length=3, max_length=160)
    fact: str = Field(min_length=8, max_length=600)
    reason: str = Field(min_length=3, max_length=240)
    source_reference: str | None = Field(default=None, max_length=240)

    @field_validator("customer_id", "subject", "fact", "reason", "source_reference")
    @classmethod
    def reject_blank_values(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Value cannot be blank.")
        return value

    @field_validator("customer_id")
    @classmethod
    def validate_customer_identifier(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}", value):
            raise ValueError("Customer scope must be an opaque identifier.")
        return value


class MemoryPermissionError(PermissionError):
    pass


class PendingProposalExists(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _subject_key(value: str) -> str:
    return " ".join(re.findall(r"\w+", _plain(value)))


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"\w+", _plain(value))
        if len(token) > 2
    }


def contains_prohibited_content(value: str) -> bool:
    return bool(
        _PROHIBITED_TERMS.search(value)
        or _EMAIL.search(value)
        or _PHONE.search(value)
    )


def validate_candidate(
    candidate: MemoryCandidate | dict[str, Any],
    *,
    origin_message: str,
    customer_id: str | None,
    allowed_references: set[str],
) -> MemoryCandidate | None:
    try:
        parsed = MemoryCandidate.model_validate(candidate)
    except ValidationError:
        return None

    fields = [
        parsed.customer_id or "",
        parsed.subject,
        parsed.fact,
        parsed.reason,
        parsed.source_reference or "",
    ]
    if any(contains_prohibited_content(value) for value in [origin_message, *fields]):
        return None
    if parsed.category == "customer_preference":
        if not customer_id or parsed.customer_id != customer_id:
            return None
    elif parsed.customer_id is not None and parsed.customer_id != customer_id:
        return None
    if _INDIVIDUAL_TICKET.search(parsed.subject) or _INDIVIDUAL_TICKET.search(parsed.fact):
        return None
    if parsed.source_reference not in allowed_references:
        parsed = parsed.model_copy(update={"source_reference": None})
    return parsed


class MemoryStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_memory (
                    memory_id TEXT PRIMARY KEY,
                    business_area TEXT NOT NULL,
                    category TEXT NOT NULL,
                    customer_id TEXT,
                    subject TEXT NOT NULL,
                    subject_key TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    verification_status TEXT NOT NULL
                        CHECK (verification_status IN ('verified', 'pending_verification')),
                    source_reference TEXT,
                    approved_by_actor_id TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    business_area TEXT NOT NULL,
                    category TEXT NOT NULL,
                    customer_id TEXT,
                    candidate_json TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    UNIQUE (conversation_id)
                );
                CREATE TABLE IF NOT EXISTS memory_audit (
                    event_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    memory_id TEXT,
                    action TEXT NOT NULL,
                    business_area TEXT NOT NULL,
                    category TEXT NOT NULL,
                    customer_id TEXT,
                    conversation_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_memory_area_customer
                    ON agent_memory (business_area, customer_id, expires_at);
                CREATE INDEX IF NOT EXISTS ix_memory_audit_created
                    ON memory_audit (created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS ux_memory_scope_subject
                    ON agent_memory (
                        business_area, category, COALESCE(customer_id, ''), subject_key
                    );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _source_hash(origin_message: str) -> str:
        return hashlib.sha256(origin_message.strip().encode("utf-8")).hexdigest()

    def retrieve(
        self,
        query: str,
        *,
        business_area: str,
        customer_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if business_area != "support":
            return []
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        now = _timestamp(_now())
        max_results = max(1, min(limit, 5))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_memory
                WHERE business_area = ?
                  AND expires_at > ?
                  AND (customer_id IS NULL OR customer_id = ?)
                """,
                (business_area, now, customer_id),
            ).fetchall()
            ranked: list[tuple[int, sqlite3.Row]] = []
            for row in rows:
                searchable = f"{row['subject']} {row['fact']} {row['category']}"
                score = len(query_tokens.intersection(_tokens(searchable)))
                if score:
                    ranked.append((score, row))
            ranked.sort(
                key=lambda item: (
                    item[0],
                    item[1]["approved_at"],
                ),
                reverse=True,
            )
            selected = ranked[:max_results]
            if selected:
                refresh = _timestamp(_now() + timedelta(days=180))
                used_at = _timestamp(_now())
                connection.executemany(
                    """
                    UPDATE agent_memory
                    SET last_used_at = ?, expires_at = ?
                    WHERE memory_id = ?
                    """,
                    [(used_at, refresh, row["memory_id"]) for _, row in selected],
                )
        return [
            {
                "memory_id": row["memory_id"],
                "business_area": row["business_area"],
                "category": row["category"],
                "customer_id": row["customer_id"],
                "subject": row["subject"],
                "fact": row["fact"],
                "verification_status": row["verification_status"],
                "source_reference": row["source_reference"],
                "approved_by_actor_id": row["approved_by_actor_id"],
                "approved_at": row["approved_at"],
            }
            for _, row in selected
        ]

    def propose(
        self,
        candidate: MemoryCandidate,
        *,
        origin_message: str,
        conversation_id: str,
        actor_id: str,
        actor_role: str,
    ) -> str:
        self._require_approver(actor_role)
        self.consolidate()
        checked = validate_candidate(
            candidate,
            origin_message=origin_message,
            customer_id=candidate.customer_id,
            allowed_references=(
                {candidate.source_reference} if candidate.source_reference else set()
            ),
        )
        if checked is None:
            raise ValueError("Memory candidate failed deterministic validation.")
        candidate = checked
        proposal_id = str(uuid4())
        now = _now()
        created_at = _timestamp(now)
        expires_at = _timestamp(now + timedelta(days=7))
        source_hash = self._source_hash(origin_message)
        stored_candidate = candidate.model_dump()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO memory_proposals (
                        proposal_id, conversation_id, actor_id, business_area,
                        category, customer_id, candidate_json, source_hash,
                        created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proposal_id,
                        conversation_id,
                        actor_id,
                        candidate.business_area,
                        candidate.category,
                        candidate.customer_id,
                        json.dumps(stored_candidate, ensure_ascii=False),
                        source_hash,
                        created_at,
                        expires_at,
                    ),
                )
                self._audit(
                    connection,
                    proposal_id=proposal_id,
                    action="proposed",
                    candidate=candidate,
                    conversation_id=conversation_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    source_hash=source_hash,
                    created_at=created_at,
                )
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                if "UNIQUE constraint failed: memory_proposals.conversation_id" in str(exc):
                    raise PendingProposalExists(
                        "A proposal is already pending for this conversation."
                    ) from exc
                raise
        return proposal_id

    def get_pending(
        self,
        *,
        conversation_id: str,
        actor_id: str,
        actor_role: str,
    ) -> dict[str, Any] | None:
        self._require_approver(actor_role)
        self.expire_proposals()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT proposal_id, candidate_json, created_at, expires_at
                FROM memory_proposals
                WHERE conversation_id = ? AND actor_id = ?
                """,
                (conversation_id, actor_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "proposal_id": row["proposal_id"],
            "candidate": json.loads(row["candidate_json"]),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }

    def resolve(
        self,
        proposal_id: str,
        *,
        decision: Literal["approve", "reject", "discard", "edit"],
        conversation_id: str,
        actor_id: str,
        actor_role: str,
        origin_message: str,
        edited_candidate: MemoryCandidate | None = None,
    ) -> str | None:
        self._require_approver(actor_role)
        self.consolidate()
        now = _now()
        created_at = _timestamp(now)
        source_hash = self._source_hash(origin_message)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            proposal = connection.execute(
                """
                SELECT * FROM memory_proposals
                WHERE proposal_id = ? AND conversation_id = ? AND actor_id = ?
                """,
                (proposal_id, conversation_id, actor_id),
            ).fetchone()
            if proposal is None:
                connection.rollback()
                return None
            if proposal["expires_at"] <= created_at:
                self._audit_row(
                    connection,
                    proposal_id=proposal_id,
                    action="expired",
                    business_area=proposal["business_area"],
                    category=proposal["category"],
                    customer_id=proposal["customer_id"],
                    conversation_id=conversation_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    source_hash=proposal["source_hash"],
                    created_at=created_at,
                )
                connection.execute(
                    "DELETE FROM memory_proposals WHERE proposal_id = ?",
                    (proposal_id,),
                )
                return None

            proposed = MemoryCandidate.model_validate(
                json.loads(proposal["candidate_json"])
            )
            memory_id: str | None = None
            if decision == "approve":
                memory_id = self._upsert_memory(
                    connection,
                    proposed,
                    actor_id=actor_id,
                    now=now,
                )
                self._audit(
                    connection,
                    proposal_id=proposal_id,
                    memory_id=memory_id,
                    action="approved",
                    candidate=proposed,
                    conversation_id=conversation_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    source_hash=proposal["source_hash"],
                    created_at=created_at,
                )
            elif decision == "edit":
                if edited_candidate is None:
                    raise ValueError("An edited candidate is required.")
                self._audit(
                    connection,
                    proposal_id=proposal_id,
                    action="edited",
                    candidate=proposed,
                    conversation_id=conversation_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    source_hash=proposal["source_hash"],
                    created_at=created_at,
                )
            else:
                self._audit(
                    connection,
                    proposal_id=proposal_id,
                    action="rejected" if decision == "reject" else "discarded",
                    candidate=proposed,
                    conversation_id=conversation_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    source_hash=proposal["source_hash"],
                    created_at=created_at,
                )
            connection.execute(
                "DELETE FROM memory_proposals WHERE proposal_id = ?",
                (proposal_id,),
            )
            if decision == "edit":
                assert edited_candidate is not None
                replacement_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO memory_proposals (
                        proposal_id, conversation_id, actor_id, business_area,
                        category, customer_id, candidate_json, source_hash,
                        created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        replacement_id,
                        conversation_id,
                        actor_id,
                        edited_candidate.business_area,
                        edited_candidate.category,
                        edited_candidate.customer_id,
                        json.dumps(
                            edited_candidate.model_dump(),
                            ensure_ascii=False,
                        ),
                        source_hash,
                        created_at,
                        _timestamp(now + timedelta(days=7)),
                    ),
                )
                self._audit(
                    connection,
                    proposal_id=replacement_id,
                    action="proposed",
                    candidate=edited_candidate,
                    conversation_id=conversation_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    source_hash=source_hash,
                    created_at=created_at,
                )
                result_id = replacement_id
            elif decision == "approve":
                result_id = memory_id
            else:
                result_id = None
        return result_id

    def consolidate(self, *, now: datetime | None = None) -> dict[str, int]:
        current = now or _now()
        timestamp = _timestamp(current)
        audit_cutoff = _timestamp(current - timedelta(days=365))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            expired_proposals = connection.execute(
                "SELECT * FROM memory_proposals WHERE expires_at <= ?",
                (timestamp,),
            ).fetchall()
            for proposal in expired_proposals:
                self._audit_row(
                    connection,
                    proposal_id=proposal["proposal_id"],
                    action="expired",
                    business_area=proposal["business_area"],
                    category=proposal["category"],
                    customer_id=proposal["customer_id"],
                    conversation_id=proposal["conversation_id"],
                    actor_id=proposal["actor_id"],
                    actor_role="system",
                    source_hash=proposal["source_hash"],
                    created_at=timestamp,
                )
            connection.execute(
                "DELETE FROM memory_proposals WHERE expires_at <= ?",
                (timestamp,),
            )
            expired_memories = connection.execute(
                "SELECT memory_id FROM agent_memory WHERE expires_at <= ?",
                (timestamp,),
            ).fetchall()
            for row in expired_memories:
                connection.execute(
                    """
                    INSERT INTO memory_audit (
                        event_id, proposal_id, memory_id, action, business_area,
                        category, customer_id, conversation_id, actor_id,
                        actor_role, source_hash, created_at
                    )
                    SELECT ?, '', memory_id, 'memory_expired', business_area,
                        category, customer_id, '', approved_by_actor_id,
                        'system', '', ?
                    FROM agent_memory WHERE memory_id = ?
                    """,
                    (str(uuid4()), timestamp, row["memory_id"]),
                )
            connection.execute("DELETE FROM agent_memory WHERE expires_at <= ?", (timestamp,))
            connection.execute("DELETE FROM memory_audit WHERE created_at < ?", (audit_cutoff,))
            return {
                "expired_proposals": len(expired_proposals),
                "expired_memories": len(expired_memories),
            }

    def expire_proposals(self) -> int:
        timestamp = _timestamp(_now())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            expired = connection.execute(
                "SELECT * FROM memory_proposals WHERE expires_at <= ?",
                (timestamp,),
            ).fetchall()
            for proposal in expired:
                self._audit_row(
                    connection,
                    proposal_id=proposal["proposal_id"],
                    action="expired",
                    business_area=proposal["business_area"],
                    category=proposal["category"],
                    customer_id=proposal["customer_id"],
                    conversation_id=proposal["conversation_id"],
                    actor_id=proposal["actor_id"],
                    actor_role="system",
                    source_hash=proposal["source_hash"],
                    created_at=timestamp,
                )
            connection.execute(
                "DELETE FROM memory_proposals WHERE expires_at <= ?",
                (timestamp,),
            )
            return len(expired)

    @staticmethod
    def _require_approver(actor_role: str) -> None:
        if actor_role not in APPROVER_ROLES:
            raise MemoryPermissionError("This role cannot write support memories.")

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        *,
        proposal_id: str,
        action: str,
        candidate: MemoryCandidate,
        conversation_id: str,
        actor_id: str,
        actor_role: str,
        source_hash: str,
        created_at: str,
        memory_id: str | None = None,
    ) -> None:
        MemoryStore._audit_row(
            connection,
            proposal_id=proposal_id,
            memory_id=memory_id,
            action=action,
            business_area=candidate.business_area,
            category=candidate.category,
            customer_id=candidate.customer_id,
            conversation_id=conversation_id,
            actor_id=actor_id,
            actor_role=actor_role,
            source_hash=source_hash,
            created_at=created_at,
        )

    @staticmethod
    def _audit_row(
        connection: sqlite3.Connection,
        *,
        proposal_id: str,
        action: str,
        business_area: str,
        category: str,
        customer_id: str | None,
        conversation_id: str,
        actor_id: str,
        actor_role: str,
        source_hash: str,
        created_at: str,
        memory_id: str | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO memory_audit (
                event_id, proposal_id, memory_id, action, business_area,
                category, customer_id, conversation_id, actor_id, actor_role,
                source_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                proposal_id,
                memory_id,
                action,
                business_area,
                category,
                customer_id,
                conversation_id,
                actor_id,
                actor_role,
                source_hash,
                created_at,
            ),
        )

    @staticmethod
    def _upsert_memory(
        connection: sqlite3.Connection,
        candidate: MemoryCandidate,
        *,
        actor_id: str,
        now: datetime,
    ) -> str:
        memory_id = str(uuid4())
        timestamp = _timestamp(now)
        expiry = _timestamp(now + timedelta(days=180))
        row = connection.execute(
            """
            SELECT memory_id FROM agent_memory
            WHERE business_area = ? AND category = ?
              AND customer_id IS ? AND subject_key = ?
            """,
            (
                candidate.business_area,
                candidate.category,
                candidate.customer_id,
                _subject_key(candidate.subject),
            ),
        ).fetchone()
        verification_status = (
            "verified" if candidate.source_reference else "pending_verification"
        )
        if row:
            memory_id = row["memory_id"]
            connection.execute(
                """
                UPDATE agent_memory SET subject = ?, fact = ?,
                    verification_status = ?, source_reference = ?,
                    approved_by_actor_id = ?, approved_at = ?,
                    last_used_at = ?, expires_at = ?
                WHERE memory_id = ?
                """,
                (
                    candidate.subject,
                    candidate.fact,
                    verification_status,
                    candidate.source_reference,
                    actor_id,
                    timestamp,
                    timestamp,
                    expiry,
                    memory_id,
                ),
            )
            return memory_id
        connection.execute(
            """
            INSERT INTO agent_memory (
                memory_id, business_area, category, customer_id, subject,
                subject_key, fact, verification_status, source_reference,
                approved_by_actor_id, approved_at, last_used_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                candidate.business_area,
                candidate.category,
                candidate.customer_id,
                candidate.subject,
                _subject_key(candidate.subject),
                candidate.fact,
                verification_status,
                candidate.source_reference,
                actor_id,
                timestamp,
                timestamp,
                expiry,
            ),
        )
        return memory_id

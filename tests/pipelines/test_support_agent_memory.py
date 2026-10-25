from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from services.agent.memory import (
    MemoryCandidate,
    MemoryPermissionError,
    MemoryStore,
    validate_candidate,
)
from services.agent.support import SupportAgent

BASE_CANDIDATE = {
    "business_area": "support",
    "category": "escalation_procedure",
    "customer_id": None,
    "subject": "Asignación de tickets urgentes premium",
    "fact": "Los tickets urgentes premium se asignan directamente a un agente senior.",
    "reason": "Es una regla operativa repetible.",
    "source_reference": None,
}
ORIGIN = "La regla general de asignación cambió este mes."


def _approved_store(tmp_path) -> MemoryStore:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    proposal_id = store.propose(
        MemoryCandidate.model_validate(BASE_CANDIDATE),
        origin_message=ORIGIN,
        conversation_id="approval-test",
        actor_id="manager-1",
        actor_role="manager",
    )
    assert store.retrieve(
        "tickets urgentes premium", business_area="support"
    ) == []
    store.resolve(
        proposal_id,
        decision="approve",
        conversation_id="approval-test",
        actor_id="manager-1",
        actor_role="manager",
        origin_message="Sí, confirmo.",
    )
    return store


def _agent(tmp_path, *, reply_fn, intent_classifier):
    return SupportAgent(
        tmp_path / "checkpoints.sqlite3",
        retrieve_fn=lambda _question: [],
        structured_generate_fn=reply_fn,
        intent_classifier=intent_classifier,
    )


def test_proposal_requires_approval_and_survives_reopen(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    proposal_id = store.propose(
        MemoryCandidate.model_validate(BASE_CANDIDATE),
        origin_message=ORIGIN,
        conversation_id="conversation-a",
        actor_id="manager-1",
        actor_role="manager",
    )
    assert store.retrieve("tickets urgentes premium", business_area="support") == []
    assert store.get_pending(
        conversation_id="conversation-a",
        actor_id="manager-1",
        actor_role="manager",
    )["proposal_id"] == proposal_id

    store.resolve(
        proposal_id,
        decision="approve",
        conversation_id="conversation-a",
        actor_id="manager-1",
        actor_role="manager",
        origin_message="Sí, confirmo.",
    )
    reopened = MemoryStore(tmp_path / "memory.sqlite3")
    memory = reopened.retrieve("tickets urgentes premium", business_area="support")
    assert len(memory) == 1
    assert memory[0]["fact"] == BASE_CANDIDATE["fact"]
    assert memory[0]["verification_status"] == "pending_verification"
    with sqlite3.connect(reopened.database_path) as connection:
        actions = [
            row[0]
            for row in connection.execute(
                "SELECT action FROM memory_audit ORDER BY created_at, rowid"
            )
        ]
    assert actions == ["proposed", "approved"]


def test_rejection_is_audited_without_changing_active_memory(tmp_path) -> None:
    store = _approved_store(tmp_path)
    before = store.retrieve("tickets urgentes premium", business_area="support")
    proposal_id = store.propose(
        MemoryCandidate.model_validate({
            **BASE_CANDIDATE,
            "fact": "Los tickets urgentes premium se asignan a la cola general.",
        }),
        origin_message=ORIGIN,
        conversation_id="conversation-reject",
        actor_id="manager-1",
        actor_role="manager",
    )
    store.resolve(
        proposal_id,
        decision="reject",
        conversation_id="conversation-reject",
        actor_id="manager-1",
        actor_role="manager",
        origin_message="No, rechazar.",
    )

    assert store.retrieve("tickets urgentes premium", business_area="support") == before
    with sqlite3.connect(store.database_path) as connection:
        actions = [
            row[0]
            for row in connection.execute(
                "SELECT action FROM memory_audit ORDER BY created_at, rowid"
            )
        ]
    assert actions == ["proposed", "approved", "proposed", "rejected"]


def test_agent_runs_approval_and_later_retrieves_memory(tmp_path) -> None:
    replies = [
        {
            "answer": "La base documental no contiene más detalle.",
            "propuesta_memoria": BASE_CANDIDATE,
        },
        {
            "answer": "La base documental no contiene más detalle.",
            "propuesta_memoria": None,
        },
    ]

    def reply_fn(_question, memories, retrieved, *, fixed_answer, customer_id):
        return {
            "answer": fixed_answer or "Respuesta documental.",
            "propuesta_memoria": replies.pop(0)["propuesta_memoria"],
        }

    def intent_classifier(_message, _candidate):
        return {
            "intent": "approve",
            "continuation_question": None,
            "edited_candidate": None,
        }

    agent = _agent(
        tmp_path,
        reply_fn=reply_fn,
        intent_classifier=intent_classifier,
    )
    try:
        first = agent.invoke(
            "¿Cuál es el procedimiento para escalar tickets premium?",
            run_id="proposal-run",
            conversation_id="conversation-1",
            actor_id="manager-1",
            actor_role="manager",
        )
        assert "¿Quieres que lo recuerde?" in first["answer"]
        assert agent.memory_store.retrieve(
            "tickets urgentes premium", business_area="support"
        ) == []
        approved = agent.invoke(
            "Sí, confirmo.",
            run_id="approval-run",
            conversation_id="conversation-1",
            actor_id="manager-1",
            actor_role="manager",
        )
        assert approved["answer"] == "Recuerdo aprobado y guardado."

        later = agent.invoke(
            "¿Cuál es el procedimiento para escalar tickets premium?",
            run_id="later-run",
            conversation_id="conversation-1",
            actor_id="manager-1",
            actor_role="manager",
        )
        assert later["answer"]
        receive = next(
            event for event in agent.get_trace("later-run")
            if event["node_name"] == "receive_question"
            and event["status"] == "completed"
        )
        assert receive["output"]["memory_count"] == 1
        assert receive["output"]["memory_references"][0]["category"] == (
            "escalation_procedure"
        )
    finally:
        agent.close()


def test_agent_rejects_and_discards_pending_on_new_topic(tmp_path) -> None:
    responses = [
        {"answer": "Respuesta fija.", "propuesta_memoria": BASE_CANDIDATE},
        {"answer": "Respuesta a la nueva consulta.", "propuesta_memoria": None},
    ]

    def reply_fn(_question, _context, _memories, *, fixed_answer, customer_id):
        response = responses.pop(0)
        return {
            "answer": fixed_answer or response["answer"],
            "propuesta_memoria": response["propuesta_memoria"],
        }

    agent = SupportAgent(
        tmp_path / "checkpoints.sqlite3",
        retrieve_fn=lambda _question: [],
        structured_generate_fn=reply_fn,
        intent_classifier=lambda _message, _candidate: {
            "intent": "new_topic",
            "continuation_question": None,
            "edited_candidate": None,
        },
    )
    try:
        agent.invoke(
            "¿Cuál es el procedimiento para escalar tickets premium?",
            run_id="pending-run",
            conversation_id="conversation-2",
            actor_id="manager-1",
            actor_role="manager",
        )
        result = agent.invoke(
            "¿Cuál es el precio del servicio?",
            run_id="topic-run",
            conversation_id="conversation-2",
            actor_id="manager-1",
            actor_role="manager",
        )
        assert result["question"] == "¿Cuál es el precio del servicio?"
        assert agent.get_state("topic-run").values["question"] == (
            "¿Cuál es el precio del servicio?"
        )
        assert agent.memory_store.get_pending(
            conversation_id="conversation-2",
            actor_id="manager-1",
            actor_role="manager",
        ) is None
        assert agent.memory_store.retrieve(
            "tickets urgentes premium", business_area="support"
        ) == []
    finally:
        agent.close()


def test_edit_creates_one_new_pending_proposal_without_approval(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    proposal_id = store.propose(
        MemoryCandidate.model_validate(BASE_CANDIDATE),
        origin_message=ORIGIN,
        conversation_id="edit-conversation",
        actor_id="manager-1",
        actor_role="manager",
    )
    edited = MemoryCandidate.model_validate({
        **BASE_CANDIDATE,
        "fact": "Los tickets premium urgentes se asignan directamente a un agente senior.",
    })
    replacement = store.resolve(
        proposal_id,
        decision="edit",
        conversation_id="edit-conversation",
        actor_id="manager-1",
        actor_role="manager",
        origin_message="Corrige el orden de las palabras.",
        edited_candidate=edited,
    )
    pending = store.get_pending(
        conversation_id="edit-conversation",
        actor_id="manager-1",
        actor_role="manager",
    )
    assert replacement != proposal_id
    assert pending["proposal_id"] == replacement
    assert pending["candidate"]["fact"] == edited.fact
    assert store.retrieve("tickets urgentes premium", business_area="support") == []


def test_expiry_deduplication_and_audit_retention(tmp_path) -> None:
    store = _approved_store(tmp_path)
    proposal_id = store.propose(
        MemoryCandidate.model_validate({
            **BASE_CANDIDATE,
            "subject": "Asignación de tickets urgentes premium",
            "fact": "Los tickets premium urgentes pasan a una persona senior.",
        }),
        origin_message=ORIGIN,
        conversation_id="dedupe",
        actor_id="manager-1",
        actor_role="manager",
    )
    store.resolve(
        proposal_id,
        decision="approve",
        conversation_id="dedupe",
        actor_id="manager-1",
        actor_role="manager",
        origin_message="Confirmo la corrección.",
    )
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0] == 1
        connection.execute(
            "UPDATE agent_memory SET expires_at = ?",
            ((datetime.now(UTC) - timedelta(days=1)).isoformat(),),
        )
        connection.execute(
            "UPDATE memory_audit SET created_at = ? WHERE action = 'rejected'",
            ((datetime.now(UTC) - timedelta(days=366)).isoformat(),),
        )

    assert store.retrieve("tickets urgentes premium", business_area="support") == []
    result = store.consolidate()
    assert result["expired_memories"] == 1
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0] == 0
        actions = [row[0] for row in connection.execute("SELECT action FROM memory_audit")]
    assert "memory_expired" in actions
    assert "rejected" not in actions


def test_customer_scope_prohibited_content_and_role_permissions(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    customer_candidate = MemoryCandidate.model_validate({
        **BASE_CANDIDATE,
        "category": "customer_preference",
        "customer_id": "customer-17",
        "subject": "Confirmación de cierre por email",
        "fact": "La empresa solicita confirmación por email antes de cerrar tickets.",
    })
    proposal_id = store.propose(
        customer_candidate,
        origin_message="Una preferencia recurrente de la cuenta.",
        conversation_id="customer",
        actor_id="manager-1",
        actor_role="manager",
    )
    store.resolve(
        proposal_id,
        decision="approve",
        conversation_id="customer",
        actor_id="manager-1",
        actor_role="manager",
        origin_message="Confirmo.",
    )
    assert store.retrieve(
        "confirmación cierre email",
        business_area="support",
        customer_id=None,
    ) == []
    assert len(store.retrieve(
        "confirmación cierre email",
        business_area="support",
        customer_id="customer-17",
    )) == 1
    assert store.retrieve(
        "confirmación cierre email",
        business_area="support",
        customer_id="customer-99",
    ) == []

    assert validate_candidate(
        BASE_CANDIDATE,
        origin_message="Es una corrección para un candidato con CV.",
        customer_id=None,
        allowed_references=set(),
    ) is None
    with pytest.raises(MemoryPermissionError):
        store.propose(
            MemoryCandidate.model_validate(BASE_CANDIDATE),
            origin_message=ORIGIN,
            conversation_id="unauthorized",
            actor_id="user-1",
            actor_role="user",
        )


def test_memory_and_audit_commit_atomically(tmp_path, monkeypatch) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    proposal_id = store.propose(
        MemoryCandidate.model_validate(BASE_CANDIDATE),
        origin_message=ORIGIN,
        conversation_id="atomic",
        actor_id="manager-1",
        actor_role="manager",
    )

    def fail_audit(*_args, **_kwargs):
        raise sqlite3.IntegrityError("audit insert failed")

    monkeypatch.setattr(store, "_audit", fail_audit)
    with pytest.raises(sqlite3.IntegrityError, match="audit insert failed"):
        store.resolve(
            proposal_id,
            decision="approve",
            conversation_id="atomic",
            actor_id="manager-1",
            actor_role="manager",
            origin_message="Confirmo.",
        )

    assert store.retrieve("tickets urgentes premium", business_area="support") == []
    assert store.get_pending(
        conversation_id="atomic",
        actor_id="manager-1",
        actor_role="manager",
    )["proposal_id"] == proposal_id


def test_expired_proposal_is_removed_and_only_metadata_is_audited(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    proposal_id = store.propose(
        MemoryCandidate.model_validate(BASE_CANDIDATE),
        origin_message=ORIGIN,
        conversation_id="expired",
        actor_id="manager-1",
        actor_role="manager",
    )
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE memory_proposals SET expires_at = ? WHERE proposal_id = ?",
            ((datetime.now(UTC) - timedelta(days=1)).isoformat(), proposal_id),
        )

    assert store.get_pending(
        conversation_id="expired",
        actor_id="manager-1",
        actor_role="manager",
    ) is None
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM memory_proposals"
        ).fetchone()[0] == 0
        audit = connection.execute(
            "SELECT action, category, source_hash FROM memory_audit WHERE action = 'expired'"
        ).fetchone()
    assert audit[0] == "expired"
    assert audit[1] == "escalation_procedure"
    assert ORIGIN not in json.dumps(audit)

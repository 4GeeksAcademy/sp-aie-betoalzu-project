from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from services.agent.support import (
    SupportAgent,
    route_after_receive,
    route_after_retrieve,
)


@pytest.fixture
def create_agent(tmp_path) -> Callable[..., SupportAgent]:
    agents: list[SupportAgent] = []

    def create(**kwargs: Any) -> SupportAgent:
        agent = SupportAgent(tmp_path / "agent.sqlite3", **kwargs)
        agents.append(agent)
        return agent

    yield create
    for agent in agents:
        agent.close()


def test_conditional_routes_choose_expected_nodes() -> None:
    assert route_after_receive({"error": None}) == "retrieve_context"
    assert route_after_receive({"error": "question_required"}) == "end"
    assert route_after_retrieve({"context": [{"text": "evidence"}]}) == "generate_response"
    assert route_after_retrieve({"context": []}) == "answer_without_context"


def test_compiled_graph_connects_every_route_to_an_exit(
    create_agent: Callable[..., SupportAgent],
) -> None:
    agent = create_agent(retrieve_fn=lambda _question: [], generate_fn=lambda _q, _c: "")
    graph = agent.graph.get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert ("__start__", "receive_question") in edges
    assert ("receive_question", "retrieve_context") in edges
    assert ("receive_question", "__end__") in edges
    assert ("retrieve_context", "generate_response") in edges
    assert ("retrieve_context", "answer_without_context") in edges
    assert ("generate_response", "__end__") in edges
    assert ("answer_without_context", "__end__") in edges


def test_valid_question_retrieves_then_generates_and_persists_state(
    create_agent: Callable[..., SupportAgent],
) -> None:
    retrieve_fn = Mock(return_value=[{
        "source_document": "nexova-pricing-model",
        "section": "Honorarios",
        "text": "La tarifa estándar es del 22%.",
    }])
    generate_fn = Mock(return_value="La tarifa es del 22%.")
    agent = create_agent(retrieve_fn=retrieve_fn, generate_fn=generate_fn)

    with patch("data_project.pipelines.rag.query") as query_fn:
        result = agent.invoke("  ¿Cuál es la tarifa?  ")

    assert result["answer"] == "La tarifa es del 22%."
    assert result["error"] is None
    retrieve_fn.assert_called_once_with("¿Cuál es la tarifa?")
    generate_fn.assert_called_once_with(
        "¿Cuál es la tarifa?",
        [{
            "source_document": "nexova-pricing-model",
            "section": "Honorarios",
            "text": "La tarifa estándar es del 22%.",
        }],
    )
    query_fn.assert_not_called()
    state = agent.get_state(result["run_id"])
    assert state.values["answer"] == result["answer"]
    assert state.values["question"] == "  ¿Cuál es la tarifa?  "
    events = agent.get_trace(result["run_id"])
    completed_nodes = [
        event["node_name"]
        for event in events
        if event["status"] == "completed"
    ]
    assert completed_nodes == [
        "receive_question",
        "retrieve_context",
        "generate_response",
    ]
    retrieval_event = next(
        event for event in events
        if event["node_name"] == "retrieve_context"
        and event["status"] == "completed"
    )
    assert retrieval_event["output"]["references"] == [
        {"source_document": "nexova-pricing-model", "section": "Honorarios"}
    ]
    assert "text" not in str(retrieval_event["output"])

    database_path = agent.database_path
    agent.close()
    reopened_agent = SupportAgent(
        database_path,
        retrieve_fn=retrieve_fn,
        generate_fn=generate_fn,
    )
    try:
        recovered_state = reopened_agent.get_state(result["run_id"])
        assert recovered_state.values["answer"] == result["answer"]
    finally:
        reopened_agent.close()


def test_empty_question_skips_retrieval_and_generation(
    create_agent: Callable[..., SupportAgent],
) -> None:
    retrieve_fn = Mock(return_value=[])
    generate_fn = Mock()
    agent = create_agent(
        retrieve_fn=retrieve_fn,
        generate_fn=generate_fn,
    )

    result = agent.invoke("   ")

    assert result["error"] == "question_required"
    retrieve_fn.assert_not_called()
    generate_fn.assert_not_called()
    assert [event["node_name"] for event in agent.get_trace(result["run_id"])
            if event["status"] == "completed"] == ["receive_question"]


def test_empty_context_abstains_without_generation(
    create_agent: Callable[..., SupportAgent],
) -> None:
    retrieve_fn = Mock(return_value=[])
    generate_fn = Mock()
    agent = create_agent(
        retrieve_fn=retrieve_fn,
        generate_fn=generate_fn,
    )

    result = agent.invoke("¿Cuál es el horario de atención?")

    assert "base de conocimiento" in result["answer"].lower()
    retrieve_fn.assert_called_once_with("¿Cuál es el horario de atención?")
    generate_fn.assert_not_called()
    assert [event["node_name"] for event in agent.get_trace(result["run_id"])
            if event["status"] == "completed"] == [
        "receive_question",
        "retrieve_context",
        "answer_without_context",
    ]


def test_node_failure_is_traced_without_exception_details(tmp_path) -> None:
    agent = SupportAgent(
        tmp_path / "agent.sqlite3",
        retrieve_fn=lambda _question: (_ for _ in ()).throw(
            RuntimeError("provider secret should not be recorded")
        ),
    )

    run_id = str(UUID("d70d8c51-f034-47e9-bc22-86802ebf7331"))
    with patch("services.agent.support.uuid4", return_value=UUID(run_id)):
        with pytest.raises(RuntimeError, match="provider secret"):
            agent.invoke("¿Precio?")

    try:
        events = agent.get_trace(run_id)
        failure = next(event for event in events if event["status"] == "failed")
        assert failure["output"] == {
            "source": "rag", "outcome": "failed", "error": "node_failed",
        }
        assert "provider secret" not in str(events)
    finally:
        agent.close()


def test_incident_graph_skips_rag_and_records_source_result(create_agent) -> None:
    from services.agent.tools import IncidentQuery, IncidentResult

    incidents_fn = Mock(return_value=IncidentResult(status="not_found"))
    retrieve_fn = Mock()
    generate_fn = Mock()
    agent = create_agent(
        incidents_fn=incidents_fn, retrieve_fn=retrieve_fn, generate_fn=generate_fn,
    )
    result = agent.invoke("¿Cuál es el estado del ticket 17?")

    incidents_fn.assert_called_once_with(IncidentQuery(incident_id=17))
    retrieve_fn.assert_not_called()
    generate_fn.assert_not_called()
    assert "no puedo confirmar su estado" in result["answer"]
    events = agent.get_trace(result["run_id"])
    assert [event["node_name"] for event in events if event["status"] == "completed"] == [
        "receive_question", "consult_incidents", "compose_response",
    ]
    source_event = next(event for event in events if event["node_name"] == "consult_incidents"
                        and event["status"] == "completed")
    assert source_event["output"]["source"] == "incidents"
    assert source_event["output"]["outcome"] == "not_found"


def test_mixed_graph_combines_confirmed_incident_with_documentation(create_agent) -> None:
    from services.agent.tools import IncidentResult
    from services.api.incidents.models import IncidentOut

    incident = IncidentOut(
        id=17, ticket_id="TKT-017", title="private incident title",
        status="in_progress", category="technical_failure", origin="internal",
        branch="central", created_at="2026-10-21", updated_at="2026-10-21",
    )
    agent = create_agent(
        incidents_fn=lambda _query: IncidentResult(status="success", incidents=[incident]),
        retrieve_fn=lambda _q: [{"source_document": "sla", "section": "Plazos", "text": "Document"}],
        generate_fn=lambda _q, _c: "La política documental se aplica según contrato (sla).",
    )
    result = agent.invoke("¿Cuál es el estado del ticket 17 y qué SLA aplica?")
    assert "estado=in_progress" in result["answer"]
    assert "política documental" in result["answer"]
    events = agent.get_trace(result["run_id"])
    assert [event["node_name"] for event in events if event["status"] == "completed"] == [
        "receive_question", "consult_incidents", "retrieve_context",
        "generate_response", "compose_response",
    ]
    assert "private incident title" not in str(events)
    assert "estado=in_progress" not in str(events)
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert agent.get_state(result["run_id"]).values["incident_result"]["status"] == "success"

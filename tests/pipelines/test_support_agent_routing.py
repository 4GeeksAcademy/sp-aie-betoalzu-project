from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
import requests

from services.agent.routing import plan_question
from services.agent.support import SupportAgent, TraceStore
from services.agent.tools import (
    IncidentQuery,
    IncidentResult,
    InventoryQuery,
    InventoryResult,
    query_incidents,
)
from services.api.incidents.models import IncidentOut
from services.api.inventory.models import AssetResponse

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "support_agent_routing.json").read_text()
)["cases"]
CONTEXT = [{
    "source_document": "pricing-model", "section": "Headhunting ejecutivo",
    "text": "La tarifa es del 22%.",
}]


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Offline evaluation attempted an external HTTP call")

    monkeypatch.setattr("requests.sessions.Session.request", forbidden)
    for key in ("SUPPORT_AGENT_SERVICE_TOKEN", "LLM_API_KEY", "EMBED_MODEL_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def incident_result(status="success"):
    if status == "failed":
        return IncidentResult(status="failed", error="timeout")
    if status == "not_found":
        return IncidentResult(status="not_found")
    return IncidentResult(status="success", incidents=[IncidentOut(
        id=17, ticket_id="TKT-017", title="Private test-only title",
        description="Private test-only description",
        status="in_progress", category="technical_failure", origin="internal",
        branch="central", created_at="2026-10-21", updated_at="2026-10-21",
    )])


def inventory_result():
    return InventoryResult(status="success", products=[AssetResponse(
        id=3, name="Test-only product", sku="NXV-IT-003", category="hardware",
        office="Valencia", currency="EUR", current_stock=8,
    )])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_offline_routing_evaluates_persisted_trace_and_answer(tmp_path, case):
    incidents_fn = Mock(return_value=incident_result(case.get("incident_status", "success")))
    inventory_fn = Mock(return_value=inventory_result())
    retrieve_fn = Mock(return_value=CONTEXT)
    generate_fn = Mock(return_value=(
        "Respuesta de documentación de prueba."
        if case["id"] == "document-about-incidents"
        else "La tarifa es del 22% (pricing-model)."
    ))
    database = tmp_path / "evaluation.sqlite3"
    agent = SupportAgent(
        database, incidents_fn=incidents_fn, inventory_fn=inventory_fn,
        retrieve_fn=retrieve_fn, generate_fn=generate_fn,
    )
    try:
        result = agent.invoke(case["question"])
        assert result["error"] is None
        assert case["expected_text"] in result["answer"]
        assert agent.get_state(result["run_id"]).values["answer"] == result["answer"]
    finally:
        agent.close()

    # Evaluate the durable trace after closing the running graph.
    events = TraceStore(database).get(result["run_id"])
    completed = [event for event in events if event["status"] == "completed"]
    assert [event["node_name"] for event in completed] == case["nodes"]
    assert completed[0]["output"]["sources"] == case["sources"]
    source_nodes = {"consult_incidents", "consult_inventory", "retrieve_context"}
    consulted = [event for event in completed if event["node_name"] in source_nodes]
    assert [event["output"]["source"] for event in consulted] == case["sources"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert incidents_fn.call_count == int("incidents" in case["sources"])
    assert inventory_fn.call_count == int("inventory" in case["sources"])
    assert retrieve_fn.call_count == int("rag" in case["sources"])
    assert generate_fn.call_count == int("rag" in case["sources"])
    if "incidents" in case["sources"]:
        query = incidents_fn.call_args.args[0]
        assert isinstance(query, IncidentQuery)
        assert query.incident_id == 17 or query.ticket_id == "TKT-017"
        source = next(event for event in consulted if event["output"]["source"] == "incidents")
        assert source["output"]["outcome"] == case["incident_status"]
        if case["incident_status"] != "success":
            assert "estado=" not in result["answer"]
    if "inventory" in case["sources"]:
        assert inventory_fn.call_args.args[0] == InventoryQuery(product_id=3)
    assert "Private test-only" not in str(events)
    assert "Authorization" not in str(events)


@pytest.mark.parametrize("stage", ["retrieve", "generate"])
def test_mixed_rag_failure_preserves_only_confirmed_ticket_data(tmp_path, stage):
    retrieve_fn = Mock(return_value=CONTEXT)
    generate_fn = Mock(return_value="Documentary answer")
    failing = retrieve_fn if stage == "retrieve" else generate_fn
    failing.side_effect = RuntimeError("private provider failure")
    agent = SupportAgent(
        tmp_path / "agent.sqlite3", incidents_fn=lambda _q: incident_result(),
        retrieve_fn=retrieve_fn, generate_fn=generate_fn,
    )
    try:
        result = agent.invoke("Consulta el ticket 17 y el SLA de soporte.")
        assert "estado=in_progress" in result["answer"]
        assert "No pude consultar la información documental" in result["answer"]
        events = agent.get_trace(result["run_id"])
        failed = [event for event in events if event["output"].get("outcome") == "failed"]
        assert failed
        assert all(event["output"]["source"] == "rag" for event in failed)
        assert "private provider failure" not in str(events)
        if stage == "retrieve":
            generate_fn.assert_not_called()
    finally:
        agent.close()


@pytest.mark.parametrize("status", ["not_found", "failed"])
def test_inventory_fallback_never_invents_stock(tmp_path, status):
    agent = SupportAgent(
        tmp_path / "agent.sqlite3",
        inventory_fn=lambda _q: InventoryResult(
            status=status, error="timeout" if status == "failed" else None,
        ),
        retrieve_fn=Mock(side_effect=AssertionError("RAG must not be called")),
        generate_fn=Mock(side_effect=AssertionError("LLM must not be called")),
    )
    try:
        result = agent.invoke("Consulta el stock del producto 3.")
        assert "confirmar" in result["answer"]
        assert "stock=" not in result["answer"]
        completed = [
            event for event in agent.get_trace(result["run_id"])
            if event["status"] == "completed" and event["node_name"] == "consult_inventory"
        ]
        assert completed[0]["output"]["outcome"] == status
    finally:
        agent.close()


@pytest.mark.parametrize("question,expected", [
    ("Lista las incidencias abiertas de Miami.", IncidentQuery(status="open", branch="miami_office")),
    ("Consulta las incidencias de origen interno.", IncidentQuery(origin="internal")),
    ("Busca incidencias de fallo técnico.", IncidentQuery(category="technical_failure")),
    ("Consulta el ticket con id #17.", IncidentQuery(incident_id=17)),
])
def test_question_plan_preserves_real_incident_filters(question, expected):
    plan = plan_question(question)
    assert plan["sources"] == ["incidents"]
    assert IncidentQuery.model_validate(plan["incident_query"]) == expected


def test_sku_question_targets_inventory_without_rag():
    plan = plan_question("¿Cuál es el stock de NXV-IT-003?")
    assert plan["sources"] == ["inventory"]
    assert InventoryQuery.model_validate(plan["inventory_query"]).search == "NXV-IT-003"


def test_real_incident_tool_timeout_does_not_block_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORT_AGENT_SERVICE_TOKEN", str(uuid4()))
    get = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr("services.agent.tools.requests.get", get)
    agent = SupportAgent(
        tmp_path / "agent.sqlite3", incidents_fn=query_incidents,
        retrieve_fn=Mock(side_effect=AssertionError("RAG must not be called")),
    )
    try:
        result = agent.invoke("Consulta el estado del ticket 17.")
        assert result["error"] is None
        assert "No pude confirmar" in result["answer"]
        assert "estado=" not in result["answer"]
        assert get.call_args.kwargs["timeout"] == 4.0
        events = agent.get_trace(result["run_id"])
        completed = [event for event in events if event["status"] == "completed"]
        assert completed[1]["output"]["source"] == "incidents"
        assert completed[1]["output"]["outcome"] == "failed"
        assert completed[1]["output"]["error"] == "timeout"
    finally:
        agent.close()

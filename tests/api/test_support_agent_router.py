from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

import server
from server import app
from services.agent.support import SupportAgent, get_support_agent
from services.api.users.auth import get_current_user
from services.api.users.models import Role

OPERATOR_USER = SimpleNamespace(
    id=1,
    is_active=True,
    role=Role.MANAGER,
)


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv(
        "SUPPORT_AGENT_DB_PATH",
        str(tmp_path / "support-agent.sqlite3"),
    )
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def graph_agent(tmp_path) -> SupportAgent:
    agent = SupportAgent(tmp_path / "support-agent.sqlite3")
    yield agent
    agent.close()


def test_query_requires_authentication() -> None:
    client = TestClient(app)
    response = client.post("/agent/query", json={"question": "¿Precio?"})

    assert response.status_code == 401


def test_empty_question_is_traced_and_returns_422(
    client: TestClient,
    graph_agent: SupportAgent,
) -> None:
    agent = graph_agent
    with patch("services.agent.routes.get_support_agent", return_value=agent):
        response = client.post("/agent/query", json={"question": "   "})

        assert response.status_code == 422
        error = response.json()["detail"]
        assert error["message"] == "La pregunta no puede estar vacía."
        trace = client.get(f"/agent/traces/{error['run_id']}")
        assert trace.status_code == 200
        assert [
            event["node_name"]
            for event in trace.json()["events"]
            if event["status"] == "completed"
        ] == ["receive_question"]


def test_query_returns_answer_and_trace(client: TestClient) -> None:
    agent = Mock()
    agent.invoke.side_effect = lambda _question, *, run_id: {
        "answer": "La tarifa estándar es del 22%.",
        "error": None,
        "run_id": run_id,
    }
    agent.get_trace.return_value = [{
        "run_id": "test-run",
        "sequence": 1,
        "node_name": "receive_question",
        "status": "completed",
        "timestamp": "2026-10-20T09:00:00+00:00",
        "output": {"valid": True},
    }]
    with patch("services.agent.routes.get_support_agent", return_value=agent):
        response = client.post(
            "/agent/query",
            json={"question": "¿Cuál es la tarifa?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "La tarifa estándar es del 22%."
        assert body["run_id"]
        invoke_args = agent.invoke.call_args.args
        invoke_kwargs = agent.invoke.call_args.kwargs
        assert invoke_args == ("¿Cuál es la tarifa?",)
        assert invoke_kwargs["run_id"] == body["run_id"]
        assert invoke_kwargs["actor_id"] == "1"
        assert invoke_kwargs["actor_role"] == "manager"
        assert invoke_kwargs["conversation_id"] == body["conversation_id"]
        assert body["conversation_id"]
        trace = client.get(f"/agent/traces/{body['run_id']}")
        assert trace.status_code == 200
        assert trace.json()["run_id"] == body["run_id"]
        assert trace.json()["events"][0]["node_name"] == "receive_question"


def test_failed_execution_returns_generic_error_and_run_id(
    client: TestClient,
) -> None:
    agent = Mock()
    agent.invoke.side_effect = RuntimeError("provider secret detail")
    with patch("services.agent.routes.get_support_agent", return_value=agent):
        response = client.post("/agent/query", json={"question": "¿Precio?"})

    assert response.status_code == 500
    body = response.json()["detail"]
    assert body["run_id"]
    assert "provider secret" not in str(body)
    assert body["message"] == (
        "No se pudo completar la consulta. Usa el run_id para investigar."
    )


def test_trace_requires_authentication() -> None:
    client = TestClient(app)
    response = client.get("/agent/traces/run-id")

    assert response.status_code == 401


def test_guardrail_summary_requires_authentication() -> None:
    client = TestClient(app)
    response = client.get("/agent/guardrails/summary")

    assert response.status_code == 401


def test_guardrail_summary_returns_aggregated_counts(client: TestClient) -> None:
    agent = Mock()
    agent.get_guardrail_summary.return_value = {
        "total": 1,
        "by_type": {"structural": 0, "content": 0, "security": 1},
        "by_guardrail": {
            "instruction_override": {"blocked": 1, "redirected": 0},
        },
    }
    with patch("services.agent.routes.get_support_agent", return_value=agent):
        response = client.get("/agent/guardrails/summary")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["by_type"]["security"] == 1
    assert response.json()["by_guardrail"]["instruction_override"]["blocked"] == 1


def test_trace_lookup_does_not_expose_checkpoints(client: TestClient) -> None:
    agent = Mock()
    agent.get_trace.return_value = []
    with patch("services.agent.routes.get_support_agent", return_value=agent):
        response = client.get("/agent/traces/unknown-run")

    assert response.status_code == 404


def test_application_lifespan_initializes_and_closes_agent(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SUPPORT_AGENT_DB_PATH",
        str(tmp_path / "support-agent.sqlite3"),
    )
    monkeypatch.setattr(server, "init_db", lambda: None)

    with TestClient(app):
        assert get_support_agent().graph is not None

    with pytest.raises(RuntimeError, match="not initialized"):
        get_support_agent()

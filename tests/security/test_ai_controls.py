"""Pruebas de controles de IA: rate limiting autenticado, aislamiento de
trazas del agente y registro estructurado minimizado.

Usa una app FastAPI mínima que monta solo los routers de conocimiento y del
agente de soporte, sin `server.py` (evita el bloqueo de importación
preexistente del chat). Todos los proveedores externos y la lógica del agente
se sustituyen con dobles sintéticos; no se contactan servicios externos ni se
usan datos reales.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.agent.routes import agent_api
from services.agent.support import SupportAgent
from services.api.knowledge.routes import knowledge_api
from services.api.rate_limit import model_inference_limiter
from services.api.users.auth import get_current_user
from services.api.users.models import Role

OPERATOR = SimpleNamespace(id=1, is_active=True, role=Role.MANAGER)
OPERATOR_TWO = SimpleNamespace(id=2, is_active=True, role=Role.MANAGER)
NORMAL_USER = SimpleNamespace(id=3, is_active=True, role=Role.USER)


def _make_app(user) -> FastAPI:
    app = FastAPI()
    app.include_router(knowledge_api)
    app.include_router(agent_api)
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _reset_limiter(limit: int) -> None:
    model_inference_limiter.clear()
    model_inference_limiter.limit = limit


# ── Rate limiting autenticado sobre inferencia ─────────────────────────────

def test_rate_limit_returns_429_without_second_inference() -> None:
    """El límite de inferencia por usuario devuelve 429 sin invocar el modelo."""
    _reset_limiter(limit=1)
    try:
        client = TestClient(_make_app(NORMAL_USER))
        with patch(
            "services.api.knowledge.routes.rag_query", return_value="Respuesta."
        ) as infer:
            first = client.post(
                "/knowledge/query", json={"question": "Primera pregunta"}
            )
            second = client.post(
                "/knowledge/query", json={"question": "Segunda pregunta"}
            )
        assert first.status_code == 200
        assert second.status_code == 429
        assert "retry-after" in second.headers
        assert int(second.headers["retry-after"]) > 0
        infer.assert_called_once_with("Primera pregunta")
    finally:
        model_inference_limiter.clear()


def test_rate_limit_is_scoped_per_user_id() -> None:
    """Un usuario autenticado no agota la cuota de otro."""
    _reset_limiter(limit=1)
    try:
        with patch("services.api.knowledge.routes.rag_query", return_value="R."):
            first = TestClient(_make_app(NORMAL_USER))
            assert first.post("/knowledge/query", json={"question": "¿A?"}).status_code == 200
            assert first.post("/knowledge/query", json={"question": "¿B?"}).status_code == 429

            other = TestClient(_make_app(OPERATOR))
            resp = other.post("/knowledge/query", json={"question": "¿C?"})
            assert resp.status_code == 200
    finally:
        model_inference_limiter.clear()


def test_rate_limiter_rejects_invalid_configuration() -> None:
    from services.api.rate_limit import SlidingWindowRateLimiter

    for kwargs in ({"limit": 0, "window_seconds": 60}, {"limit": 10, "window_seconds": 0}):
        try:
            SlidingWindowRateLimiter(**kwargs)
        except ValueError:
            pass
        else:  # pragma: no cover - expected branch
            raise AssertionError(f"Expected ValueError for {kwargs}")


# ── Aislamiento de trazas del agente por operador ──────────────────────────

def test_agent_trace_is_visible_only_to_initiating_operator(tmp_path) -> None:
    """Las trazas quedan vinculadas al operador que las inició.

    Se valida la capa de trazas directamente (evita el embedding RAG real):
    el operador dueño ve su traza; otro operador autenticado recibe 404 y el
    acceso directo a `get_trace` con otro `actor_id` devuelve lista vacía.
    """
    from services.agent.support import TraceStore

    db = tmp_path / "owner-isolation.sqlite3"
    store = TraceStore(db)
    store.record(
        "synthetic-owned-run",
        "input_guardrail",
        "completed",
        {"action": "allow"},
    )
    store.set_owner("synthetic-owned-run", "1")

    agent = object.__new__(SupportAgent)
    agent.traces = store

    assert agent.get_trace("synthetic-owned-run", actor_id="1")
    assert agent.get_trace("synthetic-owned-run", actor_id="2") == []

    with patch("services.agent.routes.get_support_agent", return_value=agent):
        owner = TestClient(_make_app(OPERATOR))
        assert owner.get("/agent/traces/synthetic-owned-run").status_code == 200
        other = TestClient(_make_app(OPERATOR_TWO))
        assert other.get("/agent/traces/synthetic-owned-run").status_code == 404


# ── Registro estructurado minimizado del agente ───────────────────────────

def test_agent_audit_log_is_structured_and_omits_question(
    tmp_path, caplog
) -> None:
    caplog.set_level(logging.INFO, logger="services.agent.routes")
    agent = Mock()
    agent.invoke.side_effect = lambda question, *, run_id, **_: {
        "answer": "Respuesta sintética",
        "error": None,
        "run_id": run_id,
    }
    secret_question = "CANARY_PII synthetic candidate salary 90000"
    with patch("services.agent.routes.get_support_agent", return_value=agent):
        client = TestClient(_make_app(OPERATOR))
        response = client.post("/agent/query", json={"question": secret_question})
    assert response.status_code == 200

    records = [
        record for record in caplog.records if record.getMessage() == "agent_audit"
    ]
    assert len(records) == 1
    audit = records[0].audit
    assert audit["correlation_id"]
    assert audit["actor_pseudonym"]
    assert audit["agent"] == "support"
    assert audit["decision"] == "completed"
    assert secret_question not in str(audit)
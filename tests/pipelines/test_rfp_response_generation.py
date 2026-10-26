from __future__ import annotations

import threading

import pytest

from data_project.pipelines.rfp_intake import responses
from data_project.pipelines.rfp_intake.graph import RfpIntakeError


def _handoff() -> dict:
    return {
        "schema_version": "1.0",
        "ticket_id": "ticket-1",
        "metadata": {
            "client_name": "Cliente de prueba",
            "client_hq": "España",
            "service_types": ["headhunting", "customer_support"],
            "departments_needed": ["seleccion", "soporte"],
            "open_questions": ["Falta el presupuesto."],
            "department_extracts": {
                "seleccion": "Extracto privado de selección",
                "soporte": "Extracto privado de soporte",
            },
        },
        "active_workstreams": [
            {"department_id": "seleccion", "contact": "Javier Almeida"},
            {"department_id": "soporte", "contact": "Roberto Díaz"},
        ],
        "key_aspects": {
            "seleccion": [{"aspect": "Roles", "value": "Cinco", "evidence": "Cinco"}],
            "soporte": [{"aspect": "Turnos", "value": None, "open_question": "¿Turnos?"}],
        },
        "open_questions": ["Falta el presupuesto."],
    }


def _passing_draft(department_id: str) -> str:
    if department_id == "soporte":
        return (
            "Incluye la garantía de satisfacción de Nexova a 90 días. "
            "La propuesta se expresa en EUR y contempla el SLA de respuesta de 24 horas."
        )
    return (
        "Incluye la garantía de satisfacción de Nexova a 90 días. "
        "La propuesta se expresa en EUR y estima un cierre en 15 días hábiles."
    )


def _install_agents(monkeypatch, generator=None, generator_barrier=None):
    calls: list[tuple[str, dict]] = []

    def invoke(agent_name, _instruction, payload, response_model):
        calls.append((agent_name, payload))
        if agent_name.startswith("generator_"):
            department_id = agent_name.removeprefix("generator_")
            if generator_barrier:
                generator_barrier.wait(timeout=2)
            content = (
                generator(department_id, payload)
                if generator
                else _passing_draft(department_id)
            )
            return responses.DraftOutput(draft_content=content)
        if agent_name.startswith("relevance_evaluator_"):
            return responses.RelevanceResult.model_validate(
                {"pass": True, "missing_aspects": []}
            )
        raise AssertionError(f"Unexpected agent: {agent_name}")

    monkeypatch.setattr(responses, "_invoke_json_agent", invoke)
    return calls


def test_generators_receive_only_their_department_aspects(monkeypatch):
    calls = _install_agents(monkeypatch, generator_barrier=threading.Barrier(2))

    result = responses.generate_rfp_responses("ticket-1", _handoff())

    generator_payloads = {
        name.removeprefix("generator_"): payload
        for name, payload in calls
        if name.startswith("generator_")
    }
    assert set(generator_payloads) == {"seleccion", "soporte"}
    assert generator_payloads["seleccion"]["key_aspects"] == _handoff()["key_aspects"][
        "seleccion"
    ]
    assert generator_payloads["soporte"]["key_aspects"] == _handoff()["key_aspects"][
        "soporte"
    ]
    assert all(
        "department_extracts" not in payload["metadata"]
        for payload in generator_payloads.values()
    )
    assert result["status"] == "en-evaluación"
    assert result["handoff"]["schema_version"] == "2.0"
    assert all(
        section["evaluation_result"]["overall_pass"]
        for section in result["sections"]
    )


def test_evaluators_run_in_parallel_and_combine_structured_results(monkeypatch):
    barrier = threading.Barrier(3)

    def wait_for_peers(*_args):
        barrier.wait(timeout=2)

    monkeypatch.setattr(responses, "_readability_evaluator", lambda draft: (
        wait_for_peers(draft),
        responses.ReadabilityResult.model_validate(
            {"pass": True, "score": 90, "details": "Métrica simulada."}
        ),
    )[1])
    monkeypatch.setattr(
        responses,
        "_relevance_evaluator",
        lambda *_args: (
            wait_for_peers(),
            responses.RelevanceResult.model_validate(
                {"pass": True, "missing_aspects": []}
            ),
        )[1],
    )
    monkeypatch.setattr(
        responses,
        "_compliance_evaluator",
        lambda *_args: (
            wait_for_peers(),
            responses.ComplianceResult.model_validate(
                {"pass": True, "rule_ids": ["rule"], "violations": []}
            ),
        )[1],
    )

    result = responses._evaluate_draft(
        "seleccion", {"client_hq": "España"}, [], "Propuesta."
    )

    assert result.overall_pass is True
    assert result.readability.score == 90
    assert result.relevance.missing_aspects == []
    assert result.compliance.rule_ids == ["rule"]
    assert len(result.draft_sha256) == 64


@pytest.mark.parametrize(
    ("department_id", "metadata", "draft", "rule_id"),
    [
        (
            "seleccion",
            {"client_hq": "España", "service_types": ["headhunting"]},
            "Garantía de satisfacción a 90 días. EUR. Cierre en 10 días hábiles.",
            "executive_search_minimum_15_business_days",
        ),
        (
            "soporte",
            {"client_hq": "España", "service_types": ["customer_support"]},
            "Garantía de satisfacción a 90 días. EUR. Atención de soporte.",
            "outsourced_support_sla_24_hours",
        ),
    ],
)
def test_concrete_briefing_violations_are_reported(
    department_id, metadata, draft, rule_id
):
    result = responses._compliance_evaluator(department_id, metadata, draft)

    assert result.pass_ is False
    assert rule_id in result.rule_ids
    assert result.violations


def test_unknown_currency_is_not_reported_as_compliant():
    result = responses._compliance_evaluator(
        "capacitacion",
        {"client_hq": "no_especificado"},
        "Garantía de satisfacción de Nexova a 90 días.",
    )

    assert result.pass_ is False
    assert "currency_matches_client_hq" in result.rule_ids
    assert any("No se puede verificar la moneda" in item for item in result.violations)


def test_named_current_client_reference_fails_anonymization_rule():
    result = responses._compliance_evaluator(
        "capacitacion",
        {"client_hq": "España"},
        "Garantía de satisfacción a 90 días. EUR. "
        "Clientes actuales como Vantex Retail Group.",
    )

    assert result.pass_ is False
    assert "anonymize_current_client_references" in result.rule_ids
    assert any("Vantex Retail Group" in item for item in result.violations)


def test_only_failed_section_retries_and_last_draft_survives_limit(monkeypatch):
    def relevance(_department, _metadata, aspects, _draft):
        if aspects and aspects[0]["aspect"] == "Roles":
            return responses.RelevanceResult.model_validate(
                {"pass": True, "missing_aspects": []}
            )
        return responses.RelevanceResult.model_validate(
            {"pass": True, "missing_aspects": []}
        )

    monkeypatch.setattr(responses, "_relevance_evaluator", relevance)
    generated: list[str] = []

    def generator(department_id, _payload):
        generated.append(department_id)
        if department_id == "soporte":
            return "Garantía de satisfacción de Nexova a 90 días. EUR. Soporte."
        return _passing_draft(department_id)

    calls = _install_agents(monkeypatch, generator)
    passed_draft = _passing_draft("seleccion")
    passed_result = responses._evaluate_draft(
        "seleccion",
        _handoff()["metadata"],
        _handoff()["key_aspects"]["seleccion"],
        passed_draft,
    )
    existing = {
        "seleccion": {
            "draft_content": passed_draft,
            "evaluation_results": {
                "schema_version": "1.0",
                "iteration_count": 1,
                "section_status": "ready_for_approval",
                "result": passed_result.model_dump(mode="json", by_alias=True),
            },
        }
    }
    persisted: list[tuple[str, int, str]] = []

    result = responses.generate_rfp_responses(
        "ticket-1",
        _handoff(),
        existing_sections=existing,
        on_evaluated=lambda department, draft, bundle: persisted.append(
            (department, bundle["iteration_count"], draft)
        ),
    )

    assert generated == ["soporte"] * responses.MAX_GENERATION_ATTEMPTS
    assert len(
        [name for name, _payload in calls if name == "generator_seleccion"]
    ) == 0
    assert [item[1] for item in persisted] == [1, 2, 3]
    support = next(section for section in result["sections"] if section["department_id"] == "soporte")
    assert support["section_status"] == "needs_human_review"
    assert support["needs_human_review"] is True
    assert support["draft_content"] == persisted[-1][2]
    assert support["evaluation_result"]["compliance"]["pass"] is False
    assert result["status"] == "needs_human_review"
    assert len(result["handoff"]["active_workstreams"]) == 2


def test_invalid_handoff_fails_before_generation(monkeypatch):
    calls = _install_agents(monkeypatch)
    invalid = _handoff()
    invalid["active_workstreams"] = []

    with pytest.raises(RfpIntakeError, match="departamentos activos"):
        responses.generate_rfp_responses("ticket-1", invalid)

    assert calls == []


def test_failed_evaluation_does_not_consume_iteration_or_persist(monkeypatch):
    _install_agents(monkeypatch)

    def fail_relevance(*_args):
        raise RfpIntakeError("evaluación no disponible")

    monkeypatch.setattr(responses, "_relevance_evaluator", fail_relevance)
    persisted: list[object] = []

    with pytest.raises(RfpIntakeError, match="evaluación no disponible"):
        responses.generate_rfp_responses(
            "ticket-1",
            {
                **_handoff(),
                "active_workstreams": [_handoff()["active_workstreams"][0]],
                "key_aspects": {"seleccion": _handoff()["key_aspects"]["seleccion"]},
                "metadata": {
                    **_handoff()["metadata"],
                    "service_types": ["headhunting"],
                    "departments_needed": ["seleccion"],
                },
            },
            on_evaluated=lambda *_args: persisted.append(True),
        )

    assert persisted == []

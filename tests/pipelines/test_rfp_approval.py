from __future__ import annotations

from types import SimpleNamespace

from data_project.pipelines.rfp_intake.approval import (
    authorized_departments,
    detect_structured_conflicts,
)
from data_project.pipelines.rfp_intake.responses import _extract_structured_facts


def _section(
    department_id: str,
    *,
    rule_ids: list[str] | None = None,
    violations: list[str] | None = None,
    currencies: list[str] | None = None,
    structured_facts: dict | None = None,
    key_aspects: list[dict] | None = None,
) -> dict:
    return {
        "department_id": department_id,
        "draft_content": "Contenido de propuesta.",
        "draft_sha256": "a" * 64,
        "draft_version": 1,
        "key_aspects": key_aspects or [],
        "evaluation_results": {
            "result": {
                "compliance": {
                    "pass": not violations,
                    "rule_ids": rule_ids or [],
                    "violations": violations or [],
                    "currencies_mentioned": currencies or [],
                },
                "structured_facts": structured_facts or {},
            }
        },
    }


def test_approver_identity_comes_from_admin_role_not_profile_name():
    named_profile = SimpleNamespace(
        role=SimpleNamespace(value="user"),
        profile={"name": "Javier Almeida"},
    )
    admin = SimpleNamespace(role=SimpleNamespace(value="admin"), profile=None)

    assert authorized_departments(named_profile) == set()
    assert authorized_departments(admin) == {
        "seleccion",
        "capacitacion",
        "soporte",
    }


def test_support_sla_trigger_requires_matching_structured_rule_and_violation():
    section = _section(
        "soporte",
        rule_ids=["outsourced_support_sla_24_hours"],
        violations=["Menciona explícitamente el SLA de respuesta de 24 horas."],
    )

    conflicts = detect_structured_conflicts(
        {"client_hq": "España"}, [section]
    )

    assert [item["trigger_id"] for item in conflicts] == ["support-sla-missing"]
    assert conflicts[0]["arbitrator"] == "Roberto Díaz"


def test_currency_trigger_uses_structured_currency_and_client_headquarters():
    section = _section(
        "seleccion",
        rule_ids=["currency_matches_client_hq"],
        currencies=["USD"],
    )

    conflicts = detect_structured_conflicts(
        {"client_hq": "España"}, [section]
    )

    assert [item["trigger_id"] for item in conflicts] == ["currency-mismatch"]
    assert conflicts[0]["arbitrator"] == "Marcos Ibáñez"


def test_timing_conflict_requires_same_structured_scope():
    selection = _section(
        "seleccion",
        structured_facts={
            "time_to_close_business_days": 20,
            "roles_key": "senior analysts",
        },
    )
    training = _section(
        "capacitacion",
        structured_facts={
            "training_start_business_days": 10,
            "roles_key": "senior analysts",
        },
    )
    unrelated_training = _section(
        "capacitacion",
        structured_facts={
            "training_start_business_days": 10,
            "roles_key": "different cohort",
        },
    )

    conflict = detect_structured_conflicts(
        {"client_hq": "no_especificado"}, [selection, training]
    )
    no_conflict = detect_structured_conflicts(
        {"client_hq": "no_especificado"}, [selection, unrelated_training]
    )

    assert [item["trigger_id"] for item in conflict] == [
        "ttc-vs-training-window"
    ]
    assert no_conflict == []


def test_timing_extractor_requires_explicit_labeled_fields():
    assert _extract_structured_facts(
        "Time to close: 20 días hábiles; training start: 10 días hábiles; "
        "Roles: Senior Analysts"
    ) == {
        "time_to_close_business_days": 20,
        "training_start_business_days": 10,
        "roles_key": "senior analysts",
    }
    assert _extract_structured_facts(
        "El cierre podría tardar 20 días hábiles y la formación podría comenzar antes."
    ) == {}

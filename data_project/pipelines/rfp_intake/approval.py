from __future__ import annotations

import hashlib
from typing import Any

DEPARTMENT_APPROVERS = {
    "seleccion": "Javier Almeida",
    "capacitacion": "Elena Vargas",
    "soporte": "Roberto Díaz",
}
SUPPORTED_DEPARTMENTS = frozenset(DEPARTMENT_APPROVERS)
SALES_ARBITRATOR = "Marcos Ibáñez"
APPROVAL_SCHEMA_VERSION = "2.0"


class RfpApprovalError(ValueError):
    pass


def draft_digest(draft_content: str) -> str:
    return hashlib.sha256(draft_content.encode("utf-8")).hexdigest()


def authorized_departments(user: Any) -> set[str]:
    if getattr(getattr(user, "role", None), "value", None) == "admin":
        return set(SUPPORTED_DEPARTMENTS)
    return set()


def validate_approval_handoff(
    ticket_id: str,
    handoff: Any,
    sections: list[Any],
) -> list[dict[str, Any]]:
    if not isinstance(handoff, dict) or handoff.get("ticket_id") != ticket_id:
        raise RfpApprovalError("El handoff no corresponde al ticket.")
    if handoff.get("schema_version") != APPROVAL_SCHEMA_VERSION:
        raise RfpApprovalError("La versión del handoff no admite aprobaciones.")
    generation = handoff.get("response_generation")
    if not isinstance(generation, dict) or generation.get("status") not in {
        "ready_for_part_3",
        "needs_human_review",
    }:
        raise RfpApprovalError("El handoff no está listo para aprobación humana.")
    workstreams = handoff.get("active_workstreams")
    if not isinstance(workstreams, list) or not workstreams:
        raise RfpApprovalError("El handoff no contiene departamentos activos.")

    persisted = {section.department_id: section for section in sections}
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for workstream in workstreams:
        if not isinstance(workstream, dict):
            raise RfpApprovalError("El handoff contiene una sección inválida.")
        department_id = workstream.get("department_id")
        section = persisted.get(department_id)
        if (
            department_id not in SUPPORTED_DEPARTMENTS
            or department_id in seen
            or section is None
        ):
            raise RfpApprovalError(
                "Los departamentos activos no coinciden con las secciones persistidas."
            )
        draft = section.draft_content
        bundle = section.evaluation_results
        if not isinstance(draft, str) or not draft.strip() or not isinstance(bundle, dict):
            raise RfpApprovalError(
                f"La sección {department_id} no tiene borrador y evaluación persistidos."
            )
        if (
            workstream.get("draft_content") != draft
            or workstream.get("evaluation_results") != bundle
            or workstream.get("section_status") != bundle.get("section_status")
        ):
            raise RfpApprovalError(
                f"El handoff de {department_id} está desactualizado respecto a la sección."
            )
        result = bundle.get("result")
        if (
            bundle.get("schema_version") != "1.0"
            or not isinstance(result, dict)
            or result.get("section_id") != department_id
            or result.get("draft_sha256") != draft_digest(draft)
            or not isinstance(bundle.get("iteration_count"), int)
        ):
            raise RfpApprovalError(
                f"El borrador y la evaluación de {department_id} no son compatibles."
            )
        validated.append(
            {
                **workstream,
                "department_id": department_id,
                "draft_content": draft,
                "evaluation_results": bundle,
                "draft_sha256": draft_digest(draft),
                "draft_version": bundle["iteration_count"],
            }
        )
        seen.add(department_id)
    if seen != set(persisted):
        raise RfpApprovalError(
            "Hay secciones persistidas que no aparecen como departamentos activos."
        )
    return validated


def detect_structured_conflicts(
    metadata: dict[str, Any], sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return only conflicts supported by persisted structured evaluation data."""
    conflicts: list[dict[str, Any]] = []
    by_department = {section["department_id"]: section for section in sections}

    support = by_department.get("soporte")
    if support:
        compliance = support["evaluation_results"]["result"]["compliance"]
        if (
            "outsourced_support_sla_24_hours" in compliance.get("rule_ids", [])
            and any(
                "sla de respuesta de 24 horas" in str(item).casefold()
                for item in compliance.get("violations", [])
            )
        ):
            conflicts.append(
                {
                    "trigger_id": "support-sla-missing",
                    "departments": ["soporte"],
                    "arbitrator": "Roberto Díaz",
                    "rule": (
                        "Bloquear aprobación hasta que el SLA de respuesta 24h sea "
                        "explícito; revisar staffing si el SLA es inviable."
                    ),
                    "evidence": compliance.get("violations", []),
                }
            )

    expected_currency = {"España": "EUR", "Miami": "USD"}.get(
        metadata.get("client_hq")
    )
    currency_sections = []
    for section in sections:
        compliance = section["evaluation_results"]["result"]["compliance"]
        if "currency_matches_client_hq" in compliance.get("rule_ids", []):
            currency_sections.append((section, compliance))
    currencies_detected = {
        currency
        for _, compliance in currency_sections
        for currency in compliance.get("currencies_mentioned", [])
    }
    has_currency_violation = any(
        any("moneda" in str(item).casefold() for item in compliance.get("violations", []))
        for _, compliance in currency_sections
    )
    if len(currencies_detected) > 1 or (
        expected_currency
        and (
            has_currency_violation
            or any(currency != expected_currency for currency in currencies_detected)
        )
    ):
        conflicts.append(
            {
                "trigger_id": "currency-mismatch",
                "departments": [section["department_id"] for section, _ in currency_sections],
                "arbitrator": SALES_ARBITRATOR,
                "rule": (
                    (
                        f"Usar {expected_currency} según la sede del cliente; si no "
                        "se resuelve tras el límite de iteraciones, rechazar."
                    )
                    if expected_currency
                    else "No inferir moneda: resolver la discrepancia con la sede verificada."
                ),
                "evidence": [
                    {
                        "department_id": section["department_id"],
                        "violations": compliance.get("violations", []),
                    }
                    for section, compliance in currency_sections
                    if not compliance.get("pass", False)
                ] or {"currencies_detected": sorted(currencies_detected)},
            }
        )

    selection = by_department.get("seleccion")
    training = by_department.get("capacitacion")
    if selection and training:
        selection_facts = selection["evaluation_results"]["result"].get(
            "structured_facts", {}
        )
        training_facts = training["evaluation_results"]["result"].get(
            "structured_facts", {}
        )
        selection_days = selection_facts.get("time_to_close_business_days")
        training_days = training_facts.get("training_start_business_days")
        same_scope = (
            selection_facts.get("cohort_key")
            and selection_facts.get("cohort_key") == training_facts.get("cohort_key")
        ) or (
            selection_facts.get("roles_key")
            and selection_facts.get("roles_key") == training_facts.get("roles_key")
        )
        if (
            same_scope
            and isinstance(selection_days, int)
            and isinstance(training_days, int)
            and training_days < selection_days
        ):
            conflicts.append(
                {
                    "trigger_id": "ttc-vs-training-window",
                    "departments": ["seleccion", "capacitacion"],
                    "arbitrator": SALES_ARBITRATOR,
                    "rule": (
                        "Secuenciar entregas y solicitar cambios para que la formación "
                        "no empiece antes de un cierre realista; en búsqueda ejecutiva "
                        "el mínimo es 15 días hábiles."
                    ),
                    "evidence": {
                        "selection_time_to_close_days": selection_days,
                        "training_start_days": training_days,
                    },
                }
            )
    return conflicts

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from operator import add
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, ConfigDict, Field

from data_project.pipelines.rfp_intake.graph import (
    DEPARTMENTS,
    RfpIntakeError,
    _invoke_json_agent,
)

MAX_GENERATION_ATTEMPTS = 3
READABILITY_MAX_WORDS_PER_SENTENCE = 25
RESPONSE_SCHEMA_VERSION = "1.0"
SUPPORTED_DEPARTMENTS = frozenset(DEPARTMENTS)


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_content: str = Field(min_length=1, max_length=20_000)


class ReadabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass_: bool = Field(alias="pass")
    score: float = Field(ge=0, le=100)
    details: str = Field(min_length=1)


class RelevanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass_: bool = Field(alias="pass")
    missing_aspects: list[str] = Field(default_factory=list)


class ComplianceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass_: bool = Field(alias="pass")
    rule_ids: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    currencies_mentioned: list[Literal["EUR", "USD"]] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = RESPONSE_SCHEMA_VERSION
    section_id: str
    readability: ReadabilityResult
    relevance: RelevanceResult
    compliance: ComplianceResult
    overall_pass: bool
    feedback_for_generator: str = Field(min_length=1)
    draft_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    structured_facts: dict[str, str | int] = Field(default_factory=dict)


class ExistingSection(TypedDict, total=False):
    draft_content: str | None
    evaluation_results: dict[str, Any] | None


class RfpResponseState(TypedDict, total=False):
    ticket_id: str
    handoff: dict[str, Any]
    existing_sections: dict[str, ExistingSection]
    on_phase: PhaseCallback
    on_evaluated: EvaluationCallback
    metadata: dict[str, Any]
    shared_metadata: dict[str, Any]
    open_questions: list[str]
    workstreams: list[dict[str, Any]]
    section_results: Annotated[list[dict[str, Any]], add]
    response_result: dict[str, Any]


PhaseCallback = Callable[[str, str], None]
EvaluationCallback = Callable[[str, str, dict[str, Any]], None]


def _draft_digest(draft_content: str) -> str:
    return hashlib.sha256(draft_content.encode("utf-8")).hexdigest()


def _is_valid_previous_result(section: ExistingSection) -> bool:
    draft = section.get("draft_content")
    stored = section.get("evaluation_results")
    if not isinstance(draft, str) or not isinstance(stored, dict):
        return False
    evaluation = stored.get("result")
    if not isinstance(evaluation, dict):
        return False
    try:
        parsed = EvaluationResult.model_validate(evaluation)
    except ValueError:
        return False
    return parsed.draft_sha256 == _draft_digest(draft)


def _readability_evaluator(draft_content: str) -> ReadabilityResult:
    words = re.findall(r"\b[\w'-]+\b", draft_content, flags=re.UNICODE)
    sentences = [part for part in re.split(r"[.!?]+", draft_content) if part.strip()]
    average = len(words) / len(sentences) if sentences else None
    score = (
        max(0.0, round(100 - 2 * max(0, average - 20), 2))
        if average is not None
        else 0.0
    )
    passed = average is not None and average <= READABILITY_MAX_WORDS_PER_SENTENCE
    average_text = f"{average:.2f}" if average is not None else "no medible"
    return ReadabilityResult.model_validate(
        {
            "pass": passed,
            "score": score,
            "details": (
                "Métrica reproducible: promedio heurístico de palabras por oración "
                f"(español; palabras/oración). Resultado: {average_text}; "
                f"umbral de aprobación: <= {READABILITY_MAX_WORDS_PER_SENTENCE}. "
                "La puntuación es una señal de longitud, no una medida de calidad "
                "de negocio ni de comprensión."
            ),
        }
    )


def _relevance_evaluator(
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: list[dict[str, Any]],
    draft_content: str,
) -> RelevanceResult:
    result = _invoke_json_agent(
        f"relevance_evaluator_{department_id}",
        (
            "Evalúa si el borrador responde a los aspectos clave y al alcance "
            "de este departamento. Enumera en missing_aspects solo aspectos "
            "relevantes omitidos; no pidas como hechos valores ausentes. Las "
            "preguntas abiertas deben permanecer como incertidumbres, no como "
            "hechos o compromisos. pass solo si no faltan aspectos relevantes."
        ),
        {
            "department_id": department_id,
            "metadata": metadata,
            "key_aspects": key_aspects,
            "draft_content": draft_content,
        },
        RelevanceResult,
    )
    return RelevanceResult.model_validate(result.model_dump(by_alias=True))


def _contains_satisfaction_guarantee(draft_content: str) -> bool:
    text = draft_content.casefold()
    return (
        bool(re.search(r"garant[ií]a.{0,80}satisfacci[oó]n", text))
        and bool(re.search(r"90\s*d[ií]as", text))
    )


def _executive_search_applies(
    department_id: str, metadata: dict[str, Any]
) -> bool:
    services = {str(value).casefold() for value in metadata.get("service_types", [])}
    return department_id == "seleccion" and "headhunting" in services


def _has_short_executive_timeline(draft_content: str) -> bool:
    text = draft_content.casefold()
    for match in re.finditer(r"(\d+)\s*d[ií]as?\s*h[aá]biles", text):
        if int(match.group(1)) < 15:
            return True
    return False


def _mentions_support_sla(draft_content: str) -> bool:
    return bool(
        re.search(
            r"\bsla\b.{0,80}\b24\s*horas?\b|\b24\s*horas?\b.{0,80}\bsla\b",
            draft_content,
            flags=re.IGNORECASE,
        )
    )


def _unredacted_client_reference(draft_content: str) -> str | None:
    reference = re.search(
        r"(?:clientes?\s+(?:actual(?:es)?|de referencia)|"
        r"hemos trabajado con|referencias?\s+como)\s*[:,-]?\s*"
        r"(?:como\s+)?"
        r"([A-ZÁÉÍÓÚÑ][\w&.-]*(?:\s+[A-ZÁÉÍÓÚÑ][\w&.-]*)*)",
        draft_content,
        flags=re.IGNORECASE,
    )
    if reference is None:
        return None
    client_name = reference.group(1).strip()
    return client_name if client_name[:1].isupper() else None


def _compliance_evaluator(
    department_id: str, metadata: dict[str, Any], draft_content: str
) -> ComplianceResult:
    rule_ids: list[str] = []
    violations: list[str] = []

    rule_ids.append("satisfaction_guarantee_90_days")
    if not _contains_satisfaction_guarantee(draft_content):
        violations.append(
            "Incluye explícitamente la garantía estándar de satisfacción de Nexova a 90 días."
        )

    rule_ids.append("currency_matches_client_hq")
    expected_currency = {
        "España": ("EUR", r"\bEUR\b|€"),
        "Miami": ("USD", r"\bUSD\b|\$"),
    }.get(str(metadata.get("client_hq", "")))
    if expected_currency is None:
        violations.append(
            "No se puede verificar la moneda: client_hq no identifica España ni Miami."
        )
    else:
        other_currency = "USD" if expected_currency[0] == "EUR" else "EUR"
        other_pattern = r"\bUSD\b|\$" if other_currency == "USD" else r"\bEUR\b|€"
        expected_present = re.search(
            expected_currency[1], draft_content, flags=re.IGNORECASE
        )
        other_present = re.search(other_pattern, draft_content, flags=re.IGNORECASE)
        if not expected_present:
            violations.append(
                f"Incluye la moneda {expected_currency[0]} correspondiente a client_hq."
            )
        if other_present:
            violations.append(
                f"El borrador menciona {other_currency}, que no corresponde a "
                f"client_hq; utiliza solo {expected_currency[0]}."
            )

    if _executive_search_applies(department_id, metadata):
        rule_ids.append("executive_search_minimum_15_business_days")
        if _has_short_executive_timeline(draft_content):
            violations.append(
                "El borrador promete un cierre de búsqueda ejecutiva menor a "
                "15 días hábiles; elimina o corrige ese plazo."
            )

    if department_id == "soporte":
        rule_ids.append("outsourced_support_sla_24_hours")
        if not _mentions_support_sla(draft_content):
            violations.append(
                "Menciona explícitamente el SLA de respuesta de 24 horas para soporte."
            )

    rule_ids.append("anonymize_current_client_references")
    client_reference = _unredacted_client_reference(draft_content)
    if client_reference:
        violations.append(
            f"Anonimiza la referencia a «{client_reference}»; usa una descripción "
            "genérica del sector en lugar del nombre del cliente."
        )

    currency_mentions: list[Literal["EUR", "USD"]] = []
    if re.search(r"\bEUR\b|€", draft_content, flags=re.IGNORECASE):
        currency_mentions.append("EUR")
    if re.search(r"\bUSD\b|\$", draft_content, flags=re.IGNORECASE):
        currency_mentions.append("USD")

    return ComplianceResult.model_validate(
        {
            "pass": not violations,
            "rule_ids": rule_ids,
            "violations": violations,
            "currencies_mentioned": currency_mentions,
        }
    )


def _extract_structured_facts(draft_content: str) -> dict[str, str | int]:
    facts: dict[str, str | int] = {}
    labelled_days = (
        (
            "time_to_close_business_days",
            (
                r"(?:time[_ ]to[_ ]close|tiempo estimado de cierre|cierre estimado)"
                r"\s*[:=]\s*(\d+)\s*d[ií]as?\s*h[aá]biles"
            ),
        ),
        (
            "training_start_business_days",
            (
                r"(?:training[_ ]start|inicio de formaci[oó]n|ventana de formaci[oó]n)"
                r"\s*[:=]\s*(\d+)\s*d[ií]as?\s*h[aá]biles"
            ),
        ),
    )
    for fact_name, pattern in labelled_days:
        match = re.search(pattern, draft_content, flags=re.IGNORECASE)
        if match:
            facts[fact_name] = int(match.group(1))

    cohort = re.search(
        r"(?:cohort(?:_id)?|cohorte)\s*[:=]\s*([^\n;,.]+)",
        draft_content,
        flags=re.IGNORECASE,
    )
    if cohort:
        facts["cohort_key"] = cohort.group(1).strip().casefold()
    roles = re.search(
        r"(?:roles?|puestos?)\s*[:=]\s*([^\n;,.]+)",
        draft_content,
        flags=re.IGNORECASE,
    )
    if roles:
        facts["roles_key"] = " ".join(roles.group(1).casefold().split())
    return facts


def _build_feedback(
    readability: ReadabilityResult,
    relevance: RelevanceResult,
    compliance: ComplianceResult,
) -> str:
    feedback: list[str] = []
    if not readability.pass_:
        feedback.append(f"Legibilidad: {readability.details}")
    if not relevance.pass_:
        if relevance.missing_aspects:
            missing = "; ".join(relevance.missing_aspects)
            feedback.append(
                "Pertinencia: aborda estos aspectos recibidos que faltan, sin "
                f"inventar datos: {missing}."
            )
        else:
            feedback.append(
                "Pertinencia: el evaluador no aprobó la cobertura; comprueba cada "
                "aspecto clave y pregunta abierta de este departamento."
            )
    if not compliance.pass_:
        feedback.extend(f"Cumplimiento: {violation}" for violation in compliance.violations)
    return " ".join(feedback) or "No se detectaron defectos en los criterios evaluados."


def _evaluate_draft(
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: list[dict[str, Any]],
    draft_content: str,
) -> EvaluationResult:
    with ThreadPoolExecutor(max_workers=3) as executor:
        readability_future = executor.submit(_readability_evaluator, draft_content)
        relevance_future = executor.submit(
            _relevance_evaluator,
            department_id,
            metadata,
            key_aspects,
            draft_content,
        )
        compliance_future = executor.submit(
            _compliance_evaluator, department_id, metadata, draft_content
        )
        readability = readability_future.result()
        relevance = relevance_future.result()
        compliance = compliance_future.result()

    overall_pass = (
        readability.pass_ and relevance.pass_ and compliance.pass_
    )
    result = EvaluationResult(
        section_id=department_id,
        readability=readability,
        relevance=relevance,
        compliance=compliance,
        overall_pass=overall_pass,
        feedback_for_generator=_build_feedback(
            readability, relevance, compliance
        ),
        draft_sha256=_draft_digest(draft_content),
        structured_facts=_extract_structured_facts(draft_content),
    )
    return result


def _section_generator(
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: list[dict[str, Any]],
    open_questions: list[str],
    previous_draft: str | None,
    feedback: str | None,
) -> str:
    generated = _invoke_json_agent(
        f"generator_{department_id}",
        (
            f"Redacta únicamente la sección de propuesta de {department_id}. Usa "
            "solo los metadatos compartidos, los aspectos clave de este departamento "
            "y las preguntas abiertas. No uses ni infieras contenido de otros "
            "departamentos. No inventes precios, presupuestos, volúmenes, fechas, "
            "personal, condiciones ni compromisos operativos. Expresa los datos "
            "desconocidos como pendientes, no como hechos o promesas. Incluye la "
            "garantía estándar de satisfacción de 90 días; si client_hq es España "
            "indica EUR, y si es Miami indica USD, pero no inventes importes. En "
            "caso de sede no especificada, no declares ni infieras una moneda. "
            "búsqueda ejecutiva no prometas cierre inferior a 15 días hábiles. En "
            "soporte outsourced menciona el SLA de respuesta de 24 horas."
        ),
        {
            "department_id": department_id,
            "metadata": metadata,
            "key_aspects": key_aspects,
            "open_questions": open_questions,
            "previous_draft": previous_draft,
            "feedback_for_generator": feedback,
        },
        DraftOutput,
    )
    return DraftOutput.model_validate(generated.model_dump()).draft_content


def _process_department(
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: list[dict[str, Any]],
    open_questions: list[str],
    existing: ExistingSection,
    on_phase: PhaseCallback | None,
    on_evaluated: EvaluationCallback | None,
) -> dict[str, Any]:
    previous_valid = _is_valid_previous_result(existing)
    prior_state = existing.get("evaluation_results") if previous_valid else None
    prior_result = prior_state.get("result") if prior_state else None
    iteration_count = (
        int(prior_state.get("iteration_count", 0)) if prior_state else 0
    )
    draft_content = existing.get("draft_content") if previous_valid else None
    feedback = (
        prior_result.get("feedback_for_generator") if prior_result else None
    )

    force_revision = (
        isinstance(prior_state, dict)
        and prior_state.get("section_status") == "needs_revision"
    )
    if prior_result and prior_result.get("overall_pass") and not force_revision:
        section_status = "ready_for_approval"
        result_bundle = dict(prior_state)
    elif iteration_count >= MAX_GENERATION_ATTEMPTS and prior_result:
        section_status = "needs_human_review"
        result_bundle = dict(prior_state)
    else:
        while iteration_count < MAX_GENERATION_ATTEMPTS:
            if on_phase:
                on_phase("generating", department_id)
            draft_content = _section_generator(
                department_id,
                metadata,
                key_aspects,
                open_questions,
                draft_content,
                feedback,
            )
            if on_phase:
                on_phase("evaluating", department_id)
            evaluation = _evaluate_draft(
                department_id, metadata, key_aspects, draft_content
            )
            iteration_count += 1
            if evaluation.overall_pass:
                section_status = "ready_for_approval"
            elif iteration_count >= MAX_GENERATION_ATTEMPTS:
                section_status = "needs_human_review"
            else:
                section_status = "needs_revision"
            result_bundle = {
                "schema_version": RESPONSE_SCHEMA_VERSION,
                "iteration_count": iteration_count,
                "section_status": section_status,
                "result": evaluation.model_dump(mode="json", by_alias=True),
            }
            if on_evaluated:
                on_evaluated(department_id, draft_content, result_bundle)
            if evaluation.overall_pass or section_status == "needs_human_review":
                break
            feedback = evaluation.feedback_for_generator

    if on_phase:
        on_phase("completed", department_id)
    return {
        "department_id": department_id,
        "draft_content": draft_content,
        "evaluation_results": result_bundle,
        "section_status": section_status,
        "iteration_count": iteration_count,
        "needs_human_review": section_status == "needs_human_review",
        "evaluation_result": result_bundle["result"],
    }


def _validate_handoff(handoff: dict[str, Any], ticket_id: str) -> list[dict[str, Any]]:
    if (
        not isinstance(handoff, dict)
        or handoff.get("ticket_id") != ticket_id
        or handoff.get("schema_version") not in {"1.0", "2.0"}
    ):
        raise RfpIntakeError("El handoff de RFP no corresponde al ticket solicitado.")
    if handoff.get("schema_version") == "2.0" and (
        handoff.get("response_generation_version") != RESPONSE_SCHEMA_VERSION
        or not isinstance(handoff.get("response_generation"), dict)
    ):
        raise RfpIntakeError("El handoff de Parte 2 no es compatible para revisión.")
    metadata = handoff.get("metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("client_hq")
        not in {"España", "Miami", "no_especificado"}
        or not isinstance(metadata.get("service_types"), list)
        or not isinstance(metadata.get("departments_needed"), list)
    ):
        raise RfpIntakeError("El handoff no contiene metadatos RFP válidos.")
    workstreams = handoff.get("active_workstreams")
    aspects_by_department = handoff.get("key_aspects")
    if (
        not isinstance(workstreams, list)
        or not workstreams
        or not isinstance(aspects_by_department, dict)
    ):
        raise RfpIntakeError(
            "El handoff debe contener departamentos activos y key_aspects por departamento."
        )

    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for workstream in workstreams:
        if not isinstance(workstream, dict):
            raise RfpIntakeError("El handoff contiene un departamento inválido.")
        department_id = workstream.get("department_id")
        if department_id not in SUPPORTED_DEPARTMENTS or department_id in seen:
            raise RfpIntakeError("El handoff contiene un ID de departamento inválido o duplicado.")
        key_aspects = aspects_by_department.get(department_id)
        if not isinstance(key_aspects, list):
            raise RfpIntakeError(
                f"El handoff no contiene key_aspects válidos para {department_id}."
            )
        seen.add(department_id)
        validated.append(
            {
                **workstream,
                "department_id": department_id,
                "key_aspects": key_aspects,
            }
        )
    if (
        set(aspects_by_department) != seen
        or set(metadata["departments_needed"]) != seen
    ):
        raise RfpIntakeError(
            "Los key_aspects del handoff no corresponden a sus departamentos activos."
        )
    return validated


def _prepare_response_state(state: RfpResponseState) -> dict[str, Any]:
    handoff = state["handoff"]
    workstreams = _validate_handoff(handoff, state["ticket_id"])
    metadata = handoff["metadata"]
    open_questions = handoff.get("open_questions", [])
    if not isinstance(open_questions, list):
        raise RfpIntakeError("El handoff contiene preguntas abiertas inválidas.")
    return {
        "metadata": metadata,
        "shared_metadata": {
            key: value for key, value in metadata.items() if key != "department_extracts"
        },
        "open_questions": open_questions,
        "workstreams": workstreams,
    }


def _dispatch_response_sections(state: RfpResponseState) -> list[Send]:
    existing_sections = state.get("existing_sections", {})
    return [
        Send(
            "process_department",
            {
                "department_id": workstream["department_id"],
                "metadata": state["shared_metadata"],
                "key_aspects": workstream["key_aspects"],
                "open_questions": state["open_questions"],
                "existing_section": existing_sections.get(
                    workstream["department_id"], {}
                ),
                "on_phase": state.get("on_phase"),
                "on_evaluated": state.get("on_evaluated"),
            },
        )
        for workstream in state["workstreams"]
    ]


def _process_response_department(state: dict[str, Any]) -> dict[str, Any]:
    section = _process_department(
        state["department_id"],
        state["metadata"],
        state["key_aspects"],
        state["open_questions"],
        state["existing_section"],
        state.get("on_phase"),
        state.get("on_evaluated"),
    )
    return {"section_results": [section]}


def _assemble_response_handoff(state: RfpResponseState) -> dict[str, Any]:
    results = {
        section["department_id"]: section
        for section in state.get("section_results", [])
    }
    active_workstreams = [
        {
            **workstream,
            **results[workstream["department_id"]],
        }
        for workstream in state["workstreams"]
    ]
    needs_human_review = any(
        section["needs_human_review"] for section in active_workstreams
    )
    response_handoff = {
        **state["handoff"],
        "schema_version": "2.0",
        "response_generation_version": RESPONSE_SCHEMA_VERSION,
        "active_workstreams": active_workstreams,
        "key_aspects": {
            section["department_id"]: section["key_aspects"]
            for section in active_workstreams
        },
        "response_generation": {
            "status": "needs_human_review" if needs_human_review else "ready_for_part_3",
            "max_generation_attempts": MAX_GENERATION_ATTEMPTS,
            "iteration_count": {
                section["department_id"]: section["iteration_count"]
                for section in active_workstreams
            },
        },
        "created_at": datetime.now(UTC).isoformat(),
    }
    return {
        "response_result": {
            "status": "needs_human_review" if needs_human_review else "en-evaluación",
            "handoff": response_handoff,
            "sections": active_workstreams,
        }
    }


def _build_response_graph():
    graph = StateGraph(RfpResponseState)
    graph.add_node("prepare", _prepare_response_state)
    graph.add_node("process_department", _process_response_department)
    graph.add_node("assemble_handoff", _assemble_response_handoff)
    graph.add_edge(START, "prepare")
    graph.add_conditional_edges(
        "prepare",
        _dispatch_response_sections,
        ["process_department"],
    )
    graph.add_edge("process_department", "assemble_handoff")
    graph.add_edge("assemble_handoff", END)
    return graph.compile()


def generate_rfp_responses(
    ticket_id: str,
    handoff: dict[str, Any],
    existing_sections: dict[str, ExistingSection] | None = None,
    on_phase: PhaseCallback | None = None,
    on_evaluated: EvaluationCallback | None = None,
) -> dict[str, Any]:
    """Generate and evaluate one section per active department from a stored handoff."""
    return _build_response_graph().invoke(
        {
            "ticket_id": ticket_id,
            "handoff": handoff,
            "existing_sections": existing_sections or {},
            "on_phase": on_phase,
            "on_evaluated": on_evaluated,
            "section_results": [],
        }
    )["response_result"]

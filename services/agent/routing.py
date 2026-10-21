from __future__ import annotations

import re
import unicodedata
from typing import Literal, TypedDict

from services.agent.tools import IncidentQuery, InventoryQuery

Source = Literal["rag", "incidents", "inventory"]


class QueryPlan(TypedDict):
    sources: list[Source]
    incident_query: dict[str, object]
    inventory_query: dict[str, object]


def _plain(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _identifier(question: str, domain: str) -> str | None:
    match = re.search(
        rf"\b(?:{domain})\s*(?:(?:con\s+)?(?:id|numero|n[ºo.]?)\s*)?"
        r"[#:]?\s*([a-z][a-z0-9]*(?:-[a-z0-9]+)+|\d+)\b",
        question, re.IGNORECASE,
    )
    return match.group(1) if match else None


def plan_question(question: str) -> QueryPlan:
    plain = _plain(question)
    text = plain.casefold()
    incident_id = _identifier(plain, "ticket|incidente|incidencia")
    product_id = _identifier(plain, "producto|activo")
    incident_domain = bool(re.search(r"\b(tickets?|incidentes?|incidencias?)\b", text))
    inventory_domain = bool(re.search(
        r"\b(inventario|stock|existencias|productos?|activos?)\b", text,
    ))
    documentary = bool(re.search(
        r"\b(sla|politicas?|procedimientos?|procesos?|manual|guia|tarifas?|"
        r"precios?|garantia|plazos?|servicios?|requisitos?|documentacion|"
        r"que es|que son|significa|definicion|como (?:se |puedo |crear|registrar))\b",
        text,
    ))
    operational = bool(re.search(
        r"\b(estado|situacion|detalle|consulta|consultar|busca|buscar|lista|listar|"
        r"cuantos?|cuantas?|abiert[oa]s?|resuelt[oa]s?|pendientes?|actual|"
        r"asignad[oa]s?|fecha|categoria|origen|sede|muestra|mostrar|ver|hay|"
        r"stock|existencias|disponibilidad)\b", text,
    ))
    incidents = incident_domain and (
        incident_id is not None or operational or not documentary
    )
    inventory = inventory_domain and (
        product_id is not None or operational or not documentary
    )
    sources: list[Source] = []
    incident_args: dict[str, object] = {}
    if incidents:
        sources.append("incidents")
        if incident_id:
            incident_args[
                "incident_id" if incident_id.isdigit() else "ticket_id"
            ] = int(incident_id) if incident_id.isdigit() else incident_id
        filter_patterns = {
            "status": {
                "open": r"\b(abiert[oa]s?|open)\b",
                "in_progress": r"\b(en (curso|progreso)|in_progress)\b",
                "resolved": r"\b(resuelt[oa]s?|cerrad[oa]s?|resolved)\b",
                "discarded": r"\b(descartad[oa]s?|discarded)\b",
            },
            "branch": {
                "miami_office": r"\bmiami\b",
                "valencia_operations": r"\bvalencia\b",
                "central": r"\bcentral\b",
                "remote": r"\b(remot[oa]|remote)\b",
            },
            "origin": {
                "customer": r"\b(?:origen|de tipo)\s+(?:cliente|customer)\b",
                "internal": r"\b(?:origen|de tipo)\s+(?:interno|internal)\b",
                "branch": r"\b(?:origen|de tipo)\s+(?:sede|branch)\b",
            },
            "category": {
                "technical_failure": r"\b(fallo tecnico|technical_failure)\b",
                "process_error": r"\b(error de proceso|process_error)\b",
                "client_complaint": r"\b(queja de cliente|client_complaint)\b",
                "candidate_issue": r"\b(problema de candidato|candidate_issue)\b",
                "staff_issue": r"\b(problema de personal|staff_issue)\b",
                "sla_breach": r"\b(incumplimiento de sla|sla_breach)\b",
                "data_quality": r"\b(calidad de datos|data_quality)\b",
                "other": r"\b(categoria otros|other)\b",
            },
        }
        for key, patterns in filter_patterns.items():
            matches = [value for value, pattern in patterns.items() if re.search(pattern, text)]
            if len(matches) == 1:
                incident_args[key] = matches[0]
    inventory_args: dict[str, object] = {}
    if inventory:
        sources.append("inventory")
        if product_id and product_id.isdigit():
            inventory_args["product_id"] = int(product_id)
        else:
            sku = re.search(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+){2,}\b", plain, re.IGNORECASE)
            search = re.search(
                r"\b(?:stock|existencias|disponibilidad)\s+(?:de|del|para)\s+"
                r"(.+?)(?:[?;]|\s+y\s+|$)", plain, re.IGNORECASE,
            )
            if sku:
                inventory_args["search"] = sku.group()
            elif search:
                inventory_args["search"] = search.group(1).strip()
    if documentary or not sources:
        sources.append("rag")
    return {
        "sources": sources,
        "incident_query": IncidentQuery.model_validate(incident_args).model_dump(mode="json"),
        "inventory_query": InventoryQuery.model_validate(inventory_args).model_dump(mode="json"),
    }

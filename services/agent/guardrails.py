from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class InputDecision:
    action: str
    guardrail_id: str | None = None
    category: str | None = None
    answer: str | None = None


_INSTRUCTION_OVERRIDE = re.compile(
    r"\b(ignore|ignora|olvida|forget|disregard|desactiva|disable|override|"
    r"anula|cambia|change|reemplaza|replace)\b.{0,100}\b(instrucciones?|"
    r"instructions?|reglas?|rules?|politicas?|policies|restricciones?|"
    r"restrictions?|permisos?|permissions?|system prompt|prompt del sistema)\b"
)
_UNRESTRICTED_ROLE = re.compile(
    r"\b(ahora|desde ahora|a partir de ahora|from now on)\b.{0,100}\b"
    r"(asistente|assistant|modelo|model|chatbot)\b.{0,80}\b(sin reglas|"
    r"sin restricciones|unrestricted|no rules|no limits)\b"
)
_OBEY_USER = re.compile(
    r"\b(obedece|obey|follow)\b.{0,60}\b(unicamente|solo|only)\b.{0,40}\b"
    r"(mis ordenes|my orders|my instructions)\b"
)
_REVEAL_INTERNAL = re.compile(
    r"\b(revela|muestra|imprime|copia|repite|reveal|show|print|dump)\b"
    r".{0,80}\b(system prompt|prompt del sistema|instrucciones internas|"
    r"internal instructions|razonamiento privado|chain of thought)\b"
)
_PERSONAL_REQUEST = re.compile(
    r"\b(escribe|escribeme|redacta|redactame|crea|creame|haz|hazme|resuelve|"
    r"resuelveme|ayudame con|write|create|solve)\b"
    r".{0,100}\b(poema de amor|poema romantico|carta de amor|tarea universitaria|"
    r"deberes de la universidad|ensayo para clase|examen|mi tarea|my homework|"
    r"love poem|personal advice)\b"
)
_ACADEMIC_TASK = re.compile(
    r"\b(tarea|deberes|ensayo|examen|homework|assignment|essay)\b"
    r".{0,80}\b(universidad|universitaria|escuela|colegio|clase|university|school)\b"
)
_DOMAIN_TERMS = re.compile(
    r"\b(nexova|seleccion|headhunting|outsourcing|formacion|soporte|servicio|"
    r"proceso|incidente|ticket|inventario|stock|producto|proveedor|cliente|"
    r"sla|escalacion|candidato|contratacion|reclutamiento|tarifa|precio|"
    r"facturacion|helpdesk|horario|atencion|soporte al cliente)\b"
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", without_accents).strip()


def inspect_user_input(question: str) -> InputDecision:
    """Apply deterministic security and scope checks before agent processing."""
    normalized = _normalize(question)
    if not normalized:
        return InputDecision(action="allow")

    if any(pattern.search(normalized) for pattern in (
        _INSTRUCTION_OVERRIDE,
        _UNRESTRICTED_ROLE,
        _OBEY_USER,
        _REVEAL_INTERNAL,
    )):
        return InputDecision(
            action="blocked",
            guardrail_id="instruction_override",
            category="security",
            answer=(
                "No puedo cambiar mis instrucciones ni revelar contenido interno. "
                "Puedo ayudarte con soporte, servicios y procesos de Nexova."
            ),
        )

    if _PERSONAL_REQUEST.search(normalized) or _ACADEMIC_TASK.search(normalized):
        return InputDecision(
            action="blocked",
            guardrail_id="personal_use",
            category="content",
            answer=(
                "No puedo ayudar con tareas personales. Sí puedo ayudarte con "
                "soporte interno, servicios y procesos de Nexova."
            ),
        )

    if "hora" in normalized and any(place in normalized for place in ("tokio", "japon")):
        current_time = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%H:%M")
        return InputDecision(
            action="redirected",
            guardrail_id="small_talk",
            category="content",
            answer=(
                f"Ahora son las {current_time} en Tokio. ¿Te ayudo con alguna "
                "consulta de soporte o de Nexova?"
            ),
        )

    if re.fullmatch(r"(hola|buenos dias|buenas tardes|buenas noches|gracias|de nada|"
                    r"como estas|how are you)[.!? ]*", normalized):
        response = (
            "De nada. ¿Te ayudo con otra consulta de Nexova?"
            if normalized.startswith(("gracias", "de nada"))
            else "¡Hola! ¿En qué puedo ayudarte con soporte o procesos de Nexova?"
        )
        return InputDecision(
            action="redirected",
            guardrail_id="small_talk",
            category="content",
            answer=response,
        )

    if not _DOMAIN_TERMS.search(normalized):
        return InputDecision(
            action="redirected",
            guardrail_id="out_of_domain",
            category="content",
            answer=(
                "Puedo ayudarte con consultas relacionadas con Nexova: soporte, "
                "servicios, procesos, incidentes o inventario."
            ),
        )

    return InputDecision(action="allow")

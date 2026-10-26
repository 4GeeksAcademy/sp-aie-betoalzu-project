# Generación y evaluación de respuestas RFP (Parte 2)

La Parte 2 se ejecuta sobre el handoff persistido por la recepción RFP. No recibe ni convierte el PDF. Solo procesa los departamentos presentes en `active_workstreams`, con sus `key_aspects` y metadatos compartidos; cada generador recibe exclusivamente los aspectos de su propio departamento.

## Contrato de evaluación y handoff

Cada sección conserva `draft_content` y `evaluation_results` juntos. El objeto persistido en `evaluation_results` usa `schema_version: "1.0"`, `iteration_count`, `section_status` y el resultado estructurado con:

- `section_id` y `draft_sha256` del borrador evaluado;
- `readability` (`pass`, `score`, `details`);
- `relevance` (`pass`, `missing_aspects`);
- `compliance` (`pass`, `rule_ids`, `violations`);
- `overall_pass` y `feedback_for_generator`.

El digest permite comprobar que la evaluación describe exactamente el borrador que se guarda. El handoff de Parte 3 incrementa `schema_version` a `"2.0"` y conserva todas las secciones activas, incluido el último borrador de las que requieren revisión humana.

## Decisiones de generación y evaluación

- El máximo es **3 evaluaciones válidas por sección**; cada evaluación válida cuenta como un intento de generación. Un error técnico antes de producir una evaluación estructurada no aumenta el contador.
- La legibilidad usa una métrica heurística reproducible en español: promedio de palabras por oración, aprobada con un máximo de 25. `score` vale 100 hasta 20 palabras por oración y desciende dos puntos por palabra adicional; es una señal de longitud, no de calidad comercial.
- Pertinencia se evalúa mediante un agente estructurado por departamento, usando los metadatos compartidos, los aspectos de ese departamento y el borrador. Las preguntas abiertas no se convierten en hechos.
- Cumplimiento se evalúa con reglas deterministas del briefing. La moneda no pasa si la sede es desconocida; la ausencia de sede se informa como no verificable, no como una moneda inferida.
- Las evaluaciones de legibilidad, pertinencia y cumplimiento se ejecutan en paralelo y se combinan después. El feedback enumera omisiones y violaciones concretas.
- Las secciones aprobadas no se regeneran cuando otra sección falla. Una sección solo reintenta con su último borrador y feedback; al llegar al máximo conserva evaluación/borrador y queda `needs_human_review`.
- El ticket se entrega a Parte 3 en `en-evaluación` si todas las secciones pasan, o `needs_human_review` si alguna agota los intentos.

La generación usa agentes estructurados del pipeline existente. Las pruebas sustituyen esos agentes y no requieren LLM en vivo ni servicios externos.

## Ejecución y persistencia HTTP

El endpoint autenticado `POST /rfp-intake/tickets/{ticket_id}/generate` inicia la Parte 2 solo para tickets en `analisis_completo`. La API carga y contrasta el handoff, metadatos y secciones persistidos; no lee el PDF. Cada evaluación válida actualiza el borrador y su resultado estructurado en la fila de sección. Al finalizar, la API actualiza el handoff y el estado del ticket en una transacción.

Los errores técnicos se registran sin guardar el detalle del documento, devuelven el ticket a `analisis_completo` y permiten reintentar. Las secciones ya evaluadas se reutilizan al reanudar. Las ejecuciones interrumpidas se vuelven recuperables tras el umbral de obsolescencia existente; cada callback verifica la marca de inicio de su ejecución para evitar que una ejecución antigua sobrescriba un reintento.

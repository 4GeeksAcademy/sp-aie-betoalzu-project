# Generación y evaluación de respuestas RFP (Parte 2)

La Parte 2 se ejecuta sobre el handoff persistido por la recepción RFP mediante un grafo LangGraph dedicado. No recibe ni convierte el PDF. El grafo hace fan-out con `Send` solo a los departamentos presentes en `active_workstreams`; cada generador recibe metadatos compartidos sin extractos y los `key_aspects` de su propio departamento. Dentro de cada sección, legibilidad, pertinencia y cumplimiento se evalúan en paralelo y se agregan antes de iterar.

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

## Aprobación y cierre (Parte 3)

La Parte 3 consume el handoff persistido `2.0`; no lee el PDF. `POST /rfp-intake/tickets/{ticket_id}/approvals/start` valida que cada departamento activo tenga su borrador y evaluación compatibles y crea una rama durable por equipo con `thread_id=rfp-{ticket_id}:{department_id}`. Las ramas son filas separadas: las decisiones de un departamento no esperan a que otro reanude.

La aprobación está autorizada para usuarios autenticados con rol `admin`, según la autorización operativa confirmada para el flujo. La interfaz muestra el responsable departamental del briefing, pero no confía en nombres de perfil autodeclarados para autorizar acciones. El alta pública crea exclusivamente usuarios `user`; el primer administrador se provisiona una sola vez mediante `POST /auth/bootstrap-admin`, protegido por `ADMIN_BOOTSTRAP_TOKEN`. Esa variable debe configurarse como secreto del entorno backend; si falta, el endpoint queda deshabilitado. Después del bootstrap, un admin puede provisionar usuarios mediante `POST /users/admin`.

Una decisión se envía por `POST /rfp-intake/tickets/{ticket_id}/approvals/{department_id}/decision` con `action` (`approve`, `reject` o `request_changes`), `draft_sha256`, `draft_version` y, para rechazo/cambios, comentario no vacío. Las decisiones guardan usuario, comentario, digest, versión, timestamp y snapshot de la sección/evaluación. Hay una restricción única por ticket, departamento, digest y versión; repetir la misma solicitud es idempotente y una decisión diferente para esa versión se rechaza.

`reject` y `request_changes` reabren únicamente la sección afectada y reutilizan el grafo de Parte 2. El límite centralizado sigue siendo de tres evaluaciones válidas; al agotarlo se preservan el último borrador/evaluación y la decisión para resolución humana. Una nueva versión invalida el sign-off anterior y deja la misma rama pendiente sobre el nuevo digest y versión.

Si una generación de revisión se interrumpe por un error técnico, un admin puede reanudarla con `POST /rfp-intake/tickets/{ticket_id}/approvals/{department_id}/resume`; el endpoint exige que la rama conserve el borrador, la evaluación `needs_revision` y la versión que originó la revisión.

El arbitraje es determinista y usa únicamente evidencia estructurada persistida:

- `support-sla-missing`: se dispara por la infracción estructurada `outsourced_support_sla_24_hours`; bloquea la aprobación y solicita cambios según la regla del briefing.
- `currency-mismatch`: compara las monedas detectadas estructuradas (`currencies_mentioned`) con `client_hq` y con el resto de secciones.
- `ttc-vs-training-window`: requiere campos etiquetados de días hábiles y una cohorte o roles explícitamente coincidentes; texto sin esos campos no activa el trigger.

Cada arbitraje conserva trigger, departamentos afectados, regla fija, evidencia y snapshots. Sus salidas se registran sin delegar desempate a un LLM. Si una revisión agota el límite, el ticket queda en `needs_human_review`, sin síntesis automática.

Tras el sign-off vigente de todas las secciones activas y sin conflictos, se persiste una sola fila `RfpFinalDocument` en formato JSON con secciones aprobadas, moneda, versión, timestamp y digests. El guardado del artefacto y el paso a `terminado` comparten transacción. `GET /rfp-intake/tickets/{ticket_id}/final-document` entrega el adjunto solo a quien puede consultar el ticket; no se envía al cliente.

El backoffice expone borradores, evaluaciones, estados, decisiones y la descarga final. Las pruebas de Parte 3 usan fixtures, SQLite y agentes simulados; no requieren LLMs ni servicios externos.

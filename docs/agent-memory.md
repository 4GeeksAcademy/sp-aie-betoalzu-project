# Memoria operativa del agente de soporte

La memoria es un SQLite independiente de los checkpoints y de Qdrant. El agente solo acepta recuerdos del área `support` en estas categorías: `escalation_procedure`, `customer_preference` e `incident_pattern`. Cada consulta autenticada recupera hasta cinco recuerdos relevantes, limitados al área y al `customer_id` exacto; los recuerdos generales también pueden aplicarse. El agente no escribe en el corpus RAG.

`POST /agent/query` devuelve un `conversation_id` UUID. Envíalo en los mensajes posteriores de esa conversación y, para una regla específica de una empresa cliente, añade su identificador opaco en `customer_id`. Una propuesta se muestra en la respuesta, pero no crea memoria activa. Solo `admin` y `manager` pueden proponer o resolver propuestas. Al responder explícitamente sí, no o con una corrección, el agente clasifica la intención antes de procesar el resto del mensaje. Si el mensaje contiene además una consulta, se resuelve la propuesta y después se procesa esa consulta.

## Ciclo aprobado reproducible

1. Un usuario `manager` envía `¿Cuál es el procedimiento para escalar tickets premium?` con un `conversation_id` nuevo. La generación estructurada propone: `Los tickets urgentes premium se asignan directamente a un agente senior.` La respuesta pregunta si debe recordarlo. `agent_memory` sigue sin ese recuerdo; la propuesta está pendiente siete días.
2. El mismo actor envía `Sí, confirmo.` con el mismo `conversation_id`. La intención se clasifica como `approve`, la decisión y el recuerdo se escriben en una transacción, y la respuesta confirma el guardado.
3. En otra consulta sobre tickets premium con ese `conversation_id`, la recuperación devuelve el recuerdo dentro del contexto acotado. Si no existe referencia documental que lo verifique, se etiqueta `pending_verification`; no prevalece sobre una fuente operativa vigente.

Se puede ejecutar este ciclo sin LLM ni Qdrant con:

```bash
pytest -q tests/pipelines/test_support_agent_memory.py::test_agent_runs_approval_and_later_retrieves_memory
```

## Ciclo rechazado reproducible

1. Un usuario `manager` crea una propuesta válida para una regla de escalación. No aparece en los recuerdos activos mientras está pendiente.
2. El actor responde `No, rechazar.` con el mismo identificador de conversación. La decisión queda auditada; se elimina el contenido de la propuesta pendiente y el conjunto de recuerdos activos permanece idéntico.

La prueba offline del ciclo está en `tests/pipelines/test_support_agent_memory.py::test_rejection_is_audited_without_changing_active_memory`.

## Ejemplos que no generan recuerdos

- Consultas puntuales como «¿Cuántos tickets abiertos hay ahora?».
- Cierres sociales como «Perfecto, gracias por la explicación».
- Tareas de un solo uso como resumir un ticket para un informe.
- Correcciones que solo aplican a un ticket concreto.
- Datos personales de candidatos, CV, calificaciones, notas de entrevistas e información salarial de negociaciones activas.

Las propuestas con alcance incompleto, contenido prohibido o rol no autorizado no se guardan ni se incluyen en auditoría o trazas. La auditoría conserva metadatos y un hash del origen, nunca el mensaje completo. Una propuesta editada reemplaza a la anterior como única pendiente y requiere una aprobación nueva.

## Caducidad y consolidación

Las propuestas caducan a los siete días. Los recuerdos dejan de recuperarse tras 180 días sin uso y se eliminan en la siguiente consolidación. Los eventos de auditoría se conservan 365 días. La consolidación se ejecuta al arrancar y mediante una tarea asíncrona diaria; también se invoca antes de crear o resolver una propuesta.

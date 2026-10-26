# Especificacion de implementacion: generacion y evaluacion de respuestas a RFP

## Objetivo

Implementar la Parte 2 del flujo agéntico de RFPs de Nexova. A partir del handoff persistido por la Parte 1, generar una seccion de propuesta por cada departamento activo, evaluar cada seccion y devolver feedback accionable al generador cuando no cumpla. La salida, incluso si requiere revision humana, debe quedar persistida y lista para el handoff a la Parte 3.

Esta fase no recibe ni vuelve a analizar el PDF como entrada principal, no aprueba secciones y no genera el documento final.

## Fuentes de verdad

- Departamentos, responsables, formatos y reglas de negocio: [`docs/briefing-rft-intake.md`](../docs/briefing-rft-intake.md). Este es el documento que la solicitud llama `company-BRIEFING.md`; no se debe buscar ni crear un archivo adicional con ese nombre.
- Contrato de entrada: handoff de Parte 1 documentado en [`specs/rfp-intake-workflow.md`](./rfp-intake-workflow.md).
- Persistencia y HTTP: extender las entidades, transacciones, autenticacion y backend existentes bajo `services/`; no crear un segundo API ni sustituir PostgreSQL/Supabase por TinyDB o JSON.
- Logica de agentes y orquestacion: extender el grafo dedicado en `data/pipelines/rfp_intake/`; no mezclarlo con el grafo CX.

## Alcance y restricciones

- Consumir tickets en `analisis_completo` desde el handoff de Parte 1: `ticket_id`, metadatos normalizados, departamentos activos y `key_aspects` por departamento. No reingerir el PDF ni reconstruir el analisis.
- Procesar unicamente los departamentos presentes en el handoff. Usar exactamente los IDs `seleccion`, `capacitacion` y `soporte`; nunca activar departamentos por defecto.
- Crear un generador identificable por departamento. Cada uno recibe los metadatos compartidos y los aspectos relevantes de su propio departamento, no las secciones completas de otros departamentos como fuente de hechos.
- No inventar precios, presupuestos, volumenes, fechas, personal, compromisos operativos ni datos de empresa ausentes. Reflejar incertidumbres y preguntas abiertas del handoff, sin convertirlas en hechos o promesas.
- Mantener la generacion y evaluacion en el pipeline existente. Extender los endpoints existentes solo si hace falta exponer estado o resultados; no añadir un servidor HTTP nuevo.
- La base de conocimiento semantica es opcional. Si se reutiliza una integracion ya disponible, solo puede apoyar al generador con contexto empresarial; su indisponibilidad no debe bloquear la Parte 2 ni permitir que el generador invente politicas. No se requiere crear o reindexar una base de conocimiento para esta tarea.

## Contratos de entrada, salida y persistencia

### Entrada

Antes de ejecutar agentes, cargar y validar el handoff del ticket. Debe haber un `ticket_id`, metadatos de RFP y al menos un departamento activo con sus `key_aspects`. Si falta o es incompatible alguno de estos datos, registrar un error trazable y no generar una respuesta con valores inventados ni tratar el ticket como descartado.

El estado inicial esperado del ticket es `analisis_completo`. La ejecucion debe ser idempotente o detectar una ejecucion previa para evitar crear secciones duplicadas al reintentar.

### Seccion departamental

Persistir para cada departamento activo, como minimo:

- `ticket_id` y `department_id`.
- `draft_content`, incluido el ultimo borrador aunque no haya aprobado.
- Estado de la seccion, numero de iteraciones y resultado de evaluacion asociado al borrador.
- Metadatos de ejecucion necesarios para reintentar o continuar el ticket sin perder el ultimo resultado.

Reutilizar las entidades y relaciones existentes de Parte 1. Guardar el contenido y su evaluacion de forma consistente: un `EvaluationResult` debe describir exactamente el borrador que se conserva. Las escrituras finales de una seccion y la actualizacion del ticket deben usar la capa transaccional existente cuando corresponda.

### Resultado de evaluacion

Persistir un objeto estructurado equivalente a:

```text
EvaluationResult:
  section_id / department_id
  readability:
    pass: bool
    score: number
    details: string
  relevance:
    pass: bool
    missing_aspects: string[]
  compliance:
    pass: bool
    rule_ids: string[]
    violations: string[]
  overall_pass: bool
  feedback_for_generator: string
```

Los nombres pueden adaptarse al modelo existente, pero no se debe reemplazar la estructura por una evaluacion en texto libre. `feedback_for_generator` debe nombrar los defectos observados y las correcciones solicitadas; no incluir instrucciones ambiguas como "mejorar la propuesta". El resultado combinado solo pasa si pasan legibilidad, pertinencia y cumplimiento.

### Handoff a Parte 3

El handoff debe conservar, por cada departamento activo, el borrador vigente, su resultado estructurado mas reciente, el estado de la seccion y si necesita revision humana. Incluir igualmente las secciones que agotaron iteraciones; no filtrar ni descartar el ticket por una evaluacion fallida.

## Flujo de generacion y evaluacion

1. **Consumir el handoff.** Cargar los datos persistidos de Parte 1 y determinar los departamentos activos a partir de ese payload.
2. **Generar por departamento.** Ejecutar un generador dedicado para cada departamento activo. Procesar departamentos independientes en paralelo cuando el runtime lo permita.
3. **Evaluar cada borrador en paralelo.** Ejecutar, por seccion, evaluaciones independientes de:
   - **Legibilidad:** calcular una metrica reproducible (se recomienda `py-readability-metrics`), devolver puntuacion, detalles y resultado de aprobacion. Documentar la metrica, el idioma/unidad y el criterio de aprobacion usado; no presentar la puntuacion como medida de calidad de negocio.
   - **Pertinencia:** comparar la seccion con los `key_aspects`, el alcance y las preguntas abiertas recibidas. Enumerar los aspectos relevantes que falten; no exigir datos que el handoff no contiene como si fueran hechos conocidos.
   - **Cumplimiento:** comprobar reglas concretas del briefing, no emitir una opinion de estilo libre.
4. **Combinar resultados.** Un nodo o paso de agregacion reune los resultados de los evaluadores, calcula `overall_pass` y genera feedback. Los evaluadores paralelos devuelven resultados independientes; no escriben concurrentemente en el mismo campo compartido del estado.
5. **Iterar solo la seccion fallida.** Si `overall_pass` es falso y quedan iteraciones, enviar al generador de ese departamento el borrador y el feedback concreto. Los departamentos/secciones que ya pasaron no se regeneran por el fallo de otra seccion.
6. **Limitar los ciclos.** Definir un maximo finito de iteraciones y contar de manera consistente cada intento de generacion. El limite debe estar centralizado, documentado y probado; un reintento tecnico no debe consumir una iteracion de calidad si no produjo una evaluacion valida.
7. **Finalizar cada seccion.** Al aprobar, conservar borrador y evaluacion. Al agotar el limite sin aprobar, conservar el ultimo borrador y su `EvaluationResult`, marcar la seccion `needs_human_review` y continuar al handoff. Nunca descartar el ticket completo por ese motivo.
8. **Actualizar el ticket y persistir.** Reflejar el progreso durante el trabajo. Solo marcar `needs_human_review` como estado del ticket si al menos una seccion activa agoto el limite. Si todas pasan, persistir el handoff y mantener `en_evaluación` hasta que la Parte 3 consuma el handoff y asigne su propio estado. Persistir el handoff antes de considerar completada la ejecucion.

Los estados permitidos del ticket para esta fase son:

| Estado | Uso |
| --- | --- |
| `analisis_completo` | Entrada desde la Parte 1; no reescribir el resultado del analisis |
| `generando_borrador` | Hay generadores produciendo o revisando secciones |
| `en_evaluación` | Hay evaluadores o ciclos de evaluacion en ejecucion |
| `needs_human_review` | Una o mas secciones agotaron el limite y pasan a Parte 3 con borrador y evaluacion |

No crear ni asignar estados de Parte 3 como `esperando_aprobación` o `terminado`; la Parte 3 es responsable de esa transicion.

## Reglas de cumplimiento del briefing

La evaluacion de cumplimiento debe verificar, cuando la regla aplique al servicio y a los datos de la RFP:

| ID estable sugerido | Regla |
| --- | --- |
| `satisfaction_guarantee_90_days` | Toda propuesta incluye la garantia de satisfaccion estandar de Nexova a 90 dias. |
| `currency_matches_client_hq` | Cotizar en EUR para sede en Espana y en USD para Miami/EE. UU., derivando la moneda de `client_hq`. Si la sede no esta especificada, no inventar una moneda ni declarar cumplimiento. |
| `executive_search_minimum_15_business_days` | Una propuesta de busqueda ejecutiva no compromete un cierre menor a 15 dias habiles. |
| `outsourced_support_sla_24_hours` | Una propuesta de soporte outsourced menciona explicitamente un SLA de respuesta de 24 horas. |
| `anonymize_current_client_references` | No incluir nombres de clientes actuales sin anonimizar; usar referencias genericas, por ejemplo, "cliente del sector retail". |

`rule_ids` debe identificar las reglas verificadas y `violations` describir las ausencias o contradicciones. No marcar una regla como aprobada por omision de informacion. El evaluador debe distinguir los datos desconocidos de una infraccion verificable. Las pruebas de cumplimiento deben incluir al menos una violacion explicita anclada a una regla de esta tabla.

## Pruebas y criterios de aceptacion

Anadir pruebas unitarias focalizadas bajo `tests/pipelines/`. Las pruebas de modelos generativos, evaluadores, persistencia y concurrencia deben poder ejecutarse sin llamar a un LLM en vivo ni a servicios externos.

- Un generador por departamento produce una seccion usando el payload del handoff y el identificador correcto.
- El flujo consume `ticket_id`, metadatos y `key_aspects` persistidos de Parte 1; no vuelve a parsear el PDF para redactar.
- Evaluadores de legibilidad, pertinencia y cumplimiento producen campos estructurados. Los evaluadores se ejecutan en paralelo y sus resultados se combinan sin escrituras concurrentes conflictivas.
- Una evaluacion fallida genera feedback accionable y hace que vuelva a ejecutarse solo el generador de la seccion correspondiente.
- Una evaluacion aprobada detiene las iteraciones de esa seccion, aunque otra seccion siga iterando o necesite revision.
- Una prueba de compliance demuestra que una regla concreta del briefing (por ejemplo, una promesa de cierre ejecutivo menor a 15 dias habiles o la omision del SLA de 24 horas en soporte) produce `compliance.pass == false` y una infraccion identificable.
- Al alcanzar el maximo, el ultimo borrador y su evaluacion permanecen persistidos, la seccion queda `needs_human_review` y el handoff incluye esa seccion.
- El estado del ticket corresponde al progreso real y no se usan estados reservados a Parte 3.
- Los reintentos tecnicos y la reanudacion no duplican secciones ni pierden el ultimo borrador/evaluacion.

La Parte 2 esta lista cuando cada departamento activo tiene un borrador y una evaluacion estructurada persistidos, las secciones aprobadas y las que necesitan revision se distinguen claramente, y la Parte 3 puede consumir todos esos resultados sin acceder de nuevo al PDF.

## Decisiones que deben quedar documentadas durante la implementacion

- El limite de iteraciones y si el conteo representa intentos de generacion o ciclos completos.
- La metrica de legibilidad, su idioma/unidad y el umbral que determina `pass`.
- El criterio para `relevance.pass`, basado en los `key_aspects` y preguntas abiertas.
- El esquema persistido/versionado de `EvaluationResult` y el contrato de handoff a Parte 3.
- Como se agregan los estados de las secciones al estado unico del ticket y como se reanuda un ticket interrumpido.

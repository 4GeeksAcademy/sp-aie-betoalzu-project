# Especificacion de implementacion: aprobacion y cierre de RFP

## Objetivo

Implementar la Parte 3 del flujo de RFP de Nexova. A partir del handoff persistido por la Parte 2, cada departamento activo debe revisar y aprobar su seccion mediante una decision humana persistida. Cuando todas las secciones requeridas esten aprobadas, generar y guardar automaticamente el documento final para Ventas.

La Parte 3 completa el mismo ticket iniciado en la Parte 1. No debe volver a leer el PDF ni tratar la evaluacion automatica de la Parte 2 como aprobacion humana.

## Fuentes de verdad

- Reglas y contexto de negocio: [`docs/rfp-response-generation.md`](../docs/rfp-response-generation.md). Este es el archivo del repositorio al que la solicitud adjunta se refiere como `company-BRIEFING.md`; no buscar ni crear otro archivo con ese nombre.
- Contrato de entrada y persistencia de Parte 1: [`specs/rfp-intake-workflow.md`](./rfp-intake-workflow.md).
- Contrato de borradores, evaluaciones y handoff de Parte 2: [`specs/rfp-response-generation.md`](./rfp-response-generation.md).
- Extender el backend, la autenticacion y la persistencia existentes bajo `services/`; extender el flujo dedicado de RFP bajo `data/pipelines/rfp_intake/`. No crear otro servidor HTTP ni conectar este flujo al agente CX.

### Decisiones de negocio requeridas antes de implementar

El briefing de referencia debe ser la autoridad para los aprobadores por departamento, los triggers de conflicto, el arbitro fijo y el formato del documento final. Si esos datos no estan definidos explicitamente en `docs/rfp-response-generation.md` o en una fuente de negocio que el equipo confirme, no inventarlos ni deducirlos de nombres de agentes o responsables de Parte 1. Registrar la decision pendiente y solicitarla antes de habilitar el comportamiento correspondiente.

## Alcance y restricciones

- Consumir el handoff persistido por Parte 2, incluyendo todas las secciones activas, el ultimo `draft_content`, su `EvaluationResult`, el estado y la version del esquema. No regenerar ni reanalizar el documento de entrada para iniciar una aprobacion.
- Crear tareas de aprobacion solo para los departamentos incluidos en el handoff; no activar departamentos por defecto.
- Cada aprobacion, rechazo o solicitud de cambios debe estar asociada a un usuario autenticado autorizado para ese departamento, seccion y ticket.
- La interrupcion y reanudacion deben ser durables e idempotentes. Reanudar no debe reiniciar la Parte 1, la Parte 2 ni las ramas ya completadas.
- No guardar la RFP completa ni secretos en logs. La auditoria debe protegerse con los mismos controles de acceso que el ticket.
- No enviar automaticamente el documento al cliente. La salida de esta fase es un documento final guardado y accesible para Ventas.

## Estados del ticket

Usar la misma fila y los estados existentes. En esta fase:

| Estado | Uso |
| --- | --- |
| `en-evaluación` / `needs_human_review` | Entrada desde Parte 2; existen borradores y evaluaciones para aprobar |
| `esperando_aprobación` | Al menos una aprobacion humana esta pendiente |
| `terminado` | El documento final esta persistido y accesible |

No crear estados alternativos ni marcar el ticket `terminado` antes de confirmar la persistencia del documento final. Las transiciones deben conservar los resultados de Partes 1 y 2.

## Contrato de aprobacion

Cada solicitud de aprobacion debe mostrar al revisor, como minimo:

- ticket, departamento y aprobador asignado;
- contenido del borrador exacto sujeto a aprobacion;
- resumen de `EvaluationResult`, incluyendo omisiones, infracciones y necesidad de revision humana;
- contexto y preguntas abiertas pertinentes disponibles en el handoff, sin afirmar datos ausentes.

Aceptar unicamente acciones estructuradas: `approve`, `reject` o `request_changes`. Validar accion, identidad, permisos, version del borrador y comentario requerido para rechazo o cambios antes de reanudar el grafo. Rechazar entradas invalidas sin alterar la seccion ni el checkpoint.

Persistir por decision: ticket/seccion, departamento, usuario aprobador, accion, comentario cuando aplique, version o digest del borrador, timestamp y resultado. Una aprobacion solo es valida para el borrador identificado; si este cambia, requerir una nueva decision humana.

## Flujo y concurrencia

1. Validar que el ticket tiene un handoff de Parte 2 compatible y que cada seccion activa tiene borrador y evaluacion persistidos. Ante un contrato incompleto, detener el procesamiento y registrar un error trazable; no fabricar una seccion ni aprobarla.
2. Crear o reanudar una rama de aprobacion independiente por departamento activo. Antes de solicitar la decision humana, persistir el estado mediante el checkpointer.
3. Interrumpir la rama justo antes de aplicar la decision humana. La espera de una rama no debe impedir que otras ramas se ejecuten, se aprueben o queden a la espera de su propia decision.
4. Reanudar explicitamente la rama pendiente con la respuesta validada. No volver a ejecutar etapas completadas ni reemplazar resultados de otras ramas.
5. En `approve`, registrar el sign-off del borrador actual y completar esa rama.
6. En `reject` o `request_changes`, guardar la decision y el feedback. Enrutar solo esa seccion a la ruta de revision/generacion existente de Parte 2; el borrador actualizado debe volver a evaluarse y presentarse para una nueva aprobacion. El ciclo de revision debe tener un limite finito y centralizado, reutilizar el limite definido por Parte 2 cuando sea compatible y conservar el ultimo borrador/evaluacion al agotarlo. No continuar en ciclos ilimitados ni descartar el ticket. Si el limite de Parte 2 no permite completar la revision, detener la automatizacion y dejar la decision pendiente de resolucion humana conforme a las reglas de negocio aprobadas.
7. Cuando todas las ramas activas tengan sign-off valido, invocar el sintetizador final una sola vez con las secciones aprobadas. No incluir secciones rechazadas, pendientes o versiones antiguas.
8. Persistir el artefacto final y sus metadatos y, en la misma operacion transaccional cuando sea posible, marcar el ticket `terminado`. Si la generacion o persistencia falla, informar un fallo tecnico trazable y permitir reintentar sin duplicar el documento ni perder aprobaciones.

Se puede implementar cada rama como subgrafo/ejecucion por departamento o usar otra arquitectura equivalente, pero debe demostrar concurrencia real: una rama pausada no bloquea otra rama independiente. No simular este requisito ejecutando aprobaciones en serie.

## Checkpoint, idempotencia y auditoria

- Namespaciar `thread_id` por ticket y departamento, por ejemplo `rfp-{ticket_id}:{department_id}`. Ningun ticket ni departamento concurrente debe compartir checkpoint.
- Exponer una ruta explicita para reanudar una aprobacion pendiente. El inicio repetido y el envio repetido de la misma decision no deben duplicar auditorias, revisiones ni documentos.
- Proteger las escrituras frente a carreras: una respuesta tardia de una ejecucion anterior no puede sobrescribir una decision o version mas reciente.
- Registrar para cada nodo de negocio ejecutado el agente/nodo, ticket y departamento, referencias o representacion segura del input/output y timestamp. Restringir los datos sensibles y no registrar el PDF completo, credenciales ni tokens.
- Mantener trazabilidad de versiones para enlazar cada evaluacion, decision humana y seccion incluida en el documento final.

## Arbitraje de conflictos

- Implementar un nodo de arbitraje explicito, separado de los generadores y evaluadores.
- Dispararlo solo ante triggers estructurados definidos por el briefing; no interpretar texto libre con un LLM como unico detector de conflicto.
- Resolver cada conflicto con el arbitro fijo o la regla determinista definida en el briefing. Un LLM no puede votar, desempatar ni sustituir al arbitro.
- Registrar trigger, evidencia, regla/arbitro aplicado y resultado. No modificar sign-offs ya registrados fuera del alcance autorizado.
- No activar arbitraje con reglas inventadas. Si faltan triggers o arbitro en la fuente de verdad, tratarlo como decision de negocio pendiente y no habilitar una resolucion automatica.

## Documento final

- Generarlo automaticamente solo despues del sign-off de todas las secciones activas y de resolver los conflictos que requieran arbitraje.
- Consolidar unicamente las versiones aprobadas, preservando la estructura, formato y reglas definidas por el briefing.
- Guardar el artefacto en el mecanismo de almacenamiento existente, asociado al ticket y accesible por el equipo autorizado de Ventas.
- Persistir tipo/formato, ubicacion segura, version, timestamp y referencias/digests de las secciones incluidas. Evitar duplicados al reintentar.
- No afirmar en el documento precios, fechas, volumenes, SLA, compromisos ni datos ausentes del handoff o de la fuente de negocio.

## Interfaz y API

- Extender la interfaz del ticket en `uis/backoffice` para listar cada seccion, su estado, borrador, evaluacion y decision requerida.
- Permitir que un aprobador autorizado apruebe, rechace o solicite cambios, con feedback obligatorio para las dos ultimas acciones.
- Mostrar claramente si el ticket esta esperando aprobacion, requiere cambios, tiene un conflicto en arbitraje o esta terminado; presentar el enlace de descarga solo cuando el artefacto final este disponible.
- Reutilizar los endpoints, autenticacion y convenciones de respuesta del backend existentes. No exponer rutas locales del sistema de archivos ni aceptar ubicaciones arbitrarias del cliente.

## Pruebas y criterios de aceptacion

Las pruebas deben ser deterministas y no llamar a LLMs ni servicios externos. Usar mocks/fixtures y aprobaciones simuladas mediante la ruta real de reanudacion.

- Una rama se interrumpe antes del sign-off, persiste su checkpoint y reanuda desde ese punto con una decision valida.
- Una respuesta invalida o de un usuario sin permisos no cambia el estado ni la aprobacion.
- Se demuestra que el departamento B puede aprobarse mientras el departamento A sigue interrumpido; sus checkpoints y resultados son independientes.
- Una repeticion de inicio o `resume` no duplica decisiones, secciones ni artefactos, y una decision para un borrador obsoleto se rechaza.
- Rechazo/solicitud de cambios reabre solo la seccion correspondiente, conserva historial y respeta el limite finito de revisiones.
- El limite de iteraciones es alcanzable y verificable en pruebas; al agotarlo se conserva el ultimo borrador y se evita un loop infinito.
- El arbitraje se activa ante un trigger configurado, usa el arbitro/regla fijo y no delega la decision a un LLM.
- No se genera documento final mientras exista una seccion pendiente, rechazada o en arbitraje.
- Con todas las secciones aprobadas, el documento final contiene solo las versiones aprobadas, se persiste y el ticket pasa a `terminado`.
- Un fallo de sintesis/persistencia no pierde sign-offs y permite reintentar sin duplicados.
- Una ruta E2E reproducible recorre Parte 1, Parte 2 y Parte 3 con fixtures y resumes simulados, verificando estados, datos y mensajes consistentes en las transiciones.
- Las pruebas unitarias en `tests/pipelines/` cubren interrupcion/reanudacion, limite de iteraciones, arbitraje y aprobacion paralela bajo interrupcion.

La Parte 3 esta lista cuando una RFP puede recorrer las tres partes sin saltos de estado, las decisiones humanas son auditables y reanudables por departamento, y el documento final solo queda accesible tras la aprobacion de todas las secciones requeridas.

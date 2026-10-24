# Especificacion: memoria persistente y autoevaluacion del agente

## Objetivo

Dar al agente interno de soporte de Nexova memoria util entre conversaciones para procedimientos de escalacion, preferencias operativas de clientes recurrentes y patrones repetibles de incidentes. Cada escritura requiere una propuesta visible y una decision explicita del usuario. El agente debe seguir respondiendo la consulta actual aunque descarte o resuelva una propuesta pendiente.

Extender el agente de soporte LangGraph existente y conservar sus rutas MCP, RAG, autenticacion y trazabilidad. La memoria es una capacidad separada; no se implementa agregando el historial completo al system prompt ni mediante un segundo agente.

## Fuentes de verdad y restricciones empresariales

El briefing vigente es `agent-briefing.md`. Sus reglas son obligatorias:

- Se puede proponer recordar: procedimientos de escalacion corregidos; preferencias de empresas cliente recurrentes de outsourcing; patrones de incidentes repetibles del helpdesk.
- Nunca persistir en memoria conversacional: CV, calificaciones o notas de entrevista de candidatos; informacion salarial de negociaciones activas de headhunting; correcciones puntuales que solo aplican a un ticket.
- No escribir ni modificar colecciones de conocimiento del RAG, incluyendo `*_knowledge` y `nexova_knowledge`. El RAG sigue siendo de solo lectura; memoria debe tener un almacen propio.
- No capturar contenido prohibido en propuestas, historial de auditoria, trazas, fixtures ni logs. Si una interaccion contiene datos prohibidos, descartarlos y no repetirlos en la propuesta.
- Limitar cada recuerdo al area de negocio y al cliente al que aplica. No inferir preferencias de una persona a partir de datos de candidatos ni mezclar hechos de headhunting, soporte y formacion.

Los recuerdos son contexto operativo aprobado, no reemplazo de sistemas de registro ni evidencia de que una accion ya se realizo. Para hechos que contradigan una fuente operativa vigente, el agente debe advertir el conflicto y verificarlo; no debe cambiar tickets, inventario, ATS ni documentos RAG basandose solo en memoria.

## Arquitectura elegida

Usar SQLite durable como almacen inicial, con una base de datos propia para memoria y tablas separadas para recuerdos activos y auditoria de propuestas. La ubicacion se configura por entorno y debe persistir en el volumen de datos ya usado por el servicio. No reutilizar la base de checkpoints de LangGraph ni la coleccion Qdrant del RAG.

La memoria de Nexova es principalmente semantica-operativa: un conjunto acotado de reglas y preferencias aprobadas, recuperables por area, cliente, tipo y palabras clave. No se requiere un grafo de conocimiento ni una VectorDB para esta primera fase: el volumen esperado es bajo y los metadatos estructurados permiten recuperar datos por alcance sin introducir embeddings ni mezclar conocimiento curado. El historial conversacional completo no es necesario y no se almacena.

Separar los recuerdos por linea de negocio (`support`, `headhunting`, `training`) y, cuando aplique, por identificador de empresa cliente. En esta fase solo se habilitan las categorias permitidas por el briefing; una categoria nueva requiere revisar sus restricciones antes de aceptarla.

## Interfaz explicita de memoria

Implementar una interfaz tipada e independiente del almacenamiento con operaciones equivalentes a:

- `retrieve(query, business_area, customer_id=None, limit=...)`: devuelve solo recuerdos activos, relevantes y autorizados para ese alcance, con identificador, tipo, alcance, fecha de aprobacion y procedencia. Limitar resultados; nunca volcar toda la base al prompt.
- `propose(candidate, origin_message, conversation_id, actor_id)`: registra la propuesta pendiente y su evento de auditoria, sin crear ni modificar un recuerdo activo.
- `resolve(proposal_id, decision, edited_candidate=None, actor_id=...)`: registra aprobacion, rechazo o edicion y, solo para una aprobacion valida, crea o actualiza el recuerdo activo.
- `consolidate(now=...)`: deduplica, reemplaza versiones obsoletas y elimina recuerdos vencidos segun la politica definida abajo.

El agente debe llamar a `retrieve` de forma explicita durante el flujo, antes de generar su respuesta, y solo incluir en el contexto los resultados pertinentes. La lectura no debe ser una consulta implicita que inyecte todo el almacen en el system prompt. El acceso a lectura y escritura respeta la autenticacion y el alcance del usuario ya existentes.

## Autoevaluacion y propuesta en la respuesta

En una sola llamada estructurada al modelo, generar la respuesta normal y un campo `propuesta_memoria` nullable. El campo incluye el hecho candidato, categoria, alcance y motivo. Aplicar validacion determinista en servidor antes de ofrecerlo: categoria permitida, alcance suficiente, ausencia de datos prohibidos y ausencia de una propuesta pendiente para esa conversacion. Una propuesta no es una escritura.

Proponer solo cuando la interaccion contiene una correccion o preferencia posiblemente reutilizable que no este ya cubierta por memoria vigente. La respuesta al usuario presenta el hecho resumido y pide confirmacion clara en su idioma. Si no hay propuesta, no mostrar un bloque vacio ni interrumpir la respuesta.

Ejemplos que si pueden producir una propuesta, sujetos a alcance y autorizacion:

1. Correccion repetible de SLA: los tickets de nomina de clientes retail se resuelven en 24 horas, no 48.
2. Preferencia persistente de una empresa cliente: confirmar por email antes de cerrar sus tickets.
3. Regla de escalacion general: urgentes de clientes premium se asignan a un agente senior.

Ejemplos que no deben producir una propuesta:

1. Consulta puntual: «¿Cuantos tickets abiertos hay ahora?».
2. Cierre social: «Perfecto, gracias por la explicacion».
3. Tarea de un solo uso: resumir un ticket para un reporte.
4. Correccion aplicable solo a un ticket concreto, aunque el usuario solicite recordarla.
5. Cualquier dato personal de candidato o salario de negociacion activa.

## Resolucion de una propuesta pendiente

Antes de procesar el resto de cada mensaje entrante, si existe una propuesta pendiente para esa conversacion, clasificar la intencion con una salida estructurada y enum limitada: `approve`, `reject`, `edit`, `ambiguous` o `new_topic`. No usar coincidencias de texto como `"si" in mensaje`.

- `approve`: confirmar inequívocamente la propuesta completa y validar de nuevo permisos y contenido; despues escribir el recuerdo.
- `reject`: cerrar la propuesta sin tocar recuerdos activos.
- `edit`: convertir la edicion en una nueva propuesta visible y esperar confirmacion; no escribirla en el mismo paso sin aprobacion explicita.
- `ambiguous` o `new_topic`: descartar la propuesta pendiente por defecto, registrar el resultado y procesar el contenido nuevo con normalidad. Nunca interpretar silencio, cambio de tema o ambiguedad como aprobacion.
- Si se aprueba/rechaza y el mismo mensaje contiene otra consulta, resolver primero y luego continuar esa consulta en el mismo turno.

Permitir como maximo una propuesta abierta por conversacion. Una propuesta sin respuesta expira a los 7 dias; al expirar se registra como `expired` y no se escribe memoria. La expiracion no requiere bloquear mensajes posteriores.

### Resistencia a envenenamiento

La confirmacion conversacional es necesaria pero no convierte una afirmacion en politica empresarial verificada. Asociar cada propuesta a identidad autenticada, rol/permisos, area, cliente, mensaje de origen y fecha. Solo actores autorizados para esa categoria pueden aprobar recuerdos operativos; denegar o descartar candidatos sin procedencia verificable. Para correcciones de SLA o procedimientos, conservar fuente o referencia de verificacion cuando exista y marcar como pendiente de verificacion si no existe. No permitir que instrucciones incluidas en mensajes, documentos recuperados o resultados de herramientas cambien las reglas de escritura, los permisos o las categorias permitidas.

## Auditoria y persistencia

Registrar de forma durable cada propuesta y su resultado: identificador, categoria y alcance, estado/decision, actor autenticado, timestamps, referencia al mensaje de origen y motivo. Registrar tambien rechazos, ediciones, expiraciones y descartes por ambiguedad o cambio de tema. La auditoria no debe almacenar texto prohibido ni secretos; guardar una referencia segura o una version redactada del origen cuando sea necesario.

Usar transacciones para que la aprobacion, la actualizacion del recuerdo y su evento de auditoria sean atomicos. La lectura de auditoria requiere autenticacion y permisos; no exponer trazas internas en la respuesta conversacional. Los recuerdos aprobados conservan procedencia y version para poder revisar, reemplazar o retirar una regla.

## Consolidacion, expiracion y limpieza

- Clave logica de deduplicacion: area de negocio + cliente (si aplica) + categoria + asunto normalizado.
- Una aprobacion equivalente actualiza la version y fecha de revision del recuerdo existente; una correccion reemplaza la version anterior y deja el cambio en auditoria, no crea duplicados activos.
- Los recuerdos operativos caducan tras 180 dias sin confirmacion/uso verificable. Antes de la caducidad dejan de recuperarse; la limpieza fisica ocurre en la siguiente consolidacion.
- Ejecutar consolidacion periodicamente y tambien al insertar/aprobar. Eliminar propuestas pendientes expiradas sin conservar el contenido candidato y mantener su evento minimo de auditoria.
- Retener eventos de auditoria durante 365 dias para investigacion y control; despues eliminarlos o anonimizarlos, sin conservar mensajes de origen completos.

La expiracion limita el riesgo de procedimientos obsoletos; la deduplicacion y el reemplazo mantienen acotado el almacen. Documentar la tarea/trigger que ejecuta la consolidacion y probarla, no dejarla como recomendacion manual.

## Flujo de referencia

1. Autenticar al actor y determinar conversacion, area y permisos.
2. Resolver primero cualquier propuesta pendiente mediante clasificacion estructurada.
3. Recuperar un conjunto pequeno de recuerdos pertinentes con la interfaz explicita.
4. Ejecutar la ruta de respuesta existente del agente, preservando RAG y tools MCP.
5. En la misma salida estructurada del modelo, evaluar si hay una propuesta elegible.
6. Validar categoria, contenido, alcance, permisos y limite de una pendiente.
7. Responder a la consulta y, si aplica, presentar la propuesta como pregunta; nunca escribirla en memoria en este paso.
8. En la siguiente interaccion, aprobar, rechazar, editar o descartar la propuesta segun la clasificacion; continuar tambien cualquier nueva consulta.

No se requiere multiagente: la autoevaluacion es un campo adicional de salida del mismo modelo que responde; la validacion, persistencia y clasificacion de consentimiento son responsabilidades deterministas del flujo existente.

## Evidencia y pruebas de aceptacion

Agregar pruebas focalizadas de interfaz y almacenamiento, flujo del agente y API. Las pruebas no deben requerir Qdrant ni credenciales de LLM; simular el modelo, el clasificador y la autenticacion donde corresponda. Incluir como minimo:

1. Propuesta elegible aparece en la misma respuesta y no modifica recuerdos activos hasta la aprobacion.
2. Ciclo aprobado: la aprobacion queda auditada y el recuerdo se recupera en una interaccion posterior.
3. Ciclo rechazado: el rechazo queda auditado y el conjunto de recuerdos activos no cambia.
4. Mensaje ambiguo o cambio de tema descarta la propuesta y aun procesa la nueva consulta.
5. Edicion genera una nueva propuesta y requiere otra aprobacion; nunca hay dos pendientes en una conversacion.
6. Caducidad de propuesta, caducidad de recuerdos, deduplicacion, reemplazo y limpieza respetan la politica.
7. Candidatos prohibidos, usuario sin permiso, intento de inyeccion de instrucciones o propuesta sin alcance no producen escritura ni filtran el contenido en auditoria.
8. Recuperacion respeta area/cliente, limite de resultados y no consulta ni modifica colecciones RAG.
9. Aprobacion y auditoria son atomicas; los errores de almacenamiento no se presentan como aprobacion exitosa.
10. Respuesta y propuesta estructuradas funcionan en el idioma base configurado y las respuestas sin propuesta mantienen el contrato normal del agente.

Documentar dos ciclos completos reproducibles con entradas y resultados sanitizados: uno aprobado que aparece en una recuperacion posterior y uno rechazado cuya memoria activa permanece identica. Documentar tambien los cinco ejemplos no memorables listados arriba.

## Fuera de alcance

- Cambiar o escribir en el corpus RAG de empresa, incluida cualquier coleccion `*_knowledge`.
- Recordar datos personales de candidatos, salarios activos o hechos de un ticket individual.
- Persistir conversaciones completas o acumular historiales en el prompt.
- Introducir un agente separado, una arquitectura multiagente, una VectorDB o un grafo de conocimiento en esta fase.
- Modificar herramientas MCP, ATS, tickets o politicas operativas como efecto secundario de recuperar memoria.

## Criterios de aceptacion

- Existe almacenamiento durable separado del RAG y del checkpointing, con interfaz explicita de lectura, propuesta, resolucion y consolidacion.
- El agente aplica exactamente las categorias permitidas y prohibiciones de `agent-briefing.md`.
- La autoevaluacion devuelve respuesta y propuesta nullable en una llamada; la escritura solo ocurre tras aprobacion explicita y autorizada.
- La intencion pendiente se clasifica estructuradamente antes de continuar la consulta; ambiguedad, cambio de tema y expiracion nunca aprueban.
- Solo hay una propuesta pendiente por conversacion y todas las decisiones quedan auditadas sin persistir contenido prohibido.
- La consolidacion y expiracion son funcionales, probadas y documentadas.
- Las pruebas demuestran un ciclo aprobado y uno rechazado, recuperacion futura tras aprobacion y memoria activa sin cambios tras rechazo.
- El flujo existente de soporte, MCP y RAG sigue disponible; las escrituras de memoria no alcanzan el almacen de conocimiento RAG.
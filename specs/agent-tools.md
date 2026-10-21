# Especificacion: tools del agente de soporte LangGraph

## Objetivo

Ampliar el agente de soporte con tools de consulta sobre los servicios reales de Nexova. El agente debe escoger automaticamente entre consultar el RAG, consultar tickets de soporte o combinar ambas fuentes, y dejar constancia verificable de las fuentes usadas. Las respuestas nunca deben inventar datos operativos cuando una tool falla o no puede confirmar un recurso.

## Contexto y fuentes de verdad

- La especificacion de los pasos anteriores del agente esta en `specs/support-agent-langgraph.md`. Se deben conservar su grafo, API, persistencia, autenticacion y trazas existentes.
- Los tickets se consultan desde el gestor de incidentes existente, usando `GET /api/incidents` y/o `GET /api/incidents/{id}` o la capa de servicio/repositorio equivalente si comparte paquete con el agente.
- Los nombres, tipos y valores devueltos deben corresponder al contrato real de la API de incidentes. Antes de implementar, inspeccionar sus schemas, rutas y requisitos de autenticacion; no inventar un contrato incompatible.
- El RAG existente es la fuente para preguntas que dependen de documentos y conocimiento de Nexova. No duplicar ni reemplazar su recuperacion.
- El inventario es una fuente opcional: incluir su tool solo si el gestor de inventario existente puede consultarse desde esta aplicacion.

## Alcance

1. Definir e implementar una tool de solo lectura para consultar incidentes.
2. Incorporarla al grafo con una ruta condicional que la seleccione segun la pregunta del usuario.
3. Permitir consultas al RAG, a la tool o a ambas cuando la pregunta necesite informacion de las dos fuentes.
4. Hacer visible en la traza cada fuente consultada y el orden de ejecucion.
5. Agregar evaluaciones de enrutamiento que se ejecuten sin depender de servicios externos.
6. Como extension opcional, incorporar una tool de consulta de inventario con las mismas garantias.

Fuera de alcance: crear, actualizar o eliminar incidentes o productos; usar datasets simulados como fuente de respuestas; modificar el contrato de `POST /knowledge/query`; y cambiar el corpus o el ranking del RAG.

## Contrato y acceso a tickets

- La tool debe tener modelos tipados de entrada y salida. Aceptar identificador de ticket, filtros de busqueda o ambos, de acuerdo con lo que soporte la API existente.
- La salida debe exponer solo campos disponibles en el servicio real; como minimo, cuando existan, estado, categoria, origen y fechas. Los tipos deben reflejar el schema de la API.
- La tool debe consultar exclusivamente datos reales mediante HTTP al servicio o mediante su capa de servicio/repositorio en proceso. No crear una copia paralela ni incluir respuestas simuladas o valores hardcodeados.
- Usar solo operaciones de lectura (`GET`). No permitir operaciones de escritura ni esconderlas detras de esta tool.
- Si el servicio requiere autenticacion, cargar las credenciales de la configuracion/entorno y enviarlas usando el patron existente de llamadas backend-a-backend. Nunca guardar tokens o claves en codigo, prompts, fixtures o trazas. Si no requiere autenticacion, documentar ese hecho para la revision.
- Configurar un timeout explicito, numerico y finito para cada llamada. Usar 4 segundos como valor inicial, salvo que el cliente compartido ya defina un timeout equivalente.
- Tratar timeout, error de servicio y ticket inexistente como resultados no confirmados. El agente debe responder de forma honesta (por ejemplo, "no pude confirmar el estado de ese ticket ahora mismo") y no inferir ni inventar su estado.
- Distinguir un resultado vacio de un error tecnico si la API permite hacerlo; no devolver una respuesta de exito que oculte fallos.

## Tool opcional de inventario

Si existe un gestor de inventario utilizable, agregar una tool independiente para consultar productos/stock (por ejemplo, `GET /inventory/products`), con contrato tipado, timeout explicito, autenticacion segun corresponda y fallback honesto.

La tool de incidentes y la de inventario deben tener responsabilidades separadas. No crear una tool generica que consulte ambos dominios segun el caso.

## Enrutamiento del grafo

- Agregar un nodo dedicado a la consulta de incidentes y aristas condicionales para dirigir la ejecucion al RAG, a la tool, a ambos o a la respuesta, segun la informacion que solicite la pregunta.
- La decision debe derivarse de la pregunta del usuario; no exigir que este indique que fuente utilizar.
- Consultar la tool para datos operativos actuales o especificos de tickets; consultar el RAG para conocimiento documental. Si hacen falta ambos tipos de informacion, invocar ambas fuentes y combinar unicamente los datos que cada fuente confirme.
- Mantener cada nodo y tool con una unica responsabilidad. Reutilizar los nodos existentes del agente y evitar duplicar la recuperacion o generacion RAG.
- Representar el resultado de cada consulta con tipos/estados explicitos para diferenciar datos encontrados, ausencia del recurso y fallo de la fuente. No convertir un error de tool en datos normales para el generador.
- Ante un fallo, aplicar el fallback del dominio afectado. Si una respuesta requiere una fuente que no pudo consultarse, indicar esa limitacion y no completar el dato con una suposicion.

## Trazabilidad

- Extender la traza estructurada existente para registrar el nodo/tool ejecutado, su fuente (`rag`, `incidents` y, si aplica, `inventory`), el resultado (`success`, `not_found` o `failed`) y el orden de ejecucion.
- Registrar referencias o identificadores suficientes para entender de donde procede cada dato, sin guardar credenciales, headers, stack traces ni respuestas crudas que puedan exponer informacion sensible.
- La traza de una corrida debe permitir determinar claramente si se uso el RAG, una tool o ambos, y en que orden.
- Conservar los controles de acceso y el almacenamiento de trazas definidos en `specs/support-agent-langgraph.md`.

## Evaluaciones y pruebas

Agregar al menos dos evaluaciones nuevas que verifiquen el enrutamiento:

1. Una pregunta que requiera consultar un ticket y demuestre que se usa la tool, no el RAG.
2. Una pregunta documental que demuestre que se usa el RAG, no la tool.

Un caso adicional de fallback ante indisponibilidad del servicio de incidentes es recomendado. Si se implementa inventario, incluir tambien cobertura de su contrato, timeout y fallback.

Las pruebas deben verificar:

- La tool usa el contrato y la fuente reales, recibe correctamente la autenticacion configurada y solo realiza consultas.
- El timeout es finito y un fallo o timeout no bloquea el grafo ni produce un estado inventado.
- El ticket inexistente y los errores del servicio producen resultados/fallback distinguibles y honestos.
- Las rutas condicionales seleccionan la fuente adecuada sin instruccion explicita del usuario; cubrir RAG, tool y, si existe, ambos.
- La traza conserva fuentes y orden de ejecucion.
- Los casos offline no requieren credenciales, servicios HTTP, Qdrant ni un proveedor LLM. Usar dobles de prueba para verificar el enrutamiento; no presentarlos como fuente de datos de produccion.
- Se mantienen las rutas y el comportamiento de la especificacion existente del agente y de `POST /knowledge/query`.

## Criterios de aceptacion

- Hay un contrato de entrada/salida tipado para la consulta de incidentes, compatible con el servicio existente.
- La tool obtiene tickets reales, usa `GET` exclusivamente y gestiona autenticacion sin secretos hardcodeados.
- Cada llamada tiene un timeout explicito y numerico.
- Timeout, fallo del servicio y ticket inexistente no generan estados inventados y activan una respuesta honesta.
- El agente decide automaticamente entre RAG, tool o ambas fuentes de acuerdo con la pregunta.
- La traza muestra que fuentes se usaron y su orden.
- Hay al menos dos evaluaciones nuevas: una de enrutamiento a tool y otra de enrutamiento a RAG.
- Si se agrega inventario, su consulta es una tool independiente y aplica las mismas garantias.

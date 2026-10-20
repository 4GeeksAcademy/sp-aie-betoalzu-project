# Especificacion: agente de soporte con LangGraph

## Objetivo

Migrar el flujo de consulta RAG de Nexova a un grafo de LangGraph observable y evaluable, sin reescribir la recuperacion ni la generacion existentes. El agente debe conservar las respuestas ancladas en la base de conocimiento y permitir inspeccionar, despues de cada ejecucion, los nodos recorridos y sus resultados.

## Estado actual y fuentes de verdad

- La implementacion RAG que se debe reutilizar esta en `data_project/pipelines/rag.py` y exporta `retrieve(query, *, k=5, min_score=None)`, `generate_answer(question, context)` y `query(question)`.
- El flujo del agente debe importar `retrieve` y `generate_answer` por separado. No debe llamar a `query()` desde un nodo: `query()` vuelve a recuperar contexto y ocultaria la transicion que el grafo debe exponer.
- La base vectorial se prepara desde `data_project/process/knowledge_base.py`; la coleccion y las fuentes existentes son las del RAG de Nexova.
- La API existente incluye `POST /knowledge/query`, que se conserva y no cambia su contrato `{ "answer": "..." }`.
- La especificacion RAG vigente en `specs/rag-nexova-implementation.md` define las politicas de respuesta, fuentes y configuracion que el agente debe respetar.

## Alcance

1. Crear un modulo de agente dentro de `services/` que defina el estado, nodos, rutas condicionales, compilacion y ejecucion del grafo.
2. Reutilizar el RAG existente y conservar separadas las operaciones de recuperacion y generacion.
3. Guardar checkpoints durables y trazas estructuradas, consultables por identificador de ejecucion.
4. Exponer el grafo en un endpoint FastAPI independiente.
5. Crear evaluaciones reproducibles basadas en trazas ya guardadas, sin invocar Qdrant ni el proveedor LLM durante la evaluacion offline.

Fuera de alcance: historial completo de conversacion, memoria entre preguntas, cambios al corpus o al ranking RAG, cambios al endpoint existente y cambios al pipeline Prefect.

## Diseno del grafo

### Estado

Definir un estado minimo, tipado y serializable que incluya:

- `question`: pregunta recibida, preservada para trazabilidad.
- `context`: lista de chunks que devuelve `retrieve`; vacia antes de recuperar.
- `answer`: respuesta final o mensaje de abstencion/error validado.
- `error`: codigo/mensaje publico de validacion cuando la entrada no permite continuar; no guardar stack traces ni secretos.
- `run_id`: identificador estable de la ejecucion, utilizable para consultar traza y checkpoints.

No incluir historial, mensajes arbitrarios ni objetos de cliente Qdrant/LLM en el estado.

### Nodos y responsabilidades

- `receive_question`: valida y normaliza la pregunta sin recuperarla. Una pregunta vacia o compuesta solo por espacios deja un error de entrada claro.
- `retrieve_context`: invoca unicamente `data_project.pipelines.rag.retrieve(question)`, guarda los chunks obtenidos en `context` y no genera respuesta.
- `generate_response`: invoca unicamente `data_project.pipelines.rag.generate_answer(question, context)` cuando existe contexto aceptado.
- `answer_without_context`: genera una abstencion explicita y honesta sin llamar al LLM cuando la recuperacion no encuentra contexto util.

Los nodos deben tener una sola responsabilidad y devolver actualizaciones explicitas del estado.

### Rutas

Definir las siguientes transiciones condicionales:

1. `START -> receive_question`.
2. Desde `receive_question`: pregunta valida -> `retrieve_context`; entrada vacia -> `END` con `error` claro.
3. Desde `retrieve_context`: contexto no vacio -> `generate_response`; contexto vacio -> `answer_without_context`.
4. `generate_response -> END` y `answer_without_context -> END`.

Las decisiones de ruta deben estar implementadas como funciones condicionales verificables. No codificar los nodos como una secuencia fija. La recuperacion existente aplica su umbral configurado; el agente no debe rebajar ese umbral ni fabricar contexto.

### Compilacion y ejecucion

- Construir y compilar explicitamente el grafo al inicializar el modulo o la aplicacion, antes de aceptar invocaciones. Un fallo estructural debe impedir el arranque con un error accionable.
- Ejecutar el grafo compilado mediante `invoke`/`ainvoke` pasando un `run_id` unico y un `thread_id` de checkpoint. No compilar un grafo nuevo por cada request.
- Fallos en un nodo deben marcar la ejecucion como fallida, conservar una traza segura y producir un error HTTP controlado. No convertir fallos de infraestructura en una respuesta RAG aparentemente valida.

## Checkpointing y trazabilidad

### Checkpointing

- Usar un checkpointer durable de LangGraph respaldado por SQLite (incluida la dependencia compatible necesaria), no un saver solo en memoria.
- Persistir checkpoints en las transiciones de estado de la ejecucion. Cada request usa un `thread_id` aislado asociado a su `run_id`, para permitir inspeccion y reanudacion sin mezclar preguntas.
- Configurar la ubicacion de la base de datos por entorno y asegurar que el archivo sobreviva reinicios del proceso/contenedor mediante el volumen apropiado. No guardar la base dentro de un directorio temporal.
- Probar que una transicion queda persistida y que el estado puede recuperarse por `thread_id`.

### Trace consultable

- Cada ejecucion genera eventos estructurados y persistidos con `run_id`, secuencia, nombre del nodo, estado (`started`, `completed` o `failed`), timestamps y salida serializable del nodo.
- Las salidas deben permitir verificar orden y decisiones: resultado de validacion, referencias de chunks recuperados (fuente/seccion e identificador disponible), resultado de generacion o motivo de abstencion. No registrar credenciales, stack traces, headers ni respuestas crudas del proveedor.
- Persistir las trazas en un almacen local durable consultable despues de terminar el request. Se puede compartir SQLite con el checkpointer usando tablas separadas; no depender de `print` ni de logs efimeros como unica evidencia.
- Proteger la lectura de trazas con la autenticacion existente. No devolver automaticamente chunks internos en la respuesta normal del endpoint.

## API

Agregar `POST /agent/query` en el router del agente y registrarlo en `server.py` siguiendo los patrones de FastAPI del repositorio.

Request:

```json
{ "question": "¿Cual es la tarifa de seleccion?" }
```

Respuesta exitosa:

```json
{ "answer": "...", "run_id": "..." }
```

- El endpoint valida el esquema, invoca el grafo compilado y traduce el resultado; no contiene recuperacion, generacion ni decisiones de negocio duplicadas.
- Permitir que una pregunta vacia llegue al nodo de validacion del grafo para que la ruta de error se pueda trazar. Responder con un 422 controlado y sin stack trace.
- Los errores inesperados responden con mensaje generico y `run_id` para investigacion; no incluir mensajes internos de proveedor, secretos ni stack trace.
- Agregar una ruta autenticada de solo lectura para consultar la traza por `run_id` (por ejemplo `GET /agent/traces/{run_id}`). La respuesta incluye eventos serializados y no revela checkpoints de otras ejecuciones.
- Mantener `POST /knowledge/query` intacto y disponible.

## Evaluaciones offline

Crear evaluaciones en `tests/pipelines/` ejecutables con un solo comando, por ejemplo:

```bash
python -m pytest tests/pipelines/test_support_agent.py -q
```

Las evaluaciones deben leer artefactos de traza/respuesta persistidos y no ejecutar el grafo en vivo. Mantener los fixtures estables, sanitizados y versionados junto a las pruebas; una prueba unitaria independiente puede usar mocks para verificar que la generacion no se invoca si no hay contexto.

Incluir al menos estos criterios verificables:

1. Pregunta valida con contexto: orden `receive_question -> retrieve_context -> generate_response`, recuperacion anterior a generacion y respuesta no vacia.
2. Entrada vacia: se registra el error de validacion, termina sin ejecutar `retrieve_context` ni `generate_response` y la API representa el error como 422 controlado.
3. Sin resultados sobre el umbral: la traza muestra recuperacion vacia y ejecucion de `answer_without_context`; la respuesta expresa que la base no tiene informacion suficiente.
4. Anclaje en la base de conocimiento: una pregunta sobre una politica comercial conocida debe producir el dato esperado en la respuesta y citar la fuente/seccion correspondiente. Como minimo, cubrir la tarifa del 22% o la garantia contractual de reemplazo de 6 meses, segun el documento existente de pricing/SLA. No aceptar una traza correcta si el contenido de la respuesta contradice la fuente.

Las evaluaciones pueden compartir fixture siempre que haya al menos tres casos diferenciados. No sustituir ni debilitar `tests/pipelines/test_rag.py` ni las pruebas RAG existentes.

## Pruebas y validacion

- Pruebas unitarias de cada ruta condicional con nodos RAG simulados; comprobar llamadas exactas a `retrieve` y `generate_answer` y que no se llama `query`.
- Pruebas de compilacion del grafo y deteccion de rutas/nodos desconectados o sin salida.
- Prueba de checkpoint persistido y recuperable.
- Pruebas de persistencia/consulta del trace, orden de eventos y serializacion segura.
- Pruebas del endpoint: autenticacion, pregunta vacia, respuesta exitosa, acceso a trace, ejecucion fallida y ausencia de detalles internos.
- Ejecutar las nuevas evaluaciones offline junto con `tests/pipelines/test_rag.py` y `tests/pipelines/test_pipeline.py` para proteger el RAG y el flow Prefect existente.
- No requerir Qdrant ni credenciales LLM para las pruebas unitarias y evaluaciones offline.

## Dependencias y configuracion

- Declarar LangGraph y su checkpointer SQLite en los manifiestos de dependencias usados por el entorno local y Docker.
- Documentar la ruta configurable de checkpoints/trazas y asegurar permisos de escritura y persistencia en Compose.
- No introducir credenciales nuevas ni almacenar secretos en el repositorio, fixtures, checkpoints de prueba o trazas.

## Criterios de aceptacion

- El estado es minimo, explicito, tipado y no contiene el historial completo.
- Existen nodos independientes para recibir/validar, recuperar, generar y abstenerse cuando no haya contexto.
- Las rutas condicionales impiden recuperar una pregunta vacia y generar con contexto vacio.
- Los nodos llaman `retrieve` y `generate_answer` por separado; ninguno invoca `query()`.
- El grafo se compila antes de ejecutarse y el error estructural es claro.
- Hay checkpoint durable verificable y trazas persistidas consultables por ejecucion.
- `POST /agent/query` invoca el grafo; el endpoint de conocimiento existente sigue funcionando sin cambios.
- Hay al menos tres evaluaciones offline en `tests/pipelines/`, incluida una prueba de anclaje a una politica real del corpus.
- Las pruebas RAG y Prefect existentes siguen pasando; las fallas del agente no exponen stack traces ni secretos.
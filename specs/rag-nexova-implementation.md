# Especificación de implementación: RAG comercial de Nexova

## Objetivo

Construir un asistente de consulta para SDRs y account managers que responda preguntas comerciales usando exclusivamente la base de conocimiento de Nexova. El trabajo se ejecutará fase por fase; cada fase tiene un resultado verificable y no se avanzará a la siguiente si su criterio de salida no se cumple.

## Fuentes de verdad

- Requisitos funcionales: [`RAG-context.md`](../RAG-context.md).
- Reglas de negocio, nombre de colección y esquema de metadatos: [`CONTEXT-company.md`](../CONTEXT-company.md).
- Documentos indexables existentes:
  - `docs/company-knowledge-base/nexova-service-lines.es.md`
  - `docs/company-knowledge-base/nexova-pricing-model.es.md`
  - `docs/company-knowledge-base/nexova-hiring-process-sla.es.md`
  - `docs/company-knowledge-base/nexova-objection-handling.es.md`

Los cuatro documentos locales son la fuente de verdad que indexa el sistema.

## Reglas globales

- La colección Qdrant se llama exactamente `nexova_knowledge`.
- Los payloads incluyen `company`, `source_document`, `section`, `language`, `chunk_index` y `text`; usar `company="nexova"` y `language="es"`. Los valores de `source_document` son `service-lines`, `pricing-model`, `hiring-process-sla` y `objection-handling`.
- `embed(text)` es la misma función al indexar y al recuperar. Usa el modelo de embeddings indicado por `EMBED_MODEL`; el modelo de generación es independiente y debe tener un ID distinto. Priorizar para generación el modelo gratuito de 4Geeks para estudiantes si está disponible.
- No almacenar credenciales en el repositorio, logs, pruebas ni respuestas. La configuración debe poder operar tanto desde el host como desde Docker.
- Mantener intacto el pipeline Prefect semanal existente. El endpoint no implementa lógica RAG propia: delega en `data/pipelines/`.
- La API responde únicamente `{ "answer": "..." }`. La respuesta de texto debe nombrar documento y sección como trazabilidad breve; no enviar payloads, chunks ni scores como campos de la respuesta.
- Toda respuesta debe ser fiel a los chunks recuperados. Nunca ofrecer un descuento sobre la tarifa del 22%; excepciones y descuentos requieren aprobación humana. Los tiempos son promedios, excepto la garantía contractual de reemplazo de 6 meses. Mantener la transparencia indicada en el documento de objeciones al hablar de clientes de la competencia.
- Cuando no haya evidencia relevante por encima de `min_score`, decir explícitamente que la base no contiene información suficiente y no completar con conocimiento general.
- Para nuevos archivos, respetar el estilo del proyecto. La autorización para modificar `data/` y `docs/` queda confirmada por el usuario en esta tarea.

## Fase 0: configuración y contrato técnico

### Objetivo

Resolver dependencias y configuración antes de acoplar los módulos a un proveedor o asumir parámetros de Qdrant.

### Trabajo

- Inspeccionar el entorno existente: `qdrant-client` y `fastembed` fueron instalados localmente (`qdrant-client>=1.16.2`, `fastembed>=0.8.0`). Confirmar importación y compatibilidad; añadir las dependencias al manifiesto apropiado (`pyproject.toml` y/o `services/requirements.txt`) para que instalación y Docker sean reproducibles.
- Confirmar modelo concreto configurado en `EMBED_MODEL`, dónde se ejecuta y su dimensión. FastEmbed es una opción local de embeddings, no asumir que equivale a un modelo alojado por 4Geeks.
- Confirmar endpoint, ID y credencial del modelo generativo gratuito de 4Geeks. Mantenerlo separado del proveedor/modelo de embeddings.
- Definir configuración documentada para modelos, credenciales, URL de Qdrant, dimensión, métrica y `min_score`; proporcionar valores de ejemplo no secretos donde corresponda.
- Identificar la dirección de Qdrant desde host y desde Compose. Verificar cómo el servicio backend y el indexador accederán a `docs/company-knowledge-base/`; si indexa dentro del contenedor, montar los documentos de solo lectura o construir una alternativa reproducible.
- Elegir métrica adecuada al modelo de embeddings (por ejemplo, cosine solo si el contrato del modelo lo respalda) y un umbral inicial. El valor definitivo se calibrará en la fase de evaluación.

### Criterio de salida

La instalación declarada permite importar los clientes en un entorno limpio; existen nombres, ubicaciones y valores de configuración documentados sin secretos; se conoce la dimensión del vector y se puede alcanzar Qdrant desde el proceso que indexará/consultará.

## Fase 1: chunking e indexación

### Objetivo

Implementar `embed(text: str) -> list[float]` y `setup()` bajo `data/process/` para cargar los cuatro documentos completos en Qdrant.

### Trabajo

- Leer el corpus desde `docs/company-knowledge-base/`; no codificar una copia alternativa de su contenido.
- Fragmentar primero por encabezados y secciones semánticas. Mantener juntas listas, condiciones, excepciones y reglas comerciales. Aplicar límites de tamaño como recurso secundario y no cortar frases o reglas a mitad.
- Cada documento debe producir al menos 3 chunks. Registrar el conteo real por fuente para la documentación.
- Implementar `embed()` con `EMBED_MODEL` y compartir esa misma ruta en indexación y búsqueda. Validar vector no vacío, dimensión consistente y errores del proveedor.
- Crear la colección `nexova_knowledge` con dimensión y métrica resueltas en fase 0.
- Incluir en cada punto todos los metadatos requeridos y un texto suficiente para usarlo como contexto de generación.
- Hacer `setup()` idempotente con IDs deterministas basados en fuente/sección/índice y contenido normalizado. Reejecutar actualiza puntos existentes, sin duplicar; evitar borrar la colección completa silenciosamente.
- Fallar con un mensaje accionable si existe una colección incompatible con el modelo/dimensión, en vez de intentar insertar vectores incorrectos.

### Criterio de salida

Una ejecución indexa los cuatro documentos y todos sus chunks tienen metadatos completos. Dos ejecuciones consecutivas conservan el mismo número de puntos e IDs. Una inspección de muestras confirma que los chunks preservan sus reglas y secciones de origen.

## Fase 2: recuperación y generación

### Objetivo

Implementar el pipeline de consulta en un módulo RAG nuevo de `data/pipelines/`, sin alterar el flow Prefect existente.

### Contrato

- `retrieve(query: str, *, k: int = 5, min_score: float) -> list[dict]`
- `generate_answer(question: str, context: list[dict]) -> str`
- `query(question: str) -> str`

### Trabajo

- `retrieve()` usa `embed()` para vectorizar la consulta, consulta Qdrant por similitud, limita a `k`, descarta todo resultado bajo `min_score` y retorna payloads Python, no objetos SDK ni scores.
- `generate_answer()` construye el prompt y llama al modelo generativo configurado. Instruye al modelo a responder en español con voz segura, comercial y orientada a cerrar, para un SDR que conversa con prospectos, usando solo los chunks recibidos.
- Instruir al modelo para que cite brevemente `source_document` y `section`, no invente datos, diferencie promedios de garantías y remita descuentos/excepciones a una persona autorizada.
- Con contexto vacío, no llamar al modelo con una instrucción que invite a completar vacíos: devolver una abstención explícita y honesta.
- `query()` compone solamente recuperación y generación. La separación permite que un futuro agente reutilice ambos pasos sin recuperar dos veces.
- Configurar timeout y manejo de errores de los clientes sin exponer credenciales, textos internos de excepción ni resultados crudos.

### Criterio de salida

Una consulta devuelve contexto con payloads válidos y sin score expuesto; los resultados inferiores al umbral se descartan y pueden quedar menos de `k`. `query()` devuelve texto generado o abstención, y nunca texto crudo de chunks como respuesta.

## Fase 3: endpoint FastAPI

### Objetivo

Exponer `POST /knowledge/query` y dejar el pipeline como única implementación de recuperación y generación.

### Trabajo

- Crear router en `services/api/knowledge/` y modelos Pydantic para request y response.
- Request: `{ "question": "..." }`. Response: `{ "answer": "..." }`.
- Registrar el router en `server.py` conforme a los patrones actuales de la API.
- Proteger la ruta con el patrón de autenticación existente y aplicar validación de entrada: pregunta no vacía y tamaño máximo razonable.
- El handler llama a `query()` y no importa ni usa Qdrant o el SDK generativo directamente.
- Traducir fallos externos a respuestas HTTP controladas, sin filtrar stack traces, chunks, scores ni secretos.

### Criterio de salida

Pruebas de API confirman autenticación, validación, respuesta `{answer}` y errores controlados. Ninguna respuesta expone datos de recuperación. El endpoint opera con el pipeline, no con una copia de su lógica.

## Fase 4: interfaz del backoffice

### Objetivo

Permitir al usuario hacer una pregunta y leer la respuesta del endpoint.

### Trabajo

- Añadir la página `/knowledge` en el backoffice y un acceso desde la navegación existente.
- Reutilizar el patrón de `/reporting` para URL del backend, autenticación y manejo de errores.
- Incluir campo de pregunta, acción para enviar, estado de carga, estado de error y presentación de respuesta. Evitar que un fallo de red parezca una respuesta vacía.
- Mantener el sistema visual existente y sus modos claro/oscuro si están disponibles; no añadir otra librería de UI para este alcance.

### Criterio de salida

Una persona autenticada puede enviar una pregunta y ver la respuesta; carga y error son distinguibles; el flujo funciona en tamaños de pantalla usados por el backoffice.

## Fase 5: pruebas unitarias y de contrato

### Objetivo

Asegurar el comportamiento sin Qdrant ni proveedor generativo en vivo.

### Trabajo

- Crear `tests/pipelines/test_rag.py` siguiendo los patrones existentes.
- Stub/mock de Qdrant: comprobar filtrado por `min_score`, que puede devolver menos de `k`, forma de payloads y errores relevantes.
- Mock de `retrieve()` y del generador: comprobar que `query()` devuelve salida del generador, compone las funciones una sola vez y no devuelve chunks directamente.
- Comprobar abstención sin contexto, prompt en español con voz/audiencia Nexova, citas y restricciones comerciales.
- Añadir pruebas del router para request inválido, autenticación, respuesta mínima y ausencia de payloads/scores.

### Criterio de salida

`python -m pytest tests/pipelines/test_rag.py` pasa sin conectividad a Qdrant o al LLM; pruebas de API focalizadas pasan; `tests/pipelines/test_pipeline.py` sigue pasando.

## Fase 6: evaluación de retrieval

### Objetivo

Medir de forma repetible el KPI Recall@3 definido por el contexto Nexova.

### Trabajo

- Crear `data/eval/test-queries.json` con al menos 8 preguntas, que cubran los cuatro documentos e incluyan al menos dos objeciones comerciales extraídas de `nexova-objection-handling.es.md`.
- Cada caso identifica pregunta, documento relevante y chunk o sección esperada; mantener etiquetas reproducibles y específicas.
- Crear o documentar una ejecución de evaluación que llame a `retrieve()` y calcule Recall@3 conforme al criterio de relevancia anotado.
- Ajustar el umbral con resultados observables; registrar dataset, métrica, umbral utilizado y resultado. No presentar como medido un resultado no ejecutado.
- Revisar respuestas representativas para fidelidad de tarifas, promedios, garantía y competencia, además de Recall@3.

### Criterio de salida

Dataset con ≥8 preguntas y cobertura de todas las fuentes; Recall@3 medido y ≥80%. Si no se alcanza, revisar chunking/embeddings antes de avanzar y volver a medir.

## Fase 7: documentación y cierre

### Objetivo

Dejar el diseño utilizable y mantener una huella verificable del resultado real.

### Trabajo

- Crear `docs/rag/rag-design.md` con flujo de extremo a extremo: documentos → chunking → `setup()`/Qdrant → `retrieve()` → prompt → modelo de generación → respuesta/API.
- Explicar por qué el chunking elegido encaja con estos documentos, cómo preserva reglas y condiciones, y cuántos chunks produjo cada fuente.
- Registrar IDs exactos de embedding y generación, proveedor cuando aplique, dimensión, métrica, umbral y cómo se calibró; aclarar cualquier normalización/preprocesado.
- Documentar instalación, variables necesarias, indexación, acceso a Qdrant en Docker, pruebas y evaluación.
- Registrar solo resultados efectivamente observados. Revisar el diff y confirmar que no se incluyeron secretos o cambios fuera del alcance.

### Criterio de salida

Un desarrollador puede configurar, indexar, ejecutar, probar y evaluar el pipeline leyendo la documentación; se cumplen los KPIs o se deja explícito cualquier bloqueo medible.

## Orden sugerido de ejecución

Completar y revisar una fase por iteración: fase 0 → fase 1 → fase 2 → fase 3 → fase 4 → fase 5 → fase 6 → fase 7. Las pruebas unitarias de cada módulo se ejecutan en su propia fase; la fase 5 consolida el contrato completo. No avanzar si no se cumple el criterio de salida de la fase actual.

## Referencias de implementación existentes

- Indexación y eval: `data/process/`, `data/eval/`.
- Pipeline Prefect que debe permanecer independiente: `data/pipelines/pipeline.py` y `tests/pipelines/test_pipeline.py`.
- API/auth: `services/api/`, `services/reporting/routes.py`, `services/api/users/auth.py`, `server.py`.
- Compose/Qdrant: `docker-compose.yml`.
- UI: `uis/backoffice/app/reporting/page.tsx`, `uis/backoffice/components/NavBar.tsx`.
- Validación del backoffice: ejecutar lint/build desde `uis/backoffice` según scripts disponibles.

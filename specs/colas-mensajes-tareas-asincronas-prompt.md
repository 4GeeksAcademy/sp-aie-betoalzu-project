# Tarea: colas de mensajes y tareas asíncronas con Celery

Implementa en este monorepo los requisitos de colas, workers y observabilidad descritos en esta especificación. Antes de cambiar código, inspecciona las convenciones reales de FastAPI, configuración, persistencia, Docker, autenticación, pruebas y logging. Reutiliza las abstracciones existentes y limita los cambios a esta funcionalidad.

## Objetivo y flujo candidato

La operación pesada candidata es el análisis CSV de `POST /api/incidents/analyze`: actualmente la ruta lee y analiza el archivo durante la petición, y conserva el resultado en `_last_analysis`, una variable local al proceso. Confirma que sigue siendo el flujo apropiado antes de implementarlo; si el código ha cambiado, identifica y justifica el endpoint costoso equivalente.

La API debe aceptar el CSV, guardar su contenido en almacenamiento duradero accesible tanto por la API como por el worker, encolar únicamente una referencia y responder `202 Accepted` con `{"task_id": "..."}`. El worker carga esa referencia y ejecuta el análisis fuera del proceso de FastAPI. Conserva el comportamiento de exportación de resultados, adaptándolo para recuperar el resultado por `task_id` y no desde memoria local de un proceso.

## Inspección y límites

- Inspecciona el endpoint candidato, `analyze_csv_stream`, la ruta de exportación, autenticación, inicialización de base de datos, `docker-compose.yml`, `services/Dockerfile`, dependencias y pruebas vecinas antes de definir los cambios.
- Conserva validaciones existentes del archivo y contratos no afectados. No cargues ni analices el CSV completo en la ruta si puede procesarse por streaming; mide el tiempo de respuesta de encolado separándolo del tiempo que el cliente tarda en enviar el archivo.
- El broker nunca debe recibir el contenido del archivo ni otro payload voluminoso: pasa solo IDs, nombres de objeto o referencias equivalentes. La referencia debe seguir siendo accesible si se reinicia la API y desde el contenedor del worker; configura almacenamiento persistente/compartido y permisos adecuados.
- No almacenes resultados exclusivamente en variables globales ni en memoria del proceso API. El estado/resultados consultables deben persistir a través del backend de resultados de Celery según su configuración.
- No cambies rutas protegidas por `AGENTS.md` (incluidos `data/`, `docs/`, `README.md` y `README.es.md`) sin autorización explícita. La documentación solicitada del worker requiere actualizar el README raíz: antes de editarlo, pide esa autorización y pausa ese cambio si no se concede. No crees un commit.

## Infraestructura y configuración

- Añade Redis con imagen oficial a `docker-compose.yml`, publicado en el puerto `6379` y configurado con política de memoria `noeviction`.
- Añade Flower, accesible en el puerto `5555`, configurado para observar el mismo broker. No lo dejes expuesto con credenciales predeterminadas o sin controles de acceso apropiados para el entorno.
- Configura API, worker y Flower para usar `REDIS_URL` desde el entorno; la instancia Celery usa esa URL tanto como broker como backend de resultados. Proporciona valores locales coherentes en la configuración existente sin guardar secretos.
- Añade un servicio `worker` independiente del proceso FastAPI, con dependencias, red y almacenamiento compartido necesarios. La API y el worker deben poder detenerse y arrancarse independientemente; Redis conserva los mensajes pendientes según su configuración.
- Actualiza las dependencias Python de los archivos que realmente instalan el backend y comprueba que Docker instala Celery y su cliente Redis.

## Tarea Celery, reintentos y DLQ

- Crea una instancia Celery en `services/` con Redis como broker y result backend, y registra al menos una tarea para ejecutar el análisis seleccionado.
- Encola solo la referencia al archivo y metadatos pequeños estrictamente necesarios. Devuelve como resultado serializable el resumen de análisis existente; no serialices objetos internos innecesarios.
- Configura reintentos automáticos para errores transitorios con `max_retries=3` y backoff exponencial con demora creciente y distinta de cero. No reintentes errores de validación permanentes como si fueran fallos transitorios. Documenta qué excepciones se reintentan.
- Al agotarse los reintentos, registra una entrada persistente de Dead Letter Queue en la base de datos existente. Debe incluir `task_id`, número de intento, mensaje completo del error y timestamp UTC. La escritura debe ser idempotente por tarea y no ocultar el error original si falla el registro: informa ambos fallos claramente.
- Usa el conteo de reintentos de Celery de forma consistente: con `max_retries=3`, distingue los tres reintentos de la ejecución inicial y deja documentado qué número se persiste en el fallo terminal.
- Asegura que los archivos temporales o subidos se limpien en éxito y fallo sin eliminar un archivo antes de que el worker lo procese. No registres contenido CSV ni datos sensibles.

## API

- Cambia el endpoint de análisis para encolar el trabajo y responder de inmediato con HTTP `202` y `{"task_id": "..."}`. Mantén la autenticación y validación de entrada existentes.
- Añade `GET /tasks/{task_id}`. Consulta el estado/resultados reales de Celery y responde con `{"task_id": "...", "status": "...", "result": ...}`. Los estados expuestos deben ser `pending`, `started`, `success` o `failure`; define una traducción coherente para estados internos transitorios/desconocidos sin exponer estados inventados. `result` debe ser nulo mientras no haya resultado, el resumen cuando termine correctamente y un error seguro/conciso al fallar.
- Evita que usuarios no autorizados consulten resultados de otras personas; conserva la política de autenticación del endpoint original y añade propiedad/autorización de tarea si la aplicación la requiere.
- Adapta la exportación de resultados para que use el `task_id` terminado con éxito, en lugar de `_last_analysis`. Devuelve errores HTTP claros para tareas inexistentes, pendientes o fallidas.
- Gestiona errores de Redis/encolado: no respondas con `202` si el mensaje no se pudo publicar y no dejes archivos huérfanos cuando sea posible limpiarlos con seguridad.

## Observabilidad

- Registra para cada tarea `task_id`, número de intento, estado final y duración de ejecución. En fallos registra también el mensaje completo del error.
- Incluye el ID de tarea en logs de encolado, reintento, inicio, éxito y fallo. Usa timestamps y no registres el payload ni el contenido del archivo.
- Configura Flower para mostrar tareas encoladas, activas, completadas y fallidas; valida su conectividad con el broker compartido.

## Worker y documentación

- El worker debe arrancarse como proceso/servicio separado de Uvicorn y sobrevivir a la detención de la API mientras Redis siga disponible.
- Documenta en el README del monorepo los comandos para levantar y detener Redis, API, worker y Flower, las variables requeridas y la URL de Flower. Respeta la restricción de autorización indicada arriba para los README protegidos; si no se autoriza su edición, deja ese punto sin modificar y repórtalo como bloqueante de documentación.

## Verificación y criterios de aceptación

Usa pruebas focalizadas y las convenciones existentes. Verifica, al menos:

- Redis arranca con `noeviction`, y API/worker/Flower apuntan al mismo `REDIS_URL`.
- El worker corre en un proceso separado y puede consumir una tarea publicada por la API.
- El endpoint acepta un CSV válido, encola solo una referencia y devuelve `202` con `task_id`; mide que la respuesta de encolado sea menor de 200 ms después de recibir el cuerpo, excluyendo el tiempo de transferencia del cliente.
- `GET /tasks/{task_id}` refleja pendiente/iniciada, éxito y fallo, con `result` correspondiente.
- Se conserva el análisis correcto y la exportación del resultado asociado al `task_id` incluso si API y worker son procesos distintos.
- Un fallo transitorio no se reintenta inmediatamente, los retardos crecen, se realizan como máximo tres reintentos y el fallo terminal crea una entrada DLQ persistente con los cuatro datos requeridos.
- El broker no transporta contenido CSV; el worker puede abrir la referencia después de reiniciar la API.
- Los logs incluyen ID, intento, estado y duración, y el fallo incluye el mensaje completo.
- Flower muestra tareas exitosas y fallidas durante la validación. Si el entorno no permite demostrarlo end-to-end, deja pasos reproducibles y explica la limitación.

Ejecuta solo las pruebas, lint/typecheck y comprobaciones Docker pertinentes al área modificada. No intentes corregir fallos preexistentes ajenos a esta tarea; menciónalos por separado.

## Entrega

Resume los archivos modificados, el endpoint elegido, cómo se comparte el archivo sin ponerlo en Redis, la configuración y comandos del worker, la política de reintentos, el esquema/registro DLQ, los comandos y resultados de verificación y cualquier autorización/documentación pendiente. No crees un commit salvo solicitud explícita.
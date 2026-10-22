# Especificacion: servidor MCP con OAuth y herramientas de Nexova

## Objetivo

Implementar un servidor MCP Python bajo `mcps/` para que clientes autorizados consulten el inventario y gestionen incidencias de Nexova. El servidor debe adaptar las APIs existentes, proteger el descubrimiento y la ejecucion de herramientas con OAuth conforme a MCP mediante `mcpauth`, y sustituir las llamadas directas del agente LangGraph a esas fuentes.

Esta especificacion concreta sus contratos usando las APIs presentes en `services/api/incidents/`, `services/api/inventory/` y `services/agent/`.

## Alcance y restricciones

- El servidor MCP vive en `mcps/` y expone herramientas mediante el protocolo MCP estándar y el mecanismo estándar de descubrimiento.
- Se puede usar FastMCP como transporte/SDK, pero **no** su capa OAuth integrada. `mcpauth` debe actuar como resource server OAuth y validar los tokens de acceso.
- Publicar Protected Resource Metadata y validar firma, emisor, audiencia/recurso, expiración y scopes del token según el proveedor OAuth 2.1/OIDC configurado.
- Ninguna sesión anónima ni token inválido puede inicializar una sesión MCP, listar herramientas ni invocarlas. La metadata necesaria para iniciar OAuth puede permanecer accesible públicamente.
- El servidor solo puede llamar a los endpoints de backend enumerados en esta especificación. No aceptar URLs, métodos HTTP ni rutas arbitrarias como argumentos de herramientas.
- No exponer herramientas de escritura para inventario. Los intentos de escritura autenticados deben recibir una denegación explícita y estable del servidor.
- No registrar access tokens, secretos, descripciones de incidencias ni payloads completos que puedan contener datos personales.
- Mantener el esquema de dominio existente: IDs numéricos de incidencia/producto, nombres de campos y valores de enum descritos abajo.

## Contratos del backend existentes

### Incidents Manager

- Crear: `POST /api/incidents`, cuerpo basado en `IncidentCreate`.
- Consultar lista: `GET /api/incidents`, filtros admitidos `status`, `category`, `branch`, `origin`.
- Consultar detalle: `GET /api/incidents/{incident_id}`.
- Editar campos no relacionados con estado: `PUT /api/incidents/{incident_id}`, cuerpo parcial `IncidentUpdate`.
- Cambiar estado: **exclusivamente** `PATCH /api/incidents/{incident_id}/status`, cuerpo `{"status": "..."}`. No usar `PATCH /api/incidents/{id}` ni `PUT` para transiciones.
- Estados: `open`, `in_progress`, `resolved`, `discarded`. Transiciones válidas: `open -> in_progress|discarded`; `in_progress -> resolved|discarded`; `resolved` y `discarded` son terminales.
- Categorías: `technical_failure`, `process_error`, `client_complaint`, `candidate_issue`, `staff_issue`, `sla_breach`, `data_quality`, `other`.
- Orígenes: `customer`, `branch`, `internal`. Sedes: `central`, `valencia_operations`, `miami_office`, `remote`.
- Campos de creación: `title` (1-120 caracteres), `description`, `category`, `origin`, `branch` (por defecto `central`), `reported_by`, `assigned_to`, `ticket_id` (máximo 50). El servidor MCP debe omitir `status` al crear y dejar que el backend aplique `open` por defecto.
- Campos editables: `title`, `description`, `category`, `origin`, `branch`, `reported_by`, `assigned_to`, `ticket_id`. Rechazar `status` en la herramienta de edición; dirigir el cambio a la herramienta de transición.
- La API no admite filtro `ticket_id` en la lista; si se ofrece ese filtro MCP, recuperar la lista permitida y filtrar por igualdad exacta en el adaptador.
- Las rutas de incidencias requieren credenciales de servicio aceptadas por el backend (`get_current_user`). No reenviar automáticamente el token OAuth del cliente MCP: usar credenciales de servicio separadas y configuradas fuera del código, salvo que se implemente y valide explícitamente una federación compatible.

### Inventario

- Listar: `GET /inventory/products`.
- Consultar por ID: `GET /inventory/products/{product_id}`.
- Respuesta de producto (`AssetResponse`): `id`, `name`, `sku`, `category`, `office`, `currency`, `unit_cost`, `program`, `current_stock`.
- Categorías: `hardware`, `peripherals`, `office_supplies`, `training_materials`, `certification`, `onboarding_equipment`.
- Sedes: `Valencia`, `Miami`. Monedas: `USD`, `EUR`.
- No llamar a `POST`, `PUT` u otros endpoints de escritura del inventario desde el servidor MCP. La API REST actual no exige autenticación para las lecturas, por lo que el servidor MCP debe aplicar OAuth antes de permitirlas.

## Herramientas MCP

Cada herramienta debe publicar en el discovery de MCP un nombre estable, una descripción autosuficiente, parámetros tipados con descripciones/restricciones y una salida documentada. Los nombres siguientes son los nombres requeridos para esta implementación.

| Herramienta | Scope requerido | Entrada | Comportamiento y salida |
| --- | --- | --- | --- |
| `incidents_create` | `incidents:write` | Campos de creación indicados arriba, con enums descritos y sin campo `status`. | Crea con `POST /api/incidents`; devuelve el objeto de incidencia con `id`, `ticket_id`, estado, campos de dominio y fechas. |
| `incidents_get` | `incidents:read` | Opcional: `incident_id` entero positivo, `ticket_id`, `status`, `category`, `branch`, `origin`. Exigir `incident_id` o al menos un filtro; rechazar consulta sin límites. | Usa detalle por ID o lista con filtros permitidos. `ticket_id` se filtra por igualdad exacta en el adaptador. Devuelve `incidents` (lista, incluso para un único resultado) y `status` de consulta. |
| `incidents_update` | `incidents:write` | `incident_id` entero positivo y al menos un campo permitido de `IncidentUpdate`; `status` está prohibido. | Actualiza campos mediante `PUT /api/incidents/{incident_id}`; devuelve la incidencia actualizada. |
| `incidents_transition_status` | `incidents:write` | `incident_id` entero positivo y `status` enum. | Ejecuta solo `PATCH /api/incidents/{incident_id}/status`; devuelve la incidencia actualizada. El backend decide si la transición es válida. |
| `inventory_get_products` | `inventory:read` | Opcionales: `product_id` entero positivo y `search` no vacío. | Consulta por ID o lista `GET /inventory/products`; `search` filtra por coincidencia sin distinción de mayúsculas en `name` o `sku`. Devuelve productos con `current_stock`. No muta datos. |
| `inventory_write_attempt` | `inventory:read` | `operation` enum (`create_product`, `update_product`, `delete_product`, `create_inbound_order`, `create_outbound_order`) y `payload` objeto opcional. | Siempre rechaza la operación con código `INVENTORY_READ_ONLY`; nunca llama a la API ni modifica datos. La descripción debe advertir claramente esta conducta. |

Las herramientas de escritura de incidencias solo disponen del scope de escritura correspondiente; lectura y escritura deben poder concederse por separado. La herramienta de rechazo de escritura de inventario no necesita `inventory:write`, pues dicho scope no debe habilitarse en este servidor. Los clientes sin `inventory:read` reciben `403` antes de ejecutar herramientas de inventario.

## Autenticación y autorización

- Integrar `mcpauth` como resource server compatible con el transporte MCP utilizado. Definir el recurso protegido, issuer y configuración OIDC/JWKS mediante configuración externa; no fijar proveedor ni secretos en el código.
- Publicar Protected Resource Metadata para que clientes MCP compatibles puedan descubrir el issuer y el recurso protegido.
- Proteger inicialización, `tools/list` y `tools/call`. No basta con proteger solamente la ejecución.
- Scopes mínimos: `incidents:read`, `incidents:write`, `inventory:read`. Aplicar `required_scopes` de MCP Auth por herramienta y comprobar los scopes también en las rutas de ejecución.
- Token ausente, mal formado, expirado o de issuer/audience incorrectos: responder `401` con código/mensaje de autenticación distinguible. Token válido sin scope: `403` con código/mensaje de autorización distinguible.
- No aceptar credenciales en query string. Usar exclusivamente el mecanismo bearer admitido por MCP.
- El token OAuth entrante identifica al cliente MCP. La autenticación hacia el backend es independiente y usa la credencial de servicio configurada para el proceso; nunca incluirla en argumentos, resultados ni logs.

## Errores y resultados

Definir un formato estable para errores de herramientas y conservar un mensaje breve, seguro y accionable. Como mínimo, distinguir:

| Condición | Código HTTP/protocolo | Código de aplicación |
| --- | --- | --- |
| Sin token o token inválido | `401` / error de autenticación MCP | `AUTHENTICATION_REQUIRED` o `INVALID_ACCESS_TOKEN` |
| Token válido sin scope | `403` / error de autorización MCP | `INSUFFICIENT_SCOPE` |
| Argumentos inválidos o enum/campo no permitido | `400` o error de parámetros MCP (`-32602`, según el punto de validación) | `INVALID_INPUT` |
| ID inexistente | resultado de herramienta controlado; conservar el 404 del backend | `INCIDENT_NOT_FOUND` o `PRODUCT_NOT_FOUND` |
| Transición no válida | resultado de herramienta controlado; conservar el 400 del backend | `INVALID_STATUS_TRANSITION` |
| Intento de modificar inventario | resultado de herramienta controlado | `INVENTORY_READ_ONLY` |
| Timeout del backend | resultado de herramienta controlado | `UPSTREAM_TIMEOUT` |
| Error HTTP del backend | resultado de herramienta controlado | `UPSTREAM_ERROR` |
| JSON/modelo inesperado del backend | resultado de herramienta controlado | `INVALID_UPSTREAM_RESPONSE` |

No convertir fallos de autenticación, autorización, validación o negocio en un `error` genérico. No devolver trazas, tokens ni respuestas internas sensibles del backend. Validar las entradas localmente antes de realizar llamadas externas y validar las respuestas contra los modelos existentes.

## Acceso al backend y configuración

- Reutilizar el backend configurado para el agente mediante `SUPPORT_AGENT_BACKEND_URL` y la credencial de servicio `SUPPORT_AGENT_SERVICE_TOKEN`, o documentar una migración coherente de esos nombres. La URL debe validarse como HTTP(S), sin userinfo/query/fragment; desactivar redirecciones y establecer timeout finito.
- Mantener llamadas HTTP con rutas y métodos allowlisted, esquemas Pydantic existentes y manejo explícito de 404, 400/409, 5xx, timeout y JSON inválido.
- Configurar OAuth (issuer, audiencia/recurso y scopes) por variables de entorno o configuración equivalente. Añadir ejemplos con valores ficticios, nunca secretos reales.
- Añadir dependencias MCP Auth y `langchain-mcp-adapters` en el manifiesto de dependencias Python correspondiente y sincronizar lockfiles solo si existen/son gestionados por el proyecto.
- Proporcionar un punto de entrada documentado para desarrollo y una comprobación de readiness que no publique herramientas ni datos sin autenticación.

## Trazabilidad

Registrar cada invocación, incluidos los rechazos, en un log estructurado con al menos `tool_name`, identidad de cliente validada (`client_id` o `sub`), resultado (`success`/`error`/`denied`), `error_code` cuando aplique y un identificador de petición. No registrar el bearer token ni el payload íntegro. Los errores de autenticación deben poder auditarse sin confiar en claims de tokens no validados.

## Migración del agente LangGraph

- Cargar herramientas MCP con `langchain-mcp-adapters` desde el servidor protegido, usando la configuración OAuth del cliente y una URL MCP configurable; no importar ni llamar a `query_incidents`/`query_inventory` como ruta de producción.
- Reemplazar los nodos de consulta directa `consult_incidents` y `consult_inventory` por clientes/nodos que invocan las herramientas MCP correspondientes. Mantener los nombres y estructura del estado LangGraph, la composición de respuestas, la telemetría/trazas y el comportamiento de errores/not-found para no alterar el enrutamiento.
- Mantener la ruta RAG independiente. Las preguntas que combinen RAG con una fuente de negocio deben seguir consultando cada fuente seleccionada y componiendo una respuesta con procedencia, sin atribuir al RAG estados actuales de tickets o existencias.
- Retirar el camino directo a Incidents Manager del grafo. Las funciones legacy pueden eliminarse o quedar explícitamente deprecadas, pero no deben ser usadas como fallback silencioso si MCP no está disponible.
- Un fallo de conexión/autenticación MCP debe producir el resultado de fuente fallida previsto por el agente, sin degradar a llamadas directas ni ocultar el fallo.

## Pruebas requeridas

### Servidor y contratos

- Pruebas unitarias de schemas: campos requeridos, límites, enums válidos, campos extra, `status` prohibido al editar y filtro vacío rechazado.
- Pruebas de cliente backend con HTTP simulado: métodos/rutas exactos, especialmente `PATCH /api/incidents/{id}/status`; respuestas válidas e inválidas; 404, 400/409, 5xx, timeout y errores de transporte.
- Verificar que la transición usa el endpoint dedicado y que ningún intento de escritura de inventario realiza una petición HTTP.
- Verificar discovery MCP: nombres, descripciones, parámetros, enums, salidas y scopes expuestos para todas las herramientas.
- Verificar que cliente sin token no puede inicializar/listar/invocar; token inválido/expirado devuelve autenticación; token válido sin scope devuelve autorización; scopes correctos permiten únicamente las herramientas autorizadas.
- Verificar logs por invocación exitosa, fallida y denegada, y comprobar que no contienen tokens ni payloads sensibles.

### Agente

- Actualizar pruebas de enrutamiento para preservar las rutas incidents, inventory y RAG, incluidas preguntas mixtas.
- Probar que el agente llama a las herramientas cargadas por el adaptador MCP, conserva el formato de respuesta y no invoca las funciones directas ni ante fallo MCP.
- Ejecutar la suite focalizada del agente y las pruebas MCP; ejecutar typecheck/lint de los módulos tocados si están disponibles.

### Validación manual en MCP Playground

- Arrancar el servidor en Codespaces y reenviar su puerto con visibilidad pública. Usar la URL reenviada de Codespaces en [MCP Playground](https://www.mcpplayground.tech/playground), no `localhost`.
- Conectar con OAuth y demostrar un flujo completo por herramienta: crear, consultar, editar y cambiar estado de una incidencia; consultar inventario; intentar una escritura de inventario y comprobar el rechazo `INVENTORY_READ_ONLY`.
- Probar también sin token y con scope insuficiente. Documentar URL pública usada (sin secretos), configuración no sensible, pasos, resultados observados y cualquier limitación en el entregable de implementación.
- No afirmar que Playground fue ejecutado hasta conservar evidencia real de las pruebas.

## Criterios de aceptación

1. El servidor se ejecuta desde `mcps/` y el discovery MCP describe las seis herramientas especificadas.
2. Sin access token válido no se puede inicializar una sesión MCP, listar ni ejecutar herramientas; los scopes separan lectura y escritura.
3. Las herramientas de incidencias crean, leen y editan usando el modelo existente; las transiciones usan exclusivamente `PATCH /api/incidents/{id}/status`.
4. Las consultas de inventario usan exclusivamente GET y devuelven los campos y enums reales, incluido `current_stock`.
5. `inventory_write_attempt` rechaza todos los intentos con `INVENTORY_READ_ONLY` y no produce efectos laterales.
6. Errores de autenticación, autorización, validación, transición, not-found y upstream son distinguibles y documentados.
7. Cada invocación queda registrada con herramienta, cliente validado y resultado, sin secretos ni payloads sensibles.
8. LangGraph utiliza MCP para las herramientas de incidencias e inventario; no queda una ruta directa ni fallback a los servicios del backend.
9. El enrutamiento RAG y las respuestas mixtas mantienen su comportamiento anterior.
10. Se pasan las pruebas automatizadas focalizadas y se documentan los flujos efectivamente probados en MCP Playground mediante URL pública reenviada de Codespaces.

## Fuera de alcance

- Cambiar los contratos REST existentes de incidencias o inventario para adaptarlos al MCP.
- Exponer operaciones de escritura de inventario.
- Cambiar el proveedor OAuth/OIDC de la organización o almacenar secretos en el repositorio.
- Reescribir el enrutador de negocio o la estrategia RAG del agente más allá de sustituir el acceso directo por herramientas MCP.
# Servidor MCP de Nexova

El servidor publica herramientas MCP sobre Streamable HTTP y valida los access tokens OAuth/OIDC con `mcpauth`. El backend REST se usa solo como adaptador; no acepta rutas, métodos ni URLs desde los argumentos de las herramientas.

## Desarrollo

Instala las dependencias Python del proyecto y configura el entorno antes de iniciar:

```bash
export SUPPORT_AGENT_BACKEND_URL=http://127.0.0.1:8000
export SUPPORT_AGENT_SERVICE_TOKEN=<token-de-servicio-del-backend>
export MCP_AUTH_ISSUER=https://auth.example.test/
export MCP_AUTH_TYPE=oidc
export MCP_RESOURCE_URI=https://mcp.example.test/mcp
export MCP_SERVER_HOST=0.0.0.0
export MCP_SERVER_PORT=8001
python -m mcps.server
```

Los valores de ejemplo no son credenciales reales. `MCP_AUTH_ISSUER` debe publicar discovery OIDC u OAuth compatible y un JWKS para validar tokens JWT. `MCP_RESOURCE_URI` debe coincidir con la audiencia emitida para este servidor. Registra los scopes en el proveedor OAuth y asígnalos a los clientes:

- `incidents:read`
- `incidents:write`
- `inventory:read`

El endpoint MCP es `http://localhost:8001/mcp` en desarrollo. La metadata protegida queda publicada en `/.well-known/oauth-protected-resource/mcp`; `/health/ready` solo comunica readiness y no revela tools ni datos. Todo el endpoint MCP, incluida inicialización y listado de tools, exige un bearer token en `Authorization`. No se aceptan credenciales en query string.

Las incidencias y el inventario usan `SUPPORT_AGENT_SERVICE_TOKEN` como credencial de servicio independiente del token OAuth del cliente MCP. Debe pertenecer a un usuario operativo `admin` o `manager`; un usuario normal no puede consultar incidencias. Las llamadas REST están restringidas a:

- `GET /api/incidents` y `GET /api/incidents/{id}`.
- `POST /api/incidents`.
- `PUT /api/incidents/{id}`.
- `PATCH /api/incidents/{id}/status` para transiciones; nunca se cambia el estado con `PUT` o un PATCH genérico.
- `GET /inventory/products` y `GET /inventory/products/{id}`.

El servidor nunca usa rutas de escritura del inventario. `inventory_write_attempt` siempre responde `INVENTORY_READ_ONLY` sin llamar al backend.

La resolución de incidencias está bloqueada en MCP con `HUMAN_CONFIRMATION_REQUIRED`, sin llamada HTTP. El backoffice solicita confirmación explícita y envía `confirm_resolution: true` al endpoint de estado. El backend exige confirmación booleana estricta y registra `resolved_by` y `resolution_confirmed_at`. No existe una excepción para tokens de servicio; no deben usarse fuera de MCP para simular una confirmación humana.

## Herramientas y errores

| Herramienta | Scope | Salida |
| --- | --- | --- |
| `incidents_create` | `incidents:write` | Objeto de incidencia creado; el backend asigna `open`. |
| `incidents_get` | `incidents:read` | `{status, incidents}`; la lista también se usa para una consulta por ID. |
| `incidents_update` | `incidents:write` | Objeto de incidencia actualizado; no acepta `status`. |
| `incidents_transition_status` | `incidents:write` | Objeto actualizado, usando el endpoint dedicado de transición. |
| `inventory_get_products` | `inventory:read` | `{status, products}`, incluyendo `current_stock`. |
| `inventory_write_attempt` | `inventory:read` | Rechazo estable `INVENTORY_READ_ONLY`. |

Los errores controlados devuelven `error_code` y un mensaje breve. Se distinguen `AUTHENTICATION_REQUIRED`, `INVALID_ACCESS_TOKEN`, `INSUFFICIENT_SCOPE`, `INVALID_INPUT`, `INCIDENT_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `INVALID_STATUS_TRANSITION`, `INVENTORY_READ_ONLY`, `UPSTREAM_TIMEOUT`, `UPSTREAM_ERROR` e `INVALID_UPSTREAM_RESPONSE`.

Cada tool ejecutado y cada denegación se registra con `tool_name`, identidad OAuth validada, resultado, código de error e identificador de petición. No se registran tokens, payloads ni descripciones de incidencias.

## Integración cliente

Un cliente MCP usa la URL Streamable HTTP y configura un access token OAuth vigente para `MCP_RESOURCE_URI`, por ejemplo en el header Bearer del transporte. Para la integración del agente, la URL y el token obtenido/provisionado por el cliente OAuth se configuran mediante `SUPPORT_AGENT_MCP_URL` y `SUPPORT_AGENT_MCP_ACCESS_TOKEN`; el token debe incluir los scopes requeridos por las consultas planeadas. No se reenvía el token del cliente del backend REST. Si MCP no está disponible o la autenticación falla, el agente informa el fallo de esa fuente y no consulta directamente el backend como fallback.

## Validación manual

La conexión a MCP Playground no se ha ejecutado ni se afirma como validada. Para completarla en Codespaces, reenvía el puerto 8001 con visibilidad pública, usa la URL reenviada en MCP Playground y prueba las seis herramientas, un token ausente y scopes insuficientes. Registra la URL pública y los resultados reales sin incluir tokens ni secretos.

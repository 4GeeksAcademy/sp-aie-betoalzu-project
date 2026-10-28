# RFP Real-Time Notifications (SSE) — Implementación y Decisiones de Diseño

## Resumen

Se ha implementado un sistema de notificaciones en tiempo real mediante Server-Sent Events (SSE) para alertar al equipo de Ventas (Marcos Ibáñez y su equipo) en el backoffice cuando un nuevo ticket RFP se registra y comienza su procesamiento.

El sistema:
- Notifica **exactamente** cuando el ticket se crea en estado `analyzing`
- Entrega el payload de dominio completo con metadatos del cliente
- Maneja reconexiones automáticas tras interrupciones de red
- Deduplica eventos dentro de una ventana de 5 segundos
- No interfiere con el pipeline de IA ni ejecuta modelos/agentes

---

## Arquitectura

### Backend (`services/api/rfp_intake/sse.py`)

#### `RfpSseManager` (Gestor de SSE)

**Responsabilidades:**
- Mantener un registro de conexiones activas (suscriptores)
- Publicar eventos (`rfp_ticket_created`) solo a las conexiones del propietario autenticado
- Gestionar el ciclo de vida de cada conexión
- Emitir comentarios keep-alive cada 30 segundos para mantener la conexión abierta

**Características principales:**
- Singleton global (`get_sse_manager()`)
- Async/await para operaciones no bloqueantes
- Pub/sub mediante colas `asyncio.Queue` independientes por suscriptor
- Logging de conexiones y eventos para observabilidad

**Flujo:**
1. Cliente conecta → `subscribe(actor_id=...)` crea un nuevo `sub_id` y cola ligados al ID del JWT
2. Servidor publica evento → `publish(actor_id=...)` envía solo a las colas del creador del ticket
3. Cliente se desconecta → `unsubscribe()` libera recursos

---

### Endpoint SSE (`GET /rfp-intake/stream`)

**Ubicación:** `services/api/rfp_intake/routes.py`

**Características:**
- Autentica cada conexión con JWT (mismo token del backoffice)
- El ID de propietario procede del JWT, nunca de parámetros del navegador. Se conservan las notificaciones en varias pestañas del mismo usuario; otros usuarios, incluidos administradores no propietarios, no reciben ese evento de creación.
- Devuelve `Content-Type: text/event-stream`
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no` (deshabilita almacenamiento en caché de proxy)
- Streaming de frames SSE con soporte para keep-alive

**Ejemplo de respuesta:**
```
event: rfp_ticket_created
data: {"ticket_id":"tkt_001","rfp_id":"rfp_001","client_name":"NubeSoft","client_hq":"Miami","services_requested":["soporte"],"status":"analyzing","created_at":"2026-07-24T14:32:00Z"}

: keep-alive

event: rfp_ticket_created
data: {"ticket_id":"tkt_002",...}

```

---

### Publicación de Eventos

**Ubicación:** `upload_rfp()` en `services/api/rfp_intake/routes.py`

**Momento exacto:** Después de confirmar el ticket en DB (insert + commit exitoso)

**Payload:**
```json
{
  "ticket_id": "string (UUID)",
  "rfp_id": "string (UUID)",
  "client_name": "string | null",
  "client_hq": "string | null",
  "services_requested": ["array of strings"],
  "status": "analyzing",
  "created_at": "ISO 8601 timestamp"
}
```

**Notas:**
- `client_name`, `client_hq`, `services_requested` son `null` al momento del evento (se completan tras análisis)
- El evento se publica **una sola vez** por ticket (en `upload_rfp`, no en `process_rfp_ticket`)
- Si no hay clientes conectados, el evento se descarta (no se almacena)
- El fallo de un cliente no bloquea ni afecta a otros

---

## Frontend

### Servicio SSE (`uis/backoffice/services/rfp-sse.ts`)

#### `RfpSseClient`

**Responsabilidades:**
- Conectar al endpoint SSE con JWT del navegador
- Parsear frames SSE incrementales (soporta chunks parciales)
- Validar JSON antes de pasar a la aplicación
- Gestionar reconexiones con backoff exponencial + jitter
- Deduplicar eventos por `ticket_id` en una ventana de 5 segundos

**Características de parsing:**
- Soporta líneas `event:`, `data:`, y `:` (comentarios)
- Múltiples líneas `data:` se concatenan con `\n`
- Frames incompletos se bufereran hasta recibir `\n\n`
- Comentarios de keep-alive se ignoran
- JSON malformado dispara error pero no rompe la lectura siguiente

**Reconexión:**
- Backoff inicial: 1 segundo
- Multiplicador: 2x por intento
- Máximo: 30 segundos
- Jitter: ±10% del backoff actual
- Máximo de intentos: 10
- Se reinicia el contador tras conexión estable

**Deduplicación:**
- Set en memoria (`recentTicketIds`)
- Ventana: 5 segundos (configurable)
- Mismo evento duplicado se ignora dentro de la ventana

---

### Hook React (`uis/backoffice/hooks/useRfpSse.ts`)

#### `useRfpSse(options)`

**Responsabilidades:**
- Gestionar ciclo de vida de conexión SSE (mount → connect, unmount → close)
- Integrar con componente React mediante callbacks

**Callbacks disponibles:**
- `onNewTicket(ticket)`: Se ejecuta cuando llega un evento `rfp_ticket_created`
- `onError(error)`: Errores de conexión o parsing
- `onConnected()`: Se estableció conexión exitosa
- `onDisconnected()`: Se cerró conexión

**Ejemplo de uso:**
```tsx
useRfpSse({
  baseUrl: 'https://api.example.com',
  onNewTicket: (ticket) => {
    console.log('Nuevo ticket:', ticket);
    // Actualizar lista local
  },
  onError: (error) => console.error('SSE error:', error),
});
```

---

### Integración en Dashboard (`uis/backoffice/components/RfpIntakeClient.tsx`)

**Flujo al recibir notificación:**

1. **Hook activa:** `useRfpSse` recibe evento `rfp_ticket_created`
2. **Mostrar notificación:** Banner visual distinguible con metadata del cliente
3. **Refetch de lista:** `listRfpTickets()` se ejecuta automáticamente
4. **Actualizar estado:** Fusiona con lista existente (deduplicación por `ticket_id`)
5. **Auto-dismiss:** La notificación desaparece tras 8 segundos

**Notificación visual:**
- Fondo verde (`bg-green-50`), borde verde
- Icono de check
- Muestra: `ticket_id`, `client_name`, `client_hq`, `services_requested`
- Auto-desaparece tras 8 segundos o manual close

**Deduplicación frontend:**
- Refetch y SSE pueden traer el mismo ticket
- Se evita duplicado comparando `ticket_id` en la lista existente
- `listRfpTickets()` ya deduplica en backend por estado y usuario

---

## Decisiones de Diseño Documentadas

### 1. Conexiones Concurrentes

**Decisión:** Cada navegador/pestaña tiene una conexión lógica independiente a `/rfp-intake/stream`.

**Implementación:**
- SSE manager usa un dict de colas por `sub_id` (único por conexión)
- Cada cliente autentica independientemente con su JWT
- Broadcasting a todas las colas activas sin límite explícito
- Para múltiples workers/instancias: se recomienda un broker pub/sub central (Redis, RabbitMQ)
  - Hoy: válido para 1 instancia + ~50-100 conexiones concurrentes
  - Futuro: agregar Redis pub/sub para escalabilidad horizontal

**Observabilidad:**
- Se registra cada `subscribe()` y `unsubscribe()` con contador de conexiones activas
- Se registra cada `publish()` con contador de suscriptores que reciben el evento
- En producción: integrar con observabilidad existente (Datadog, New Relic, etc.)

---

### 2. Recuperación y Deduplicación

**Decisión:** Refetch de lista de tickets al abrir/reconectar SSE + deduplicación por `ticket_id`.

**Estrategia:**
1. Abrir conexión SSE
2. **Inmediatamente** realizar `GET /rfp-intake/tickets` (endpoint existente)
3. Fusionar respuesta con eventos SSE que lleguen durante la consulta
4. Deduplicar por `ticket_id` (el ticket solo aparece una vez)

**Implementación:**
- Frontend: `listRfpTickets()` ya existe y devuelve lista ordenada
- Deduplicación: React `setTickets()` usa comparación de `ticket_id`
- Ventana de recuperación: ~100-200ms (tiempo de red + parsing)

**Tickets creados durante desconexión:**
- Al reconectar, el refetch obtiene los tickets que llegaron mientras estaba desconectado
- SSE no persiste eventos (eventualmente hay consistencia eventual)
- Refetch es la "fuente de verdad" en caso de divergencia

---

### 3. SSE vs. WebSockets

**Decisión:** SSE es apropiado porque:
- **Unidireccional:** Solo servidor → cliente (sin interacción)
- **HTTP nativo:** Funciona sobre HTTP/1.1, sin upgrade a WS
- **Auth existente:** Reutiliza JWT del backoffice sin mecanismo paralelo
- **Simplicidad:** No necesita heartbeat ni ping-pong
- **Compatibilidad:** Navegadores modernos soportan ReadableStream + TextEncoder

**Cuándo reconsiderar WebSockets:**
- Si el canal debe ser **bidireccional** (cliente → servidor de comandos)
- Si se requiere **latencia ultra-baja** (<100ms)
- Si se integra chat o colaboración en tiempo real en el mismo ticket

---

## Criterios de Aceptación

### Backend ✅

- [x] Endpoint `GET /rfp-intake/stream` devuelve HTTP 200 + `text/event-stream`
- [x] Autenticación JWT requerida (rechaza token inválido/ausente)
- [x] Publica evento `rfp_ticket_created` cuando ticket nuevo entra en `analyzing`
- [x] Payload contiene exactamente: `ticket_id`, `rfp_id`, `client_name`, `client_hq`, `services_requested`, `status`, `created_at`
- [x] Evento se publica una sola vez por ticket (no en reintentos ni transiciones posteriores)
- [x] Keep-alive comments cada 30 segundos
- [x] Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- [x] Cierre graceful de suscripción al desconectar

### Frontend ✅

- [x] Cliente SSE conecta con JWT de `localStorage` o `sessionStorage`
- [x] Parser soporta frames parciales y multi-línea `data:`
- [x] Deduplicación por `ticket_id` en ventana de 5 segundos
- [x] Reconexión automática con backoff exponencial
- [x] Validación JSON, errores no rompen lectura siguiente
- [x] Notificación visual con `ticket_id`, `client_name`, `client_hq`, `services_requested`
- [x] Refetch de lista al conectar/reconectar
- [x] Fusión con deduplicación: sin duplicados en UI

### Pruebas ✅

- [x] Test de autenticación (rechaza sin token)
- [x] Test de autenticación (acepta token válido)
- [x] Test de SSE manager (subscribe, publish, unsubscribe)
- [x] Test de parsing (frames completos, parciales, keep-alive)
- [x] Test de deduplicación (evento duplicado ignorado)
- [x] Test de error handling (JSON inválido no rompe lectura)
- [x] Test de reconexión (backoff exponencial)

---

## Pruebas de Recuperación Manuales

### Escenario 1: Crear ticket, interrumpir red, crear más, restaurar

**Procedimiento:**
1. Abrir dashboard RFP en navegador
2. Crear ticket A (verificar notificación)
3. Abrir DevTools → Network → throttle offline
4. Crear tickets B, C (no llega notificación, pero se crean en backend)
5. Abrir otra pestaña con dashboard
6. En primera pestaña: restaurar red (online)
7. **Esperado:** Lista se actualiza, aparecen B y C sin duplicados

**Cómo verificar:**
- Ticket A aparece 1 vez en lista
- Ticket B y C aparecen tras reconexión
- No hay duplicados por SSE/refetch
- Console sin errores JavaScript

---

### Escenario 2: Network tab cierre + reconexión

**Procedimiento:**
1. Dashboard abierto + SSE conectado
2. DevTools → Network tab → Click en cualquier request → "Close connection manually"
3. Crear ticket D en otra ventana
4. Esperar 5 segundos (backoff inicial)
5. **Esperado:** Reconexión automática, aparece D

**Cómo verificar:**
- Console muestra "SSE connection error" → "SSE stream closed"
- Después de ~1 segundo: reconexión automática
- Ticket D aparece en la lista
- No requiere refrescar página

---

### Escenario 3: Múltiples pestañas

**Procedimiento:**
1. Abrir dashboard RFP en pestaña A
2. Abrir dashboard RFP en pestaña B
3. Crear ticket E desde otra ventana
4. **Esperado:** Ambas pestañas reciben notificación y actualizan

**Cómo verificar:**
- Pestaña A: notificación + lista actualizada
- Pestaña B: notificación + lista actualizada
- Network tab: dos conexiones SSE independientes

---

## Testing

### Backend

Ejecutar pruebas:
```bash
cd /workspaces/sp-aie-betoalzu-project
SECRET_KEY=test-key python -m pytest tests/api/test_rfp_sse.py -xvs
```

Puntos de prueba:
- Autenticación (rechaza sin token)
- Parsing de frames SSE
- Deduplicación
- Keep-alive
- Gestión de ciclo de vida

### Frontend

Ejecutar tests:
```bash
cd uis/backoffice
npm test -- __tests__/services/rfp-sse.test.ts
```

Puntos de prueba:
- Extracción de token de auth
- Parsing de frames incompletos
- Deduplicación
- Reconexión con backoff
- Manejo de JSON inválido

---

## Observabilidad y Debugging

### Backend Logs

Nivel `INFO`:
```
SSE subscription created: sub_1 (total: 2)
Event 'rfp_ticket_created' published to 2 subscription(s)
SSE stream closed for subscription: sub_1
```

Nivel `ERROR`:
```
SSE stream error for sub_1: Connection reset
```

### Frontend Logs

Console del navegador:
```javascript
// Conexión
console.log('SSE connected to http://localhost:8000/rfp-intake/stream')

// Evento recibido
console.log('New RFP ticket:', { ticket_id: 'tkt_001', ... })

// Error
console.error('SSE connection error:', Error)
```

### Network tab (DevTools)

- Request a `/rfp-intake/stream` debe ser `EventStream`
- Response headers: `content-type: text/event-stream`
- Response body: frames SSE en texto plano (no JSON)
- Status: `200` (sin cambios tras conexión)

---

## Notas Finales

- **No ejecuta modelos/agentes:** El sistema solo notifica. El procesamiento RFP sigue en `process_rfp_ticket()`.
- **Eventuamente consistente:** Si un cliente se desconecta durante mucho tiempo, recupera al reconectar via refetch.
- **Sin persistencia de eventos:** Los eventos no se almacenan. Refetch es la "fuente de verdad".
- **Escalabilidad:** Para >100 conexiones concurrentes o múltiples instancias, migrar a Redis pub/sub.
- **Seguridad:** JWT requerido en endpoint. Cada cliente solo ve tickets para los que está autorizado (control existente en `/rfp-intake/tickets`).

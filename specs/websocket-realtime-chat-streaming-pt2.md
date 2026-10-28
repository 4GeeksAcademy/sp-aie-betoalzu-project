# Especificación: WebSocket Streaming de Chat en Tiempo Real (Parte 2)

**Contexto:**  
Referencia obligatoria: [BRIEFING — Nexova: Sistemas en Tiempo Real (Parte 2)](/workspaces/sp-aie-betoalzu-project/docs/briefing-real-time-system-pt2.md)

**Objetivo:**  
Reemplazar el modelo de petición/respuesta única en el chat de soporte de Nexova con un stream bidireccional en tiempo real que permite:
1. **Streaming de tokens**: la respuesta del agente llega token por token conforme se generan
2. **Interrupción genuina**: el usuario puede abortar una generación en curso y redirigir al agente
3. **Reconexión con contexto**: al caer la conexión, rehidratarla con el mismo `session_id` y restaurar el historial

---

## 1. Entidades y Modelos de Datos

### ChatSession (Principal)
```yaml
session_id: string          # Clave primaria, válida para toda la conversación
agent_id: string            # Valor fijo: "first_line_support"
user_id: string             # Cliente que chatea (del JWT)
client_id: string           # Empresa cliente de Nexova
status: enum                # "active" | "interrupted" | "closed"
thread_id: string           # LangGraph thread_id (= session_id si usas checkpoint)
created_at: ISO8601
updated_at: ISO8601
checkpoint_id: string | null # Último checkpoint del grafo (para rehidratación)
```

**Vinculación WebSocket:**  
- El `session_id` se proporciona en el handshake (URL params o primer frame de auth)
- Es el identificador único para todas las suscripciones pub/sub durante la sesión

### Message (Historial del Chat)
```yaml
message_id: string          # Generado por el backend
session_id: string          # Foreign key → ChatSession
sender: enum                # "user" | "assistant"
text: string                # Contenido (vacío si status="interrupted" y sin tokens aún)
tokens_received: number     # Cantidad de tokens entregados (para status="interrupted")
status: enum                # "completed" | "interrupted" | "pending"
created_at: ISO8601
```

---

## 2. Requisitos Funcionales

### 2.1 Conexión WebSocket con Autenticación
- **URL Base**: `/ws/chat/{session_id}`
- **Parámetro de Autenticación**:
  - Preferencia 1: Token JWT en query string (`?token=<JWT>`)
  - Preferencia 2: Frame de auth en primer mensaje del cliente
  - **Rechazo obligatorio antes de cualquier evento de chat** si falta o es inválido
  - Usa el **mismo JWT** que la API del backoffice (Parte 1)

**Validación en el Handshake:**
```yaml
1. Extraer JWT del query string o primer frame
2. Validar firma y expiración
3. Extraer user_id, client_id del JWT
4. Validar que el user_id es propietario de session_id
5. Si falla → Cerrar conexión con código 403 (Forbidden) / 401 (Unauthorized)
6. Si válido → Permitir suscripción a canal pub/sub
```

### 2.2 Streaming de Tokens
- **Disparador**: mensaje del usuario entrante (evento `user_message` o frame directo)
- **Proceso**:
  1. Recibir input del usuario → crear Message con status="pending"
  2. Llamar al agente de soporte con `thread_id=session_id`
  3. Conectar el stream de LangGraph al canal pub/sub (`chat.{session_id}`)
  4. **Cada token generado** → emitir evento `token_chunk` con:
     ```json
     {
       "event": "token_chunk",
       "data": {
         "session_id": "chat_0157",
         "message_id": "msg_0322",
         "token": "Claro",
         "sequence": 4,
         "timestamp": "2026-10-28T18:00:00Z"
       }
     }
     ```
  5. Acumular tokens en memoria (no persisten hasta que se completa)

- **Finalización Normal**:
  - Cuando el agente termine → emitir `generation_completed`:
    ```json
    {
      "event": "generation_completed",
      "data": {
        "session_id": "chat_0157",
        "message_id": "msg_0322",
        "status": "completed",
        "total_tokens": 42
      }
    }
    ```
  - Guardar Message completo en base de datos con status="completed"

### 2.3 Interrupción y Abort de Stream
- **Evento del Cliente**: `interrupt_requested`
  ```json
  {
    "event": "interrupt_requested",
    "data": {
      "session_id": "chat_0157",
      "new_input": "en realidad mi pregunta era sobre la factura"
    }
  }
  ```

- **Acciones del Backend**:
  1. **Abortar el stream en curso**: detener la generación del modelo (no es `interrupt()` de LangGraph, es cancel/cleanup del stream)
  2. **NO usar LangGraph `interrupt()`** como sustituto del abort del stream (si lo usas, úsalo solo para pausas de grafo adicionales, no para abortar tokens)
  3. **Marcar el mensaje parcial**:
     ```json
     {
       "event": "generation_interrupted",
       "data": {
         "session_id": "chat_0157",
         "message_id": "msg_0321",
         "status": "interrupted",
         "tokens_shown": 15
       }
     }
     ```
     - Guardar en BD: Message con status="interrupted", text=tokens_acumulados, tokens_received=15
  4. **No borrar ni sobrescribir** el mensaje interrumpido — conservar como registro del turno anterior
  5. **Iniciar turno nuevo**:
     - Crear nuevo Message con sender="user", text=new_input, status="completed"
     - Invocar el agente con new_input (y `thread_id=session_id`)
     - Emitir evento `user_message` al canal pub/sub
     - Comenzar nuevo stream de tokens (nuevo `message_id`)

### 2.4 Reconexión y Rehidratación
- **Escenario**: Cliente reconecta con el mismo `session_id` tras caída de red
- **Proceso**:
  1. Validar JWT (igual que en 2.1)
  2. Cargar desde BD:
     - Historial completo de Messages (todos los turno hasta ahora)
     - Último checkpoint de LangGraph (si existe)
  3. **Antes de aceptar tokens nuevos**, emitir evento `session_snapshot`:
     ```json
     {
       "event": "session_snapshot",
       "data": {
         "session_id": "chat_0157",
         "checkpoint_id": "ckpt_789",
         "messages": [
           {
             "message_id": "msg_0320",
             "sender": "user",
             "text": "Tengo un problema con una factura"
           },
           {
             "message_id": "msg_0321",
             "sender": "assistant",
             "text": "Entendido, voy a buscar tu",
             "status": "interrupted",
             "tokens_shown": 15
           },
           {
             "message_id": "msg_0322",
             "sender": "user",
             "text": "en realidad mi pregunta era sobre la factura"
           }
         ]
       }
     }
     ```
  4. Ahora sí: aceptar nuevos frames de entrada del usuario

- **Garantía**: No se pierde el hilo de conversación — el historial y el checkpoint se restauran como si la conexión nunca hubiera caído

---

## 3. Patrón Pub/Sub (Desacoplamiento Productor/Consumidor)

### Arquitectura
```
┌─────────────────────────────────────────┐
│  Agent (LangGraph Stream)               │
│  └→ emite tokens a través del pub/sub   │
└──────────┬──────────────────────────────┘
           │ Publica en: chat.<session_id>
           ▼
┌─────────────────────────────────────────┐
│  Pub/Sub Broker (en memoria o Redis)    │
│  Canal: chat.<session_id>               │
└──────────┬──────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌─────────────┐ ┌─────────────┐
│ WebSocket   │ │ WebSocket   │
│ Client 1    │ │ Client 2    │
└─────────────┘ └─────────────┘
```

### Implementación
- **Para esta entrega**: mecanismo en memoria es aceptable (un solo proceso)
- **Interfaz mínima**:
  ```python
  class PubSubBroker:
      def subscribe(self, channel: str, callback: Callable)
      def unsubscribe(self, channel: str, callback: Callable)
      def publish(self, channel: str, message: dict)
  ```
- **Ventajas**:
  - El agente no conoce ni depende de conexiones WebSocket directas
  - Varios clientes suscritos a `chat.{session_id}` reciben los mismos eventos sin duplicar llamadas al agente
  - Fácil escalar a Redis / RabbitMQ en futuro

### Canales
- **Producción**: Agente publica en `chat.<session_id>`
- **Suscripción**: Cada conexión WebSocket se suscribe a `chat.<session_id>`

---

## 4. Eventos del WebSocket (Contrato)

### Desde el Backend (→ Cliente)
| Evento | Cuándo | Payload |
|--------|--------|---------|
| `token_chunk` | Se genera un token | `{session_id, message_id, token, sequence}` |
| `generation_completed` | Termina la generación | `{session_id, message_id, status, total_tokens}` |
| `generation_interrupted` | Se aborta un stream | `{session_id, message_id, status, tokens_shown}` |
| `session_snapshot` | Reconexión / rehidratación | `{session_id, checkpoint_id, messages[]}` |
| `user_message` | Input del usuario (eco/confirmación) | `{session_id, message_id, text}` |
| `error` | Fallo (auth, validación, etc.) | `{code, message}` |

### Desde el Cliente (→ Backend)
| Evento | Cuándo | Payload |
|--------|--------|---------|
| `auth` (opcional) | Si JWT no va en URL | `{token}` |
| `user_message` | Usuario envía input | `{text, session_id}` |
| `interrupt_requested` | Usuario quiere abortar | `{session_id, new_input}` |

---

## 5. Seguridad

### Autenticación
- JWT válido obligatorio antes de cualquier evento de chat
- Extraer `user_id`, `client_id` del token
- Validar propietario: user_id del token = user_id de ChatSession

### Autorización
- Un cliente solo puede acceder a sesiones que le pertenecen
- No es posible "espiar" sesiones de otro usuario aunque conozcas el `session_id`

### Validación de Entrada
- `session_id`: debe existir en BD y estar activo
- `text`: no vacío, length < 10000 (o límite de tu sistema)
- `token` (en jwt): firma válida, expiración futura

---

## 6. Persistencia

### Bases de Datos Requeridas
- **ChatSession**: Crear si no existe, actualizar `updated_at` y `status`
- **Message**: Insertar mensajes conforme llegan del usuario, guardar completos tras `generation_completed` o `generation_interrupted`
- **LangGraph Checkpoints** (si usas): Sincronizar `checkpoint_id` en ChatSession para rehidratación

### Transacciones
- Al crear new Message de usuario → crear transacción, guardar, y solo entonces invocar agente
- Al recibir `generation_completed` → guardar Message completo en una transacción (no en partes)

---

## 7. Requisitos Funcionales del Frontend

### 7.1 Renderizado Progresivo
- **Efecto de escritura en vivo**: mostrar tokens conforme llegan (no esperar a `generation_completed`)
- No reemplazar la respuesta completa al final — acumular tokens en el DOM

### 7.2 Control de Interrupción
- Botón / control visible mientras la respuesta está en curso
- Al presionar → enviar evento `interrupt_requested` al backend
- Mostrar visualmente que el mensaje anterior está `interrupted` (ej: etiqueta, ícono)
- Permanecer en la conversación (no cerrar chat, no limpiar historial)

### 7.3 Reconexión Automática
- Detectar caída del socket (evento `close` o timeout)
- **Backoff progresivo**: 1s, 2s, 4s, 8s (máx. 30s, ej)
- Al reconectar: enviar JWT + mismo `session_id`
- Esperar a `session_snapshot` antes de aceptar nuevos inputs

### 7.4 Manejo de Errores
- Mostrar error si JWT falla o expira
- Si `session_id` no existe → error claro
- Reconexión transparente: no mostrar popup a menos que falle definitivamente

---

## 8. Pruebas

### Unitarias (Backend)
- [ ] Validación de JWT en handshake (válido/inválido/expirado)
- [ ] Parsing de eventos (`token_chunk`, `interrupt_requested`, etc.)
- [ ] Pub/Sub broker: suscripción, publicación, múltiples suscriptores

### Integración (Backend)
- [ ] Flujo completo: conectar → enviar mensaje → recibir tokens → completar
- [ ] **Interrupción a mitad de respuesta**:
  - Conectar, enviar mensaje, esperar 5-10 tokens
  - Enviar `interrupt_requested`
  - Verificar: no hay más tokens de esa generación, `generation_interrupted` emitido, mensaje guardado con status="interrupted"
  - Enviar nuevo input, verificar: nuevo `message_id`, nuevo stream de tokens
- [ ] **Reconexión**:
  - Conectar, enviar mensaje, generar algunos tokens
  - Simular caída (cerrar socket abruptamente)
  - Reconectar con mismo `session_id` y JWT
  - Verificar: `session_snapshot` recibido con historial completo
  - Enviar nuevo input, verificar: se retoma conversación sin perder contexto

### Manual (UX)
- [ ] Chat se muestra responsivo (tokens aparecen sin lag)
- [ ] Al interrumpir, respuesta anterior queda visible y marcada
- [ ] Reconexión es invisible al usuario (no pierde mensajes)

---

## 9. Restricciones y Consideraciones

### Nombres de Entidades y Campos
**Obligatorio**: Coincidir con BRIEFING
- `session_id` (no "sessionId", "chat_id", etc.)
- `message_id` (no "msgId")
- `thread_id` (para LangGraph)
- `tokens_received` (contador de tokens interrumpidos)
- Status: `"completed" | "interrupted" | "pending"`
- Events: `token_chunk`, `generation_completed`, `generation_interrupted`, `session_snapshot`, `user_message`

### No Cambiar
- Lógica interna del agente de soporte
- Herramientas del agente
- Memoria del agente
- Payloads RFP/SSE de la Parte 1 (mezclar en WebSocket está prohibido)

### Fuera de Alcance
- No construir un agente nuevo
- No rediseñar las herramientas del soporte
- No crear nuevos canales de venta o integraciones externas (solo chat interno)

---

## 10. Preguntas de Diseño (Antes de PR)

Documenta tu respuesta a estas preguntas en la PR o en un comentario:

1. **¿Por qué WebSocket y no SSE?**  
   Explica qué requisito específico obliga bidireccionalidad (hint: interrupciones desde el cliente mientras el servidor sigue enviando).

2. **Múltiples clientes observando la misma sesión:**  
   Si un supervisor se suscribe a `chat.{session_id}` mientras un cliente chatea, ¿cómo evitas:
   - Duplicar llamadas al agente?
   - Que uno interrumpa la respuesta que el otro está viendo?
   - Conflictos de quién puede interrumpir?

3. **Abort del stream vs. LangGraph `interrupt()`:**  
   Si usaste `interrupt()`, ¿cómo separaste "parar tokens" (abort del stream) de "pausar grafo" (HITL)?  
   ¿Qué sucede con el mensaje parcial interrumpido? ¿Cómo se reanuda el turno siguiente?

---

## 11. Checklist de Implementación

### Backend
- [ ] Endpoint WebSocket `/ws/chat/{session_id}`
- [ ] Validación JWT (query param y/o primer frame)
- [ ] Modelos: `ChatSession`, `Message`
- [ ] Integración con agente de soporte + LangGraph stream
- [ ] Pub/Sub broker (en memoria)
- [ ] Manejo de `token_chunk` → acumular → `generation_completed` / `generation_interrupted`
- [ ] Abort del stream (cancel task / cleanup)
- [ ] Reconexión + `session_snapshot` + rehidratación
- [ ] Persistencia de ChatSession y Message
- [ ] Pruebas unitarias + integración
- [ ] Documentar respuestas a preguntas de diseño

### Frontend
- [ ] Conectar al WebSocket en lugar de petición única
- [ ] Renderizado progresivo de tokens
- [ ] Control de interrupción (botón)
- [ ] Mostrar mensajes parciales / interrumpidos
- [ ] Reconexión automática con backoff
- [ ] Mostrar historial en `session_snapshot`
- [ ] Pruebas manuales de UX

---

## 12. Referencias

- [BRIEFING — Nexova: Sistemas en Tiempo Real (Parte 2)](/workspaces/sp-aie-betoalzu-project/docs/briefing-real-time-system-pt2.md)
- [Reto (source)](/workspaces/sp-aie-betoalzu-project/sistema-tiempo-real-pt2.md)
- LangGraph Streaming: [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- WebSocket (Python asyncio): [Python asyncio docs](https://docs.python.org/3/library/asyncio.html)
- WebSocket (JavaScript): [MDN WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

---

**Versión**: 1.0  
**Fecha**: 2026-10-28  
**Autor**: Especificación técnica para implementación de streaming de chat WebSocket

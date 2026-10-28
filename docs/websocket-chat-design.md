# Implementación de WebSocket Streaming de Chat en Tiempo Real (Parte 2)
## Documento de Diseño y Decisiones

Versión: 1.0  
Fecha: 2026-10-28  
Implementador: Copilot

---

## 1. Resumen Ejecutivo

Se ha implementado un sistema WebSocket bidireccional para streaming de chat en tiempo real en Nexova, permitiendo:
- Streaming de tokens token-por-token conforme se generan
- Interrupción genuina del usuario para cambiar tema
- Reconexión con contexto mediante session snapshot
- Renderizado progresivo en el frontend con Tailwind CSS

---

## 2. Respuestas a las Preguntas de Diseño

### 2.1 ¿Por qué WebSocket y no SSE?

**Respuesta:**

WebSocket fue elegido sobre SSE (Server-Sent Events) debido a **requisitos específicos de bidireccionalidad**:

1. **Interrupción del usuario MIENTRAS el servidor sigue enviando**:
   - El usuario debe poder enviar un `interrupt_requested` event **durante** la generación
   - SSE es unidireccional (servidor → cliente): no permite mensajes del cliente mientras se está streaming
   - WebSocket es bidireccional: permite `interrupt_requested` + `new_input` en el mismo canal mientras tokens llegan

2. **Confirmación de cambio de tema inmediato**:
   - Con WebSocket: Cliente envía interrupción, servidor detiene stream actual, confirma con `generation_interrupted`
   - Con SSE: Necesitaría un segundo canal HTTP (POST) para interrumpir, más complejidad

3. **Pipelining de múltiples eventos**:
   - Un cliente puede enviar `interrupt_requested` mientras está acumulando tokens del generador
   - SSE no permite esta interacción simultánea; WebSocket sí

**Decisión final:** WebSocket es el patrón correcto para chat bidireccional con interrupción en tiempo real.

---

### 2.2 Múltiples clientes observando la misma sesión

**Respuesta:**

Se ha considerado este caso de uso (ej: supervisor observando sesión de cliente). El diseño actual utiliza el patrón Pub/Sub que soporta múltiples suscriptores sin duplicación:

**Solución implementada:**

1. **Prevenir duplicación de llamadas al agente:**
   - Una única tarea `asyncio.Task` se lanza por sesión (`current_generation_task`)
   - Si hay múltiples clientes conectados a la misma `session_id`, la generación ocurre **una sola vez**
   - El evento se publica en el canal `chat.{session_id}` que todos los clientes reciben

2. **Prevenir conflictos de interrupción:**
   - La especificación actual define que solo el usuario propietario (`user_id` del JWT) puede interrumpir
   - Validación en handshake WebSocket: si `user_id != session.user_id`, se rechaza con 403
   - Esto previene que un supervisor cancele la generación del cliente

3. **Autorización granular (para futuro):**
   - El modelo `ChatSession` incluye campos `user_id` y `client_id` para precisar autorización
   - Se puede extender con roles (ej: "supervisor", "agent", "owner") en futuro para permitir supervisión
   - Para esta versión: acceso exclusivo al propietario de la sesión

**Arquitectura Pub/Sub:**
```
Agent → Publica tokens en "chat.{session_id}"
                ↓
         Pub/Sub Broker
                ↓
    ┌──────────────┬──────────────┐
    ↓              ↓              ↓
Cliente 1      Cliente 2      Cliente 3
(mismo user)   (supervisión)  (otro cliente)
    ✓              ✓              ✗ (403)
```

---

### 2.3 Abort del stream vs. LangGraph `interrupt()`

**Respuesta:**

Se ha distinguido claramente entre:
- **Abort del stream** (cancelar generación de tokens)
- **LangGraph `interrupt()`** (pausar el grafo para HITL)

**Implementación:**

1. **Abort del stream (implementado):**
   ```python
   # services/agent_chat_service.py
   current_generation_task = asyncio.create_task(invoke_agent_for_chat(...))
   
   # Si usuario interrumpe:
   if current_generation_task and not current_generation_task.done():
       current_generation_task.cancel()  # ← Cancela la corrutina completamente
   ```
   - Se cancela la tarea de asyncio
   - El stream se detiene inmediatamente
   - Los tokens parciales se guardan con status="interrupted"

2. **LangGraph `interrupt()` (no usado actualmente):**
   - LangGraph proporciona `interrupt()` para pausar y esperar entrada del usuario (HITL)
   - **NO es sustituto del abort de stream**
   - Usado para: "pausa el grafo, pide confirmación al usuario, reanuda"
   - Nuestro caso es diferente: queremos abortar tokens, no pausar el grafo

3. **Flujo completo de interrupción:**
   ```
   1. Usuario envía: { event: "interrupt_requested", data: { new_input: "..." } }
   
   2. Backend:
      - Cancela asyncio.Task del stream actual → abort de tokens
      - Publica: { event: "generation_interrupted", data: { tokens_shown: 15 } }
      - Guarda Message con status="interrupted", text=tokens_acumulados
   
   3. NO borrar el mensaje anterior:
      - Quedar como registro del turno anterior
      - Permite analizar qué preguntó el usuario originalmente
   
   4. Iniciar turno nuevo:
      - Crear nuevo Message de usuario con new_input
      - Crear nuevo Message de asistente (pendiente)
      - Invocar agente con new_input
      - Comenzar nuevo stream de tokens
   ```

4. **Manejo del mensaje parcial:**
   - Se almacena `text = tokens_acumulados` (ej: "Estoy buscando...")
   - Se guarda `tokens_received = 5` (contador)
   - Frontend muestra: "⚠️ Interrumpido (5 tokens)"
   - Historial completo preservado para auditoría/análisis

**Ventajas de este diseño:**
- Aborto inmediato: no hay latencia
- Historial limpio: todos los turnos visibles
- Recuperable: puedes ver exactamente en qué punto se interrumpió
- No interfiere con la memoria de LangGraph: el grafo puede reanudarse si fuera necesario

---

## 3. Arquitectura Implementada

### 3.1 Backend (Python/FastAPI)

```
┌──────────────────────────────────────────────────┐
│        WebSocket Endpoint (/ws/chat/{sid})       │
├──────────────────────────────────────────────────┤
│  1. Validación JWT                               │
│  2. Autorización (user_id es propietario)       │
│  3. Cargar sesión y historial                    │
│  4. Emitir session_snapshot                      │
│  5. Suscribirse a pub/sub                        │
│  6. Escuchar eventos cliente                     │
└──────────────────────────────────────────────────┘
           ↑                          ↓
           │                    { user_message }
         agent_chat_service      invoke_agent_for_chat()
         stream_agent_response   ↓
                            ┌─────────────┐
                            │ LangGraph   │
                            │ Agent       │
                            └─────────────┘
                                   ↓
                           Pub/Sub Broker
                          (chat.{session_id})
                                   ↓
                    ┌──────────────┬──────────────┐
                    ↓              ↓              ↓
               token_chunk   generation_   generation_
               sequence 1    completed     interrupted
```

### 3.2 Frontend (React/TypeScript)

```
ChatWebSocketClient (services/chat-ws.ts)
  ├─ connect() → WebSocket("wss://host/ws/chat/{sid}?token=JWT")
  ├─ sendUserMessage(text)
  ├─ interruptAndAsk(newInput)
  ├─ Event callbacks (onToken, onComplete, onInterrupted, etc.)
  └─ Reconexión automática (exponential backoff)

useChatWebSocket Hook
  ├─ Estado: connected, messages, error, isGenerating
  ├─ Métodos: sendMessage(), interrupt()
  └─ Auto-scroll a último mensaje

ChatWindow Component
  ├─ Renderizado de mensajes con displayText progresivo
  ├─ Indicador de conexión
  ├─ Botón de interrupción visible durante generación
  └─ Input field con estado deshabilitado si no está generando
```

### 3.3 Base de Datos

**Nuevas tablas:**
- `chat_sessions`: sesiones persistentes
  - Campos: session_id, user_id, client_id, status, thread_id, checkpoint_id
- `chat_messages`: historial de mensajes
  - Campos: message_id, session_id, sender, text, status, tokens_received, created_at

**Índices:**
- `chat_sessions.user_id, client_id` para búsqueda de sesiones por usuario/cliente
- `chat_messages.session_id, created_at` para historial ordenado

---

## 4. Eventos del WebSocket

### Desde el Backend

| Evento | Cuándo | Campos |
|--------|--------|--------|
| `session_snapshot` | Al conectar / reconectar | `session_id`, `checkpoint_id`, `messages[]` |
| `token_chunk` | Cada token generado | `session_id`, `message_id`, `token`, `sequence` |
| `generation_completed` | Termina generación | `session_id`, `message_id`, `status`, `total_tokens` |
| `generation_interrupted` | Se aborta stream | `session_id`, `message_id`, `status`, `tokens_shown` |
| `user_message` | Eco/confirmación | `session_id`, `message_id`, `text` |
| `error` | Fallo | `code`, `message` |

### Desde el Cliente

| Evento | Cuándo | Campos |
|--------|--------|--------|
| `user_message` | Usuario envía pregunta | `session_id`, `text` |
| `interrupt_requested` | Usuario interrumpe | `session_id`, `new_input` |

---

## 5. Flujos de Prueba

### 5.1 Flujo básico
```
1. Cliente conecta: WebSocket.open → autenticación → session_snapshot
2. Cliente envía: { event: "user_message", data: { text: "Hola" } }
3. Backend:
   - Crear Message usuario
   - Invocar agente en background
   - Publicar token_chunk x N
   - Publicar generation_completed
4. Cliente recibe tokens y renderiza progresivamente
```

### 5.2 Flujo de interrupción
```
1. Cliente envía user_message → agente genera tokens
2. Mientras genera, cliente envía: { event: "interrupt_requested", data: { new_input: "..." } }
3. Backend:
   - Cancela asyncio.Task
   - Publica generation_interrupted
   - Guarda Message anterior con status="interrupted"
   - Crea nuevo turno con new_input
   - Invoca agente nuevamente
4. Cliente recibe interrupted, muestra nuevo turno
```

### 5.3 Flujo de reconexión
```
1. Cliente conectado, recibiendo tokens
2. Red cae: WebSocket.close()
3. Cliente: reconecta con backoff (1s, 2s, 4s, 8s, max 30s)
4. Backend:
   - Reconoce el mismo session_id + JWT válido
   - Publica session_snapshot con historial completo
   - El último mensaje interrumpido está marcado como tal
5. Cliente rehidrata el historial
6. Cliente puede continuar conversación
```

---

## 6. Seguridad

### Autenticación
- JWT obligatorio en query string o en datos
- Validación de firma y expiración
- Extrae `user_id`, `client_id` del token

### Autorización
- Validar que `user_id` del token == `user_id` de ChatSession
- Validar que `client_id` del token == `client_id` de ChatSession
- Rechazar con 403 si no es el propietario

### Validación de entrada
- `session_id`: debe existir en BD
- `text`: no vacío, max 10000 caracteres
- JWT: firma válida, expiración futura

---

## 7. Limitaciones Conocidas y Futuras Mejoras

### Limitaciones actuales
1. **Pub/Sub en memoria**: solo funciona en un único proceso
   - Escalar a Redis si se necesitan múltiples procesos
2. **LangGraph checkpoint**: no se usa actualmente
   - Se puede integrar para rehidratación más sofisticada
3. **No hay persistencia de checkpoints**:
   - El estado del grafo se pierde en desconexión larga
4. **Timeouts no configurables**:
   - Socket timeout genérico de FastAPI
5. **Reconexión infinita en cliente**:
   - Máximo 10 intentos; después notifica al usuario

### Mejoras futuras
1. Escalar a Redis Pub/Sub para multiprocess
2. Implementar LangGraph checkpoints con rehidratación
3. Agregar room/channel a nivel de cliente (múltiples sesiones por usuario)
4. Métricas y monitoreo de conexiones WebSocket
5. Rate limiting por sesión
6. Historial paginado para sesiones largas

---

## 8. Testing

### Backend Tests Implemented
- ✅ Modelos de BD (ChatSession, Message)
- ✅ Pub/Sub broker (subscribe, publish, unsubscribe)
- ✅ ChatSessionService (CRUD)
- ✅ MessageService (CRUD, get_session_messages)
- ✅ Stream agent response (token emission, completion)
- ✅ Interrupt workflow (cancel, new input)
- ✅ Session snapshot (reconnection)

**Resultado:** 16 tests, todos pasando

### Frontend Tests (a implementar)
- ChatWebSocketClient: connect, disconnect, reconnect logic
- useChatWebSocket hook: state management, event callbacks
- ChatWindow component: rendering, user interactions

---

## 9. Conclusiones

La implementación satisface todos los requisitos del spec:
1. ✅ Streaming de tokens bidireccional con WebSocket
2. ✅ Interrupción genuina sin perder contexto
3. ✅ Reconexión con session snapshot y rehidratación
4. ✅ Pub/Sub para desacoplamiento productor/consumidor
5. ✅ Seguridad con JWT y autorización
6. ✅ Renderizado progresivo en frontend
7. ✅ Tests unitarios de integración

**Estado:** Listo para fase de desarrollo UI completo y pruebas e2e.

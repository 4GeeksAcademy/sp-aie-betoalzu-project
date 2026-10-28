# WebSocket Real-Time Chat Streaming (Nexova Parte 2)

Implementación completa de streaming de chat en tiempo real con WebSocket bidireccional para Nexova Solutions.

## 📋 Características

### Backend (FastAPI)
- ✅ Endpoint WebSocket `/ws/chat/{session_id}`
- ✅ Autenticación con JWT (query param o primer frame)
- ✅ Streaming de tokens token-por-token
- ✅ Interrupción genuina del usuario (aborta stream, no pausa grafo)
- ✅ Reconexión automática con session snapshot
- ✅ Pub/Sub broker en memoria para desacoplamiento
- ✅ Persistencia en SQLModel (PostgreSQL/SQLite)

### Frontend (React/TypeScript)
- ✅ Cliente WebSocket con TypeScript
- ✅ Hook React `useChatWebSocket` para integración simple
- ✅ Renderizado progresivo de tokens
- ✅ Botón de interrupción visible durante generación
- ✅ Reconexión automática con backoff exponencial
- ✅ Componente visual ChatWindow

### Testing
- ✅ 16 tests unitarios (BD, Pub/Sub, Services)
- ✅ Tests de integración (flujos completos)
- ✅ Cobertura de casos de uso principales

## 🚀 Inicio Rápido

### Backend

1. **Instalar dependencias:**
   ```bash
   pip install -r services/requirements.txt
   ```

2. **Inicializar BD (si es necesario):**
   ```bash
   PYTHONPATH=. python -c "from services.database import init_db; init_db()"
   ```

3. **Arrancar servidor:**
   ```bash
   python server.py
   # o con uvicorn:
   uvicorn server:app --reload --host 0.0.0.0 --port 8000
   ```

   El servidor inicia automáticamente:
   - Inicialización de BD (SQLModel tables)
   - Agente de soporte
   - Rutas WebSocket en `/ws/chat/{session_id}`

### Frontend

1. **Arrancar Next.js dev server:**
   ```bash
   cd uis/backoffice
   npm run dev
   ```

2. **Acceder al chat:**
   - Navegar a http://localhost:3000
   - Autenticarse (si es necesario)
   - Ir a `/chat` o `/chat?sessionId=XXX`

## 📡 Protocolo WebSocket

### Conexión
```
WebSocket wss://host/ws/chat/{session_id}?token={JWT}

Handshake:
1. Cliente → Backend: Conexión con JWT válido
2. Backend → Cliente: Validación + session_snapshot
3. Ambas direcciones abiertas para eventos
```

### Eventos desde Cliente
```json
{
  "event": "user_message",
  "data": {
    "session_id": "chat_001",
    "text": "¿Cuál es tu disponibilidad?"
  }
}
```

```json
{
  "event": "interrupt_requested",
  "data": {
    "session_id": "chat_001",
    "new_input": "Espera, quería preguntar sobre..."
  }
}
```

### Eventos desde Backend
```json
{
  "event": "session_snapshot",
  "data": {
    "session_id": "chat_001",
    "checkpoint_id": null,
    "messages": [
      {
        "message_id": "msg_123",
        "sender": "user",
        "text": "Hola",
        "status": "completed"
      }
    ]
  }
}
```

```json
{
  "event": "token_chunk",
  "data": {
    "session_id": "chat_001",
    "message_id": "msg_124",
    "token": "Claro",
    "sequence": 1
  }
}
```

```json
{
  "event": "generation_completed",
  "data": {
    "session_id": "chat_001",
    "message_id": "msg_124",
    "status": "completed",
    "total_tokens": 42
  }
}
```

```json
{
  "event": "generation_interrupted",
  "data": {
    "session_id": "chat_001",
    "message_id": "msg_124",
    "status": "interrupted",
    "tokens_shown": 15
  }
}
```

## 🛠️ Desarrollo

### Ejecutar Tests
```bash
# Solo tests del chat
PYTHONPATH=. pytest tests/test_chat_websocket_p1.py tests/test_chat_websocket_p2.py -v

# Con cobertura
PYTHONPATH=. pytest tests/test_chat_websocket_p1.py tests/test_chat_websocket_p2.py --cov=services.chat_service --cov=services.pubsub
```

### Estructura del Proyecto
```
services/
├── models.py                    # ChatSession, Message models
├── pubsub.py                    # Pub/Sub broker
├── chat_service.py              # Services para BD
├── agent_chat_service.py        # Integración con agente
├── api/chat/
│   ├── __init__.py
│   └── routes.py                # WebSocket endpoint

uis/backoffice/
├── services/chat-ws.ts          # Cliente WebSocket
├── components/ChatWindow.tsx    # Componente visual
└── app/chat/page.tsx            # Página de chat

tests/
├── test_chat_websocket_p1.py    # Tests Paso 1 (modelos, pubsub, services)
└── test_chat_websocket_p2.py    # Tests Paso 2 (streaming, interruption)

docs/
└── websocket-chat-design.md     # Documentación de diseño
```

### Linting y Type Checking

**Backend:**
```bash
# Python linting (ruff)
cd services && ruff check .

# Type checking
cd services && mypy . (si está configurado)
```

**Frontend:**
```bash
cd uis/backoffice
npm run lint
npm run build  # valida TypeScript
```

## 🔐 Seguridad

### Autenticación
- JWT obligatorio en query string o datos
- Validación de firma y expiración
- Extrae `user_id`, `client_id` del token

### Autorización
- Solo el propietario de la sesión puede acceder
- Validación en handshake WebSocket
- Rechaza con 403 si no es el propietario

### Validación de Entrada
- `session_id`: debe existir en BD
- `text`: 1-10000 caracteres
- JWT: firma válida, expiración futura

## 📊 Monitoreo y Debugging

### Logs del Backend
```bash
# Habilitar logs detallados de SQL
export SQLALCHEMY_ECHO=true
python server.py
```

### Logs del WebSocket
El cliente WebSocket emite logs en la consola del navegador:
```javascript
// Chrome DevTools → Console
// Verás:
// - Conexión establecida
// - Tokens recibidos
// - Reconexiones (con backoff)
// - Errores y desconexiones
```

### Inspeccionar WebSocket (Chrome DevTools)
1. F12 → Network → WS filter
2. Selecciona la conexión `/ws/chat/...`
3. Pestaña Messages muestra todos los eventos enviados/recibidos

## 🚧 Próximas Mejoras

- [ ] Escalar Pub/Sub a Redis para multiprocess
- [ ] Integrar LangGraph checkpoints
- [ ] Múltiples canales por usuario
- [ ] Historial paginado
- [ ] Rate limiting
- [ ] Métricas y monitoreo
- [ ] Tests e2e con Playwright

## 📚 Referencias

- [Especificación Completa](./specs/websocket-realtime-chat-streaming-pt2.md)
- [Documentación de Diseño](./docs/websocket-chat-design.md)
- [WebSocket MDN](https://developer.mozilla.org/es/docs/Web/API/WebSocket)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/en/docs/advanced/websockets/)

## 📄 Licencia

Parte del proyecto Nexova Solutions.

---

**Versión:** 1.0  
**Fecha:** 2026-10-28  
**Status:** ✅ Implementado y testeado

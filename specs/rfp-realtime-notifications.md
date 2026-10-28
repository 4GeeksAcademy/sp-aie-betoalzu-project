# Especificacion: notificaciones SSE de tickets RFP

## Objetivo y alcance

Notificar al equipo de Marcos Ibáñez, Sales Director, en el backoffice cuando una nueva RFP válida se registra como ticket y comienza su procesamiento. El dashboard debe actualizarse sin recarga manual y recuperarse de interrupciones de red.

Esta entrega es una capa de comunicación en tiempo real para el flujo RFP existente. No implementa ni invoca modelos, agentes, clasificación o generación de propuestas; tampoco cambia el pipeline, el contrato de estados ni la persistencia existentes, salvo el punto mínimo necesario para publicar la notificación.

## Fuentes de verdad

- Entidades, campos, estados y momento del evento: [`docs/brefing-real-time-system.md`](../docs/brefing-real-time-system.md).
- Reutilizar la autenticación JWT del backoffice, las convenciones de `services/` y la vista de dashboard RFP existente en `uis/`. No crear una API o mecanismo de autenticación paralelo.
- En caso de diferencias con otras especificaciones del pipeline RFP, esta fase debe conservar los nombres y valores del briefing en las notificaciones; en particular, el estado inicial de este contrato es `analyzing`.

## Contrato de dominio

La notificación se produce exactamente cuando el sistema confirma el registro de un ticket nuevo para una RFP válida y su estado inicial es `analyzing`. No emitirla al recibir un documento aún no clasificado, al reintentar un ticket existente ni por cambios posteriores de estado.

Usar estas entidades y nombres de campo sin traducciones ni alias:

- **Ticket**: `ticket_id`, `rfp_id`, `status`.
- **Estados válidos**: `analyzing`, `intake_complete`, `drafting`, `under_evaluation`, `waiting_for_approval`, `done`, `discarded`.
- **RFP metadata**: `client_name`, `client_hq` (`Spain` o `Miami`), `services_requested`, `scope`, `deadline`, `budget_range`, `departments_needed`.

El evento de creación debe incluir al menos este payload plano, serializado como JSON en `data:`:

```json
{
  "ticket_id": "tkt_0341",
  "rfp_id": "rfp_0127",
  "client_name": "NubeSoft",
  "client_hq": "Miami",
  "services_requested": ["soporte"],
  "status": "analyzing",
  "created_at": "2026-07-24T14:32:00Z"
}
```

`created_at` debe ser la fecha de creación del ticket en formato ISO 8601. No incluir contenido del documento, secciones por departamento ni un sobre anidado como `{"event": ..., "data": ...}`. Si se agregan metadatos opcionales, conservar exactamente los nombres del briefing y no sustituir campos ausentes por datos inventados.

## Backend (`services/`)

- Añadir un endpoint SSE al servidor/router existente, siguiendo sus convenciones de rutas. El endpoint autentica cada conexión con el mismo JWT y dependencia de usuario que protege el backoffice. Las conexiones anónimas o con token inválido reciben el error HTTP de autenticación existente y nunca reciben eventos.
- Usar `Content-Type: text/event-stream`, mantener la conexión abierta, enviar frames válidos terminados en una línea en blanco y emitir comentarios de keep-alive periódicos. Deshabilitar el almacenamiento en caché y el buffering de proxy para la respuesta cuando la infraestructura lo permita.
- Emitir el frame nombrado `rfp_ticket_created`; su `data:` contiene el JSON plano definido arriba. No usar `message` como único tipo de evento.
- Publicar solo después de confirmar el alta del ticket en el sistema existente. Evitar una notificación de un ticket que no pueda consultarse después. El fallo o desconexión de un consumidor no debe bloquear ni revertir el procesamiento de RFP.
- Aislar el ciclo de vida de cada conexión: al desconectarse el cliente, cancelar su iterador/suscripción y liberar recursos. No crear una conexión de base de datos o tarea productora sin límite por consumidor.
- El stream no debe ejecutar el pipeline ni llamar a ningún modelo/agente. Debe recibir el evento desde el punto existente que registra la RFP o desde una abstracción de publicación acotada.

## Frontend (`uis/`)

- Integrar el consumo en el dashboard RFP existente. Usar `fetch` con `Authorization: Bearer <JWT>` y leer el cuerpo como `ReadableStream`; no depender de `EventSource`, que no permite enviar de forma directa el header de autenticación requerido.
- Implementar un parser incremental SSE que soporte frames divididos entre chunks, múltiples líneas `data:`, el nombre `event:` y comentarios keep-alive. Ignorar comentarios como eventos de negocio y validar el JSON antes de actualizar la vista.
- Mostrar una notificación visualmente distinguible con, como mínimo, `ticket_id`, `client_name` y el estado inicial. Insertar o actualizar el ticket localmente; no volver a descargar todos los datos por cada evento.
- Ante errores de red o cierre inesperado, reintentar automáticamente con backoff exponencial progresivo, un máximo configurable y jitter. Reiniciar el contador tras una conexión estable; detener y limpiar la lectura al desmontar la vista o cerrar sesión.
- Recuperación elegida: al establecer cada conexión (incluida una reconexión), abrir primero el stream y después volver a consultar la lista de tickets usando el endpoint existente. Fusionar la respuesta con los eventos que lleguen durante la consulta. Así se recuperan los tickets creados durante la desconexión y se cierra la ventana entre el refetch y la suscripción. Si no existe una consulta de lista adecuada, extender de forma mínima el API RFP existente, sin añadir un servicio paralelo.
- Deduplicar por `ticket_id` en la lista y en las notificaciones visibles; una llegada por SSE y el mismo ticket devuelto por el refetch deben producir una sola entrada/aviso. La recuperación no debe cambiar estados válidos ni duplicar el trabajo del pipeline.

## Pruebas y criterios de aceptación

### Backend

- Probar el endpoint HTTP real con un cliente de pruebas: `Content-Type` contiene `text/event-stream`; el cuerpo en wire incluye `event: rfp_ticket_created` y un `data:` JSON plano con los campos y valores del contrato (`ticket_id`, `rfp_id`, `client_name`, `client_hq`, `services_requested`, `status`, `created_at`). No basta probar un diccionario desconectado del framing SSE.
- Verificar que la creación de un ticket nuevo en `analyzing` publica una vez y que reintentos, tickets existentes o transiciones posteriores no generan falsos eventos.
- Verificar que una petición sin JWT o con JWT inválido no recibe el stream, y que un JWT válido puede conectarse. Usar los fixtures/utilidades de auth existentes.
- Comprobar el frame keep-alive y el cierre/limpieza de la suscripción al desconectar si la implementación ofrece un punto de prueba determinista.

### Frontend y recuperación

- Probar o documentar una verificación manual reproducible: recibir un ticket en vivo, interrumpir la red, crear uno o más tickets durante la caída y restaurar la conexión. Confirmar que ocurre el reintento con backoff, que los tickets aparecen tras el refetch y que no hay duplicados por `ticket_id`.
- Verificar el parser ante chunks parciales y el evento nombrado, y que un payload malformado no rompe la lectura de eventos posteriores.
- Confirmar que cada evento actualiza solo la entrada/notificación correspondiente y no dispara una recarga completa de datos.
- Mantener las pruebas aisladas de modelos/agentes y proveedores externos: no se invoca ningún componente de IA en esta entrega.

## Decisiones de diseño que deben documentarse en el PR

- **Conexiones concurrentes**: cada navegador tiene una conexión lógica independiente y solo recibe eventos mientras está autorizado. Explicar cómo se distribuye la publicación a todos los consumidores y qué límite/medida de capacidad aplica. Para una sola instancia puede bastar el mecanismo local existente; con múltiples workers o unas 50 conexiones simultáneas, valorar un broker/pub-sub compartido y límites/observabilidad, en lugar de asumir que memoria de proceso se comparte.
- **Recuperación y deduplicación**: se adopta refetch de la lista al abrir cada stream, también al reconectar. Identificar el endpoint existente utilizado y explicar la fusión/deduplicación por `ticket_id`.
- **SSE frente a WebSockets**: SSE es apropiado porque el flujo requerido es unidireccional (servidor a dashboard) sobre HTTP y la escritura/autorización continúa por las APIs existentes. Reconsiderar WebSockets si el mismo canal debe transportar acciones bidireccionales interactivas, no solo notificaciones.

## Criterio de salida

La tarea está completa cuando el dashboard autenticado muestra automáticamente cada nuevo ticket RFP en `analyzing`, con el payload de dominio correcto; una interrupción de red activa la reconexión y recupera tickets sin duplicarlos; las pruebas cubren autenticación y framing SSE real; y el cambio no ejecuta modelos ni agentes.
# Plan de Telemetría — Nexova

> **Versión:** 1.0  
> **Fecha:** 2026-08-31  
> **Responsable:** Equipo de Ingeniería — Nexova  
> **Sistema objetivo:** Sistema de Gestión de Inventario de Material de Formación e Incorporación

---

## Fase 1 — Catálogo Exhaustivo de Oportunidades de Datos

### 1.1 Métricas Obligatorias (del CONTEXT de Nexova)

Estas métricas son el **piso mínimo** exigido por el negocio. Las cinco deben instrumentarse sin excepción.

| # | `event_type` | Clasificación |
|---|-------------|---------------|
| M1 | `inbound_order_created` | **Obligatorio** |
| M2 | `outbound_order_created` | **Obligatorio** |
| M3 | `stock_threshold_triggered` | **Obligatorio** |
| M4 | `direct_stock_edit_rejected` | **Obligatorio** |
| M5 | `kit_cost_variance_detected` | **Obligatorio** |

#### M1 — `inbound_order_created`

> **Capturamos `inbound_order_created` porque necesitamos saber** cuánto material se produce o compra, para qué programa, con qué costo y en qué oficina, **lo que nos permite** planificar la producción de material según la demanda esperada de matrículas (Elena, L&D).

- **Categoría:** Negocio / Inventario
- **Se dispara cuando:** Llega un nuevo lote de material de formación o de incorporación desde un proveedor.

#### M2 — `outbound_order_created`

> **Capturamos `outbound_order_created` porque necesitamos saber** qué programas consumen más material y a qué ritmo por oficina, **lo que nos permite** anticipar necesidades de reposición antes de una ola grande de matrículas (Elena, L&D).

- **Categoría:** Negocio / Inventario
- **Se dispara cuando:** Se entrega un kit o certificado a un cliente, candidato, consultor o agente.

#### M3 — `stock_threshold_triggered`

> **Capturamos `stock_threshold_triggered` porque necesitamos saber** con qué frecuencia un programa se queda sin material disponible y en qué oficina, **lo que nos permite** ajustar el umbral mínimo o acelerar la reimpresión/reproducción de ese material (Elena, L&D).

- **Categoría:** Negocio / Inventario
- **Se dispara cuando:** El stock de un ítem cae por debajo del mínimo configurado.

#### M4 — `direct_stock_edit_rejected`

> **Capturamos `direct_stock_edit_rejected` porque necesitamos saber** si el personal intenta saltarse el control de trazabilidad del material modificando el stock directamente, **lo que nos permite** reforzar capacitación o ajustar permisos en la oficina donde esto ocurre con más frecuencia (Patricia, RRHH).

- **Categoría:** Negocio / Inventario
- **Se dispara cuando:** Un usuario intenta modificar el stock directamente (fuera de una orden) y el sistema lo rechaza.

#### M5 — `kit_cost_variance_detected`

> **Capturamos `kit_cost_variance_detected` porque necesitamos saber** cuándo un proveedor de material sube precios de forma anómala respecto al histórico del mismo material, **lo que nos permite** alertar a Elena y a Laura para renegociar o buscar un proveedor alterno.

- **Categoría:** Negocio / Inventario
- **Se dispara cuando:** El costo unitario de una orden de entrada varía más de un umbral configurado (ej. 10 %) respecto al histórico del mismo material/proveedor.

---

### 1.2 Oportunidades Identificadas

Complementamos el piso obligatorio con un catálogo amplio que explora **autenticación, rendimiento, errores, navegación y más eventos de negocio**. Cada oportunidad está justificada con una hipótesis y una decisión concreta.

#### Categoría: Autenticación

##### O1 — `login_attempted`

> **Capturamos `login_attempted` porque necesitamos saber** con qué frecuencia y desde qué contexto los operadores inician sesión en el sistema, **lo que nos permite** detectar patrones de acceso anómalos que puedan indicar un uso no autorizado (Roberto, Soporte Técnico).

- **Se dispara cuando:** Un usuario intenta autenticarse, independientemente del resultado.
- **Clasificación:** Oportunidad identificada

##### O2 — `login_failed`

> **Capturamos `login_failed` porque necesitamos saber** cuántos intentos fallidos de autenticación ocurren, por usuario y por oficina, **lo que nos permite** detectar posibles ataques de fuerza bruta o problemas de credenciales (Roberto, Soporte Técnico).

- **Se dispara cuando:** Un intento de autenticación falla por credenciales inválidas, cuenta bloqueada u otro motivo.
- **Clasificación:** Oportunidad identificada

##### O3 — `session_expired`

> **Capturamos `session_expired` porque necesitamos saber** con qué frecuencia las sesiones de los operadores expiran mientras están realizando tareas activas, **lo que nos permite** ajustar la política de expiración de sesión o implementar mecanismos de reconexión sin pérdida de datos (Roberto, Soporte Técnico).

- **Se dispara cuando:** Una sesión de usuario expira por inactividad o por superar el tiempo máximo de sesión.
- **Clasificación:** Oportunidad identificada

##### O4 — `password_reset_requested`

> **Capturamos `password_reset_requested` porque necesitamos saber** con qué frecuencia los operadores solicitan restablecimiento de contraseña, **lo que nos permite** detectar problemas de usabilidad con la autenticación o posibles cuentas comprometidas (Roberto, Soporte Técnico).

- **Se dispara cuando:** Un usuario solicita un restablecimiento de contraseña.
- **Clasificación:** Oportunidad identificada

---

#### Categoría: Rendimiento

##### O5 — `api_latency_recorded`

> **Capturamos `api_latency_recorded` porque necesitamos saber** qué endpoints del sistema de inventario presentan mayor latencia y en qué condiciones de carga, **lo que nos permite** priorizar optimizaciones de rendimiento y mantener una experiencia fluida para los operadores (Equipo de Ingeniería).

- **Se dispara cuando:** Se completa una petición a un endpoint del backoffice y se mide su tiempo de respuesta.
- **Clasificación:** Oportunidad identificada

##### O6 — `page_load_timed`

> **Capturamos `page_load_timed` porque necesitamos saber** qué secciones del backoffice cargan más lentamente para los operadores, **lo que nos permite** identificar cuellos de botella en la interfaz y optimizar los recursos frontend (Equipo de Ingeniería).

- **Se dispara cuando:** Una página del backoffice completa su carga en el navegador del usuario.
- **Clasificación:** Oportunidad identificada

---

#### Categoría: Errores

##### O7 — `frontend_error_captured`

> **Capturamos `frontend_error_captured` porque necesitamos saber** qué errores no capturados ocurren en el frontend del backoffice, en qué sección y con qué frecuencia, **lo que nos permite** corregir bugs antes de que afecten la productividad de los operadores o corrompan datos (Equipo de Ingeniería).

- **Se dispara cuando:** Se produce un error no capturado (JavaScript exception, promise rejection, error de red) en el frontend.
- **Clasificación:** Oportunidad identificada

##### O8 — `api_error_returned`

> **Capturamos `api_error_returned` porque necesitamos saber** con qué frecuencia los endpoints de la API devuelven errores (4xx/5xx), para qué endpoint y con qué código, **lo que nos permite** detectar problemas en los servicios backend antes de que escalen a caídas completas (Equipo de Ingeniería).

- **Se dispara cuando:** Un endpoint de la API del sistema de inventario devuelve un código de error HTTP.
- **Clasificación:** Oportunidad identificada

---

#### Categoría: Navegación / UX

##### O9 — `page_viewed`

> **Capturamos `page_viewed` porque necesitamos saber** qué secciones del backoffice visitan más los operadores y en qué orden, **lo que nos permite** optimizar la navegación, priorizar mejoras donde más se usa y detectar flujos infrautilizados (Producto).

- **Se dispara cuando:** Un operador navega a una sección o vista del backoffice.
- **Clasificación:** Oportunidad identificada

##### O10 — `flow_abandoned`

> **Capturamos `flow_abandoned` porque necesitamos saber** en qué paso del flujo de creación de órdenes (entrada o salida) los operadores abandonan el proceso sin completar, **lo que nos permite** simplificar pasos, mejorar la usabilidad o detectar bloqueantes técnicos en puntos concretos del wizard (Producto).

- **Se dispara cuando:** Un usuario inicia un flujo multi-paso (creación de orden, registro de producto) pero lo abandona antes del paso final de confirmación.
- **Clasificación:** Oportunidad identificada

---

#### Categoría: Negocio / Inventario (ampliación)

##### O11 — `inbound_order_cancelled`

> **Capturamos `inbound_order_cancelled` porque necesitamos saber** con qué frecuencia y por qué motivo se cancelan órdenes de entrada, **lo que nos permite** identificar problemas recurrentes con proveedores o errores en la creación de pedidos que requieren formación adicional (Elena, L&D).

- **Se dispara cuando:** Una orden de entrada se cancela antes de completarse.
- **Clasificación:** Oportunidad identificada

##### O12 — `outbound_order_cancelled`

> **Capturamos `outbound_order_cancelled` porque necesitamos saber** con qué frecuencia y por qué motivo se cancelan órdenes de salida, **lo que nos permite** identificar problemas de disponibilidad de material o errores en las entregas que afectan a clientes y candidatos (Elena, L&D).

- **Se dispara cuando:** Una orden de salida se cancela antes de completarse.
- **Clasificación:** Oportunidad identificada

##### O13 — `product_low_stock_warning`

> **Capturamos `product_low_stock_warning` porque necesitamos saber** qué productos están cerca del umbral mínimo configurado sin haberlo alcanzado aún, **lo que nos permite** reabastecer proactivamente antes de que se active el `stock_threshold_triggered`, reduciendo roturas de stock (Elena, L&D).

- **Se dispara cuando:** El stock de un producto cae al 150 % del umbral mínimo configurado (zona de precaución).
- **Clasificación:** Oportunidad identificada

##### O14 — `report_generated`

> **Capturamos `report_generated` porque necesitamos saber** con qué frecuencia se generan reportes, qué tipo y qué filtros usan Elena y Laura, **lo que nos permite** medir la adopción de la funcionalidad analítica y optimizar los reportes más solicitados (Producto).

- **Se dispara cuando:** Un usuario genera un reporte desde el módulo de informes del backoffice.
- **Clasificación:** Oportunidad identificada

##### O15 — `supplier_order_delayed`

> **Capturamos `supplier_order_delayed` porque necesitamos saber** qué proveedores están incumpliendo los plazos de entrega esperados, **lo que nos permite** activar alertas tempranas con los proveedores o diversificar las fuentes de suministro antes de que afecte a la disponibilidad de material (Elena, L&D).

- **Se dispara cuando:** Una orden de entrada no se completa dentro del plazo estimado de entrega del proveedor.
- **Clasificación:** Oportunidad identificada

---

### 1.3 Mapa del flujo de gestión de inventario — Puntos de instrumentación

A continuación se mapea el flujo completo desde que un usuario autenticado accede al sistema hasta que completa una orden de entrada o salida, señalando los **puntos de instrumentación**:

```
                     ┌─────────────────────┐
                     │  Usuario autenticado │
                     │  inicia sesión       │
                     └──────────┬──────────┘
                                │
                     ┌──────────▼──────────┐
                ┌────┤  Dashboard principal │◄──── login_attempted / login_failed
                │    │  (resumen inventario) │      session_expired
                │    └──────────┬──────────┘
                │               │
                │    ┌──────────▼──────────┐
                │    │  Sección inventario  │◄──── page_viewed
                │    │  (lista de productos)│      page_load_timed
                │    └──────────┬──────────┘
                │               │
        ┌───────┴───────┐       │
        │               │       │
   ┌────▼────┐    ┌─────▼─────┐│
   │ Entrada │    │   Salida   ││
   │ (nueva  │    │  (nueva   ││
   │ orden)  │    │   orden)  ││
   └────┬────┘    └─────┬─────┘│
        │               │      │
   ┌────▼────┐    ┌─────▼─────┐│
   │ Wizard  │    │   Wizard  ││◄──── flow_abandoned
   │ entrada │    │   salida  ││      (en cualquier paso)
   └────┬────┘    └─────┬─────┘│
        │               │      │
   ┌────▼────┐    ┌─────▼─────┐│
   │ Confirm │    │  Confirm  ││
   │ entrada │    │  salida   ││
   └────┬────┘    └─────┬─────┘│
        │               │      │
   ┌────▼────────────────▼──┐  │
   │   stock_threshold_      │  │
   │   triggered (automático)│  │
   └────▲────────────────▲──┘  │
        │               │      │
   ┌────▼────┐    ┌─────▼─────┐│
   │ inbound_│    │ outbound_ ││
   │ order_  │    │ order_    ││
   │ created │    │ created   ││
   └─────────┘    └───────────┘│
                               │
   ┌────────────────────────────┘
   │
   ├── direct_stock_edit_rejected (cualquier intento directo en el dashboard o lista)
   ├── kit_cost_variance_detected (al comparar costo de inbound_order con histórico)
   ├── product_low_stock_warning (cuando stock cae a 150 % del umbral)
   └── supplier_order_delayed (si plazo estimado superado)
```

**Puntos de instrumentación identificados (mínimo 5):**

| # | Punto | Evento asociado | Momento |
|---|-------|----------------|---------|
| 1 | Autenticación del usuario | `login_attempted`, `login_failed`, `session_expired` | Al acceder al sistema |
| 2 | Visualización del inventario | `page_viewed`, `page_load_timed` | Al cargar la sección de inventario |
| 3 | Creación de orden de entrada | `inbound_order_created` | Al confirmar una orden de entrada |
| 4 | Creación de orden de salida | `outbound_order_created` | Al confirmar una orden de salida |
| 5 | Validación de umbral de stock | `stock_threshold_triggered` | Después de cada orden que reduce stock |
| 6 | Intento de modificación directa rechazada | `direct_stock_edit_rejected` | Al intentar editar stock fuera de orden |
| 7 | Validación de costo respecto a histórico | `kit_cost_variance_detected` | Al crear/confirmar orden de entrada |

---

### 1.4 Resumen del catálogo completo

| # | `event_type` | Categoría | Clasificación |
|---|-------------|-----------|---------------|
| M1 | `inbound_order_created` | Negocio / Inventario | **Obligatorio** |
| M2 | `outbound_order_created` | Negocio / Inventario | **Obligatorio** |
| M3 | `stock_threshold_triggered` | Negocio / Inventario | **Obligatorio** |
| M4 | `direct_stock_edit_rejected` | Negocio / Inventario | **Obligatorio** |
| M5 | `kit_cost_variance_detected` | Negocio / Inventario | **Obligatorio** |
| O1 | `login_attempted` | Autenticación | Oportunidad identificada |
| O2 | `login_failed` | Autenticación | Oportunidad identificada |
| O3 | `session_expired` | Autenticación | Oportunidad identificada |
| O4 | `password_reset_requested` | Autenticación | Oportunidad identificada |
| O5 | `api_latency_recorded` | Rendimiento | Oportunidad identificada |
| O6 | `page_load_timed` | Rendimiento | Oportunidad identificada |
| O7 | `frontend_error_captured` | Errores | Oportunidad identificada |
| O8 | `api_error_returned` | Errores | Oportunidad identificada |
| O9 | `page_viewed` | Navegación / UX | Oportunidad identificada |
| O10 | `flow_abandoned` | Navegación / UX | Oportunidad identificada |
| O11 | `inbound_order_cancelled` | Negocio / Inventario | Oportunidad identificada |
| O12 | `outbound_order_cancelled` | Negocio / Inventario | Oportunidad identificada |
| O13 | `product_low_stock_warning` | Negocio / Inventario | Oportunidad identificada |
| O14 | `report_generated` | Negocio / Inventario | Oportunidad identificada |
| O15 | `supplier_order_delayed` | Negocio / Inventario | Oportunidad identificada |

> Total: **20 eventos** — 5 obligatorios + 15 oportunidades identificadas, cubriendo **5 categorías** distintas (Inventario, Autenticación, Rendimiento, Errores, Navegación/UX).

---

## Fase 2 — Diseño del Event Envelope

### 2.1 Event Envelope Estándar

Todo evento de telemetría en Nexova debe ajustarse al siguiente envelope:

```json
{
  "eventId": "uuid-v4",
  "timestamp": "2026-08-31T14:30:00.000Z",
  "sessionId": "uuid-v4",
  "userId": "string",
  "event_type": "string (entidad_acción)",
  "schemaVersion": "1.0",
  "requestId": "uuid-v4",
  "properties": {}
}
```

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `eventId` | `string (UUID v4)` | ✅ | Identificador único del evento. Generado en el momento de emisión. |
| `timestamp` | `string (ISO 8601)` | ✅ | Marca de tiempo del momento en que ocurre el evento, en UTC. |
| `sessionId` | `string (UUID v4)` | ✅ | Identificador de la sesión del usuario en la que ocurre el evento. |
| `userId` | `string` | ✅ | Identificador del usuario que realizó la acción. Puede ser un ID interno de Nexova (nunca nombre real ni email). |
| `event_type` | `string` | ✅ | Tipo de evento, siguiendo la taxonomía `entidad_acción` (ej. `inbound_order_created`). |
| `schemaVersion` | `string` | ✅ | Versión del esquema del evento (semver). Este campo permite evolucionar los esquemas sin romper consumidores existentes. |
| `requestId` | `string (UUID v4)` | ✅ | Identificador de correlación para trazar una petición HTTP a través de todos los eventos que genera. |
| `properties` | `object` | ✅ | Payload específico del evento. Solo contiene las claves definidas en el allowlist de cada `event_type`. |

### 2.2 Esquemas de Eventos

A continuación se definen los esquemas completos de todos los eventos del catálogo. Cada evento incluye su allowlist de propiedades, tipos, obligatoriedad, descripción y manejo de datos sensibles.

---

#### Eventos de Inventario — Obligatorios

##### `inbound_order_created`

- **Descripción:** Se crea una orden de entrada de material desde un proveedor.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina destino: `valencia` o `miami`. |
| `product_id` | `string` | ✅ | Identificador único del producto. |
| `product_category` | `string` | ✅ | Categoría del producto: `training_kit`, `certification`, `onboarding_equipment`. |
| `programme_id` | `string` | ✅ | Identificador del programa de formación o certificación. |
| `quantity` | `integer` | ✅ | Cantidad de unidades recibidas. |
| `currency` | `string` | ✅ | Moneda de la operación: `EUR` para Valencia, `USD` para Miami. |
| `unit_cost` | `number` | ✅ | Coste unitario del producto en la moneda de la oficina. |
| `supplier_id` | `string` | ✅ | Identificador del proveedor. |
| `inbound_order_id` | `string` | ✅ | Identificador único de la orden de entrada. |

---

##### `outbound_order_created`

- **Descripción:** Se entrega un kit o certificado a un destinatario (cliente, candidato, consultor, agente).
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII. No se incluyen nombres de destinatarios — solo el identificador del programa.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina origen: `valencia` o `miami`. |
| `product_id` | `string` | ✅ | Identificador único del producto entregado. |
| `product_category` | `string` | ✅ | Categoría del producto: `training_kit`, `certification`, `onboarding_equipment`. |
| `programme_id` | `string` | ✅ | Identificador del programa asociado. |
| `quantity` | `integer` | ✅ | Cantidad de unidades entregadas. |
| `currency` | `string` | ✅ | Moneda: `EUR` o `USD`. |
| `outbound_order_id` | `string` | ✅ | Identificador único de la orden de salida. |
| `recipient_type` | `string` | ✅ | Tipo de destinatario: `client`, `candidate`, `consultant`, `support_agent`. |

---

##### `stock_threshold_triggered`

- **Descripción:** El stock de un producto cae por debajo del umbral mínimo configurado.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina donde se activa el umbral: `valencia` o `miami`. |
| `product_id` | `string` | ✅ | Identificador del producto. |
| `product_category` | `string` | ✅ | Categoría del producto. |
| `programme_id` | `string` | ✅ | Programa al que pertenece el producto. |
| `current_stock` | `integer` | ✅ | Stock actual después de la operación que activó el umbral. |
| `minimum_threshold` | `integer` | ✅ | Umbral mínimo configurado para este producto en esta oficina. |
| `quantity` | `integer` | ✅ | Cantidad de la operación que causó la activación. |
| `currency` | `string` | ✅ | Moneda de la oficina. |

---

##### `direct_stock_edit_rejected`

- **Descripción:** Un usuario intenta modificar el stock directamente (sin pasar por una orden) y el sistema lo rechaza.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII. `user_id` en el envelope identifica al usuario, pero no se incluye su nombre ni email.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina desde la que se intentó la edición: `valencia` o `miami`. |
| `product_id` | `string` | ✅ | Identificador del producto cuyo stock se intentó modificar. |
| `product_category` | `string` | ✅ | Categoría del producto. |
| `programme_id` | `string` | ✅ | Programa al que pertenece el producto. |
| `quantity` | `integer` | ✅ | Cantidad que se intentó modificar. |
| `currency` | `string` | ✅ | Moneda de la oficina. |
| `attempted_action` | `string` | ✅ | Acción que se intentó: `increase_stock`, `decrease_stock`, `set_stock`. |
| `rejection_reason` | `string` | ✅ | Motivo del rechazo: `direct_edit_not_allowed`, `insufficient_permissions`. |

---

##### `kit_cost_variance_detected`

- **Descripción:** El costo unitario de una orden de entrada varía más de un umbral configurable respecto al histórico del mismo material/proveedor.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina de la orden: `valencia` o `miami`. |
| `product_id` | `string` | ✅ | Identificador del producto. |
| `product_category` | `string` | ✅ | Categoría del producto. |
| `programme_id` | `string` | ✅ | Programa al que pertenece el producto. |
| `quantity` | `integer` | ✅ | Cantidad de la orden. |
| `currency` | `string` | ✅ | Moneda. |
| `expected_unit_cost` | `number` | ✅ | Coste unitario histórico esperado. |
| `actual_unit_cost` | `number` | ✅ | Coste unitario real de la orden actual. |
| `variance_percentage` | `number` | ✅ | Porcentaje de variación ((actual - esperado) / esperado × 100). |
| `threshold_percentage` | `number` | ✅ | Umbral de variación configurado que disparó la alerta. |
| `supplier_id` | `string` | ✅ | Identificador del proveedor. |
| `inbound_order_id` | `string` | ✅ | Identificador de la orden de entrada asociada. |

---

#### Eventos de Autenticación

##### `login_attempted`

- **Descripción:** Un usuario intenta autenticarse en el sistema.
- **Categoría:** Autenticación
- **Datos sensibles:** No se incluye la contraseña ni datos de la credencial. `userId` puede ser desconocido si el intento falla antes de identificar al usuario.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `login_method` | `string` | ✅ | Método de autenticación: `password`, `sso`, `magic_link`. |
| `ip_country` | `string` | ❌ | País de origen de la IP (anonimizado a nivel de país). No se almacena la IP completa. |
| `office_hint` | `string` | ❌ | Posible oficina inferida por IP, si está disponible: `valencia`, `miami` o `unknown`. |

**Sanitización:** La IP origen se anonimiza truncándola a `/24` (IPv4) o `/48` (IPv6) antes de inferir el país. No se almacena la IP cruda.

---

##### `login_failed`

- **Descripción:** Un intento de autenticación falla por credenciales inválidas, cuenta bloqueada u otro motivo.
- **Categoría:** Autenticación
- **Datos sensibles:** No se almacena la contraseña ni datos biométricos. `userId` puede estar ausente si el usuario no existe.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `failure_reason` | `string` | ✅ | Motivo del fallo: `invalid_credentials`, `account_locked`, `account_disabled`, `mfa_failed`, `expired_password`. |
| `attempt_count` | `integer` | ✅ | Número de intentos fallidos consecutivos para este usuario. |
| `ip_country` | `string` | ❌ | País de origen anonimizado. |
| `login_method` | `string` | ❌ | Método de autenticación intentado. |

**Sanitización:** La IP se anonimiza de la misma forma que en `login_attempted`.

---

##### `session_expired`

- **Descripción:** Una sesión de usuario expira por inactividad o por superar el tiempo máximo.
- **Categoría:** Autenticación
- **Datos sensibles:** No contiene PII adicional al `userId` del envelope.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `expiry_reason` | `string` | ✅ | Motivo: `inactivity_timeout`, `max_session_duration`, `forced_logout`. |
| `session_duration_seconds` | `integer` | ✅ | Duración total de la sesión en segundos. |
| `last_active_page` | `string` | ❌ | Última página donde el usuario estaba activo antes de la expiración (útil para evaluar pérdida de trabajo). |

---

##### `password_reset_requested`

- **Descripción:** Un usuario solicita un restablecimiento de contraseña.
- **Categoría:** Autenticación
- **Datos sensibles:** `userId` puede estar ausente si el usuario no es identificable (se solicitó con email que no existe). No se almacena el email.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `reset_method` | `string` | ✅ | Método: `email`, `sms`, `security_questions`. |
| `user_identified` | `boolean` | ✅ | Indica si el usuario fue encontrado en el sistema o la solicitud fue para un identificador inexistente. |
| `ip_country` | `string` | ❌ | País de origen anonimizado. |

**Sanitización:** La IP se anonimiza truncándola. No se almacena el email ni datos de contacto.

---

#### Eventos de Rendimiento

##### `api_latency_recorded`

- **Descripción:** Se completa una petición a un endpoint del backoffice y se mide su tiempo de respuesta.
- **Categoría:** Rendimiento
- **Datos sensibles:** `request_path` puede contener IDs. Se sanitiza reemplazando los valores de IDs con un placeholder antes de emitir.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `endpoint` | `string` | ✅ | Ruta del endpoint (plantilla, ej. `/api/products/{id}` — sin valores concretos). |
| `http_method` | `string` | ✅ | Método HTTP: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`. |
| `http_status` | `integer` | ✅ | Código de estado HTTP devuelto. |
| `latency_ms` | `integer` | ✅ | Tiempo de respuesta en milisegundos. |
| `office` | `string` | ❌ | Oficina desde la que se hizo la petición, si está disponible. |

**Sanitización:** La ruta se sanitiza sustituyendo segmentos variables (UUIDs, números) con placeholders tipo `{id}` antes de registrar.

---

##### `page_load_timed`

- **Descripción:** Una página del backoffice completa su carga en el navegador del usuario.
- **Categoría:** Rendimiento
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `page_name` | `string` | ✅ | Identificador de la página o sección (ej. `inventory_list`, `create_inbound_order`). |
| `load_time_ms` | `integer` | ✅ | Tiempo total de carga percibido por el usuario (en milisegundos). |
| `time_to_first_byte_ms` | `integer` | ❌ | Tiempo hasta el primer byte (TTFB). |
| `dom_interactive_ms` | `integer` | ❌ | Tiempo hasta que el DOM es interactivo. |
| `office` | `string` | ❌ | Oficina del usuario, si está disponible. |

---

#### Eventos de Errores

##### `frontend_error_captured`

- **Descripción:** Se produce un error no capturado en el frontend del backoffice.
- **Categoría:** Errores
- **Datos sensibles:** `error_stack` puede contener referencias a rutas internas del código. No contiene PII de usuarios.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `error_type` | `string` | ✅ | Tipo de error: `TypeError`, `ReferenceError`, `NetworkError`, `PromiseRejection`, etc. |
| `error_message` | `string` | ✅ | Mensaje del error (sanitizado, sin datos de usuario). |
| `error_stack` | `string` | ❌ | Stack trace del error (puede contener rutas internas del código — no se expone fuera del equipo de ingeniería). |
| `page_name` | `string` | ✅ | Página donde ocurrió el error. |
| `user_agent` | `string` | ❌ | User-Agent del navegador (se almacena solo el agrupado: navegador, versión, SO). |

**Sanitización:** `error_message` se inspecciona para eliminar cualquier patrón que parezca un valor de usuario (emails, números de teléfono) mediante regex. `error_stack` solo se almacena internamente y no se expone en dashboards públicos.

---

##### `api_error_returned`

- **Descripción:** Un endpoint de la API devuelve un error HTTP (4xx o 5xx).
- **Categoría:** Errores
- **Datos sensibles:** La respuesta puede contener datos de depuración. Se sanitiza el mensaje antes de emitir.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `endpoint` | `string` | ✅ | Ruta del endpoint (plantilla sanitizada, ej. `/api/orders/{id}`). |
| `http_method` | `string` | ✅ | Método HTTP. |
| `http_status` | `integer` | ✅ | Código de error HTTP (400–599). |
| `error_code` | `string` | ❌ | Código interno de error, si existe. |
| `error_message` | `string` | ❌ | Mensaje de error sanitizado (sin datos de usuario ni trazas de pila). |
| `office` | `string` | ❌ | Oficina asociada a la petición, si está disponible. |

**Sanitización:** El cuerpo de la respuesta de error se inspecciona y se extrae solo un mensaje genérico. No se almacenan trazas de pila del backend ni valores de entrada del usuario.

---

#### Eventos de Navegación / UX

##### `page_viewed`

- **Descripción:** Un operador navega a una sección o vista del backoffice.
- **Categoría:** Navegación / UX
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `page_name` | `string` | ✅ | Identificador de la página o vista visitada. |
| `previous_page` | `string` | ❌ | Página desde la que llegó el usuario (permite trazar el flujo de navegación). |
| `referrer_origin` | `string` | ❌ | Origen de la navegación: `navigation_menu`, `breadcrumb`, `direct_link`, `notification`. |
| `office` | `string` | ❌ | Oficina del usuario. |

---

##### `flow_abandoned`

- **Descripción:** Un usuario inicia un flujo multi-paso pero lo abandona antes de completar el paso final.
- **Categoría:** Navegación / UX
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `flow_type` | `string` | ✅ | Tipo de flujo: `create_inbound_order`, `create_outbound_order`, `register_product`, `generate_report`. |
| `abandoned_step` | `integer` | ✅ | Número del paso en el que se abandonó el flujo (1-indexed). |
| `total_steps` | `integer` | ✅ | Número total de pasos del flujo. |
| `time_spent_seconds` | `integer` | ❌ | Tiempo que el usuario estuvo en el flujo antes de abandonar. |
| `has_form_data` | `boolean` | ❌ | Indica si el usuario había rellenado algún campo del formulario antes de abandonar. |
| `office` | `string` | ❌ | Oficina del usuario. |

---

#### Eventos de Negocio / Inventario (ampliación)

##### `inbound_order_cancelled`

- **Descripción:** Una orden de entrada se cancela antes de completarse.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina de la orden. |
| `inbound_order_id` | `string` | ✅ | Identificador de la orden cancelada. |
| `product_id` | `string` | ✅ | Producto asociado. |
| `product_category` | `string` | ✅ | Categoría del producto. |
| `programme_id` | `string` | ✅ | Programa asociado. |
| `quantity` | `integer` | ✅ | Cantidad prevista. |
| `currency` | `string` | ✅ | Moneda. |
| `cancellation_reason` | `string` | ❌ | Motivo de la cancelación, si el usuario lo proporciona. |
| `supplier_id` | `string` | ✅ | Proveedor asociado. |

---

##### `outbound_order_cancelled`

- **Descripción:** Una orden de salida se cancela antes de completarse.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII (no se incluyen datos del destinatario).

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina de la orden. |
| `outbound_order_id` | `string` | ✅ | Identificador de la orden cancelada. |
| `product_id` | `string` | ✅ | Producto asociado. |
| `product_category` | `string` | ✅ | Categoría del producto. |
| `programme_id` | `string` | ✅ | Programa asociado. |
| `quantity` | `integer` | ✅ | Cantidad prevista. |
| `currency` | `string` | ✅ | Moneda. |
| `cancellation_reason` | `string` | ❌ | Motivo de la cancelación, si el usuario lo proporciona. |

---

##### `product_low_stock_warning`

- **Descripción:** El stock de un producto cae al 150 % del umbral mínimo configurado (zona de precaución).
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina del producto. |
| `product_id` | `string` | ✅ | Identificador del producto. |
| `product_category` | `string` | ✅ | Categoría del producto. |
| `programme_id` | `string` | ✅ | Programa asociado. |
| `current_stock` | `integer` | ✅ | Stock actual. |
| `minimum_threshold` | `integer` | ✅ | Umbral mínimo configurado. |
| `trigger_percentage` | `number` | ✅ | Porcentaje respecto al umbral que disparó la advertencia (ej. 150). |
| `currency` | `string` | ✅ | Moneda de la oficina. |

---

##### `report_generated`

- **Descripción:** Un usuario genera un reporte desde el módulo de informes.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII. Los filtros pueden incluir IDs de programas, pero no nombres de personas.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `report_type` | `string` | ✅ | Tipo de reporte: `inventory_summary`, `consumption_by_programme`, `cost_evolution`, `stock_alerts`. |
| `office_filter` | `string` | ❌ | Filtro de oficina aplicado, si lo hay: `valencia`, `miami`, `all`. |
| `programme_filter` | `string` | ❌ | Filtro de programa aplicado, si lo hay. |
| `date_range_days` | `integer` | ❌ | Rango de fechas del reporte en días. |
| `format` | `string` | ✅ | Formato de exportación: `screen`, `pdf`, `csv`. |

---

##### `supplier_order_delayed`

- **Descripción:** Una orden de entrada no se completa dentro del plazo estimado de entrega del proveedor.
- **Categoría:** Negocio / Inventario
- **Datos sensibles:** No contiene PII.

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `office` | `string` | ✅ | Oficina de la orden. |
| `supplier_id` | `string` | ✅ | Identificador del proveedor. |
| `inbound_order_id` | `string` | ✅ | Identificador de la orden de entrada retrasada. |
| `product_id` | `string` | ✅ | Producto asociado. |
| `product_category` | `string` | ✅ | Categoría del producto. |
| `programme_id` | `string` | ✅ | Programa asociado. |
| `quantity` | `integer` | ✅ | Cantidad prevista. |
| `currency` | `string` | ✅ | Moneda. |
| `estimated_delivery_days` | `integer` | ✅ | Plazo estimado en días. |
| `actual_delay_days` | `integer` | ✅ | Días de retraso acumulados. |

---

## Fase 3 — Estrategia de Entrega

### 3.1 Decisión Stream vs. Batch

Cada evento se clasifica según la **urgencia de la decisión que alimenta**, no por preferencia técnica.

| `event_type` | Canal | Justificación |
|-------------|-------|---------------|
| `inbound_order_created` | **Stream** | Elena necesita visibilidad inmediata del material que entra para planificar la distribución. Una demora en la decisión de reposición puede paralizar programas. |
| `outbound_order_created` | **Stream** | El ritmo de consumo de material se monitoriza en tiempo real para anticipar roturas de stock. Cada orden de salida resta inventario disponible a otros programas. |
| `stock_threshold_triggered` | **Stream** | Requiere atención inmediata: el material se ha agotado. Si se procesa en batch, el programa podría estar días sin stock hasta que se detecte. |
| `direct_stock_edit_rejected` | **Stream** | Patricia necesita saber en el momento si hay personal intentando saltarse los controles. Un comportamiento recurrente requiere intervención rápida. |
| `kit_cost_variance_detected` | **Batch** | La decisión de renegociar con proveedores no es urgente: se analizan tendencias semanales o mensuales. Un procesamiento en lote es suficiente. |
| `login_attempted` | **Stream** | La detección de patrones anómalos de acceso requiere monitorización en tiempo real o cuasi-real para responder ante posibles intrusiones. |
| `login_failed` | **Stream** | Múltiples fallos en periodo corto pueden indicar un ataque de fuerza bruta. Requiere alertas inmediatas. |
| `session_expired` | **Batch** | La decisión de ajustar tiempos de expiración se basa en agregados, no en eventos individuales. Procesamiento diario es suficiente. |
| `password_reset_requested` | **Batch** | El análisis de tasas de restablecimiento es una métrica de tendencia. No requiere acción inmediata. |
| `api_latency_recorded` | **Stream** (con muestreo) | La degradación del rendimiento de la API afecta a todos los operadores. Se necesita detectar picos de latencia pronto, pero se puede muestrear al 10 % en condiciones normales. |
| `page_load_timed` | **Batch** | Las decisiones de optimización de interfaz se basan en percentiles agregados. No requiere tiempo real. |
| `frontend_error_captured` | **Stream** | Los errores de frontend no capturados pueden estar bloqueando a operadores. Requieren alertas en tiempo real para respuesta rápida del equipo de ingeniería. |
| `api_error_returned` | **Stream** | Un aumento súbito de errores 5xx indica una posible caída del servicio. Requiere alertas inmediatas. |
| `page_viewed` | **Batch** | Los patrones de navegación se analizan de forma agregada (diariamente o semanalmente). No hay decisión urgente asociada. |
| `flow_abandoned` | **Batch** | La identificación de puntos de abandono en flujos requiere agregación estadística. Un evento individual no justifica una acción inmediata. |
| `inbound_order_cancelled` | **Stream** | La cancelación de una orden de entrada puede indicar un problema con un proveedor que necesita atención inmediata para evitar desabastecimiento. |
| `outbound_order_cancelled` | **Stream** | Una cancelación de salida puede afectar a un cliente o candidato. Se necesita visibilidad rápida para coordinar con el equipo. |
| `product_low_stock_warning` | **Stream** | Es una alerta preventiva que gana valor cuando se detecta pronto para reabastecer antes de llegar al umbral crítico. |
| `report_generated` | **Batch** | El uso de reportes se analiza de forma agregada para decisiones de producto. No requiere tiempo real. |
| `supplier_order_delayed` | **Batch** | Los retrasos de proveedores se evalúan en períodos (semanal o mensualmente). Un retraso individual no requiere acción inmediata a menos que se acumule. |

### 3.2 Throttle / Debounce para eventos de alta frecuencia

Algunos eventos pueden emitirse con alta frecuencia bajo ciertas condiciones. Se aplican las siguientes estrategias:

| Evento | Estrategia | Detalle |
|--------|-----------|---------|
| `login_attempted` | **Debounce de 500 ms** | Agrupar intentos del mismo usuario en una ventana de 500 ms para evitar saturación durante reintentos automáticos. |
| `login_failed` | **Throttle de 1 por minuto por usuario** | Solo registrar el primer fallo por minuto por usuario para reducir ruido; si hay más de 5 fallos en 1 minuto, se emite un evento agregado `login_failed` adicional con `attempt_count`. |
| `api_latency_recorded` | **Muestreo al 10 %** | En condiciones normales se muestrea el 10 % de las peticiones. Si la latencia media de los últimos 5 minutos supera un umbral (ej. 2000 ms), se aumenta al 100 % temporalmente. |
| `page_viewed` | **Debounce de 2 segundos** | Si un usuario navega rápidamente entre páginas, se debounea para registrar solo la última página visitada dentro de la ventana. |
| `page_load_timed` | **Solo página completa** | Se mide solo cuando la página ha cargado completamente (no eventos parciales). |

### 3.3 Riesgos y Exclusiones

#### Eventos considerados y descartados

| Evento descartado | Motivo |
|-------------------|--------|
| `product_created` / `product_updated` | El CRUD de productos es una operación interna del equipo de inventario, no aporta valor de negocio directo. Incluir eventos de mantenimiento de catálogo sobrecargaría el sistema sin hipótesis de decisión clara. |
| `user_logged_out` | El cierre de sesión voluntario no aporta información accionable; es preferible medir la duración de la sesión mediante `session_expired` y la métrica de sesión activa. |
| `inventory_snapshot` (estado completo del inventario cada N minutos) | Generaría un volumen masivo de datos sin una decisión inmediata asociada. El estado del inventario se puede reconstruir a partir de los eventos de entrada/salida (event sourcing). |
| `email_opened` / `notification_clicked` | Son eventos del sistema de notificaciones, fuera del alcance del sistema de inventario. Se podrían considerar en un plan de telemetría separado para comunicaciones. |
| `search_terms` (lo que los operadores buscan) | Contendría términos de búsqueda que podrían incluir nombres de candidatos o clientes (PII). El riesgo de privacidad supera el beneficio. |
| `geolocation_precise` | Revelaría la ubicación exacta de los operadores. Se opta por solo almacenar el país (anónimo) a partir de IP truncada. |
| `mouse_movements` / `click_heatmaps` | Son datos de muy alta frecuencia que requerirían un pipeline separado. No hay decisión de negocio inmediata. Se podría considerar en un futuro plan de UX research. |

#### Datos que no se capturan por privacidad

- **Nombres, emails o identificadores personales** de candidatos, clientes, consultores o agentes. Solo se almacena el `userId` del operador (ID interno, no nombre real).
- **Direcciones IP completas**: se truncan a `/24` o `/48` antes de cualquier procesamiento.
- **Contenido de formularios**: no se capturan los valores que rellena el usuario en formularios, solo metadatos (paso abandonado, si había datos o no).
- **Datos biométricos o MFA**: no se registran detalles sensibles del proceso de autenticación multifactor.

#### Datos que no se capturan por costo/volumen

- **Logs de depuración completos**: los `error_stack` en `frontend_error_captured` se capturan pero se limitan en tamaño (primeros 2 KB) y se almacenan con una política de retención corta (7 días).
- **Trazas de pila del backend**: no se capturan en los eventos de error de API. Los logs de servidor existen por separado para debugging profundo.

---

## Apéndice A: Convenciones

| Elemento | Convención |
|----------|-----------|
| **Taxonomía de `event_type`** | `entidad_acción` en snake_case. Verbos en pasado (created, rejected, triggered, expired, abandoned). |
| **Nombres de `event_type`** | Todos en minúscula, snake_case. |
| **Propiedades** | snake_case. |
| **Oficinas** | Siempre en minúscula: `valencia`, `miami`. |
| **Categorías de producto** | snake_case: `training_kit`, `certification`, `onboarding_equipment`. |
| **Monedas** | Código ISO 4217 mayúsculas: `EUR`, `USD`. |
| **Fechas** | ISO 8601 en UTC, formato `YYYY-MM-DDTHH:mm:ss.sssZ`. |
| **IDs** | UUID v4 para eventId, sessionId, requestId. IDs alfanuméricos para entidades de negocio. |
| **schemaVersion** | Semver (ej. `1.0`, `1.1`, `2.0`). Se incrementa cuando se añaden/quitan campos del allowlist. |
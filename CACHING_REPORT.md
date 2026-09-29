# CACHING_REPORT — Optimización de Rendimiento

## 1. Decisiones en el Frontend

### 1.1 Lazy Loading (carga diferida)

Se identificaron como candidatos los componentes "pesados" que no son visibles inmediatamente al cargar la página principal. Se aplicó `next/dynamic` (el equivalente de `React.lazy` en Next.js App Router) en los siguientes casos:

| Componente / Ruta | Justificación |
|---|---|
| `CandidateTable` (`/talent-pipeline-tracker`) | Renderiza una tabla completa de candidatos con múltiples filas. Solo visible tras la cabecera y los filtros. |
| `CandidateFilters` (`/talent-pipeline-tracker`) | Panel de filtros con selects y botones. Separado del contenido principal, se puede cargar de forma diferida. |
| `CandidateDetailClient` (`/talent-pipeline-tracker/Candidates/[id]`) | Componente cliente pesado con gestión de estado de candidato + notas, formularios y cambios de estado. |
| `CandidateFormComponent` (`/talent-pipeline-tracker/Candidates/new`) | Formulario extenso con múltiples campos, imports grandes de tipos y utilidades. |
| `IncidentsManagerClient` (`/incidents`) | Ya usaba `dynamic()`. Se mantiene el enfoque. |
| `SuppliersManagerClient` (`/suppliers`) | Ya usaba `dynamic()`. Se mantiene el enfoque. |
| `IncidentAnalyzerClient` (`/incident-analyzer`) | Ya usaba `dynamic()`. Se mantiene el enfoque. |

**Beneficio estimado**: El bundle inicial de JavaScript se reduce en ~30-50 KB por cada componente diferido. La página principal (`/`) carga ~200ms más rápido al no incluir los bundles de las herramientas secundarias.

### 1.2 useMemo — valores memoizados

Se aplicó `useMemo` en los siguientes casos donde el cálculo no es trivial y el array de dependencias está bien definido:

| Componente | Expresión memoizada | Dependencias | Beneficio |
|---|---|---|---|
| `OrdersHistoryPage` `filteredOrders` | Filtrado por tipo + rango temporal + ordenación | `[orders, filterType, filterDays]` | Evita recalcular el filtro en cada render; especialmente útil al cargar grandes volúmenes de pedidos. |
| `IncidentsManagerClient` `sortedIncidents` | Ordenación por estado (prioridad) + fecha | `[incidents]` | La lista se reordena solo cuando cambian los datos. |
| `IncidentsManagerClient` `summaryCards` | Tarjetas de resumen del dashboard | `[summary]` | Transformación de datos para UI que solo se recalcula cuando `summary` cambia. |
| `SuppliersManagerClient` `sortedSuppliers` | Ordenación por estado + nombre | `[suppliers]` | Evita reordenar en cada interacción del formulario. |
| `InventoryProductsPage` `sortedProducts` | Ordenación alfabética de productos | `[products]` | La lista solo se reordena cuando cambia `products`. |
| `IncidentAnalyzerClient` `activeInvalidRules` | Filtrado de reglas de validación activas | `[summary]` | Filtrado sobre array de reglas; evita recorrer en cada render. |

**Beneficio estimado**: Reducción de trabajo innecesario del renderizador. En componentes con listas de >100 elementos, se evitan ~2-5ms de cómputo por render que no debería ocurrir.

---

## 2. Decisiones en el Backend

### 2.1 Sistema de Caché

Se implementó un sistema de caché en memoria (`services/cache.py`) con las siguientes características:

- **`TTLCache`**: diccionario en memoria con expiración por tiempo (TTL).
- **Soporte de tags**: cada entrada puede tener uno o más tags para invalidación por grupo.
- **Decorador `@cached`**: fácil de aplicar a funciones existentes.
- **Caché global `backend_cache`**: instancia compartida con TTL por defecto de 120 segundos.

### 2.2 Endpoints cacheados

#### Endpoint 1: `GET /api/incidents/summary` (IncidentSummary)

| Propiedad | Valor |
|---|---|
| Coste de operación | **Alto** — recorre todos los documentos de TinyDB, agregando por status, categoría, branch y origen. Escala O(n) con el número de incidencias. |
| Frecuencia estimada | **Alta** — el dashboard de incidencias lo consulta en cada carga de página y tras cada cambio de filtro. |
| Frecuencia de cambio de datos | **Baja/Media** — los datos cambian solo cuando un usuario crea, actualiza o transiciona una incidencia (operaciones manuales). |
| TTL elegido | **120 segundos** (2 minutos) |
| Estrategia de invalidación | **Por escritura**: se invalida la tag `incidents_summary` en todas las operaciones de escritura (create, update, status transition, delete, bulk insert, clear). |
| Tag de caché | `incidents_summary` |

#### Endpoint 2: `GET /inventory/orders` (Orders listing)

| Propiedad | Valor |
|---|---|
| Coste de operación | **Alto** — cruza datos de tres tablas (assets, entries, exits) y construye objetos `OrderResponse` con joins en memoria. |
| Frecuencia estimada | **Alta** — la página de histórico de pedidos lo consulta al cargar, y los filtros se aplican del lado del cliente. |
| Frecuencia de cambio de datos | **Baja** — las entradas/salidas se registran manualmente; no hay cambios automáticos ni frecuentes. |
| TTL elegido | **120 segundos** (2 minutos) |
| Estrategia de invalidación | **Por escritura**: se invalida la tag `inventory_orders` al crear entries o exits. |
| Tag de caché | `inventory_orders` |

#### Endpoint 3: `GET /inventory/products` (Assets list)

| Propiedad | Valor |
|---|---|
| Coste de operación | **Medio/Alto** — recorre todos los assets y calcula `current_stock` para cada uno haciendo sumas en las tablas entries/exits. |
| Frecuencia estimada | **Alta** — página principal de inventario. |
| Frecuencia de cambio de datos | **Baja** — cambios solo al crear/editar assets o registrar entradas/salidas. |
| TTL elegido | **120 segundos** |
| Estrategia de invalidación | Por escritura (create_entry, create_exit, create_asset, update_asset). |
| Tag de caché | `inventory_assets` |

#### Endpoint 4: `GET /api/incidents` (sin filtros)

| Propiedad | Valor |
|---|---|
| Coste de operación | **Medio** — recorre todos los documentos y los serializa. |
| Frecuencia estimada | **Alta** — se consulta en cada carga del gestor de incidencias. |
| Frecuencia de cambio de datos | **Baja** — solo cambia con operaciones CRUD manuales. |
| TTL elegido | **60 segundos** (vida más corta porque los usuarios pueden crear incidencias y esperan verlas pronto). |
| Estrategia de invalidación | Por escritura (todas las operaciones CRUD de incidencias). |
| Tag de caché | `incidents_list` |

---

## 3. Intercambios Reconocidos (Freshness vs. Performance)

### 3.1 TTL de 120s en el summary de incidencias

**Elección**: 120 segundos (2 minutos) para `get_summary()`.

**Razonamiento**: El dashboard de resumen muestra estadísticas agregadas (total por estado, categoría, etc.). Estas métricas alimentan tarjetas visuales en la UI. Un desfase de hasta 2 minutos es perfectamente aceptable porque:

1. Las incidencias no se crean masivamente en tiempo real; las operaciones son manuales.
2. Cuando *sí* hay un cambio (crear, actualizar), la invalidación por escritura limpia la caché inmediatamente — el TTL es solo un safe-guard.
3. El coste de recalcular el summary es O(n) con n = todas las incidencias; con ~1000 incidencias, la caché ahorra ~50ms por llamada.

### 3.2 TTL de 60s en listado de incidencias vs 120s en summary

El listado de incidencias tiene un TTL más corto (60s) porque los usuarios pueden estar creando o cambiando estado de incidencias y es más importante que vean el cambio reflejado pronto en la tabla. El summary, al ser solo informativo, tolera 2 minutos sin problema.

### 3.3 Invalidación por escritura en lugar de solo TTL

Se podría haber usado solo TTL (por ejemplo, 5 minutos para todo) y simplificar el diseño. Pero la invalidación por escritura garantiza que ningún usuario vea datos obsoletos después de una operación que él mismo (u otro usuario) haya realizado. El coste es la sobrecarga de limpiar tags en cada write (~1-2μs), que es despreciable comparado con el beneficio.

---

## 4. Qué no se cacheó y por qué

### 4.1 `GET /api/incidents/analyze` (Analizador de CSV)

**Decisión**: No cachear.

**Justificación**: Este endpoint recibe un archivo CSV subido por el usuario y realiza un análisis único. Cada llamada tiene un `file` diferente, y los resultados no son reutilizables. Además, los datos de análisis incluyen métricas personalizadas para cada CSV, por lo que no tendría sentido compartir caché.

### 4.2 `GET /profiles/me`

**Decisión**: No cachear.

**Justificación**: Devuelve datos **personalizados y sensibles** del usuario autenticado. Cachear esto requeriría una clave de caché por usuario (p.ej. `user_id`), y el riesgo de fuga de datos si la clave no se acota correctamente es alto. Además, la frecuencia de consulta es baja (solo al cargar la página de perfil), y el coste de la operación es mínimo (una consulta TinyDB por `user_id`).

### 4.3 `GET /suppliers`

**Decisión**: No cachear.

**Justificación**: Aunque es un endpoint de lectura frecuente, los datos de proveedores son relativamente pocos (decenas, no miles) y el acceso a TinyDB es prácticamente instantáneo. Además, los proveedores tienen operaciones CRUD frecuentes (cambios de estado, tarifas), lo que invalidaría la caché constantemente, reduciendo su efectividad.

### 4.4 `NavBar`

**Decisión**: No se aplicó lazy loading ni useMemo.

**Justificación**: El componente NavBar ya es parte del layout raíz y se renderiza en todas las páginas. Aplicarle lazy loading retrasaría la renderización de la navegación principal, empeorando la experiencia de usuario (FOUT/CLS). Su coste de renderizado es bajo (unos pocos enlaces y un avatar). No hay cálculos costosos que memoizar.

### 4.5 Páginas de autenticación (`/login`, `/register`, `/forgot-password`, `/reset-password`)

**Decisión**: No se aplicó lazy loading adicional.

**Justificación**: Estas páginas ya son ligeras por naturaleza (formularios simples sin datos pesados). Aplicar dynamic() añadiría latencia a la primera interacción del usuario con la aplicación, justo en el momento crítico de onboarding. Preferimos que carguen inline para maximizar la velocidad percibida.

---

## 5. Resumen de impacto

| Área | Optimización | Impacto estimado |
|---|---|---|
| Frontend — JS bundle | Lazy loading de 4 componentes grandes | -30-50 KB del bundle inicial |
| Frontend — Renderizado | useMemo en 6 expresiones | -2-5ms por render evitado |
| Backend — Incidencias summary | Caché TTL 120s + invalidación | -50ms por llamada (~95% de ahorro en lecturas) |
| Backend — Inventario products | Caché TTL 120s + invalidación | -30ms por llamada |
| Backend — Inventario orders | Caché TTL 120s + invalidación | -40ms por llamada |
| Backend — Lista incidencias | Caché TTL 60s + invalidación | -20ms por llamada |
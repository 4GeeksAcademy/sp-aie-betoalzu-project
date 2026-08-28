# Auditoría de Serialización de Endpoints

> **Fecha:** 2026-08-28
> **Objetivo:** Examinar todos los endpoints del proyecto en `services/api` y clasificarlos como **serializados**, **parcialmente serializados** o **no serializados**.

---

## Convenciones de evaluación

| Estado | Significado |
|--------|-------------|
| ✅ **Serializado** | La respuesta utiliza un modelo Pydantic (`model_dump(mode="json")`) o es un tipo nativo correcto (dict simple con valores escalares, `Response` de FastAPI, etc.). |
| ⚠️ **Parcialmente serializado** | La respuesta se construye como un dict manual (ej. `_serialize_*()`) sin pasar por un Pydantic de salida, o existe un `response_model` declarado pero los servicios devuelven dicts manuales. |
| ❌ **No serializado** | La respuesta es un dict plano sin ningún modelo Pydantic de respaldo ni estructura definida. |

---

## 1. Módulo: `incident_analyzer` (`services/api/incident_analyzer/routes.py`)

| # | Ruta | Método | Propósito | Estado | Problema |
|---|------|--------|-----------|--------|----------|
| 1.1 | `/api/incidents/analyze` | POST | Analizar un CSV de incidencias | ⚠️ Parcialmente serializado | `build_summary()` retorna un `dict` plano. Aunque `AnalysisResult` existe como Pydantic, no se usa para serializar la respuesta. |
| 1.2 | `/api/incidents/results/export` | GET | Exportar métricas como CSV | ✅ Serializado | Usa `Response` de FastAPI con `build_metrics_csv()`, que es el tipo correcto para CSV. |

**Sugerencia 1.1:** Crear un Pydantic `AnalysisSummaryResponse` o usar `AnalysisResult.model_dump(mode="json")` envuelto en metadatos adicionales, para garantizar validación y documentación OpenAPI automática.

---

## 2. Módulo: `incidents` (`services/api/incidents/routes.py`)

| # | Ruta | Método | Propósito | Estado | Problema |
|---|------|--------|-----------|--------|----------|
| 2.1 | `/api/incidents` | GET | Listar incidencias (con filtros) | ✅ Serializado | Usa `IncidentOut.model_dump(mode="json")`. Correcto. |
| 2.2 | `/api/incidents` | POST | Crear nueva incidencia | ✅ Serializado | Usa `IncidentOut.model_dump(mode="json")`. Correcto. |
| 2.3 | `/api/incidents/summary` | GET | Estadísticas agregadas | ⚠️ Parcialmente serializado | `get_summary()` retorna un `dict[str, Any]` plano. Existe `IncidentSummary` como Pydantic pero no se usa para serializar. |
| 2.4 | `/api/incidents/seed` | POST | Sembrar incidencias desde CSV | ❌ No serializado | Retorna un dict plano `{ "total_rows", "inserted", "discarded", "skipped", "status" }` sin modelo Pydantic. |
| 2.5 | `/api/incidents/{id}` | GET | Obtener incidencia por ID | ✅ Serializado | Usa `IncidentOut.model_dump(mode="json")`. |
| 2.6 | `/api/incidents/{id}` | PUT | Actualizar incidencia | ✅ Serializado | Usa `IncidentOut.model_dump(mode="json")`. |
| 2.7 | `/api/incidents/{id}/status` | PATCH | Transicionar estado | ✅ Serializado | Usa `IncidentOut.model_dump(mode="json")`. |
| 2.8 | `/api/incidents/{id}` | DELETE | Eliminar incidencia | ✅ Serializado | Retorna `{"message": ...}` — dict simple suficiente. |

**Sugerencia 2.3:** Hacer que `get_summary()` retorne un `IncidentSummary` y llame a `.model_dump(mode="json")`.

**Sugerencia 2.4:** Crear un Pydantic `SeedResult(BaseModel)` con los campos del dict para garantizar serialización y documentación.

---

## 3. Módulo: `inventory` (`services/api/inventory/routes.py`)

| # | Ruta | Método | Propósito | Estado | Problema |
|---|------|--------|-----------|--------|----------|
| 3.1 | `/inventory/products` | GET | Listar activos (con stock) | ⚠️ Parcialmente serializado | `list_assets()` usa `_serialize_asset()` manual + `current_stock` añadido a mano. Existe `AssetResponse` Pydantic pero no se utiliza. |
| 3.2 | `/inventory/products` | POST | Registrar nuevo activo | ⚠️ Parcialmente serializado | `create_asset()` usa `_serialize_asset()` manual, no `AssetResponse`. |
| 3.3 | `/inventory/products/{id}` | GET | Obtener activo por ID | ⚠️ Parcialmente serializado | Mismo problema: dict manual con `current_stock` añadido. |
| 3.4 | `/inventory/products/{id}` | PUT | Actualizar activo | ⚠️ Parcialmente serializado | Mismo problema: dict manual. |
| 3.5 | `/inventory/orders/inbound` | POST | Registrar entrada (inbound) | ⚠️ Parcialmente serializado | `create_entry()` usa `_serialize_entry()` manual. Existe `AssetEntryResponse` Pydantic pero no se utiliza. |
| 3.6 | `/inventory/orders/outbound` | POST | Registrar salida (outbound) | ⚠️ Parcialmente serializado | `create_exit()` usa `_serialize_exit()` manual. Existe `AssetExitResponse` Pydantic pero no se utiliza. |
| 3.7 | `/inventory/orders` | GET | Listar todas las órdenes | ✅ Serializado | `list_orders()` usa `OrderResponse.model_dump(mode="json")`. Correcto. |

**Sugerencia general (3.1–3.6):** Refactorizar los servicios para que retornen instancias de `AssetResponse`, `AssetEntryResponse` y `AssetExitResponse` (ya definidos en `services/schemas.py`) y usar `.model_dump(mode="json")` en las rutas. Eliminar las funciones `_serialize_asset`, `_serialize_entry` y `_serialize_exit`.

---

## 4. Módulo: `profiles` (`services/api/profiles/routes.py`)

| # | Ruta | Método | Propósito | Estado | Problema |
|---|------|--------|-----------|--------|----------|
| 4.1 | `/profiles/me` | GET | Obtener perfil propio | ⚠️ Parcialmente serializado | Tiene `response_model=ProfileOut` (lo cual fuerza validación), pero el servicio retorna un dict manual desde `_serialize_profile()`. |
| 4.2 | `/profiles/me` | PUT | Actualizar perfil propio | ⚠️ Parcialmente serializado | Mismo problema: `response_model=ProfileOut` declarado pero el servicio retorna dict manual. |

**Sugerencia:** Refactorizar `_serialize_profile()` para que retorne un `ProfileOut(...)` y llamar a `.model_dump(mode="json")`. Alternativamente, dado que ya tienen `response_model=ProfileOut`, FastAPI hace la conversión automática, pero es mejor práctica que el servicio devuelva el modelo directamente.

---

## 5. Módulo: `suppliers` (`services/api/suppliers/routes.py`)

| # | Ruta | Método | Propósito | Estado | Problema |
|---|------|--------|-----------|--------|----------|
| 5.1 | `/suppliers` | POST | Crear proveedor | ✅ Serializado | Usa `Supplier.model_validate().model_dump(mode="json")`. |
| 5.2 | `/suppliers` | GET | Listar proveedores (con filtros) | ✅ Serializado | Usa `_serialize_supplier()` que internamente usa `Supplier.model_validate().model_dump(mode="json")`. |
| 5.3 | `/suppliers/{id}` | GET | Obtener proveedor por ID | ✅ Serializado | Ídem. |
| 5.4 | `/suppliers/{id}` | PUT | Actualizar proveedor | ✅ Serializado | Ídem. |
| 5.5 | `/suppliers/{id}/rate` | PATCH | Actualizar tarifa mensual | ✅ Serializado | Ídem. |
| 5.6 | `/suppliers/{id}/status` | PATCH | Actualizar estado | ✅ Serializado | Ídem. |
| 5.7 | `/suppliers/{id}` | DELETE | Eliminar proveedor | ✅ Serializado | Retorna `{"id": ..., "deleted": True}`. Correcto. |

**Conclusión:** El módulo `suppliers` es el único que sigue consistentemente el patrón de serialización con Pydantic en todos sus endpoints. ✅

---

## 6. Módulo: `users` (`services/api/users/routes.py`)

| # | Ruta | Método | Propósito | Estado | Problema |
|---|------|--------|-----------|--------|----------|
| 6.1 | `/login` | POST | Autenticar usuario (JWT) | ✅ Serializado | Retorna `{"access_token", "token_type"}` — dict simple suficiente. |
| 6.2 | `/auth/forgot-password` | POST | Solicitar restablecimiento | ✅ Serializado | Retorna `{"message": ...}`. |
| 6.3 | `/auth/reset-password` | POST | Restablecer contraseña | ✅ Serializado | Retorna `{"message": ...}`. |
| 6.4 | `/auth/change-password` | POST | Cambiar contraseña | ✅ Serializado | Retorna `{"message": ...}`. |
| 6.5 | `/users` | POST | Registrar usuario | ⚠️ Parcialmente serializado | `create_user()` retorna dict de `_serialize_user()`. Existe `UserOut` Pydantic pero no se usa. |
| 6.6 | `/users` | GET | Listar usuarios | ⚠️ Parcialmente serializado | `list_users()` retorna lista de dicts de `_serialize_user()`. |
| 6.7 | `/users/{id}` | GET | Obtener usuario por ID | ⚠️ Parcialmente serializado | `get_user_by_id()` retorna dict de `_serialize_user()`. |
| 6.8 | `/users/{id}` | PUT | Actualizar usuario | ⚠️ Parcialmente serializado | `update_user()` retorna dict de `_serialize_user()`. |
| 6.9 | `/users/{id}` | DELETE | Eliminar usuario | ✅ Serializado | Retorna `{"message": ...}`. |

**Sugerencia (6.5–6.8):** Refactorizar `_serialize_user()` para retornar un `UserOut(...)` y usar `.model_dump(mode="json")` en las rutas.

---

## Resumen global

| Estado | Cantidad | Endpoints |
|--------|----------|-----------|
| ✅ Serializado | 18 | 1.2, 2.1, 2.2, 2.5, 2.6, 2.7, 2.8, 3.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.4, 6.9 |
| ⚠️ Parcialmente serializado | 12 | 1.1, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 6.5, 6.6, 6.7, 6.8 |
| ❌ No serializado | 1 | 2.4 |

**Total endpoints evaluados: 31**

---

## Recomendaciones prioritarias

1. **Alta prioridad:** Serializar los endpoints de inventario (3.1–3.6) usando `AssetResponse`, `AssetEntryResponse`, `AssetExitResponse` — los modelos ya existen en `services/schemas.py`.
2. **Alta prioridad:** Serializar `GET /api/incidents/summary` (2.3) usando `IncidentSummary.model_dump(mode="json")`.
3. **Media prioridad:** Crear un Pydantic `SeedResult` para `POST /api/incidents/seed` (2.4).
4. **Media prioridad:** Refactorizar `_serialize_user()` para retornar `UserOut` y usarlo en los endpoints de users (6.5–6.8).
5. **Media prioridad:** Refactorizar `_serialize_profile()` para retornar `ProfileOut` (4.1, 4.2).
6. **Baja prioridad:** Usar `AnalysisResult` para serializar la respuesta de `POST /api/incidents/analyze` (1.1).

---

*Fin del informe de auditoría.*
# Batería de Pruebas — API de Autenticación

## Objetivo

Validar que todos los endpoints de la API de autenticación funcionan correctamente en sus tres dimensiones:

- **Camino feliz** — el flujo esperado cuando todo va bien.
- **Caso límite** — comportamiento en el borde de lo válido (valores extremos, usuarios inexistentes, etc.).
- **Modo de fallo** — comportamiento ante entradas inválidas, credenciales erróneas, permisos insuficientes, etc.

Se prueba la **lógica de negocio**, no la serialización HTTP. Para el backend se inyectan dependencias o se prueban las funciones directamente. Para el frontend se prueban las funciones _service_ y _utility_ sin depender del servidor.

---

## Ejecución de las pruebas

### Backend (Python / FastAPI)

```bash
uv run pytest -v
```

Para ver cobertura:

```bash
uv run pytest --cov=services.api.users --cov-report=term-missing -v
```

> **Requisito:** tener `pytest` y `pytest-cov` en el entorno (`uv add --dev pytest pytest-cov` si no están).

### Frontend (TypeScript / Next.js)

```bash
cd uis/backoffice
npx jest --coverage
```

> **Requisito:** las dependencias de `jest`, `ts-jest` y `@types/jest` ya están declaradas en `package.json`.

---

## Endpoints cubiertos — Backend (Python)

| Endpoint | Método | Descripción |
|---|---|---|
| `/login` | POST | Autenticar con email y contraseña, devuelve JWT |
| `/auth/forgot-password` | POST | Solicitar token de restablecimiento de contraseña |
| `/auth/reset-password` | POST | Restablecer contraseña usando un token válido |
| `/auth/change-password` | POST | Cambiar contraseña (usuario autenticado) |
| `/users` | POST | Registrar un nuevo usuario |
| `/users` | GET | Listar todos los usuarios (protegido) |
| `/users/{user_id}` | GET | Obtener un usuario por ID (protegido) |
| `/users/{user_id}` | PUT | Actualizar un usuario (protegido) |
| `/users/{user_id}` | DELETE | Eliminar un usuario (protegido) |

### 1. `POST /login` — Inicio de sesión

| # | Tipo | Descripción |
|---|---|---|
| 1.1 | Feliz | Credenciales correctas → devuelve `access_token` y `token_type` |
| 1.2 | Límite | Email con formato válido pero no registrado → `401` |
| 1.3 | Fallo | Contraseña incorrecta → `401` |
| 1.4 | Fallo | Usuario inactivo (`is_active=false`) → `403` |
| 1.5 | Fallo | Email vacío o con formato inválido → error de validación |

### 2. `POST /auth/forgot-password` — Solicitar restablecimiento

| # | Tipo | Descripción |
|---|---|---|
| 2.1 | Feliz | Email registrado → responde con mensaje genérico (siempre `200`) |
| 2.2 | Límite | Email no registrado → responde con el **mismo** mensaje genérico (evita enumeración) |
| 2.3 | Fallo | Email con formato inválido → error de validación |

### 3. `POST /auth/reset-password` — Restablecer contraseña

| # | Tipo | Descripción |
|---|---|---|
| 3.1 | Feliz | Token válido y no expirado → actualiza contraseña, invalida token |
| 3.2 | Límite | Token expirado → `400` "Token ha expirado" |
| 3.3 | Fallo | Token ya utilizado → `400` "Token inválido o ya utilizado" |
| 3.4 | Fallo | Token inexistente (aleatorio) → `400` |
| 3.5 | Fallo | Nueva contraseña de menos de 6 caracteres → error de validación |

### 4. `POST /auth/change-password` — Cambiar contraseña (autenticado)

| # | Tipo | Descripción |
|---|---|---|
| 4.1 | Feliz | Contraseña actual correcta → actualiza y responde éxito |
| 4.2 | Límite | Contraseña actual incorrecta → `400` |
| 4.3 | Fallo | Token JWT ausente o inválido → `401` |
| 4.4 | Fallo | Nueva contraseña igual a la actual (se permite, pero debe funcionar) |

### 5. `POST /users` — Registrar usuario

| # | Tipo | Descripción |
|---|---|---|
| 5.1 | Feliz | Datos válidos → crea usuario, devuelve datos sin contraseña, `201` |
| 5.2 | Límite | Email duplicado → `409` |
| 5.3 | Fallo | Contraseña de menos de 6 caracteres → error de validación |
| 5.4 | Fallo | Email con formato inválido → error de validación |
| 5.5 | Feliz | Con perfil opcional (`name`, `phone`, `address`) → guarda perfil |

### 6. `GET /users` — Listar usuarios

| # | Tipo | Descripción |
|---|---|---|
| 6.1 | Feliz | Usuario autenticado → lista de usuarios (sin contraseñas) |
| 6.2 | Fallo | Sin token JWT → `401` |
| 6.3 | Límite | Sin usuarios registrados → lista vacía `[]` |

### 7. `GET /users/{user_id}` — Obtener usuario por ID

| # | Tipo | Descripción |
|---|---|---|
| 7.1 | Feliz | Usuario autenticado, ID existente → datos del usuario |
| 7.2 | Límite | ID inexistente → `404` |
| 7.3 | Fallo | Sin token JWT → `401` |

### 8. `PUT /users/{user_id}` — Actualizar usuario

| # | Tipo | Descripción |
|---|---|---|
| 8.1 | Feliz | Mismo usuario actualiza su email → éxito |
| 8.2 | Feliz | Admin actualiza rol de otro usuario → éxito |
| 8.3 | Límite | Email duplicado (otro usuario ya lo tiene) → `409` |
| 8.4 | Fallo | Usuario no-admin intenta cambiar su propio rol → `403` |
| 8.5 | Fallo | Usuario intenta actualizar a otro usuario sin ser admin → `403` |
| 8.6 | Fallo | ID inexistente → `404` |

### 9. `DELETE /users/{user_id}` — Eliminar usuario

| # | Tipo | Descripción |
|---|---|---|
| 9.1 | Feliz | Mismo usuario se elimina a sí mismo → `200` |
| 9.2 | Feliz | Admin elimina a otro usuario → `200` |
| 9.3 | Fallo | Usuario no-admin intenta eliminar a otro → `403` |
| 9.4 | Límite | ID inexistente → `404` |

---

## Funciones cubiertas — Frontend (TypeScript)

| Archivo | Función | Descripción |
|---|---|---|
| `services/auth-api.ts` | `loginApi` | Envía POST a `/api/auth/login` |
| `services/auth-api.ts` | `registerApi` | Envía POST a `/api/auth/register` |
| `services/auth-api.ts` | `decodeTokenPayload` | Decodifica payload de un JWT |
| `services/auth-api.ts` | `getCurrentUserApi` | Obtiene usuario por ID vía `/api/auth/me` |
| `services/auth-api.ts` | `updateUserApi` | Actualiza usuario vía proxy |
| `services/auth-api.ts` | `getMyProfileApi` | Obtiene perfil vía `/api/profiles/me` |
| `lib/auth-token.ts` | `getStoredToken` | Lee token de `localStorage` |
| `lib/auth-token.ts` | `setStoredToken` | Guarda token en `localStorage` y cookie |
| `lib/auth-token.ts` | `removeStoredToken` | Elimina token de `localStorage` y cookie |
| `lib/auth-token.ts` | `getAuthHeaders` | Devuelve `{ Authorization: "Bearer ..." }` |
| `lib/auth-token.ts` | `getTokenFromCookie` | Lee token desde cookie |
| `lib/auth-context.tsx` | `AuthProvider.login` | Flujo completo: login → guardar token → cargar perfil |
| `lib/auth-context.tsx` | `AuthProvider.register` | Flujo completo: registro → auto-login |
| `lib/auth-context.tsx` | `AuthProvider.logout` | Limpia token y estado |

### 1. `loginApi` — Loguear usuario

| # | Tipo | Descripción |
|---|---|---|
| F.1.1 | Feliz | Email y contraseña correctos → `LoginResponse` con `access_token` |
| F.1.2 | Fallo | Credenciales inválidas → lanza `Error` con mensaje del servidor |
| F.1.3 | Fallo | Error de red → la promesa se rechaza |

### 2. `registerApi` — Registrar usuario

| # | Tipo | Descripción |
|---|---|---|
| F.2.1 | Feliz | Payload válido → respuesta exitosa |
| F.2.2 | Fallo | Email duplicado → lanza `Error` |
| F.2.3 | Fallo | Contraseña muy corta → lanza `Error` |

### 3. `decodeTokenPayload` — Decodificar JWT

| # | Tipo | Descripción |
|---|---|---|
| F.3.1 | Feliz | Token JWT válido → devuelve `{ sub, role }` |
| F.3.2 | Fallo | Token malformado (sin 3 partes) → devuelve `null` |
| F.3.3 | Fallo | Payload no es JSON válido → devuelve `null` |

### 4. Token storage utils (`auth-token.ts`)

| # | Tipo | Descripción |
|---|---|---|
| F.4.1 | Feliz | `setStoredToken` → persiste en localStorage y cookie |
| F.4.2 | Feliz | `getStoredToken` → recupera el token guardado |
| F.4.3 | Feliz | `removeStoredToken` → elimina token de localStorage y cookie |
| F.4.4 | Límite | `getStoredToken` sin token previo → devuelve `null` |
| F.4.5 | Feliz | `getAuthHeaders` con token → `{ Authorization: "Bearer <token>" }` |
| F.4.6 | Límite | `getAuthHeaders` sin token → `{}` |
| F.4.7 | Feliz | `getTokenFromCookie` con cookie presente → devuelve el token |
| F.4.8 | Límite | `getTokenFromCookie` sin cookie → devuelve `null` |

---

## Estructura de archivos de prueba propuesta

```
services/
  api/
    users/
      tests/
        __init__.py
        conftest.py              # Fixtures compartidas (db temporal, usuarios semilla)
        test_login.py
        test_forgot_password.py
        test_reset_password.py
        test_change_password.py
        test_register_user.py
        test_list_users.py
        test_get_user.py
        test_update_user.py
        test_delete_user.py

uis/
  backoffice/
    __tests__/
      services/
        auth-api.test.ts
      lib/
        auth-token.test.ts
        auth-context.test.ts
```

### Backend — notas de implementación

- Usar **TinyDB en memoria** (`import tempfile` + `TinyDB(str(tmp_path))`) para no contaminar la base de datos real.
- Cada archivo de prueba se enfoca en un endpoint y contiene los tres casos (feliz, límite, fallo).
- `conftest.py` expone fixtures como:
  - `test_db` — base TinyDB temporal.
  - `sample_user` — usuario creado en la base temporal.
  - `auth_headers` — token JWT generado con `create_access_token` para rutas protegidas.
  - `admin_headers` — token JWT de un usuario administrador.

### Frontend — notas de implementación

- Las funciones de `auth-api.ts` usan `fetch` real; en los tests se mockea `global.fetch` con `jest.fn()`.
- `decodeTokenPayload` es pura (sin side effects) y se prueba directamente.
- Las funciones de `auth-token.ts` manipulan `localStorage`; se mockea con `Object.defineProperty(window, ...)` o se usua `jest-localstorage-mock`.
- `AuthProvider.login` y `AuthProvider.register` se prueban con `@testing-library/react` renderizando el proveedor y verificando estado.

---

## Criterios de aceptación

1. Todos los tests pasan con `uv run pytest -v`.
2. Todos los tests pasan con `npx jest --coverage` desde `uis/backoffice/`.
3. Cada endpoint/función tiene al menos un test de camino feliz, uno de caso límite y uno de modo de fallo.
4. No se prueba la serialización HTTP (no se usan `TestClient` de FastAPI para las rutas — se invoca la lógica directamente). Para el backend se prueban las funciones de servicio y autenticación directamente; para el frontend se prueban las funciones _service_ y _utility_ con mocks.
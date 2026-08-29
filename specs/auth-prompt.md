# Protección de rutas
- Aplica get_current_user como dependencia a cada ruta que no deba ser pública. Como mínimo: todos los endpoints de /users excepto POST/users,auth/me y al menos otras 5 rutas existentes de la API de tu monorepo (fuera de /users y /auth) que expongan o modifiquen datos sensibles.
- Devuelve 401 Unauthorized para solicitudes no autenticadas y 403 Forbidden cuando un usuario intenta acceder a un recurso que no le pertenece.

# Verificación
- Verifica el flujo completo manualmente usando los docs interactivos de FastAPI (/docs): registro con POST /users login → copiar token → usar el token en una ruta protegida.
- Confirma que llamar a una ruta protegida sin token devuelve 401
- Confirma que llamar a una ruta protegida con un token expirado o mal formado devuelve 401
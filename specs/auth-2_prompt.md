# AUTH-02 — Flujos de autenticación y vistas protegidas en el frontend

La API ya exige un token JWT en las rutas protegidas. Esta tarea cubre el lado frontend de ese contrato:

- Vistas de login y registro — formularios que llaman a la API, reciben el token y lo almacenan correctamente.
- Vistas de gestión de cuenta — página de perfil.
- Protección de rutas — cualquier vista que requiera sesión debe redirigir a los usuarios no autenticados al login. Esto aplica a todas las aplicaciones del monorepo excepto el website público (Hito 1), que permanece completamente público.
- El token debe almacenarse en localStorage y adjuntarse a cada llamada protegida a la API mediante la cabecera Authorization: Bearer. Al cerrar sesión, el token se elimina y el usuario es redirigido al login.

- No construyas una aplicación de autenticación separada. Integra estos flujos en las aplicaciones Next.js existentes dentro de tu monorepo.

# TAREA

## Vistas de autenticación
- `/login-formulario` de email y contraseña. Si tiene éxito: almacena el token en localStorage, redirige a la vista autenticada principal. Si falla: muestra un mensaje de error claro.
- `/register-formulario` de registro. Si tiene éxito: llama a POST /users (incluye campos opcionales de perfil), luego a POST
- `/auth/login` con las mismas credenciales, almacena el token y redirige. Si falla: muestra errores de validación a nivel de campo.
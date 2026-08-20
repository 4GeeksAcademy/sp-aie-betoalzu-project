# AUTH-02 — Flujos de autenticación y vistas protegidas en el frontend

La API ya exige un token JWT en las rutas protegidas. Esta tarea cubre el lado frontend de ese contrato:

- Vistas de login y registro — formularios que llaman a la API, reciben el token y lo almacenan correctamente.
- Vistas de gestión de cuenta — página de perfil.
- Protección de rutas — cualquier vista que requiera sesión debe redirigir a los usuarios no autenticados al login. Esto aplica a todas las aplicaciones del monorepo excepto el website público (Hito 1), que permanece completamente público.
- El token debe almacenarse en localStorage y adjuntarse a cada llamada protegida a la API mediante la cabecera Authorization: Bearer. Al cerrar sesión, el token se elimina y el usuario es redirigido al login.

- No construyas una aplicación de autenticación separada. Integra estos flujos en las aplicaciones Next.js existentes dentro de tu monorepo.

# TAREA

## Vistas de gestión de cuenta
- /account/profile muestra el email del usuario actual más los datos de perfil (name, phone, address) desde GET /auth/me. Permite editar nombre y contacto mediante PUT /profiles/me con el token en la cabecera.

## Protección de rutas 
- Identifica todas las vistas de tus aplicaciones Next.js (excluyendo el website público) que requieren sesión autenticada.
- Implementa un mecanismo de protección en el cliente (layout guard o hook personalizado) que compruebe el token en localStorage y redirija a /login si está ausente o no es válido. No uses el middleware de Next.js para esto salvo que el token también esté en una cookie que el middleware pueda leer.
- Asegúrate de que el website (`uis/website`) no se ve afectado - sin comprobación de token, sin redirección.

## Ciclo de vida del token
- En login y registro: almacena el token en localStorage
- En cada llamada protegida a la API: lee el token y adjúntalo como Authorization: Bearer <token>
- Al cerrar sesión: elimina el token de localStorage y redirige a /login.
- Si una llamada protegida a la API devuelve 401: limpia el token y redirigea /login.
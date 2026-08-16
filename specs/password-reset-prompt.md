# AUTH-03 — Recuperación y cambio de contraseña
La plataforma necesita dos mecanismos de contraseña — restablecimiento cuando el usuario la olvidó, y cambio estando conectado. Esto cubre tanto la API como el frontend:

## Backend:

- POST /auth/forgot-password — recibe un email, valida que el usuario existe, genera un token de restablecimiento firmado de corta duración y envía un enlace de restablecimiento a la dirección del usuario.
- POST /auth/reset-password — recibe el token de restablecimiento y una nueva contraseña, valida el token (firma + expiración), hashea la nueva contraseña y actualiza el registro del usuario. El token debe quedar invalidado tras su uso.
- POST /auth/change-password — endpoint autenticado. Recibe la contraseña actual y una nueva, verifica la actual, hashea la nueva y actualiza el registro del usuario.

## Frontend:
- /forgot-password — formulario donde el usuario introduce su email. Siempre muestra un mensaje de confirmación tras el envío, independientemente de si la dirección existe, para evitar la enumeración de usuarios.
- /reset-password — formulario donde el usuario establece una nueva contraseña. Lee el token de restablecimiento del query string de la URL y lo envía a la API junto con la nueva contraseña. Si tiene éxito, redirige a /login.
- /account/change-password — formulario con la contraseña actual, la nueva contraseña y la confirmación. Valida que la nueva contraseña y la confirmación coinciden antes de llamar a la API.
Para el envío de correos, elige uno de los siguientes servicios e intégralo:
- Resend

# TAREA
## BACKEND
- POST /auth/forgot-password - acepta { email). Si el usuario existe, genera un token de restablecimiento con expiración corta (15-60 minutos) y envía un email con el enlace de restablecimiento. Devuelve siempre 200 independientemente de si el email fue encontrado.
- POST /auth/reset-password - acepta { token, new_password). Valida el token (firma, expiración y que no se haya usado ya). Si es válido, hashea la nueva contraseña, actualiza el registro del usuario e invalida el token. Devuelve 400 para tokens inválidos, expirados o ya utilizados.
- POST/auth/change-password - acepta { current_password, new_password } Requiere un token de sesión válido en la cabecera Authorization. Verifica la contraseña actual antes de actualizar. Devuelve 400 si la contraseña actual es incorrecta.
- Integra un servicio de correo transaccional para enviar el email de restablecimiento. El email debe incluir el enlace de restablecimiento y ser legible en móvil.
- Almacena la API key del servicio de email en una variable de entorno. Documenta el nombre de la variable en tu README o en un .env.example.

## Frontend
- /forgot-password - formulario con campo de email. Al enviarlo, llama a POST /auth/forgot-password y muestra un mensaje de confirmación ("Si esa dirección está registrada, recibirás un enlace en breve"). El formulario debe desactivarse tras el envío para evitar peticiones duplicadas.
- /reset-password-formulario de nueva contraseña con campo de confirmación. Lee el token del query string de la URL. AI enviarlo, llama a POST /auth/reset-password. Si tiene éxito, redirige a /login con un mensaje de éxito. Si falla (token expirado o inválido), muestra un error claro y un enlace de vuelta a /forgot-password.
- /account/change-password formulario con la contraseña actual, la nueva contraseña y la confirmación. Valida que la nueva contraseña y la confirmación coinciden antes de llamar a la API.
- Añade un enlace "¿Olvidaste tu contraseña?" en la página /login que apunte a /forgot-password.

## Seguridad
- Los tokens de restablecimiento deben expirar e invalidarse tras su uso - un token no puede usarse dos veces.
- El endpoint/forgot-password debe devolver siempre 200, nunca revelar si un email está registrado.
- Las API keys no deben aparecer nunca en el código fuente usa exclusivamente variables de entorno.
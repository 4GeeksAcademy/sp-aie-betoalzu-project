import { proxyAuthRequest } from '../_shared';

/**
 * POST /api/auth/reset-password
 * Proxies to POST /auth/reset-password on the Python backend.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { token, new_password } = body;

    if (!token || !new_password) {
      return new Response(
        JSON.stringify({ error: 'Token y nueva contrasena son obligatorios.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    if (new_password.length < 6) {
      return new Response(
        JSON.stringify({ error: 'La contrasena debe tener al menos 6 caracteres.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    return proxyAuthRequest('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  } catch {
    return new Response(
      JSON.stringify({ error: 'Cuerpo de peticion invalido.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }
}
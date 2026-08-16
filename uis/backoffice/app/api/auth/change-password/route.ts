import { proxyAuthRequest } from '../_shared';

/**
 * POST /api/auth/change-password
 * Proxies to POST /auth/change-password on the Python backend.
 * Requires the Authorization header from the client.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { current_password, new_password } = body;

    if (!current_password || !new_password) {
      return new Response(
        JSON.stringify({ error: 'Contrasena actual y nueva contrasena son obligatorias.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    if (new_password.length < 6) {
      return new Response(
        JSON.stringify({ error: 'La contrasena debe tener al menos 6 caracteres.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    const authHeader = request.headers.get('authorization') || undefined;

    return proxyAuthRequest('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
      headers: authHeader ? { Authorization: authHeader } : {},
    });
  } catch {
    return new Response(
      JSON.stringify({ error: 'Cuerpo de peticion invalido.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }
}
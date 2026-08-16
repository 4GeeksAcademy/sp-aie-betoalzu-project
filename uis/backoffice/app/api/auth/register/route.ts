import { proxyAuthRequest } from '../_shared';

/**
 * POST /api/auth/register
 * Accepts JSON body { email, password, role?, profile? } and proxies
 * to POST /users on the Python backend.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email || !password) {
      return new Response(
        JSON.stringify({ error: 'Email y contrasena son obligatorios.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    return proxyAuthRequest('/users', {
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

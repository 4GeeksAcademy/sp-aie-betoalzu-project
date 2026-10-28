import { proxyAuthRequest } from '../_shared';

/**
 * POST /api/auth/login
 * Accepts JSON body { email, password } and proxies JSON to POST /login.
 * on the Python backend.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (typeof email !== 'string' || typeof password !== 'string' || !email || !password) {
      return new Response(
        JSON.stringify({ error: 'Email y contrasena son obligatorios.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    return proxyAuthRequest('/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  } catch {
    return new Response(
      JSON.stringify({ error: 'Cuerpo de peticion invalido.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }
}

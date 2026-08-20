import { proxyAuthRequest } from '../_shared';

/**
 * POST /api/auth/login
 * Accepts JSON body { email, password } and proxies to POST /login?email=...&password=...
 * on the Python backend.
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

    const params = new URLSearchParams({ email, password });
    return proxyAuthRequest(`/login?${params.toString()}`, { method: 'POST' });
  } catch {
    return new Response(
      JSON.stringify({ error: 'Cuerpo de peticion invalido.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }
}

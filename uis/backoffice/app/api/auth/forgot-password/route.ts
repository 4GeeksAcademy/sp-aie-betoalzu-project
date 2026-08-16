import { proxyAuthRequest } from '../_shared';

/**
 * POST /api/auth/forgot-password
 * Proxies to POST /auth/forgot-password on the Python backend.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email) {
      return new Response(
        JSON.stringify({ error: 'El correo electronico es obligatorio.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    return proxyAuthRequest('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  } catch {
    return new Response(
      JSON.stringify({ error: 'Cuerpo de peticion invalido.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }
}
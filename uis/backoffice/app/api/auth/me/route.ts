import { proxyAuthRequest } from '../_shared';

/**
 * GET /api/auth/me?id=1
 * Proxies to GET /users/{id} on the Python backend, forwarding the
 * Authorization header from the client.
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const userId = searchParams.get('id');

  if (!userId) {
    return new Response(
      JSON.stringify({ error: 'id es obligatorio.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }

  const authHeader = request.headers.get('authorization') || undefined;

  return proxyAuthRequest(`/users/${userId}`, {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

/**
 * PUT /api/auth/me?id=1
 * Proxies to PUT /users/{id} on the Python backend.
 */
export async function PUT(request: Request) {
  const { searchParams } = new URL(request.url);
  const userId = searchParams.get('id');

  if (!userId) {
    return new Response(
      JSON.stringify({ error: 'id es obligatorio.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }

  try {
    const body = await request.json();
    const authHeader = request.headers.get('authorization') || undefined;

    return proxyAuthRequest(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
      headers: authHeader ? { Authorization: authHeader } : {},
    });
  } catch {
    return new Response(
      JSON.stringify({ error: 'Cuerpo de peticion invalido.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }
}
